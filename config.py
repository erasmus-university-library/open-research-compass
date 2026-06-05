import os

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
AZ_MODEL = os.getenv("AZ_MODEL", "azure_ai/Mistral-Large-3")
DB_PATH = os.getenv("DB_PATH", "academic.duckdb")
