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


# --- Aggregation path -------------------------------------------------------
# "mean" is deliberately excluded (collides with "what does X mean"); use
# "average"/"avg" instead.
AGG_OPS = [
    ("count", ("how many", "number of", "count of")),
    ("max", ("highest", "maximum", "most", "largest", "greatest", "worst", "top ")),
    ("min", ("lowest", "minimum", "least", "smallest", "fewest")),
    ("avg", ("average", "avg")),
    ("sum", ("total", "sum", "combined", "altogether", "overall", "aggregate")),
]
LEVEL_NOUNS = {"village": 3, "tehsil": 2, "taluk": 2, "taluka": 2, "district": 1}


def detect_op(ql: str) -> str | None:
    for op, keys in AGG_OPS:
        if any(k in ql for k in keys):
            return op
    return None


def resolve_metric(con: duckdb.DuckDBPyConnection, ql: str) -> str | None:
    best, best_score = None, 0.0
    for (metric,) in con.execute("select distinct metric from agricultural_facts").fetchall():
        words = [w for w in re.split(r"[^a-z0-9]+", metric.lower()) if len(w) > 2]
        if not words:
            continue
        hits = sum(1 for w in words if w in ql)
        if not hits:
            continue
        score = hits / len(words) + 0.1 * hits  # reward full-phrase and more words
        if score > best_score:
            best, best_score = metric, score
    return best if best_score >= 0.6 else None


def resolve_geo_tokens(con: duckdb.DuckDBPyConnection, ql: str, metric: str) -> list[str]:
    geo_words: set[str] = set()
    for (g,) in con.execute("select distinct lower(geography) from agricultural_facts where geography <> ''").fetchall():
        for part in re.split(r"[>\s]+", g):
            if len(part) > 2:
                geo_words.add(part)
    metric_words = set(re.split(r"[^a-z0-9]+", metric.lower()))
    question_words = re.findall(r"[a-z]+", ql)
    seen: list[str] = []
    for w in question_words:
        if w in geo_words and w not in metric_words and w not in seen:
            seen.append(w)
    return seen


def resolve_period(con: duckdb.DuckDBPyConnection, ql: str) -> str | None:
    best, best_frac = None, 0.0
    for (p,) in con.execute("select distinct period from agricultural_facts where period <> ''").fetchall():
        parts = [w for w in re.split(r"[^a-z0-9]+", p.lower()) if w]
        if not parts:
            continue
        hits = sum(1 for w in parts if w in ql)
        frac = hits / len(parts)
        if hits and frac > best_frac:
            best, best_frac = p, frac
    return best if best_frac >= 0.5 else None


def aggregate(question: str) -> dict[str, Any] | None:
    """Answer total/average/highest-style questions with real SQL.

    Returns None when the question is not an aggregation, so the caller falls
    back to ordinary retrieval. Aggregates are computed per sheet so that
    detail rows are never summed together with a pre-aggregated summary row.
    """
    if not DB_PATH.exists():
        return None
    ql = question.lower()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        op = detect_op(ql)
        metric = resolve_metric(con, ql)
        if not metric:
            return None
        geo_tokens = resolve_geo_tokens(con, ql, metric)
        period = resolve_period(con, ql)

        if op is None:
            # Implicit total: "the <metric> acreage in <place> tehsil/district"
            # is a sum over that administrative unit even without a sum keyword.
            implicit = any(n in ql for n in LEVEL_NOUNS) or "acreage" in ql or "area" in ql
            if geo_tokens and implicit:
                op = "sum"
            else:
                return None

        where = ["metric = ?"]
        params: list[Any] = [metric]
        for t in geo_tokens:
            # Location may live in the geography column (acreage sheets) or only
            # in the sheet name (rainfall / soil-moisture sheets).
            where.append("(lower(geography) like ? or lower(sheet_name) like ?)")
            params.extend([f"%{t}%", f"%{t}%"])
        if period:
            where.append("period = ?")
            params.append(period)
        clause = " and ".join(where)

        per_sheet = con.execute(
            f"""select sheet_name, count(*) n, round(sum(value), 2) total,
                       round(avg(value), 4) mean, round(max(value), 2) max_v,
                       round(min(value), 2) min_v,
                       sum(case when value <> 0 then 1 else 0 end) nonzero
                from agricultural_facts where {clause}
                group by sheet_name order by n desc""",
            params,
        ).fetchall()
        if not per_sheet:
            return None

        cols = ["sheet_name", "n", "total", "mean", "max_v", "min_v", "nonzero"]
        sheets = [dict(zip(cols, row)) for row in per_sheet]
        primary = sheets[0]  # most granular (most rows)

        # Rank mode: "which tehsil/village has the highest/most ..."
        rank_level = next((lvl for noun, lvl in LEVEL_NOUNS.items() if noun in ql), None)
        ranking = None
        if op in ("max", "min") and rank_level is not None:
            order = "desc" if op == "max" else "asc"
            ranking = con.execute(
                f"""select coalesce(nullif(split_part(geography, ' > ', {rank_level}), ''), geography) as grp,
                           round(sum(value), 2) total
                    from agricultural_facts
                    where {clause} and sheet_name = ?
                    group by grp having grp <> '' order by total {order} limit 10""",
                params + [primary["sheet_name"]],
            ).fetchall()
            ranking = [{"group": r[0], "value": r[1]} for r in ranking]

        # Extremum location within the primary sheet (for max/min scalar).
        extreme = None
        if op in ("max", "min") and ranking is None:
            order = "desc" if op == "max" else "asc"
            row = con.execute(
                f"""select geography, value from agricultural_facts
                    where {clause} and sheet_name = ?
                    order by value {order} limit 1""",
                params + [primary["sheet_name"]],
            ).fetchone()
            if row:
                extreme = {"geography": row[0], "value": round(row[1], 2)}

        if ranking:
            answer_value = {"group": ranking[0]["group"], "value": ranking[0]["value"]}
        else:
            answer_value = {
                "sum": primary["total"], "avg": primary["mean"],
                "max": primary["max_v"], "min": primary["min_v"],
                "count": primary["nonzero"],
            }[op]

        return {
            "operation": op,
            "metric": metric,
            "geography_filter": geo_tokens,
            "period_filter": period,
            "answer_value": answer_value,
            "primary_sheet": primary["sheet_name"],
            "rows_aggregated": primary["n"],
            "per_sheet": sheets,
            "ranking": ranking,
            "extreme": extreme,
        }
    finally:
        con.close()


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
    return {
        "question": question,
        "aggregation": aggregate(question),
        "facts": fact_search(question),
        "documents": document_search(question),
    }

