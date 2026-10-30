from __future__ import annotations

import json
import os
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def settings() -> dict[str, str | bool]:
    base_url = os.getenv("AGRI_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("AGRI_LLM_MODEL", "").strip()
    return {"base_url": base_url, "model": model, "configured": bool(model)}


def build_prompt(question: str, evidence: dict[str, Any]) -> str:
    facts = evidence.get("facts", [])[:12]
    documents = evidence.get("documents", [])[:8]
    return (
        "Answer the agricultural question using only the evidence below. "
        "Do not invent values. For numerical answers, include the value, unit, "
        "geography, period and source file or source page. If the evidence is "
        "insufficient or conflicting, say so clearly. Keep the answer concise.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"STRUCTURED FACTS:\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
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
    url = f"{config['base_url']}/api/chat"
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You are a careful, source-grounded agriculture knowledge assistant."},
            {"role": "user", "content": build_prompt(question, evidence)},
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        body = response.json()
        answer = body.get("message", {}).get("content", "").strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty answer")
        return {"available": True, "model": config["model"], "answer": answer, "error": None}
    except Exception as exc:
        return {"available": False, "model": config["model"], "answer": None, "error": str(exc)}

