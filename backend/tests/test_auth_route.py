import pytest


@pytest.mark.asyncio
async def test_consume_valid_link_sets_session(app_client):
    from app.auth.magiclink import create_observer_and_link

    pool = app_client._transport.app.state.pool
    async with pool.acquire() as c:
        link = await create_observer_and_link(c, display_name="Akash", base_url="http://test")
    token = link.split("token=")[1]
    r = await app_client.get(f"/auth/magic-link/consume?token={token}", follow_redirects=False)
    assert r.status_code == 303
    assert "session=" in r.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_consume_garbage_is_401(app_client):
    r = await app_client.get("/auth/magic-link/consume?token=nope", follow_redirects=False)
    assert r.status_code == 401
