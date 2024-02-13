docker compose up -d

# Wait for Postgres to be ready
while ! docker exec -it postgres-pgvector pg_isready -U postgres; do sleep 1; done

# Enable the pgvector extension
docker exec -it postgres-pgvector psql -U postgres -d reckon -c 'CREATE EXTENSION vector;'