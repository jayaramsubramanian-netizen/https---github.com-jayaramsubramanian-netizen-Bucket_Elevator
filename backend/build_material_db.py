"""
backend/build_material_db.py -- build the complete 7-table material database.
═══════════════════════════════════════════════════════════════════════════
Runs every CREATE script in dependency order with one command. Idempotent: each
script uses CREATE TABLE IF NOT EXISTS, so re-running is safe and will not drop
or alter existing data.

THE SEVEN FOUNDATION TABLES (frozen architecture)
──────────────────────────────────────────────────
  materials_v2                 L1     identity & classification
  material_core                L2     intrinsic physical + flow properties
  material_particles           L2.5   particle characterization (PSD/shape/DEM)
  material_handling            L2.75  CEMA 550 handling descriptors
  material_hazards             L2B    safety / regulatory / compliance
  material_model_coefficients  L3     model calibration (VERSIONED, 1-to-many)
  material_sources             --     provenance / engineering config management

No further FOUNDATIONAL material tables after these seven. Equipment-specific
data lives in its own modules referencing material_id.

THE STORAGE RULE (for every future field, ask in order):
  1. Identity / classification?                  -> materials_v2
  2. Intrinsic -- true for 1 kg sent to ANY machine?
                                                 -> core / particles / handling
  3. A coefficient tuning a VECTRIX model?       -> material_model_coefficients
  4. Computed from machine geometry, conditions, or the solver?
                                                 -> NOT STORED (solver output)

PHASE 1 POPULATION RULE:
  materials_v2 / core / particles(TierA) / handling / hazards  -> populate from
      CEMA 550 and other documented sources, writing a provenance row into
      material_sources for each traced value. Blanks are EXPECTED and flagged for
      the engineer to resolve at design time.
  material_model_coefficients -> STAYS EMPTY until OEM/installation validation.
      These must be evidence-based calibration, not guessed constants.

USAGE (from backend/):
    python build_material_db.py              # build into vectrix.db
    python build_material_db.py --db new.db  # build into a different file
    python build_material_db.py --verify     # report only, build nothing
"""
from __future__ import annotations
import argparse, os, subprocess, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_DB = os.environ.get("VECTRIX_DB", os.path.join(HERE, "vectrix.db"))

# Dependency order: materials_v2 first (every other table FKs to it).
SCRIPTS = [
    ("create_materials_table.py",                    "materials_v2"),
    ("create_material_core_table.py",                "material_core"),
    ("create_material_particles_table.py",           "material_particles"),
    ("create_material_handling_table.py",            "material_handling"),
    ("create_material_hazards_table.py",             "material_hazards"),
    ("create_material_model_coefficients_table.py",  "material_model_coefficients"),
    ("create_material_sources_table.py",             "material_sources"),
]


def report(db):
    con = sqlite3.connect(db)
    try:
        print(f"\n{'table':32s} {'rows':>7s}  {'cols':>4s}  STRICT")
        print("-" * 58)
        ok = True
        for _, table in SCRIPTS:
            row = con.execute(
                "SELECT name, strict FROM pragma_table_list WHERE name=?", (table,)
            ).fetchone()
            if not row:
                print(f"{table:32s} {'--':>7s}  {'--':>4s}  MISSING")
                ok = False
                continue
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            c = con.execute(f"SELECT COUNT(*) FROM pragma_table_info('{table}')").fetchone()[0]
            strict = "yes" if row[1] else "NO"
            if not row[1]:
                ok = False
            print(f"{table:32s} {n:>7d}  {c:>4d}  {strict}")
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        print("-" * 58)
        print(f"foreign key violations: {len(fk)}")
        if fk:
            ok = False
            for v in fk[:5]:
                print("   ", v)
        return ok
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--verify", action="store_true", help="report only, build nothing")
    args = ap.parse_args()

    if args.verify:
        ok = report(args.db)
        print("\nCLEAN." if ok else "\nNOT CLEAN -- see above.")
        return 0 if ok else 1

    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 37, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} too old for STRICT (need >= 3.37).")

    print(f"building material database in: {args.db}")
    print(f"SQLite {sqlite3.sqlite_version}\n")

    for script, table in SCRIPTS:
        path = os.path.join(HERE, script)
        if not os.path.isfile(path):
            sys.exit(f"missing script: {script}")
        print(f"  -> {script}")
        r = subprocess.run([sys.executable, path, "--db", args.db],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout); print(r.stderr)
            sys.exit(f"FAILED on {script} -- nothing further was run.")

    ok = report(args.db)
    if ok:
        print("\nAll 7 foundation tables built, STRICT, FK-clean.")
        print("\nNEXT: populate materials_v2 -> core -> particles(TierA) -> handling")
        print("      -> hazards, writing provenance into material_sources.")
        print("      material_model_coefficients STAYS EMPTY until validation.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())