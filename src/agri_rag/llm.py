from __future__ import annotations

import json
import os
from typing import Any

import requests


# OpenAI-compatible endpoint. Works against LM Studio (default below) and, with
# AGRI_LLM_BASE_URL pointed at it, Ollama's /v1 surface on the Nano deployment.
DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"


def normalize_base_url(raw: str) -> str:
    """Return an OpenAI-style base URL ending in /v1.

    Accepts http://host:port, http://host:port/v1 or a legacy Ollama
    http://host:port/api value so a single setting works across runtimes.
    """
    base = raw.strip().rstrip("/")
    if base.endswith("/api"):
        base = base[: -len("/api")]
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def settings() -> dict[str, str | bool]:
    base_url = normalize_base_url(os.getenv("AGRI_LLM_BASE_URL", DEFAULT_BASE_URL))
    model = os.getenv("AGRI_LLM_MODEL", "").strip()
    return {"base_url": base_url, "model": model, "configured": bool(model)}


def build_prompt(question: str, evidence: dict[str, Any]) -> str:
    facts = evidence.get("facts", [])[:12]
    documents = evidence.get("documents", [])[:8]
    aggregation = evidence.get("aggregation")
    agg_block = ""
    if aggregation:
        agg_block = (
            "COMPUTED AGGREGATION (authoritative — this value was calculated "
            "directly over the full dataset with SQL; use it as the answer and do "
            "NOT re-sum the individual facts below, which are only a sample):\n"
            f"{json.dumps(aggregation, ensure_ascii=False, indent=2)}\n\n"
        )
    return (
        "Answer the agricultural question using only the evidence below. "
        "Do not invent values. For numerical answers, include the value, unit, "
        "geography, period and source file or source page. If the evidence is "
        "insufficient or conflicting, say so clearly. Keep the answer concise.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"{agg_block}"
        f"STRUCTURED FACTS (sample, may be truncated):\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
        f"DOCUMENT EVIDENCE:\n{json.dumps(documents, ensure_ascii=False, indent=2)}"
    )


def ask(question: str, evidence: dict[str, Any]) -> dict[str, Any]:
    config = settings()
    if not config["configured"]:
        return {
            "available": False,
            "model": None,
            "answer": None,
            "error": "Set AGRI_LLM_MODEL to enable local model answers.",
        }
    url = f"{config['base_url']}/chat/completions"
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You are a careful, source-grounded agriculture knowledge assistant."},
            {"role": "user", "content": build_prompt(question, evidence)},
        ],
        "stream": False,
        "temperature": 0.1,
    }
    try:
        # Generous timeout: the first call after the server loads a large model
        # cold can take well over the warm ~25s before the first token.
        response = requests.post(url, json=payload, timeout=600)
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") or []
        answer = (choices[0].get("message", {}).get("content", "") if choices else "").strip()
        if not answer:
            raise RuntimeError("Model server returned an empty answer")
        return {"available": True, "model": config["model"], "answer": answer, "error": None}
    except Exception as exc:
        return {"available": False, "model": config["model"], "answer": None, "error": str(exc)}
