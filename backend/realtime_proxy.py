"""Realtime WS proxy: frontend <-> backend <-> Meta Muse Voice realtime ASR.

Protocol frontend<->backend:
  frontend -> backend : binary PCM signed 16-bit LE mono 24kHz (~80ms frames)
  frontend -> backend : JSON control {"type": "idle_pause"} (hint) | {"type": "end"}
  backend  -> frontend: Meta events forwarded as-is (speechStart/transcript/
                             speechEnd/speechComplete) plus control events
                             {"type":"paused"} / {"type":"resumed"} /
                             {"type":"upstream_close","code":int} /
                             {"type":"error","message":str}

Silence state machine (backend is authoritative):
  STREAMING: forward PCM to Meta. Short trailing silence (< pause threshold)
             still forwards PCM silence so Meta can emit speechComplete.
  PAUSED (prolonged silence >= REALTIME_SILENCE_PAUSE_MS, default 15000ms):
             send {"type":"endStream"} upstream, drain pending events, close
             upstream 1000. front<->backend socket stays open. Upstream gets
             ~0 bytes while paused. Keep a PRE_ROLL_MS (default 500ms) ring
             buffer; on WAKE (150-250ms confirmed voice) open a NEW upstream
             session, send pre-roll first, then resume streaming.
"""
import asyncio
import json
import logging
import math
import os
import struct
import uuid
from collections import deque

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("realtime_proxy")

META_REALTIME_URL_DEFAULT = "wss://api.meta.ai/v1/asr/realtime"
ASR_MODEL_DEFAULT = "muse-voice-transcribe-1.0"

SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
FRAME_BYTES = 3840  # 80ms @ 24kHz mono int16
MAX_BACKLOG_MS = 5000
MAX_QUEUE_FRAMES = (MAX_BACKLOG_MS * SAMPLE_RATE * BYTES_PER_SAMPLE) // 1000 // FRAME_BYTES  # ~62
DRAIN_TIMEOUT_S = 4.0
WATCHDOG_INTERVAL_S = 0.2
# 150-250ms confirmed voice to wake: with 80ms frames -> 3 voiced frames.
WAKE_VOICED_FRAMES = 3


def get_config() -> dict:
    try:
        silence_pause_ms = int(os.getenv("REALTIME_SILENCE_PAUSE_MS", "15000"))
    except ValueError:
        silence_pause_ms = 15000
    silence_pause_ms = max(5000, min(60000, silence_pause_ms))
    try:
        pre_roll_ms = int(os.getenv("REALTIME_PRE_ROLL_MS", "500"))
    except ValueError:
        pre_roll_ms = 500
    pre_roll_ms = max(0, min(2000, pre_roll_ms))
    try:
        vad_threshold = float(os.getenv("REALTIME_VAD_THRESHOLD", "0.02"))
    except ValueError:
        vad_threshold = 0.02
    return {
        "silence_pause_ms": silence_pause_ms,
        "pre_roll_ms": pre_roll_ms,
        "vad_threshold": vad_threshold,
        "model": os.getenv("ASR_MODEL", ASR_MODEL_DEFAULT).strip() or ASR_MODEL_DEFAULT,
        "url": os.getenv("META_REALTIME_URL", META_REALTIME_URL_DEFAULT).strip()
        or META_REALTIME_URL_DEFAULT,
    }


def get_api_key() -> str:
    return os.getenv("MODEL_API_KEY", "").strip()


def frame_rms(frame: bytes) -> float:
    """RMS normalizado 0..1 de un frame PCM16LE. Silencio exacto -> 0.0."""
    if not frame:
        return 0.0
    n = len(frame) // 2
    if n == 0:
        return 0.0
    fmt = f"<{n}h"
    try:
        samples = struct.unpack(fmt, frame[: n * 2])
    except struct.error:
        return 0.0
    acc = 0.0
    for s in samples:
        v = s / 32768.0
        acc += v * v
    return math.sqrt(acc / n)


def is_voiced(frame: bytes, threshold: float) -> bool:
    return frame_rms(frame) >= threshold


def enrich_event(obj: dict) -> dict:
    """Add cleaned/topic/keywords to final transcript events (additive only)."""
    try:
        # Lazy import: top-level would cycle via backend.presentation_api.__init__
        # (controllers.transcription imports handle_frontend_socket from here).
        from backend.presentation_api.utils.topic_cleaner import analyze_topic

        t = obj.get("type")
        if t == "speechComplete":
            raw = obj.get("transcript") or ""
            if isinstance(raw, str) and raw.strip():
                a = analyze_topic(raw)
                obj = {**obj, "cleaned": a["cleaned"], "topic": a["topic"], "keywords": a["keywords"]}
        elif t == "transcript" and obj.get("final") is True:
            raw = obj.get("transcript") or ""
            if isinstance(raw, str) and raw.strip():
                a = analyze_topic(raw)
                obj = {**obj, "cleaned": a["cleaned"], "topic": a["topic"], "keywords": a["keywords"]}
    except Exception:  # noqa: BLE001
        pass
    return obj


def build_handshake(api_key: str, model: str) -> str:
    return json.dumps(
        {
            "authorization": {"accessToken": f"Bearer {api_key}"},
            "audioEncoding": "PCM_24KHZ",
            "model": model,
            "mode": "ENDPOINTING",
            "languageBias": ["Spanish"],
            "partialMode": "CUMULATIVE",
            "emitAudioProgress": False,
        }
    )


class RealtimeBridge:
    """Puente de una sesion frontend<->Meta con maquina de pausa por silencio."""

    def __init__(self, frontend: WebSocket, config: dict):
        self.frontend = frontend
        self.config = config
        self.send_lock = asyncio.Lock()
        self.upstream = None
        self.upstream_session_id: str | None = None
        self.streaming = False  # True = upstream abierto y recibiendo audio
        self.closed = False
        self.audio_queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_FRAMES)
        self.pre_roll = deque()  # bytes, cap PRE_ROLL_MS
        self.pre_roll_bytes = 0
        self.pre_roll_cap = (
            config["pre_roll_ms"] * SAMPLE_RATE * BYTES_PER_SAMPLE // 1000
        )
        self.last_voice_at = asyncio.get_event_loop().time()
        self.wake_counter = 0
        self.consumer_task: asyncio.Task | None = None
        self.watchdog_task: asyncio.Task | None = None
        self.relay_task: asyncio.Task | None = None

    async def send_front(self, obj: dict) -> None:
        async with self.send_lock:
            await self.frontend.send_text(json.dumps(obj))

    def _pre_roll_push(self, frame: bytes) -> None:
        if self.pre_roll_cap <= 0:
            return
        self.pre_roll.append(frame)
        self.pre_roll_bytes += len(frame)
        while self.pre_roll_bytes > self.pre_roll_cap and self.pre_roll:
            old = self.pre_roll.popleft()
            self.pre_roll_bytes -= len(old)

    def _pre_roll_drain(self) -> list[bytes]:
        frames = list(self.pre_roll)
        self.pre_roll.clear()
        self.pre_roll_bytes = 0
        return frames

    async def open_upstream(self) -> bool:
        """Abre una NUEVA sesion upstream (sin resume token) y hace handshake."""
        import websockets
        from websockets.exceptions import WebSocketException

        api_key = get_api_key()
        if not api_key:
            await self.send_front(
                {"type": "error", "message": "MODEL_API_KEY no configurada en el backend."}
            )
            return False
        session_id = uuid.uuid4().hex
        url = f"{self.config['url']}?sessionId={session_id}"
        try:
            # websockets>=13: extra_headers como dict; handshake dentro de 10s.
            ws = await websockets.connect(url, max_size=4 * 1024 * 1024)
            await ws.send(build_handshake(api_key, self.config["model"]))
        except WebSocketException as exc:
            logger.warning("No se pudo abrir upstream realtime: %s", exc)
            await self.send_front(
                {"type": "error", "message": f"No se pudo conectar con Meta ASR: {exc}"}
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error abriendo upstream realtime: %s", exc)
            await self.send_front(
                {"type": "error", "message": f"No se pudo conectar con Meta ASR: {exc}"}
            )
            return False
        self.upstream = ws
        self.upstream_session_id = session_id
        self.streaming = True
        self.last_voice_at = asyncio.get_event_loop().time()
        self.wake_counter = 0
        # Drena pre-roll primero para no cortar el inicio de la frase.
        for frame in self._pre_roll_drain():
            try:
                await ws.send(frame)
            except Exception:  # noqa: BLE001
                break
        self._start_relay()
        return True

    def _start_relay(self) -> None:
        if self.relay_task and not self.relay_task.done():
            return
        self.relay_task = asyncio.create_task(self._relay_loop())

    async def _relay_loop(self) -> None:
        """Reenvia eventos de Meta al frontend; detecta cierres y codigos."""
        ws = self.upstream
        if ws is None:
            return
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    continue  # eventos son JSON text; ignora binarios
                try:
                    await self.send_front(enrich_event(json.loads(message)))
                except Exception:  # noqa: BLE001
                    # Si el frontend se cerro, termina el relay.
                    break
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None)
            logger.info("Upstream relay terminado code=%s err=%s", code, exc)
            if self.streaming and not self.closed:
                await self._handle_upstream_close(code, str(exc))
            return
        # El async-for termino: el servidor cerro. Extrae codigo si existe.
        code = None
        try:
            code = getattr(ws, "close_code", None)
        except Exception:  # noqa: BLE001
            code = None
        if self.streaming and not self.closed:
            await self._handle_upstream_close(code, "upstream cerrado por el servidor")

    async def _handle_upstream_close(self, code, reason: str) -> None:
        self.streaming = False
        try:
            await self.send_front({"type": "upstream_close", "code": code, "reason": reason})
        except Exception:  # noqa: BLE001
            pass
        # Politica de reintento segun codigo Meta:
        # 1008 = no reintentar la misma sesion; 1011/1013 = backoff + NUEVA sesion.
        if code in (1011, 1013):
            await asyncio.sleep(1.0)
            if not self.closed and not self.streaming:
                # Reabre solo si hay actividad de voz reciente o llega audio nuevo;
                # por ahora reabre de inmediato para no perder el turno.
                await self.open_upstream()
        elif code not in (1000, None):
            # 1008 u otros: no reintenta solo; el usuario reinicia.
            pass

    async def pause_upstream(self, reason: str = "idle_pause") -> None:
        """Pausa prolongada: endStream, drena eventos, cierra upstream 1000."""
        ws = self.upstream
        self.streaming = False
        if ws is None:
            return
        self.upstream = None
        try:
            await ws.send(json.dumps({"type": "endStream"}))
        except Exception:  # noqa: BLE001
            pass
        # Drena eventos pendientes (p. ej. speechComplete final) con timeout.
        try:
            async def _drain() -> None:
                try:
                    async for message in ws:
                        if isinstance(message, bytes):
                            continue
                        try:
                            await self.send_front(enrich_event(json.loads(message)))
                        except Exception:  # noqa: BLE001
                            break
                except Exception:  # noqa: BLE001
                    pass

            await asyncio.wait_for(_drain(), timeout=DRAIN_TIMEOUT_S)
        except asyncio.TimeoutError:
            pass
        except Exception:  # noqa: BLE001
            pass
        try:
            await ws.close(code=1000)
        except Exception:  # noqa: BLE001
            pass
        if self.relay_task and not self.relay_task.done():
            self.relay_task.cancel()
        try:
            await self.send_front({"type": "paused", "reason": reason})
        except Exception:  # noqa: BLE001
            pass

    async def _consumer_loop(self) -> None:
        """Saca frames de la cola acotada (5s) y los envia a Meta."""
        while not self.closed:
            try:
                frame = await self.audio_queue.get()
            except asyncio.CancelledError:
                break
            ws = self.upstream
            if not self.streaming or ws is None:
                continue  # en pausa: el reader ya gestiona pre-roll; descarta
            try:
                await ws.send(frame)
            except Exception as exc:  # noqa: BLE001
                logger.info("Fallo envio a upstream: %s", exc)
                self.streaming = False

    async def _watchdog_loop(self) -> None:
        """Detecta silencio continuo >= umbral y dispara la pausa prolongada."""
        threshold_ms = self.config["silence_pause_ms"]
        while not self.closed:
            await asyncio.sleep(WATCHDOG_INTERVAL_S)
            if not self.streaming or self.upstream is None:
                continue
            now = asyncio.get_event_loop().time()
            if (now - self.last_voice_at) * 1000 >= threshold_ms:
                logger.info("Pausa prolongada tras %d ms de silencio", threshold_ms)
                await self.pause_upstream(reason="prolonged_silence")

    def _enqueue_or_drop(self, frame: bytes) -> None:
        try:
            self.audio_queue.put_nowait(frame)
        except asyncio.QueueFull:
            try:
                self.audio_queue.get_nowait()  # descarta el mas viejo (max 5s)
                self.audio_queue.put_nowait(frame)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    async def on_audio_frame(self, frame: bytes) -> None:
        voiced = is_voiced(frame, self.config["vad_threshold"])
        now = asyncio.get_event_loop().time()
        if voiced:
            self.last_voice_at = now
        if not self.streaming or self.upstream is None:
            # En pausa: solo guarda pre-roll y espera voz confirmada (WAKE).
            self._pre_roll_push(frame)
            if voiced:
                self.wake_counter += 1
            else:
                self.wake_counter = 0
            if self.wake_counter >= WAKE_VOICED_FRAMES:
                self.wake_counter = 0
                ok = await self.open_upstream()
                if ok:
                    try:
                        await self.send_front({"type": "resumed", "reason": "voice"})
                    except Exception:  # noqa: BLE001
                        pass
            return
        self._enqueue_or_drop(frame)

    async def on_control(self, obj: dict) -> None:
        ctype = obj.get("type")
        if ctype == "idle_pause":
            if self.streaming:
                await self.pause_upstream(reason="idle_pause")
        elif ctype == "end":
            await self.pause_upstream(reason="end")
            self.closed = True
            try:
                await self.frontend.close(code=1000)
            except Exception:  # noqa: BLE001
                pass

    async def run(self) -> None:
        await self.frontend.accept()
        if not get_api_key():
            await self.send_front(
                {"type": "error", "message": "MODEL_API_KEY no configurada en el backend."}
            )
            await self.frontend.close(code=1008)
            return
        ok = await self.open_upstream()
        if not ok:
            try:
                await self.frontend.close(code=1011)
            except Exception:  # noqa: BLE001
                pass
            return
        self.consumer_task = asyncio.create_task(self._consumer_loop())
        self.watchdog_task = asyncio.create_task(self._watchdog_loop())
        try:
            while not self.closed:
                message = await self.frontend.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    data = message["bytes"]
                    # Acepta cualquier tamano; acumula por FRAME_BYTES para VAD estable.
                    # Normalmente el frontend ya envia ~80ms (3840 bytes).
                    offset = 0
                    while offset < len(data):
                        chunk = data[offset : offset + FRAME_BYTES]
                        offset += FRAME_BYTES
                        # Rellena frames cortos con silencio para RMS estable.
                        if len(chunk) < FRAME_BYTES:
                            chunk = chunk + b"\x00" * (FRAME_BYTES - len(chunk))
                        await self.on_audio_frame(chunk)
                elif message.get("text") is not None:
                    try:
                        obj = json.loads(message["text"])
                    except json.JSONDecodeError:
                        continue
                    if isinstance(obj, dict):
                        # Permite ajustar el umbral de pausa por sesion (5s-60s).
                        if obj.get("type") == "config" and "silencePauseMs" in obj:
                            try:
                                v = int(obj["silencePauseMs"])
                                self.config["silence_pause_ms"] = max(5000, min(60000, v))
                            except (ValueError, TypeError):
                                pass
                        else:
                            await self.on_control(obj)
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.info("Frontend WS terminado: %s", exc)
        finally:
            self.closed = True
            for task in (self.consumer_task, self.watchdog_task):
                if task and not task.done():
                    task.cancel()
            # Cierra upstream sin endStream ruidoso si ya estaba en pausa.
            ws = self.upstream
            self.upstream = None
            self.streaming = False
            if ws is not None:
                try:
                    await ws.send(json.dumps({"type": "endStream"}))
                except Exception:  # noqa: BLE001
                    pass
                try:
                    await ws.close(code=1000)
                except Exception:  # noqa: BLE001
                    pass


async def handle_frontend_socket(frontend: WebSocket) -> None:
    """Punto de entrada del endpoint WS /ws/transcribe."""
    bridge = RealtimeBridge(frontend, get_config())
    await bridge.run()
