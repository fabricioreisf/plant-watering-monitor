"""Engine e sessões assíncronas do SQLAlchemy.

O engine é criado sob demanda para que importar a aplicação (por exemplo, nos testes)
não exija um banco acessível.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def event_loop_factory() -> asyncio.AbstractEventLoop:
    """Event loop compatível com o psycopg assíncrono.

    O loop padrão do Windows (Proactor) não é suportado pelo psycopg; em Linux (Docker, CI)
    o padrão já serve. Usado por scripts (`asyncio.run(..., loop_factory=...)`) e testes.
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependência do FastAPI: uma sessão por requisição."""
    async with get_sessionmaker()() as session:
        yield session
