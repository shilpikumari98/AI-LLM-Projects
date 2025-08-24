# from urllib.parse import quote_plus

POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "your_db"
POSTGRES_USER = "your_user"
POSTGRES_PASSWORD = "your_password"
POSTGRES_SSL = False

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

OPENAI_API_KEY = "your_api_key"
OPENAI_API_BASE = "https://api.sambanova.ai/v1"
OPENAI_MODEL_NAME = "Llama-4-Maverick-17B-128E-Instruct"
