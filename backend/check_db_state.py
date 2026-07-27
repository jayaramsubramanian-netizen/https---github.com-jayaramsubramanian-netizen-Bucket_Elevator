"""
backend/check_db_state.py -- report what actually exists in vectrix.db.
═══════════════════════════════════════════════════════════════════════════
A standing verification tool, not a one-off. Run it after any migration to see
which tables exist, how populated they are, and what is still missing.

Written as a FILE rather than a python -c one-liner because PowerShell mangles
nested quotes in -c strings.

    python check_db_state.py
    python check_db_state.py --db vectrix_backup_20260723.db
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

# group -> [(table, created_by, expected_rows_note)]
EXPECTED = {
    "Material database (7-table foundation)": [
        ("materials_v2",                "build_material_db.py", "empty until seeded"),
        ("material_core",               "build_material_db.py", "empty until seeded"),
        ("material_particles",          "build_material_db.py", "empty until seeded"),
        ("material_handling",           "build_material_db.py", "empty until seeded"),
        ("material_hazards",            "build_material_db.py", "empty until seeded"),
        ("material_model_coefficients", "build_material_db.py", "STAYS EMPTY in Phase 1"),
        ("material_sources",            "build_material_db.py", "empty until seeded"),
    ],
    "Engineering limits": [
        ("engineering_limits",          "create_engineering_limits_table.py", "13 seeded"),
    ],
    "Duty classification": [
        ("duty_classes",                "create_duty_classification.py", "5 seeded"),
        ("duty_class_rules",            "create_duty_classification.py", "13 seeded"),
    ],
    "Component catalogs": [
        ("bearing_family_capability",   "create_component_catalogs.py", "5 seeded"),
        ("housing_catalog",             "create_component_catalogs.py", "EMPTY — needs SKF data"),
        ("seal_catalog",                "create_component_catalogs.py", "EMPTY — needs SKF data"),
        ("adapter_catalog",             "create_component_catalogs.py", "EMPTY — needs SKF data"),
        ("environment_profile",         "create_component_catalogs.py", "6 seeded"),
        ("application_preference",      "create_component_catalogs.py", "6 seeded"),
    ],
    "Existing catalogs (pre-existing)": [
        ("buckets",                     "-", "40 seeded"),
        ("bearings",                    "-", "168"),
        ("materials",                   "-", "old table, retired at cutover"),
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    args = ap.parse_args()
    if not os.path.isfile(args.db):
        sys.exit(f"database not found: {args.db}")

    con = sqlite3.connect(args.db)
    try:
        present = {r[1]: r for r in con.execute("PRAGMA table_list")}
        size_mb = os.path.getsize(args.db) / 1e6
        print(f"{os.path.basename(args.db)}  ({size_mb:.1f} MB)\n")

        missing_scripts = set()
        for group, tables in EXPECTED.items():
            print(f"{group}")
            for name, script, note in tables:
                if name not in present:
                    print(f"  MISSING  {name:30s}  <- run {script}")
                    if script != "-":
                        missing_scripts.add(script)
                    continue
                rows = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                cols = len(con.execute(f"PRAGMA table_info({name})").fetchall())
                strict = present[name][5] if len(present[name]) > 5 else 0
                flag = "STRICT" if strict else "      "
                print(f"  ok       {name:30s} {rows:>6d} rows {cols:>3d} cols {flag}  {note}")
            print()

        # bucket X-X invariant, the open data question
        if "buckets" in present:
            cols = {r[1] for r in con.execute("PRAGMA table_info(buckets)")}
            if "water_level_V_L" in cols:
                bad = con.execute(
                    "SELECT bucket_id, water_level_V_L, V_L FROM buckets "
                    "WHERE water_level_V_L IS NOT NULL AND water_level_V_L >= V_L"
                ).fetchall()
                n_ok = con.execute(
                    "SELECT COUNT(*) FROM buckets WHERE water_level_V_L IS NOT NULL "
                    "AND water_level_V_L < V_L").fetchone()[0]
                print(f"bucket X-X invariant: {n_ok} pass, {len(bad)} violate")
                for bid, xx, yy in bad:
                    print(f"  !! {bid:10s} X-X {xx} >= Y-Y {yy}  (mixed basis — see C-series finding)")
                print()

        if missing_scripts:
            print("STILL TO RUN:")
            for s in sorted(missing_scripts):
                print(f"  python {s}")
        else:
            print("All expected tables present.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())