// Prefiltro de ruido frontend (WebAudio nativo, sin dependencias).
// Cadena: source -> highpass 90Hz -> compresor suave -> gate (GainNode).
// El gate NO corta el flujo: atenua a ~0.07 para que el Worklet/backend
// sigan recibiendo reloj (silencio) y no se rompa speechComplete.
// Comentarios en español neutro; identificadores en inglés.
export interface AudioPrefilter {
  /** Nodo de entrada: conectar aqui el MediaStreamSource. */
  input: GainNode;
  /** Nodo de salida: conectar hacia el Worklet o el MediaStreamDestination. */
  output: GainNode;
  /** Activa/desactiva el filtrado (bypass = ganancia 1, sin gate). */
  setEnabled(enabled: boolean): void;
  /** Umbral RMS del gate (rango sugerido 0.01-0.05). */
  setThreshold(value: number): void;
  /** Nivel RMS actual 0..1 aprox, util para vumetro. */
  getLevel(): number;
  /** Alimenta el gate con el RMS medido fuera (p. ej. Worklet). Opcional. */
  updateLevel(rms: number): void;
  /** Detiene el loop interno y desconecta nodos. */
  disconnect(): void;
}

const DEFAULT_THRESHOLD = 0.02;
const GATE_CLOSED_GAIN = 0.07;
const HANGOVER_MS = 350;
const ATTACK_TC = 0.02;
const RELEASE_TC = 0.15;

function clampThreshold(v: number): number {
  if (!Number.isFinite(v)) return DEFAULT_THRESHOLD;
  return Math.min(0.05, Math.max(0.01, v));
}

/** Crea el prefiltro dentro del AudioContext dado. No lanza si faltan nodos. */
export function createPrefilter(ctx: BaseAudioContext): AudioPrefilter {
  const input: GainNode = ctx.createGain();
  const highpass: BiquadFilterNode = ctx.createBiquadFilter();
  highpass.type = "highpass";
  highpass.frequency.value = 90;

  const compressor: DynamicsCompressorNode = ctx.createDynamicsCompressor();
  compressor.threshold.value = -24;
  compressor.knee.value = 20;
  compressor.ratio.value = 4;
  compressor.attack.value = 0.003;
  compressor.release.value = 0.2;

  const gate: GainNode = ctx.createGain();
  gate.gain.value = 1;

  // Analizador interno para medir nivel y mover el gate sin ayuda externa.
  const analyser: AnalyserNode = ctx.createAnalyser();
  analyser.fftSize = 1024;

  input.connect(highpass);
  highpass.connect(compressor);
  compressor.connect(gate);
  // Derivacion para medir nivel sin alterar la salida.
  compressor.connect(analyser);

  let enabled = true;
  let threshold = DEFAULT_THRESHOLD;
  let level = 0;
  let lastVoicedAt = 0;
  let closed = false;
  let rafId = 0;
  let stopped = false;
  const timeBuf = new Float32Array(analyser.fftSize);

  function applyGate(rms: number): void {
    // Suaviza el nivel para el vumetro.
    level = level * 0.7 + rms * 0.3;
    if (!enabled) return;
    const now = performance.now();
    if (rms >= threshold) {
      lastVoicedAt = now;
      if (closed) {
        closed = false;
        gate.gain.cancelScheduledValues(ctx.currentTime);
        gate.gain.setTargetAtTime(1.0, ctx.currentTime, ATTACK_TC);
      }
      return;
    }
    // Hangover: mantiene el gate abierto 350ms tras la ultima voz.
    if (now - lastVoicedAt < HANGOVER_MS) return;
    if (!closed) {
      closed = true;
      gate.gain.cancelScheduledValues(ctx.currentTime);
      gate.gain.setTargetAtTime(GATE_CLOSED_GAIN, ctx.currentTime, RELEASE_TC);
    }
  }

  function poll(): void {
    if (stopped) return;
    try {
      analyser.getFloatTimeDomainData(timeBuf);
      let acc = 0;
      for (let i = 0; i < timeBuf.length; i++) acc += timeBuf[i] * timeBuf[i];
      applyGate(Math.sqrt(acc / timeBuf.length));
    } catch {
      // Si el analizador falla (Safari), no rompe el audio.
    }
    rafId = requestAnimationFrame(poll);
  }
  // Inicia el gate abierto para no recortar la primera silaba.
  lastVoicedAt = performance.now();
  rafId = requestAnimationFrame(poll);

  return {
    input,
    output: gate,
    setEnabled(value: boolean) {
      enabled = value;
      try {
        gate.gain.cancelScheduledValues(ctx.currentTime);
        if (!enabled) {
          closed = false;
          // Bypass: ganancia 1, sin gate.
          gate.gain.setTargetAtTime(1.0, ctx.currentTime, ATTACK_TC);
        } else {
          // Al reactivar, parte abierto (hangover) para no comer ataque.
          lastVoicedAt = performance.now();
          gate.gain.setTargetAtTime(1.0, ctx.currentTime, ATTACK_TC);
        }
      } catch {
        // Ignora errores de automatizacion.
      }
    },
    setThreshold(value: number) {
      threshold = clampThreshold(value);
    },
    getLevel() {
      return level;
    },
    updateLevel(rms: number) {
      if (Number.isFinite(rms)) applyGate(rms);
    },
    disconnect() {
      stopped = true;
      try {
        cancelAnimationFrame(rafId);
      } catch {
        // Ignora errores de limpieza.
      }
      try {
        input.disconnect();
      } catch {
        // Ignora errores de limpieza.
      }
      try {
        highpass.disconnect();
      } catch {
        // Ignora errores de limpieza.
      }
      try {
        compressor.disconnect();
      } catch {
        // Ignora errores de limpieza.
      }
      try {
        gate.disconnect();
      } catch {
        // Ignora errores de limpieza.
      }
      try {
        analyser.disconnect();
      } catch {
        // Ignora errores de limpieza.
      }
    },
  };
}

export const PREFILTER_DEFAULT_THRESHOLD = DEFAULT_THRESHOLD;
