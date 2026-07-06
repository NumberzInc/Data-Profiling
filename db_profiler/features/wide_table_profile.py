from __future__ import annotations

from typing import Any

import pandas as pd


def profile_wide_table(
    frame: pd.DataFrame,
    wide_table_threshold: int = 75,
) -> dict[str, Any]:
    column_count = len(frame.columns)
    return {
        "profiling_level": "table",
        "column_count": column_count,
        "threshold": wide_table_threshold,
        "exceeds_threshold": column_count > wide_table_threshold,
        "columns_over_threshold": column_count - wide_table_threshold,
    }
