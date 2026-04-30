"""Merge scanner findings into a normalized JSONL stream."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

from ..utils.io import utc_timestamp, write_jsonl
from .code_fingerprints import compute_fingerprints


def load_findings(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    return data.get("findings", [])


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bandit", type=Path, required=True, help="Bandit JSON input.")
    parser.add_argument("--semgrep", type=Path, required=True, help="Semgrep JSON input.")
    parser.add_argument(
        "--extra",
        type=Path,
        action="append",
        default=[],
        help="Optional additional JSON reports to merge.",
    )
    parser.add_argument("--out", type=Path, required=True, help="Normalized JSONL output.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    merged: List[dict] = []
    inputs: List[dict] = list(load_findings(args.bandit)) + list(load_findings(args.semgrep))
    for extra in args.extra:
        inputs.extend(list(load_findings(extra)))

    for record in inputs:
        token_hash, ast_hash = compute_fingerprints(record.get("code", ""))
        normalized = {
            "finding_id": record.get("finding_id"),
            "prompt_id": record.get("prompt_id"),
            "prompt_text": record.get("prompt_text"),
            "completion_id": record.get("completion_id"),
            "language": record.get("language", "python"),
            "generator": record.get("generator"),
            "model": record.get("model"),
            "tool": record.get("tool"),
            "rule_id": record.get("rule_id"),
            "rule_name": record.get("rule_name"),
            "severity": record.get("severity"),
            "confidence": record.get("confidence"),
            "message": record.get("message"),
            "line": record.get("line"),
            "end_line": record.get("end_line"),
            "file": record.get("file"),
            "code": record.get("code"),
            "created_at": utc_timestamp(),
            "normalized_token_hash": token_hash,
            "ast_hash": ast_hash,
            "ai_evidence": record.get("ai_evidence"),
        }
        merged.append(normalized)

    write_jsonl(args.out, merged)


if __name__ == "__main__":
    main()
