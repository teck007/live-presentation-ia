"""Controller credits - stub sin lógica."""
from fastapi import APIRouter

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/health")
def health():
    return {"status": "ok", "domain": "credits"}


# TODO: endpoints de créditos
