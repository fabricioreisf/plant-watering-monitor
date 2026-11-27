"""Ponto de entrada da API FastAPI."""

import logging

from fastapi import FastAPI

from app.api.routes import auth, health, species
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="Monitor de Plantas",
        description="Recomenda quando e como regar cada planta.",
        version="0.2.0",
    )
    for module in (health, auth, species):
        app.include_router(module.router)
    return app


app = create_app()
