from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import csv
import io
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb
import requests
from bs4 import BeautifulSoup
from docx import Document
from openpyxl import load_workbook

try:
    from pypdf import PdfReader
except ImportError:  # Optional until PDF uploads are used.
    PdfReader = None


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "sources.json"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WEB_RAW_DIR = RAW_DIR / "web"
LOCAL_RAW_DIR = RAW_DIR / "local"
DB_PATH = DATA_DIR / "knowledge_base.duckdb"


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=json_default)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return value[:100] or "source"


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def numeric_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = normalize_text(value).replace(",", "")
    if not text or text.startswith("="):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def guess_unit(metric: str) -> str:
    key = metric.lower()
    if "rain" in key or "ppt" in key or "precip" in key:
        return "mm_or_source_unit"
    if "acre" in key:
        return "acre_or_source_unit"
    if "ndvi" in key:
        return "ndvi_or_source_unit"
    if "soil" in key or "moisture" in key:
        return "source_unit"
    if "yield" in key:
        return "source_unit"
    return "source_unit"


def row_to_values(row: Iterable[Any]) -> list[Any]:
    values = []
    for cell in row:
        values.append(getattr(cell, "value", cell))
    return values


def find_header_row(rows: list[list[Any]]) -> int:
    best_index = 0
    best_score = -1
    for idx, row in enumerate(rows[:20]):
        values = [normalize_text(v) for v in row]
        nonempty = [v for v in values if v]
        if not nonempty:
            continue
        text_count = sum(numeric_value(v) is None for v in nonempty)
        score = len(nonempty) + (text_count * 0.25)
        if score > best_score:
            best_index = idx
            best_score = score
    return best_index


def extract_workbook(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    metadata = {"file": path.name, "kind": "xlsx", "sheets": []}
    workbook = load_workbook(path, read_only=True, data_only=False)
    for sheet in workbook.worksheets:
        rows = [row_to_values(row) for row in sheet.iter_rows()]
        nonempty_rows = [[v for v in row] for row in rows if any(normalize_text(v) for v in row)]
        if not nonempty_rows:
            continue
        header_index = find_header_row(nonempty_rows)
        headers = []
        for i, value in enumerate(nonempty_rows[header_index]):
            header = normalize_text(value) or f"column_{i + 1}"
            headers.append(header)
        metadata["sheets"].append({
            "name": sheet.title,
            "row_count": len(rows),
            "nonempty_row_count": len(nonempty_rows),
            "header_row_index": header_index + 1,
            "header": headers,
        })
        for row_number, row in enumerate(nonempty_rows, start=1):
            values = [normalize_text(v) for v in row]
            fields = {}
            for col_index, value in enumerate(values):
                if value:
                    fields[headers[col_index] if col_index < len(headers) else f"column_{col_index + 1}"] = value
            if not fields:
                continue
            record_id = f"{path.name}|{sheet.title}|{row_number}"
            records.append({
                "record_id": record_id,
                "source_file": path.name,
                "sheet_name": sheet.title,
                "row_number": row_number,
                "header_row_index": header_index + 1,
                "fields": fields,
                "raw_values": values,
            })
            context = " | ".join(v for v in values[:4] if v)
            for col_index, raw in enumerate(row):
                value = numeric_value(raw)
                if value is None or col_index >= len(headers):
                    continue
                metric = headers[col_index]
                if col_index == 0 and metric.lower() in {"id", "row labels", "village", "district", "taluk", "tehsil"}:
                    continue
                facts.append({
                    "fact_id": f"{record_id}|{col_index + 1}",
                    "source_file": path.name,
                    "sheet_name": sheet.title,
                    "row_number": row_number,
                    "metric": metric,
                    "value": value,
                    "unit": guess_unit(metric),
                    "context": context,
                    "raw_value": normalize_text(raw),
                })
    return records, facts, metadata


def extract_docx(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    document = Document(path)
    chunks: list[dict[str, Any]] = []
    chunk_no = 0
    for paragraph_no, paragraph in enumerate(document.paragraphs, start=1):
        text = normalize_text(paragraph.text)
        if not text:
            continue
        chunk_no += 1
        chunks.append({
            "document_id": f"{path.name}|paragraph|{paragraph_no}",
            "source_file": path.name,
            "source_type": "docx",
            "location": f"paragraph {paragraph_no}",
            "text": text,
        })
    for table_no, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            rows.append([normalize_text(cell.text) for cell in row.cells])
        text = "\n".join(" | ".join(cell for cell in row) for row in rows if any(row))
        if text:
            chunk_no += 1
            chunks.append({
                "document_id": f"{path.name}|table|{table_no}",
                "source_file": path.name,
                "source_type": "docx",
                "location": f"table {table_no}",
                "text": text,
            })
    return chunks, {"file": path.name, "kind": "docx", "chunk_count": len(chunks)}


def extract_delimited(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Extract CSV/TSV files while retaining the original row evidence."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [normalize_text(h) or f"column_{i + 1}" for i, h in enumerate(reader.fieldnames or [])]
    records: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        values = [normalize_text(row.get(header, "")) for header in (reader.fieldnames or [])]
        fields = {headers[i]: values[i] for i in range(min(len(headers), len(values))) if values[i]}
        if not fields:
            continue
        record_id = f"{path.name}|row|{row_number}"
        records.append({
            "record_id": record_id,
            "source_file": path.name,
            "sheet_name": path.stem,
            "row_number": row_number,
            "header_row_index": 1,
            "fields": fields,
            "raw_values": values,
        })
        context = " | ".join(v for v in values[:4] if v)
        for col_index, raw in enumerate(values):
            value = numeric_value(raw)
            if value is None or col_index >= len(headers):
                continue
            metric = headers[col_index]
            if col_index == 0 and metric.lower() in {"id", "village", "district", "taluk", "tehsil"}:
                continue
            facts.append({
                "fact_id": f"{record_id}|{col_index + 1}",
                "source_file": path.name,
                "sheet_name": path.stem,
                "row_number": row_number,
                "metric": metric,
                "value": value,
                "unit": guess_unit(metric),
                "context": context,
                "raw_value": raw,
            })
    return records, facts, {"file": path.name, "kind": path.suffix.lower().lstrip("."), "row_count": len(records), "header": headers}


def extract_text_file(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract narrative files into location-aware chunks for retrieval."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("PDF upload support requires pypdf; install requirements.txt")
        reader = PdfReader(str(path))
        chunks = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                chunks.append({
                    "document_id": f"{path.name}|page|{page_no}",
                    "source_file": path.name,
                    "source_type": "pdf",
                    "location": f"page {page_no}",
                    "text": text,
                })
        return chunks, {"file": path.name, "kind": "pdf", "page_count": len(reader.pages), "chunk_count": len(chunks)}
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        raw = BeautifulSoup(raw, "html.parser").get_text("\n", strip=True)
    elif suffix == ".json":
        try:
            raw = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    paragraphs = [normalize_text(part) for part in re.split(r"\n\s*\n|\r\n", raw) if normalize_text(part)]
    chunks = []
    for paragraph_no, text in enumerate(paragraphs, start=1):
        chunks.append({
            "document_id": f"{path.name}|section|{paragraph_no}",
            "source_file": path.name,
            "source_type": suffix.lstrip(".") or "text",
            "location": f"section {paragraph_no}",
            "text": text[:12000],
        })
    return chunks, {"file": path.name, "kind": suffix.lstrip(".") or "text", "chunk_count": len(chunks)}


def snapshot_web_sources(config: dict[str, Any]) -> list[dict[str, Any]]:
    WEB_RAW_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = []
    headers = {"User-Agent": "AgricultureRAG/0.1 (+local knowledge-base build)"}
    for source in config.get("web_sources", []):
        source_id = safe_name(source["id"])
        try:
            if source.get("method", "GET").upper() == "POST":
                response = requests.post(source["url"], json=source.get("payload", {}), headers=headers, timeout=30)
            else:
                response = requests.get(source["url"], headers=headers, timeout=30)
            response.raise_for_status()
            content = response.content
            suffix = ".json" if "json" in response.headers.get("content-type", "").lower() else ".html"
            output = WEB_RAW_DIR / f"{source_id}{suffix}"
            output.write_bytes(content)
            text = content.decode(response.encoding or "utf-8", errors="replace")
            visible_text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
            snapshots.append({
                "source_id": source["id"],
                "url": source["url"],
                "kind": source.get("kind"),
                "authority": source.get("authority"),
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "path": str(output.relative_to(ROOT)),
                "sha256": checksum_bytes(content),
                "visible_text_preview": visible_text[:500],
                "error": None,
            })
        except Exception as exc:  # Keep the build moving and record the failure.
            snapshots.append({
                "source_id": source["id"],
                "url": source["url"],
                "kind": source.get("kind"),
                "authority": source.get("authority"),
                "status_code": None,
                "content_type": None,
                "path": None,
                "sha256": None,
                "visible_text_preview": None,
                "error": repr(exc),
            })
    return snapshots


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json_text(row) + "\n")


def build_database(records: list[dict[str, Any]], facts: list[dict[str, Any]], documents: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = DB_PATH.with_suffix(".duckdb.tmp")
    if temporary_path.exists():
        temporary_path.unlink()
    con = duckdb.connect(str(temporary_path))
    con.execute("""
        create table workbook_rows (
            record_id varchar,
            source_file varchar,
            sheet_name varchar,
            row_number integer,
            header_row_index integer,
            fields_json varchar,
            raw_values_json varchar
        )
    """)
    con.execute("""
        create table agricultural_facts (
            fact_id varchar,
            source_file varchar,
            sheet_name varchar,
            row_number integer,
            metric varchar,
            value double,
            unit varchar,
            context varchar,
            raw_value varchar
        )
    """)
    con.execute("""
        create table document_chunks (
            document_id varchar,
            source_file varchar,
            source_type varchar,
            location varchar,
            text varchar
        )
    """)
    con.execute("""
        create table source_manifest (
            source_id varchar,
            source_type varchar,
            source varchar,
            url varchar,
            path varchar,
            status varchar,
            sha256 varchar,
            notes varchar
        )
    """)
    con.executemany(
        "insert into workbook_rows values (?, ?, ?, ?, ?, ?, ?)",
        [(r["record_id"], r["source_file"], r["sheet_name"], r["row_number"], r["header_row_index"], json_text(r["fields"]), json_text(r["raw_values"])) for r in records],
    )
    con.executemany(
        "insert into agricultural_facts values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(f["fact_id"], f["source_file"], f["sheet_name"], f["row_number"], f["metric"], f["value"], f["unit"], f["context"], f["raw_value"]) for f in facts],
    )
    con.executemany(
        "insert into document_chunks values (?, ?, ?, ?, ?)",
        [(d["document_id"], d["source_file"], d["source_type"], d["location"], d["text"]) for d in documents],
    )
    manifest_rows = []
    for local in manifest.get("local", []):
        manifest_rows.append((local["source_id"], "local", local["source"], None, local.get("path"), local["status"], local.get("sha256"), local.get("notes", "")))
    for web in manifest.get("web", []):
        manifest_rows.append((web["source_id"], "web", web["source_id"], web.get("url"), web.get("path"), "ok" if web.get("error") is None else "error", web.get("sha256"), web.get("error") or ""))
    con.executemany("insert into source_manifest values (?, ?, ?, ?, ?, ?, ?, ?)", manifest_rows)
    con.execute("create index facts_metric on agricultural_facts(metric)")
    con.execute("create index facts_source on agricultural_facts(source_file, sheet_name)")
    con.execute("create index docs_source on document_chunks(source_file)")
    con.close()
    os.replace(temporary_path, DB_PATH)


def build(upload_paths: Iterable[Path] | None = None) -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    local_raw = LOCAL_RAW_DIR / "source_files"
    local_raw.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    local_manifest = []
    workbook_metadata = []
    document_metadata = []
    sources: list[tuple[str, Path]] = [(relative, ROOT / relative) for relative in config.get("local_files", [])]
    for upload_path in upload_paths or []:
        upload_path = Path(upload_path)
        sources.append((f"upload/{upload_path.name}", upload_path))

    for relative, source_path in sources:
        if not source_path.exists():
            local_manifest.append({"source_id": relative, "source": relative, "status": "missing", "path": None})
            continue
        copied = local_raw / source_path.name
        if source_path.resolve() != copied.resolve():
            copied.write_bytes(source_path.read_bytes())
        digest = checksum_bytes(copied.read_bytes())
        local_manifest.append({"source_id": relative, "source": relative, "status": "ok", "path": str(copied.relative_to(ROOT)), "sha256": digest})
        if source_path.suffix.lower() == ".xlsx":
            new_records, new_facts, meta = extract_workbook(source_path)
            records.extend(new_records)
            facts.extend(new_facts)
            for record in new_records:
                note_parts = [
                    normalize_text(value)
                    for value in record["raw_values"]
                    if normalize_text(value)
                ]
                note_text = " | ".join(note_parts)
                lower_note = note_text.lower()
                if len(note_text) >= 120 or "ndvi range" in lower_note or "normalized difference vegetation" in lower_note:
                    documents.append({
                        "document_id": f"{record['record_id']}|note",
                        "source_file": record["source_file"],
                        "source_type": "xlsx_note",
                        "location": f"{record['sheet_name']} row {record['row_number']}",
                        "text": note_text,
                    })
            workbook_metadata.append(meta)
        elif source_path.suffix.lower() in {".csv", ".tsv"}:
            new_records, new_facts, meta = extract_delimited(source_path)
            records.extend(new_records)
            facts.extend(new_facts)
            workbook_metadata.append(meta)
        elif source_path.suffix.lower() == ".docx":
            new_documents, meta = extract_docx(source_path)
            documents.extend(new_documents)
            document_metadata.append(meta)
        elif source_path.suffix.lower() in {".pdf", ".html", ".htm", ".json", ".txt", ".md"}:
            new_documents, meta = extract_text_file(source_path)
            documents.extend(new_documents)
            document_metadata.append(meta)
    web_manifest = snapshot_web_sources(config)
    manifest = {"local": local_manifest, "web": web_manifest}
    write_jsonl(DATA_DIR / "facts.jsonl", facts)
    write_jsonl(DATA_DIR / "documents.jsonl", documents)
    build_database(records, facts, documents, manifest)
    report = {
        "version": "0.1.0",
        "workbook_rows": len(records),
        "agricultural_facts": len(facts),
        "document_chunks": len(documents),
        "workbooks": workbook_metadata,
        "documents": document_metadata,
        "web_snapshots": web_manifest,
        "database": str(DB_PATH.relative_to(ROOT)),
    }
    (DATA_DIR / "manifest.json").write_text(json_text(manifest), encoding="utf-8")
    (DATA_DIR / "ingestion_report.json").write_text(json_text(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = build()
    print(json.dumps({k: result[k] for k in ("workbook_rows", "agricultural_facts", "document_chunks", "database")}, indent=2))

