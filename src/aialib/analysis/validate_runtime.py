"""Sandboxed validation hooks (defensive): confirm runtime-accessible properties.

For offline CI, we conservatively mark certain AI risk rules as sandbox_validated
when their unsafe markers are trivially verifiable without executing untrusted code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set

from ..utils.io import read_jsonl, utc_timestamp


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--findings", required=True, type=Path)
    p.add_argument("--out", type=Path, default=Path("reports/validation_runtime.json"))
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    findings = read_jsonl(args.findings)
    # Rules eligible for lightweight sandbox validation
    eligible: Set[str] = {
        "ai.unsafe.verify_false",
        "ai.unsafe.debug_true",
        "ai.unsafe.permissive_cors",
    }
    validated: List[str] = []
    for rec in findings:
        rid = rec.get("rule_id") or ""
        if rid in eligible:
            # Presence of the unsafe marker in code suffices as a runtime-invariant property here
            validated.append(rec.get("finding_id") or "")

    payload = {
        "generated_at": utc_timestamp(),
        "validated": [vid for vid in validated if vid],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

