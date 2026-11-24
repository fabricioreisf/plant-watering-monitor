from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_session
from app.main import app


class FakeSession:
    """Substitui a AsyncSession: registra a consulta ou simula falha do banco."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.executed: list[str] = []

    async def execute(self, statement: Any) -> None:
        if self.error is not None:
            raise self.error
        self.executed.append(str(statement))


def override_session(fake: FakeSession) -> None:
    async def _get_session() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _get_session


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok_when_database_responds(client: TestClient) -> None:
    fake = FakeSession()
    override_session(fake)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert fake.executed == ["SELECT 1"]


def test_readiness_503_when_database_unreachable(client: TestClient) -> None:
    error = OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))
    override_session(FakeSession(error=error))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


def test_openapi_schema_lists_health_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/health" in paths
    assert "/health/ready" in paths
