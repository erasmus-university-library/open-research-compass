import argparse
import duckdb
import json
import os
import uuid
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# ============================================================
# DB SETUP
# ============================================================

def create_tables(con, embedding_dim: int):

    # --------------------------------------------------------
    # Core relational tables
    # --------------------------------------------------------

    con.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        issued TEXT,
        title TEXT,
        language TEXT,
        type TEXT,
        doi TEXT,
        abstract TEXT
    );
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS authors (
        uuid TEXT PRIMARY KEY,
        name TEXT,
        faculty_name TEXT,
        orcid TEXT
    );
    """)

    con.execute("""
    CREATE TABLE IF NOT EXISTS document_authors (
        document_id TEXT,
        author_uuid TEXT
    );
    """)

    # --------------------------------------------------------
    # Embeddings table
    # --------------------------------------------------------

    con.execute("INSTALL vss;")
    con.execute("LOAD vss;")

    con.execute("""
    SET hnsw_enable_experimental_persistence = TRUE;
    """)

    con.execute("DROP TABLE IF EXISTS document_embeddings;")

    con.execute(f"""
    CREATE TABLE document_embeddings (
        document_id TEXT,
        embedding FLOAT[{embedding_dim}]
    );
    """)

    # --------------------------------------------------------
    # FTS Extension
    # --------------------------------------------------------

    con.execute("INSTALL fts;")
    con.execute("LOAD fts;")


# ============================================================
# LOAD DATA
# ============================================================

def load_jsonl(con, path):

    documents = []
    authors = []
    doc_authors = []

    with open(path, "r", encoding="utf-8") as f:

        for i, line in enumerate(f):

            try:
                data = json.loads(line)

                doc_id = data.get("id")

                documents.append((
                    doc_id,
                    data.get("issued"),
                    data.get("title"),
                    data.get("language"),
                    data.get("type"),
                    data.get("doi"),
                    data.get("abstract")
                ))

                for a in data.get("author", []):

                    name = a.get("name")

                    aff = a.get("affiliation")

                    faculty_name = (
                        aff[0].get("faculty_name", "Unknown")
                        if aff
                        else "External"
                    )

                    a_uuid = a.get("uuid") or str(uuid.uuid4())

                    authors.append((
                        a_uuid,
                        name,
                        faculty_name,
                        a.get("orcid")
                    ))

                    doc_authors.append((
                        doc_id,
                        a_uuid
                    ))

            except Exception as e:
                print(f"Error on line {i}: {e}")

    # --------------------------------------------------------
    # Insert documents
    # --------------------------------------------------------

    con.executemany("""
    INSERT OR REPLACE INTO documents
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, documents)

    # --------------------------------------------------------
    # Insert authors
    # --------------------------------------------------------

    con.executemany("""
    INSERT OR IGNORE INTO authors
    VALUES (?, ?, ?, ?)
    """, authors)

    # --------------------------------------------------------
    # Insert document-author relations
    # --------------------------------------------------------

    con.executemany("""
    INSERT INTO document_authors
    VALUES (?, ?)
    """, doc_authors)

    con.commit()


# ============================================================
# BUILD FTS INDEX
# ============================================================

def build_fts_index(con):

    print("Building FTS index...")

    try:
        con.execute("""
        PRAGMA drop_fts_index('documents');
        """)
    except:
        pass

    con.execute("""
    PRAGMA create_fts_index(
        'documents',
        'id',
        'title',
        'abstract'
    );
    """)

    con.commit()


# ============================================================
# EMBEDDINGS
# ============================================================

def build_embeddings(con, model):

    print("Generating embeddings...")

    rows = con.execute("""
    SELECT
        id,
        COALESCE(title, '') || ' ' ||
        COALESCE(abstract, '')
    FROM documents
    """).fetchall()

    ids = []
    texts = []

    for row in rows:

        ids.append(row[0])
        texts.append(row[1])

    embeddings = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=True,
        normalize_embeddings=True
    ).tolist()

    embedding_rows = list(zip(ids, embeddings))

    con.executemany("""
    INSERT INTO document_embeddings
    VALUES (?, ?)
    """, embedding_rows)

    con.commit()

    print("Building HNSW index...")

    con.execute("""
    CREATE INDEX document_embedding_idx
    ON document_embeddings
    USING HNSW (embedding)
    WITH (metric = 'cosine');
    """)

    con.commit()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Build a DuckDB academic database with FTS and vector indexes."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the JSONL input file (one document object per line)."
    )
    parser.add_argument(
        "--db",
        default="academic.duckdb",
        help="Path to the DuckDB output file (default: academic.duckdb)."
    )
    parser.add_argument(
        "--model",
        default=EMBEDDING_MODEL,
        help=f"Sentence-transformers model for embeddings (default: {EMBEDDING_MODEL})."
    )
    args = parser.parse_args()

    print("Loading embedding model...")

    model = SentenceTransformer(args.model).half()

    embedding_dim = model.get_sentence_embedding_dimension()

    print("Connecting to DuckDB...")

    con = duckdb.connect(args.db)

    print("Creating schema...")

    create_tables(con, embedding_dim)

    print("Loading JSONL...")

    load_jsonl(con, args.input)

    print("Building FTS...")

    build_fts_index(con)

    print("Building embeddings...")

    build_embeddings(con, model)

    print("Done.")