import psycopg2

# Database connection parameters - adjust these according to your environment
db_params = {
    'dbname': 'reckon',
    'user': 'postgres',
    'password': 'password',
    'host': 'localhost'
}

# SQL commands to be executed
commands = [
    # """
    # CREATE EXTENSION IF NOT EXISTS pgvector;
    # """,
    # """
    # CREATE TABLE IF NOT EXISTS reckoning (
    #     id SERIAL PRIMARY KEY,
    #     text TEXT NOT NULL
    # );
    # """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        id SERIAL PRIMARY KEY,
        reckoning_id INTEGER NOT NULL,
        embedding VECTOR(384), -- Adjust the dimension based on your model's output
        FOREIGN KEY (reckoning_id) REFERENCES reckoning(id)
    );
    """
]

def create_tables(commands, db_params):
    # Establishing the connection to the database
    conn = None
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        
        # Execute each command
        for command in commands:
            cur.execute(command)

        # Commit the changes to the database
        conn.commit()

        # Close communication with the database
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    create_tables(commands, db_params)
