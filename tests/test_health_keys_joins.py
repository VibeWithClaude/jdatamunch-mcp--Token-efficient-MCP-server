"""Dataset health (B4), suggest_keys + suggest_joins (B5)."""

import csv

import pytest

from jdatamunch_mcp.tools.index_local import index_local
from jdatamunch_mcp.tools.get_dataset_health import get_dataset_health
from jdatamunch_mcp.tools.suggest_keys import suggest_keys
from jdatamunch_mcp.tools.suggest_joins import suggest_joins


@pytest.fixture
def storage(tmp_path):
    customers = tmp_path / "customers.csv"
    with open(customers, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["customer_id", "email"])
        for i in range(1, 21):
            w.writerow([i, f"user{i}@example.com"])

    orders = tmp_path / "orders.csv"
    with open(orders, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "customer_id", "amount"])
        for i in range(1, 31):
            w.writerow([i, (i % 20) + 1, i * 9.99])

    storage = tmp_path / "data-index"
    storage.mkdir()
    index_local(path=str(customers), name="customers", storage_path=str(storage))
    index_local(path=str(orders), name="orders", storage_path=str(storage))
    return str(storage)


def test_dataset_health_grade_present(storage):
    res = get_dataset_health(dataset="customers", storage_path=storage)
    assert "error" not in res
    assert res["result"]["grade"] in {"A", "B", "C", "D", "F"}
    assert "components" in res["result"]
    assert "issues" in res["result"]


def test_suggest_keys_finds_pk(storage):
    res = suggest_keys(dataset="customers", storage_path=storage)
    names = {c["column"] for c in res["result"]["candidates"]}
    assert "customer_id" in names


def test_suggest_joins_finds_fk(storage):
    res = suggest_joins(dataset="orders", storage_path=storage)
    proposals = res["result"]["proposals"]
    # orders.customer_id should map to customers.customer_id
    assert any(
        p["source_column"] == "customer_id"
        and p["target_dataset"] == "customers"
        and p["target_column"] == "customer_id"
        for p in proposals
    ), proposals
