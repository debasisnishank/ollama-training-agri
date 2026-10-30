#!/usr/bin/env python3
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agri_rag.vector import build_index


if __name__ == "__main__":
    report = build_index()
    print(json.dumps(report, indent=2))

