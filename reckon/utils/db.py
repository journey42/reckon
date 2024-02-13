from sentence_transformers import SentenceTransformer
import psycopg2
import numpy as np

db_params = {
    'dbname': 'reckon',
    'user': 'postgres',
    'password': 'password',
    'host': 'localhost'
}

def get_matching_threshold():
    return 0.5

def get_matching_count():
    return 10

def insert_text_with_embedding(text, reckoning_id):
    # Load the model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate the embedding
    embedding = model.encode(text)
    embedding_list = embedding.tolist()

    # Connect to the database
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    # Insert the embedding into the embeddings table with a reference to the reckoning_id
    cur.execute("INSERT INTO embeddings (embedding, reckoning_id) VALUES (%s, %s)", (embedding_list, reckoning_id))

    # Commit the changes and close the connection
    conn.commit()
    cur.close()
    conn.close()

def find_similar_texts_with_join(rid, threshold, limit):

    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    cur.execute('''
        SELECT 
            reckoning_id, 
            embedding <=> (SELECT embedding FROM embeddings WHERE reckoning_id = %(id)s) AS similarity
        FROM 
            embeddings 
        WHERE 
            embedding <=> (SELECT embedding FROM embeddings WHERE reckoning_id = %(id)s) < %(threshold)s
        ORDER BY 
            similarity
        LIMIT 
            %(limit)s
    ''', {'id': rid, 'threshold': threshold, 'limit': limit})
    

    results = cur.fetchall()
    keys = [id for id, similarity in results]

    cur.close()
    conn.close()

    return keys, results
