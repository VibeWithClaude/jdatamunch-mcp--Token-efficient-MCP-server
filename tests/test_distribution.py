"""get_distribution covers numeric / datetime / categorical (B8)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.get_distribution import get_distribution


@pytest.fixture
def indexed(tmp_path):
    csv_path = tmp_path / "mix.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "tag", "ts"])
        for i in range(100):
            tag = "x" if i % 3 == 0 else ("y" if i % 3 == 1 else "z")
            w.writerow([i, tag, f"2024-{(i % 12) + 1:02d}-15"])
    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(csv_path), name="mix", storage_path=str(storage))
    return str(storage)


def test_numeric_distribution(indexed):
    res = get_distribution(dataset="mix", column="score", bins=5, storage_path=indexed)
    assert res["result"]["kind"] == "numeric"
    bins = res["result"]["bins"]
    assert len(bins) == 5
    assert sum(b["count"] for b in bins) == 100


def test_categorical_distribution(indexed):
    res = get_distribution(dataset="mix", column="tag", bins=10, storage_path=indexed)
    assert res["result"]["kind"] == "categorical"
    values = {b["value"] for b in res["result"]["bins"]}
    assert {"x", "y", "z"}.issubset(values)


def test_datetime_distribution(indexed):
    res = get_distribution(dataset="mix", column="ts", bins=12, storage_path=indexed)
    assert res["result"]["kind"] == "datetime"
    assert all("bucket" in b for b in res["result"]["bins"])


def test_invalid_column(indexed):
    res = get_distribution(dataset="mix", column="nope", storage_path=indexed)
    assert "error" in res
