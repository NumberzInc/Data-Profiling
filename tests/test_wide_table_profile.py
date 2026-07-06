from __future__ import annotations

import pandas as pd

from db_profiler.features.wide_table_profile import profile_wide_table


def _make_frame(num_columns: int) -> pd.DataFrame:
    return pd.DataFrame({f"col_{i}": [1, 2, 3] for i in range(num_columns)})


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


def test_output_has_required_keys() -> None:
    frame = _make_frame(10)

    profile = profile_wide_table(frame, wide_table_threshold=75)

    assert set(profile.keys()) == {
        "profiling_level",
        "column_count",
        "threshold",
        "exceeds_threshold",
        "columns_over_threshold",
    }


def test_profiling_level_is_table() -> None:
    profile = profile_wide_table(_make_frame(10), wide_table_threshold=75)

    assert profile["profiling_level"] == "table"


# ---------------------------------------------------------------------------
# Column count
# ---------------------------------------------------------------------------


def test_column_count_reflects_frame_width() -> None:
    profile = profile_wide_table(_make_frame(42), wide_table_threshold=75)

    assert profile["column_count"] == 42


def test_threshold_is_included_in_output() -> None:
    profile = profile_wide_table(_make_frame(10), wide_table_threshold=50)

    assert profile["threshold"] == 50


# ---------------------------------------------------------------------------
# Threshold logic
# ---------------------------------------------------------------------------


def test_table_under_threshold_does_not_exceed() -> None:
    profile = profile_wide_table(_make_frame(10), wide_table_threshold=75)

    assert profile["exceeds_threshold"] is False


def test_table_at_threshold_does_not_exceed() -> None:
    profile = profile_wide_table(_make_frame(75), wide_table_threshold=75)

    assert profile["exceeds_threshold"] is False


def test_table_one_over_threshold_exceeds() -> None:
    profile = profile_wide_table(_make_frame(76), wide_table_threshold=75)

    assert profile["exceeds_threshold"] is True


def test_table_well_over_threshold_exceeds() -> None:
    profile = profile_wide_table(_make_frame(120), wide_table_threshold=75)

    assert profile["exceeds_threshold"] is True


# ---------------------------------------------------------------------------
# Delta
# ---------------------------------------------------------------------------


def test_columns_over_threshold_is_zero_when_at_threshold() -> None:
    profile = profile_wide_table(_make_frame(75), wide_table_threshold=75)

    assert profile["columns_over_threshold"] == 0


def test_columns_over_threshold_is_positive_when_exceeded() -> None:
    profile = profile_wide_table(_make_frame(80), wide_table_threshold=75)

    assert profile["columns_over_threshold"] == 5


def test_columns_over_threshold_is_negative_when_under() -> None:
    profile = profile_wide_table(_make_frame(70), wide_table_threshold=75)

    assert profile["columns_over_threshold"] == -5


# ---------------------------------------------------------------------------
# Configurable threshold guardrail
# ---------------------------------------------------------------------------


def test_custom_threshold_changes_exceeds_result() -> None:
    frame = _make_frame(30)

    narrow_profile = profile_wide_table(frame, wide_table_threshold=20)
    wide_profile = profile_wide_table(frame, wide_table_threshold=50)

    assert narrow_profile["exceeds_threshold"] is True
    assert wide_profile["exceeds_threshold"] is False


def test_custom_threshold_changes_delta() -> None:
    frame = _make_frame(30)

    profile = profile_wide_table(frame, wide_table_threshold=20)

    assert profile["columns_over_threshold"] == 10


# ---------------------------------------------------------------------------
# Guardrail: does not mutate input
# ---------------------------------------------------------------------------


def test_does_not_mutate_input_frame() -> None:
    frame = _make_frame(10)
    original = frame.copy(deep=True)

    profile_wide_table(frame, wide_table_threshold=75)

    assert frame.equals(original)
