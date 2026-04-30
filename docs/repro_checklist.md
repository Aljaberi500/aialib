Reproducibility Checklist
=========================

- Seed pinning
  - Use `--seed 1337` (default) across `expand` and `generate`.
- Deterministic prompt expansion
  - `data/prompts_v2.yaml` → `data/prompts_expanded.jsonl` is byte-identical for fixed seed.
- Provenance manifest
  - `data/run_manifest.json` includes: seed, pipeline version, git commit SHA, analyzer versions, Semgrep and Bandit config hashes, prompt spec hash, language, analyzers, providers, and prompt counts by family/CWE.
- Standardized generation params
  - Recorded per completion: provider, model, temperature, top_p, system prompt, seed.
- Caching & resume
  - `--resume` skips prompts already present in completions output for the same provider/model.
- Offline dependency registry
  - `data/registry/pypi_index.json` is versioned and used by the dependency checker.
- Validation & gating
  - `make validate` enforces schema/mapping; `aialib.quality.gate` supports CI thresholds.
