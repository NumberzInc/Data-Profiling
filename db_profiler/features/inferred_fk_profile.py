from __future__ import annotations

import re
from itertools import combinations
from typing import Any, Mapping

import pandas as pd
from pandas.api.types import is_numeric_dtype, is_object_dtype, is_string_dtype


JOIN_NAME_TOKENS = ("id", "key", "code", "uuid", "number", "num", "identifier")


def profile_inferred_foreign_keys(
    tables: Mapping[str, pd.DataFrame],
    min_confidence: float = 0.50,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for left_table, right_table in combinations(sorted(tables), 2):
        left_frame = tables[left_table]
        right_frame = tables[right_table]
        for left_column, right_column in _candidate_column_pairs(left_table, left_frame, right_table, right_frame):
            parent_table, parent_column, parent_values, child_table, child_column, child_values = _orient_parent_child(
                left_table,
                left_column,
                left_frame[left_column],
                right_table,
                right_column,
                right_frame[right_column],
            )
            candidate = profile_relationship_candidate(
                parent_table=parent_table,
                parent_column=parent_column,
                parent_values=parent_values,
                child_table=child_table,
                child_column=child_column,
                child_values=child_values,
            )
            if candidate["relationship_confidence"] >= min_confidence and max(
                candidate["raw_coverage"],
                candidate["normalized_coverage"],
            ) > 0:
                candidates.append(candidate)
    return candidates


def profile_relationship_candidate(
    parent_table: str,
    parent_column: str,
    parent_values: pd.Series,
    child_table: str,
    child_column: str,
    child_values: pd.Series,
) -> dict[str, Any]:
    parent_strings = _non_null_strings(parent_values)
    child_strings = _non_null_strings(child_values)
    parent_set = set(parent_strings)
    child_set = set(child_strings)
    normalized_parent_set = {_normalize_for_join(value) for value in parent_strings}
    normalized_child_strings = [_normalize_for_join(value) for value in child_strings]

    raw_matches = sum(1 for value in child_strings if value in parent_set)
    normalized_matches = sum(1 for value in normalized_child_strings if value in normalized_parent_set)
    orphan_values = [value for value in child_strings if value not in parent_set]
    orphan_row_count = len(orphan_values)
    orphan_distinct_count = len(set(orphan_values))
    parent_uniqueness = _uniqueness_ratio(parent_values)
    raw_coverage = _percentage(raw_matches, len(child_strings))
    normalized_coverage = _percentage(normalized_matches, len(child_strings))
    type_compatibility = _data_type_compatibility(parent_values, child_values)
    pattern_compatibility = _pattern_compatibility(parent_strings, child_strings)

    return {
        "profiling_level": "table",
        "parent_table": parent_table,
        "parent_column": parent_column,
        "child_table": child_table,
        "child_column": child_column,
        "candidate_filter_reasons": [
            "compatible_column_name",
            "compatible_data_type",
            "sufficient_cardinality",
        ],
        "is_declared_relationship": False,
        "is_confirmed_relationship": False,
        "parent_uniqueness_ratio": parent_uniqueness,
        "parent_null_percentage": _null_percentage(parent_values),
        "child_null_percentage": _null_percentage(child_values),
        "child_to_parent_match_rate": raw_coverage,
        "orphan_child_count": orphan_row_count,
        "orphan_child_row_count": orphan_row_count,
        "orphan_child_distinct_count": orphan_distinct_count,
        "orphan_child_percentage": _percentage(orphan_row_count, len(child_strings)),
        "data_type_compatibility": type_compatibility,
        "pattern_compatibility": pattern_compatibility,
        "raw_coverage": raw_coverage,
        "normalized_coverage": normalized_coverage,
        "inferred_cardinality": _inferred_cardinality(parent_values, child_values),
        "relationship_confidence": _relationship_confidence(
            parent_uniqueness=parent_uniqueness,
            raw_coverage=raw_coverage,
            normalized_coverage=normalized_coverage,
            data_type_compatibility=type_compatibility,
            pattern_compatibility=pattern_compatibility,
        ),
    }


def _candidate_column_pairs(
    left_table: str,
    left_frame: pd.DataFrame,
    right_table: str,
    right_frame: pd.DataFrame,
) -> list[tuple[str, str]]:
    pairs = []
    for left_column in left_frame.columns:
        for right_column in right_frame.columns:
            if not _compatible_column_names(left_table, left_column, right_table, right_column):
                continue
            if not _data_types_can_match(left_frame[left_column], right_frame[right_column]):
                continue
            if not _sufficient_cardinality(left_frame[left_column], right_frame[right_column]):
                continue
            pairs.append((left_column, right_column))
    return pairs


def _orient_parent_child(
    left_table: str,
    left_column: str,
    left_values: pd.Series,
    right_table: str,
    right_column: str,
    right_values: pd.Series,
) -> tuple[str, str, pd.Series, str, str, pd.Series]:
    left_uniqueness = _uniqueness_ratio(left_values)
    right_uniqueness = _uniqueness_ratio(right_values)
    if right_uniqueness > left_uniqueness:
        return right_table, right_column, right_values, left_table, left_column, left_values
    return left_table, left_column, left_values, right_table, right_column, right_values


def _compatible_column_names(left_table: str, left_column: str, right_table: str, right_column: str) -> bool:
    left = _normalize_column_name(left_column)
    right = _normalize_column_name(right_column)
    if left == right:
        return any(token in left.split("_") for token in JOIN_NAME_TOKENS)

    left_table_stem = _table_name_stem(left_table)
    right_table_stem = _table_name_stem(right_table)
    return (
        left == "id"
        and right == f"{left_table_stem}_id"
        or right == "id"
        and left == f"{right_table_stem}_id"
    )


def _normalize_column_name(column: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", column.strip().casefold()).strip("_")


def _table_name_stem(table_name: str) -> str:
    normalized = _normalize_column_name(table_name)
    if normalized.endswith("ies"):
        return f"{normalized[:-3]}y"
    if normalized.endswith("s") and len(normalized) > 1:
        return normalized[:-1]
    return normalized


def _data_types_can_match(left_values: pd.Series, right_values: pd.Series) -> bool:
    if is_numeric_dtype(left_values.dtype) and is_numeric_dtype(right_values.dtype):
        return True
    return _is_text_like(left_values) and _is_text_like(right_values)


def _data_type_compatibility(left_values: pd.Series, right_values: pd.Series) -> str:
    return "compatible" if _data_types_can_match(left_values, right_values) else "incompatible"


def _is_text_like(values: pd.Series) -> bool:
    return is_string_dtype(values.dtype) or is_object_dtype(values.dtype)


def _sufficient_cardinality(left_values: pd.Series, right_values: pd.Series) -> bool:
    return max(_uniqueness_ratio(left_values), _uniqueness_ratio(right_values)) >= 0.80


def _uniqueness_ratio(values: pd.Series) -> float:
    non_null = _non_null_strings(values)
    if not non_null:
        return 0.0
    return _percentage(len(set(non_null)), len(non_null))


def _null_percentage(values: pd.Series) -> float:
    return _percentage(int(values.isna().sum()), len(values))


def _non_null_strings(values: pd.Series) -> list[str]:
    return [str(value) for value in values if not pd.isna(value)]


def _normalize_for_join(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().casefold())


def _pattern_compatibility(parent_values: list[str], child_values: list[str]) -> str:
    parent_patterns = {_pattern_signature(value) for value in parent_values}
    child_patterns = {_pattern_signature(value) for value in child_values}
    normalized_parent_patterns = {_pattern_signature(_normalize_for_join(value)) for value in parent_values}
    normalized_child_patterns = {_pattern_signature(_normalize_for_join(value)) for value in child_values}
    if parent_patterns & child_patterns or normalized_parent_patterns & normalized_child_patterns:
        return "compatible"
    return "incompatible"


def _pattern_signature(value: str) -> str:
    signature = []
    for character in value:
        if character.isalpha():
            signature.append("A")
        elif character.isdigit():
            signature.append("0")
        else:
            signature.append(character)
    return "".join(signature)


def _inferred_cardinality(parent_values: pd.Series, child_values: pd.Series) -> str:
    parent_unique = _uniqueness_ratio(parent_values) == 1.0
    child_unique = _uniqueness_ratio(child_values) == 1.0
    if parent_unique and child_unique:
        return "1:1"
    if parent_unique:
        return "1:N"
    return "N:M"


def _relationship_confidence(
    parent_uniqueness: float,
    raw_coverage: float,
    normalized_coverage: float,
    data_type_compatibility: str,
    pattern_compatibility: str,
) -> float:
    type_score = 1.0 if data_type_compatibility == "compatible" else 0.0
    pattern_score = 1.0 if pattern_compatibility == "compatible" else 0.0
    score = 0.35 * parent_uniqueness + 0.20 * raw_coverage + 0.20 * normalized_coverage + 0.15 * type_score + 0.10 * pattern_score
    return round(score, 3)


def _percentage(count: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return round(count / denominator, 4)
