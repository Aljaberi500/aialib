"""CLI wrapper around Bandit to scan generated snippets."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--config", dest="config_path", type=Path, help="Bandit config.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    completions = read_jsonl(args.input_path)
    if not completions:
        print("No completions found; skipping Bandit run.", file=sys.stderr)
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(
            json.dumps({"tool": "bandit", "generated_at": utc_timestamp(), "findings": []}),
            encoding="utf-8",
        )
        return

    with tempfile.TemporaryDirectory(prefix="aialib_bandit_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        file_lookup: Dict[str, dict] = {}
        for item in completions:
            filename = f"{item['prompt_id']}__{item['completion_id']}.py"
            file_path = tmp_path / filename
            file_path.write_text(item.get("code", ""), encoding="utf-8")
            file_lookup[str(file_path)] = item

        cmd = ["bandit", "-f", "json", "-q", "-r", str(tmp_path)]
        if args.config_path:
            cmd.extend(["-c", str(args.config_path)])
        try:
            result = subprocess.run(
                cmd, check=False, capture_output=True, text=True, encoding="utf-8"
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Bandit command not found. Install Bandit or run `make setup`."
            ) from exc

        if result.returncode not in (0, 1):
            raise RuntimeError(f"Bandit failed: {result.stderr.strip()}")

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse Bandit output.") from exc

        findings: List[dict] = []
        for issue in payload.get("results", []):
            file_record = file_lookup.get(issue.get("filename", ""))
            if not file_record:
                continue
            finding_id = hash_text(
                f"bandit|{file_record['prompt_id']}|{file_record['completion_id']}|"
                f"{issue.get('test_id')}|{issue.get('line_number')}"
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
                    "tool": "bandit",
                    "rule_id": issue.get("test_id"),
                    "rule_name": issue.get("test_name"),
                    "severity": issue.get("issue_severity"),
                    "confidence": issue.get("issue_confidence"),
                    "message": issue.get("issue_text"),
                    "file": issue.get("filename"),
                    "line": issue.get("line_number"),
                    "code": file_record.get("code", ""),
                }
            )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps({"tool": "bandit", "generated_at": utc_timestamp(), "findings": findings}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
