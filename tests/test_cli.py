import json
from pathlib import Path

import pandas as pd

import db_profiler.cli as cli


class StubYDataProfiler:
    version = "stub"

    def profile_dataframe(self, table_name, frame):
        return {
            "table": {"n": len(frame), "n_var": len(frame.columns)},
            "variables": {},
            "alerts": [],
        }


def test_profile_command_writes_json_from_csv_fixture(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "build_profile", lambda tables, config, table_load_metadata=None: {
        "metadata": {
            "sampling": {"sample_rows": config.sampling.sample_rows},
            "table_names": sorted(tables),
            "table_load_metadata": table_load_metadata or {},
        },
        "tables": {
            table_name: {"row_count": len(frame)}
            for table_name, frame in tables.items()
        },
        "relationships": {"declared": [], "inferred_candidates": [], "normalized_join_candidates": []},
        "database_health": {"warnings": [], "unavailable_checks": []},
        "query_generation_hints": {"join_graph": [], "do_not_auto_join": []},
    })
    output_path = tmp_path / "profile.json"
    history_path = tmp_path / "profile_history.jsonl"
    fixture_path = Path("tests/fixtures/customers.csv")

    exit_code = cli.main(
        [
            "profile",
            "--table-csv",
            f"customers={fixture_path}",
            "--sample-rows",
            "2",
            "--output",
            str(output_path),
            "--history",
            str(history_path),
        ]
    )

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert loaded["metadata"]["sampling"]["sample_rows"] == 2
    assert loaded["metadata"]["table_names"] == ["customers"]
    assert loaded["tables"]["customers"]["row_count"] == 2
    assert history_path.exists()


def test_profile_command_loads_from_database_url_when_no_csv(monkeypatch, tmp_path: Path) -> None:
    def fake_load_postgres_tables(database_url, schema, sample_rows, include_tables):
        assert database_url == "postgresql+psycopg://user:pass@localhost:5432/demo"
        assert schema == "analytics"
        assert sample_rows == 10
        assert include_tables == ["customers"]
        return (
            {"customers": pd.DataFrame({"id": [1, 2]})},
            {"customers": {"source": "postgres", "source_row_count": 100000, "sample_count": 2}},
        )

    monkeypatch.setattr(cli, "load_postgres_tables", fake_load_postgres_tables)
    monkeypatch.setattr(cli, "build_profile", lambda tables, config, table_load_metadata=None: {
        "metadata": {"table_load_metadata": table_load_metadata},
        "tables": {"customers": {"row_count": len(tables["customers"])}},
        "relationships": {"declared": [], "inferred_candidates": [], "normalized_join_candidates": []},
        "database_health": {"warnings": [], "unavailable_checks": []},
        "query_generation_hints": {"join_graph": [], "do_not_auto_join": []},
    })
    config_path = tmp_path / "profiling.yml"
    config_path.write_text(
        "\n".join(
            [
                "database:",
                "  schema: analytics",
                "  include_tables:",
                "    - customers",
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "profile.json"

    exit_code = cli.main(
        [
            "profile",
            "--database-url",
            "postgresql+psycopg://user:pass@localhost:5432/demo",
            "--sample-rows",
            "10",
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ]
    )

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert loaded["metadata"]["table_load_metadata"]["customers"]["source_row_count"] == 100000
