from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb

from agri_rag.vector import semantic_search


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "knowledge_base.duckdb"


def tokens(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9_]+", text) if len(t) > 2 or t.isdigit()]


def fact_search(question: str, limit: int = 12) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        raise FileNotFoundError("Knowledge base not found. Run scripts/build_kb.py first.")
    search_tokens = tokens(question)
    if not search_tokens:
        return []
    con = duckdb.connect(str(DB_PATH), read_only=True)
    searchable = "lower(coalesce(context, '') || ' ' || coalesce(metric, '') || ' ' || coalesce(source_file, '') || ' ' || coalesce(sheet_name, ''))"
    score_expr = " + ".join([f"case when {searchable} like ? then 1 else 0 end"] * len(search_tokens))
    score_params = [f"%{token}%" for token in search_tokens]
    where = " or ".join([f"{searchable} like ?" for _ in search_tokens])
    where_params = [f"%{token}%" for token in search_tokens]
    rows = con.execute(
        f"select fact_id, source_file, sheet_name, row_number, metric, value, unit, context, ({score_expr}) as score from agricultural_facts where {where} order by score desc, case when lower(sheet_name) = 'summary' then 1 else 0 end desc, source_file, sheet_name, row_number limit ?",
        score_params + where_params + [limit],
    ).fetchall()
    columns = [d[0] for d in con.description]
    con.close()
    return [dict(zip(columns, row)) for row in rows]


def document_search(question: str, limit: int = 8) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        raise FileNotFoundError("Knowledge base not found. Run scripts/build_kb.py first.")
    search_tokens = tokens(question)
    if not search_tokens:
        return []
    try:
        semantic_hits = semantic_search(question, limit=limit)
        if semantic_hits:
            return semantic_hits
    except Exception:
        # Keep the local UI useful when Ollama or the embedding index is not configured.
        pass
    con = duckdb.connect(str(DB_PATH), read_only=True)
    score_expr = " + ".join(["case when lower(text) like ? then 1 else 0 end"] * len(search_tokens))
    score_params = [f"%{token}%" for token in search_tokens]
    where = " or ".join(["lower(text) like ?" for _ in search_tokens])
    where_params = [f"%{token}%" for token in search_tokens]
    rows = con.execute(
        f"select document_id, source_file, location, text, ({score_expr}) as score from document_chunks where {where} order by score desc limit ?",
        score_params + where_params + [limit],
    ).fetchall()
    columns = [d[0] for d in con.description]
    con.close()
    return [dict(zip(columns, row)) for row in rows]


def search(question: str) -> dict[str, Any]:
    return {"question": question, "facts": fact_search(question), "documents": document_search(question)}

