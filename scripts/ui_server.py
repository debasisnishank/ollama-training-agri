#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import duckdb

from agri_rag.llm import ask as ask_llm, settings as llm_settings
from agri_rag.build import build, safe_name, checksum_bytes
from agri_rag.query import search


HOST = os.environ.get("AGRI_UI_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGRI_UI_PORT", "8000"))
DB_PATH = ROOT / "data" / "knowledge_base.duckdb"
INDEX_PATH = ROOT / "ui" / "index.html"
UPLOAD_DIR = ROOT / "data" / "uploads"
JOB_DIR = ROOT / "data" / "jobs"
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
ALLOWED_EXTENSIONS = {".xlsx", ".csv", ".tsv", ".docx", ".pdf", ".html", ".htm", ".json", ".txt", ".md"}
JOBS: dict[str, dict[str, object]] = {}
JOB_LOCK = threading.Lock()
BUILD_LOCK = threading.Lock()


def db_counts() -> dict[str, int | str]:
    if not DB_PATH.exists():
        return {"status": "missing", "facts": 0, "documents": 0, "sources": 0}
    con = duckdb.connect(str(DB_PATH), read_only=True)
    values = {
        "status": "ok",
        "facts": con.execute("select count(*) from agricultural_facts").fetchone()[0],
        "documents": con.execute("select count(*) from document_chunks").fetchone()[0],
        "sources": con.execute("select count(*) from source_manifest").fetchone()[0],
    }
    con.close()
    return values


def source_rows() -> list[dict[str, object]]:
    if not DB_PATH.exists():
        return []
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute("select source, source_type, status, coalesce(path, url, '') as location from source_manifest order by source_type, source").fetchall()
    con.close()
    return [{"source": r[0], "source_type": r[1], "status": r[2], "location": r[3]} for r in rows]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def persist_job(job: dict[str, object]) -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    (JOB_DIR / f"{job['id']}.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def update_job(job_id: str, **changes: object) -> None:
    with JOB_LOCK:
        job = JOBS[job_id]
        job.update(changes)
        job["updated_at"] = now()
        persist_job(job)


def list_jobs() -> list[dict[str, object]]:
    with JOB_LOCK:
        jobs = list(JOBS.values())
    return sorted(jobs, key=lambda item: str(item.get("created_at", "")), reverse=True)


def run_ingestion(job_id: str, paths: list[Path]) -> None:
    try:
        update_job(job_id, status="running", message="Extracting, validating and rebuilding the knowledge base")
        with BUILD_LOCK:
            report = build(upload_paths=paths)
        update_job(
            job_id,
            status="complete",
            message="Knowledge base release completed",
            report={
                "facts": report["agricultural_facts"],
                "documents": report["document_chunks"],
                "workbook_rows": report["workbook_rows"],
                "database": report["database"],
            },
        )
    except Exception as exc:
        log = JOB_DIR / f"{job_id}.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        update_job(job_id, status="error", message="Processing failed", error=str(exc), log=str(log.relative_to(ROOT)))


def load_existing_jobs() -> None:
    if not JOB_DIR.exists():
        return
    for path in sorted(JOB_DIR.glob("*.json")):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            if job.get("status") in {"queued", "running"}:
                job["status"] = "interrupted"
                job["message"] = "Server restarted before this job completed"
            JOBS[str(job["id"])] = job
        except (OSError, json.JSONDecodeError, KeyError):
            continue


def parse_upload(body: bytes, content_type: str, job_id: str) -> tuple[list[Path], list[dict[str, object]]]:
    if not content_type.lower().startswith("multipart/form-data"):
        raise ValueError("Upload must use multipart/form-data")
    envelope = (f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode() + body
    message = BytesParser(policy=policy.default).parsebytes(envelope)
    paths: list[Path] = []
    files: list[dict[str, object]] = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for part in message.walk():
        if part.is_multipart() or part.get_content_disposition() != "form-data":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        clean = safe_name(Path(filename).name)
        suffix = Path(clean).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {suffix or 'no extension'}")
        payload = part.get_payload(decode=True) or b""
        if not payload:
            raise ValueError(f"Uploaded file is empty: {clean}")
        stored = UPLOAD_DIR / f"{job_id}_{clean}"
        stored.write_bytes(payload)
        paths.append(stored)
        files.append({"name": clean, "stored": str(stored.relative_to(ROOT)), "bytes": len(payload), "sha256": checksum_bytes(payload)})
    if not paths:
        raise ValueError("No files were included in the upload")
    return paths, files


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, "text/html; charset=utf-8", INDEX_PATH.read_bytes())
            return
        if parsed.path == "/api/health":
            self._send(200, "application/json; charset=utf-8", json.dumps(db_counts()).encode())
            return
        if parsed.path == "/api/sources":
            self._send(200, "application/json; charset=utf-8", json.dumps(source_rows()).encode())
            return
        if parsed.path == "/api/llm":
            config = llm_settings()
            self._send(200, "application/json; charset=utf-8", json.dumps({"configured": config["configured"], "model": config["model"]}).encode())
            return
        if parsed.path == "/api/jobs":
            self._send(200, "application/json; charset=utf-8", json.dumps(list_jobs(), ensure_ascii=False).encode())
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with JOB_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._send(404, "application/json; charset=utf-8", b'{"error":"job not found"}')
                return
            self._send(200, "application/json; charset=utf-8", json.dumps(job, ensure_ascii=False).encode())
            return
        if parsed.path == "/api/search":
            question = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not question:
                self._send(400, "application/json; charset=utf-8", b'{"error":"missing q"}')
                return
            self._send(200, "application/json; charset=utf-8", json.dumps(search(question), ensure_ascii=False).encode())
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD_BYTES:
                    raise ValueError(f"Upload must be between 1 byte and {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
                job_id = uuid.uuid4().hex[:12]
                body = self.rfile.read(length)
                paths, files = parse_upload(body, self.headers.get("Content-Type", ""), job_id)
                job = {
                    "id": job_id,
                    "status": "queued",
                    "message": "Files received; processing is queued",
                    "created_at": now(),
                    "updated_at": now(),
                    "files": files,
                }
                with JOB_LOCK:
                    JOBS[job_id] = job
                    persist_job(job)
                threading.Thread(target=run_ingestion, args=(job_id, paths), daemon=True).start()
                self._send(202, "application/json; charset=utf-8", json.dumps(job, ensure_ascii=False).encode())
            except Exception as exc:
                self._send(400, "application/json; charset=utf-8", json.dumps({"error": str(exc)}).encode())
            return
        if parsed.path != "/api/ask":
            self._send(404, "application/json; charset=utf-8", b'{"error":"Not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = str(payload.get("question", "")).strip()
            if not question:
                self._send(400, "application/json; charset=utf-8", b'{"error":"missing question"}')
                return
            evidence = search(question)
            result = ask_llm(question, evidence)
            result.update({"question": question, "facts": evidence["facts"], "documents": evidence["documents"]})
            self._send(200, "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False).encode())
        except Exception as exc:
            self._send(500, "application/json; charset=utf-8", json.dumps({"error": str(exc)}).encode())

    def log_message(self, format: str, *args: object) -> None:
        print(f"[ui] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    load_existing_jobs()
    print(f"Agriculture Knowledge Base UI: http://{HOST}:{PORT}")
    print("Press Ctrl-C to stop.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
