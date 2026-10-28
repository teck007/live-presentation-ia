"""Cliente LLM, para llamar a la API de Meta."""

import json
import os
import time
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

client = OpenAI(
    base_url="https://api.meta.ai/v1",
    api_key=os.getenv("MODEL_API_KEY"),
)
VALID_LAYOUTS = ("title_text", "title_bullets", "text_image", "quote")

SLIDE_SYSTEM_PROMPT = (
    "Generas contenido para una presentación en vivo. "
    "Responde SOLO con JSON válido, sin markdown ni texto extra. "
    "Esquema: {\"relevant\": true|false, "
    "\"layout\": \"title_text|title_bullets|text_image|quote\", "
    "\"title\": \"título breve en español\", "
    "\"text\": \"explicación breve en español de la temática mencionada, 1-2 frases, máximo 30 palabras\", "
    "\"bullets\": [\"opcional, máximo 4 items cortos\"], "
    "\"keywords\": [\"opcional, máximo 5\"]}. "
    "relevant=false si la transcripción es saludo, muletilla, off-topic u otra temática "
    "que NO aporta al Tema principal (evaluación semántica, no literal; acepta sinónimos). "
    "Si relevant=false, devuelve layout title_text con title y text vacíos. "
    "Si relevant=true, text NO repite literal la transcripción: explica la temática "
    "contextualizada al Tema principal. "
    "Usa text_image SOLO si el texto describe algo visualizable "
    "(lugar, objeto, proceso, persona, escena). En otro caso usa "
    "title_text, title_bullets o quote. Solo español."
)


def _fallback_slide(transcript: str, keywords: list[str] | None, topic: str = "") -> dict:
    """Slide mínimo cuando el LLM falla o devuelve JSON inválido."""
    from backend.presentation_api.utils.topic_cleaner import is_relevant

    text = (transcript or "").strip()
    words = text.split()
    short = " ".join(words[:30]) if len(words) > 30 else text
    # Respaldo barato: si el LLM falló, usa el filtro literal para no generar basura.
    relevant = is_relevant(text, topic or "", list(keywords or []))
    return {
        "layout": "title_text",
        "title": " ".join(words[:8]) if words else "En vivo",
        "text": short or "Contenido en vivo.",
        "bullets": [],
        "keywords": list(keywords or [])[:5],
        "relevant": relevant,
        "filtered": not relevant,
    }


def generate_slide(transcript: str, topic: str, keywords: list[str] | None = None) -> dict:
    """Generate slide content as plain JSON (no HTML).

    The LLM only chooses content + layout id. Design lives in the frontend.
    Always returns a valid dict with layout/title/text/bullets/keywords.
    """
    kws = list(keywords or [])[:5]
    start = time.perf_counter()
    try:
        user_content = (
            f"Tema principal: {topic.strip() or '(sin definir)'}\n"
            f"Keywords: {', '.join(kws) if kws else '(ninguna)'}\n"
            f"Transcripción: {transcript.strip()}"
        )
        response = client.chat.completions.create(
            model="muse-spark-1.3",
            messages=[
                {"role": "system", "content": SLIDE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            top_p=0.9,
            max_completion_tokens=500,
            reasoning_effort="minimal",
            response_format={"type": "json_object"},
        )
        elapsed = time.perf_counter() - start
        print(f"[llm] generate_slide tomó {elapsed:.2f}s")
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            return _fallback_slide(transcript, kws, topic)
        # El modelo decide en esta misma respuesta si corresponde al tema principal.
        relevant = data.get("relevant", True)
        relevant = False if relevant is False else True
        if not relevant:
            return {
                "layout": "title_text",
                "title": "",
                "text": "",
                "bullets": [],
                "keywords": kws,
                "relevant": False,
                "filtered": True,
            }
        layout = data.get("layout") if isinstance(data, dict) else None
        if layout not in VALID_LAYOUTS:
            layout = "title_text"
        title = str(data.get("title") or "").strip()[:120] or "En vivo"
        text = str(data.get("text") or "").strip()[:500] or (transcript or "").strip()[:500]
        bullets = data.get("bullets") if isinstance(data.get("bullets"), list) else []
        bullets = [str(b).strip()[:140] for b in bullets if str(b).strip()][:4]
        out_kws = data.get("keywords") if isinstance(data.get("keywords"), list) else kws
        out_kws = [str(k).strip() for k in out_kws if str(k).strip()][:5]
        return {
            "layout": layout,
            "title": title,
            "text": text,
            "bullets": bullets,
            "keywords": out_kws,
            "relevant": True,
            "filtered": False,
        }
    except Exception as exc:  # noqa: BLE001 - MVP: fallback, no rompe el vivo
        print(f"[llm] generate_slide fallback por error: {exc}")
        return _fallback_slide(transcript, kws, topic)


def analyze_text(text: str) -> str:
    """Compat: devuelve el texto breve del slide (antes devolvía str libre)."""
    slide = generate_slide(text, topic="", keywords=[])
    return slide.get("text", "")


if __name__ == "__main__":
    print(generate_slide("Python es un lenguaje de programación", "Python", ["programación"]))
