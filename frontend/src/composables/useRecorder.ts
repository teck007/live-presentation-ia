import { ref } from "vue";
import { createPrefilter } from "./useAudioPrefilter";
import type { AudioPrefilter } from "./useAudioPrefilter";

// MimeTypes preferidos en orden: Opus en WebM, luego MP4 (Safari).
const PREFERRED_MIME_TYPES = ["audio/webm;codecs=opus", "audio/mp4"];

/** Elige el primer mimeType soportado por el navegador. */
function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const mime of PREFERRED_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return "";
}

/**
 * Composable para grabar audio con el microfono.
 * Expone estado reactivo y funciones start/stop con limpieza de pistas.
 */
export function useRecorder() {
  const isRecording = ref(false);
  const blob = ref<Blob | null>(null);
  const audioUrl = ref<string | null>(null);
  const elapsed = ref(0);
  const error = ref<string | null>(null);

  let recorder: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let chunks: BlobPart[] = [];
  let timer: ReturnType<typeof setInterval> | null = null;
  let activeMimeType = "";
  let filterContext: AudioContext | null = null;
  let filterSource: MediaStreamAudioSourceNode | null = null;
  let filterDest: MediaStreamAudioDestinationNode | null = null;
  let filter: AudioPrefilter | null = null;

function readBatchPrefilterEnabled(): boolean {
  try {
    const raw = localStorage.getItem("prefilter.enabled");
    return raw === null ? true : raw !== "false";
  } catch {
    return true;
  }
}

function readBatchPrefilterThreshold(): number {
  try {
    const raw = localStorage.getItem("prefilter.threshold");
    const v = raw === null ? 0.02 : Number(raw);
    if (!Number.isFinite(v)) return 0.02;
    return Math.min(0.05, Math.max(0.01, v));
  } catch {
    return 0.02;
  }
}

  /** Libera el object URL anterior para no acumular memoria. */
  function revokeUrl() {
    if (audioUrl.value) {
      URL.revokeObjectURL(audioUrl.value);
      audioUrl.value = null;
    }
  }

  /** Detiene el cronometro y las pistas del microfono. */
  function cleanupTracks() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    try {
      filter?.disconnect();
    } catch {
      // Ignora errores de limpieza.
    }
    filter = null;
    try {
      filterSource?.disconnect();
    } catch {
      // Ignora errores de limpieza.
    }
    filterSource = null;
    filterDest = null;
    if (filterContext) {
      const ctx = filterContext;
      filterContext = null;
      void ctx.close().catch(() => undefined);
    }
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
      stream = null;
    }
    recorder = null;
  }

  /** Inicia la grabacion pidiendo permiso de microfono. */
  async function start() {
    error.value = null;
    if (isRecording.value) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      error.value =
        "Este navegador no soporta grabación de audio. Usa Chrome, Edge o Safari reciente.";
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch {
      error.value =
        "No se pudo acceder al micrófono. Revisa los permisos del navegador.";
      return;
    }
    chunks = [];
    activeMimeType = pickMimeType();
    // Fuente para MediaRecorder: prefiltrada si es posible, original si falla.
    let recordStream: MediaStream = stream;
    try {
      if (readBatchPrefilterEnabled() && typeof AudioContext !== "undefined") {
        filterContext = new AudioContext();
        filter = createPrefilter(filterContext);
        filter.setThreshold(readBatchPrefilterThreshold());
        filter.setEnabled(true);
        filterSource = filterContext.createMediaStreamSource(stream);
        filterDest = filterContext.createMediaStreamDestination();
        filterSource.connect(filter.input);
        filter.output.connect(filterDest);
        recordStream = filterDest.stream;
      }
    } catch {
      // Fallback: sigue con el stream original sin filtro.
      try {
        filter?.disconnect();
      } catch {
        // Ignora errores de limpieza.
      }
      filter = null;
      filterSource = null;
      filterDest = null;
      if (filterContext) {
        const ctx = filterContext;
        filterContext = null;
        void ctx.close().catch(() => undefined);
      }
      recordStream = stream;
    }
    try {
      recorder = activeMimeType
        ? new MediaRecorder(recordStream, { mimeType: activeMimeType })
        : new MediaRecorder(recordStream);
    } catch {
      error.value = "No se pudo iniciar la grabación en este navegador.";
      cleanupTracks();
      return;
    }

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      const type = activeMimeType || recorder?.mimeType || "audio/webm";
      const result = new Blob(chunks, { type });
      chunks = [];
      revokeUrl();
      blob.value = result;
      audioUrl.value = URL.createObjectURL(result);
      cleanupTracks();
      isRecording.value = false;
    };
    recorder.onerror = () => {
      error.value = "Ocurrió un error durante la grabación.";
      cleanupTracks();
      isRecording.value = false;
    };

    revokeUrl();
    blob.value = null;
    elapsed.value = 0;
    recorder.start();
    isRecording.value = true;
    const startedAt = Date.now();
    timer = setInterval(() => {
      elapsed.value = Math.floor((Date.now() - startedAt) / 1000);
    }, 500);
  }

  /** Detiene la grabacion y genera el blob final. */
  function stop() {
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    } else {
      cleanupTracks();
      isRecording.value = false;
    }
  }

  /** Limpia el blob actual y libera recursos. */
  function clear() {
    revokeUrl();
    blob.value = null;
    elapsed.value = 0;
    error.value = null;
  }

  /** Devuelve la extension sugerida segun el mimeType usado. */
  function suggestedExtension(): string {
    const type = blob.value?.type ?? activeMimeType;
    if (type.includes("mp4")) return "mp4";
    return "webm";
  }

  return {
    isRecording,
    blob,
    audioUrl,
    elapsed,
    error,
    start,
    stop,
    clear,
    suggestedExtension,
  };
}
