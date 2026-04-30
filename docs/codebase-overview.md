# AI‑Aware Threat Library Prototype — Codebase Overview

This repository automates building an "AI‑aware" threat library from generated code snippets. It expands templated prompts, generates code (offline by default), scans with static analyzers, merges/normalizes results, annotates with AI‑specific metadata, validates quality gates, and exports a curated dataset (CSV/SQLite).

## Purpose
- Produce a reproducible corpus of security‑relevant, AI‑generated code behaviors.
- Enrich findings with CWE/OWASP, MITRE ATLAS techniques, and AI‑specific causal factors.
- Run fully offline by default; optionally use OpenAI if configured.

## Directory Layout
- `src/aialib/` — pipeline modules
  - `generation/` — prompt expansion and snippet generation
  - `analysis/` — Bandit/Semgrep wrappers, AI‑risk detector, merging, fingerprints, trust calibration
  - `annotation/` — rule‑based enrichment to threat‑library schema
  - `quality/` — schema + coverage + novelty validation
  - `export/` — CSV/SQLite exporters
  - `pipeline/` — one‑off end‑to‑end snippet processor
  - `review/` — human‑in‑the‑loop queue + apply tools
- `configs/` — analyzer configs, annotation rulebook, ATLAS catalog, AI risk rules
- `schemas/` — JSON Schema for threat‑library entries
- `data/` — prompts, expanded prompts, completions, annotations, manifests
- `reports/` — raw analyzer outputs and validation reports
- `out/` — exported threat library (CSV/SQLite)
- `Makefile` — orchestrates the full run
- `README.md` — quickstart and pipeline overview

## Pipeline Data Flow
1. Expand prompts
   - `python -m aialib.generation.expand --spec data/prompts_v2.yaml --out data/prompts_expanded.jsonl --manifest data/run_manifest.json`
2. Generate snippets (offline by default)
   - `python -m aialib.generation.generate --prompts data/prompts_expanded.jsonl --out data/completions.jsonl --provider local`
3. Scan with static analyzers + AI risk detector
   - `python -m aialib.analysis.run_bandit --in data/completions.jsonl --out reports/bandit.json --config configs/bandit.yml`
   - `python -m aialib.analysis.run_semgrep --in data/completions.jsonl --out reports/semgrep.json --config configs/semgrep.yml`
   - `python -m aialib.analysis.detect_ai_risks --in data/completions.jsonl --out reports/ai_risks.json --config configs/ai_risk_rules.yaml`
4. Merge and normalize findings
   - `python -m aialib.analysis.merge_findings --bandit reports/bandit.json --semgrep reports/semgrep.json --extra reports/ai_risks.json --out reports/findings.jsonl`
5. Annotate with CWE/OWASP/ATLAS + AI metadata
   - `python -m aialib.annotation.annotate --findings reports/findings.jsonl --out data/annotations.jsonl --rules configs/annotation_rules.yaml`
6. Validate quality gates (schema, mapping coverage, novelty, duplicates)
   - `python -m aialib.quality.validate --annotations data/annotations.jsonl --schema schemas/threat_entry.schema.json --rules configs/annotation_rules.yaml --atlas-catalog configs/atlas_catalog.yaml --coverage-report reports/mapping_coverage.json --novelty-report reports/novelty_report.json`
7. Export curated library
   - `python -m aialib.export.export_library --annotations data/annotations.jsonl --csv out/threat_library.csv --sqlite out/threat_library.sqlite`

Shortcut: `make all` runs the full sequence. Outputs land in `data/`, `reports/`, and `out/`.

## Key Modules
- Generation (`src/aialib/generation/`)
  - `expand.py` — expands `data/prompts_v2.yaml` into `data/prompts_expanded.jsonl`. Supports adversarial mutators (`mutators.py`) and family stratification.
  - `generate.py` — turns prompts into code snippets via providers. `provider.py` implements:
    - `LocalGenerator` (offline, uses `data/samples/local_generations.jsonl` with deterministic fallbacks)
    - `OpenAIProvider` (optional; requires `OPENAI_API_KEY`)
- Analysis (`src/aialib/analysis/`)
  - `run_bandit.py` / `run_semgrep.py` — sandbox the generated snippets into temp dirs and run tools using repo configs.
  - `detect_ai_risks.py` — heuristic AI‑risk detector based on `configs/ai_risk_rules.yaml` (e.g., dependency hallucinations, unsafe defaults, prompt/code misalignment, multi‑file bypass).
  - `merge_findings.py` — normalizes tool outputs and adds code fingerprints from `code_fingerprints.py` (token + AST hashes).
  - `trust_calibration.py` — aggregates human review precision and disagreement metrics.
- Annotation (`src/aialib/annotation/annotate.py`)
  - Loads `configs/annotation_rules.yaml`, normalizes severities, tags AI causes/propagation/human factors, and emits enriched records.
- Quality (`src/aialib/quality/validate.py`)
  - Validates against `schemas/threat_entry.schema.json`, enforces rule coverage and allowed severities, checks duplicates, writes coverage and novelty reports.
- Export (`src/aialib/export/export_library.py`)
  - Writes CSV and SQLite. Array fields are serialized into `[]`‑suffixed CSV columns for compatibility.
- One‑off pipeline (`src/aialib/pipeline/process_snippet.py`)
  - Runs a single file end‑to‑end (scan → annotate → validate → export) into `out/manual_run/`.
- Human review (`src/aialib/review/`)
  - `queue.py` builds a stratified review queue; `apply.py` merges reviewer decisions back into annotations.

## Configuration
- `data/prompts_v2.yaml` — prompt families, difficulties, variables, adversarial mutators, and coverage targets.
- `configs/semgrep.yml` and `configs/bandit.yml` — curated rulepacks and settings for analyzers.
- `configs/ai_risk_rules.yaml` — AI‑risk heuristics.
- `configs/annotation_rules.yaml` — rulebook mapping tool rule IDs to CWE/OWASP/ATLAS and AI‑aware metadata.
- `configs/atlas_catalog.yaml` — allowed ATLAS techniques for validation.

## Schema & Reports
- Schema: `schemas/threat_entry.schema.json` (required fields include `ai_cause`, `propagation_vector`, `atlas_techniques`, fingerprints, and review status).
- Reports: `reports/mapping_coverage.json` (mapping coverage by tool/rule/family), `reports/novelty_report.json` (unique‑pattern clustering), `reports/trust_report.json` (precision/disagreement from reviews).

## Development Notes
- Python 3.11, `pyproject.toml` and `requirements.txt` manage dependencies.
- Deterministic: seeded RNG and short content hashes from `src/aialib/utils/io.py`.
- Offline‑first: local generator and vendored analyzer configs require no network access; OpenAI is optional.

## Extension Points
- Add prompt families in `data/prompts_v2.yaml` and extend `LocalGenerator` samples.
- Add analyzer rules in `configs/semgrep.yml`/`configs/bandit.yml` or integrate new tools under `src/aialib/analysis/` and map rule IDs in `configs/annotation_rules.yaml`.
- Expand schema or exporters in `schemas/` and `src/aialib/export/` after updating validators.

## Quick Commands
- Setup: `python3.11 -m venv .venv && source .venv/bin/activate && make setup`
- Full run: `make all`
- One‑off snippet: `python -m aialib.pipeline.process_snippet --code path/to/file.py --prompt-text "context"`
- Use OpenAI: `make generate PROVIDER=openai` with `OPENAI_API_KEY` set.

