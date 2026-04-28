"""plan_query tool: ranked tool sequence for a stated intent (B3).

Pure routing logic — no LLM call. Maps a natural-language intent into a
deterministic, ranked list of tool calls the agent should issue against
the dataset, given its schema.
"""

import time
from typing import Optional

from ..config import get_index_path
from ..storage.data_store import DataStore


_INTENT_KEYWORDS = {
    "summarize": frozenset(["summarize", "summary", "describe", "overview", "shape", "what is"]),
    "anomalies": frozenset(["anomaly", "anomalies", "outlier", "outliers", "weird", "suspicious", "issue", "issues"]),
    "compare": frozenset(["compare", "diff", "drift", "changed", "between"]),
    "join": frozenset(["join", "merge", "link", "combine", "relate"]),
    "filter": frozenset(["filter", "where", "find rows", "matching", "subset"]),
    "trend": frozenset(["trend", "over time", "by month", "by year", "timeseries", "time series"]),
    "correlate": frozenset(["correlate", "correlation", "relationship", "predicts"]),
}


def _classify_intent(intent: str) -> str:
    text = (intent or "").lower()
    best = "summarize"
    best_hits = 0
    for label, keywords in _INTENT_KEYWORDS.items():
        hits = sum(1 for k in keywords if k in text)
        if hits > best_hits:
            best = label
            best_hits = hits
    return best


def _plan_for(intent: str, idx) -> list:
    """Return a list of {tool, args, why} steps for the resolved intent."""
    dataset = idx.dataset
    has_datetime = any(c["type"] == "datetime" for c in idx.columns)
    has_numeric = any(c["type"] in ("integer", "float") for c in idx.columns)

    if intent == "summarize":
        return [
            {"tool": "describe_dataset", "args": {"dataset": dataset},
             "why": "Schema + per-column profile is the cheapest orientation."},
            {"tool": "get_dataset_health", "args": {"dataset": dataset},
             "why": "Single-number quality grade with breakdown."},
            {"tool": "sample_rows", "args": {"dataset": dataset, "n": 5},
             "why": "Confirm row shape matches schema expectations."},
        ]
    if intent == "anomalies":
        return [
            {"tool": "get_data_hotspots", "args": {"dataset": dataset, "top_n": 10},
             "why": "Ranks columns by null/cardinality/spread risk."},
            {"tool": "describe_column", "args": {"dataset": dataset, "column": "<top hotspot>"},
             "why": "Deep-dive on the highest-risk column."},
        ]
    if intent == "compare":
        return [
            {"tool": "get_schema_drift", "args": {"dataset_a": dataset, "dataset_b": "<other>"},
             "why": "Detect added/removed columns and type changes."},
            {"tool": "get_dataset_history", "args": {"dataset": dataset, "n": 10},
             "why": "Internal drift: how this dataset has changed across re-indexes."},
        ]
    if intent == "join":
        return [
            {"tool": "suggest_keys", "args": {"dataset": dataset},
             "why": "Identify primary-key candidates first."},
            {"tool": "suggest_joins", "args": {"dataset": dataset},
             "why": "Cross-dataset FK proposals via containment."},
            {"tool": "join_datasets", "args": {"dataset_a": dataset, "dataset_b": "<target>",
                                                "join_column_a": "<src>", "join_column_b": "<target_pk>"},
             "why": "Execute the join once a target PK is chosen."},
        ]
    if intent == "filter":
        return [
            {"tool": "search_data", "args": {"dataset": dataset, "query": intent},
             "why": "Find which columns and values match the intent text."},
            {"tool": "get_rows", "args": {"dataset": dataset, "filters": []},
             "why": "Return only the matching rows once filter columns are known."},
        ]
    if intent == "trend":
        if not has_datetime:
            return [{"tool": "describe_dataset", "args": {"dataset": dataset},
                     "why": "No datetime column found; trend requires one."}]
        return [
            {"tool": "get_distribution", "args": {"dataset": dataset, "column": "<datetime col>"},
             "why": "Histogram by time bucket."},
            {"tool": "aggregate", "args": {"dataset": dataset, "aggregations": [
                {"column": "*", "function": "count", "alias": "n"}],
                "group_by": ["<datetime col>"]},
             "why": "Per-period counts as a token-cheap timeseries."},
        ]
    if intent == "correlate":
        if not has_numeric:
            return [{"tool": "describe_dataset", "args": {"dataset": dataset},
                     "why": "No numeric columns; correlation not applicable."}]
        return [
            {"tool": "get_correlations", "args": {"dataset": dataset, "method": "pearson"},
             "why": "Pairwise Pearson r between numeric columns."},
            {"tool": "get_correlations", "args": {"dataset": dataset, "method": "spearman"},
             "why": "Spearman is robust to outliers and monotonic non-linearity."},
        ]
    return [{"tool": "describe_dataset", "args": {"dataset": dataset},
             "why": "Default orientation when intent is unclear."}]


def plan_query(
    dataset: str,
    intent: str = "summarize",
    storage_path: Optional[str] = None,
) -> dict:
    """Return a ranked tool-call sequence to satisfy `intent` for `dataset`."""
    t0 = time.perf_counter()
    store = DataStore(base_path=storage_path or str(get_index_path()))
    idx = store.load(dataset)
    if idx is None:
        return {"error": f"NOT_INDEXED: dataset {dataset!r} is not indexed."}

    classified = _classify_intent(intent)
    plan = _plan_for(classified, idx)

    return {
        "result": {
            "dataset": dataset,
            "intent": intent,
            "resolved_intent": classified,
            "step_count": len(plan),
            "plan": plan,
        },
        "_meta": {"timing_ms": round((time.perf_counter() - t0) * 1000, 1)},
    }
