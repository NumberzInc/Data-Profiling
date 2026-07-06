import pandas as pd

from db_profiler.config import ProfilingConfig
from db_profiler.features.phone_profile import profile_phone_numbers
from db_profiler.runner import build_profile


class StubYDataProfiler:
    version = "stub"

    def profile_dataframe(self, table_name: str, frame: pd.DataFrame) -> dict:
        return {"table": {"n": len(frame)}, "variables": {}, "alerts": []}


def test_profile_phone_numbers_reports_variations_and_collisions() -> None:
    values = pd.Series(
        [
            "415-555-2671",
            "+1 (415) 555-2671",
            "(212) 555-0100",
            "2125550100 ext 9",
            "not a phone",
            None,
        ],
        name="phone",
    )

    profile = profile_phone_numbers(values, default_country="US")

    assert profile["profiling_level"] == "column"
    assert profile["total_non_null_count"] == 5
    assert profile["valid_phone_count"] == 4
    assert profile["invalid_phone_count"] == 1
    assert profile["valid_phone_percentage"] == 0.8
    assert profile["country_code_present_percentage"] == 0.25
    assert profile["extension_present_count"] == 1
    assert profile["raw_distinct_count"] == 5
    assert profile["normalized_distinct_count"] == 2
    assert profile["normalization_collision_count"] == 2
    assert profile["collision_examples"] == [
        {
            "normalized_value": "+14155552671",
            "raw_variants": ["415-555-2671", "+1 (415) 555-2671"],
        },
        {
            "normalized_value": "+12125550100",
            "raw_variants": ["(212) 555-0100", "2125550100 ext 9"],
        },
    ]
    assert profile["invalid_examples"] == ["not a phone"]


def test_profile_phone_numbers_does_not_mutate_input_values() -> None:
    values = pd.Series(["415-555-2671"], name="phone")
    original = values.copy(deep=True)

    profile_phone_numbers(values, default_country="US")

    assert values.equals(original)


def test_build_profile_includes_phone_profiles_from_config() -> None:
    config = ProfilingConfig()
    config.phone_profile.columns = {"customers": ["phone"]}
    frame = pd.DataFrame({"phone": ["415-555-2671", "+1 (415) 555-2671"], "name": ["Ada", "Grace"]})

    document = build_profile(
        tables={"customers": frame},
        config=config,
        ydata_profiler=StubYDataProfiler(),
    )

    phone_profile = document["tables"]["customers"]["custom_profiles"]["phone_profile"]
    assert set(phone_profile) == {"phone"}
    assert phone_profile["phone"]["normalization_collision_count"] == 1
