"""Controller presentation: genera slides JSON desde transcripción + LLM."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.presentation_api.utils.llm_client import VALID_LAYOUTS, generate_slide
from backend.presentation_api.utils.topic_cleaner import analyze_topic

router = APIRouter(prefix="/presentations", tags=["presentations"])


class GenerateSlideRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)
    topic: str = Field(default="", max_length=300)
    keywords: list[str] = Field(default_factory=list, max_length=10)


class GenerateSlideResponse(BaseModel):
    layout: str
    title: str
    text: str
    bullets: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    filtered: bool = False


@router.get("/health")
def health():
    return {"status": "ok", "domain": "presentations"}


@router.post("/generate", response_model=GenerateSlideResponse)
def generate(req: GenerateSlideRequest):
    transcript = req.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript vacío.")
    topic = (req.topic or "").strip()
    keywords = [k.strip() for k in (req.keywords or []) if k.strip()][:10]

    # Si no hay keywords, derivarlas del transcript para el LLM.
    if not keywords:
        keywords = analyze_topic(transcript).get("keywords", [])

    # El LLM decide en esta misma respuesta si corresponde al tema principal.
    slide = generate_slide(transcript, topic, keywords)
    if slide.get("filtered") is True or slide.get("relevant") is False:
        return GenerateSlideResponse(
            layout="title_text",
            title="",
            text="",
            bullets=[],
            keywords=keywords,
            filtered=True,
        )
    layout = slide.get("layout") if slide.get("layout") in VALID_LAYOUTS else "title_text"
    return GenerateSlideResponse(
        layout=layout,
        title=str(slide.get("title") or "En vivo")[:120],
        text=str(slide.get("text") or "")[:500],
        bullets=list(slide.get("bullets") or [])[:4],
        keywords=list(slide.get("keywords") or keywords)[:5],
        filtered=False,
    )
