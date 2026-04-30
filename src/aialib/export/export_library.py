"""Export annotated findings to CSV and SQLite."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import List

from ..utils.io import read_jsonl


REQUIRED_FIELDS = [
    "run_id",
    "vuln_id",
    "language",
    "generator",
    "prompt_id",
    "completion_id",
    "cwe_id",
    "owasp_tag",
    "severity",
    "sink_api",
    "ai_cause[]",
    "propagation_vector[]",
    "human_ai_factor[]",
    "atlas_techniques[]",
    "detection_tools[]",
    "validation_level",
    "mitigation_short",
    "evidence_ref",
    "notes",
    "normalized_token_hash",
    "ast_hash",
    "review_status",
    "ai_evidence",
]

OPTIONAL_FIELDS = [
    "prompt_text",
    "rule_id",
    "reviewer_id",
    "review_timestamp",
    "review_notes",
    "source_findings[]",
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--sqlite", required=True, type=Path)
    return parser


def normalize_entry(entry: dict) -> dict:
    formatted = {}
    for field in REQUIRED_FIELDS:
        if field.endswith("[]"):
            key = field.rstrip("[]")
            value = entry.get(key) or []
            formatted[field] = json.dumps(value, sort_keys=True)
        else:
            if field == "ai_evidence":
                formatted[field] = json.dumps(entry.get("ai_evidence"), sort_keys=True)
            else:
                formatted[field] = entry.get(field)
    for field in OPTIONAL_FIELDS:
        if field in entry:
            formatted[field] = entry[field]
    return formatted


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = REQUIRED_FIELDS + [f for f in OPTIONAL_FIELDS if any(f in r for r in rows)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_sqlite(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS "threat_library";')
        columns_sql = ", ".join(f'"{field}" TEXT' for field in REQUIRED_FIELDS + OPTIONAL_FIELDS)
        cursor.execute(f'CREATE TABLE "threat_library" ({columns_sql});')
        columns = REQUIRED_FIELDS + OPTIONAL_FIELDS
        column_sql = ", ".join(f'"{field}"' for field in columns)
        for row in rows:
            values = [row.get(field) for field in REQUIRED_FIELDS + OPTIONAL_FIELDS]
            placeholders = ", ".join("?" for _ in values)
            insert_sql = f'INSERT INTO "threat_library" ({column_sql}) VALUES ({placeholders});'
            cursor.execute(insert_sql, values)
        conn.commit()


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    if not annotations:
        raise SystemExit("No annotations provided; run annotate step first.")

    normalized_rows = [normalize_entry(entry) for entry in annotations]
    write_csv(args.csv, normalized_rows)
    write_sqlite(args.sqlite, normalized_rows)


if __name__ == "__main__":
    main()
