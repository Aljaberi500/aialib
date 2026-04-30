"""Patch annotations with validation_level based on runtime validation results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..utils.io import read_jsonl, write_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", required=True, type=Path)
    p.add_argument("--validation", required=True, type=Path)
    p.add_argument("--out", type=Path, default=Path("data/annotations.jsonl"))
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    ann = read_jsonl(args.annotations)
    try:
        data = json.loads(args.validation.read_text(encoding="utf-8"))
    except Exception:
        data = {"validated": []}
    validated = set(data.get("validated") or [])
    for rec in ann:
        if rec.get("vuln_id") in validated or rec.get("source_findings") and any(fid in validated for fid in (rec.get("source_findings") or [])):
            rec["validation_level"] = "sandbox_validated"
        elif rec.get("review_status") == "verified_true":
            rec["validation_level"] = "manually_reviewed"
        else:
            rec["validation_level"] = rec.get("validation_level") or "static_only"
    write_jsonl(args.out, ann)


if __name__ == "__main__":
    main()

