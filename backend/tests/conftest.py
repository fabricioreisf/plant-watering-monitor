"""Fixtures compartilhadas.

Testes de domínio são puros e não precisam de nada. Testes de API usam um PostgreSQL real
indicado por TEST_DATABASE_URL (o nome do banco precisa terminar em `_test`, porque as
tabelas são recriadas). Sem essa variável, eles são pulados com um aviso explícito.
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Definidos antes de importar a aplicação: Settings exige estas variáveis.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost:5432/unused")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-chars")
os.environ.setdefault("APP_ENV", "test")

from app.db.base import Base
from app.db.seed import seed_species
from app.db.session import event_loop_factory, get_session
from app.main import app
from app.models import register_models

register_models()

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
PASSWORD = "correct-horse-battery"


def pytest_asyncio_loop_factories(config: pytest.Config, item: pytest.Item) -> dict[str, object]:
    return {"loop": event_loop_factory}


AuthHeaders = dict[str, str]


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set: skipping tests that need PostgreSQL")
    if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a database whose name ends with '_test'")

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessionmaker(db_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with maker() as session:
        await seed_species(session)
    yield maker
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
async def client(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
def login(client: AsyncClient) -> Callable[[str], Awaitable[AuthHeaders]]:
    """Cadastra (se preciso) e autentica um usuário; retorna o header Authorization."""

    async def _login(email: str) -> AuthHeaders:
        await client.post("/auth/register", json={"email": email, "password": PASSWORD})
        response = await client.post("/auth/login", data={"username": email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login


@pytest.fixture
async def auth_headers(login: Callable[[str], Awaitable[AuthHeaders]]) -> AuthHeaders:
    return await login("ana@exemplo.com.br")


@pytest.fixture
async def other_auth_headers(login: Callable[[str], Awaitable[AuthHeaders]]) -> AuthHeaders:
    return await login("bruno@exemplo.com.br")


@pytest.fixture
async def species_id(client: AsyncClient) -> str:
    response = await client.get("/species", params={"q": "Epipremnum"})
    return response.json()[0]["id"]


@pytest.fixture
def plant_payload(species_id: str) -> dict[str, object]:
    return {
        "species_id": species_id,
        "nickname": "Jiboia da sala",
        "environment": "indoor",
        "latitude": -23.55,
        "longitude": -46.63,
        "pot_volume_liters": 3.0,
    }


@pytest.fixture
async def plant(
    client: AsyncClient, auth_headers: AuthHeaders, plant_payload: dict[str, object]
) -> dict[str, object]:
    response = await client.post("/plants", json=plant_payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()
