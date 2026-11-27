"""Modelos ORM. Importar este pacote registra todas as tabelas em `Base.metadata`."""

from app.models.plant import Plant
from app.models.species import Species
from app.models.user import User
from app.models.watering_log import WateringLog

__all__ = ["Plant", "Species", "User", "WateringLog", "register_models"]


def register_models() -> None:
    """No-op explícito: chamar garante que os imports acima aconteceram."""
