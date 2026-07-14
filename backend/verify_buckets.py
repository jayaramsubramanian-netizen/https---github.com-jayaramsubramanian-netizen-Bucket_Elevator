"""
backend/verify_buckets.py -- run BEFORE deleting BUCKET_SERIES.
═══════════════════════════════════════════════════════════════════════════
Asserts that catalog.load_buckets() (read from the `buckets` DB table) is
field-for-field identical to calculations.BUCKET_SERIES (the in-code constant,
with BUCKET_PUNCHING already merged in by apply_punching_data()).

WHY THIS EXISTS
───────────────
The DB column names are NOT the keys the code reads:

    bucket_id -> id      W_mm -> W      P_mm -> P      H_mm -> H      V_L -> V

One wrong key does not throw. It silently yields a bucket with a missing or wrong
dimension, which propagates into capacity, bucket spacing, belt width selection,
the BOM mass, and the bolt pattern on the CAD bucket drawing. That is exactly the
class of failure that must be caught by a diff, not by eyeballing a UI.

So: prove equivalence first, delete second. If this prints CLEAN, the swap is
safe. If it prints any DIFF, do not touch calculations.py -- send me the output.

USAGE (from backend/):
    python verify_buckets.py
"""
import sys

def main():
    try:
        from calculations import BUCKET_SERIES as CODE
    except Exception as e:
        sys.exit(f"Could not import BUCKET_SERIES from calculations.py: {e}")
    try:
        from catalog import load_buckets
        DB = list(load_buckets())
    except Exception as e:
        sys.exit(f"Could not load buckets from the DB via catalog.py: {e}")

    print(f"in-code BUCKET_SERIES : {len(CODE)} buckets")
    print(f"DB `buckets` table    : {len(DB)} buckets")
    print()

    code_by_id = {b["id"]: b for b in CODE}
    db_by_id   = {b["id"]: b for b in DB}

    only_code = sorted(set(code_by_id) - set(db_by_id))
    only_db   = sorted(set(db_by_id) - set(code_by_id))
    if only_code:
        print(f"!! in CODE but NOT in DB ({len(only_code)}): {only_code}")
    if only_db:
        print(f"!! in DB but NOT in CODE ({len(only_db)}): {only_db}")

    # Compare only the keys the SOLVER actually reads. The DB legitimately carries
    # extra columns (custom, recommended_materials, note) that the constant never
    # had -- those are additions, not diffs, and are listed separately below.
    diffs = []
    extra_keys = set()
    for bid in sorted(set(code_by_id) & set(db_by_id)):
        c, d = code_by_id[bid], db_by_id[bid]
        extra_keys |= (set(d) - set(c))
        for k in sorted(c):
            cv, dv = c.get(k), d.get(k)
            if isinstance(cv, float) or isinstance(dv, float):
                same = (cv is None and dv is None) or (
                    cv is not None and dv is not None and abs(float(cv) - float(dv)) < 1e-6)
            else:
                same = cv == dv
            if not same:
                diffs.append((bid, k, cv, dv))

    if diffs:
        print(f"!! {len(diffs)} FIELD DIFFERENCE(S) -- DO NOT DELETE THE CONSTANT:\n")
        for bid, k, cv, dv in diffs[:40]:
            print(f"   {bid:10s} {k:20s} code={cv!r:>18}   db={dv!r:>18}")
        if len(diffs) > 40:
            print(f"   ... and {len(diffs)-40} more")
    else:
        print("No field differences on any key the solver reads.")

    if extra_keys:
        print(f"\nExtra columns present in the DB but absent from the constant")
        print(f"(additions, not diffs -- they carry through harmlessly):")
        print(f"   {sorted(extra_keys)}")

    # Punching specifically -- this one lands on a fabrication drawing.
    print("\nPunching spot-check (these drive the CAD bolt pattern):")
    for bid in ("AA_6x4", "AA_14x8", "AC_12x8", "SC_30x12"):
        c, d = code_by_id.get(bid), db_by_id.get(bid)
        if not c or not d:
            continue
        cp = (c.get("punch"), c.get("boltN"), c.get("boltA_mm"), c.get("punch_confirmed"))
        dp = (d.get("punch"), d.get("boltN"), d.get("boltA_mm"), d.get("punch_confirmed"))
        flag = "OK " if cp == dp else "!! "
        print(f"   {flag}{bid:10s} code={cp}  db={dp}")

    ok = not diffs and not only_code and not only_db
    print()
    if ok:
        print("CLEAN -- the DB reproduces BUCKET_SERIES exactly.")
        print("Safe to switch calculations.py over:")
        print("    replace the BUCKET_SERIES literal (line ~158) with:")
        print("        from catalog import BUCKET_SERIES")
        print("    and DELETE the apply_punching_data(BUCKET_SERIES) call (~line 483).")
    else:
        print("NOT CLEAN -- leave calculations.py alone and send me the output above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())