import pandas as pd

from db_profiler.config import ProfilingConfig
from db_profiler.features.semantic_alias_profile import profile_semantic_aliases
from db_profiler.runner import build_profile


class StubYDataProfiler:
    version = "stub"

    def profile_dataframe(self, table_name: str, frame: pd.DataFrame) -> dict:
        return {"table": {"n": len(frame)}, "variables": {}, "alerts": []}


def test_profile_semantic_aliases_groups_configured_variants() -> None:
    values = pd.Series(["California", "CA", "Calif.", "New York", "NY", "Cali", None], name="state")
    aliases = {
        "CA": ["California", "Calif.", "ca"],
        "NY": ["New York", "N.Y."],
    }

    profile = profile_semantic_aliases(values, aliases)

    assert profile["profiling_level"] == "column"
    assert profile["raw_distinct_count"] == 6
    assert profile["canonical_distinct_count"] == 3
    assert profile["variation_group_count"] == 2
    assert profile["variation_groups"] == [
        {"canonical_value": "CA", "raw_variants": ["California", "CA", "Calif."], "count": 3},
        {"canonical_value": "NY", "raw_variants": ["New York", "NY"], "count": 2},
    ]
    assert profile["unmapped_values"] == ["Cali"]
    assert profile["mapped_value_percentage"] == 0.8333


def test_profile_semantic_aliases_does_not_mutate_input_values() -> None:
    values = pd.Series(["California", "CA"], name="state")
    original = values.copy(deep=True)

    profile_semantic_aliases(values, {"CA": ["California"]})

    assert values.equals(original)


def test_build_profile_includes_semantic_alias_profiles_from_config() -> None:
    config = ProfilingConfig()
    config.semantic_aliases.aliases = {
        "customers.state": {
            "CA": ["California", "Calif."],
        }
    }
    frame = pd.DataFrame({"state": ["California", "CA", "Cali"]})

    document = build_profile(
        tables={"customers": frame},
        config=config,
        ydata_profiler=StubYDataProfiler(),
    )

    profile = document["tables"]["customers"]["custom_profiles"]["semantic_alias_profile"]["state"]
    assert profile["canonical_distinct_count"] == 2
    assert profile["unmapped_values"] == ["Cali"]
