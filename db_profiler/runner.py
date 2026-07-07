from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping
from uuid import uuid4

import pandas as pd

from . import __version__
from .config import ProfilingConfig
from .features.case_profile import profile_table_case_conventions
from .features.format_profile import profile_table_format_patterns
from .features.inferred_fk_profile import profile_inferred_foreign_keys
from .features.normalized_join_profile import profile_normalized_join_compatibility
from .output import empty_profile_document
from .ydata_profile import YDataProfiler


def build_profile(
    tables: Mapping[str, pd.DataFrame],
    config: ProfilingConfig,
    ydata_profiler: YDataProfiler | None = None,
) -> dict:
    profiler = ydata_profiler or YDataProfiler(include_raw=config.ydata.include_raw, explorative=config.ydata.explorative)
    document = empty_profile_document()
    profiled_at = datetime.now(timezone.utc).isoformat()

    document["metadata"] = {
        "run_id": str(uuid4()),
        "profiled_at": profiled_at,
        "profiler_version": __version__,
        "database": {
            "url": _redact_url(config.database.url),
            "schema": config.database.schema,
        },
        "sampling": {
            "mode": config.sampling.mode,
            "sample_rows": config.sampling.sample_rows,
        },
        "history": {
            "path": config.history.path,
        },
        "tool_versions": {
            "ydata_profiling": profiler.version,
        },
    }

    for table_name, frame in tables.items():
        document["tables"][table_name] = {
            "row_count": int(len(frame)),
            "sample_count": int(len(frame)),
            "column_count": int(len(frame.columns)),
            "columns": _column_metadata(frame),
            "custom_profiles": {
                "case_profile": profile_table_case_conventions(frame),
                "format_profile": profile_table_format_patterns(
                    frame,
                    min_affix_frequency=config.thresholds.min_affix_frequency,
                ),
            },
            "ydata_profile": profiler.profile_dataframe(table_name, frame),
        }

    document["relationships"]["normalized_join_candidates"] = profile_normalized_join_compatibility(
        tables,
        max_collision_rate=config.thresholds.max_normalized_collision_rate,
        min_match_rate=config.thresholds.min_join_match_rate,
    )
    document["relationships"]["inferred_candidates"] = profile_inferred_foreign_keys(
        tables,
        min_confidence=0.50,
    )

    return document


def _column_metadata(frame: pd.DataFrame) -> dict:
    return {
        column: {
            "dtype": str(frame[column].dtype),
            "nullable": bool(frame[column].isna().any()),
        }
        for column in frame.columns
    }


def _redact_url(url: str | None) -> str | None:
    if not url:
        return None
    if "@" not in url:
        return url
    scheme_and_auth, host = url.rsplit("@", 1)
    scheme = scheme_and_auth.split("://", 1)[0] if "://" in scheme_and_auth else "database"
    return f"{scheme}://***@{host}"
