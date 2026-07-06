from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd


def profile_table_semantic_aliases(
    table_name: str,
    frame: pd.DataFrame,
    configured_aliases: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, Any]]:
    profiles = {}
    for column in frame.columns:
        aliases = configured_aliases.get(f"{table_name}.{column}") or configured_aliases.get(column)
        if aliases:
            profiles[column] = profile_semantic_aliases(frame[column], aliases)
    return profiles


def profile_semantic_aliases(values: pd.Series, aliases: dict[str, list[str]]) -> dict[str, Any]:
    alias_lookup = _alias_lookup(aliases)
    non_null_values = [str(value) for value in values if not pd.isna(value)]
    canonical_values = [_canonicalize(value, alias_lookup) for value in non_null_values]
    canonical_counts = Counter(canonical_values)
    groups: dict[str, list[str]] = defaultdict(list)
    unmapped_values = []

    for raw_value, canonical_value in zip(non_null_values, canonical_values):
        if canonical_value == raw_value:
            if _normalize(raw_value) not in alias_lookup:
                if raw_value not in unmapped_values:
                    unmapped_values.append(raw_value)
                continue
        variants = groups[canonical_value]
        if raw_value not in variants:
            variants.append(raw_value)

    variation_groups = [
        {
            "canonical_value": canonical_value,
            "raw_variants": variants,
            "count": canonical_counts[canonical_value],
        }
        for canonical_value, variants in groups.items()
        if len(variants) > 1
    ]

    mapped_count = len(non_null_values) - sum(1 for value in non_null_values if value in unmapped_values)

    return {
        "profiling_level": "column",
        "raw_distinct_count": len(set(non_null_values)),
        "canonical_distinct_count": len(set(canonical_values)),
        "variation_group_count": len(variation_groups),
        "variation_groups": variation_groups[:10],
        "unmapped_values": unmapped_values[:25],
        "mapped_value_percentage": _percentage(mapped_count, len(non_null_values)),
    }


def _alias_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
    lookup = {}
    for canonical_value, raw_aliases in aliases.items():
        lookup[_normalize(canonical_value)] = canonical_value
        for alias in raw_aliases:
            lookup[_normalize(alias)] = canonical_value
    return lookup


def _canonicalize(value: str, alias_lookup: dict[str, str]) -> str:
    return alias_lookup.get(_normalize(value), value)


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().replace(".", "").split())


def _percentage(count: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(count / denominator, 4)

