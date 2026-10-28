import { ref } from "vue";
import { generateSlide } from "../api/presentation";
import type { SlideItem, TranscriptItem } from "../types";

// Evita saturar al LLM: espera este silencio antes de enviar el turno final.
const DEBOUNCE_MS = 4000;

/**
 * Cola de turnos finales -> POST /api/presentations/generate -> slides[].
 * El LLM devuelve JSON plano (layout + texto); el diseño vive en SlideCanvas.
 */
export function useLivePresentation() {
  const slides = ref<SlideItem[]>([]);
  const pending = ref(0);
  const error = ref<string | null>(null);
  const lastFiltered = ref(false);

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let queued: TranscriptItem | null = null;
  let topic = "";
  // Dedupe opción B: red de seguridad por turnId (el origen ya evita el doble push).
  const seenTurnIds = new Set<string>();
  let lastSentKey = "";

  function setTopic(value: string) {
    topic = value.trim();
  }

  function clear() {
    slides.value = [];
    error.value = null;
    lastFiltered.value = false;
    queued = null;
    seenTurnIds.clear();
    lastSentKey = "";
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    pending.value = 0;
  }

  async function flush() {
    const item = queued;
    queued = null;
    if (!item || !item.text.trim()) return;
    // Segunda barrera: mismo turnId o mismo texto ya enviado → no repite consulta al LLM.
    const key = `${item.sessionId ?? "turn"}|${item.text.trim()}`;
    if (item.sessionId && seenTurnIds.has(item.sessionId)) return;
    if (key === lastSentKey) return;
    if (item.sessionId) seenTurnIds.add(item.sessionId);
    lastSentKey = key;
    pending.value += 1;
    error.value = null;
    try {
      const res = await generateSlide({
        transcript: item.text,
        topic,
        keywords: item.keywords ?? [],
      });
      lastFiltered.value = res.filtered;
      if (res.filtered) return;
      slides.value.push({
        ...res,
        id: `${item.sessionId ?? "turn"}-${Date.now()}`,
        timestamp: Date.now(),
      });
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : "No se pudo generar el slide.";
    } finally {
      pending.value = Math.max(0, pending.value - 1);
    }
  }

  /** Encola un turno final; se envía tras DEBOUNCE_MS sin nuevos turnos. */
  function queueTranscript(item: TranscriptItem) {
    queued = item;
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => void flush(), DEBOUNCE_MS);
  }

  return {
    slides,
    pending,
    error,
    lastFiltered,
    setTopic,
    queueTranscript,
    clear,
  };
}
