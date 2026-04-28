"""run_sql sandboxed SQL escape hatch (B1)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.run_sql import run_sql


@pytest.fixture
def storage(tmp_path):
    a = tmp_path / "a.csv"
    with open(a, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "n"])
        for i in range(20):
            w.writerow([i, i * 3])
    b = tmp_path / "b.csv"
    with open(b, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "label"])
        for i in range(20):
            w.writerow([i, f"x{i % 3}"])
    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(a), name="a", storage_path=str(storage))
    index_local(path=str(b), name="b", storage_path=str(storage))
    return str(storage)


def test_basic_select(storage):
    res = run_sql(sql="SELECT COUNT(*) AS n FROM rows", datasets=["a"], storage_path=storage)
    assert res["result"]["rows"][0]["n"] == 20


def test_attached_dataset(storage):
    res = run_sql(
        sql="SELECT COUNT(*) AS n FROM rows JOIN b.rows USING (id)",
        datasets=["a", "b"],
        storage_path=storage,
    )
    assert res["result"]["rows"][0]["n"] == 20


def test_with_cte(storage):
    res = run_sql(
        sql="WITH t AS (SELECT n FROM rows WHERE n > 30) SELECT COUNT(*) AS c FROM t",
        datasets=["a"],
        storage_path=storage,
    )
    assert res["result"]["rows"][0]["c"] > 0


def test_rejects_non_select(storage):
    res = run_sql(sql="DELETE FROM rows", datasets=["a"], storage_path=storage)
    assert "error" in res


def test_rejects_multiple_statements(storage):
    res = run_sql(
        sql="SELECT 1; SELECT 2",
        datasets=["a"],
        storage_path=storage,
    )
    assert "error" in res


def test_rejects_pragma(storage):
    res = run_sql(sql="SELECT * FROM rows; PRAGMA integrity_check", datasets=["a"], storage_path=storage)
    assert "error" in res


def test_row_cap(storage):
    res = run_sql(
        sql="SELECT * FROM rows", datasets=["a"], limit=5, storage_path=storage
    )
    assert res["result"]["returned"] == 5


def test_unknown_dataset(storage):
    res = run_sql(sql="SELECT 1", datasets=["nope"], storage_path=storage)
    assert "error" in res
