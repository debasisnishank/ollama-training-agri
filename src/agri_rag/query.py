from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb

from agri_rag.vector import semantic_search


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "knowledge_base.duckdb"
STOPWORDS = {
    "the", "and", "for", "from", "with", "what", "which", "where", "when", "does", "show",
    "give", "tell", "about", "data", "file", "files", "report", "number", "numbers", "value", "values",
}


def tokens(text: str) -> list[str]:
    return [
        t.lower() for t in re.findall(r"[A-Za-z0-9_]+", text)
        if (len(t) > 2 or t.isdigit()) and t.lower() not in STOPWORDS
    ]


def fact_search(question: str, limit: int = 12) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        raise FileNotFoundError("Knowledge base not found. Run scripts/build_kb.py first.")
    search_tokens = tokens(question)
    if not search_tokens:
        return []
    con = duckdb.connect(str(DB_PATH), read_only=True)
    metric = "lower(coalesce(metric, ''))"
    sheet = "lower(coalesce(sheet_name, ''))"
    geography = "lower(coalesce(geography, ''))"
    period = "lower(coalesce(period, ''))"
    context = "lower(coalesce(context, ''))"
    source = "lower(coalesce(source_file, ''))"
    score_parts = []
    score_params = []
    where_parts = []
    where_params = []
    for token in search_tokens:
        pattern = f"%{token}%"
        score_parts.extend([
            f"case when {metric} like ? then 5 else 0 end",
            f"case when {geography} like ? then 4 else 0 end",
            f"case when {sheet} like ? then 3 else 0 end",
            f"case when {period} like ? then 2 else 0 end",
            f"case when {context} like ? then 1 else 0 end",
            f"case when {source} like ? then 0.25 else 0 end",
        ])
        score_params.extend([pattern] * 6)
        where_parts.append(
            f"({metric} like ? or {geography} like ? or {sheet} like ? "
            f"or {period} like ? or {context} like ? or {source} like ?)"
        )
        where_params.extend([pattern] * 6)
    score_expr = " + ".join(score_parts)
    where = " or ".join(where_parts)
    rows = con.execute(
        f"select fact_id, source_file, sheet_name, row_number, metric, value, unit, geography, period, context, cast(round(({score_expr}), 2) as double) as score from agricultural_facts where {where} order by score desc, source_file, sheet_name, row_number limit ?",
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
    text_expr = "lower(coalesce(text, ''))"
    source_expr = "lower(coalesce(source_file, '') || ' ' || coalesce(location, ''))"
    score_parts = []
    score_params = []
    where_parts = []
    where_params = []
    for token in search_tokens:
        pattern = f"%{token}%"
        score_parts.extend([
            f"case when {text_expr} like ? then 2 else 0 end",
            f"case when {source_expr} like ? then 0.25 else 0 end",
        ])
        score_params.extend([pattern, pattern])
        where_parts.append(f"({text_expr} like ? or {source_expr} like ?)")
        where_params.extend([pattern, pattern])
    score_expr = " + ".join(score_parts)
    where = " or ".join(where_parts)
    rows = con.execute(
        f"select document_id, source_file, location, text, cast(round(({score_expr}), 2) as double) as score from document_chunks where {where} order by score desc limit ?",
        score_params + where_params + [limit],
    ).fetchall()
    columns = [d[0] for d in con.description]
    con.close()
    return [dict(zip(columns, row)) for row in rows]


def search(question: str) -> dict[str, Any]:
    return {"question": question, "facts": fact_search(question), "documents": document_search(question)}

