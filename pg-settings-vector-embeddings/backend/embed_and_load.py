import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer

# Database connection parameters
DB_HOST = "localhost"
DB_PORT = your_port
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "your_password"

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def fetch_pg_settings_metadata_embeddings(conn):
    query = """
    SELECT 
        name,
        setting AS current_value,
        boot_val AS default_value,
        short_desc,
        context,
        vartype,
        min_val,
        max_val
    FROM pg_settings;
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()

def fetch_insights_data(conn):
    query = "SELECT settings_name, ai_insights FROM insights;"
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()

def generate_embedding_text(row):
    name, current_value, default_value, short_desc, context, vartype, min_val, max_val = row
    parts = [
        name,
        short_desc or '',
        context or '',
        f"Current value: {current_value or ''}",
        f"Default value: {default_value or ''}",
        f"Type: {vartype or ''}",
        f"Range: {min_val or ''} to {max_val or ''}"
    ]
    return " ".join(parts).strip()

def upsert_pg_settings_metadata_embeddings(cur, batch_data):
    insert_query = """
    INSERT INTO pg_settings_metadata_embeddings
      (name, embedding, current_value, default_value, short_desc, context, vartype, min_val, max_val)
    VALUES %s
    ON CONFLICT (name) DO UPDATE SET
      embedding = EXCLUDED.embedding,
      current_value = EXCLUDED.current_value,
      default_value = EXCLUDED.default_value,
      short_desc = EXCLUDED.short_desc,
      context = EXCLUDED.context,
      vartype = EXCLUDED.vartype,
      min_val = EXCLUDED.min_val,
      max_val = EXCLUDED.max_val;
    """
    execute_values(cur, insert_query, batch_data, template=None, page_size=100)

def upsert_insight_embeddings(cur, batch_data):
    insert_query = """
    INSERT INTO insight_embeddings (settings_name, embedding)
    VALUES %s
    ON CONFLICT (settings_name) DO UPDATE SET embedding = EXCLUDED.embedding;
    """
    execute_values(cur, insert_query, batch_data, template=None, page_size=100)

def main():
    conn = connect_db()

    # 1. Embeddings for PostgreSQL settings metadata
    pg_metadata_rows = fetch_pg_settings_metadata_embeddings(conn)
    print(f"Fetched {len(pg_metadata_rows)} pg_settings metadata records.")

    pg_batch_data = []
    for row in pg_metadata_rows:
        embedding_text = generate_embedding_text(row)
        embedding = model.encode(embedding_text)
        # Convert numpy float32 to Python float explicitly
        embedding_list = [float(x) for x in embedding]
        pg_batch_data.append((
            row[0],               # name
            embedding_list,       # converted embedding vector
            row[1],               # current_value
            row[2],               # default_value
            row[3],               # short_desc
            row[4],               # context
            row[5],               # vartype
            row[6],               # min_val
            row[7],               # max_val
        ))


    with conn.cursor() as cur:
        upsert_pg_settings_metadata_embeddings(cur, pg_batch_data)
        conn.commit()
    print("pg_settings_metadata_embeddings table updated successfully.")

    # 2. Embeddings for AI insights
    insight_rows = fetch_insights_data(conn)
    print(f"Fetched {len(insight_rows)} insights records.")

    insight_batch_data = []
    for settings_name, ai_insights in insight_rows:
        if not ai_insights:
            continue
        embedding = model.encode(ai_insights)
        embedding_list = [float(x) for x in embedding]  # convert every element to Python float
        insight_batch_data.append((settings_name, embedding_list))

    with conn.cursor() as cur:
        upsert_insight_embeddings(cur, insight_batch_data)
        conn.commit()
    print("insight_embeddings table updated successfully.")

    conn.close()
    print("Embedding generation and database update completed.")

if __name__ == "__main__":
    main()
