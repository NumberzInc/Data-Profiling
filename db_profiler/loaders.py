from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


def load_csv_tables(table_specs: list[str], sample_rows: int | None = None) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for spec in table_specs:
        table_name, csv_path = _parse_table_spec(spec)
        frame = pd.read_csv(csv_path)
        if sample_rows is not None:
            frame = frame.head(sample_rows)
        tables[table_name] = frame
    return tables


def _parse_table_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError(f"Expected TABLE=PATH for --table-csv, got: {spec}")

    table_name, path_text = spec.split("=", 1)
    table_name = table_name.strip()
    if not table_name:
        raise ValueError(f"Table name is required for --table-csv, got: {spec}")

    path = Path(path_text).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"CSV fixture does not exist: {path}")
    return table_name, path


def load_postgres_tables(
    database_url: str,
    schema: str,
    sample_rows: int,
    include_tables: list[str] | None = None,
    engine_factory: Callable[[str], Engine] = create_engine,
    inspector_factory: Callable[[Engine], Any] = inspect,
    read_sql_query: Callable[..., pd.DataFrame] = pd.read_sql_query,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
    engine = engine_factory(database_url)
    table_names = include_tables or inspector_factory(engine).get_table_names(schema=schema)
    tables: dict[str, pd.DataFrame] = {}
    metadata: dict[str, dict[str, Any]] = {}

    with engine.connect() as connection:
        for table_name in table_names:
            started_at = perf_counter()
            qualified_table = _qualified_table_name(engine, schema, table_name)
            source_row_count = int(connection.execute(text(f"SELECT COUNT(*) FROM {qualified_table}")).scalar_one())
            frame = read_sql_query(
                text(f"SELECT * FROM {qualified_table} LIMIT :sample_rows"),
                connection,
                params={"sample_rows": sample_rows},
            )
            tables[table_name] = frame
            metadata[table_name] = {
                "source": "postgres",
                "source_row_count": source_row_count,
                "sample_count": int(len(frame)),
                "sample_row_limit": sample_rows,
                "load_duration_seconds": round(perf_counter() - started_at, 4),
            }

    return tables, metadata


def _qualified_table_name(engine: Engine, schema: str, table_name: str) -> str:
    preparer = engine.dialect.identifier_preparer
    return f"{preparer.quote_schema(schema)}.{preparer.quote(table_name)}"
