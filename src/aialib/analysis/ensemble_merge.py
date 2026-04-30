"""Ensemble merge: deduplicate findings and combine tool votes.

Findings are grouped by (prompt_id, completion_id, rule_id, normalized_token_hash)
and merged to a single record with:
  - detection_tools: list of contributing tools
  - source_findings: list of finding_ids
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

from ..utils.io import read_jsonl, write_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", required=True, type=Path)
    parser.add_argument("--out", dest="output_path", required=True, type=Path)
    return parser


def group_key(rec: dict) -> Tuple[str | None, str | None, str | None, str | None]:
    return (
        rec.get("prompt_id"),
        rec.get("completion_id"),
        rec.get("rule_id"),
        rec.get("normalized_token_hash"),
    )


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    records = read_jsonl(args.input_path)
    buckets: Dict[Tuple[str | None, str | None, str | None, str | None], List[dict]] = {}
    for rec in records:
        buckets.setdefault(group_key(rec), []).append(rec)

    merged: List[dict] = []
    for _, items in buckets.items():
        # Stable order: by tool name then finding id
        items = sorted(items, key=lambda r: (r.get("tool") or "", r.get("finding_id") or ""))
        head = dict(items[0])
        tools = []
        sources = []
        for r in items:
            t = r.get("tool") or "unknown"
            if t not in tools:
                tools.append(t)
            if r.get("finding_id"):
                sources.append(r["finding_id"])
        head["detection_tools"] = tools
        head["source_findings"] = sources
        merged.append(head)

    write_jsonl(args.output_path, merged)


if __name__ == "__main__":
    main()

