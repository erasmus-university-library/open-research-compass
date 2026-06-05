# Open Research Compass

A multi-service AI agent that lets users query the Erasmus University CRIS dataset in natural language. Users can identify domain experts, search publications by topic, explore author profiles, and run ad-hoc analytics against the underlying DuckDB database.

## Architecture

```
User ──► Frontend (Next.js, :3000)
           └──► Agent API (FastAPI/ADK, :8000)
                  ├── expansion_agent  (LiteLLM → Azure AI Mistral)
                  └── MCP Toolset ──► MCP Server (FastMCP SSE, :9000)
                                        ├── DuckDB 
                                        └── Embedding Service (:6666)
                                              └── BAAI/bge-m3
```

### Services

| Service | Path | Port | Description |
|---|---|---|---|
| `agent` | `services/agent/backend_agent.py` | 8000 | FastAPI + Google ADK root agent, AG-UI protocol |
| `mcp` | `services/mcp/mcp_server.py` | 9000 | FastMCP SSE server — DuckDB tools exposed to the agent |
| `embeddings` | `services/embeddings/embedding_service.py` | 6666 | FastAPI service serving `BAAI/bge-m3` embeddings |
| `frontend` | `ui/` | 3000 | Next.js chat UI |

### Agent logic (`services/agent/agent.py`)

The root agent (Mistral via Azure AI) dispatches to four workflows:

| Query type | Workflow |
|---|---|
| **Expert identification** | `expansion_agent` → `get_author_stats` |
| **Topic / concept / method** | `expansion_agent` → `search_database` |
| **Person / author** | `search_authors` → profile synthesis |
| **Similarity** | `most_similar` (vector search) |
| **Open-ended analytics** | `get_schema` → `summarize_table` → `execute_query` |

### MCP tools (`services/mcp/mcp_server.py`)

| Tool | Description |
|---|---|
| `search_database` | BM25 full-text search over titles and abstracts |
| `get_author_stats` | Rank authors by matching publication count |
| `search_authors` | Retrieve all publications for a named author |
| `most_similar` | Cosine similarity vector search |
| `get_faculties` | Return all faculty names present in the DB (used to validate `faculty_name` filters) |
| `get_schema` | Return full DB schema |
| `summarize_table` | Per-column statistics (SUMMARIZE) |
| `execute_query` | Read-only SQL SELECT execution |

## Database schema

Built by `data/build_duckdb.py` from a JSONL export of the CRIS system.

| Table | Key columns |
|---|---|
| `documents` | `id`, `issued`, `title`, `language`, `type`, `doi`, `abstract` |
| `authors` | `uuid`, `name`, `faculty_name`, `orcid` |
| `document_authors` | `document_id`, `author_uuid` |
| `document_embeddings` | `document_id`, `embedding FLOAT[N]` (HNSW index) |

FTS index on `documents(title, abstract)` via the DuckDB `fts` extension.  
Vector index via the DuckDB `vss` extension (cosine, HNSW).

## Local development

### Prerequisites

- Docker and Docker Compose
- `academic.duckdb` in the project root (build with `build_duckdb.py`)

### Configuration

Runtime configuration lives in `services/agent/config.py`, which reads from environment variables with the defaults shown below. Copy `.env.example` to `.env` and override any values you need.

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `AZURE_AI_API_KEY` | — | Azure AI API key (required) |
| `AZURE_AI_API_BASE` | — | Azure AI endpoint URL (required) |
| `AZ_MODEL` | `azure_ai/Mistral-Large-3` | LiteLLM model string for the root and expansion agents |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Sentence-transformers model used by the embedding service and `build_duckdb.py` |
| `DB_PATH` | `academic.duckdb` | Path to the DuckDB file, read by the MCP server at runtime |

`EMBEDDING_MODEL` must be the same value when building the database and when running the embedding service — if they differ, vector search results will be incorrect.

To use a different LLM provider — local (e.g. Ollama/vLLM) or cloud (e.g. OpenAI, OpenRouter, Google Vertex, etc.) — set `AZ_MODEL` to the appropriate LiteLLM model string for that provider and supply its auth env var (e.g., `OPENAI_API_KEY` for OpenAI). `AZURE_AI_API_KEY` and `AZURE_AI_API_BASE` are Azure-specific and ignored by LiteLLM for other providers.  

### Run

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Services start in dependency order: `embeddings` → `mcp` → `agent` → `frontend`.  
The embeddings service loads a ~570 MB model on first start — allow ~2 minutes.

Open [http://localhost:3000](http://localhost:3000).

### Build the database (one-time)

```bash
pip install duckdb sentence-transformers
python data/build_duckdb.py --input your_data.jsonl --db academic.duckdb
```

Reads a JSONL file (one document per line), creates tables, builds the FTS index, generates embeddings with `BAAI/bge-m3`, and writes an HNSW index.

**Adding new data:** re-run the script with a JSONL containing only the new records. The FTS and HNSW indexes are always dropped and rebuilt over the full `documents` table, so existing data remains indexed. Avoid re-submitting already-imported documents — the `document_authors` table has no deduplication and will accumulate duplicate rows. You can also delete the existing database and rebuild from scratch. 

See [data/DATA_FORMAT.md](data/DATA_FORMAT.md) for the expected schema and a description of required vs optional fields. A sample dataset is provided in [data/sample_data.jsonl](data/sample_data.jsonl).

## Kubernetes / AKS deployment

See [deploy/helm/README.md](deploy/helm/README.md) for the full Helm chart reference and the `deploy-aks.sh` one-shot provisioning script.

Quick start:

```bash
./deploy/deploy-aks.sh   # provisions ACR, AKS, storage, and installs the Helm chart
```
