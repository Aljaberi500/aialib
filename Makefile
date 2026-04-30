PYTHON ?= python3
export PYTHONPATH := src
PROMPTS_SPEC := data/prompts_v2.yaml
PROMPTS_EXPANDED := data/prompts_expanded.jsonl
PROMPTS_MANIFEST := data/run_manifest.json
COMPLETIONS := data/completions.jsonl
BANDIT_REPORT := reports/bandit.json
SEMGREP_REPORT := reports/semgrep.json
FINDINGS := reports/findings.jsonl
ANNOTATIONS := data/annotations.jsonl
CSV_OUT := out/threat_library.csv
SQLITE_OUT := out/threat_library.sqlite
AI_RISKS_REPORT := reports/ai_risks.json
COVERAGE_REPORT := reports/mapping_coverage.json
NOVELTY_REPORT := reports/novelty_report.json

.PHONY: setup expand expand-prompts generate scan annotate validate export export-sarif export-csv export-sqlite calibrate run ablate sarif manifest all clean test

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

expand:
	$(PYTHON) -m aialib.generation.expand --spec $(PROMPTS_SPEC) --out $(PROMPTS_EXPANDED) --manifest $(PROMPTS_MANIFEST) --stratify family --seed 1337

expand-prompts: expand

generate: expand
	$(PYTHON) -m aialib.generation.generate --prompts $(PROMPTS_EXPANDED) --out $(COMPLETIONS) --provider local --k 1 --temperature 0.8 --seed 1337

scan: generate
	$(PYTHON) -m aialib.analysis.run_bandit --in $(COMPLETIONS) --out $(BANDIT_REPORT) --config configs/bandit.yml
	$(PYTHON) -m aialib.analysis.run_semgrep --in $(COMPLETIONS) --config configs/semgrep.yml --out $(SEMGREP_REPORT)
	$(PYTHON) -m aialib.analysis.detect_ai_risks --in $(COMPLETIONS) --config configs/ai_risk_rules.yaml --out $(AI_RISKS_REPORT)
	$(PYTHON) -m aialib.analysis.merge_findings --bandit $(BANDIT_REPORT) --semgrep $(SEMGREP_REPORT) --extra $(AI_RISKS_REPORT) --out $(FINDINGS)

annotate: scan
	$(PYTHON) -m aialib.annotation.annotate --findings $(FINDINGS) --out $(ANNOTATIONS)

validate: annotate
	$(PYTHON) -m aialib.quality.validate --annotations $(ANNOTATIONS) --schema schemas/threat_entry.schema.json --rules configs/annotation_rules.yaml --atlas-catalog configs/atlas_catalog.yaml --coverage-report $(COVERAGE_REPORT) --novelty-report $(NOVELTY_REPORT)

calibrate: validate
	$(PYTHON) -m aialib.analysis.trust_calibration --annotations $(ANNOTATIONS) --out reports/trust_report.json

export: validate
	$(PYTHON) -m aialib.export.export_library --annotations $(ANNOTATIONS) --csv $(CSV_OUT) --sqlite $(SQLITE_OUT)

export-sarif:
	$(PYTHON) -m aialib.export.export_sarif --annotations $(ANNOTATIONS) --out out/threat_library.sarif

export-csv:
	$(PYTHON) -m aialib.export.export_library --annotations $(ANNOTATIONS) --csv $(CSV_OUT) --sqlite /dev/null

export-sqlite:
	$(PYTHON) -m aialib.export.export_library --annotations $(ANNOTATIONS) --csv /dev/null --sqlite $(SQLITE_OUT)

all: export

run:
	$(PYTHON) -m aialib.pipeline.run --provider local --detectors bandit semgrep ai --seed 1337 --k 1 --resume

ablate:
	# Provider-only ablation (local vs k2think; OpenAI optional)
	$(PYTHON) -m aialib.pipeline.run --provider local --detectors bandit semgrep ai --seed 1337 --k 1
	$(PYTHON) -m aialib.pipeline.run --provider k2think --detectors bandit semgrep ai --seed 1337 --k 1
	# Detector-only ablations
	$(PYTHON) -m aialib.pipeline.run --provider local --detectors bandit --seed 1337 --k 1
	$(PYTHON) -m aialib.pipeline.run --provider local --detectors semgrep --seed 1337 --k 1
	$(PYTHON) -m aialib.pipeline.run --provider local --detectors ai --seed 1337 --k 1

sarif:
	$(PYTHON) -m aialib.export.export_sarif --annotations $(ANNOTATIONS) --out out/threat_library.sarif

manifest:
	$(PYTHON) -m aialib.pipeline.manifest > /dev/null || true

test:
	python -m unittest -v

clean:
	rm -f $(COMPLETIONS) $(BANDIT_REPORT) $(SEMGREP_REPORT) $(AI_RISKS_REPORT) $(FINDINGS) $(ANNOTATIONS)
	rm -f $(CSV_OUT) $(SQLITE_OUT) $(PROMPTS_EXPANDED) $(PROMPTS_MANIFEST) $(COVERAGE_REPORT) $(NOVELTY_REPORT) reports/trust_report.json
