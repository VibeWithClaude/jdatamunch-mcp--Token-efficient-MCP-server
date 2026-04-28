"""HAVING clause on aggregate (B11)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.aggregate import aggregate


@pytest.fixture
def indexed(tmp_path):
    csv_path = tmp_path / "groups.csv"
    rows = (
        [("a", 1)] * 5
        + [("b", 1)] * 2
        + [("c", 1)] * 8
        + [("d", 1)] * 1
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["g", "n"])
        w.writerows(rows)
    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(csv_path), name="groups", storage_path=str(storage))
    return str(storage)


def test_having_filters_groups(indexed):
    res = aggregate(
        dataset="groups",
        aggregations=[{"column": "*", "function": "count", "alias": "n"}],
        group_by=["g"],
        having=[{"column": "n", "op": "gte", "value": 5}],
        storage_path=indexed,
    )
    groups = {g["g"]: g["n"] for g in res["result"]["groups"]}
    assert set(groups) == {"a", "c"}


def test_having_rejects_non_alias(indexed):
    res = aggregate(
        dataset="groups",
        aggregations=[{"column": "*", "function": "count", "alias": "n"}],
        group_by=["g"],
        having=[{"column": "g", "op": "eq", "value": "a"}],  # 'g' is a group key, not an alias
        storage_path=indexed,
    )
    assert "error" in res
    assert "INVALID_HAVING" in res["error"]


def test_having_in_operator(indexed):
    res = aggregate(
        dataset="groups",
        aggregations=[{"column": "*", "function": "count", "alias": "n"}],
        group_by=["g"],
        having=[{"column": "n", "op": "in", "value": [1, 8]}],
        storage_path=indexed,
    )
    groups = {g["g"]: g["n"] for g in res["result"]["groups"]}
    assert set(groups) == {"c", "d"}
