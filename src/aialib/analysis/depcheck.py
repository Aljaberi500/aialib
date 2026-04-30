"""Dependency hallucination checker for Python imports (offline + optional online).

Default behavior is offline-only: extract top-level imports and check against a
vendored registry snapshot. When ``--online`` is provided, also query the PyPI
API to verify existence and reduce false positives (e.g., ``yaml`` provided by
the ``PyYAML`` distribution).

Heuristics in online mode try common aliases (pep503-normalized name, ``py``
prefix, ``python-`` prefix, and suffix variants). Findings include both offline
and online evidence to aid triage.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import httpx
from typing import Dict, List, Set, Tuple

from ..utils.io import read_jsonl, utc_timestamp, hash_text


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", required=True, type=Path)
    parser.add_argument("--registry", dest="registry_path", required=True, type=Path)
    parser.add_argument("--out", dest="output_path", required=True, type=Path)
    parser.add_argument("--online", action="store_true", help="Enable online PyPI validation (network).")
    parser.add_argument("--timeout", dest="timeout", type=float, default=5.0, help="Online request timeout (seconds).")
    return parser


def load_registry(path: Path) -> Set[str]:
    if not path.exists():
        # Empty set: treat as unknown; checker will be no-op
        return set()
    data = json.loads(path.read_text(encoding="utf-8") or "[]")
    return set(data)


def levenshtein(a: str, b: str) -> int:
    # Simple iterative DP
    n, m = len(a), len(b)
    if n > m:
        a, b = b, a
        n, m = m, n
    prev = list(range(n + 1))
    for i, ch in enumerate(b, start=1):
        cur = [i] + [0] * n
        for j, ch2 in enumerate(a, start=1):
            cost = 0 if ch == ch2 else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def nearest_neighbor(name: str, registry: Set[str]) -> Tuple[str | None, int | None]:
    best: Tuple[str | None, int | None] = (None, None)
    for candidate in registry:
        d = levenshtein(name, candidate)
        if best[1] is None or (d < best[1]):
            best = (candidate, d)
    return best


_pep503_normalize = re.compile(r"[-_.]+")


def pep503_name(name: str) -> str:
    """Normalize a distribution name per PEP 503 conventions (lowercase, collapse separators)."""
    return _pep503_normalize.sub("-", name).lower()


def pypi_exists(pkg: str, timeout: float = 5.0) -> tuple[bool, dict]:
    """Check if a distribution exists on PyPI using the JSON API.

    Returns (exists, evidence).
    """
    headers = {"Connection": "close"}
    base = "https://pypi.org/pypi"
    url = f"{base}/{pkg}/json"
    try:
        with httpx.Client(timeout=timeout, headers=headers, http2=False, trust_env=False) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return True, {"endpoint": url, "status": resp.status_code}
            else:
                return False, {"endpoint": url, "status": resp.status_code}
    except Exception as exc:  # pragma: no cover - network dep
        return False, {"endpoint": url, "error": type(exc).__name__}


def pypi_candidates_for_module(modname: str) -> list[str]:
    """Generate candidate distribution names that might provide a top-level module.

    Heuristics only; helps bridge module name (e.g., ``yaml``) to distribution (``PyYAML``).
    """
    base = pep503_name(modname)
    cands = {
        base,
        f"py{base}",
        f"python-{base}",
        f"{base}-python",
    }
    # Expand collapsed separators: turn 'yaml' -> 'pyyaml' handled above; if name already has '-', test stripped variants
    cands.add(base.replace("-", ""))
    return list(cands)


def extract_imports(code: str) -> List[str]:
    names: Set[str] = set()
    try:
        tree = ast.parse(code)
    except Exception:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.name or "").split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return sorted(names)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    registry = load_registry(args.registry_path)
    completions = read_jsonl(args.input_path)
    findings: List[dict] = []

    # Build a unique set of imported names to avoid redundant network calls
    all_mods: Set[str] = set()
    per_rec_imports: Dict[str, List[str]] = {}
    for rec in completions:
        code = rec.get("code", "")
        mods = extract_imports(code)
        per_rec_imports[rec.get("completion_id") or "unknown"] = mods
        all_mods.update(mods)

    online_cache: Dict[str, dict] = {}
    # If online mode, pre-check candidates for each module
    if args.online and all_mods:
        for mod in sorted(all_mods):
            if mod in registry:
                continue  # already known-good offline
            exists_online = False
            online_ev: dict = {"candidates": [], "exists": False}
            for cand in pypi_candidates_for_module(mod):
                ok, ev = pypi_exists(cand, timeout=args.timeout)
                if ok:
                    exists_online = True
                    online_ev.update({"exists": True, "matched_distribution": cand, **ev})
                    break
                else:
                    online_ev.setdefault("attempts", []).append(ev)
            online_cache[mod] = online_ev

    for rec in completions:
        code = rec.get("code", "")
        for pkg in per_rec_imports.get(rec.get("completion_id") or "unknown", []):
            exists_offline = pkg in registry
            nn, dist = (None, None)
            if not exists_offline and registry:
                nn, dist = nearest_neighbor(pkg, registry)
            # Online override
            exists_online = False
            online_ev: dict | None = None
            if args.online and not exists_offline:
                online_ev = online_cache.get(pkg)
                exists_online = bool(online_ev and online_ev.get("exists"))

            # Skip finding if either offline registry or online check indicates existence
            if exists_offline or exists_online:
                continue

            evidence = {
                "package": pkg,
                "registry_check": {
                    "exists": exists_offline,
                    "nearest_neighbor": nn,
                    "distance": dist,
                },
            }
            if args.online:
                evidence["online_check"] = online_ev or {"exists": False}

            message = (
                f"Unknown package '{pkg}' not found in offline registry"
                + (" and PyPI" if args.online else "")
                + "."
            )
            finding_id = hash_text(
                f"depcheck|{rec.get('prompt_id')}|{rec.get('completion_id')}|{pkg}"
            )
            findings.append(
                {
                    "finding_id": finding_id,
                    "prompt_id": rec.get("prompt_id"),
                    "completion_id": rec.get("completion_id"),
                    "language": rec.get("language", "python"),
                    "generator": rec.get("generator"),
                    "model": rec.get("model"),
                    "prompt_text": rec.get("prompt_text"),
                    "tool": "depcheck",
                    "rule_id": "ai.dependency.hallucination",
                    "rule_name": "Hallucinated or unknown dependency",
                    "severity": "HIGH",
                    "confidence": "medium" if args.online else "low",
                    "message": message,
                    "file": f"inline:{rec.get('prompt_id')}",
                    "line": 1,
                    "code": code,
                    "ai_evidence": evidence,
                }
            )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(
        json.dumps({"tool": "depcheck", "generated_at": utc_timestamp(), "findings": findings}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
