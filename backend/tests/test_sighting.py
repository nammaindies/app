import io

import pytest
from PIL import Image


def _jpeg():
    b = io.BytesIO()
    Image.new("RGB", (400, 300), (100, 140, 90)).save(b, "JPEG")
    return b.getvalue()


@pytest.mark.asyncio
async def test_post_sighting_requires_auth(app_client):
    r = await app_client.post(
        "/sighting",
        files={"photos": ("d.jpg", _jpeg(), "image/jpeg")},
        data={"geo_source": "none", "captured_at": "2026-07-19T10:00:00Z"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_sighting_creates_rows(authed_client):
    client, oid = authed_client
    r = await client.post(
        "/sighting",
        files={"photos": ("d.jpg", _jpeg(), "image/jpeg")},
        data={
            "lat": "12.97",
            "lng": "77.59",
            "geo_source": "device_gps",
            "geo_accuracy_m": "8.0",
            "captured_at": "2026-07-19T10:00:00Z",
        },
    )
    assert r.status_code == 201
    sid = r.json()["sighting_id"]
    pool = client._transport.app.state.pool
    async with pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT observer_id, individual_id, match_status, review_status, "
            "ST_Y(geog::geometry) AS lat FROM sightings WHERE id=$1",
            sid,
        )
        assert row["observer_id"] == oid
        assert row["individual_id"] is None
        assert row["match_status"] == "unmatched" and row["review_status"] == "valid"
        assert abs(row["lat"] - 12.97) < 1e-6
        n = await c.fetchval("SELECT count(*) FROM photos WHERE sighting_id=$1", sid)
        assert n == 1


@pytest.mark.asyncio
async def test_post_sighting_geo_none_stores_null_geog(authed_client):
    client, _ = authed_client
    r = await client.post(
        "/sighting",
        files={"photos": ("d.jpg", _jpeg(), "image/jpeg")},
        data={"geo_source": "none", "captured_at": "2026-07-19T10:00:00Z"},
    )
    assert r.status_code == 201
    pool = client._transport.app.state.pool
    async with pool.acquire() as c:
        g = await c.fetchval("SELECT geog FROM sightings WHERE id=$1", r.json()["sighting_id"])
    assert g is None
