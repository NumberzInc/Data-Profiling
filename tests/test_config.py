from pathlib import Path

import pytest

from db_profiler.config import load_config


def test_load_config_uses_defaults_without_file() -> None:
    config = load_config(None)

    assert config.database.schema == "public"
    assert config.sampling.mode == "sampled"
    assert config.sampling.sample_rows == 50_000
    assert config.thresholds.wide_table_columns == 75
    assert config.history.path == "state/profile_history.jsonl"


def test_load_config_overrides_known_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "profiling.yml"
    config_path.write_text(
        "\n".join(
            [
                "database:",
                "  schema: analytics",
                "sampling:",
                "  sample_rows: 25",
                "thresholds:",
                "  wide_table_columns: 40",
                "history:",
                "  path: state/test.jsonl",
                "ydata:",
                "  enabled: false",
                "  include_raw: true",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.database.schema == "analytics"
    assert config.sampling.sample_rows == 25
    assert config.thresholds.wide_table_columns == 40
    assert config.history.path == "state/test.jsonl"
    assert config.ydata.enabled is False
    assert config.ydata.include_raw is True


def test_load_config_rejects_unknown_options(tmp_path: Path) -> None:
    config_path = tmp_path / "profiling.yml"
    config_path.write_text("sampling:\n  surprise: true\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown config option"):
        load_config(config_path)
