from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import duckdb
import requests


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "knowledge_base.duckdb"
INDEX_PATH = ROOT / "data" / "vector_index.jsonl"
MANIFEST_PATH = ROOT / "data" / "vector_manifest.json"


def embedding_settings() -> dict[str, str | bool]:
    base_url = os.getenv("AGRI_EMBED_BASE_URL", os.getenv("AGRI_LLM_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
    model = os.getenv("AGRI_EMBED_MODEL", "").strip()
    return {"base_url": base_url, "model": model, "configured": bool(model)}


def embed(texts: list[str]) -> list[list[float]]:
    config = embedding_settings()
    if not config["configured"]:
        raise RuntimeError("Set AGRI_EMBED_MODEL to build or search the vector index.")
    response = requests.post(
        f"{config['base_url']}/api/embed",
        json={"model": config["model"], "input": texts, "truncate": True},
        timeout=180,
    )
    response.raise_for_status()
    vectors = response.json().get("embeddings")
    if not vectors or len(vectors) != len(texts):
        raise RuntimeError("Embedding service returned an unexpected response")
    return vectors


def cosine(a: list[float], b: list[float]) -> float:
    numerator = sum(x * y for x, y in zip(a, b))
    denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return numerator / denominator if denominator else 0.0


def build_index(batch_size: int = 32) -> dict[str, Any]:
    if not DB_PATH.exists():
        raise FileNotFoundError("Knowledge base not found. Run scripts/build_kb.py first.")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute("select document_id, source_file, source_type, location, text from document_chunks order by document_id").fetchall()
    con.close()
    if not rows:
        raise RuntimeError("No document chunks available for embedding")
    records = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        vectors = embed([row[4] for row in batch])
        for row, vector in zip(batch, vectors):
            records.append({
                "document_id": row[0],
                "source_file": row[1],
                "source_type": row[2],
                "location": row[3],
                "text": row[4],
                "embedding": vector,
            })
    INDEX_PATH.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
    manifest = {"model": embedding_settings()["model"], "document_count": len(records), "dimensions": len(records[0]["embedding"]), "index": str(INDEX_PATH.relative_to(ROOT))}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def semantic_search(question: str, limit: int = 8) -> list[dict[str, Any]]:
    if not INDEX_PATH.exists():
        return []
    query_vector = embed([question])[0]
    hits = []
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        score = cosine(query_vector, record.pop("embedding"))
        record["score"] = round(score, 6)
        hits.append(record)
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:limit]

