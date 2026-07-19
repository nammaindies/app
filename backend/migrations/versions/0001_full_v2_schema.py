"""full v2 schema (10 tables, roles, PostGIS+pgvector)

Revision ID: 0001_full_v2_schema
Revises:
Create Date: 2026-07-19

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_full_v2_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Roles are cluster-global; CREATE ROLE must be idempotent.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
                CREATE ROLE app_rw;
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'public_read') THEN
                CREATE ROLE public_read;
            END IF;
        END
        $$;
        """
    )

    # 1. observers
    op.execute(
        """
        CREATE TABLE observers (
            id uuid PRIMARY KEY,
            phone_hash text UNIQUE,
            contact_enc bytea,
            display_name text,
            trust_tier text,
            home_geog geography(Point,4326),
            home_radius_m double precision,
            created_by_observer uuid REFERENCES observers(id),
            created_via text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz
        );
        """
    )

    # 5. individuals (created before sightings so sightings.individual_id can
    # reference it directly; match_proposals/confirmations/clinical_records
    # need it too)
    op.execute(
        """
        CREATE TABLE individuals (
            id uuid PRIMARY KEY,
            name text,
            first_seen_at timestamptz,
            last_seen_at timestamptz,
            territory_geog geography(Point,4326),
            created_by text CHECK (created_by IN ('model','feeder','manual')),
            named_by uuid REFERENCES observers(id),
            named_at timestamptz,
            created_by_observer uuid REFERENCES observers(id),
            created_via text,
            status text,
            merged_into uuid REFERENCES individuals(id),
            notes text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (status <> 'merged' OR merged_into IS NOT NULL)
        );
        """
    )

    # 2. sightings
    op.execute(
        """
        CREATE TABLE sightings (
            id uuid PRIMARY KEY,
            observer_id uuid REFERENCES observers(id) ON DELETE SET NULL,
            captured_at timestamptz NOT NULL,
            reported_at timestamptz,
            geog geography(Point,4326),
            geo_source text CHECK (geo_source IN ('device_gps','pin','none')),
            geo_accuracy_m double precision,
            individual_id uuid REFERENCES individuals(id),
            match_status text NOT NULL DEFAULT 'unmatched'
                CHECK (match_status IN ('unmatched','proposed','confirmed')),
            review_status text NOT NULL DEFAULT 'valid'
                CHECK (review_status IN ('pending','valid','rejected')),
            phash text,
            attrs jsonb NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_sightings_geog ON sightings USING GIST (geog);")
    op.execute("CREATE INDEX ix_sightings_individual_id ON sightings (individual_id);")
    op.execute("CREATE INDEX ix_sightings_observer_id ON sightings (observer_id);")
    op.execute("CREATE INDEX ix_sightings_captured_at ON sightings (captured_at);")

    # 3. photos
    op.execute(
        """
        CREATE TABLE photos (
            id uuid PRIMARY KEY,
            sighting_id uuid NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
            s3_key text NOT NULL,
            width int,
            height int,
            phash text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_photos_sighting_id ON photos (sighting_id);")

    # 4. embeddings
    op.execute(
        """
        CREATE TABLE embeddings (
            id uuid PRIMARY KEY,
            photo_id uuid NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            model text NOT NULL,
            dim int NOT NULL,
            vec vector,
            bbox jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (photo_id, model)
        );
        """
    )

    # 6. match_proposals
    op.execute(
        """
        CREATE TABLE match_proposals (
            id uuid PRIMARY KEY,
            sighting_id uuid NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
            candidate_individual_id uuid REFERENCES individuals(id),
            score double precision,
            method text,
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','confirmed','rejected')),
            resolved_by uuid REFERENCES observers(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # 7. confirmations
    op.execute(
        """
        CREATE TABLE confirmations (
            id uuid PRIMARY KEY,
            sighting_id uuid NOT NULL REFERENCES sightings(id) ON DELETE CASCADE,
            individual_id uuid REFERENCES individuals(id),
            observer_id uuid REFERENCES observers(id),
            proposal_id uuid REFERENCES match_proposals(id),
            verdict text NOT NULL CHECK (verdict IN ('same','different')),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # 8. clinical_records
    op.execute(
        """
        CREATE TABLE clinical_records (
            id uuid PRIMARY KEY,
            individual_id uuid REFERENCES individuals(id),
            sighting_id uuid REFERENCES sightings(id),
            external_ref text,
            visit_date date,
            procedure text,
            vet text,
            notes text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # 9. areas
    op.execute(
        """
        CREATE TABLE areas (
            id uuid PRIMARY KEY,
            name text,
            geog geography(MultiPolygon,4326),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # 10. jobs
    op.execute(
        """
        CREATE TABLE jobs (
            id uuid PRIMARY KEY,
            kind text NOT NULL,
            payload jsonb NOT NULL DEFAULT '{}',
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','running','done','failed')),
            attempts int NOT NULL DEFAULT 0,
            run_after timestamptz,
            last_error text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # Grants
    op.execute("GRANT USAGE ON SCHEMA public TO app_rw;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_rw;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;")
    # public_read: intentionally no grants in this migration.


def downgrade() -> None:
    op.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    # Do NOT drop the roles here -- roles are cluster-global and shared
    # across databases; dropping them in downgrade would be destructive
    # beyond the scope of this schema.
