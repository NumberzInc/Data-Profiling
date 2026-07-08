from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DatabaseConfig:
    url: str | None = None
    schema: str = "public"
    include_tables: list[str] = field(default_factory=list)


@dataclass
class SamplingConfig:
    mode: str = "sampled"
    sample_rows: int = 50_000


@dataclass
class ThresholdsConfig:
    wide_table_columns: int = 75
    max_normalized_collision_rate: float = 0.02
    min_join_match_rate: float = 0.95
    min_affix_frequency: float = 0.10


@dataclass
class HistoryConfig:
    path: str = "state/profile_history.jsonl"


@dataclass
class FreshnessConfig:
    trusted_timestamp_columns: dict[str, str] = field(default_factory=dict)
    expected_update_intervals_hours: dict[str, float] = field(default_factory=dict)


@dataclass
class YDataConfig:
    enabled: bool = True
    include_raw: bool = False
    explorative: bool = True


@dataclass
class ProfilingConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    freshness: FreshnessConfig = field(default_factory=FreshnessConfig)
    ydata: YDataConfig = field(default_factory=YDataConfig)


def load_config(path: Path | None) -> ProfilingConfig:
    config = ProfilingConfig()
    if path is None:
        return config

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    _apply_section(config.database, raw.get("database", {}))
    _apply_section(config.sampling, raw.get("sampling", {}))
    _apply_section(config.thresholds, raw.get("thresholds", {}))
    _apply_section(config.history, raw.get("history", {}))
    _apply_section(config.freshness, raw.get("freshness", {}))
    _apply_section(config.ydata, raw.get("ydata", {}))
    return config


def _apply_section(target: Any, values: Any) -> None:
    if values is None:
        return
    if not isinstance(values, dict):
        raise ValueError(f"Config section for {type(target).__name__} must be a mapping.")

    allowed = set(target.__dataclass_fields__)
    unknown = set(values) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown config option(s) for {type(target).__name__}: {names}")

    for key, value in values.items():
        setattr(target, key, value)
