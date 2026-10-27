<template>
  <section class="flex flex-col gap-3">
    <div class="flex justify-center gap-2">
      <button
        v-if="!isRecording"
        type="button"
        class="rounded-lg px-5 py-2.5 transition bg-red-700 text-white hover:bg-red-800"
        @click="emit('start')"
      >
        Grabar
      </button>
      <button
        v-else
        type="button"
        class="rounded-lg px-5 py-2.5 transition bg-gray-500 text-white hover:bg-gray-600"
        @click="emit('stop')"
      >
        Detener ({{ elapsed }}s)
      </button>
      <button
        v-if="audioUrl && !isRecording"
        type="button"
        class="rounded-lg px-5 py-2.5 transition border border-neutral-300 bg-transparent hover:bg-neutral-100"
        @click="emit('clear')"
      >
        Limpiar
      </button>
    </div>

    <p v-if="isRecording" class="font-bold text-red-700 animate-pulse">
      Grabando... {{ elapsed }}s
    </p>
    <audio
      v-if="audioUrl && !isRecording"
      :src="audioUrl"
      controls
      class="w-full"
    />
    <p v-if="recorderError" class="rounded-md bg-red-50 p-2 text-red-700">
      {{ recorderError }}
    </p>
  </section>
</template>

<script setup lang="ts">
// Componente de grabacion: solo presenta estado y emite eventos.
// La logica de MediaRecorder vive en el composable useRecorder.
defineProps<{
  isRecording: boolean;
  audioUrl: string | null;
  elapsed: number;
  recorderError: string | null;
}>();

const emit = defineEmits<{
  (e: "start"): void;
  (e: "stop"): void;
  (e: "clear"): void;
}>();
</script>
