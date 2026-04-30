"""Compute trust calibration metrics from human adjudication data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from ..utils.io import read_jsonl, utc_timestamp

REVIEW_TRUE = "verified_true"
REVIEW_FALSE = "false_positive"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports/trust_report.json"),
        help="Destination for trust calibration metrics.",
    )
    return parser


def accumulate_precision(bucket: Dict[str, float], status: str) -> None:
    bucket["total"] = bucket.get("total", 0) + 1
    if status == REVIEW_TRUE:
        bucket["verified_true"] = bucket.get("verified_true", 0) + 1
    elif status == REVIEW_FALSE:
        bucket["false_positive"] = bucket.get("false_positive", 0) + 1


def compute_precision(buckets: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    report: Dict[str, Dict[str, float]] = {}
    for key, stats in buckets.items():
        positives = stats.get("verified_true", 0)
        negatives = stats.get("false_positive", 0)
        total = positives + negatives
        precision = None
        if total:
            precision = round(positives / total, 3)
        report[key] = {
            "verified_true": positives,
            "false_positive": negatives,
            "precision": precision,
            "reviewed": total,
        }
    return report


def compute_disagreement(records: List[dict]) -> Dict[str, float]:
    clusters: Dict[str, Dict[str, str]] = {}
    for record in records:
        token_hash = record.get("normalized_token_hash")
        tool = (record.get("detection_tools") or ["unknown"])[0] or "unknown"
        status = record.get("review_status")
        if not token_hash:
            continue
        clusters.setdefault(token_hash, {})[tool] = status

    disagreements = 0
    comparable = 0
    for cluster in clusters.values():
        if len(cluster) < 2:
            continue
        statuses = [status for status in cluster.values() if status in {REVIEW_TRUE, REVIEW_FALSE}]
        if len(statuses) < 2:
            continue
        comparable += 1
        if REVIEW_TRUE in statuses and REVIEW_FALSE in statuses:
            disagreements += 1
    rate = 0.0
    if comparable:
        rate = round(disagreements / comparable, 3)
    return {"comparable_pairs": comparable, "disagreements": disagreements, "rate": rate}


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    tool_buckets: Dict[str, Dict[str, float]] = {}
    rule_buckets: Dict[str, Dict[str, float]] = {}
    status_counts: Dict[str, int] = {}

    for record in annotations:
        status = record.get("review_status", "unreviewed")
        status_counts[status] = status_counts.get(status, 0) + 1
        tool = (record.get("detection_tools") or ["unknown"])[0] or "unknown"
        rule = record.get("rule_id") or "unknown"
        if status in {REVIEW_TRUE, REVIEW_FALSE}:
            accumulate_precision(tool_buckets.setdefault(tool, {}), status)
            accumulate_precision(rule_buckets.setdefault(rule, {}), status)

    precision_by_tool = compute_precision(tool_buckets)
    precision_by_rule = compute_precision(rule_buckets)
    disagreement_stats = compute_disagreement(annotations)
    unreviewed = status_counts.get("unreviewed", 0)
    total = sum(status_counts.values()) or 1
    unknown_fraction = round(unreviewed / total, 3)

    payload = {
        "generated_at": utc_timestamp(),
        "precision_by_tool": precision_by_tool,
        "precision_by_rule": precision_by_rule,
        "disagreement_rate": disagreement_stats,
        "review_status_counts": status_counts,
        "unknown_fraction": unknown_fraction,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
