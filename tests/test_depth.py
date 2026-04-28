"""Adaptive profiling depth (B7)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local


def _write(path, n_rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["x"])
        for i in range(n_rows):
            w.writerow([i])


def test_invalid_depth_rejected(tmp_path):
    csv_path = tmp_path / "x.csv"
    _write(csv_path, 10)
    storage = tmp_path / "data-index"
    storage.mkdir()
    res = index_local(path=str(csv_path), name="x", depth="bogus", storage_path=str(storage))
    assert "error" in res


def test_shallow_caps_row_count(tmp_path):
    csv_path = tmp_path / "x.csv"
    _write(csv_path, 200_000)
    storage = tmp_path / "data-index"
    storage.mkdir()
    res = index_local(path=str(csv_path), name="x", depth="shallow", storage_path=str(storage))
    assert res["result"]["rows"] == 100_000
    assert res["result"]["depth"] == "shallow"


def test_standard_default(tmp_path):
    csv_path = tmp_path / "x.csv"
    _write(csv_path, 50)
    storage = tmp_path / "data-index"
    storage.mkdir()
    res = index_local(path=str(csv_path), name="x", storage_path=str(storage))
    assert res["result"]["depth"] == "standard"
