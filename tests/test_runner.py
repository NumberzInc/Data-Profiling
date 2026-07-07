import pandas as pd

from db_profiler.config import ProfilingConfig
from db_profiler.runner import build_profile


class StubYDataProfiler:
    version = "stub"

    def profile_dataframe(self, table_name: str, frame: pd.DataFrame) -> dict:
        return {
            "table": {"n": len(frame), "n_var": len(frame.columns)},
            "variables": {column: {"type": str(frame[column].dtype)} for column in frame.columns},
            "alerts": [],
        }


def test_build_profile_returns_stable_json_contract_for_tables() -> None:
    frame = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "name": ["Ada", "Grace", "Katherine"],
        }
    )

    document = build_profile(
        tables={"customers": frame},
        config=ProfilingConfig(),
        ydata_profiler=StubYDataProfiler(),
    )

    assert set(document) == {
        "metadata",
        "tables",
        "relationships",
        "database_health",
        "query_generation_hints",
    }
    assert document["metadata"]["sampling"]["mode"] == "sampled"
    assert document["metadata"]["tool_versions"]["ydata_profiling"] == "stub"
    assert document["tables"]["customers"]["row_count"] == 3
    assert document["tables"]["customers"]["sample_count"] == 3
    assert document["tables"]["customers"]["column_count"] == 2
    assert document["tables"]["customers"]["columns"]["name"]["dtype"] == "object"
    assert document["tables"]["customers"]["ydata_profile"]["table"]["n"] == 3


def test_build_profile_uses_source_row_count_metadata_for_sampled_tables() -> None:
    frame = pd.DataFrame({"customer_id": [1, 2]})

    document = build_profile(
        tables={"customers": frame},
        config=ProfilingConfig(),
        ydata_profiler=StubYDataProfiler(),
        table_load_metadata={
            "customers": {
                "source": "postgres",
                "source_row_count": 250000,
                "sample_count": 2,
                "sample_row_limit": 50000,
                "load_duration_seconds": 0.1234,
            }
        },
    )

    assert document["tables"]["customers"]["row_count"] == 250000
    assert document["tables"]["customers"]["source_row_count"] == 250000
    assert document["tables"]["customers"]["sample_count"] == 2
    assert document["tables"]["customers"]["sample_row_limit"] == 50000
    assert document["tables"]["customers"]["load_metadata"]["source"] == "postgres"
    assert "profile_duration_seconds" in document["tables"]["customers"]
    assert "total_profile_duration_seconds" in document["metadata"]["performance"]
