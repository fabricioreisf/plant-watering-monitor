import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Definido antes de importar a aplicação: Settings exige DATABASE_URL.
# Nenhum teste desta fase abre conexão real; o engine é criado sob demanda.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("APP_ENV", "test")

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
