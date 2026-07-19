from collections.abc import AsyncIterator

import asyncpg
from fastapi import Request

from app.storage.s3 import S3Storage, storage_from_settings


async def get_conn(request: Request) -> AsyncIterator[asyncpg.Connection]:
    async with request.app.state.pool.acquire() as conn:
        yield conn


def get_storage() -> S3Storage:
    return storage_from_settings()
