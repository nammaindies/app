import httpx
import pytest

from app.storage.s3 import storage_from_settings


@pytest.mark.asyncio
async def test_put_then_presigned_url_roundtrips_bytes():
    s = storage_from_settings()
    await s.ensure_bucket()
    key = "test/hello.txt"
    payload = b"woof-woof-123"
    await s.put(key, payload, "text/plain")
    url = await s.url(key, expires_s=120)
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
    assert r.status_code == 200
    assert r.content == payload
