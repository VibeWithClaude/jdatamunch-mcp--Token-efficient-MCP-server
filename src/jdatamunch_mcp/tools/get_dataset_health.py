"""get_dataset_health tool: composite quality score with A–F grade (B4).

Combines existing profile signals — null severity, type-confidence, constant
columns, PK presence — into a single number plus a structured breakdown.

Pure read of index.json; no SQLite query needed.
"""

import time
from typing import Optional

from ..config import get_index_path
from ..storage.data_store import DataStore


# Component weights (sum to 1.0). Tuned so a clean, well-typed dataset with
# at least one PK-candidate column scores ≥ 0.85.
_W_NULL = 0.30
_W_TYPE_CONF = 0.30
_W_CONSTANT = 0.10
_W_PK = 0.10
_W_SEMANTIC = 0.10
_W_DRIFT_FREE = 0.10


def _grade(score: float) -> str:
    if score >= 0.90:
        return "A"
    if score >= 0.80:
        return "B"
    if score >= 0.70:
        return "C"
    if score >= 0.60:
        return "D"
    return "F"


def get_dataset_health(
    dataset: str,
    storage_path: Optional[str] = None,
) -> dict:
    """Return a composite health score for a dataset (B4)."""
    t0 = time.perf_counter()
    store = DataStore(base_path=storage_path or str(get_index_path()))
    idx = store.load(dataset)
    if idx is None:
        return {"error": f"NOT_INDEXED: dataset {dataset!r} is not indexed."}

    cols = idx.columns
    n = len(cols) or 1

    # 1. Null severity — weighted average of (1 - null_pct/100)
    null_avg = sum((100.0 - (c.get("null_pct") or 0.0)) for c in cols) / n / 100.0

    # 2. Type confidence — average across columns (default 1.0 for legacy)
    type_conf_avg = sum(c.get("type_confidence", 1.0) for c in cols) / n

    # 3. Constant columns — penalize if more than ~5% of columns are constant
    constant_cols = [c for c in cols if (c.get("cardinality") or 0) == 1]
    constant_penalty = min(len(constant_cols) / n, 1.0)
    constant_score = 1.0 - constant_penalty

    # 4. PK presence — credit when at least one PK candidate exists
    pk_cols = [c for c in cols if c.get("is_primary_key_candidate")]
    pk_score = 1.0 if pk_cols else 0.5

    # 5. Semantic typing rate — credit semantic_type detected on string/numeric cols
    typed = [c for c in cols if c.get("semantic_type")]
    candidate_count = sum(1 for c in cols if c.get("type") in ("string", "integer", "float"))
    semantic_score = (
        len(typed) / candidate_count if candidate_count else 1.0
    )

    # 6. Drift-free — count history snapshots; "no schema-changing drift" is rewarded
    snapshots = store.read_history(dataset, n=10)
    drift_score = 1.0
    if len(snapshots) >= 2:
        first = snapshots[0]
        last = snapshots[-1]
        first_cols = {c["name"] for c in first.get("schema_digest", [])}
        last_cols = {c["name"] for c in last.get("schema_digest", [])}
        if first_cols and first_cols != last_cols:
            drift_score = 0.5

    score = (
        _W_NULL * null_avg
        + _W_TYPE_CONF * type_conf_avg
        + _W_CONSTANT * constant_score
        + _W_PK * pk_score
        + _W_SEMANTIC * semantic_score
        + _W_DRIFT_FREE * drift_score
    )

    grade = _grade(score)

    high_null = [c["name"] for c in cols if (c.get("null_pct") or 0.0) >= 50.0]
    low_conf = [c["name"] for c in cols if c.get("type_confidence", 1.0) < 0.9]

    return {
        "result": {
            "dataset": dataset,
            "grade": grade,
            "score": round(score, 3),
            "row_count": idx.row_count,
            "column_count": idx.column_count,
            "components": {
                "null_avg": round(null_avg, 3),
                "type_confidence_avg": round(type_conf_avg, 3),
                "constant_columns": round(constant_score, 3),
                "primary_key": round(pk_score, 3),
                "semantic_typing": round(semantic_score, 3),
                "drift_free": round(drift_score, 3),
            },
            "issues": {
                "high_null_columns": high_null[:20],
                "low_type_confidence_columns": low_conf[:20],
                "constant_columns": [c["name"] for c in constant_cols[:20]],
                "primary_key_candidates": [c["name"] for c in pk_cols[:5]],
            },
        },
        "_meta": {"timing_ms": round((time.perf_counter() - t0) * 1000, 1)},
    }
