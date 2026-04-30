"""Apply human review decisions back into the annotations stream."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..annotation.annotate import REVIEW_STATUSES
from ..utils.io import read_jsonl, write_jsonl
from ..utils.io import utc_timestamp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/annotations_reviewed.jsonl"))
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    annotations = read_jsonl(args.annotations)
    queue = read_jsonl(args.reviews)
    if not queue:
        raise SystemExit("No reviews provided.")

    lookup = {record.get("vuln_id"): record for record in annotations}
    updates = 0
    for review in queue:
        vuln_id = review.get("vuln_id")
        status = review.get("review_status")
        if not vuln_id or status not in REVIEW_STATUSES or status == "unreviewed":
            continue
        target = lookup.get(vuln_id)
        if not target:
            continue
        target["review_status"] = status
        target["reviewer_id"] = review.get("reviewer_id")
        target["review_timestamp"] = review.get("review_timestamp") or utc_timestamp()
        target["review_notes"] = review.get("review_notes")
        updates += 1

    if not updates:
        raise SystemExit("No actionable reviews found in queue.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out, annotations)
    print(f"Applied {updates} reviews to annotation set.")


if __name__ == "__main__":
    main()
