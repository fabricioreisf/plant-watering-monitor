"""Healthcheck: não usa banco real; a sessão é substituída por um dublê."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
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


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def override_session(fake: FakeSession) -> None:
    async def _get_session() -> AsyncIterator[FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _get_session


async def test_liveness_returns_ok(http: AsyncClient) -> None:
    response = await http.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok_when_database_responds(http: AsyncClient) -> None:
    fake = FakeSession()
    override_session(fake)

    response = await http.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert fake.executed == ["SELECT 1"]


async def test_readiness_503_when_database_unreachable(http: AsyncClient) -> None:
    error = OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))
    override_session(FakeSession(error=error))

    response = await http.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


async def test_openapi_schema_lists_routes(http: AsyncClient) -> None:
    paths = (await http.get("/openapi.json")).json()["paths"]

    for path in ("/health", "/health/ready", "/auth/login", "/species"):
        assert path in paths
