"""Analyze propagation chains and persistence across prompt variants.

Computes, per lineage_root, whether the same sink pattern (rule_id + normalized_token_hash)
persists across reuse/refactor/secure_refactor variants.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from ..utils.io import read_jsonl, utc_timestamp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports/propagation_report.json"))
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    findings = read_jsonl(args.findings)
    groups: Dict[str, List[tuple[str, tuple[str | None, str | None]]]] = defaultdict(list)
    for rec in findings:
        pid = rec.get("prompt_id") or ""
        # Derive lineage root and variant from the prompt_id suffixes.
        # Include base prompts as their own root to enable intersections.
        if pid.endswith("-secure_refactor"):
            root = pid[: -len("-secure_refactor")]
            variant = "secure_refactor"
        elif pid.endswith("-refactor"):
            root = pid[: -len("-refactor")]
            variant = "refactor"
        elif pid.endswith("-reuse"):
            root = pid[: -len("-reuse")]
            variant = "reuse"
        else:
            root = pid
            variant = "base"
        sig = (rec.get("rule_id"), rec.get("normalized_token_hash"))
        groups[root].append((variant, sig))

    stats: List[dict] = []
    for root, items in groups.items():
        # Partition by variant
        by_variant: Dict[str, List[Tuple[str | None, str | None]]] = defaultdict(list)
        for variant, sig in items:
            by_variant[variant].append(sig)

        base = set(by_variant.get("base", []))
        reuse = set(by_variant.get("reuse", []))
        refac = set(by_variant.get("refactor", []))
        sref = set(by_variant.get("secure_refactor", []))
        stats.append(
            {
                "lineage_root": root,
                "base_count": len(base),
                "reuse_persistence": len(base & reuse),
                "refactor_persistence": len(base & refac),
                "secure_refactor_persistence": len(base & sref),
            }
        )

    payload = {
        "generated_at": utc_timestamp(),
        "lineages": len(groups),
        "stats": stats,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
