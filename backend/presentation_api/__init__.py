"""Presentation API package. Crea app FastAPI y registra routers con prefijo /api."""
from fastapi import FastAPI
from backend.presentation_api.controllers import contact, credits, presentation

app = FastAPI(title="Live Presentation - Presentation API")

app.include_router(presentation.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(contact.router, prefix="/api")

__all__ = ["app"]
