from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def load_previous_table_profiles(history_path: Path | None) -> dict[str, dict[str, Any]]:
    if history_path is None or not history_path.exists():
        return {}

    latest_document = None
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        latest_document = json.loads(line)

    if latest_document is None:
        return {}

    previous: dict[str, dict[str, Any]] = {}
    for table_name, table_profile in latest_document.get("tables", {}).items():
        growth_profile = table_profile.get("growth_freshness_profile", {})
        if "current_row_count" in growth_profile:
            previous[table_name] = {"row_count": growth_profile["current_row_count"]}
    return previous


def append_profile_history(profile_document: dict[str, Any], history_path: Path | None) -> None:
    if history_path is None:
        return

    history_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "metadata": profile_document.get("metadata", {}),
        "tables": {
            table_name: {
                "growth_freshness_profile": table_profile.get("growth_freshness_profile", {}),
            }
            for table_name, table_profile in profile_document.get("tables", {}).items()
        },
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True, default=str) + "\n")


def profile_table_growth_and_freshness(
    table_name: str,
    frame: pd.DataFrame,
    profiled_at: datetime,
    previous_profile: dict[str, Any] | None,
    trusted_timestamp_column: str | None,
    expected_update_interval_hours: float | None,
) -> dict[str, Any]:
    current_row_count = int(len(frame))
    previous_row_count = previous_profile.get("row_count") if previous_profile else None
    row_count_change = _row_count_change(current_row_count, previous_row_count)
    latest_timestamp, unavailable_reason = _latest_trusted_timestamp(frame, trusted_timestamp_column)
    hours_since_latest_update = _hours_since(profiled_at, latest_timestamp)
    freshness_status = _freshness_status(
        latest_timestamp=latest_timestamp,
        hours_since_latest_update=hours_since_latest_update,
        expected_update_interval_hours=expected_update_interval_hours,
    )

    return {
        "profiling_level": "table",
        "table_name": table_name,
        "current_row_count": current_row_count,
        "previous_row_count": previous_row_count,
        "row_count_change": row_count_change,
        "row_count_change_percentage": _row_count_change_percentage(row_count_change, previous_row_count),
        "profiling_timestamp": profiled_at.isoformat(),
        "trusted_timestamp_column": trusted_timestamp_column,
        "latest_trusted_timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
        "hours_since_latest_update": hours_since_latest_update,
        "expected_update_interval_hours": expected_update_interval_hours,
        "freshness_status": freshness_status,
        "unavailable_reason": unavailable_reason,
    }


def _row_count_change(current_row_count: int, previous_row_count: int | None) -> int | None:
    if previous_row_count is None:
        return None
    return current_row_count - int(previous_row_count)


def _row_count_change_percentage(row_count_change: int | None, previous_row_count: int | None) -> float | None:
    if row_count_change is None or previous_row_count in (None, 0):
        return None
    return round(row_count_change / previous_row_count, 4)


def _latest_trusted_timestamp(
    frame: pd.DataFrame,
    trusted_timestamp_column: str | None,
) -> tuple[datetime | None, str | None]:
    if trusted_timestamp_column is None:
        return None, "trusted_timestamp_column_not_configured"
    if trusted_timestamp_column not in frame.columns:
        return None, "trusted_timestamp_column_missing"

    timestamps = pd.to_datetime(frame[trusted_timestamp_column], errors="coerce", utc=True).dropna()
    if timestamps.empty:
        return None, "trusted_timestamp_values_unparseable"
    return timestamps.max().to_pydatetime(), None


def _hours_since(profiled_at: datetime, latest_timestamp: datetime | None) -> float | None:
    if latest_timestamp is None:
        return None
    if profiled_at.tzinfo is None:
        profiled_at = profiled_at.replace(tzinfo=timezone.utc)
    delta = profiled_at.astimezone(timezone.utc) - latest_timestamp.astimezone(timezone.utc)
    return round(delta.total_seconds() / 3600, 4)


def _freshness_status(
    latest_timestamp: datetime | None,
    hours_since_latest_update: float | None,
    expected_update_interval_hours: float | None,
) -> str:
    if latest_timestamp is None or hours_since_latest_update is None or expected_update_interval_hours is None:
        return "unknown"
    if hours_since_latest_update <= expected_update_interval_hours:
        return "fresh"
    return "stale"
