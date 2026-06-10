# Open Research Compass

A multi-service AI agent that lets users query a [Pure](https://pure.eur.nl/) research information system (CRIS) dataset in natural language. Users can identify domain experts, search publications by topic, explore author profiles, and run ad-hoc analytics against the underlying DuckDB database.

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

The root agent (Mistral via Azure AI) dispatches to five workflows:

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

## What is not included

| Item | Notes |
|---|---|
| **Source data** | The publication and author data comes from [Pure](https://pure.eur.nl/), the Erasmus University research information system. The actual export is not part of this repository — see [Data](#data) below for the expected format and a sample dataset you can use to get started. |
| **Credentials** | No API keys, `.env` files, or Azure/cloud credentials are committed. Copy `.env.example` to `.env` and fill in your own values before running. |
| **Embeddings / pre-built database** | `academic.duckdb` is not committed (it is generated from your own data export). You must build it yourself with `build_duckdb.py`. |

## Data

The database is built from a [Pure](https://pure.eur.nl/) research-information-system export converted to JSONL format. **The source data is not included in this repository.**

To use this project you need to supply your own data in the expected JSONL format. See [data/DATA_FORMAT.md](data/DATA_FORMAT.md) for the full field reference and a minimal example, and [data/sample_data.jsonl](data/sample_data.jsonl) for 12 synthetic records you can use to verify the setup end-to-end before connecting real data.

If you are working with a Pure instance, export your publications via the Pure API or reporting module, transform the records to the JSONL schema described in DATA_FORMAT.md, and then run `build_duckdb.py` as described below.

## Local development

### Prerequisites

- Docker and Docker Compose
- An LLM with agentic (tool-calling) capabilities, accessible via a [LiteLLM](https://docs.litellm.ai/docs/providers)-compatible model string — any provider supported by LiteLLM works (Azure AI, OpenAI, OpenRouter, Vertex AI, Ollama/vLLM, etc.)
- Your own publication data in the JSONL format described in [data/DATA_FORMAT.md](data/DATA_FORMAT.md), used to build `academic.duckdb`

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
docker-compose -f deploy/docker-compose.yml --env-file .env up --build
```

Services start in dependency order: `embeddings` → `mcp` → `agent` → `frontend`.  
The embeddings service loads a ~570 MB model on first start — allow ~2 minutes.

Open [http://localhost:3000](http://localhost:3000).

### Build the database (one-time)

```bash
pip install duckdb sentence-transformers
python data/build_duckdb.py --input your_data.jsonl --db academic.duckdb
```

Reads a JSONL file (one document per line), creates tables, builds the FTS index, generates embeddings with `BAAI/bge-m3`, and writes an HNSW index. Use [data/sample_data.jsonl](data/sample_data.jsonl) to test the pipeline before loading real data.

**Adding new data:** re-run the script with a JSONL containing only the new records. The FTS and HNSW indexes are always dropped and rebuilt over the full `documents` table, so existing data remains indexed. Avoid re-submitting already-imported documents — the `document_authors` table has no deduplication and will accumulate duplicate rows. You can also delete the existing database and rebuild from scratch.

## Kubernetes / AKS deployment

See [deploy/helm/README.md](deploy/helm/README.md) for the full Helm chart reference and the `deploy-aks.sh` one-shot provisioning script.

Quick start:

```bash
./deploy/deploy-aks.sh   # provisions ACR, AKS, storage, and installs the Helm chart
```
