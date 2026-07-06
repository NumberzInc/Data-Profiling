from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

import pandas as pd

from db_profiler.features.normalized_join_profile import JOIN_NAME_TOKENS


def profile_isolated_tables(tables: Mapping[str, pd.DataFrame]) -> list[dict[str, Any]]:
    if not tables:
        return []

    table_key_columns: dict[str, set[str]] = {
        table_name: {_normalize_column(col) for col in frame.columns if _is_key_column(col)}
        for table_name, frame in tables.items()
    }

    key_column_counts: Counter[str] = Counter()
    for key_cols in table_key_columns.values():
        key_column_counts.update(key_cols)

    shared_keys = {col for col, count in key_column_counts.items() if count > 1}

    return [
        {
            "profiling_level": "database",
            "table": table_name,
            "shared_key_count": 0,
            "candidate_reason": "unknown",
        }
        for table_name in sorted(tables)
        if not (table_key_columns[table_name] & shared_keys)
    ]


def _normalize_column(column: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", column.strip().casefold()).strip("_")


def _is_key_column(column: str) -> bool:
    normalized = _normalize_column(column)
    return any(token in normalized.split("_") for token in JOIN_NAME_TOKENS)
