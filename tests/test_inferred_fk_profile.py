import pandas as pd

from db_profiler.config import ProfilingConfig
from db_profiler.features.inferred_fk_profile import (
    profile_inferred_foreign_keys,
    profile_relationship_candidate,
)
from db_profiler.runner import build_profile


class StubYDataProfiler:
    version = "stub"

    def profile_dataframe(self, table_name: str, frame: pd.DataFrame) -> dict:
        return {"table": {"n": len(frame)}, "variables": {}, "alerts": []}


def test_profile_relationship_candidate_reports_fk_metrics() -> None:
    customers = pd.Series(["C001", "C002", "C003"], name="customer_id")
    orders = pd.Series(["C001", "C001", "C002", "MISSING", None], name="customer_id")

    candidate = profile_relationship_candidate(
        parent_table="customers",
        parent_column="customer_id",
        parent_values=customers,
        child_table="orders",
        child_column="customer_id",
        child_values=orders,
    )

    assert candidate["profiling_level"] == "table"
    assert candidate["parent_table"] == "customers"
    assert candidate["parent_column"] == "customer_id"
    assert candidate["child_table"] == "orders"
    assert candidate["child_column"] == "customer_id"
    assert candidate["is_declared_relationship"] is False
    assert candidate["is_confirmed_relationship"] is False
    assert candidate["parent_uniqueness_ratio"] == 1.0
    assert candidate["parent_null_percentage"] == 0.0
    assert candidate["child_null_percentage"] == 0.2
    assert candidate["child_to_parent_match_rate"] == 0.75
    assert candidate["orphan_child_count"] == 1
    assert candidate["orphan_child_row_count"] == 1
    assert candidate["orphan_child_distinct_count"] == 1
    assert candidate["orphan_child_percentage"] == 0.25
    assert candidate["data_type_compatibility"] == "compatible"
    assert candidate["pattern_compatibility"] == "compatible"
    assert candidate["raw_coverage"] == 0.75
    assert candidate["normalized_coverage"] == 0.75
    assert candidate["inferred_cardinality"] == "1:N"
    assert candidate["relationship_confidence"] == 0.9


def test_profile_relationship_candidate_reports_orphan_rows_and_distinct_orphans() -> None:
    customers = pd.Series(["C001", "C002"], name="customer_id")
    orders = pd.Series(["C001", "MISSING", "MISSING", "UNKNOWN"], name="customer_id")

    candidate = profile_relationship_candidate(
        parent_table="customers",
        parent_column="customer_id",
        parent_values=customers,
        child_table="orders",
        child_column="customer_id",
        child_values=orders,
    )

    assert candidate["orphan_child_count"] == 3
    assert candidate["orphan_child_row_count"] == 3
    assert candidate["orphan_child_distinct_count"] == 2
    assert candidate["orphan_child_percentage"] == 0.75


def test_profile_relationship_candidate_uses_normalized_coverage() -> None:
    customers = pd.Series(["ABC-001", "ABC-002"], name="customer_code")
    orders = pd.Series(["abc001", " abc002 "], name="customer_code")

    candidate = profile_relationship_candidate(
        parent_table="customers",
        parent_column="customer_code",
        parent_values=customers,
        child_table="orders",
        child_column="customer_code",
        child_values=orders,
    )

    assert candidate["raw_coverage"] == 0.0
    assert candidate["normalized_coverage"] == 1.0
    assert candidate["child_to_parent_match_rate"] == 0.0
    assert candidate["relationship_confidence"] == 0.8


def test_profile_inferred_foreign_keys_excludes_low_cardinality_status_columns() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "customer_id": ["C001", "C002", "C003"],
                "status": ["ACTIVE", "INACTIVE", "ACTIVE"],
            }
        ),
        "orders": pd.DataFrame(
            {
                "customer_id": ["C001", "C002", "C003"],
                "status": ["ACTIVE", "ACTIVE", "INACTIVE"],
            }
        ),
    }

    candidates = profile_inferred_foreign_keys(tables, min_confidence=0.50)

    assert len(candidates) == 1
    assert candidates[0]["parent_column"] == "customer_id"
    assert candidates[0]["child_column"] == "customer_id"
    assert candidates[0]["candidate_filter_reasons"] == [
        "compatible_column_name",
        "compatible_data_type",
        "sufficient_cardinality",
    ]


def test_profile_inferred_foreign_keys_detects_id_to_table_id_pattern() -> None:
    tables = {
        "customers": pd.DataFrame(
            {
                "id": ["C001", "C002", "C003"],
                "name": ["Ada", "Grace", "Katherine"],
            }
        ),
        "orders": pd.DataFrame(
            {
                "order_id": ["O001", "O002", "O003"],
                "customer_id": ["C001", "C002", "C001"],
            }
        ),
    }

    candidates = profile_inferred_foreign_keys(tables, min_confidence=0.50)

    assert len(candidates) == 1
    assert candidates[0]["parent_table"] == "customers"
    assert candidates[0]["parent_column"] == "id"
    assert candidates[0]["child_table"] == "orders"
    assert candidates[0]["child_column"] == "customer_id"
    assert candidates[0]["candidate_filter_reasons"] == [
        "compatible_column_name",
        "compatible_data_type",
        "sufficient_cardinality",
    ]


def test_profile_relationship_candidate_confidence_uses_zero_to_one_scale() -> None:
    parent = pd.Series(["C001", "C002"], name="customer_id")
    child = pd.Series(["C001", "C002"], name="customer_id")

    candidate = profile_relationship_candidate(
        parent_table="customers",
        parent_column="customer_id",
        parent_values=parent,
        child_table="orders",
        child_column="customer_id",
        child_values=child,
    )

    assert candidate["relationship_confidence"] == 1.0


def test_profile_inferred_foreign_keys_requires_evidence_beyond_similar_names() -> None:
    tables = {
        "customers": pd.DataFrame({"customer_id": ["C001", "C002", "C003"]}),
        "orders": pd.DataFrame({"customer_id": ["X001", "X002", "X003"]}),
    }

    candidates = profile_inferred_foreign_keys(tables, min_confidence=0.50)

    assert candidates == []


def test_build_profile_wires_inferred_fk_candidates_into_relationships() -> None:
    tables = {
        "customers": pd.DataFrame({"customer_id": ["C001", "C002", "C003"]}),
        "orders": pd.DataFrame({"customer_id": ["C001", "C002", "C001"]}),
    }

    document = build_profile(
        tables=tables,
        config=ProfilingConfig(),
        ydata_profiler=StubYDataProfiler(),
    )

    candidates = document["relationships"]["inferred_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["parent_table"] == "customers"
    assert candidates[0]["child_table"] == "orders"
    assert candidates[0]["inferred_cardinality"] == "1:N"
