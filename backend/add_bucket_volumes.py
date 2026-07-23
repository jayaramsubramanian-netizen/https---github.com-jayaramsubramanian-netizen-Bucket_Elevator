"""
backend/add_bucket_volumes.py -- add and populate the water-level (X-X) volume
column, and add a (deferred) lip-height column, on the `buckets` table.
═══════════════════════════════════════════════════════════════════════════
WHY
───
The buckets table stored ONE volume, V_L, which is the Y-Y (100% fill / heaped)
capacity. Jay's fill model needs BOTH geometric endpoints:

    V_geometric = X-X + (Y-Y - X-X) * heap_factor      # heap_factor per material
    Q = (v/spacing) * V_geometric * fill_pct * rho * 3.6

Without X-X there is no floor for the heap interpolation -- the solver can only
use the Y-Y ceiling. This adds `water_level_V_L` (X-X) and populates all 40 from
the Martin catalog (real published data, transcribed and verified by Jay against
the catalog images).

`lip_height_mm` is added as a column but left NULL. It CANNOT be back-calculated
from the published volumes without inventing a per-style cross-section shape
model (AA curved / AC hooded / C quarter-circle / MF 30° / HF 45° / SC scoop),
which would be a fabrication. It is deferred to the custom-bucket session, where
a validated geometric model will fill it. See TASK_LIST.md.

DATA ONLY -- this script changes no equation. calc_capacity still uses V_L until
the capacity rewire (which is gated on confirming the material heap_factor field).

USAGE (from backend/):
    python add_bucket_volumes.py --dry-run
    python add_bucket_volumes.py
    python add_bucket_volumes.py --verify     # re-check without writing
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

FT3_TO_L = 28.3168

# X-X water-level volume [ft3], transcribed from the Martin catalog and VERIFIED
# by Jay against the catalog images. Stored as litres in the DB.
XX_FT3 = {
    "AA_6x4":0.02,"AA_8x5":0.04,"AA_10x6":0.07,"AA_12x7":0.12,"AA_14x8":0.20,
    "AA_16x8":0.23,"AA_18x8":0.26,"AA_18x10":0.33,
    "AC_12x8":0.231,"AC_14x8":0.271,"AC_16x8":0.311,"AC_18x10":0.488,
    "AC_20x10":0.542,"AC_24x10":0.651,
    "C_6x4":0.026,"C_8x4":0.035,"C_10x5":0.052,"C_14x7":0.138,"C_16x7":0.158,
    "MF_10x7":0.103,"MF_12x7":0.125,"MF_12x8":0.163,"MF_14x8":0.190,
    "MF_16x8":0.220,"MF_18x8":0.250,"MF_24x10":0.512,
    "HF_10x7":0.130,"HF_12x7":0.155,"HF_14x7":0.184,"HF_14x8":0.240,
    "HF_16x8":0.275,"HF_18x8":0.315,
    "SC_12x8":0.35,"SC_14x8":0.41,"SC_16x8":0.46,"SC_18x8":0.52,"SC_20x8":0.58,
    "SC_20x12":1.40,"SC_24x12":1.68,"SC_30x12":2.11,
}

NEW_COLUMNS = [("water_level_V_L", "REAL"), ("lip_height_mm", "REAL")]


def verify(con):
    """X-X must exist for all 40, be > 0, and be STRICTLY LESS THAN Y-Y (V_L).
    Struck volume below heaped volume is a physical invariant -- if any row
    violates it, a value was transcribed into the wrong bucket."""
    rows = con.execute(
        "SELECT bucket_id, V_L, water_level_V_L FROM buckets ORDER BY bucket_id"
    ).fetchall()
    problems, n_ok = [], 0
    for bid, yy, xx in rows:
        if xx is None:
            problems.append(f"{bid}: water_level_V_L is NULL"); continue
        if xx <= 0:
            problems.append(f"{bid}: X-X {xx} <= 0"); continue
        if yy is not None and xx >= yy:
            problems.append(f"{bid}: X-X {xx:.2f} >= Y-Y {yy:.2f}  (struck must be < heaped)")
            continue
        n_ok += 1
    print(f"  {n_ok} rows pass (X-X present, >0, and < Y-Y)")
    for p in problems:
        print(f"  !! {p}")
    return not problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(a.db)
    try:
        if a.verify:
            print("VERIFY:"); ok = verify(con); sys.exit(0 if ok else 1)

        existing = {r[1] for r in con.execute("PRAGMA table_info(buckets)")}
        to_add = [(c, t) for c, t in NEW_COLUMNS if c not in existing]
        print("columns to add:", [c for c, _ in to_add] or "none (already present)")

        db_ids = {r[0] for r in con.execute("SELECT bucket_id FROM buckets")}
        missing = set(XX_FT3) - db_ids
        extra   = db_ids - set(XX_FT3)
        if missing: print(f"  !! in transcription but NOT in DB: {sorted(missing)}")
        if extra:   print(f"  !! in DB but NO X-X value given:   {sorted(extra)}")

        print(f"\n{len(XX_FT3)} buckets to populate with X-X water-level volume:")
        for bid in sorted(XX_FT3):
            print(f"  {bid:10s} X-X {XX_FT3[bid]:.3f} ft3 = {XX_FT3[bid]*FT3_TO_L:6.2f} L")

        if a.dry_run:
            print("\nDRY RUN -- nothing written."); return 0

        for c, t in to_add:
            con.execute(f"ALTER TABLE buckets ADD COLUMN {c} {t}")
        for bid, ft3 in XX_FT3.items():
            con.execute("UPDATE buckets SET water_level_V_L = ? WHERE bucket_id = ?",
                        (round(ft3 * FT3_TO_L, 2), bid))
        con.commit()
        print("\nwritten. verifying invariant (X-X < Y-Y):")
        ok = verify(con)
        print("\nCLEAN." if ok else "\n!! INVARIANT VIOLATED — review above.")
        return 0 if ok else 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())