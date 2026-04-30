"""Process a single snippet through the pipeline without running make all."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ..utils.io import hash_text, read_jsonl, utc_timestamp, write_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", type=Path, required=True, help="Path to the code snippet file.")
    parser.add_argument("--prompt-id", type=str, help="Optional prompt identifier.")
    parser.add_argument("--prompt-text", type=str, default="Manual snippet")
    parser.add_argument("--out-dir", type=Path, default=Path("out/manual_run"))
    parser.add_argument("--language", type=str, default="python")
    parser.add_argument("--bandit-config", type=Path, default=Path("configs/bandit.yml"))
    parser.add_argument("--semgrep-config", type=Path, default=Path("configs/semgrep.yml"))
    parser.add_argument("--ai-risk-config", type=Path, default=Path("configs/ai_risk_rules.yaml"))
    parser.add_argument("--rules", type=Path, default=Path("configs/annotation_rules.yaml"))
    parser.add_argument("--atlas", type=Path, default=Path("configs/atlas_catalog.yaml"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/threat_entry.schema.json"))
    return parser


def run_module(module: str, *args: str) -> None:
    cmd = [sys.executable, "-m", module, *args]
    result = subprocess.run(cmd, check=False, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{module} failed with code {result.returncode}")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    code = args.code.read_text(encoding="utf-8")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    prompt_id = args.prompt_id or f"manual_{hash_text(code)[:8]}"
    completion_id = f"{prompt_id}-1"

    completions_path = args.out_dir / "manual_completions.jsonl"
    bandit_path = args.out_dir / "manual_bandit.json"
    semgrep_path = args.out_dir / "manual_semgrep.json"
    ai_risks_path = args.out_dir / "manual_ai_risks.json"
    findings_path = args.out_dir / "manual_findings.jsonl"
    annotations_path = args.out_dir / "manual_annotations.jsonl"
    coverage_path = args.out_dir / "manual_coverage.json"
    novelty_path = args.out_dir / "manual_novelty.json"
    csv_path = args.out_dir / "manual_threat_library.csv"
    sqlite_path = args.out_dir / "manual_threat_library.sqlite"

    record = {
        "prompt_id": prompt_id,
        "prompt_text": args.prompt_text,
        "completion_id": completion_id,
        "code": code,
        "language": args.language,
        "generator": "manual",
        "model": "manual",
        "temperature": 0,
        "seed": 0,
        "created_at": utc_timestamp(),
    }
    write_jsonl(completions_path, [record])

    run_module(
        "aialib.analysis.run_bandit",
        "--in",
        str(completions_path),
        "--out",
        str(bandit_path),
        "--config",
        str(args.bandit_config),
    )
    run_module(
        "aialib.analysis.run_semgrep",
        "--in",
        str(completions_path),
        "--out",
        str(semgrep_path),
        "--config",
        str(args.semgrep_config),
    )
    run_module(
        "aialib.analysis.detect_ai_risks",
        "--in",
        str(completions_path),
        "--out",
        str(ai_risks_path),
        "--config",
        str(args.ai_risk_config),
    )
    run_module(
        "aialib.analysis.merge_findings",
        "--bandit",
        str(bandit_path),
        "--semgrep",
        str(semgrep_path),
        "--extra",
        str(ai_risks_path),
        "--out",
        str(findings_path),
    )

    findings = read_jsonl(findings_path)
    if not findings:
        print(
            "No findings generated for this snippet; skipping annotation, validation, and export."
        )
        return
    run_module(
        "aialib.annotation.annotate",
        "--findings",
        str(findings_path),
        "--out",
        str(annotations_path),
        "--rules",
        str(args.rules),
    )
    run_module(
        "aialib.quality.validate",
        "--annotations",
        str(annotations_path),
        "--schema",
        str(args.schema),
        "--rules",
        str(args.rules),
        "--atlas-catalog",
        str(args.atlas),
        "--coverage-report",
        str(coverage_path),
        "--novelty-report",
        str(novelty_path),
    )
    run_module(
        "aialib.export.export_library",
        "--annotations",
        str(annotations_path),
        "--csv",
        str(csv_path),
        "--sqlite",
        str(sqlite_path),
    )
    print(f"Manual pipeline complete. Outputs stored in {args.out_dir}")


if __name__ == "__main__":
    main()
