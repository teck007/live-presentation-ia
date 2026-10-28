import type {
  GenerateSlideRequest,
  GenerateSlideResponse,
  SlideLayoutId,
} from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";

const TIMEOUT_MS = 60_000;
const VALID_LAYOUTS: SlideLayoutId[] = [
  "title_text",
  "title_bullets",
  "text_image",
  "quote",
];

function normalizeResponse(data: unknown): GenerateSlideResponse {
  const d = (data ?? {}) as Partial<GenerateSlideResponse>;
  const layout: SlideLayoutId = VALID_LAYOUTS.includes(d.layout as SlideLayoutId)
    ? (d.layout as SlideLayoutId)
    : "title_text";
  return {
    layout,
    title: typeof d.title === "string" ? d.title : "",
    text: typeof d.text === "string" ? d.text : "",
    bullets: Array.isArray(d.bullets)
      ? d.bullets.filter((b): b is string => typeof b === "string")
      : [],
    keywords: Array.isArray(d.keywords)
      ? d.keywords.filter((k): k is string => typeof k === "string")
      : [],
    filtered: d.filtered === true,
  };
}

/** Pide al backend un slide JSON desde un turno final de transcripción. */
export async function generateSlide(
  req: GenerateSlideRequest,
): Promise<GenerateSlideResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE_URL}/api/presentations/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
    if (!response.ok) {
      let detail = `Error ${response.status}`;
      try {
        const data = await response.json();
        const d = (data as { detail?: unknown }).detail;
        if (typeof d === "string" && d.trim()) detail = d;
      } catch {
        // Usa el status como fallback.
      }
      throw new Error(detail);
    }
    return normalizeResponse(await response.json());
  } finally {
    clearTimeout(timer);
  }
}
