"""CLI for generating code snippets from prompts."""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List

import yaml

from ..utils.io import read_jsonl, utc_timestamp, write_jsonl, append_jsonl
from .provider import (
    GenerationParams,
    LocalGenerator,
    OpenAIProvider,
    K2ThinkProvider,
    Prompt,
)


def load_prompts(path: Path) -> List[Prompt]:
    """Load prompts from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    if path.suffix in {".jsonl", ".json"}:
        entries = read_jsonl(path)
    else:
        with path.open("r", encoding="utf-8") as handle:
            entries = yaml.safe_load(handle)
    prompts: List[Prompt] = []
    for entry in entries:
        prompt_id = entry.get("id") or entry.get("prompt_id")
        prompt_text = entry.get("prompt") or entry.get("prompt_text")
        if not prompt_id or not prompt_text:
            raise ValueError(f"Prompt entries must include 'id'/'prompt': {entry}")
        metadata = {k: v for k, v in entry.items() if k not in {"id", "prompt_id", "prompt", "prompt_text"}}
        prompts.append(Prompt(prompt_id=prompt_id, prompt_text=prompt_text, metadata=metadata))
    return prompts


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", required=True, type=Path, help="Path to prompts YAML.")
    parser.add_argument("--out", required=True, type=Path, help="Destination JSONL path.")
    parser.add_argument(
        "--provider",
        choices=("local", "openai", "openai_direct", "k2think", "anthropic"),
        default="local",
        help="Generation provider to use.",
    )
    parser.add_argument("--k", type=int, default=1, help="Number of completions per prompt.")
    parser.add_argument("--temperature", type=float, default=0.8, help="Sampling temperature.")
    parser.add_argument("--seed", type=int, default=1337, help="Deterministic seed.")
    parser.add_argument("--model", type=str, help="Optional model override for provider.")
    parser.add_argument("--top-p", type=float, default=1.0, help="Top-p sampling parameter.")
    parser.add_argument(
        "--system-prompt",
        type=str,
        default="You are generating code snippets for security testing.",
        help="System prompt for chat providers.",
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=Path("data/samples/local_generations.jsonl"),
        help="Path to canned completions for local provider.",
    )
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens per completion (provider permitting).")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume and skip prompts already present in --out for this provider/model.",
    )
    parser.add_argument(
        "--errors",
        type=Path,
        default=Path("reports/generation_errors.jsonl"),
        help="Where to append per-prompt errors for observability.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=30.0,
        help="Per-request timeout (seconds) for provider API calls.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    random.seed(args.seed)

    prompts = load_prompts(args.prompts)
    params = GenerationParams(
        k=args.k,
        temperature=args.temperature,
        top_p=args.top_p,
        seed=args.seed,
        model=args.model,
        system_prompt=args.system_prompt,
        max_tokens=args.max_tokens,
        request_timeout=args.request_timeout,
    )

    if args.provider == "local":
        generator = LocalGenerator(samples_path=args.samples)
        generator_name = "local"
    elif args.provider == "openai":
        generator = OpenAIProvider(model=args.model or "gpt-4o-mini")
        generator_name = "openai"
    elif args.provider == "openai_direct":
        from .provider import OpenAIDirectProvider

        generator = OpenAIDirectProvider(model=args.model or "gpt-4o-mini")
        generator_name = "openai"
    elif args.provider == "k2think":
        generator = K2ThinkProvider(model=args.model or "k2think-small")
        generator_name = "k2think"
    else:
        # Anthropic (Claude) direct HTTP client
        from .provider import AnthropicProvider

        generator = AnthropicProvider(model=args.model or "claude-3-5-sonnet-latest")
        generator_name = "anthropic"

    # Resume support: collect counts of existing completions per (prompt_id, provider, model).
    existing = {}
    if args.resume and args.out.exists():
        for rec in read_jsonl(args.out):
            key = (rec.get("prompt_id"), rec.get("generator"), rec.get("model"))
            existing[key] = existing.get(key, 0) + 1

    records = []
    for prompt in prompts:
        key = (prompt.prompt_id, generator_name, args.model or getattr(generator, "model", generator_name))
        already = existing.get(key, 0)
        needed = max(0, args.k - already) if args.resume else args.k
        if needed == 0:
            continue
        try:
            completions = generator.generate(prompt, params)
        except Exception as exc:  # pragma: no cover - observability
            # Append error record and continue.
            from ..utils.io import append_jsonl

            append_jsonl(
                args.errors,
                [
                    {
                        "prompt_id": prompt.prompt_id,
                        "provider": generator_name,
                        "model": args.model or getattr(generator, "model", generator_name),
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "created_at": utc_timestamp(),
                    }
                ],
            )
            continue
        # Deterministic selection for resume: use tail slice after 'already'
        for idx, completion in enumerate(completions[already : already + needed], start=already + 1):
            completion_id = f"{prompt.prompt_id}-{idx}"
            record = {
                "prompt_id": prompt.prompt_id,
                "prompt_text": prompt.prompt_text,
                "completion_id": completion_id,
                "code": completion.get("code", ""),
                "language": completion.get("language", "python"),
                "generator": generator_name,
                "model": completion.get("model") or args.model or generator_name,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "seed": args.seed,
                "max_tokens": args.max_tokens,
                "system_prompt": args.system_prompt,
                "created_at": utc_timestamp(),
            }
            metadata = completion.get("metadata")
            if metadata:
                record["metadata"] = metadata
            records.append(record)

    # Write outputs (append when resuming to preserve previous records)
    if args.resume and args.out.exists():
        append_jsonl(args.out, records)
    else:
        write_jsonl(args.out, records)


if __name__ == "__main__":
    main()
