"""
backend/create_chains_table.py -- one-off migration: create the `chains` table
and seed it FROM THE EXISTING CHAIN_SERIES CONSTANT.
═══════════════════════════════════════════════════════════════════════════
WHY THIS IS NEEDED
──────────────────
Chains are the worst source-of-truth split in the codebase. A chain is currently
defined in THREE places:

    backend/calculations.py     CHAIN_SERIES     <- what the SOLVER reads
    frontend InputSidebar.jsx   CHAIN_OPTIONS    <- hardcoded again
    desktop-poc                 CHAIN_OPTIONS    <- hardcoded a third time

...and there is NO DATABASE TABLE AT ALL. Unlike buckets (DB complete, solver
ignored it) and motors (table exists but Pkw is NULL at source), chains have
never had a table. seed_all.py's TABLE_SPECS has no `chains` entry;
export_vectrix_db.py's TABLES has no `chains` entry; there is no
/components/chains endpoint.

So a chain cannot be added, edited, or even LISTED through the Components
Library. Adding a chain today means editing three source files in two languages.

WHERE THE DATA COMES FROM
─────────────────────────
This script imports CHAIN_SERIES from calculations.py and writes exactly those
nine rows. NOTHING IS INVENTED -- not a pitch, not a working load, not a speed
limit. The source of truth simply moves from a Python literal into the table,
byte for byte, and verify_chains.py then proves the round-trip.

If the constant is wrong today, it will be wrong in the DB too -- migration is
not validation. Fixing chain data (if it needs fixing) is a separate,
CEMA-checked exercise.

SCHEMA NOTE
───────────
`series` is a LIST in the constant (e.g. ["100","200","700","800"] -- the CEMA
elevator series a chain is used in). SQLite has no array type, so it is stored as
JSON TEXT, exactly as `recommended_materials` is on the buckets table. catalog.py
parses it back to a list on read, so the solver sees the identical shape.

USAGE (from backend/):
    python create_chains_table.py            # create + seed
    python create_chains_table.py --dry-run  # show what would be written
    python create_chains_table.py --force    # DROP and recreate (destroys custom rows)

Idempotent: re-running upserts by chain_id and will not duplicate rows.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

_DB_PATH = os.environ.get(
    "VECTRIX_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectrix.db"),
)

# Mirrors the buckets table's conventions: a `custom` flag so user-created chains
# are distinguishable from the seeded catalogue, and JSON TEXT for the list field.
DDL = """
CREATE TABLE IF NOT EXISTS chains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id    TEXT    NOT NULL UNIQUE,   -- "N102B"  (the constant's "id")
    name        TEXT,                      -- "N-102B  (4\" std, single)"
    pitch_mm    REAL,                      -- chain pitch [mm]
    WL_kg       REAL,                      -- published working load per strand [kg]
    wt_kg_m     REAL,                      -- chain weight per strand per metre [kg/m]
    v_max_ms    REAL,                      -- CEMA rated max chain speed [m/s]
    n_strands   INTEGER,                   -- 1 = single, 2 = double (SC only)
    series      TEXT,                      -- JSON list: CEMA elevator series
    note        TEXT,
    custom      INTEGER NOT NULL DEFAULT 0
);
"""

COLUMNS = ["chain_id", "name", "pitch_mm", "WL_kg", "wt_kg_m",
           "v_max_ms", "n_strands", "series", "note", "custom"]


def rows_from_constant():
    """Read the nine chains straight out of calculations.py. No transcription."""
    try:
        from calculations import CHAIN_SERIES
    except Exception as e:
        sys.exit(f"Could not import CHAIN_SERIES from calculations.py: {e}")
    out = []
    for c in CHAIN_SERIES:
        out.append({
            "chain_id":  c["id"],
            "name":      c.get("name"),
            "pitch_mm":  c.get("pitch_mm"),
            "WL_kg":     c.get("WL_kg"),
            "wt_kg_m":   c.get("wt_kg_m"),
            "v_max_ms":  c.get("v_max_ms"),
            "n_strands": c.get("n_strands"),
            "series":    json.dumps(c.get("series") or []),
            "note":      c.get("note"),
            "custom":    0,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="DROP the table first. Destroys any custom chains.")
    args = ap.parse_args()

    rows = rows_from_constant()
    print(f"CHAIN_SERIES -> {len(rows)} chains to write\n")
    for r in rows:
        print(f"  {r['chain_id']:8s} pitch={r['pitch_mm']:>6} mm  "
              f"WL={r['WL_kg']:>7} kg  wt={r['wt_kg_m']:>5} kg/m  "
              f"v_max={r['v_max_ms']:>5} m/s  strands={r['n_strands']}  "
              f"series={json.loads(r['series'])}")

    if args.dry_run:
        print("\nDRY RUN -- nothing written.")
        return 0

    con = sqlite3.connect(args.db)
    try:
        if args.force:
            con.execute("DROP TABLE IF EXISTS chains")
            print("\nDropped existing `chains` table (--force).")
        con.executescript(DDL)

        placeholders = ", ".join("?" for _ in COLUMNS)
        updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "chain_id")
        sql = (
            f"INSERT INTO chains ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(chain_id) DO UPDATE SET {updates}"
        )
        for r in rows:
            con.execute(sql, [r[c] for c in COLUMNS])
        con.commit()

        n = con.execute("SELECT COUNT(*) FROM chains").fetchone()[0]
        n_custom = con.execute("SELECT COUNT(*) FROM chains WHERE custom=1").fetchone()[0]
        print(f"\n`chains` table now holds {n} rows ({n_custom} custom).")
        print("Next: run verify_chains.py to prove the round-trip before switching")
        print("calculations.py over to `from catalog import CHAIN_SERIES`.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())