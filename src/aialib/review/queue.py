"""Generate a stratified human-review queue."""

from __future__ import annotations

import argparse
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from ..utils.io import read_jsonl, write_jsonl


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/review_queue.jsonl"))
    parser.add_argument("--per-cwe", type=int, default=40, help="Targets 30-50 samples per CWE.")
    parser.add_argument("--top-cwe", type=int, default=3, help="Number of CWEs to prioritize.")
    parser.add_argument("--seed", type=int, default=1337)
    return parser


def stratified_sample(records: List[dict], target: int, rng: random.Random) -> List[dict]:
    buckets: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for record in records:
        severity = record.get("severity", "MEDIUM")
        tool = (record.get("detection_tools") or ["unknown"])[0] or "unknown"
        buckets[(severity, tool)].append(record)
    for bucket in buckets.values():
        bucket.sort(key=lambda item: item.get("vuln_id", ""))

    selected: List[dict] = []
    while len(selected) < target and buckets:
        for key in sorted(buckets):
            bucket = buckets[key]
            if not bucket:
                continue
            index = rng.randrange(len(bucket))
            selected.append(bucket.pop(index))
            if len(selected) >= target:
                break
        buckets = {k: v for k, v in buckets.items() if v}
    return selected


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    if not annotations:
        raise SystemExit("No annotations available for review sampling.")

    rng = random.Random(args.seed)
    cwe_counts = Counter(record.get("cwe_id") for record in annotations)
    top_cwes = [item for item, _ in cwe_counts.most_common(args.top_cwe)]

    queued: List[dict] = []
    for cwe_id in top_cwes:
        subset = [record for record in annotations if record.get("cwe_id") == cwe_id]
        queued.extend(stratified_sample(subset, min(args.per_cwe, len(subset)), rng))

    if not queued:
        raise SystemExit("Unable to assemble review queue; adjust parameters.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out, queued)
    print(f"Wrote {len(queued)} review candidates covering CWEs: {', '.join(top_cwes)}")


if __name__ == "__main__":
    main()
