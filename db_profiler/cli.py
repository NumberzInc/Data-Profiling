from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .config import load_config
from .features.growth_freshness_profile import append_profile_history
from .loaders import load_csv_tables
from .output import write_profile_json
from .runner import build_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="db-profiler",
        description="Profile database-shaped data and emit a JSON health report.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile = subparsers.add_parser("profile", help="Build a profiling JSON report.")
    profile.add_argument("--database-url", help="SQLAlchemy database URL for a future live database run.")
    profile.add_argument("--schema", default=None, help="Database schema to profile.")
    profile.add_argument("--config", type=Path, default=None, help="Optional YAML profiling config.")
    profile.add_argument("--output", type=Path, required=True, help="Path for the generated JSON report.")
    profile.add_argument("--history", type=Path, default=None, help="Path to append run history in later milestones.")
    profile.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Maximum rows to profile per table. Overrides config sampling.sample_rows.",
    )
    profile.add_argument(
        "--wide-table-threshold",
        type=int,
        default=None,
        help="Column-count threshold reserved for the wide-table feature branch.",
    )
    profile.add_argument(
        "--table-csv",
        action="append",
        default=[],
        metavar="TABLE=PATH",
        help="Fixture CSV table input. May be provided multiple times for local tests.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "profile":
        config = load_config(args.config)
        if args.schema:
            config.database.schema = args.schema
        if args.database_url:
            config.database.url = args.database_url
        if args.history:
            config.history.path = str(args.history)
        if args.sample_rows is not None:
            config.sampling.sample_rows = args.sample_rows
        if args.wide_table_threshold is not None:
            config.thresholds.wide_table_columns = args.wide_table_threshold

        if not args.table_csv:
            parser.error("At least one --table-csv TABLE=PATH fixture input is required in this scaffold milestone.")

        tables = load_csv_tables(args.table_csv, sample_rows=config.sampling.sample_rows)
        profile = build_profile(tables=tables, config=config)
        write_profile_json(profile, args.output)
        append_profile_history(profile, Path(config.history.path) if config.history.path else None)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
