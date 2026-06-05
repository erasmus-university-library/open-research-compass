# Input data format

`build_duckdb.py` reads a JSONL file — one JSON object per line, each representing a publication.

## Required fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier for the document |
| `title` | string | Publication title (used for FTS and embeddings) |
| `abstract` | string | Publication abstract (used for FTS and embeddings) |
| `author` | array | List of author objects (see below); may be empty `[]` |
| `author[].name` | string | Author display name |

## Optional fields

| Field | Type | Description |
|---|---|---|
| `issued` | string | Publication year or date, e.g. `"2023"` |
| `language` | string | ISO 639-1 language code, e.g. `"en"` |
| `type` | string | Publication type, e.g. `"journal-article"`, `"conference-paper"` |
| `doi` | string | DOI, e.g. `"10.1000/xyz123"` |
| `author[].uuid` | string | Stable author identifier; a random UUID is generated if omitted |
| `author[].orcid` | string | Author ORCID iD |
| `author[].affiliation` | array | List of affiliation objects |
| `author[].affiliation[].faculty_name` | string | Department or faculty label used for filtering in the agent |

Authors with no `affiliation` are stored with `faculty_name = "External"`.

## Minimal example

```json
{"id": "doc-1", "title": "My Paper", "abstract": "We study X.", "author": [{"name": "Jane Doe"}]}
```

## Full example

See [`sample_data.jsonl`](sample_data.jsonl) for 12 complete records covering multiple authors, departments, and publication types.

## Usage

```bash
python build_duckdb.py --input sample_data.jsonl --db academic.duckdb
```

Optional flags:

| Flag | Default | Description |
|---|---|---|
| `--input` | *(required)* | Path to the JSONL file |
| `--db` | `academic.duckdb` | Output DuckDB file path |
| `--model` | `BAAI/bge-m3` | Sentence-transformers model for embeddings |
