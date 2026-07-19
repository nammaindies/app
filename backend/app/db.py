from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    """Create (and cache) the asyncpg connection pool for the app database."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url)
    return _pool


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection from the pool. Minimal dependency-style helper;
    real FastAPI wiring (lifespan-managed pool, request dependency) comes later.
    """
    pool = await create_pool()
    async with pool.acquire() as conn:
        yield conn
