import reflex as rx
from sentence_transformers import SentenceTransformer
from sqlalchemy.sql import text
import numpy as np

def get_matching_threshold():
    return 0.5

def get_matching_count():
    return 10

# def insert_text_with_embedding(text_to_embed, reckoning_id):
#     # Load the model
#     model = SentenceTransformer('all-MiniLM-L6-v2')

#     # Generate the embedding
#     embedding = model.encode(text_to_embed)
#     embedding_list = embedding.tolist()

#     # Connect to the database using SQLAlchemy session
#     with rx.session() as session:
#         # Prepare the SQL query
#         query = text("""
#         INSERT INTO embeddings (embedding, reckoning_id) VALUES (:embedding, :reckoning_id)
#         """)
#         # Execute the query with parameters
#         session.execute(query, {'embedding': embedding_list, 'reckoning_id': reckoning_id})
#         # Commit the transaction
#         session.commit()

def _ensure_embeddings_schema(session):
    """Make sure the vector extension and embeddings table exist."""
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                reckoning_id INTEGER PRIMARY KEY REFERENCES reckoning(id) ON DELETE CASCADE,
                embedding vector(384)
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_embeddings_embedding
            ON embeddings USING ivfflat (embedding vector_cosine_ops)
            """
        )
    )


def insert_text_with_embedding(text_to_embed, reckoning_id):
    # Load the model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate the embedding
    embedding = model.encode(text_to_embed)
    embedding_list = embedding.tolist()

    # Connect to the database using SQLAlchemy session
    with rx.session() as session:
        _ensure_embeddings_schema(session)
        # Prepare the SQL query with UPSERT functionality
        query = text("""
        INSERT INTO embeddings (embedding, reckoning_id) 
        VALUES (:embedding, :reckoning_id)
        ON CONFLICT (reckoning_id) 
        DO UPDATE SET embedding = EXCLUDED.embedding
        """)
        # Execute the query with parameters
        session.execute(query, {'embedding': embedding_list, 'reckoning_id': reckoning_id})
        # Commit the transaction
        session.commit()


def find_similar_texts_with_join(rid, threshold, limit):
    with rx.session() as session:
        _ensure_embeddings_schema(session)
        # Prepare the SQL query
        query = text("""
        WITH target_embedding AS (
            SELECT embedding 
            FROM embeddings 
            WHERE reckoning_id = :id
            LIMIT 1
        ), similarity_results AS (
            SELECT 
                e.reckoning_id, 
                CASE 
                    WHEN e.reckoning_id = :id THEN 0
                    ELSE e.embedding <=> te.embedding 
                END AS similarity
            FROM 
                embeddings e
            INNER JOIN 
                reckoning r ON e.reckoning_id = r.id
            CROSS JOIN 
                target_embedding te
            WHERE 
                r.type = 0
                AND e.embedding <=> te.embedding < :threshold
        ), include_original AS (
            SELECT 
                reckoning_id, similarity
            FROM 
                similarity_results
            UNION ALL
            SELECT 
                :id AS reckoning_id, 0 AS similarity
            WHERE
                NOT EXISTS (
                    SELECT 1 
                    FROM similarity_results 
                    WHERE similarity = 0
                )
            OR :limit = 1 -- Include the original if the limit is 1, assuming you want the original in case of a single result
        )
        SELECT * FROM include_original
        ORDER BY 
            similarity,
            reckoning_id = :id DESC
        LIMIT 
            :limit;
        """)
        # Execute the query with parameters
        result = session.execute(query, {'id': rid, 'threshold': threshold, 'limit': limit})
        results = result.fetchall()
        # Process results
        keys = [id for id, similarity in results]

    return keys, results
