# Contributing to aialib

Thanks for your interest in extending the AI-Aware Threat Library.

## Ways to contribute

- **New prompt families.** Add an entry to `data/prompts_v2.yaml` describing
  the security weakness, difficulty levels, template variables, and
  adversarial mutators. Re-run `make expand` to materialize the new prompts.
- **New providers.** Implement a `Provider` subclass under
  `src/aialib/generation/provider.py` and register it in `generate.py`.
  Providers must log every generation parameter (`model`, `temperature`,
  `top_p`, `max_tokens`, `seed`, `system_prompt`) so runs remain comparable.
- **New detectors.** Drop a wrapper under `src/aialib/analysis/`, return
  records in the merge-friendly JSONL shape (`rule_id`, `cwe`, `severity`,
  `evidence`, `tool`), and add the rule mappings under
  `configs/annotation_rules.yaml`.
- **New ATLAS / CWE mappings.** Add the rationale notes in
  `docs/mappings/` and update the catalog under
  `configs/atlas_catalog.yaml`.

## Local checks before opening a PR

```bash
make setup
make run            # full pipeline against the offline corpus
make validate       # quality gates (schema, ATLAS catalog, novelty)
python -m unittest -v
```

A pull request must keep `tests/test_expand_deterministic.py` green so that
the prompt expansion stays byte-identical for the documented seed.

## Coding conventions

- Python 3.11+, type hints on public functions.
- Avoid extra runtime dependencies — the pipeline aims to remain installable
  with the six packages in `requirements.txt`.
- Keep module entry points runnable as `python -m aialib.<module>` so they
  compose into the Makefile.

## Reporting findings

If you discover a regression in the threat library (a finding that disappears
or changes vuln_id between two clean runs from the same seed), please open an
issue with the run manifest (`data/run_manifest.json`) and the diffing
fingerprints. That kind of report is the most useful one we receive.

## Code of conduct

Be kind. Assume good faith. Treat the threat library as research data —
don't use it to attack systems you don't own or operate.
