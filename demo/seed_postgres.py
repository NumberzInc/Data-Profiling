from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the local Postgres demo database.")
    parser.add_argument("--database-url", required=True, help="SQLAlchemy Postgres URL.")
    parser.add_argument(
        "--sql",
        type=Path,
        default=Path(__file__).with_name("postgres_seed.sql"),
        help="Seed SQL file to execute.",
    )
    args = parser.parse_args()

    sql = args.sql.read_text(encoding="utf-8")
    engine = create_engine(args.database_url)
    with engine.begin() as connection:
        for statement in _split_sql(sql):
            connection.execute(text(statement))
    return 0


def _split_sql(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


if __name__ == "__main__":
    raise SystemExit(main())

