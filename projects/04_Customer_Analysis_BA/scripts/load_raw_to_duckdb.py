#!/usr/bin/env python3
"""Load parquet raw tables into DuckDB as the `raw` schema views."""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "warehouse.duckdb"


def main():
    files = sorted(RAW.glob("*.parquet"))
    if not files:
        raise SystemExit(f"no parquet files in {RAW}; run scripts/generate_mock_data.py first")
    con = duckdb.connect(str(DB))
    con.execute("create schema if not exists raw")
    for f in files:
        con.execute(
            f"create or replace view raw.{f.stem} as select * from read_parquet('{f.as_posix()}')"
        )
    rows = con.execute(
        "select table_name from information_schema.tables where table_schema='raw' order by 1"
    ).fetchall()
    print(f"[duckdb] {DB.name}: loaded {len(rows)} raw views")
    for (name,) in rows:
        cnt = con.execute(f"select count(*) from raw.{name}").fetchone()[0]
        print(f"  raw.{name:<28} {cnt:>9,} rows")
    con.close()


if __name__ == "__main__":
    main()
