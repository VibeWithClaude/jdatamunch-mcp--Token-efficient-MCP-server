"""Spearman correlation (B10)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.get_correlations import get_correlations


@pytest.fixture
def indexed(tmp_path):
    # x and y are monotonically related but non-linear: y = x^3.
    # Pearson(r) is < 1 here (curved), but Spearman(r) is exactly 1 (rank-equal).
    csv_path = tmp_path / "rank.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["x", "y"])
        for i in range(1, 51):
            w.writerow([i, i ** 3])
    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(csv_path), name="rank", storage_path=str(storage))
    return str(storage)


def test_spearman_perfect_on_monotonic_nonlinear(indexed):
    res = get_correlations(
        dataset="rank",
        method="spearman",
        min_abs_correlation=0.0,
        storage_path=indexed,
    )
    pairs = res["result"]["correlations"]
    assert pairs, "expected at least one pair"
    assert abs(pairs[0]["r"] - 1.0) < 1e-6


def test_pearson_lower_than_spearman_on_curved(indexed):
    pearson = get_correlations(
        dataset="rank", method="pearson", min_abs_correlation=0.0,
        storage_path=indexed,
    )["result"]["correlations"][0]["r"]
    spearman = get_correlations(
        dataset="rank", method="spearman", min_abs_correlation=0.0,
        storage_path=indexed,
    )["result"]["correlations"][0]["r"]
    assert spearman > pearson


def test_invalid_method_rejected(indexed):
    res = get_correlations(dataset="rank", method="kendall", storage_path=indexed)
    assert "error" in res
