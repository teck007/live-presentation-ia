"""Controller contact - stub sin lógica."""
from fastapi import APIRouter

router = APIRouter(prefix="/contact", tags=["contact"])


@router.get("/health")
def health():
    return {"status": "ok", "domain": "contact"}


# TODO: endpoints de contacto
