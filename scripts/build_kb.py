#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agri_rag.build import build


if __name__ == "__main__":
    report = build()
    print(f"Built {report['database']}")
    print(f"Workbook rows: {report['workbook_rows']}")
    print(f"Agricultural facts: {report['agricultural_facts']}")
    print(f"Document chunks: {report['document_chunks']}")
    print(f"Web snapshots: {len(report['web_snapshots'])}")

