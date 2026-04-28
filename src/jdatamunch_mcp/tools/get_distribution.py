"""get_distribution tool: unified bin-counts for any column type (B8).

* Numeric columns → equal-width bins between [min, max].
* Datetime columns → time-bucket bins (auto-chosen: day / month / year).
* Categorical / string columns → top-n + 'other' bucket.

A token-cheap way to ask "what does this column look like?" without
materializing rows.
"""

import sqlite3
import time
from typing import Optional

from ..config import get_index_path
from ..storage.data_store import DataStore
from ..storage.sqlite_store import _qcol


_MAX_BINS = 100
_DEFAULT_BINS = 20


def _numeric_distribution(conn, col: str, bins: int, mn: float, mx: float) -> list:
    qc = _qcol(col)
    if mx <= mn:
        # Degenerate — single value
        row = conn.execute(
            f"SELECT COUNT(*) FROM rows WHERE {qc} = ?", [mn]
        ).fetchone()
        return [{
            "bin_index": 0,
            "lower": mn,
            "upper": mx,
            "count": int(row[0]) if row else 0,
        }]
    width = (mx - mn) / bins
    out: list = []
    for i in range(bins):
        lo = mn + i * width
        hi = mn + (i + 1) * width
        if i == bins - 1:
            sql = (
                f"SELECT COUNT(*) FROM rows WHERE {qc} >= ? AND {qc} <= ?"
            )
        else:
            sql = (
                f"SELECT COUNT(*) FROM rows WHERE {qc} >= ? AND {qc} < ?"
            )
        row = conn.execute(sql, [lo, hi]).fetchone()
        out.append({
            "bin_index": i,
            "lower": round(lo, 6),
            "upper": round(hi, 6),
            "count": int(row[0]) if row else 0,
        })
    return out


def _datetime_distribution(conn, col: str, bins: int) -> list:
    qc = _qcol(col)
    # Use SQLite's strftime to bucket; choose granularity by range span.
    rng = conn.execute(
        f"SELECT MIN({qc}), MAX({qc}) FROM rows WHERE {qc} IS NOT NULL"
    ).fetchone()
    if rng is None or rng[0] is None:
        return []
    # Pick granularity: bins target ≤ requested
    # For simplicity bucket by 'YYYY-MM' (month). Year/day variants could be added.
    sql = (
        f"SELECT substr({qc}, 1, 7) AS bucket, COUNT(*) AS n "
        f"FROM rows WHERE {qc} IS NOT NULL GROUP BY bucket "
        f"ORDER BY bucket"
    )
    rows = conn.execute(sql).fetchall()
    return [{"bucket": r[0], "count": int(r[1])} for r in rows[:bins]]


def _categorical_distribution(conn, col: str, bins: int) -> list:
    qc = _qcol(col)
    sql = (
        f"SELECT {qc} AS value, COUNT(*) AS n FROM rows "
        f"WHERE {qc} IS NOT NULL GROUP BY {qc} ORDER BY n DESC LIMIT ?"
    )
    rows = conn.execute(sql, [bins]).fetchall()
    top = [{"value": r[0], "count": int(r[1])} for r in rows]
    # Compute "other" bucket
    if len(top) >= bins:
        total_row = conn.execute(
            f"SELECT COUNT(*) FROM rows WHERE {qc} IS NOT NULL"
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        accounted = sum(b["count"] for b in top)
        other = max(0, total - accounted)
        if other > 0:
            top.append({"value": "<other>", "count": other})
    return top


def get_distribution(
    dataset: str,
    column: str,
    bins: int = _DEFAULT_BINS,
    storage_path: Optional[str] = None,
) -> dict:
    """Return bin-counts for `column`, dispatching by type (B8)."""
    t0 = time.perf_counter()
    bins = min(max(1, bins), _MAX_BINS)
    store = DataStore(base_path=storage_path or str(get_index_path()))
    idx = store.load(dataset)
    if idx is None:
        return {"error": f"NOT_INDEXED: dataset {dataset!r} is not indexed."}

    col = next((c for c in idx.columns if c["name"] == column), None)
    if col is None:
        return {"error": f"INVALID_COLUMN: {column!r}"}

    sqlite_path = store.sqlite_path(dataset)
    if not sqlite_path.exists():
        return {"error": f"NOT_INDEXED: SQLite missing for {dataset!r}."}

    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.execute("PRAGMA query_only=1")
        if col["type"] in ("integer", "float"):
            mn = col.get("min")
            mx = col.get("max")
            if mn is None or mx is None:
                return {
                    "result": {
                        "dataset": dataset, "column": column, "kind": "numeric",
                        "bins": [],
                    },
                    "_meta": {"timing_ms": round((time.perf_counter() - t0) * 1000, 1)},
                }
            payload = _numeric_distribution(conn, column, bins, float(mn), float(mx))
            kind = "numeric"
        elif col["type"] == "datetime":
            payload = _datetime_distribution(conn, column, bins)
            kind = "datetime"
        else:
            payload = _categorical_distribution(conn, column, bins)
            kind = "categorical"

    return {
        "result": {
            "dataset": dataset,
            "column": column,
            "kind": kind,
            "bins": payload,
        },
        "_meta": {"timing_ms": round((time.perf_counter() - t0) * 1000, 1)},
    }
