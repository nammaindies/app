# Base: pgvector/pgvector:pg16 (Postgres 16 + pgvector, Debian bookworm).
# postgis is available directly from bookworm's apt repo as
# postgresql-16-postgis-3, so we add it via apt instead of building from
# source (much faster/more reliable than the reverse: postgis/postgis
# doesn't have a pgvector apt package and building pgvector from source
# there requires compiling with llvm/build-essential).
FROM pgvector/pgvector:pg16

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*
