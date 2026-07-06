from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from db_profiler.features.growth_freshness_profile import (
    append_history_entry,
    load_history,
    profile_table_growth_freshness,
)


NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Growth metrics
# ---------------------------------------------------------------------------


def test_no_history_reports_null_growth_fields() -> None:
    frame = pd.DataFrame({"id": [1, 2, 3]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        now=NOW,
    )

    assert profile["profiling_level"] == "table"
    assert profile["current_row_count"] == 3
    assert profile["previous_row_count"] is None
    assert profile["row_count_change"] is None
    assert profile["row_count_change_percentage"] is None


def test_growth_reports_positive_change() -> None:
    frame = pd.DataFrame({"id": range(150)})
    history = [{"table": "customers", "row_count": 100, "profiled_at": "2026-06-28T12:00:00+00:00"}]

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=history,
        now=NOW,
    )

    assert profile["current_row_count"] == 150
    assert profile["previous_row_count"] == 100
    assert profile["row_count_change"] == 50
    assert profile["row_count_change_percentage"] == 0.5


def test_growth_reports_negative_change_on_shrinkage() -> None:
    frame = pd.DataFrame({"id": range(80)})
    history = [{"table": "customers", "row_count": 100, "profiled_at": "2026-06-28T12:00:00+00:00"}]

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=history,
        now=NOW,
    )

    assert profile["row_count_change"] == -20
    assert profile["row_count_change_percentage"] == -0.2


def test_growth_reports_zero_when_count_unchanged() -> None:
    frame = pd.DataFrame({"id": range(100)})
    history = [{"table": "customers", "row_count": 100, "profiled_at": "2026-06-28T12:00:00+00:00"}]

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=history,
        now=NOW,
    )

    assert profile["row_count_change"] == 0
    assert profile["row_count_change_percentage"] == 0.0


def test_growth_uses_most_recent_history_entry() -> None:
    frame = pd.DataFrame({"id": range(150)})
    history = [
        {"table": "customers", "row_count": 50, "profiled_at": "2026-06-27T12:00:00+00:00"},
        {"table": "customers", "row_count": 100, "profiled_at": "2026-06-28T12:00:00+00:00"},
    ]

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=history,
        now=NOW,
    )

    assert profile["previous_row_count"] == 100


def test_growth_ignores_history_entries_for_other_tables() -> None:
    frame = pd.DataFrame({"id": range(50)})
    history = [{"table": "orders", "row_count": 200, "profiled_at": "2026-06-28T12:00:00+00:00"}]

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=history,
        now=NOW,
    )

    assert profile["previous_row_count"] is None
    assert profile["row_count_change"] is None


# ---------------------------------------------------------------------------
# Freshness metrics
# ---------------------------------------------------------------------------


def test_no_timestamp_column_declared_reports_unknown_freshness() -> None:
    frame = pd.DataFrame({"id": [1, 2], "updated_at": ["2026-06-29", "2026-06-28"]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        now=NOW,
    )

    assert profile["freshness"]["status"] == "unknown"
    assert profile["freshness"]["timestamp_column"] is None
    assert profile["freshness"]["latest_update"] is None
    assert profile["freshness"]["hours_since_update"] is None


def test_timestamp_column_not_in_frame_reports_unknown_freshness() -> None:
    frame = pd.DataFrame({"id": [1, 2]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        now=NOW,
    )

    assert profile["freshness"]["status"] == "unknown"
    assert profile["freshness"]["latest_update"] is None


def test_all_null_timestamp_column_reports_unknown_freshness() -> None:
    frame = pd.DataFrame({"id": [1, 2], "updated_at": [None, None]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        now=NOW,
    )

    assert profile["freshness"]["status"] == "unknown"
    assert profile["freshness"]["latest_update"] is None


def test_fresh_when_within_expected_interval() -> None:
    recent = (NOW - timedelta(hours=12)).isoformat()
    frame = pd.DataFrame({"id": [1], "updated_at": [recent]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        expected_update_interval_hours=24,
        now=NOW,
    )

    assert profile["freshness"]["status"] == "fresh"
    assert profile["freshness"]["hours_since_update"] == 12.0
    assert profile["freshness"]["timestamp_column"] == "updated_at"
    assert profile["freshness"]["expected_update_interval_hours"] == 24


def test_stale_when_beyond_expected_interval() -> None:
    old = (NOW - timedelta(hours=48)).isoformat()
    frame = pd.DataFrame({"id": [1], "updated_at": [old]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        expected_update_interval_hours=24,
        now=NOW,
    )

    assert profile["freshness"]["status"] == "stale"
    assert profile["freshness"]["hours_since_update"] == 48.0


def test_no_expected_interval_reports_unknown_status_but_includes_latest_update() -> None:
    recent = (NOW - timedelta(hours=5)).isoformat()
    frame = pd.DataFrame({"id": [1], "updated_at": [recent]})

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        now=NOW,
    )

    assert profile["freshness"]["status"] == "unknown"
    assert profile["freshness"]["latest_update"] is not None
    assert profile["freshness"]["hours_since_update"] == 5.0
    assert profile["freshness"]["expected_update_interval_hours"] is None


def test_uses_latest_timestamp_across_multiple_rows() -> None:
    frame = pd.DataFrame({
        "id": [1, 2, 3],
        "updated_at": [
            (NOW - timedelta(hours=48)).isoformat(),
            (NOW - timedelta(hours=6)).isoformat(),
            (NOW - timedelta(hours=24)).isoformat(),
        ],
    })

    profile = profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        expected_update_interval_hours=12,
        now=NOW,
    )

    assert profile["freshness"]["hours_since_update"] == 6.0
    assert profile["freshness"]["status"] == "fresh"


def test_does_not_mutate_input_frame() -> None:
    frame = pd.DataFrame({"id": [1, 2], "updated_at": ["2026-06-29", "2026-06-28"]})
    original = frame.copy(deep=True)

    profile_table_growth_freshness(
        table_name="customers",
        frame=frame,
        history=None,
        timestamp_column="updated_at",
        now=NOW,
    )

    assert frame.equals(original)


# ---------------------------------------------------------------------------
# History I/O helpers
# ---------------------------------------------------------------------------


def test_load_history_returns_empty_list_when_file_does_not_exist(tmp_path: Path) -> None:
    result = load_history(tmp_path / "history.jsonl")
    assert result == []


def test_load_history_parses_all_jsonl_entries(tmp_path: Path) -> None:
    history_file = tmp_path / "history.jsonl"
    history_file.write_text(
        json.dumps({"table": "customers", "row_count": 100, "profiled_at": "2026-06-28T00:00:00+00:00"}) + "\n"
        + json.dumps({"table": "orders", "row_count": 200, "profiled_at": "2026-06-28T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )

    result = load_history(history_file)

    assert len(result) == 2
    assert result[0]["table"] == "customers"
    assert result[1]["table"] == "orders"


def test_append_history_entry_creates_file_when_missing(tmp_path: Path) -> None:
    history_file = tmp_path / "subdir" / "history.jsonl"

    append_history_entry(history_file, {"table": "customers", "row_count": 100, "profiled_at": "2026-06-29T00:00:00+00:00"})

    assert history_file.exists()
    entries = [json.loads(line) for line in history_file.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    assert entries[0]["table"] == "customers"


def test_append_history_entry_appends_without_overwriting(tmp_path: Path) -> None:
    history_file = tmp_path / "history.jsonl"
    history_file.write_text(
        json.dumps({"table": "customers", "row_count": 100, "profiled_at": "2026-06-28T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )

    append_history_entry(history_file, {"table": "customers", "row_count": 150, "profiled_at": "2026-06-29T00:00:00+00:00"})

    entries = [json.loads(line) for line in history_file.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 2
    assert entries[0]["row_count"] == 100
    assert entries[1]["row_count"] == 150
