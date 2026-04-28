"""Aggregate result cache (B2).

Tools that perform deterministic aggregations on indexed data — `aggregate`,
`get_correlations`, `get_data_hotspots` — get a cheap key/value cache keyed
on (dataset, source_hash, tool, normalized_args).

Stored as JSON files under `~/.data-index/{dataset}/_cache/{key}.json`.
Invalidated when source_hash changes (re-index changes the hash).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


_CACHE_DIRNAME = "_cache"


def _normalize(obj: Any) -> Any:
    """Convert dict/list into a canonically-ordered JSON-safe structure."""
    if isinstance(obj, dict):
        return {k: _normalize(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return obj


def make_key(tool: str, source_hash: str, args: dict) -> str:
    payload = {
        "tool": tool,
        "source_hash": source_hash,
        "args": _normalize(args),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def cache_dir(dataset_dir: Path) -> Path:
    d = dataset_dir / _CACHE_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def get(dataset_dir: Path, key: str) -> Optional[dict]:
    path = cache_dir(dataset_dir) / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def put(dataset_dir: Path, key: str, value: dict) -> None:
    path = cache_dir(dataset_dir) / f"{key}.json"
    tmp = path.with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f)
        tmp.replace(path)
    except OSError:
        pass


def invalidate(dataset_dir: Path) -> None:
    """Drop all cached results for a dataset (called on re-index)."""
    d = dataset_dir / _CACHE_DIRNAME
    if not d.exists():
        return
    for f in d.glob("*.json"):
        try:
            f.unlink()
        except OSError:
            pass
