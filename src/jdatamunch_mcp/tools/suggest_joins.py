"""suggest_joins tool: discover FK candidates across indexed datasets (B5).

For each non-PK column in `dataset`, scan the PK candidates of other indexed
datasets and report any whose values cover ≥ 95% of the source column's
distinct values. Sample-based to keep the cost bounded across many datasets.
"""

import sqlite3
import time
from typing import Optional

from ..config import get_index_path
from ..storage.data_store import DataStore
from ..storage.sqlite_store import _qcol


_MAX_DATASETS_SCANNED = 20
_SAMPLE_SIZE = 500
_CONTAINMENT_THRESHOLD = 0.95


def _sample_distinct_values(sql_path, col_name: str, n: int) -> set:
    """Return up to n distinct non-null values from col_name as strings."""
    qc = _qcol(col_name)
    out: set = set()
    try:
        with sqlite3.connect(str(sql_path)) as conn:
            conn.execute("PRAGMA query_only=1")
            sql = (
                f"SELECT DISTINCT {qc} FROM rows "
                f"WHERE {qc} IS NOT NULL LIMIT ?"
            )
            for row in conn.execute(sql, [n]):
                if row[0] is not None:
                    out.add(str(row[0]))
    except sqlite3.DatabaseError:
        pass
    return out


def _column_contains_all(sql_path, col_name: str, values: set) -> int:
    """Return count of values from `values` present in (col_name) of sql_path."""
    if not values:
        return 0
    qc = _qcol(col_name)
    try:
        with sqlite3.connect(str(sql_path)) as conn:
            conn.execute("PRAGMA query_only=1")
            ph = ",".join("?" * len(values))
            sql = (
                f"SELECT COUNT(DISTINCT {qc}) FROM rows "
                f"WHERE {qc} IN ({ph})"
            )
            row = conn.execute(sql, list(values)).fetchone()
            return int(row[0]) if row else 0
    except sqlite3.DatabaseError:
        return 0


def suggest_joins(
    dataset: str,
    storage_path: Optional[str] = None,
) -> dict:
    """Discover FK candidates between `dataset` and other indexed datasets."""
    t0 = time.perf_counter()
    store = DataStore(base_path=storage_path or str(get_index_path()))
    src_idx = store.load(dataset)
    if src_idx is None:
        return {"error": f"NOT_INDEXED: dataset {dataset!r} is not indexed."}

    # Collect PK candidates across other datasets
    other_datasets = []
    for entry in store.list_datasets()[:_MAX_DATASETS_SCANNED]:
        if entry["dataset"] == dataset:
            continue
        other_idx = store.load(entry["dataset"])
        if other_idx is None:
            continue
        pks = [c for c in other_idx.columns if c.get("is_primary_key_candidate")]
        if pks:
            other_datasets.append((other_idx, pks))

    src_sql = store.sqlite_path(dataset)
    proposals: list = []

    for src_col in src_idx.columns:
        # Skip PK candidates — they're the *source* of joins, not the target
        if src_col.get("is_primary_key_candidate"):
            continue
        # Only consider integer / string columns; floats rarely participate in joins
        if src_col["type"] not in ("integer", "string"):
            continue
        # Skip columns that are mostly null
        if (src_col.get("null_pct") or 0.0) > 50.0:
            continue
        sample = _sample_distinct_values(src_sql, src_col["name"], _SAMPLE_SIZE)
        if len(sample) < 5:
            continue

        for other_idx, pks in other_datasets:
            other_sql = store.sqlite_path(other_idx.dataset)
            for pk in pks:
                # Skip type mismatch (int can join string-of-digits in SQLite, but
                # we keep this conservative)
                if pk["type"] != src_col["type"]:
                    continue
                hits = _column_contains_all(other_sql, pk["name"], sample)
                containment = hits / len(sample)
                if containment >= _CONTAINMENT_THRESHOLD:
                    proposals.append({
                        "source_column": src_col["name"],
                        "target_dataset": other_idx.dataset,
                        "target_column": pk["name"],
                        "containment": round(containment, 3),
                        "sample_size": len(sample),
                    })

    proposals.sort(key=lambda p: p["containment"], reverse=True)

    return {
        "result": {
            "dataset": dataset,
            "datasets_scanned": len(other_datasets),
            "proposal_count": len(proposals),
            "proposals": proposals,
        },
        "_meta": {"timing_ms": round((time.perf_counter() - t0) * 1000, 1)},
    }
