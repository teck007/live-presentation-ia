<template>
  <main
    class="mx-auto max-w-2xl px-4 py-8 text-center font-sans min-h-screen bg-neutral-50 text-slate-800 antialiased"
  >
    <h1 class="text-3xl font-bold tracking-tight">
      Transcripción de voz en vivo
    </h1>
    <p class="mt-2 text-neutral-500">
      Habla y mira el texto en tiempo real, o graba por lotes como alternativa.
    </p>

    <section class="mt-6 rounded-lg border border-neutral-200 bg-white p-4 text-left shadow-sm">
      <div class="flex flex-wrap items-center gap-3">
        <h2 class="text-lg font-semibold">Transcripción en vivo</h2>
        <span
          class="rounded-full px-3 py-1 text-sm font-medium"
          :class="statusPillClass"
          role="status"
        >
          {{ statusLabel }}
        </span>
      </div>

      <div class="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-lg bg-green-600 px-5 py-2.5 text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-300"
          :disabled="liveActive"
          @click="live.start()"
        >
          Iniciar en vivo
        </button>
        <button
          type="button"
          class="rounded-lg bg-neutral-600 px-5 py-2.5 text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
          :disabled="!liveActive"
          @click="live.stop()"
        >
          Detener
        </button>
        <button
          type="button"
          class="rounded-lg bg-transparent px-4 py-2.5 text-neutral-500 transition hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="liveActive || (live.finalItems.value.length === 0 && !live.partialText.value)"
          @click="live.clearLive()"
        >
          Limpiar
        </button>
      </div>

      <div class="mt-4 rounded-md border border-neutral-200 bg-neutral-50 p-3">
        <label class="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            class="size-4 accent-green-600"
            :checked="live.prefilterEnabled.value"
            @change="live.setPrefilterEnabled(($event.target as HTMLInputElement).checked)"
          />
          Reducción de ruido
        </label>
        <label class="mt-3 block text-sm text-slate-600">
          Cercanía
          <span class="block text-xs text-neutral-400">Más a la derecha = solo muy cercano</span>
          <input
            type="range"
            min="0.01"
            max="0.05"
            step="0.005"
            class="mt-1 w-full accent-green-600"
            :value="live.prefilterThreshold.value"
            :disabled="!live.prefilterEnabled.value"
            @input="live.setPrefilterThreshold(Number(($event.target as HTMLInputElement).value))"
          />
        </label>
        <div class="mt-2 flex items-center gap-2">
          <span class="text-xs text-neutral-400">Nivel</span>
          <div class="h-2 flex-1 overflow-hidden rounded-full bg-neutral-200" role="meter" aria-label="Nivel de micrófono">
            <div
              class="h-full rounded-full bg-green-500 transition-[width]"
              :style="{ width: `${Math.min(100, Math.round(live.prefilterLevel.value * 400))}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div v-if="live.notice.value" class="mt-3 rounded-md bg-blue-50 p-3 text-sm text-blue-800" role="status">
        {{ live.notice.value }}
      </div>
      <div v-if="live.error.value" class="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
        {{ live.error.value }}
        <span class="mt-1 block text-red-600">Puedes usar el grabador por lotes de abajo como alternativa.</span>
      </div>

      <div
        v-if="live.partialText.value"
        class="mt-3 rounded-md border-l-4 border-blue-400 bg-neutral-100 p-3 text-left text-neutral-600 italic"
        role="status"
        aria-live="polite"
      >
        {{ live.partialText.value }}<span class="animate-pulse">…</span>
      </div>
      <p v-else-if="liveActive" class="mt-3 text-sm text-neutral-400">
        {{ live.serverPaused.value ? "En pausa por silencio prolongado. Habla para retomar." : "Escuchando… habla para transcribir." }}
      </p>

      <ul v-if="live.finalItems.value.length > 0" class="mt-3 space-y-2 text-left">
        <li
          v-for="(item, index) in live.finalItems.value"
          :key="`${item.sessionId ?? 'turn'}-${index}`"
          class="rounded-md bg-green-50 p-3 text-green-800"
        >
          {{ item.text }}
        </li>
      </ul>
    </section>

    <section class="mt-6 rounded-lg border border-neutral-200 bg-white p-4 text-left shadow-sm">
      <h2 class="text-lg font-semibold">Grabador por lotes (alternativa)</h2>
      <p class="mt-1 text-sm text-neutral-500">
        Graba tu voz con el micrófono y presiona Transcribir para obtener el
        texto en español.
      </p>

      <AudioRecorder
        :is-recording="isRecording"
        :audio-url="audioUrl"
        :elapsed="elapsed"
        :recorder-error="recorderError"
        @start="start"
        @stop="stop"
        @clear="handleClear"
      />

      <div class="mt-4">
        <button
          type="button"
          class="rounded-lg bg-blue-600 px-6 py-3 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
          :disabled="!blob || loading"
          @click="handleTranscribe"
        >
          {{ loading ? "Transcribiendo..." : "Transcribir" }}
        </button>
      </div>

      <div v-if="loading" class="mt-4 flex items-center justify-center gap-2" role="status">
        <span
          class="inline-block size-[18px] animate-spin rounded-full border-[3px] border-neutral-300 border-t-blue-600"
          aria-hidden="true"
        ></span>
        Transcribiendo...
      </div>

      <div v-if="resultText" class="mt-4 rounded-md bg-green-50 p-3 text-left text-green-800" role="status">
        {{ resultText }}
      </div>
      <div v-if="isEmptyWarning" class="mt-4 rounded-md bg-yellow-50 p-3 text-yellow-800" role="status">
        Transcripción vacía.
      </div>
      <div v-if="apiError" class="mt-4 rounded-md bg-red-50 p-3 text-red-700" role="alert">{{ apiError }}</div>
    </section>

    <TranscriptHistory :items="history" />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import AudioRecorder from "./components/AudioRecorder.vue";
import TranscriptHistory from "./components/TranscriptHistory.vue";
import { transcribeAudio } from "./api/transcribe";
import { useRecorder } from "./composables/useRecorder";
import { useRealtimeTranscription } from "./composables/useRealtimeTranscription";
import type { TranscriptItem } from "./types";

// Sesion de transcripcion en vivo (realtime WS).
const live = useRealtimeTranscription();

const liveActive = computed(
  () =>
    live.status.value === "connecting" ||
    live.status.value === "listening" ||
    live.status.value === "speaking" ||
    live.status.value === "paused",
);

const statusLabel = computed(() => {
  switch (live.status.value) {
    case "connecting":
      return "Conectando…";
    case "listening":
      return "Escuchando";
    case "speaking":
      return "Hablando";
    case "paused":
      return "En pausa";
    case "error":
      return "Error";
    default:
      return "Inactivo";
  }
});

const statusPillClass = computed(() => {
  switch (live.status.value) {
    case "listening":
      return "bg-blue-100 text-blue-800";
    case "speaking":
      return "bg-green-100 text-green-800";
    case "paused":
      return "bg-yellow-100 text-yellow-800";
    case "connecting":
      return "bg-neutral-200 text-neutral-700";
    case "error":
      return "bg-red-100 text-red-700";
    default:
      return "bg-neutral-100 text-neutral-500";
  }
});

// Estado de grabacion por lotes provisto por el composable (fallback).
const {
  isRecording,
  blob,
  audioUrl,
  elapsed,
  error: recorderError,
  start,
  stop,
  clear,
  suggestedExtension,
} = useRecorder();

// Estado de la transcripcion y del historial (mas reciente primero).
const loading = ref(false);
const resultText = ref("");
const isEmptyWarning = ref(false);
const apiError = ref<string | null>(null);
const history = ref<TranscriptItem[]>([]);

const canTranscribe = computed(() => blob.value !== null && !loading.value);

function handleClear() {
  clear();
  resultText.value = "";
  isEmptyWarning.value = false;
  apiError.value = null;
}

/** Envia el audio grabado al backend y actualiza el historial. */
async function handleTranscribe() {
  if (!canTranscribe.value || !blob.value) return;
  loading.value = true;
  resultText.value = "";
  isEmptyWarning.value = false;
  apiError.value = null;
  try {
    const filename = `grabacion.${suggestedExtension()}`;
    const data = await transcribeAudio(blob.value, filename);
    const text = data.text.trim();
    history.value.unshift({ text, sessionId: data.sessionId ?? null });
    if (text) {
      resultText.value = text;
    } else {
      isEmptyWarning.value = true;
    }
  } catch (error) {
    apiError.value =
      error instanceof Error ? error.message : "Error desconocido.";
  } finally {
    loading.value = false;
  }
}
</script>
