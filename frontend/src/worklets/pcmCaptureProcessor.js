/* AudioWorklet: captura PCM mono 24kHz Int16 en frames de 80ms + VAD por energia.
 * Siempre emite frames (incluido silencio) para que Meta mantenga el reloj
 * realtime y pueda emitir speechComplete en silencios cortos.
 * Mensajes de salida: { type: "frame", pcm: ArrayBuffer, rms: number, voiced: boolean }
 * Mensajes de entrada: { type: "config", threshold: number }
 */
const OUTPUT_RATE = 24000;
const FRAME_SAMPLES = 1920; // 80ms @ 24kHz
const DEFAULT_THRESHOLD = 0.02;

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.threshold = DEFAULT_THRESHOLD;
    this.outBuffer = new Float32Array(FRAME_SAMPLES);
    this.outCount = 0;
    // Remuestreo lineal: tiempo (en muestras de entrada) del proximo sample de salida.
    this.stepUp = sampleRate / OUTPUT_RATE;
    this.nextOutAt = this.stepUp;
    this.inputIndex = 0;
    this.prevSample = 0;
    this.hasPrev = false;
    this.port.onmessage = (event) => {
      const msg = event.data;
      if (msg && msg.type === "config" && typeof msg.threshold === "number") {
        this.threshold = msg.threshold;
      }
    };
  }

  pushSample(value) {
    this.outBuffer[this.outCount++] = value;
    if (this.outCount >= FRAME_SAMPLES) {
      this.emitFrame();
    }
  }

  emitFrame() {
    const pcm = new Int16Array(FRAME_SAMPLES);
    let acc = 0;
    for (let i = 0; i < FRAME_SAMPLES; i++) {
      const v = Math.max(-1, Math.min(1, this.outBuffer[i]));
      acc += v * v;
      pcm[i] = Math.round(v * 32767);
    }
    const rms = Math.sqrt(acc / FRAME_SAMPLES);
    const voiced = rms >= this.threshold;
    const copy = pcm.buffer.slice(0);
    this.port.postMessage({ type: "frame", pcm: copy, rms, voiced }, [copy]);
    this.outCount = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) {
      return true;
    }
    const channels = input;
    const len = channels[0].length;
    for (let i = 0; i < len; i++) {
      let sample = 0;
      for (let c = 0; c < channels.length; c++) {
        sample += channels[c][i];
      }
      sample /= channels.length;
      this.inputIndex += 1;
      if (!this.hasPrev) {
        this.prevSample = sample;
        this.hasPrev = true;
        continue;
      }
      // Emite todos los samples de salida cuyo tiempo cae en (inputIndex-1, inputIndex].
      while (this.nextOutAt <= this.inputIndex) {
        const alpha = this.nextOutAt - (this.inputIndex - 1);
        const value = this.prevSample + alpha * (sample - this.prevSample);
        this.pushSample(value);
        this.nextOutAt += this.stepUp;
      }
      this.prevSample = sample;
    }
    return true;
  }
}

registerProcessor("pcm-capture-processor", PcmCaptureProcessor);
