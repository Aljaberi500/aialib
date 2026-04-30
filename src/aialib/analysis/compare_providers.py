"""Compare multiple provider runs on the same prompt suite.

Reads per-run artifacts under each run directory and emits a compact comparison
report (Markdown or JSON) with yield, severity/validation splits, tool mix,
and novelty. Does not modify existing code or artifacts.

Expected layout per run_dir (either a snapshot folder or the repo root):
  run_dir/
    data/run_manifest.json
    data/completions.jsonl
    data/annotations.jsonl
    reports/findings_ensemble.jsonl
    reports/novelty_report.json

Usage:
  python -m aialib.analysis.compare_providers \
      --runs openai_run_1 . \
      --out reports/provider_comparison.md --format md
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass
class RunStats:
    label: str
    path: Path
    run_id: str | None
    provider: str | None
    model: str | None
    completions: int
    findings: int
    annotations: int
    yield_ratio: float
    severity: Dict[str, int]
    validation: Dict[str, int]
    per_tool: Dict[str, int]
    novelty_rows: int | None
    novelty_unique: int | None


def summarize_run(run_dir: Path, label: str | None = None) -> RunStats:
    data_dir = run_dir / "data"
    rep_dir = run_dir / "reports"
    manifest_path = data_dir / "run_manifest.json"
    comps_path = data_dir / "completions.jsonl"
    anns_path = data_dir / "annotations.jsonl"
    ens_path = rep_dir / "findings_ensemble.jsonl"
    nov_path = rep_dir / "novelty_report.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    provider = (manifest.get("generation") or {}).get("provider")
    model = (manifest.get("generation") or {}).get("model")
    run_id = manifest.get("run_id")
    auto_label = label or f"{provider or 'unknown'}|{model or 'unknown'}"

    comps = read_jsonl(comps_path)
    anns = read_jsonl(anns_path)
    ensemble = read_jsonl(ens_path)
    sev: Dict[str, int] = {}
    val: Dict[str, int] = {}
    per_tool: Dict[str, int] = {}
    for rec in anns:
        sev[rec.get("severity") or "unknown"] = sev.get(rec.get("severity") or "unknown", 0) + 1
        val[rec.get("validation_level") or "unknown"] = val.get(rec.get("validation_level") or "unknown", 0) + 1
        tool = (rec.get("detection_tools") or ["unknown"])[0] or "unknown"
        per_tool[tool] = per_tool.get(tool, 0) + 1

    novelty_rows = None
    novelty_unique = None
    if nov_path.exists():
        nov = json.loads(nov_path.read_text(encoding="utf-8"))
        novelty_rows = nov.get("rows")
        novelty_unique = nov.get("unique_patterns")

    comps_n = len(comps)
    ens_n = len(ensemble)
    yield_ratio = round((ens_n / comps_n) if comps_n else 0.0, 4)

    return RunStats(
        label=auto_label,
        path=run_dir,
        run_id=run_id,
        provider=provider,
        model=model,
        completions=comps_n,
        findings=ens_n,
        annotations=len(anns),
        yield_ratio=yield_ratio,
        severity=sev,
        validation=val,
        per_tool=per_tool,
        novelty_rows=novelty_rows,
        novelty_unique=novelty_unique,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", nargs="+", required=True, type=Path, help="Run directories (snapshot folders or repo roots).")
    p.add_argument("--labels", nargs="*", help="Optional labels matching --runs order.")
    p.add_argument("--out", type=Path, help="Optional output file path (md or json). If omitted, prints to stdout.")
    p.add_argument("--format", choices=("md", "json"), default="md")
    return p


def to_markdown(rows: List[RunStats]) -> str:
    # Build a compact markdown table comparing key metrics
    headers = [
        "label",
        "run_id",
        "provider",
        "model",
        "completions",
        "findings",
        "yield",
        "HIGH",
        "MED",
        "sandbox%",
        "tool_semgrep",
        "tool_ai",
        "unique",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        high = r.severity.get("HIGH", 0)
        med = r.severity.get("MEDIUM", 0)
        sand = r.validation.get("sandbox_validated", 0)
        sand_pct = 0.0
        if r.annotations:
            sand_pct = round(sand / r.annotations * 100, 1)
        line = [
            r.label,
            r.run_id or "",
            r.provider or "",
            (r.model or "").replace("|", "/"),
            str(r.completions),
            str(r.findings),
            f"{r.yield_ratio:.3f}",
            str(high),
            str(med),
            f"{sand_pct}",
            str(r.per_tool.get("semgrep", 0)),
            str(r.per_tool.get("ai-risk-detector", 0)),
            str(r.novelty_unique if r.novelty_unique is not None else ""),
        ]
        lines.append("| " + " | ".join(line) + " |")
    return "\n".join(lines)


def main() -> None:
    args = build_arg_parser().parse_args()
    labels: List[str | None] = []
    if args.labels:
        if len(args.labels) != len(args.runs):
            raise SystemExit("--labels must match --runs count, or omit --labels.")
        labels = list(args.labels)
    else:
        labels = [None] * len(args.runs)

    rows: List[RunStats] = []
    for run_dir, label in zip(args.runs, labels):
        rows.append(summarize_run(run_dir.resolve(), label))

    if args.format == "json":
        def stats_to_dict(r: RunStats) -> dict:
            return {
                "label": r.label,
                "path": str(r.path),
                "run_id": r.run_id,
                "provider": r.provider,
                "model": r.model,
                "completions": r.completions,
                "findings": r.findings,
                "annotations": r.annotations,
                "yield_ratio": r.yield_ratio,
                "severity": r.severity,
                "validation": r.validation,
                "per_tool": r.per_tool,
                "novelty_rows": r.novelty_rows,
                "novelty_unique": r.novelty_unique,
            }
        payload = [stats_to_dict(r) for r in rows]
        text = json.dumps(payload, indent=2)
    else:
        text = to_markdown(rows)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
