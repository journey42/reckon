import reflex as rx
from sentence_transformers import SentenceTransformer
from sqlalchemy.sql import text
import numpy as np

def get_matching_threshold():
    return 0.5

def get_matching_count():
    return 10

def insert_text_with_embedding(text_to_embed, reckoning_id):
    # Load the model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate the embedding
    embedding = model.encode(text_to_embed)
    embedding_list = embedding.tolist()

    # Connect to the database using SQLAlchemy session
    with rx.session() as session:
        # Prepare the SQL query
        query = text("""
        INSERT INTO embeddings (embedding, reckoning_id) VALUES (:embedding, :reckoning_id)
        """)
        # Execute the query with parameters
        session.execute(query, {'embedding': embedding_list, 'reckoning_id': reckoning_id})
        # Commit the transaction
        session.commit()

def find_similar_texts_with_join(rid, threshold, limit):
    with rx.session() as session:
        # Prepare the SQL query
        query = text("""
        WITH target_embedding AS (
            SELECT embedding 
            FROM embeddings 
            WHERE reckoning_id = :id
            LIMIT 1
        )
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
            (
                r.type = 0 OR
                e.reckoning_id = :id -- Ensures inclusion of the target record regardless of its type
            ) AND (
                e.reckoning_id = :id OR
                e.embedding <=> te.embedding < :threshold
            )
        ORDER BY 
            e.reckoning_id = :id DESC, -- Ensures the record with id is on top
            similarity
        LIMIT 
            :limit;
        """)
        # Execute the query with parameters
        result = session.execute(query, {'id': rid, 'threshold': threshold, 'limit': limit})
        results = result.fetchall()
        print(results)
        keys = [id for id, similarity in results]
        print(keys)

    return keys, results
