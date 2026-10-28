<template>
  <section v-if="items.length > 0" class="mt-6 text-left">
    <h2 class="text-xl font-semibold">Historial ({{ items.length }})</h2>
    <p class="rounded-md bg-blue-50 p-2.5">
      <strong>Último:</strong> {{ items[0]?.text }}
    </p>
    <ol class="list-decimal space-y-2 pl-5">
      <li v-for="(item, index) in items" :key="index">
        <p>{{ item.text }}</p>
        <div v-if="item.keywords?.length" class="mt-1 flex flex-wrap gap-1.5">
          <span
            v-for="(keyword, kIndex) in item.keywords"
            :key="`${keyword}-${kIndex}`"
            class="rounded-full bg-neutral-200 px-2.5 py-0.5 text-xs font-medium text-neutral-700"
          >
            {{ keyword }}
          </span>
        </div>
        <small v-if="item.sessionId" class="text-sm text-neutral-500"
          >sessionId: {{ item.sessionId }}</small
        >
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import type { TranscriptItem } from "../types";

// Muestra el historial con el mas reciente primero.
defineProps<{
  items: TranscriptItem[];
}>();
</script>
