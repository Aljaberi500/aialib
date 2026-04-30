"""Attach run_id from run manifest to annotations for export traceability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..utils.io import read_jsonl, write_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--out", type=Path, default=Path("data/annotations.jsonl"))
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    records = read_jsonl(args.annotations)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        run_id = manifest.get("run_id")
    except Exception:
        run_id = None
    if run_id:
        for r in records:
            r["run_id"] = run_id
    write_jsonl(args.out, records)


if __name__ == "__main__":
    main()

