"""CI gating: fail builds based on configurable thresholds."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

import yaml

from ..utils.io import read_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", required=True, type=Path)
    p.add_argument("--config", type=Path, default=Path("configs/gating.yaml"))
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    annotations = read_jsonl(args.annotations)
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) if args.config.exists() else {}
    max_high = int(cfg.get("max_high", 9999))
    block_atlas = set(cfg.get("block_atlas", []))

    high = [r for r in annotations if (r.get("severity") or "").upper() == "HIGH"]
    if len(high) > max_high:
        print(f"Gating failure: HIGH findings {len(high)} > threshold {max_high}", file=sys.stderr)
        raise SystemExit(2)

    if block_atlas:
        blocked = [r for r in annotations if set(r.get("atlas_techniques") or []) & block_atlas]
        if blocked:
            print(
                f"Gating failure: {len(blocked)} findings include blocked ATLAS techniques: {sorted(block_atlas)}",
                file=sys.stderr,
            )
            raise SystemExit(3)

    print("Gating checks passed.")


if __name__ == "__main__":
    main()

