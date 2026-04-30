"""Quality gate validation for annotated findings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import yaml

import jsonschema

from ..utils.io import read_jsonl
from ..utils.io import utc_timestamp
from ..annotation.annotate import load_rulebook


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path, help="Annotated JSONL path.")
    parser.add_argument("--schema", required=True, type=Path, help="JSON Schema path.")
    parser.add_argument(
        "--rules",
        type=Path,
        default=Path("configs/annotation_rules.yaml"),
        help="Annotation rules YAML path.",
    )
    parser.add_argument(
        "--atlas-catalog",
        type=Path,
        default=Path("configs/atlas_catalog.yaml"),
        help="ATLAS technique catalog.",
    )
    parser.add_argument(
        "--coverage-report",
        type=Path,
        default=Path("reports/mapping_coverage.json"),
        help="Where to write mapping coverage metrics.",
    )
    parser.add_argument(
        "--novelty-report",
        type=Path,
        default=Path("reports/novelty_report.json"),
        help="Where to write dedup/novelty metrics.",
    )
    parser.add_argument(
        "--strict-mapping",
        choices=("strict", "permissive"),
        default="strict",
        help="Fail on unmapped rules in strict mode; warn otherwise.",
    )
    parser.add_argument(
        "--run-manifest",
        type=Path,
        default=Path("data/run_manifest.json"),
        help="Run manifest for provenance and coverage comparison.",
    )
    parser.add_argument(
        "--coverage-min",
        type=int,
        default=1,
        help="Minimum prompts per family; warn/fail if unmet (strict-mapping governs fail/warn).",
    )
    return parser


def load_schema(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_atlas_catalog(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"ATLAS catalog not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return set(data.get("techniques", []))


def validate_schema(records: List[dict], schema: Dict[str, object]) -> List[str]:
    validator = jsonschema.Draft202012Validator(schema)
    errors: List[str] = []
    for index, record in enumerate(records):
        for error in validator.iter_errors(record):
            location = " > ".join(str(part) for part in error.path)
            if location:
                message = f"[record {index}] {location}: {error.message}"
            else:
                message = f"[record {index}] {error.message}"
            errors.append(message)
    return errors


def check_duplicates(records: Iterable[dict]) -> Tuple[List[str], List[str]]:
    seen_vuln: Dict[str, int] = {}
    seen_finding: Dict[Tuple[str, str, str | None, Tuple[str, ...]], int] = {}
    vuln_duplicates: List[str] = []
    finding_duplicates: List[str] = []

    for index, record in enumerate(records):
        vuln_id = record.get("vuln_id")
        key = (
            record.get("prompt_id"),
            record.get("completion_id"),
            record.get("rule_id"),
            tuple(sorted(record.get("detection_tools") or [])),
        )

        if vuln_id:
            prev = seen_vuln.setdefault(vuln_id, index)
            if prev != index:
                vuln_duplicates.append(f"[record {index}] duplicate vuln_id '{vuln_id}' (first seen at record {prev})")

        if key[0] and key[1]:
            prev_finding = seen_finding.setdefault(key, index)
            if prev_finding != index:
                finding_duplicates.append(
                    f"[record {index}] duplicate finding signature {key} (first seen at record {prev_finding})"
                )

    return vuln_duplicates, finding_duplicates


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    if not annotations:
        raise SystemExit("No annotations provided; run annotate step first.")

    schema = load_schema(args.schema)
    _, rules = load_rulebook(args.rules)
    atlas_catalog = load_atlas_catalog(args.atlas_catalog)

    schema_errors = validate_schema(annotations, schema)
    vuln_duplicates, finding_duplicates = check_duplicates(annotations)

    coverage_errors: List[str] = []
    allowed_severities = {"LOW", "MEDIUM", "HIGH"}
    mapped_rule_ids = set(rules.keys())

    tool_totals: Dict[str, Dict[str, float]] = {}
    rule_totals: Dict[str, Dict[str, float]] = {}
    family_totals: Dict[str, Dict[str, float]] = {}

    for index, record in enumerate(annotations):
        rule_id = record.get("rule_id")
        tool = (record.get("detection_tools") or ["unknown"])[0] or "unknown"
        family = "unknown"
        prompt_id = record.get("prompt_id") or ""
        if prompt_id:
            family = prompt_id.split("_")[0]

        tool_entry = tool_totals.setdefault(tool, {"total": 0, "mapped": 0})
        rule_entry = rule_totals.setdefault(rule_id or "unmapped", {"total": 0, "mapped": 0})
        family_entry = family_totals.setdefault(family, {"total": 0, "mapped": 0})

        tool_entry["total"] += 1
        rule_entry["total"] += 1
        family_entry["total"] += 1

        if not rule_id or rule_id not in mapped_rule_ids:
            coverage_errors.append(
                f"[record {index}] missing annotation rule for rule_id '{rule_id}'"
            )
        else:
            tool_entry["mapped"] += 1
            rule_entry["mapped"] += 1
            family_entry["mapped"] += 1

        severity = (record.get("severity") or "").upper()
        if severity not in allowed_severities:
            coverage_errors.append(f"[record {index}] severity '{record.get('severity')}' is not mapped")

        atlas_values = record.get("atlas_techniques") or []
        for technique in atlas_values:
            if technique not in atlas_catalog:
                coverage_errors.append(
                    f"[record {index}] atlas technique '{technique}' not found in catalog"
                )

    # R4: Mapping strictness
    problems = schema_errors + vuln_duplicates + finding_duplicates
    if args.strict_mapping == "strict":
        problems += coverage_errors
    else:
        for warning in coverage_errors:
            print(f"[warn] {warning}", file=sys.stderr)

    # R11: Coverage guardrail via run manifest
    try:
        manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
    except Exception:
        manifest = None
    if manifest and manifest.get("prompt_counts_by_family"):
        fam_counts = manifest["prompt_counts_by_family"]
        for family, count in fam_counts.items():
            if count < args.coverage_min:
                msg = f"family '{family}' underpowered: {count} < {args.coverage_min}"
                if args.strict_mapping == "strict":
                    problems.append(msg)
                else:
                    print(f"[warn] {msg}", file=sys.stderr)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        raise SystemExit(f"Validation failed with {len(problems)} issues.")

    coverage_payload = {
        "generated_at": utc_timestamp(),
        "total_records": len(annotations),
        "tools": {
            tool: {
                "total": stats["total"],
                "mapped": stats["mapped"],
                "coverage_pct": 0 if not stats["total"] else round(stats["mapped"] / stats["total"] * 100, 2),
            }
            for tool, stats in tool_totals.items()
        },
        "rules": {
            rule: {
                "total": stats["total"],
                "mapped": stats["mapped"],
                "coverage_pct": 0 if not stats["total"] else round(stats["mapped"] / stats["total"] * 100, 2),
            }
            for rule, stats in rule_totals.items()
        },
        "families": {
            family: {
                "total": stats["total"],
                "mapped": stats["mapped"],
                "coverage_pct": 0 if not stats["total"] else round(stats["mapped"] / stats["total"] * 100, 2),
            }
            for family, stats in family_totals.items()
        },
    }
    args.coverage_report.parent.mkdir(parents=True, exist_ok=True)
    args.coverage_report.write_text(json.dumps(coverage_payload, indent=2), encoding="utf-8")

    clusters: Dict[Tuple[str | None, str | None, str | None], List[str]] = {}
    for record in annotations:
        key = (
            record.get("cwe_id"),
            record.get("sink_api"),
            record.get("normalized_token_hash"),
        )
        clusters.setdefault(key, []).append(record.get("vuln_id"))

    novelty_payload = {
        "generated_at": utc_timestamp(),
        "rows": len(annotations),
        "unique_patterns": len(clusters),
        "clusters": [
            {
                "cwe_id": key[0],
                "sink_api": key[1],
                "normalized_token_hash": key[2],
                "examples": value[:5],
                "count": len(value),
            }
            for key, value in clusters.items()
        ],
    }
    args.novelty_report.parent.mkdir(parents=True, exist_ok=True)
    args.novelty_report.write_text(json.dumps(novelty_payload, indent=2), encoding="utf-8")

    print(f"Validated {len(annotations)} annotations; schema/mapping/duplicates/novelty OK.")


if __name__ == "__main__":
    main()
