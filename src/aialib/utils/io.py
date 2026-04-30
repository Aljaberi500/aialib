"""Utility helpers for JSONL IO, hashing, and timestamps."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence


def read_jsonl(path: str | Path) -> List[dict]:
    """Return all records from a JSONL file. Empty list when file missing."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def stream_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield records from a JSONL file lazily."""
    for record in read_jsonl(path):
        yield record


def write_jsonl(path: str | Path, records: Iterable[dict]) -> None:
    """Write iterable records to a JSONL file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")


def append_jsonl(path: str | Path, records: Iterable[dict]) -> None:
    """Append iterable records to an existing JSONL file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return utc_now().isoformat()


def hash_text(text: str, length: int = 12) -> str:
    """Stable short hash for identifiers."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:length]


def ensure_directory(path: str | Path) -> Path:
    """Ensure the directory represented by `path` exists."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def chunked(sequence: Sequence, size: int) -> Iterator[Sequence]:
    """Yield fixed-size chunks from a sequence."""
    for idx in range(0, len(sequence), size):
        yield sequence[idx : idx + size]
