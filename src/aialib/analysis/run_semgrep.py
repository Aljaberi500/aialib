"""CLI wrapper around Semgrep to scan generated snippets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

from ..utils.io import hash_text, read_jsonl, utc_timestamp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", required=True, type=Path)
    parser.add_argument("--out", dest="output_path", required=True, type=Path)
    parser.add_argument("--config", dest="config_path", required=True, type=Path)
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    completions = read_jsonl(args.input_path)
    if not completions:
        print("No completions found; skipping Semgrep run.", file=sys.stderr)
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(
            json.dumps({"tool": "semgrep", "generated_at": utc_timestamp(), "findings": []}),
            encoding="utf-8",
        )
        return

    with tempfile.TemporaryDirectory(prefix="aialib_semgrep_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        file_lookup: Dict[str, dict] = {}
        for item in completions:
            filename = f"{item['prompt_id']}__{item['completion_id']}.py"
            file_path = tmp_path / filename
            file_path.write_text(item.get("code", ""), encoding="utf-8")
            file_lookup[str(file_path)] = item
            file_lookup[file_path.name] = item

        cmd = [
            "semgrep",
            "--config",
            str(args.config_path),
            "--json",
            "--quiet",
            "--no-rewrite-rule-ids",
            str(tmp_path),
        ]
        env = os.environ.copy()
        env["SEMGREP_USER_HOME"] = str(tmp_path)
        env["HOME"] = str(tmp_path)

        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Semgrep command not found. Install Semgrep or run `make setup`."
            ) from exc

        if result.returncode not in (0, 1):
            raise RuntimeError(f"Semgrep failed: {result.stderr.strip()}")

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse Semgrep output.") from exc

        findings: List[dict] = []
        for issue in payload.get("results", []):
            path = issue.get("path")
            file_record = file_lookup.get(path)
            if not file_record:
                normalized_path = str((tmp_path / path).resolve()) if path else ""
                file_record = file_lookup.get(normalized_path)
            if not file_record:
                continue
            start = issue.get("start", {})
            end = issue.get("end", {})
            finding_id = hash_text(
                f"semgrep|{file_record['prompt_id']}|{file_record['completion_id']}|"
                f"{issue.get('check_id')}|{start.get('line')}"
            )
            findings.append(
                {
                    "finding_id": finding_id,
                    "prompt_id": file_record["prompt_id"],
                    "completion_id": file_record["completion_id"],
                    "language": file_record.get("language", "python"),
                    "generator": file_record.get("generator"),
                    "model": file_record.get("model"),
                    "prompt_text": file_record.get("prompt_text"),
                    "tool": "semgrep",
                    "rule_id": issue.get("check_id"),
                    "rule_name": issue.get("extra", {}).get("metadata", {}).get("short_description")
                    or issue.get("check_id"),
                    "severity": issue.get("extra", {}).get("severity"),
                    "confidence": issue.get("extra", {}).get("confidence", "medium"),
                    "message": issue.get("extra", {}).get("message"),
                    "file": path,
                    "line": start.get("line"),
                    "end_line": end.get("line"),
                    "code": file_record.get("code", ""),
                }
            )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps({"tool": "semgrep", "generated_at": utc_timestamp(), "findings": findings}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
