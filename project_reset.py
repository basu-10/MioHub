"""Fresh-install helper: drop ALL tables in the configured database, then run init_db.

This script is intentionally destructive.

Notes:
- Uses config.get_database_uri() to connect.
- Designed for fresh installs / local dev. Do NOT run on a database you care about.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from flask import Flask
from sqlalchemy import inspect, text

# Set environment file to prod.env before importing config
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

import config


CONFIRMATION_FLAG = "--yes-delete-everything"


def _quote_mysql_identifier(identifier: str) -> str:
    """Quote a MySQL identifier using backticks.

    MySQL escapes backticks within identifiers by doubling them.
    """
    if identifier is None:
        raise TypeError("identifier cannot be None")
    return "`" + identifier.replace("`", "``") + "`"


def build_drop_table_statements(
    table_names: Sequence[str],
    *,
    chunk_size: int = 30,
) -> List[str]:
    """Build DROP TABLE statements in chunks.

    Chunking keeps statements to a reasonable size.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    quoted = [_quote_mysql_identifier(t) for t in table_names]
    statements: List[str] = []
    for start in range(0, len(quoted), chunk_size):
        chunk = quoted[start : start + chunk_size]
        if not chunk:
            continue
        statements.append(f"DROP TABLE IF EXISTS {', '.join(chunk)};")
    return statements


@dataclass(frozen=True)
class TableInfo:
    name: str
    engine: str | None
    table_rows_estimate: int | None
    data_length: int | None
    index_length: int | None


def _format_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.2f} {units[idx]}"


def _load_table_infos(engine, db_name: str) -> List[TableInfo]:
    """Fetch table metadata from information_schema for logging."""
    query = text(
        """
        SELECT
            table_name,
            engine,
            table_rows,
            data_length,
            index_length
        FROM information_schema.tables
        WHERE table_schema = :schema
        ORDER BY table_name
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(query, {"schema": db_name}).fetchall()
    infos: List[TableInfo] = []
    for r in rows:
        infos.append(
            TableInfo(
                name=str(r[0]),
                engine=(str(r[1]) if r[1] is not None else None),
                table_rows_estimate=(int(r[2]) if r[2] is not None else None),
                data_length=(int(r[3]) if r[3] is not None else None),
                index_length=(int(r[4]) if r[4] is not None else None),
            )
        )
    return infos


def _count_rows(engine, table_name: str) -> int:
    # Using text() with a quoted identifier is tricky; we quote manually.
    quoted = _quote_mysql_identifier(table_name)
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
        return int(row.scalar() or 0)


def _print_table_report(infos: Sequence[TableInfo]) -> None:
    if not infos:
        print("No tables found.")
        return

    print("\nTables found (from information_schema):")
    print("-" * 88)
    print(f"{'table':40} {'rows(est)':>10} {'data':>12} {'index':>12} {'engine':>10}")
    print("-" * 88)
    for info in infos:
        print(
            f"{info.name:40} "
            f"{(str(info.table_rows_estimate) if info.table_rows_estimate is not None else '?'):>10} "
            f"{_format_bytes(info.data_length):>12} "
            f"{_format_bytes(info.index_length):>12} "
            f"{(info.engine or '?'):>10}"
        )
    print("-" * 88)


def reset_database_and_reinit(*, count_rows: bool) -> None:
    """Drop all tables in the configured DB, then run init_db.init_app_and_tables()."""

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = config.get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Import the same db instance used by the app models.
    from blueprints.p2.models import db as shared_db

    shared_db.init_app(app)

    with app.app_context():
        inspector = inspect(shared_db.engine)
        table_names = inspector.get_table_names()

        print("\n=== Fresh Install: DATABASE RESET ===")
        print(f"Database: {config.DB_NAME}")
        print(f"Host:     {config.DB_HOST}:{config.DB_PORT}")
        print(f"User:     {config.DB_USER}")

        try:
            infos = _load_table_infos(shared_db.engine, config.DB_NAME)
        except Exception as exc:  # pragma: no cover (depends on DB privileges)
            print(f"Warning: could not read information_schema.tables ({exc}).")
            infos = [TableInfo(name=t, engine=None, table_rows_estimate=None, data_length=None, index_length=None) for t in table_names]

        _print_table_report(infos)

        if not table_names:
            print("\nNothing to drop. Running init_db...")
        else:
            if count_rows:
                print("\nCounting rows (this can be slow on large tables)...")
                for t in table_names:
                    try:
                        cnt = _count_rows(shared_db.engine, t)
                        print(f"- {t}: {cnt} rows")
                    except Exception as exc:
                        print(f"- {t}: row count failed ({exc})")

            print("\nDropping ALL tables...")
            with shared_db.engine.begin() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
                for stmt in build_drop_table_statements(table_names):
                    print(f"SQL> {stmt}")
                    conn.execute(text(stmt))
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))

            # Verify
            remaining = inspect(shared_db.engine).get_table_names()
            if remaining:
                raise RuntimeError(f"Some tables still exist after drop: {remaining}")
            print("\n✅ All tables dropped.")

        print("\nRe-initializing database via init_db.py...")
        import project_update

        project_update.init_app_and_tables()
        print("\n✅ Fresh install reset complete.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "DANGEROUS: Drops ALL tables in the configured database, then runs init_db. "
            "Requires explicit confirmation flag."
        )
    )
    parser.add_argument(
        "--yes-delete-everything",
        action="store_true",
        help="Required. Confirms you understand this will delete ALL tables/data.",
    )
    parser.add_argument(
        "--count-rows",
        action="store_true",
        help="Optional. Counts rows per table before dropping (can be slow).",
    )

    args = parser.parse_args(argv)

    if not args.yes_delete_everything:
        print("\nRefusing to run without confirmation.")
        print(f"Re-run with {CONFIRMATION_FLAG} to proceed.")
        return 2

    # Extra guard against accidentally wiping a local DB when user expected PA, etc.
    print("\n!!! DESTRUCTIVE OPERATION !!!")
    print("This will permanently delete ALL tables and ALL data in this database:")
    print(f"  {config.DB_USER}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
    print("If that is not correct, CTRL+C now and fix your config/env vars.")

    try:
        reset_database_and_reinit(count_rows=args.count_rows)
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
