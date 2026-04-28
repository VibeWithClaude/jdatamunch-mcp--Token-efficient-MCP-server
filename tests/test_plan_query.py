"""plan_query routing (B3)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.plan_query import plan_query


@pytest.fixture
def indexed(tmp_path):
    csv_path = tmp_path / "p.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a", "b"])
        for i in range(10):
            w.writerow([i, i * 2])
    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(csv_path), name="p", storage_path=str(storage))
    return str(storage)


def test_summarize_intent_returns_describe_dataset(indexed):
    res = plan_query(dataset="p", intent="summarize the data", storage_path=indexed)
    tools = [s["tool"] for s in res["result"]["plan"]]
    assert "describe_dataset" in tools


def test_anomaly_intent_returns_hotspots(indexed):
    res = plan_query(dataset="p", intent="find anomalies and outliers", storage_path=indexed)
    tools = [s["tool"] for s in res["result"]["plan"]]
    assert "get_data_hotspots" in tools


def test_correlate_intent(indexed):
    res = plan_query(dataset="p", intent="show me correlations", storage_path=indexed)
    tools = [s["tool"] for s in res["result"]["plan"]]
    assert "get_correlations" in tools


def test_unknown_dataset(tmp_path):
    storage = tmp_path / "data-index"
    storage.mkdir()
    res = plan_query(dataset="nope", intent="summarize", storage_path=str(storage))
    assert "error" in res
