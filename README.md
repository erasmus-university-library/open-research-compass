# Open Research Compass

A multi-service AI agent that lets users query a [Pure](https://pure.eur.nl/) research information system (CRIS) dataset in natural language. Users can identify domain experts, search publications by topic, create author profiles, and run ad-hoc analytics against the underlying DuckDB database.

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
| **Source data** | The publication and author data comes from [Pure](https://pure.eur.nl/), the Erasmus University research information system. The actual export is not part of this repository. See [Data](#data) below for the expected format and a sample dataset you can use to get started. |
| **Credentials** | No API keys, `.env` files, or Azure/cloud credentials are committed. Copy `.env.example` to `.env` and fill in your own values before running. |
| **Embeddings / pre-built database** | `academic.duckdb` is not committed (it is generated from your own data export). You must build it yourself with `build_duckdb.py`. |

## Data

The database is built from a [Pure](https://pure.eur.nl/) research-information-system export converted to JSONL format. **The source data is not included in this repository.**

To use this project you need to supply your own data in the expected JSONL format. See [data/DATA_FORMAT.md](data/DATA_FORMAT.md) for the full field reference and a minimal example, and [data/sample_data.jsonl](data/sample_data.jsonl) for 12 synthetic records you can use to verify the setup end-to-end before connecting real data.

If you are working with a Pure instance, export your publications via the Pure API or reporting module, transform the records to the JSONL schema described in DATA_FORMAT.md, and then run `build_duckdb.py` as described below.

## Local setup — step by step

### Before you start

You need two things that are not included in this repository:

1. **[Docker Desktop](https://www.docker.com/products/docker-desktop/)**  download and install it for your operating system (Mac, Windows, or Linux). Docker Desktop includes Docker Compose and runs all the services for you without needing to install Python, Node.js, or anything else manually.
2. **An LLM API key** the agent requires a language model that supports tool calling. The default configuration uses Azure AI (Mistral), but any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers) works (OpenAI, OpenRouter, Google Vertex, a local Ollama instance, etc.).

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/erasmus-university-library/open-research-compass
cd duck-agent
```

---

### Step 2 — Configure your API credentials

Copy the example environment file and open it in a text editor:

```bash
cp .env.example .env
```

The file looks like this. Fill in your own values:

```bash
# Azure AI credentials (required if using Azure AI)
AZURE_AI_API_KEY=your-key-here
AZURE_AI_API_BASE=https://your-endpoint.services.ai.azure.com/models

# Model (optional, change if using a different provider)
AZ_MODEL=azure_ai/Mistral-Large-3
```

**Using a different LLM provider?** Set `AZ_MODEL` to the [LiteLLM model string](https://docs.litellm.ai/docs/providers) for your provider and add that provider's key instead. For example:

| Provider | `AZ_MODEL` value | Key to add to `.env` |
|---|---|---|
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY=sk-...` |
| OpenRouter | `openrouter/google/gemini-2.0-flash-001` | `OPENROUTER_API_KEY=sk-...` |
| Azure AI | `azure_ai/Mistral-Large-3` | `AZURE_AI_API_KEY` + `AZURE_AI_API_BASE` |
| Ollama (local) | `ollama/llama3.1` | *(no key needed)* |

The model must support tool/function calling.

---

### Step 3 — Build the database

The database is not included. You need to build it from your own data, or use the provided sample to test first.

**Option A: use the sample data (quickest way to verify everything works)**

```bash
pip install -r data/requirements.txt
python data/build_duckdb.py --input data/sample_data.jsonl --db academic.duckdb
```

This creates `academic.duckdb` in the project root using 12 synthetic publications. The embedding step downloads a ~570 MB model (`BAAI/bge-m3`) on first run and takes a few minutes.

**Option B: use your own Pure export**

Export your publications from [Pure](https://pure.eur.nl/) (via the API or reporting module), convert the records to the JSONL format described in [data/DATA_FORMAT.md](data/DATA_FORMAT.md), then run:

```bash
pip install -r data/requirements.txt
python data/build_duckdb.py --input your_export.jsonl --db academic.duckdb
```

When it finishes you should see `academic.duckdb` in the project root.

> **Adding new records later:** re-run the script with a JSONL file containing only the new records. The search indexes are rebuilt automatically. Do not re-submit records already in the database since there is no deduplication and you will get duplicates. If in doubt, delete `academic.duckdb` and rebuild from scratch.

---

### Step 4 — Start the application

```bash
docker-compose -f deploy/docker-compose.yml --env-file .env up --build
```

Docker will build the four service images and start them in order. The first build takes several minutes. On subsequent runs it is much faster.

The embeddings service loads the model on first start. Allow around 2 minutes before the app is fully ready.

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### Environment variable reference

All configuration is read from `.env`. The full list:

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_AI_API_KEY` | if using Azure AI | — | Azure AI API key |
| `AZURE_AI_API_BASE` | if using Azure AI | — | Azure AI endpoint URL |
| `AZ_MODEL` | no | `azure_ai/Mistral-Large-3` | LiteLLM model string for the agent |
| `EMBEDDING_MODEL` | no | `BAAI/bge-m3` | Embedding model used by the embedding service and `build_duckdb.py` |
| `DB_PATH` | no | `academic.duckdb` | Path to the DuckDB file inside the container |

## Kubernetes / AKS deployment

See [deploy/helm/README.md](deploy/helm/README.md) for the full Helm chart reference and the `deploy-aks.sh` one-shot provisioning script.

Quick start:

```bash
./deploy/deploy-aks.sh   # provisions ACR, AKS, storage, and installs the Helm chart
```
