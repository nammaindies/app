import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.deps import SESSION_COOKIE, require_observer
from app.ids import uuid7
from app.security import issue_session


def _req(cookie: str | None):
    headers = [(b"cookie", f"{SESSION_COOKIE}={cookie}".encode())] if cookie else []
    return Request({"type": "http", "headers": headers})


@pytest.mark.asyncio
async def test_require_observer_accepts_valid_session():
    oid = uuid7()
    got = await require_observer(_req(issue_session(oid)))
    assert got == oid


@pytest.mark.asyncio
async def test_require_observer_rejects_missing_and_bad():
    with pytest.raises(HTTPException) as e1:
        await require_observer(_req(None))
    assert e1.value.status_code == 401
    with pytest.raises(HTTPException):
        await require_observer(_req("garbage"))
