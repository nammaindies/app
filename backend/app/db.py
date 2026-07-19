from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None
_dsn_override: str | None = None


def set_dsn_override(dsn: str | None) -> None:
    """Override the DSN used by `create_pool`/`effective_dsn`. Tests use this
    to point the app's pool at the test database instead of `settings.database_url`."""
    global _dsn_override
    _dsn_override = dsn


def effective_dsn() -> str:
    return _dsn_override or settings.database_url


async def create_pool() -> asyncpg.Pool:
    """Create (and cache) the asyncpg connection pool for the app database."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(effective_dsn())
    return _pool


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the pool. Minimal dependency-style helper;
    real FastAPI wiring (lifespan-managed pool, request dependency) comes later.
    """
    pool = await create_pool()
    async with pool.acquire() as conn:
        yield conn
