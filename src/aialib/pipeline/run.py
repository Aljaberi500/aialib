"""End-to-end pipeline runner with ablations, caching, and manifests."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List

from .. import __version__ as PIPELINE_VERSION
from ..utils.io import read_jsonl
from .manifest import write_run_manifest


def run_module(module: str, *args: str) -> None:
    cmd = [sys.executable, "-m", module, *args]
    result = subprocess.run(cmd, check=False, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{module} failed with code {result.returncode}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("local", "openai", "openai_direct", "k2think", "anthropic"), default="local")
    parser.add_argument("--detectors", nargs="+", choices=("bandit", "semgrep", "ai"), default=["bandit", "semgrep", "ai"], help="Subset of detectors to run.")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--model", type=str)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of prompts processed.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prompts-spec", type=Path, default=Path("data/prompts_v2.yaml"))
    parser.add_argument("--prompts", type=Path, default=Path("data/prompts_expanded.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/run_manifest.json"))
    parser.add_argument("--completions", type=Path, default=Path("data/completions.jsonl"))
    parser.add_argument("--bandit-out", type=Path, default=Path("reports/bandit.json"))
    parser.add_argument("--semgrep-out", type=Path, default=Path("reports/semgrep.json"))
    parser.add_argument("--ai-out", type=Path, default=Path("reports/ai_risks.json"))
    parser.add_argument("--depcheck-out", type=Path, default=Path("reports/depcheck.json"))
    parser.add_argument("--depcheck-online", action="store_true", help="Enable online PyPI validation in depcheck.")
    parser.add_argument("--depcheck-timeout", type=float, default=5.0, help="Online depcheck request timeout (seconds).")
    parser.add_argument("--findings", type=Path, default=Path("reports/findings.jsonl"))
    parser.add_argument("--ensemble", type=Path, default=Path("reports/findings_ensemble.jsonl"))
    parser.add_argument("--annotations", type=Path, default=Path("data/annotations.jsonl"))
    parser.add_argument("--sarif", type=Path, default=Path("out/threat_library.sarif"))
    parser.add_argument("--csv", type=Path, default=Path("out/threat_library.csv"))
    parser.add_argument("--sqlite", type=Path, default=Path("out/threat_library.sqlite"))
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    # 1) Expand prompts (deterministic)
    run_module(
        "aialib.generation.expand",
        "--spec",
        str(args.prompts_spec),
        "--out",
        str(args.prompts),
        "--manifest",
        str(args.manifest),
        "--seed",
        str(args.seed),
        "--stratify",
        "family",
        "--propagate",
    )

    # 2) Generate completions (resume/cached)
    gen_args: List[str] = [
        "--prompts",
        str(args.prompts),
        "--out",
        str(args.completions),
        "--provider",
        args.provider,
        "--k",
        str(args.k),
        "--temperature",
        str(args.temperature),
        "--top-p",
        str(args.top_p),
        "--seed",
        str(args.seed),
        "--request-timeout",
        str(args.request_timeout),
    ]
    if args.max_tokens is not None:
        gen_args.extend(["--max-tokens", str(args.max_tokens)])
    if args.model:
        gen_args.extend(["--model", args.model])
    if args.resume:
        gen_args.append("--resume")
    run_module("aialib.generation.generate", *gen_args)

    # If --limit is set, trim prompts for this run
    if args.limit is not None and args.prompts.exists():
        tmp_prompts = Path("tmp/prompts_limited.jsonl")
        tmp_prompts.parent.mkdir(parents=True, exist_ok=True)
        lines = args.prompts.read_text(encoding="utf-8").splitlines()
        tmp_prompts.write_text("\n".join(lines[: args.limit]) + ("\n" if lines else ""), encoding="utf-8")
        gen_args[gen_args.index(str(args.prompts)) + 0] = str(tmp_prompts)

    # 3) Run detectors
    detectors_run = []
    if "bandit" in args.detectors:
        run_module(
            "aialib.analysis.run_bandit",
            "--in",
            str(args.completions),
            "--out",
            str(args.bandit_out),
            "--config",
            "configs/bandit.yml",
        )
        detectors_run.append("bandit")
    if "semgrep" in args.detectors:
        run_module(
            "aialib.analysis.run_semgrep",
            "--in",
            str(args.completions),
            "--out",
            str(args.semgrep_out),
            "--config",
            "configs/semgrep.yml",
        )
        detectors_run.append("semgrep")
    if "ai" in args.detectors:
        run_module(
            "aialib.analysis.detect_ai_risks",
            "--in",
            str(args.completions),
            "--out",
            str(args.ai_out),
            "--config",
            "configs/ai_risk_rules.yaml",
        )
        detectors_run.append("ai-risk-detector")

    # Dependency checker (supply chain) always on; harmless offline
    dep_args = [
        "--in", str(args.completions),
        "--registry", "data/registry/pypi_index.json",
        "--out", str(args.depcheck_out),
    ]
    # Allow env override or explicit CLI flag
    import os as _os
    online_env = (_os.getenv("AIALIB_DEPCHECK_ONLINE", "").lower() in {"1", "true", "yes"})
    if args.depcheck_online or online_env:
        dep_args.extend(["--online", "--timeout", str(args.depcheck_timeout)])
    run_module("aialib.analysis.depcheck", *dep_args)

    # 4) Merge raw findings
    merge_args = [
        "--bandit",
        str(args.bandit_out),
        "--semgrep",
        str(args.semgrep_out),
        "--extra",
        str(args.ai_out),
        "--extra",
        str(args.depcheck_out),
        "--out",
        str(args.findings),
    ]
    run_module("aialib.analysis.merge_findings", *merge_args)

    # 5) Ensemble merge (dedupe + tool votes)
    run_module(
        "aialib.analysis.ensemble_merge",
        "--in",
        str(args.findings),
        "--out",
        str(args.ensemble),
    )

    # 5b) Propagation persistence report (optional)
    run_module(
        "aialib.analysis.propagation",
        "--findings",
        str(args.ensemble),
        "--out",
        "reports/propagation_report.json",
    )

    # 6) Annotate -> Validation patches
    run_module(
        "aialib.annotation.annotate",
        "--findings",
        str(args.ensemble),
        "--out",
        str(args.annotations),
        "--rules",
        "configs/annotation_rules.yaml",
    )
    # Lightweight runtime validations
    run_module(
        "aialib.analysis.validate_runtime",
        "--findings",
        str(args.ensemble),
        "--out",
        "reports/validation_runtime.json",
    )
    run_module(
        "aialib.annotation.augment_validation",
        "--annotations",
        str(args.annotations),
        "--validation",
        "reports/validation_runtime.json",
        "--out",
        str(args.annotations),
    )
    # 7) Write manifest early and attach run_id before validate/export
    counts_family = {}
    counts_cwe = {}
    for item in read_jsonl(args.prompts):
        fam = item.get("family") or "unknown"
        counts_family[fam] = counts_family.get(fam, 0) + 1
        for cwe in item.get("cwe_targets") or []:
            counts_cwe[cwe] = counts_cwe.get(cwe, 0) + 1
    gen_meta = {
        "provider": args.provider,
        "model": args.model,
        "k": args.k,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "system_prompt": "You are generating code snippets for security testing.",
    }
    run_id = write_run_manifest(
        args.manifest,
        seed=args.seed,
        prompt_spec_path=args.prompts_spec,
        prompts_expanded_path=args.prompts,
        prompt_counts_by_family=counts_family,
        prompt_counts_by_cwe=counts_cwe,
        language="python",
        analyzers=detectors_run + ["depcheck"],
        providers=[args.provider],
        generation=gen_meta,
    )

    run_module(
        "aialib.annotation.augment_runid",
        "--annotations",
        str(args.annotations),
        "--manifest",
        str(args.manifest),
        "--out",
        str(args.annotations),
    )

    # 8) Validate and Export
    run_module(
        "aialib.quality.validate",
        "--annotations",
        str(args.annotations),
        "--schema",
        "schemas/threat_entry.schema.json",
        "--rules",
        "configs/annotation_rules.yaml",
        "--atlas-catalog",
        "configs/atlas_catalog.yaml",
        "--coverage-report",
        "reports/mapping_coverage.json",
        "--novelty-report",
        "reports/novelty_report.json",
    )
    run_module(
        "aialib.export.export_library",
        "--annotations",
        str(args.annotations),
        "--csv",
        str(args.csv),
        "--sqlite",
        str(args.sqlite),
    )

    # SARIF export for CI
    run_module(
        "aialib.export.export_sarif",
        "--annotations",
        str(args.annotations),
        "--out",
        str(args.sarif),
    )

    # Trust calibration (uses any applied human reviews)
    run_module(
        "aialib.analysis.trust_calibration",
        "--annotations",
        str(args.annotations),
        "--out",
        "reports/trust_report.json",
    )

    # Final reporting

    print(
        f"Pipeline complete (v{PIPELINE_VERSION}). Outputs: {args.annotations}, {args.csv}, {args.sqlite}, {args.sarif}, manifest={args.manifest}"
    )


if __name__ == "__main__":
    main()
