"""
VECTRIX™ — Export vectrix.db to CSV + JSON
─────────────────────────────────────────────────────────────────────────────
Run this script from your /backend folder:

    python export_vectrix_db.py

Produces (in the same folder):
    vectrix_export/
        materials.csv
        buckets.csv
        bearings.csv
        motors.csv
        gearboxes.csv
        drives.csv
        belts.csv
        screws.csv
        bolts.csv
        cost_items.csv
        custom_materials.csv
        material_grades.csv
        vectrix_db_export.json   ← all tables combined, for the seed script

Why both formats:
  - CSV: easy to open in Excel, inspect or edit the 440-material list,
         share a single sheet without anything else.
  - JSON: machine-readable for the seed script that will replace seed_catalog.py;
          same structure as the tables so the import is a straight loop,
          same pattern as the existing seed_buckets() / seed_material_grades().

Safe to re-run — always overwrites, never appends. Skips tables with 0 rows
but lists them so you know what's empty.

JSON field handling:
  - SQLite JSON-column values (hazard_codes, flags, recommended_materials,
    component_types, features) are stored as TEXT in SQLite — this script
    parses them back to real Python lists/dicts before writing JSON, so the
    output file is clean JSON throughout, not a string-within-JSON mess.
  - NULL values are written as JSON null (not the string "None").
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

# ── Configuration ────────────────────────────────────────────────────────────

DB_FILE = "vectrix.db"           # relative to the /backend folder
OUT_DIR = "vectrix_export"       # created next to the script

# Tables to export, in a sensible order for the seed script to consume.
# calc_audit / calc_log / design_versions / designs / sqlite_sequence are
# operational/logging tables — excluded deliberately (not catalog data).
TABLES = [
    "materials",
    "buckets",
    "bearings",
    "motors",
    "gearboxes",
    "drives",
    "belts",
    "screws",
    "bolts",
    "cost_items",
    "custom_materials",
    "material_grades",
]

# Columns that contain JSON stored as TEXT in SQLite.
# These get parsed back to real Python objects in the output.
JSON_COLUMNS: dict[str, list[str]] = {
    "materials":       ["hazard_codes", "flags"],
    "buckets":         ["recommended_materials", "punch"],
    "drives":          ["features"],
    "material_grades": ["component_types"],
    "custom_materials":["hazard_codes"],
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_json_field(value: Any) -> Any:
    """Safely parse a TEXT-stored JSON column back to a Python object."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value          # already parsed (shouldn't happen with sqlite3)
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value          # leave as-is if it wasn't valid JSON


def rows_for_table(con: sqlite3.Connection, table: str) -> tuple[list[str], list[dict]]:
    """Return (column_names, list_of_row_dicts) for a table."""
    json_cols = set(JSON_COLUMNS.get(table, []))
    cur = con.execute(f"SELECT * FROM {table} ORDER BY id ASC")
    cols = [d[0] for d in cur.description]
    rows = []
    for raw in cur.fetchall():
        row: dict[str, Any] = {}
        for col, val in zip(cols, raw):
            if col in json_cols:
                val = _parse_json_field(val)
            row[col] = val
        rows.append(row)
    return cols, rows


def write_csv(out_path: Path, cols: list[str], rows: list[dict]) -> None:
    """Write rows to a CSV file.

    JSON-typed columns (lists/dicts) are serialised back to compact JSON
    strings in CSV since Excel can't natively display a Python list — they
    round-trip cleanly back through the seed script.
    """
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            flat: dict[str, Any] = {}
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    flat[k] = json.dumps(v, ensure_ascii=False)
                elif v is None:
                    flat[k] = ""       # blank cell, not the string "None"
                else:
                    flat[k] = v
            writer.writerow(flat)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    db_path = Path(DB_FILE)
    if not db_path.exists():
        print(f"ERROR: {db_path.resolve()} not found.")
        print("Run this script from your /backend folder, next to vectrix.db")
        sys.exit(1)

    out = Path(OUT_DIR)
    out.mkdir(exist_ok=True)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    all_data: dict[str, list[dict]] = {}
    summary: list[str] = []

    for table in TABLES:
        try:
            cols, rows = rows_for_table(con, table)
        except sqlite3.OperationalError as e:
            summary.append(f"  SKIP  {table:20s}  (table missing: {e})")
            continue

        n = len(rows)
        if n == 0:
            summary.append(f"  EMPTY {table:20s}  — 0 rows, CSV written (headers only)")
        else:
            summary.append(f"  OK    {table:20s}  — {n:4d} rows")

        # Always write the CSV (even empty — headers are useful as a template)
        write_csv(out / f"{table}.csv", cols, rows)
        all_data[table] = rows

    # Combined JSON
    json_path = out / "vectrix_db_export.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)

    con.close()

    print(f"\nVECTRIX™ DB export — {db_path.resolve()}")
    print("─" * 60)
    for line in summary:
        print(line)
    print("─" * 60)
    total = sum(len(r) for r in all_data.values())
    print(f"  Total rows exported: {total}")
    print(f"  Output folder:       {out.resolve()}/")
    print(f"  Combined JSON:       {json_path.name}")
    print()
    print("Next step: share vectrix_export/vectrix_db_export.json or")
    print("the individual CSVs. I'll write a seed_all.py from that data.")


if __name__ == "__main__":
    main()