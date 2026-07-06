from __future__ import annotations

import pandas as pd

from db_profiler.features.isolated_table_profile import profile_isolated_tables


# Helpers


def _table(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({col: ["a", "b", "c"] for col in columns})


# Edge cases


def test_empty_tables_returns_empty_list() -> None:
    result = profile_isolated_tables({})

    assert result == []


def test_single_table_is_always_isolated() -> None:
    tables = {"customers": _table(["customer_id", "name"])}

    result = profile_isolated_tables(tables)

    assert len(result) == 1
    assert result[0]["table"] == "customers"



# Isolation detection


def test_tables_sharing_key_column_are_not_isolated() -> None:
    tables = {
        "customers": _table(["customer_id", "name"]),
        "orders": _table(["customer_id", "total"]),
    }

    result = profile_isolated_tables(tables)

    assert result == []


def test_table_with_no_key_columns_is_isolated() -> None:
    tables = {
        "customers": _table(["customer_id", "name"]),
        "orders": _table(["customer_id", "total"]),
        "audit_log": _table(["action", "description", "timestamp"]),
    }

    result = profile_isolated_tables(tables)

    assert len(result) == 1
    assert result[0]["table"] == "audit_log"


def test_table_with_key_columns_matching_no_other_table_is_isolated() -> None:
    tables = {
        "customers": _table(["customer_id", "name"]),
        "products": _table(["product_id", "title"]),
    }

    result = profile_isolated_tables(tables)

    isolated_names = {r["table"] for r in result}
    assert isolated_names == {"customers", "products"}


def test_non_isolated_table_not_in_results() -> None:
    tables = {
        "customers": _table(["customer_id", "name"]),
        "orders": _table(["customer_id", "order_id", "total"]),
        "audit_log": _table(["action", "description"]),
    }

    result = profile_isolated_tables(tables)

    isolated_names = {r["table"] for r in result}
    assert "customers" not in isolated_names
    assert "orders" not in isolated_names
    assert "audit_log" in isolated_names


def test_multiple_isolated_tables_all_reported() -> None:
    tables = {
        "customers": _table(["customer_id"]),
        "products": _table(["product_id"]),
        "orphan_a": _table(["notes"]),
        "orphan_b": _table(["description"]),
    }

    result = profile_isolated_tables(tables)

    isolated_names = {r["table"] for r in result}
    assert "orphan_a" in isolated_names
    assert "orphan_b" in isolated_names


# Output contract

def test_isolated_table_reports_zero_shared_key_count() -> None:
    tables = {"customers": _table(["name", "status"])}

    result = profile_isolated_tables(tables)

    assert result[0]["shared_key_count"] == 0


def test_profiling_level_is_database() -> None:
    tables = {"customers": _table(["name"])}

    result = profile_isolated_tables(tables)

    assert result[0]["profiling_level"] == "database"


def test_output_has_required_keys() -> None:
    tables = {"customers": _table(["name"])}

    result = profile_isolated_tables(tables)

    assert set(result[0].keys()) == {
        "profiling_level",
        "table",
        "shared_key_count",
        "candidate_reason",
    }


def test_candidate_reason_is_unknown() -> None:
    tables = {"customers": _table(["name"])}

    result = profile_isolated_tables(tables)

    assert result[0]["candidate_reason"] == "unknown"


# Key-column matching guardrails
# ---------------------------------------------------------------------------


def test_key_matching_is_case_insensitive() -> None:
    tables = {
        "customers": _table(["CUSTOMER_ID", "name"]),
        "orders": _table(["customer_id", "total"]),
    }

    result = profile_isolated_tables(tables)

    assert result == []


def test_non_key_column_name_overlap_does_not_count_as_shared_key() -> None:
    tables = {
        "customers": _table(["name", "status"]),
        "products": _table(["name", "price"]),
    }

    result = profile_isolated_tables(tables)

    isolated_names = {r["table"] for r in result}
    assert "customers" in isolated_names
    assert "products" in isolated_names


def test_various_key_tokens_are_recognised() -> None:
    tables = {
        "a": _table(["order_code"]),
        "b": _table(["order_code", "total"]),
        "c": _table(["session_uuid"]),
        "d": _table(["session_uuid", "started_at"]),
    }

    result = profile_isolated_tables(tables)

    assert result == []


# ---------------------------------------------------------------------------
# Guardrail: does not mutate inputs
# ---------------------------------------------------------------------------


def test_does_not_mutate_input_tables() -> None:
    frame = _table(["customer_id", "name"])
    original = frame.copy(deep=True)
    tables = {"customers": frame}

    profile_isolated_tables(tables)

    assert frame.equals(original)
