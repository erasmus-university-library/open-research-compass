import os

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
MODEL_NAME = os.getenv("MODEL_NAME", "azure_ai/Mistral-Large-3")
DB_PATH = os.getenv("DB_PATH", "academic.duckdb")
