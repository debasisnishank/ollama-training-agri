# Agriculture RAG Knowledge Base

This repository now contains the first implementation milestone for the agriculture RAG project.

The pipeline currently:

- snapshots the three specified web sources and the APEDA catalogue endpoint;
- extracts workbook metadata and row-level records from the Dharwad and Madurai workbooks;
- extracts paragraphs and tables from the source-assessment DOCX;
- stores normalized observations and document chunks in DuckDB;
- writes portable JSONL exports for later embedding and vector indexing;
- exposes a query command for source-aware lexical retrieval and structured fact inspection.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_kb.py
.venv/bin/python scripts/query_kb.py "Madurai highly stressed acreage 15 October 2026"
```

The build creates:

- `data/knowledge_base.duckdb`
- `data/documents.jsonl`
- `data/facts.jsonl`
- `data/manifest.json`
- `data/ingestion_report.json`

## Local UI

Start the browser UI after building the knowledge base:

```bash
.venv/bin/python scripts/ui_server.py
```

Open `http://127.0.0.1:8000`. The UI shows ingestion health, source status, structured fact retrieval and document evidence. It can also call a local Ollama model when configured; otherwise it remains in evidence-only mode.

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

Add an Ollama-compatible embedding adapter, a vector index, a question router and an answer API. The current build already preserves the metadata needed for citations and evaluation.

