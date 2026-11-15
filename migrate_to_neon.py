"""
One-time SQLite -> Neon PostgreSQL migration for RNV STORES.

Run from the project folder after setting DATABASE_URL and RNV_SECRET_KEY.
The Neon database must be empty. This script refuses to overwrite existing rows.
"""
import os
from pathlib import Path

os.environ["RNV_SKIP_DB_INIT"] = "1"

from sqlalchemy import create_engine, MetaData, Table, select, func, text
from app_postgres import app, db

SQLITE_FILE = Path(__file__).resolve().parent / "rnv_stores.db"
TABLE_ORDER = ["user", "product", "sale", "sale_item"]

if not SQLITE_FILE.exists():
    raise SystemExit(f"SQLite database not found: {SQLITE_FILE}")

source_engine = create_engine(f"sqlite:///{SQLITE_FILE.as_posix()}")
source_metadata = MetaData()
source_metadata.reflect(bind=source_engine)

with app.app_context():
    target_engine = db.engine
    # Create tables from the application's current SQLAlchemy models.
    db.metadata.create_all(bind=target_engine)

    # Refuse to merge into a database that already has data.
    for table_name in TABLE_ORDER:
        target_table = db.metadata.tables[table_name]
        existing = target_engine.connect().execute(
            select(func.count()).select_from(target_table)
        ).scalar_one()
        if existing:
            raise SystemExit(
                f"STOP: Neon table '{table_name}' already contains {existing} row(s). "
                "No data was copied. Do not rerun or clear the database."
            )

    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        for table_name in TABLE_ORDER:
            if table_name not in source_metadata.tables:
                raise SystemExit(f"SQLite is missing expected table: {table_name}")
            source_table = source_metadata.tables[table_name]
            target_table = db.metadata.tables[table_name]
            rows = source_conn.execute(select(source_table)).mappings().all()
            if rows:
                target_conn.execute(target_table.insert(), [dict(row) for row in rows])
            print(f"{table_name}: copied {len(rows)} row(s)")

        # Align PostgreSQL auto-increment sequences with the imported IDs.
        for table_name in TABLE_ORDER:
            # Quote identifiers because the table name "user" is a PostgreSQL keyword.
            quoted_table = f'"{table_name}"'
            sequence_table_name = f'"{table_name}"'
            target_conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{sequence_table_name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {quoted_table}), 1), "
                f"(SELECT MAX(id) IS NOT NULL FROM {quoted_table}))"
            ))

    print("\nMigration completed. Verify the row counts in Neon before deploying.")
