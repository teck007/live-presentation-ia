"""Tests del proxy de transcripcion. No requieren ffmpeg ni red real."""
import io
import shutil
import wave
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.presentation_api.controllers.transcription as transcription
from backend.presentation_api import app


def generar_wav_1s() -> bytes:
    """Genera un WAV valido de 1 segundo (tono 440 Hz, mono 16-bit 24 kHz)."""
    buffer = io.BytesIO()
    sample_rate = 24000
    n_frames = sample_rate  # 1 segundo
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        import math
        import struct

        for i in range(n_frames):
            sample = int(10000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def client_sin_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    return TestClient(app)


def test_health_sin_key(client_sin_key):
    resp = client_sin_key.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model"] == "muse-voice-transcribe-1.0"
    assert body["api_key_configured"] is False


def test_transcribe_sin_key_da_503(client_sin_key):
    wav = generar_wav_1s()
    resp = client_sin_key.post(
        "/api/transcribe", files={"file": ("audio.wav", wav, "audio/wav")}
    )
    assert resp.status_code == 503
    assert "MODEL_API_KEY" in resp.json()["detail"]


def test_transcribe_ok_mockeado(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "LLM_test")
    client = TestClient(app)
    wav = generar_wav_1s()

    fake = FakeResponse(
        200,
        {
            "transcript": "hola mundo",
            "sessionId": "abc123",
            "audioDurationMs": 1000,
            "turns": [],
        },
    )
    mock_post = AsyncMock(return_value=fake)

    with (
        patch.object(transcription, "convert_audio_bytes", return_value=wav),
        patch("httpx.AsyncClient.post", mock_post),
    ):
        resp = client.post(
            "/api/transcribe", files={"file": ("audio.wav", wav, "audio/wav")}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"] == "hola mundo"
    assert body["sessionId"] == "abc123"

    # Verifica que se llamo a Meta con multipart y auth.
    _, kwargs = mock_post.call_args
    assert "files" in kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer LLM_test"
    assert "request" in kwargs["files"]
    assert "audio" in kwargs["files"]


def test_error_meta_propagado(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "LLM_test")
    client = TestClient(app)
    wav = generar_wav_1s()

    fake = FakeResponse(429, {"error": "rate limited"}, text='{"error":"rate limited"}')
    mock_post = AsyncMock(return_value=fake)

    with (
        patch.object(transcription, "convert_audio_bytes", return_value=wav),
        patch("httpx.AsyncClient.post", mock_post),
    ):
        resp = client.post(
            "/api/transcribe", files={"file": ("audio.wav", wav, "audio/wav")}
        )

    assert resp.status_code == 429
    assert "429" in resp.json()["detail"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no instalado")
def test_conversion_real_si_ffmpeg_existe():
    wav = generar_wav_1s()
    out = transcription.convert_audio_bytes(wav)
    # Un WAV valido empieza con RIFF.
    assert out[:4] == b"RIFF"
