"""Expand templated prompt specifications into concrete prompts."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import yaml

from ..utils.io import hash_text, write_jsonl
from .mutators import apply_mutators


@dataclass
class TemplateSpec:
    template_id: str
    family: str
    cwe_targets: List[str]
    difficulties: List[str]
    template: str
    vars: Dict[str, List[str]]
    mutators: List[str]
    samples_per_difficulty: int


def render_template(template: str, context: Dict[str, str]) -> str:
    """Render a minimal moustache-like template."""
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def load_spec(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Prompt spec not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)
    if spec.get("version") != 2:
        raise ValueError("Prompt spec version must be 2.")
    return spec


def prepare_templates(entries: List[dict]) -> List[TemplateSpec]:
    specs = []
    for entry in entries:
        vars_mapping = entry.get("vars", {}).copy()
        # risk_nudges are user-friendly alias for "nudge" variable.
        if "risk_nudges" in entry and "nudge" not in vars_mapping:
            vars_mapping["nudge"] = entry["risk_nudges"]
        spec = TemplateSpec(
            template_id=entry["id"],
            family=entry["family"],
            cwe_targets=entry.get("cwe_targets", []),
            difficulties=entry.get("difficulty", ["unspecified"]),
            template=entry["template"],
            vars=vars_mapping,
            mutators=entry.get("adversarial_mutators", []),
            samples_per_difficulty=int(entry.get("samples_per_difficulty", 1)),
        )
        specs.append(spec)
    return specs


def iterate_instances(
    template: TemplateSpec, rng: random.Random
) -> Iterator[dict]:
    for difficulty in template.difficulties:
        for index in range(template.samples_per_difficulty):
            context = {}
            for key, values in template.vars.items():
                if not values:
                    continue
                context[key] = rng.choice(values)
            rendered = render_template(template.template, context)
            mutated_text, applied_mutators, mutator_details = apply_mutators(
                rendered, template.mutators, rng
            )
            prompt_id = f"{template.template_id}_{difficulty}_{index + 1:02d}"
            prompt_hash = hash_text(mutated_text + prompt_id)
            yield {
                "prompt_id": prompt_id,
                "prompt": mutated_text.strip() + "\n",
                "family": template.family,
                "difficulty": difficulty,
                "cwe_targets": template.cwe_targets,
                "template_id": template.template_id,
                "vars": context,
                "mutators": applied_mutators,
                "mutator_details": mutator_details,
                "prompt_hash": prompt_hash,
            }


def stratify(instances: List[dict], families_target: Dict[str, int]) -> List[dict]:
    grouped: Dict[str, List[dict]] = {}
    for instance in instances:
        grouped.setdefault(instance["family"], []).append(instance)
    selected: List[dict] = []
    for family, prompts in grouped.items():
        target = families_target.get(family, len(prompts))
        selected.extend(prompts[:target])
    return selected


def write_manifest(manifest_path: Optional[Path], spec: dict, prompts: List[dict]) -> None:
    if not manifest_path:
        return
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    counts_by_family: Dict[str, int] = {}
    counts_by_cwe: Dict[str, int] = {}
    for prompt in prompts:
        counts_by_family[prompt["family"]] = counts_by_family.get(prompt["family"], 0) + 1
        for cwe in prompt.get("cwe_targets", []):
            counts_by_cwe[cwe] = counts_by_cwe.get(cwe, 0) + 1
    spec_hash = hash_text(json.dumps(spec, sort_keys=True))
    manifest = {
        "spec_path": str(spec.get("__path__", "")),
        "spec_hash": spec_hash,
        "seed": spec.get("seed"),
        "counts": {
            "families": counts_by_family,
            "cwe": counts_by_cwe,
        },
        "total_prompts": len(prompts),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="YAML specification path.")
    parser.add_argument("--out", required=True, type=Path, help="Expanded prompts JSONL output.")
    parser.add_argument("--manifest", type=Path, help="Optional manifest output path.")
    parser.add_argument(
        "--stratify",
        choices=("family", "none"),
        default="family",
        help="Apply stratification when selecting prompts.",
    )
    parser.add_argument("--seed", type=int, help="Override seed from spec.")
    parser.add_argument(
        "--propagate",
        action="store_true",
        help="Generate propagation variants (reuse/refactor/secure_refactor) with lineage metadata.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    spec = load_spec(args.spec)
    spec["__path__"] = str(args.spec)
    seed = args.seed if args.seed is not None else spec.get("seed", 1337)
    rng = random.Random(seed)

    templates = prepare_templates(spec.get("templates", []))
    instances: List[dict] = []
    for template in templates:
        instances.extend(list(iterate_instances(template, rng)))

    if args.stratify == "family":
        families_target = spec.get("coverage", {}).get("families_target", {})
        instances = stratify(instances, families_target)

    # Optional propagation variants
    if args.propagate:
        propagated: List[dict] = []
        for base in instances:
            root = base["prompt_id"]
            for variant in ("reuse", "refactor", "secure_refactor"):
                derived = dict(base)
                derived["prompt_id"] = f"{root}-{variant}"
                derived["variant"] = variant
                derived["lineage_root"] = root
                derived["lineage_parent"] = root
                derived["prompt_hash"] = hash_text(derived["prompt"] + derived["prompt_id"])
                propagated.append(derived)
        instances.extend(propagated)

    # Deterministic ordering to keep reproducibility for JSONL writer.
    instances.sort(key=lambda item: item["prompt_id"])

    write_jsonl(args.out, instances)
    write_manifest(args.manifest, spec, instances)


if __name__ == "__main__":
    main()
