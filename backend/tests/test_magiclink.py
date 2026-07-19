import pytest

from app.auth.magiclink import MagicLinkProvider, consume, create_observer_and_link


@pytest.mark.asyncio
async def test_mint_consume_roundtrip(migrated_db):
    link = await create_observer_and_link(migrated_db, display_name="Akash", base_url="http://x")
    assert "token=" in link
    token = link.split("token=")[1]
    oid = await consume(migrated_db, token)
    assert oid is not None
    # observer really exists
    n = await migrated_db.fetchval("SELECT count(*) FROM observers WHERE id=$1", oid)
    assert n == 1


@pytest.mark.asyncio
async def test_consume_rejects_garbage(migrated_db):
    assert await consume(migrated_db, "not-a-real-token") is None


@pytest.mark.asyncio
async def test_expired_token_is_rejected():
    p = MagicLinkProvider()
    from app.ids import uuid7

    tok = p.mint(uuid7())
    assert p.verify(tok, max_age_s=0) is None  # already older than 0s
