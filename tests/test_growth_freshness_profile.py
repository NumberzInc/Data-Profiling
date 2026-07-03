from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from db_profiler.config import ProfilingConfig
from db_profiler.features.growth_freshness_profile import (
    append_profile_history,
    load_previous_table_profiles,
    profile_table_growth_and_freshness,
)
from db_profiler.runner import build_profile


class StubYDataProfiler:
    version = "stub"

    def profile_dataframe(self, table_name: str, frame: pd.DataFrame) -> dict:
        return {"table": {"n": len(frame)}, "variables": {}, "alerts": []}


def test_profile_table_growth_and_freshness_reports_row_delta_and_fresh_status() -> None:
    frame = pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "updated_at": ["2026-07-01T09:00:00+00:00", "2026-07-01T10:00:00+00:00", None],
        }
    )
    previous = {"row_count": 2}

    profile = profile_table_growth_and_freshness(
        table_name="orders",
        frame=frame,
        profiled_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        previous_profile=previous,
        trusted_timestamp_column="updated_at",
        expected_update_interval_hours=4,
    )

    assert profile["profiling_level"] == "table"
    assert profile["current_row_count"] == 3
    assert profile["previous_row_count"] == 2
    assert profile["row_count_change"] == 1
    assert profile["row_count_change_percentage"] == 0.5
    assert profile["profiling_timestamp"] == "2026-07-01T12:00:00+00:00"
    assert profile["trusted_timestamp_column"] == "updated_at"
    assert profile["latest_trusted_timestamp"] == "2026-07-01T10:00:00+00:00"
    assert profile["hours_since_latest_update"] == 2.0
    assert profile["expected_update_interval_hours"] == 4
    assert profile["freshness_status"] == "fresh"
    assert profile["unavailable_reason"] is None


def test_profile_table_growth_and_freshness_reports_stale_when_interval_exceeded() -> None:
    frame = pd.DataFrame({"updated_at": ["2026-06-30T00:00:00+00:00"]})

    profile = profile_table_growth_and_freshness(
        table_name="orders",
        frame=frame,
        profiled_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        previous_profile=None,
        trusted_timestamp_column="updated_at",
        expected_update_interval_hours=24,
    )

    assert profile["previous_row_count"] is None
    assert profile["row_count_change"] is None
    assert profile["row_count_change_percentage"] is None
    assert profile["hours_since_latest_update"] == 36.0
    assert profile["freshness_status"] == "stale"


def test_profile_table_growth_and_freshness_reports_unknown_without_trusted_timestamp() -> None:
    frame = pd.DataFrame({"created_at": ["2026-07-01T10:00:00+00:00"]})

    profile = profile_table_growth_and_freshness(
        table_name="orders",
        frame=frame,
        profiled_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        previous_profile=None,
        trusted_timestamp_column=None,
        expected_update_interval_hours=None,
    )

    assert profile["latest_trusted_timestamp"] is None
    assert profile["hours_since_latest_update"] is None
    assert profile["freshness_status"] == "unknown"
    assert profile["unavailable_reason"] == "trusted_timestamp_column_not_configured"


def test_load_previous_table_profiles_reads_latest_jsonl_snapshot(tmp_path: Path) -> None:
    history_path = tmp_path / "profile_history.jsonl"
    history_path.write_text(
        "\n".join(
            [
                '{"metadata": {"run_id": "old"}, "tables": {"orders": {"growth_freshness_profile": {"current_row_count": 2}}}}',
                '{"metadata": {"run_id": "new"}, "tables": {"orders": {"growth_freshness_profile": {"current_row_count": 5}}}}',
            ]
        ),
        encoding="utf-8",
    )

    previous = load_previous_table_profiles(history_path)

    assert previous == {"orders": {"row_count": 5}}


def test_append_profile_history_writes_compact_jsonl_snapshot(tmp_path: Path) -> None:
    history_path = tmp_path / "profile_history.jsonl"
    profile_document = {
        "metadata": {"run_id": "test-run"},
        "tables": {
            "orders": {
                "growth_freshness_profile": {"current_row_count": 7},
                "ydata_profile": {"large": "excluded"},
            }
        },
    }

    append_profile_history(profile_document, history_path)

    previous = load_previous_table_profiles(history_path)
    written = history_path.read_text(encoding="utf-8")
    assert previous == {"orders": {"row_count": 7}}
    assert "test-run" in written
    assert "large" not in written


def test_build_profile_includes_growth_freshness_profiles() -> None:
    config = ProfilingConfig()
    config.freshness.trusted_timestamp_columns = {"orders": "updated_at"}
    config.freshness.expected_update_intervals_hours = {"orders": 24}
    frame = pd.DataFrame({"order_id": [1], "updated_at": ["2026-07-01T10:00:00+00:00"]})

    document = build_profile(
        tables={"orders": frame},
        config=config,
        ydata_profiler=StubYDataProfiler(),
    )

    profile = document["tables"]["orders"]["growth_freshness_profile"]
    assert profile["current_row_count"] == 1
    assert profile["trusted_timestamp_column"] == "updated_at"
    assert profile["freshness_status"] in {"fresh", "stale"}
