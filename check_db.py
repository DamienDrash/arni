#!/usr/bin/env python3
"""Check database state and billing V2 tables."""
import os
import sqlalchemy

db_name = os.environ.get("POSTGRES_DB", "ariia_staging")
db_pass = os.environ.get("POSTGRES_PASSWORD", "ariia_dev_password")
db_url = f"postgresql+psycopg://postgres:{db_pass}@postgres:5432/{db_name}"

engine = sqlalchemy.create_engine(db_url)
with engine.connect() as conn:
    # Check alembic_version
    print("=== alembic_version ===")
    try:
        result = conn.execute(sqlalchemy.text("SELECT * FROM alembic_version"))
        rows = result.fetchall()
        print(f"Rows: {len(rows)}")
        for r in rows:
            print(f"  {r}")
    except Exception as e:
        print(f"Error: {e}")

    # Check billing V2 tables
    print("\n=== Billing V2 Tables ===")
    result = conn.execute(sqlalchemy.text(
        "SELECT tablename FROM pg_tables WHERE tablename LIKE 'billing_%' ORDER BY tablename"
    ))
    tables = result.fetchall()
    print(f"Found: {len(tables)}")
    for t in tables:
        print(f"  {t[0]}")

    # Check all tables
    print("\n=== All Tables ===")
    result = conn.execute(sqlalchemy.text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ))
    for t in result.fetchall():
        print(f"  {t[0]}")
