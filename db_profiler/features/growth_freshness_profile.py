from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def profile_table_growth_freshness(
    table_name: str,
    frame: pd.DataFrame,
    history: list[dict] | None,
    timestamp_column: str | None = None,
    expected_update_interval_hours: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    current_row_count = len(frame)
    previous_entry = _most_recent_entry(history, table_name)

    previous_row_count = None
    row_count_change = None
    row_count_change_percentage = None

    if previous_entry is not None:
        previous_row_count = previous_entry["row_count"]
        row_count_change = current_row_count - previous_row_count
        if previous_row_count != 0:
            row_count_change_percentage = round(row_count_change / previous_row_count, 4)

    return {
        "profiling_level": "table",
        "profiled_at": now.isoformat(),
        "current_row_count": current_row_count,
        "previous_row_count": previous_row_count,
        "row_count_change": row_count_change,
        "row_count_change_percentage": row_count_change_percentage,
        "freshness": _compute_freshness(frame, timestamp_column, expected_update_interval_hours, now),
    }


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_history_entry(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _most_recent_entry(history: list[dict] | None, table_name: str) -> dict | None:
    if not history:
        return None
    entries = [e for e in history if e.get("table") == table_name]
    if not entries:
        return None
    return max(entries, key=lambda e: e["profiled_at"])


def _compute_freshness(
    frame: pd.DataFrame,
    timestamp_column: str | None,
    expected_update_interval_hours: float | None,
    now: datetime,
) -> dict[str, Any]:
    base = {
        "timestamp_column": timestamp_column,
        "latest_update": None,
        "hours_since_update": None,
        "expected_update_interval_hours": expected_update_interval_hours,
    }

    if timestamp_column is None:
        return {"status": "unknown", **base}

    if timestamp_column not in frame.columns:
        return {"status": "unknown", **base}

    parsed = pd.to_datetime(frame[timestamp_column], utc=True, errors="coerce")
    latest = parsed.max()

    if pd.isna(latest):
        return {"status": "unknown", **base}

    latest_dt = latest.to_pydatetime()
    hours_since_update = round((now - latest_dt).total_seconds() / 3600, 2)

    if expected_update_interval_hours is not None:
        status = "fresh" if hours_since_update <= expected_update_interval_hours else "stale"
    else:
        status = "unknown"

    return {
        "status": status,
        "timestamp_column": timestamp_column,
        "latest_update": latest_dt.isoformat(),
        "hours_since_update": hours_since_update,
        "expected_update_interval_hours": expected_update_interval_hours,
    }
