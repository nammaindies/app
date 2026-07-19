import io

import pytest
from PIL import Image


def _jpeg():
    b = io.BytesIO()
    Image.new("RGB", (320, 240), (90, 130, 110)).save(b, "JPEG")
    return b.getvalue()


async def _post(client, geo=True):
    data = {"geo_source": "device_gps" if geo else "none", "captured_at": "2026-07-19T10:00:00Z"}
    if geo:
        data |= {"lat": "12.97", "lng": "77.59", "geo_accuracy_m": "8.0"}
    r = await client.post("/sighting", files={"photos": ("d.jpg", _jpeg(), "image/jpeg")}, data=data)
    assert r.status_code == 201
    return r.json()["sighting_id"]


@pytest.mark.asyncio
async def test_dex_requires_auth(app_client):
    r = await app_client.get("/dex")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dex_returns_only_own_sightings(authed_client):
    client, oid_a = authed_client
    # observer A posts two
    a1 = await _post(client)
    a2 = await _post(client)
    # create observer B, switch the session cookie, post one as B
    from app.ids import uuid7
    from app.security import issue_session

    pool = client._transport.app.state.pool  # match E2's accessor
    oid_b = uuid7()
    async with pool.acquire() as c:
        await c.execute("INSERT INTO observers (id, display_name, created_via) VALUES ($1,'B','test')", oid_b)
    client.cookies.set("session", issue_session(oid_b))
    b1 = await _post(client)
    # back to A
    client.cookies.set("session", issue_session(oid_a))
    r = await client.get("/dex")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["sightings"]]
    assert set(ids) == {a1, a2}
    assert b1 not in ids
    # photos carry presigned urls
    s0 = r.json()["sightings"][0]
    assert s0["photos"][0]["url"].startswith("http")
    assert s0["photos"][0]["thumb_url"].startswith("http")
