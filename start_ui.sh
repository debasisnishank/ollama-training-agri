#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Model configuration. Defaults target LM Studio on this Mac; override any of
# these by exporting them before running (e.g. the Ollama base URL on the Nano).
export AGRI_LLM_BASE_URL="${AGRI_LLM_BASE_URL:-http://127.0.0.1:1234/v1}"
export AGRI_LLM_MODEL="${AGRI_LLM_MODEL:-qwen/qwen3-coder-30b}"
export AGRI_EMBED_BASE_URL="${AGRI_EMBED_BASE_URL:-http://127.0.0.1:1234/v1}"
export AGRI_EMBED_MODEL="${AGRI_EMBED_MODEL:-text-embedding-nomic-embed-text-v1.5}"

echo "LLM:       $AGRI_LLM_MODEL  @ $AGRI_LLM_BASE_URL"
echo "Embedding: $AGRI_EMBED_MODEL  @ $AGRI_EMBED_BASE_URL"

exec .venv/bin/python scripts/ui_server.py
