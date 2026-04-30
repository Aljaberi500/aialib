"""Build and write a per-run manifest with provenance metadata."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

from .. import __version__ as PIPELINE_VERSION
from ..utils.io import hash_text, utc_timestamp


def _get_git_commit_sha(cwd: Optional[Path] = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(cwd or Path.cwd()),
        )
        return result.stdout.strip()
    except Exception:
        return None


def _tool_version(cmd: str) -> str | None:
    try:
        res = subprocess.run([cmd, "--version"], check=False, capture_output=True, text=True)
        out = res.stdout.strip() or res.stderr.strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


@dataclass
class RunManifest:
    pipeline_version: str
    created_at: str
    run_id: str
    seed: int
    git_commit: str | None
    prompt_spec_path: str
    prompt_spec_hash: str
    prompts_expanded_path: str | None
    prompts_expanded_hash: str | None
    semgrep_config_hash: str | None
    bandit_config_hash: str | None
    ai_risk_rules_hash: str | None
    annotation_rules_hash: str | None
    atlas_catalog_hash: str | None
    semgrep_version: str | None
    bandit_version: str | None
    language: str
    analyzers: list[str]
    providers: list[str]
    generation: dict
    prompt_counts_by_family: Dict[str, int]
    prompt_counts_by_cwe: Dict[str, int]


def _hash_file(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return hash_text(path.read_text(encoding="utf-8"))


def write_run_manifest(
    out_path: Path,
    *,
    seed: int,
    prompt_spec_path: Path,
    prompts_expanded_path: Path | None = None,
    prompt_counts_by_family: Dict[str, int] | None = None,
    prompt_counts_by_cwe: Dict[str, int] | None = None,
    language: str = "python",
    analyzers: list[str] | None = None,
    providers: list[str] | None = None,
    generation: dict | None = None,
) -> str:
    analyzers = analyzers or ["bandit", "semgrep", "ai-risk-detector"]
    providers = providers or ["local"]
    generation = generation or {}

    created_at = utc_timestamp()
    # Run id derived from seed + created_at + commit for uniqueness and reproducibility context
    base = f"{seed}|{created_at}|{_get_git_commit_sha() or 'nogit'}"
    run_id = hash_text(base, length=16)

    manifest = RunManifest(
        pipeline_version=PIPELINE_VERSION,
        created_at=created_at,
        run_id=run_id,
        seed=seed,
        git_commit=_get_git_commit_sha(),
        prompt_spec_path=str(prompt_spec_path),
        prompt_spec_hash=_hash_file(prompt_spec_path),
        prompts_expanded_path=str(prompts_expanded_path) if prompts_expanded_path else None,
        prompts_expanded_hash=_hash_file(prompts_expanded_path) if prompts_expanded_path else None,
        semgrep_config_hash=_hash_file(Path("configs/semgrep.yml")),
        bandit_config_hash=_hash_file(Path("configs/bandit.yml")),
        ai_risk_rules_hash=_hash_file(Path("configs/ai_risk_rules.yaml")),
        annotation_rules_hash=_hash_file(Path("configs/annotation_rules.yaml")),
        atlas_catalog_hash=_hash_file(Path("configs/atlas_catalog.yaml")),
        semgrep_version=_tool_version("semgrep"),
        bandit_version=_tool_version("bandit"),
        language=language,
        analyzers=analyzers,
        providers=providers,
        generation=generation,
        prompt_counts_by_family=prompt_counts_by_family or {},
        prompt_counts_by_cwe=prompt_counts_by_cwe or {},
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return run_id
