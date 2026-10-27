import type { ServerEvent } from "../types";

// Base HTTP del backend (solo para derivar el host del WS cuando hay override).
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";

function deriveWsUrl(): string {
  // En desarrollo con Vite el proxy de /ws evita CORS: usa el mismo origen
  // cuando el frontend y el backend comparten host. Si VITE_API_BASE_URL
  // apunta a otro host, deriva ws(s)://host de ahi.
  try {
    const base = new URL(API_BASE_URL, window.location.origin);
    if (base.host === window.location.host && window.location.host !== "") {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      return `${scheme}://${window.location.host}/ws/transcribe`;
    }
    const scheme = base.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${base.host}/ws/transcribe`;
  } catch {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${window.location.host}/ws/transcribe`;
  }
}

export type RealtimeClientEvents = {
  onEvent: (event: ServerEvent) => void;
  onOpen?: () => void;
  onClose?: (code: number, reason: string) => void;
  onError?: (message: string) => void;
};

/**
 * Cliente WS realtime: PCM binario hacia arriba, eventos JSON hacia abajo.
 * No reintenta solo ante 1008 (sesion invalida); 1011/1013 con backoff.
 */
export class RealtimeClient {
  private socket: WebSocket | null = null;
  private events: RealtimeClientEvents;
  private manualClose = false;
  private retries = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  readonly url: string;

  constructor(events: RealtimeClientEvents, url?: string) {
    this.events = events;
    this.url = url ?? deriveWsUrl();
  }

  get connected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  connect(silencePauseMs?: number): void {
    this.manualClose = false;
    this.disconnect(1000, "reconnect");
    const socket = new WebSocket(this.url);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    socket.onopen = () => {
      this.retries = 0;
      if (silencePauseMs) {
        this.sendControl({ type: "config", silencePauseMs });
      }
      this.events.onOpen?.();
    };
    socket.onmessage = (ev: MessageEvent) => {
      if (typeof ev.data !== "string") return;
      try {
        const parsed = JSON.parse(ev.data) as ServerEvent;
        if (parsed && typeof parsed.type === "string") {
          this.events.onEvent(parsed);
        }
      } catch {
        // Ignora frames no JSON.
      }
    };
    socket.onerror = () => {
      this.events.onError?.("Error de conexión con el servidor realtime.");
    };
    socket.onclose = (ev: CloseEvent) => {
      this.events.onClose?.(ev.code, ev.reason);
      // 1008: no reintentar la misma sesion. Cierre manual: tampoco.
      if (this.manualClose || ev.code === 1008) return;
      // 1011/1013 o cierres abnormales: backoff (max 3 intentos).
      if (this.retries < 3) {
        const delay = [1000, 2000, 4000][this.retries] ?? 4000;
        this.retries += 1;
        this.retryTimer = setTimeout(() => this.connect(silencePauseMs), delay);
      }
    };
  }

  sendPcm(buffer: ArrayBuffer): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(buffer);
    }
  }

  sendControl(payload: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  notifyIdlePause(): void {
    this.sendControl({ type: "idle_pause" });
  }

  disconnect(code = 1000, reason = "done"): void {
    this.manualClose = true;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.socket) {
      try {
        this.sendControl({ type: "end" });
      } catch {
        // El socket puede estar ya cerrado.
      }
      try {
        this.socket.close(code, reason);
      } catch {
        // Ignora errores de cierre.
      }
      this.socket = null;
    }
  }
}
