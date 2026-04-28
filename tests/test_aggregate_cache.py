"""Aggregate result cache (B2)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.aggregate import aggregate


@pytest.fixture
def indexed(tmp_path):
    csv_path = tmp_path / "c.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["g", "v"])
        for i in range(100):
            w.writerow(["a" if i % 2 == 0 else "b", i])
    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(csv_path), name="c", storage_path=str(storage))
    return str(storage)


def test_second_call_is_cache_hit(indexed):
    args = {
        "dataset": "c",
        "aggregations": [{"column": "*", "function": "count", "alias": "n"}],
        "group_by": ["g"],
        "storage_path": indexed,
    }
    a = aggregate(**args)
    b = aggregate(**args)
    assert a["_meta"]["cache_hit"] is False
    assert b["_meta"]["cache_hit"] is True
    assert a["result"] == b["result"]


def test_different_args_miss(indexed):
    a = aggregate(
        dataset="c",
        aggregations=[{"column": "*", "function": "count", "alias": "n"}],
        group_by=["g"],
        storage_path=indexed,
    )
    b = aggregate(
        dataset="c",
        aggregations=[{"column": "v", "function": "sum", "alias": "s"}],
        group_by=["g"],
        storage_path=indexed,
    )
    assert a["_meta"]["cache_hit"] is False
    assert b["_meta"]["cache_hit"] is False


def test_reindex_invalidates_cache(tmp_path):
    csv_path = tmp_path / "drift.csv"
    storage = tmp_path / "data-index"
    storage.mkdir()

    def write(rows):
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["g"])
            for r in rows:
                w.writerow([r])

    write(["a"] * 5)
    index_local(path=str(csv_path), name="drift", storage_path=str(storage))
    a = aggregate(
        dataset="drift",
        aggregations=[{"column": "*", "function": "count", "alias": "n"}],
        storage_path=str(storage),
    )
    assert a["result"]["groups"][0]["n"] == 5

    write(["a"] * 8)
    index_local(path=str(csv_path), name="drift", storage_path=str(storage))
    b = aggregate(
        dataset="drift",
        aggregations=[{"column": "*", "function": "count", "alias": "n"}],
        storage_path=str(storage),
    )
    assert b["_meta"]["cache_hit"] is False
    assert b["result"]["groups"][0]["n"] == 8
