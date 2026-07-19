from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import effective_dsn
from app.deps import get_storage
from app.routes.auth import router as auth_router
from app.routes.dex import router as dex_router
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
app.include_router(dex_router)
app.include_router(sighting_router)

# Serve the built frontend PWA (frontend/dist) if present, e.g. after
# `cd frontend && npm run build`. Mounted last so the API routes above still
# take priority; falls back to index.html for any other path (SPA routing).
# Guarded so tests/dev without a build don't break.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
