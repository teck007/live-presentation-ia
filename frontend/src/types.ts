// Tipos compartidos entre la API y los componentes.
// Respuesta del endpoint POST /api/transcribe del backend FastAPI.
export interface TranscribeResponse {
  text: string;
  sessionId?: string | null;
  audioDurationMs?: number | null;
  turns: unknown[];
  topic?: string | null;
  cleaned?: string | null;
  keywords?: string[];
}

// Item del historial local de transcripciones.
export interface TranscriptItem {
  text: string;
  sessionId?: string | null;
  cleaned?: string | null;
  topic?: string | null;
  keywords?: string[];
}

// Slide generado por el LLM (JSON plano, sin HTML).
export type SlideLayoutId =
  | "title_text"
  | "title_bullets"
  | "text_image"
  | "quote";

export interface GenerateSlideRequest {
  transcript: string;
  topic: string;
  keywords: string[];
}

export interface GenerateSlideResponse {
  layout: SlideLayoutId;
  title: string;
  text: string;
  bullets: string[];
  keywords: string[];
  filtered: boolean;
}

export interface SlideItem extends GenerateSlideResponse {
  id: string;
  timestamp: number;
}

// Estado visible de la sesion realtime.
export type RealtimeStatus =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "paused"
  | "error";

// Turno de transcripcion realtime, claveado por turnId (los turnos pueden solaparse).
export interface TurnState {
  turnId: string;
  text: string;
  final: boolean;
  ended: boolean;
  updatedAt: number;
  cleaned?: string | null;
  topic?: string | null;
  keywords?: string[];
}

// Eventos que el backend reenvia de Meta (realtime) mas controles propios.
export interface MetaSpeechStartEvent {
  type: "speechStart";
  turnId: string;
}

export interface MetaTranscriptEvent {
  type: "transcript";
  transcript: string;
  final?: boolean;
  turnId?: string;
  cleaned?: string | null;
  topic?: string | null;
  keywords?: string[];
}

export interface MetaSpeechEndEvent {
  type: "speechEnd";
  turnId: string;
}

export interface MetaSpeechCompleteEvent {
  type: "speechComplete";
  turnId: string;
  transcript: string;
  cleaned?: string | null;
  topic?: string | null;
  keywords?: string[];
}

export interface BridgePausedEvent {
  type: "paused";
  reason?: string;
}

export interface BridgeResumedEvent {
  type: "resumed";
  reason?: string;
}

export interface BridgeUpstreamCloseEvent {
  type: "upstream_close";
  code?: number | null;
  reason?: string;
}

export interface BridgeErrorEvent {
  type: "error";
  message: string;
}

export type ServerEvent =
  | MetaSpeechStartEvent
  | MetaTranscriptEvent
  | MetaSpeechEndEvent
  | MetaSpeechCompleteEvent
  | BridgePausedEvent
  | BridgeResumedEvent
  | BridgeUpstreamCloseEvent
  | BridgeErrorEvent;
