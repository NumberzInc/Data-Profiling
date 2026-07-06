from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import pandas as pd


EXTENSION_PATTERN = re.compile(r"\b(?:ext|extension|x)\.?\s*\d+\b", re.IGNORECASE)


def profile_table_phone_numbers(
    table_name: str,
    frame: pd.DataFrame,
    configured_columns: dict[str, list[str]],
    default_country: str = "US",
) -> dict[str, dict[str, Any]]:
    profiles = {}
    for column in configured_columns.get(table_name, []):
        if column in frame.columns:
            profiles[column] = profile_phone_numbers(frame[column], default_country=default_country)
    return profiles


def profile_phone_numbers(values: pd.Series, default_country: str = "US") -> dict[str, Any]:
    non_null_values = [str(value) for value in values if not pd.isna(value)]
    parsed_values = [_parse_phone(value, default_country=default_country) for value in non_null_values]
    valid_values = [parsed for parsed in parsed_values if parsed["is_valid"]]
    invalid_values = [parsed["raw_value"] for parsed in parsed_values if not parsed["is_valid"]]
    normalized_to_variants: dict[str, list[str]] = defaultdict(list)

    for parsed in valid_values:
        variants = normalized_to_variants[parsed["normalized_value"]]
        if parsed["raw_value"] not in variants:
            variants.append(parsed["raw_value"])

    collision_examples = [
        {"normalized_value": normalized_value, "raw_variants": variants}
        for normalized_value, variants in normalized_to_variants.items()
        if len(variants) > 1
    ]

    return {
        "profiling_level": "column",
        "default_country": default_country,
        "total_non_null_count": len(non_null_values),
        "valid_phone_count": len(valid_values),
        "invalid_phone_count": len(invalid_values),
        "valid_phone_percentage": _percentage(len(valid_values), len(non_null_values)),
        "country_code_present_percentage": _percentage(
            sum(1 for parsed in valid_values if parsed["country_code_present"]),
            len(valid_values),
        ),
        "extension_present_count": sum(1 for parsed in valid_values if parsed["extension_present"]),
        "raw_distinct_count": len(set(non_null_values)),
        "normalized_distinct_count": len(set(normalized_to_variants)),
        "normalization_collision_count": len(collision_examples),
        "collision_examples": collision_examples[:10],
        "invalid_examples": _unique_in_order(invalid_values)[:10],
    }


def _parse_phone(raw_value: str, default_country: str) -> dict[str, Any]:
    extension_present = EXTENSION_PATTERN.search(raw_value) is not None
    value_without_extension = EXTENSION_PATTERN.sub("", raw_value)
    country_code_present = value_without_extension.strip().startswith("+")
    digits = re.sub(r"\D+", "", value_without_extension)

    if default_country.upper() == "US":
        if len(digits) == 11 and digits.startswith("1"):
            normalized = f"+{digits}"
            return _parsed(raw_value, normalized, country_code_present=True, extension_present=extension_present)
        if len(digits) == 10:
            normalized = f"+1{digits}"
            return _parsed(
                raw_value,
                normalized,
                country_code_present=country_code_present,
                extension_present=extension_present,
            )

    return {
        "raw_value": raw_value,
        "normalized_value": None,
        "is_valid": False,
        "country_code_present": country_code_present,
        "extension_present": extension_present,
    }


def _parsed(
    raw_value: str,
    normalized_value: str,
    country_code_present: bool,
    extension_present: bool,
) -> dict[str, Any]:
    return {
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "is_valid": True,
        "country_code_present": country_code_present,
        "extension_present": extension_present,
    }


def _percentage(count: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(count / denominator, 4)


def _unique_in_order(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique

