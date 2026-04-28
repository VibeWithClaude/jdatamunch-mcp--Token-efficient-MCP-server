"""suggest_keys tool: surface PK candidates with confidence (B5).

Pure read of index.json — uses existing is_primary_key_candidate flag plus
heuristics to rank candidates and explain why.
"""

import time
from typing import Optional

from ..config import get_index_path
from ..storage.data_store import DataStore


def _confidence(col: dict) -> float:
    """Heuristic: integer/UUID columns + zero nulls + exact cardinality = strongest."""
    if not col.get("is_primary_key_candidate"):
        return 0.0
    score = 0.6
    if col.get("type") == "integer":
        score += 0.15
    if col.get("semantic_type") == "uuid":
        score += 0.2
    if col.get("null_pct") == 0.0:
        score += 0.1
    if col.get("cardinality_is_exact"):
        score += 0.05
    return min(score, 1.0)


def suggest_keys(
    dataset: str,
    storage_path: Optional[str] = None,
) -> dict:
    """Return ranked primary-key candidates for a dataset (B5)."""
    t0 = time.perf_counter()
    store = DataStore(base_path=storage_path or str(get_index_path()))
    idx = store.load(dataset)
    if idx is None:
        return {"error": f"NOT_INDEXED: dataset {dataset!r} is not indexed."}

    candidates = []
    for col in idx.columns:
        if col.get("is_primary_key_candidate"):
            conf = _confidence(col)
            reasons = []
            if col.get("type") == "integer":
                reasons.append("integer column")
            if col.get("semantic_type") == "uuid":
                reasons.append("UUID format")
            if col.get("null_pct") == 0.0:
                reasons.append("no nulls")
            if col.get("cardinality_is_exact"):
                reasons.append("exact-count unique")
            candidates.append({
                "column": col["name"],
                "type": col["type"],
                "semantic_type": col.get("semantic_type"),
                "confidence": round(conf, 3),
                "cardinality": col.get("cardinality"),
                "reasons": reasons,
            })

    candidates.sort(key=lambda c: c["confidence"], reverse=True)

    return {
        "result": {
            "dataset": dataset,
            "candidate_count": len(candidates),
            "candidates": candidates,
        },
        "_meta": {"timing_ms": round((time.perf_counter() - t0) * 1000, 1)},
    }
