# Agriculture RAG Knowledge Base

This repository now contains the first implementation milestone for the agriculture RAG project.

The pipeline currently:

- snapshots the three specified web sources and the APEDA catalogue endpoint;
- extracts workbook metadata and row-level records from the Dharwad and Madurai workbooks;
- extracts paragraphs and tables from the source-assessment DOCX;
- stores normalized observations and document chunks in DuckDB;
- writes portable JSONL exports for later embedding and vector indexing;
- exposes a query command for source-aware lexical retrieval and structured fact inspection.

## Prerequisites

Install these once before running anything:

- **Python 3.11+** with `venv` (`python3 --version`).
- **A local model server** that exposes an OpenAI-compatible API:
  - **Mac (development): [LM Studio](https://lmstudio.ai)** — install the app, then the
    `lms` CLI ships with it (`~/.lmstudio/bin/lms`).
  - **Ubuntu / Nano (deployment): [Ollama](https://ollama.com)** — see the Nano section below.
- **Two models** downloaded in the server:
  - LLM for answering: `qwen/qwen3-coder-30b` (needs ~18 GB free RAM; any
    instruct model works, just change `AGRI_LLM_MODEL`).
  - Embedding model for semantic search: `text-embedding-nomic-embed-text-v1.5`.

  In LM Studio, download them from the app's search tab, or with the CLI:

  ```bash
  lms get qwen/qwen3-coder-30b
  lms get text-embedding-nomic-embed-text-v1.5
  ```

## Setup

Run these steps in order from the project folder. Steps 1–2 are one-time; step 3 is
once per machine boot; steps 4–5 rebuild the knowledge base whenever source data changes.

```bash
# 1. Python environment + dependencies (one time)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Model configuration (defaults target LM Studio; start_ui.sh sets these too)
export AGRI_LLM_BASE_URL=http://127.0.0.1:1234/v1
export AGRI_LLM_MODEL=qwen/qwen3-coder-30b
export AGRI_EMBED_BASE_URL=http://127.0.0.1:1234/v1
export AGRI_EMBED_MODEL=text-embedding-nomic-embed-text-v1.5

# 3. Start the model server and load both models (once per boot)
lms server start
lms load qwen/qwen3-coder-30b --gpu max
lms load text-embedding-nomic-embed-text-v1.5

# 4. Build the knowledge base from the source data
.venv/bin/python scripts/build_kb.py

# 5. Build the semantic vector index (uses the embedding model)
.venv/bin/python scripts/build_embeddings.py
```

Verify from the command line before opening the UI:

```bash
.venv/bin/python scripts/query_kb.py "Madurai highly stressed acreage 15 October 2026"
```

Step 4 (`build_kb.py`) creates:

- `data/knowledge_base.duckdb`
- `data/documents.jsonl`
- `data/facts.jsonl`
- `data/manifest.json`
- `data/ingestion_report.json`

Step 5 (`build_embeddings.py`) creates `data/vector_index.jsonl` and `data/vector_manifest.json`.

Once setup is complete, start the UI with `./start_ui.sh` (details below).

## Local UI

Start the browser UI after building the knowledge base:

```bash
.venv/bin/python scripts/ui_server.py
```

Open `http://127.0.0.1:8000`. The UI shows ingestion health, source status, structured fact retrieval and document evidence. It calls the configured local model (LM Studio or Ollama) for grounded answers; without the `AGRI_LLM_*` variables set it stays in evidence-only mode (retrieval, no generated answer).

The UI also provides a local ingestion console. Upload one or more XLSX, CSV/TSV, DOCX, PDF, HTML, JSON, TXT or Markdown files. Each upload is stored under `data/uploads/`, checksummed, processed as a background job, and added to a new knowledge-base release. Job state and release counts are available from the browser. The database replacement is atomic so the previous release remains queryable if a build fails.

For easier later access, run `./start_ui.sh` from the project folder.

The model layer talks to any OpenAI-compatible server. On the Mac this is **LM Studio**
(default `http://127.0.0.1:1234/v1`); on the Ubuntu/Nano deployment it is **Ollama**
(`http://127.0.0.1:11434/v1`). The same code targets both — only the base URL and model
name change. The base URL may be given with or without the trailing `/v1`.

Start LM Studio's server and load the models once:

```bash
lms server start
lms load qwen/qwen3-coder-30b --gpu max
lms load text-embedding-nomic-embed-text-v1.5
```

Then point the app at it before starting the UI:

```bash
export AGRI_LLM_BASE_URL=http://127.0.0.1:1234/v1
export AGRI_LLM_MODEL=qwen/qwen3-coder-30b
.venv/bin/python scripts/ui_server.py
```

The chat endpoint is `/v1/chat/completions`; the answer prompt includes the retrieved
facts and document evidence and asks the model to preserve source, period, geography and
unit details. The first request after a cold model load can take a minute; later warm
answers return in roughly 25 seconds.

To build the optional semantic document index, configure an embedding model and run:

```bash
export AGRI_EMBED_BASE_URL=http://127.0.0.1:1234/v1
export AGRI_EMBED_MODEL=text-embedding-nomic-embed-text-v1.5
.venv/bin/python scripts/build_embeddings.py
```

The embedding endpoint is `/v1/embeddings`. On the Nano, substitute the Ollama base URL
and the equivalent pulled models.

When `data/vector_index.jsonl` exists and the embedding model is available, document retrieval automatically prefers semantic search and falls back to lexical search when it is not.
- `data/raw/web/` snapshots

For office-network access, run the UI on the in-house server and bind it to the server's LAN interface only after adding authentication and a reverse proxy. The current development server binds to `127.0.0.1` intentionally; change `HOST` in `scripts/ui_server.py` to the private LAN address or `0.0.0.0` only for a controlled internal deployment.

### Ubuntu 22 / Nano deployment

Copy the project directory and source data to the Nano; do not copy the Mac `.venv` directory. On Ubuntu 22, run:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential
cd /path/to/ollama-training-data-agriculture
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_kb.py
AGRI_UI_HOST=0.0.0.0 AGRI_UI_PORT=8000 ./start_ui.sh
```

Then open `http://<nano-lan-ip>:8000` from an office workstation. The local model endpoint should point to the model server running on the Nano, normally `http://127.0.0.1:11434`. Add authentication and a reverse proxy before allowing multiple users or exposing the service beyond the private office network.

The numerical data is stored separately from narrative document chunks. This is deliberate: exact values should be answered from structured facts, while scheme, agronomy and source-definition questions should use document retrieval.

## Next implementation milestone

The OpenAI-compatible model adapter, semantic vector index and grounded answer API are
in place. Remaining quality work: a question router that chooses fact vs document
retrieval per query, full-text (FTS/BM25) fact search, and better handling of
multi-level-header spreadsheets.

