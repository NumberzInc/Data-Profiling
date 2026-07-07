import json
from pathlib import Path

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
    monkeypatch.setattr(cli, "build_profile", lambda tables, config: {
        "metadata": {
            "sampling": {"sample_rows": config.sampling.sample_rows},
            "table_names": sorted(tables),
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
