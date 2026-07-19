import os
import subprocess
from pathlib import Path

import asyncpg
import psycopg
import pytest
import pytest_asyncio

from app.config import settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _default_db_url_sync() -> str:
    """The sync URL to the always-present `postgres` maintenance database,
    derived from the configured test database's sync URL."""
    url = settings.test_database_url_sync
    prefix, _, _rest = url.rpartition("/")
    return f"{prefix}/postgres"


def _ensure_test_database() -> None:
    admin_url = _default_db_url_sync().replace("postgresql+psycopg://", "postgresql://")
    dbname = settings.test_database_url_sync.rsplit("/", 1)[-1]
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(f'CREATE DATABASE "{dbname}"')


def _run_migrations() -> None:
    env = os.environ.copy()
    env["ALEMBIC_DB_URL"] = settings.test_database_url_sync
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_database():
    _ensure_test_database()
    _run_migrations()
    yield


@pytest_asyncio.fixture
async def migrated_db():
    conn = await asyncpg.connect(settings.test_database_url)
    try:
        await conn.execute(
            "TRUNCATE observers, sightings, photos, embeddings, individuals, "
            "match_proposals, confirmations, clinical_records RESTART IDENTITY CASCADE"
        )
        yield conn
    finally:
        await conn.close()
