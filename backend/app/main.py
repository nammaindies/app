from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from app.db import effective_dsn
from app.deps import get_storage
from app.routes.auth import router as auth_router
from app.routes.sighting import router as sighting_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(effective_dsn())
    await get_storage().ensure_bucket()
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(sighting_router)
