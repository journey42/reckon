FROM postgres:16

# Install the pgvector extension package for PostgreSQL.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

# Initialize the database with the pgvector extension.
COPY docker/db/init.sql /docker-entrypoint-initdb.d/00-init.sql

