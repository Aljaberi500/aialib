#!/usr/bin/env python3
"""Recompute Table 1 of the paper from the shipped findings and verify it.

Reads sample_outputs/reports/master_findings.csv, recomputes per-run
finding counts, HIGH/MEDIUM severity counts, and yields, and compares them
against the expected values frozen in the paper (Table 1) and
reports/master_summary.md. Exits non-zero on any mismatch, so it can gate CI.

Usage:
    python scripts/reproduce_table1.py \
        [--findings sample_outputs/reports/master_findings.csv]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

COMPLETIONS_PER_RUN = 536

# Frozen expectations: model -> (findings, HIGH, MED, yield)
EXPECTED = {
    "gpt-4o-mini": (143, 47, 96, 0.267),
    "gpt-4.1": (142, 41, 101, 0.265),
    "claude-sonnet-4-20250514": (115, 56, 59, 0.215),
    "MBZUAI-IFM/K2-Think-v2": (104, 48, 56, 0.194),
}

MODEL_COLUMNS = ["model", "model_name", "generator_model"]
SEVERITY_COLUMNS = ["severity", "normalized_severity", "severity_normalized"]


def pick_column(fieldnames: list[str], candidates: list[str], kind: str) -> str:
    for c in candidates:
        if c in fieldnames:
            return c
    sys.exit(
        f"ERROR: no {kind} column found; looked for {candidates}, "
        f"file has {fieldnames}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--findings",
        type=Path,
        default=Path("sample_outputs/reports/master_findings.csv"),
    )
    args = ap.parse_args()

    with args.findings.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        model_col = pick_column(fields, MODEL_COLUMNS, "model")
        sev_col = pick_column(fields, SEVERITY_COLUMNS, "severity")
        counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"findings": 0, "HIGH": 0, "MEDIUM": 0}
        )
        for row in reader:
            model = row[model_col]
            counts[model]["findings"] += 1
            sev = (row.get(sev_col) or "").upper()
            if sev in ("HIGH", "MEDIUM"):
                counts[model][sev] += 1

    failures: list[str] = []
    print(f"{'model':<28}{'find.':>6}{'HIGH':>6}{'MED':>6}{'yield':>8}")
    for model, (exp_f, exp_h, exp_m, exp_y) in EXPECTED.items():
        got = counts.get(model)
        if got is None:
            failures.append(f"missing run for model {model!r}")
            continue
        y = round(got["findings"] / COMPLETIONS_PER_RUN, 3)
        print(
            f"{model:<28}{got['findings']:>6}{got['HIGH']:>6}"
            f"{got['MEDIUM']:>6}{y:>8}"
        )
        for name, got_v, exp_v in (
            ("findings", got["findings"], exp_f),
            ("HIGH", got["HIGH"], exp_h),
            ("MEDIUM", got["MEDIUM"], exp_m),
            ("yield", y, exp_y),
        ):
            if got_v != exp_v:
                failures.append(f"{model}: {name} = {got_v}, expected {exp_v}")

    total = sum(c["findings"] for c in counts.values())
    print(f"{'TOTAL':<28}{total:>6}")
    if total != 504:
        failures.append(f"total findings = {total}, expected 504")

    if failures:
        print("\nTABLE 1 MISMATCH:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)
    print("\nOK: recomputed values match Table 1 (seed 1337 freeze).")


if __name__ == "__main__":
    main()
