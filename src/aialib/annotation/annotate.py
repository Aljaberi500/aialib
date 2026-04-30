"""Annotate normalized findings with CWE/OWASP, ATLAS, and AI-aware metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from ..utils.io import hash_text, read_jsonl, write_jsonl

DEFAULT_RULES_PATH = Path("configs/annotation_rules.yaml")
REVIEW_STATUSES = {"unreviewed", "verified_true", "false_positive", "disputed"}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES_PATH,
        help=f"Annotation rules YAML (default: {DEFAULT_RULES_PATH})",
    )
    return parser


def ensure_list(values: List[str] | str | None, fallback: List[str]) -> List[str]:
    if values is None:
        return list(fallback)
    if isinstance(values, list):
        return values or list(fallback)
    return [values]


def load_rulebook(path: Path) -> Tuple[Dict[str, object], Dict[str, Dict[str, object]]]:
    if not path.exists():
        raise FileNotFoundError(f"Annotation rules not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    defaults = data.get("defaults", {})
    rules = data.get("rules", {})
    return defaults, rules


def normalize_severity(raw: str | None) -> str:
    if not raw:
        return "MEDIUM"
    mapping = {
        "ERROR": "HIGH",
        "WARNING": "MEDIUM",
        "INFO": "LOW",
    }
    normalized = raw.upper()
    return mapping.get(normalized, normalized)


def annotate_record(record: dict, defaults: Dict[str, object], rules: Dict[str, dict]) -> dict:
    mapping = rules.get(record.get("rule_id"), {})
    merged = {**defaults, **mapping}

    ai_cause = ensure_list(merged.get("ai_cause"), ensure_list(defaults.get("ai_cause"), ["unspecified"]))
    propagation = ensure_list(
        merged.get("propagation_vector"),
        ensure_list(defaults.get("propagation_vector"), ["unknown"]),
    )
    human_factor = ensure_list(
        merged.get("human_ai_factor"),
        ensure_list(defaults.get("human_ai_factor"), ["unspecified"]),
    )
    atlas = ensure_list(
        merged.get("atlas_techniques"),
        ensure_list(defaults.get("atlas_techniques"), ["ATLAS:Model Misuse"]),
    )

    cwe_id = merged.get("cwe_id", "CWE-000")
    owasp_tag = merged.get("owasp_tag", "A10:2021-Insufficient Logging & Monitoring")
    mitigation = merged.get(
        "mitigation_short", "Review and harden the generated code before deployment."
    )

    vuln_id = hash_text(f"{record.get('finding_id')}|{cwe_id}|{record.get('tool')}")
    evidence_ref = f"{record.get('file','?')}:{record.get('line','?')}"
    sink_api = merged.get("sink_api", "unspecified")

    review_status = "unreviewed"
    if review_status not in REVIEW_STATUSES:
        raise ValueError(f"Invalid default review status: {review_status}")

    detection_tools = record.get("detection_tools") or [record.get("tool")]
    annotated = {
        "vuln_id": vuln_id,
        "language": record.get("language", "python"),
        "generator": record.get("generator", "unknown"),
        "prompt_id": record.get("prompt_id"),
        "completion_id": record.get("completion_id"),
        "cwe_id": cwe_id,
        "owasp_tag": owasp_tag,
        "severity": normalize_severity(record.get("severity")),
        "sink_api": sink_api,
        "ai_cause": ai_cause,
        "propagation_vector": propagation,
        "human_ai_factor": human_factor,
        "detection_tools": detection_tools,
        "atlas_techniques": atlas,
        "validation_level": "static_only",
        "mitigation_short": mitigation,
        "evidence_ref": evidence_ref,
        "notes": record.get("message"),
        "prompt_text": record.get("prompt_text"),
        "rule_id": record.get("rule_id"),
        "normalized_token_hash": record.get("normalized_token_hash"),
        "ast_hash": record.get("ast_hash"),
        "review_status": review_status,
        "reviewer_id": None,
        "review_timestamp": None,
        "review_notes": None,
        "ai_evidence": record.get("ai_evidence"),
        "source_findings": record.get("source_findings"),
    }
    return annotated


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    defaults, rules = load_rulebook(args.rules)
    findings = read_jsonl(args.findings)
    annotated = [annotate_record(record, defaults, rules) for record in findings]
    write_jsonl(args.out, annotated)


if __name__ == "__main__":
    main()
