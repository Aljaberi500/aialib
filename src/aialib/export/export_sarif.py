"""Export annotated findings to SARIF for CI consumption."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from .. import __version__ as PIPELINE_VERSION
from ..utils.io import read_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def to_sarif(annotations: List[dict]) -> Dict[str, object]:
    rules: Dict[str, dict] = {}
    results: List[dict] = []

    for rec in annotations:
        rule_id = rec.get("rule_id") or "unknown"
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": rule_id},
                "fullDescription": {"text": f"Rule {rule_id}"},
                "properties": {
                    "cwe_id": rec.get("cwe_id"),
                    "owasp_tag": rec.get("owasp_tag"),
                },
            }
        level_map = {"LOW": "note", "MEDIUM": "warning", "HIGH": "error"}
        level = level_map.get((rec.get("severity") or "").upper(), "warning")
        loc = {
            "physicalLocation": {
                "artifactLocation": {"uri": rec.get("evidence_ref")},
            }
        }
        run_id = rec.get("run_id")
        results.append(
            {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": rec.get("notes") or ""},
                "locations": [loc],
                "properties": {
                    "run_id": run_id,
                    "prompt_id": rec.get("prompt_id"),
                    "completion_id": rec.get("completion_id"),
                    "generator": rec.get("generator"),
                    "language": rec.get("language"),
                    "ai_cause": rec.get("ai_cause"),
                    "ai_evidence": rec.get("ai_evidence"),
                    "atlas_techniques": rec.get("atlas_techniques"),
                    "validation_level": rec.get("validation_level"),
                    "detection_tools": rec.get("detection_tools"),
                },
            }
        )

    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "aialib",
                        "semanticVersion": PIPELINE_VERSION,
                        "rules": list(rules.values()),
                        "properties": {
                            "run_id": run_id,
                        },
                    }
                },
                "results": results,
            }
        ],
    }
    return sarif


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    sarif = to_sarif(annotations)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(sarif, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
