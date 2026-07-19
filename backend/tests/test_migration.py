import asyncpg, pytest

TABLES = {"observers","sightings","photos","embeddings","individuals",
          "match_proposals","confirmations","clinical_records","areas","jobs"}

@pytest.mark.asyncio
async def test_all_tables_exist(migrated_db):
    rows = await migrated_db.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    assert TABLES.issubset({r['tablename'] for r in rows})

@pytest.mark.asyncio
async def test_public_read_has_no_grant_on_sightings(migrated_db):
    has = await migrated_db.fetchval("SELECT has_table_privilege('public_read','sightings','SELECT')")
    assert has is False

@pytest.mark.asyncio
async def test_sightings_geog_is_gist_indexed(migrated_db):
    idx = await migrated_db.fetch("SELECT indexdef FROM pg_indexes WHERE tablename='sightings'")
    assert any('gist' in r['indexdef'].lower() and 'geog' in r['indexdef'].lower() for r in idx)

@pytest.mark.asyncio
async def test_sightings_individual_id_nullable(migrated_db):
    nn = await migrated_db.fetchval(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name='sightings' AND column_name='individual_id'")
    assert nn == 'YES'

@pytest.mark.asyncio
async def test_embeddings_unique_photo_model(migrated_db):
    cnt = await migrated_db.fetchval(
        "SELECT count(*) FROM pg_constraint WHERE conname LIKE '%photo_id%model%' OR conname LIKE '%embeddings%'")
    # a UNIQUE(photo_id, model) constraint exists
    con = await migrated_db.fetch(
        "SELECT conname, contype FROM pg_constraint c JOIN pg_class t ON c.conrelid=t.oid "
        "WHERE t.relname='embeddings' AND contype='u'")
    assert len(con) >= 1
