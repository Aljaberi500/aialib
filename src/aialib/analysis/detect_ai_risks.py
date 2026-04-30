"""Detector for AI-specific risk patterns beyond traditional SAST."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import yaml

from ..utils.io import hash_text, read_jsonl, utc_timestamp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", required=True, type=Path)
    parser.add_argument(
        "--config",
        dest="config_path",
        type=Path,
        default=Path("configs/ai_risk_rules.yaml"),
        help="AI risk detector config.",
    )
    parser.add_argument("--out", dest="output_path", required=True, type=Path)
    return parser


def load_rules(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"AI risk config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("rules", [])


def dependency_matches(code: str, packages: List[str]) -> List[str]:
    hits: List[str] = []
    for name in packages:
        marker = f"import {name}"
        from_marker = f"from {name}"
        if marker in code or from_marker in code:
            hits.append(name)
    return hits


def substring_match(code: str, pattern: str) -> bool:
    return pattern in code


def prompt_mentions_security(prompt_text: str, keywords: List[str]) -> bool:
    normalized = prompt_text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def code_has_markers(code: str, markers: List[str]) -> bool:
    lower_code = code.lower()
    return any(marker.lower() in lower_code for marker in markers)


def run_detector(record: dict, rule: dict) -> List[dict]:
    findings: List[dict] = []
    code = record.get("code", "")
    prompt_text = record.get("prompt_text", "")
    detector_type = rule.get("detector")
    rule_id = rule.get("rule_id")
    severity = rule.get("severity", "MEDIUM")
    description = rule.get("description", rule_id)

    matches: List[str] = []
    evidence_common = {"rule_id": rule_id}
    if detector_type == "dependency":
        pkgs = dependency_matches(code, rule.get("packages", []))
        matches = pkgs
    elif detector_type == "substring":
        if substring_match(code, rule.get("pattern", "")):
            matches = [rule.get("pattern", "pattern")]
    elif detector_type == "misalignment":
        if prompt_mentions_security(prompt_text, rule.get("secure_keywords", [])) and code_has_markers(
            code, rule.get("unsafe_markers", [])
        ):
            matches = ["prompt/code misalignment"]
    elif detector_type == "multifile":
        if code_has_markers(code, rule.get("file_markers", [])) and code_has_markers(
            code, rule.get("sanitizer_tokens", [])
        ):
            if code_has_markers(code, rule.get("bypass_tokens", [])):
                matches = ["sanitizer bypass"]

    if not matches:
        return findings

    for match in matches:
        finding_id = hash_text(
            f"ai-risk|{record.get('prompt_id')}|{record.get('completion_id')}|{rule_id}|{match}"
        )
        ai_evidence: Dict[str, object] = {**evidence_common}
        if detector_type == "dependency":
            ai_evidence.update({"packages": matches})
        elif detector_type == "substring":
            ai_evidence.update({"unsafe_marker": match})
        elif detector_type == "misalignment":
            ai_evidence.update({
                "context_flags": {
                    "secure_keywords_hit": True,
                    "unsafe_markers": rule.get("unsafe_markers", []),
                }
            })
        elif detector_type == "multifile":
            ai_evidence.update({
                "file_markers": rule.get("file_markers", []),
                "sanitizer_tokens": rule.get("sanitizer_tokens", []),
                "bypass_tokens": rule.get("bypass_tokens", []),
            })

        findings.append(
            {
                "finding_id": finding_id,
                "prompt_id": record.get("prompt_id"),
                "completion_id": record.get("completion_id"),
                "language": record.get("language", "python"),
                "generator": record.get("generator"),
                "model": record.get("model"),
                "prompt_text": prompt_text,
                "tool": "ai-risk-detector",
                "rule_id": rule_id,
                "rule_name": description,
                "severity": severity,
                "confidence": "medium",
                "message": f"{description} (signal={match})",
                "file": f"inline:{record.get('prompt_id')}",
                "line": 1,
                "code": code,
                "ai_evidence": ai_evidence,
            }
        )
    return findings


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    completions = read_jsonl(args.input_path)
    if not completions:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(
            json.dumps({"tool": "ai-risk-detector", "generated_at": utc_timestamp(), "findings": []}),
            encoding="utf-8",
        )
        return

    rules = load_rules(args.config_path)
    aggregated: List[dict] = []
    for record in completions:
        for rule in rules:
            aggregated.extend(run_detector(record, rule))

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps(
            {
                "tool": "ai-risk-detector",
                "generated_at": utc_timestamp(),
                "findings": aggregated,
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
