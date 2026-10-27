"""Controller presentation - stub sin lógica."""
from fastapi import APIRouter

router = APIRouter(prefix="/presentations", tags=["presentations"])


@router.get("/health")
def health():
    return {"status": "ok", "domain": "presentations"}


# TODO: endpoints de presentaciones
