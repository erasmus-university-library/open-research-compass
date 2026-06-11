# mcp_server_duckdb.py

from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import duckdb
import json
import os
import requests




# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv("DB_PATH", "academic.duckdb")

mcp = FastMCP("academic-agent")

# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    con = duckdb.connect(DB_PATH)

    con.execute("INSTALL fts;")
    con.execute("LOAD fts;")

    con.execute("INSTALL vss;")
    con.execute("LOAD vss;")

    return con

# ============================================================
# HELPERS
# ============================================================

# def build_fts_query(queries: List[str]) -> str:

#     clean_terms = [
#         q.strip()
#         for q in queries
#         if q.strip()
#     ]

#     return " ".join(clean_terms)

def build_fts_query(queries):
    phrases = []
    terms = []
    abbr = []

    for q in queries:
        q = q.strip()
        if len(q.split()) >= 2:
            phrases.append(f'"{q}"')
        elif len(q) <= 5:
            abbr.append(q)
        else:
            terms.append(q)

    # boost phrases by repeating them
    boosted_phrases = phrases * 2

    return " OR ".join(boosted_phrases + terms + abbr)

# ============================================================
# SEARCH DATABASE
# ============================================================

def search_database_internal(
    queries: str,
    faculty_name: Optional[str] = None
):

    if not queries:
        return []


    sql = """
    WITH ranked_docs AS (

        SELECT
            d.*,

            fts_main_documents.match_bm25(
                d.id,
                ?
            ) AS bm25_score

        FROM documents d

    ),

    filtered AS (

        SELECT DISTINCT
            rd.*

        FROM ranked_docs rd

        LEFT JOIN document_authors da
            ON rd.id = da.document_id

        LEFT JOIN authors a
            ON da.author_uuid = a.uuid

        WHERE bm25_score IS NOT NULL
    """

    params = [queries]

    if faculty_name:

        sql += """
        AND a.faculty_name = ?
        """

        params.append(faculty_name)

    sql += """
    )

    SELECT

        f.id,
        f.issued,
        f.title,
        f.language,
        f.type,
        f.doi,
        f.abstract,
        f.bm25_score,

        string_agg(
            a.name || ' (' || COALESCE(a.faculty_name, '') || ')',
            '; '
        ) AS author_names

    FROM filtered f

    LEFT JOIN document_authors da
        ON f.id = da.document_id

    LEFT JOIN authors a
        ON da.author_uuid = a.uuid

    GROUP BY
        f.id,
        f.issued,
        f.title,
        f.language,
        f.type,
        f.doi,
        f.abstract,
        f.bm25_score

    ORDER BY f.bm25_score DESC
    LIMIT 100
    """

    con = get_connection()

    try:

        rows = con.execute(
            sql,
            params
        ).fetchall()

        return [
            {
                "id": r[0],
                "issued": r[1],
                "title": r[2],
                "language": r[3],
                "type": r[4],
                "doi": r[5],
                "abstract": r[6],
                "score": r[7],
                "authors": r[8]
            }
            for r in rows
        ]

    finally:
        con.close()

# ============================================================
# AUTHOR STATS
# ============================================================


def get_author_stats_internal(
    queries: str,
    faculty_name: Optional[str] = None
):

    if not queries:
        return []

    sql = """
    WITH ranked_docs AS (

        SELECT
            d.id,
            d.issued,

            fts_main_documents.match_bm25(
                d.id,
                ?,
                fields := 'title, abstract'
                
            ) AS bm25_score

        FROM documents d
        WHERE bm25_score NOT NULL

    )


    SELECT

        a.name || ' (' || COALESCE(a.faculty_name, '') || ')' AS expert_name,
        COUNT(DISTINCT rd.id) AS matching_papers,

    FROM ranked_docs rd

    JOIN document_authors da
        ON rd.id = da.document_id

    JOIN authors a
        ON da.author_uuid = a.uuid

    WHERE rd.bm25_score IS NOT NULL
      AND a.faculty_name != 'External'
    """

    params = [queries]

    if faculty_name:
        sql += " AND a.faculty_name = ? "
        params.append(faculty_name)

    sql += """
    GROUP BY a.name, a.faculty_name
    HAVING matching_papers > 0
    ORDER BY matching_papers DESC
    LIMIT 50
    """

    print(sql)

    con = get_connection()

    try:
        rows = con.execute(sql, params).fetchall()

        return [
            {
                "expert": r[0],
                "papers": r[1]
            }
            for r in rows
        ]

    finally:
        con.close()
# ============================================================
# SEARCH AUTHORS
# ============================================================

def search_authors_internal(
    names: List[str]
):

    if not names:
        return []

    where_clauses = []
    params = []

    for name in names:

        where_clauses.append(
            "LOWER(a2.name) LIKE LOWER(?)"
        )

        params.append(f"%{name}%")

    where_sql = " OR ".join(where_clauses)

    sql = f"""
    SELECT

        d.id,
        d.issued,
        d.title,
        d.language,
        d.type,
        d.doi,
        d.abstract,

        string_agg(
            a.name || ' (' || COALESCE(a.faculty_name, '') || ')',
            '; '
        ) AS author_names

    FROM documents d

    JOIN document_authors da
        ON d.id = da.document_id

    JOIN authors a
        ON da.author_uuid = a.uuid

    WHERE d.id IN (
        SELECT da2.document_id
        FROM document_authors da2
        JOIN authors a2 ON da2.author_uuid = a2.uuid
        WHERE {where_sql}
    )

    GROUP BY
        d.id,
        d.issued,
        d.title,
        d.language,
        d.type,
        d.doi,
        d.abstract

    ORDER BY d.issued DESC
    """

    con = get_connection()

    try:

        rows = con.execute(
            sql,
            params
        ).fetchall()

        return [
            {
                "id": r[0],
                "issued": r[1],
                "title": r[2],
                "language": r[3],
                "type": r[4],
                "doi": r[5],
                "abstract": r[6],
                "authors": r[7]
            }
            for r in rows
        ]

    finally:
        con.close()

# ============================================================
# FACULTIES
# ============================================================

def get_faculties_internal():
    con = get_connection()
    try:
        rows = con.execute("""
        SELECT DISTINCT faculty_name
        FROM authors
        WHERE faculty_name IS NOT NULL
          AND faculty_name != 'External'
        ORDER BY faculty_name
        """).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()

# ============================================================
# SCHEMA
# ============================================================

def get_schema_internal():

    con = get_connection()

    try:

        tables = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        """).fetchall()

        schema = {}

        for table in tables:

            table_name = table[0]

            columns = con.execute(f"""
            SELECT
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            """).fetchall()

            schema[table_name] = [
                {
                    "name": c[0],
                    "type": c[1]
                }
                for c in columns
            ]

        return schema

    finally:
        con.close()


# ============================================================
# EMBEDDING SEARCH (most similar search)
# ============================================================

EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8080")

def get_embedding(text: str):
    response = requests.post(
        f"{EMBEDDING_SERVICE_URL}/embed",
        json={"text": text},
        timeout=30
    )

    return (response.json()["embedding"], response.json()["embedding_dim"])

def most_similar_internal(query:str):
    embedding, embedding_dim  = get_embedding(query)
    con = get_connection()

    sql = f"""
    SELECT   
        d.id,
        d.issued,
        d.title,
        d.language,
        d.type,
        d.doi,
        d.abstract,
            string_agg(
            a.name || ' (' || COALESCE(a.faculty_name, '') || ')',
            '; '
        ) AS author_names,
        array_cosine_similarity(embedding, {embedding}::FLOAT[{embedding_dim}]) as similarity

    FROM document_embeddings de
    LEFT JOIN documents d ON d.id = de.document_id 
    JOIN document_authors da ON d.id = da.document_id
    JOIN authors a ON da.author_uuid = a.uuid 
    GROUP BY 
        d.id,
        d.issued,
        d.title,
        d.language,
        d.type,
        d.doi,
        d.abstract,
        similarity
        
    ORDER BY similarity desc
    LIMIT 10
    """
    rows = con.execute(sql).fetchall()

    columns = [
        d[0]
        for d in con.description
    ]

    results = [
        dict(zip(columns, row))
        for row in rows
    ]

    return json.dumps(results)

# ============================================================
# SUMMARIZE TABLE
# ============================================================

def _json_default(obj):
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def summarize_table_internal(table_name: str):
    con = get_connection()
    try:
        rows = con.execute(f"SUMMARIZE {table_name}").fetchall()
        columns = [d[0] for d in con.description]
        return json.dumps([dict(zip(columns, row)) for row in rows], default=_json_default)
    finally:
        con.close()

# ============================================================
# SAFE QUERY EXECUTION
# ============================================================

def execute_query_internal(
    query: str
):

    query_clean = query.strip().lower()

    # --------------------------------------------------------
    # SAFETY
    # --------------------------------------------------------

    if not query_clean.startswith("select"):

        return json.dumps({
            "error": "Only SELECT queries are allowed."
        })

    forbidden = [
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "pragma",
        "copy"
    ]

    if any(word in query_clean for word in forbidden):

        return json.dumps({
            "error": "Query contains forbidden operations."
        })

    con = get_connection()

    try:

        rows = con.execute(query).fetchall()

        columns = [
            d[0]
            for d in con.description
        ]

        results = [
            dict(zip(columns, row))
            for row in rows
        ]

        return json.dumps(results)

    except Exception as e:

        return json.dumps({
            "error": str(e)
        })

    finally:
        con.close()

# ============================================================
# MCP TOOLS
# ============================================================



@mcp.tool()
def most_similar(query: str):
    """
    Find the 10 most semantically similar publications to a free-text query using
    vector (cosine) similarity on document embeddings.

    Use this for: "find papers similar to X", "research like Y", or when the user
    provides a descriptive passage rather than keywords.
    Do NOT use this for author lookups — use search_authors instead.

    Args:
        query: A natural-language description or title. The full string is embedded
               as-is, so pass the user's intent verbatim (e.g. "causal inference in
               panel data with fixed effects").

    Returns:
        JSON array of up to 10 documents ordered by descending cosine similarity,
        each with: id, issued, title, language, type, doi, abstract, author_names,
        similarity (float 0–1).
    """
    return most_similar_internal(query)

@mcp.tool()
def search_database(
    queries: str,
    faculty_name: Optional[str] = None
):
    """
    Full-text BM25 search over publication titles and abstracts.

    Use this for TOPIC / CONCEPT / METHOD queries AFTER calling expansion_agent.
    Pass the expanded terms from expansion_agent directly as the `queries` string.
    Do NOT pass the raw user question — pass the pre-processed expansion output.

    Args:
        queries: A BM25 query string of OR-joined terms and quoted phrases, e.g.
                 '"machine learning" OR "deep learning" OR neural OR AI'.
                 Use the output of expansion_agent verbatim.
        faculty_name: Optional filter. Call get_faculties() to get valid values.

    Returns:
        List of up to 100 matching documents ordered by BM25 relevance score,
        each with: id, issued, title, language, type, doi, abstract, score,
        authors (semicolon-separated name (faculty) pairs).
    """

    return search_database_internal(
        queries=queries,
        faculty_name=faculty_name
    )

@mcp.tool()
def get_author_stats(
    queries: str,
    faculty_name: Optional[str] = None
):
    """
    Rank internal Erasmus authors by number of matching publications for a topic.

    Use this as STEP 2 of the EXPERT workflow, after expansion_agent has produced
    expanded search terms. Pass those expanded terms as `queries`.
    Returns the top 50 authors ranked by publication count — use the top 5 to
    generate expert bios.

    Args:
        queries: A BM25 query string of OR-joined terms and quoted phrases.
                 Use the output of expansion_agent verbatim.
        faculty_name: Optional filter. Call get_faculties() to get valid values.

    Returns:
        List of up to 50 authors ordered by matching_papers descending,
        each with: expert (name (faculty)), papers (int count).
        External authors are excluded automatically.
    """

    return get_author_stats_internal(
        queries=queries,
        faculty_name=faculty_name
    )

@mcp.tool()
def search_authors(
    names: List[str]
):
    """
    Retrieve all publications for one or more authors by name (case-insensitive,
    partial match).

    Use this for PERSON / AUTHOR queries — when the user asks about a specific
    researcher by name. Do NOT use expansion_agent first; pass the name directly.

    Args:
        names: List of author name strings to search for. Each string is matched
               as a partial, case-insensitive LIKE query against the authors table.
               Example: ["Jan Smit"] or ["van der Berg", "Hoffman"].

    Returns:
        All documents authored by any of the matched authors, ordered by issued
        date descending. Each document has: id, issued, title, language, type,
        doi, abstract, authors (semicolon-separated name (faculty) pairs).
    """

    return search_authors_internal(
        names
    )

@mcp.tool()
def get_faculties():
    """
    Return all faculty names present in the database (excluding external authors).

    Call this before filtering search_database or get_author_stats by faculty_name
    to get the exact strings accepted by those tools.

    Returns:
        Sorted list of faculty name strings.
    """
    return get_faculties_internal()

@mcp.tool()
def get_schema():
    """
    Return the full database schema: all tables with their column names and types.

    Use this as STEP 1 for open-ended analytical queries before writing SQL.
    Always call this before execute_query so you know which tables and columns exist.

    Returns:
        Dict keyed by table name, each value a list of {name, type} column dicts.
        Main tables include: documents, authors, document_authors, document_embeddings.
    """

    return get_schema_internal()

@mcp.tool()
def summarize_table(table_name: str):
    """
    Return per-column statistics for a table: row count, approx unique values,
    null percentage, min, max, avg, and quartiles.

    Use this AFTER get_schema and BEFORE execute_query when you need to understand
    the range or cardinality of values in a column (e.g. what faculty_name values
    exist, date ranges, numeric distributions). This replaces multiple
    SELECT DISTINCT queries.

    Args:
        table_name: Exact table name as returned by get_schema (e.g. "documents",
                    "authors", "document_authors").

    Returns:
        One row per column with: column_name, column_type, count, approx_unique,
        null_percentage, min, max, avg, std, q25, q50, q75.
    """
    return summarize_table_internal(table_name)


@mcp.tool()
def execute_query(
    query: str
):
    """
    Execute a read-only SQL SELECT query against the DuckDB academic database.

    Use this ONLY after calling get_schema() to inspect available tables/columns.
    For topic searches prefer search_database; for author lookups prefer
    search_authors. Use this tool only when those don't cover the user's need
    (e.g. aggregate statistics, date ranges, cross-table joins).

    Args:
        query: A SQL SELECT statement. Only SELECT is allowed — INSERT, UPDATE,
               DELETE, DROP, ALTER, and COPY are rejected with an error.
               DuckDB SQL dialect (e.g. QUALIFY, EXCLUDE, LIST_AGG) is supported.

    Returns:
        JSON array of result rows as dicts, or {"error": "..."} on failure.
    """

    return execute_query_internal(
        query
    )

# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":
    from mcp.server.transport_security import TransportSecuritySettings
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = int(os.getenv("MCP_PORT", "9000"))
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
    mcp.run(transport="sse")