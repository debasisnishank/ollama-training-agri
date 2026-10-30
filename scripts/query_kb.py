#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agri_rag.query import search


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        raise SystemExit("Usage: python scripts/query_kb.py 'your question'")
    print(json.dumps(search(question), indent=2, ensure_ascii=False))

