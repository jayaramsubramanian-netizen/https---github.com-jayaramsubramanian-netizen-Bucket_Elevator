"""
backend/verify_chains.py -- run AFTER create_chains_table.py, BEFORE switching
calculations.py over to the DB.
═══════════════════════════════════════════════════════════════════════════
Asserts that catalog.load_chains() (read from the new `chains` table) is
field-for-field identical to calculations.CHAIN_SERIES (the constant it was
seeded from).

WHY THIS MATTERS
────────────────
select_chain_auto() picks the smallest chain whose working load meets the
required safety factor:

    WL_required = T_pull_N × sf / (9.81 × n_strands)

So every field here has teeth:

  * WL_kg wrong      -> a chain is selected that cannot carry the load, or an
                        unnecessarily heavy one is. The SF check may still PASS,
                        because it is computed from the same wrong number.
  * n_strands wrong  -> the candidate filter picks from the wrong pool entirely
                        (single-strand chains for an SC double-strand elevator).
  * wt_kg_m wrong    -> chain weight feeds back into the tension calculation that
                        selected the chain. A wrong weight is self-reinforcing.
  * v_max_ms wrong   -> the chain speed check passes or fails incorrectly.
  * series wrong     -> the JSON round-trip failed; the list came back as a
                        string or empty.

None of these throw. A wrong chain just quietly appears on the BOM.

USAGE (from backend/):
    python verify_chains.py
"""
import sys


def main():
    try:
        from calculations import CHAIN_SERIES as CODE
    except Exception as e:
        sys.exit(f"Could not import CHAIN_SERIES from calculations.py: {e}")
    try:
        from catalog import load_chains
        DB = list(load_chains())
    except Exception as e:
        sys.exit(f"Could not load chains from the DB via catalog.py: {e}\n"
                 f"Did you run create_chains_table.py?")

    print(f"in-code CHAIN_SERIES : {len(CODE)} chains")
    print(f"DB `chains` table    : {len(DB)} chains")
    print()

    code_by_id = {c["id"]: c for c in CODE}
    db_by_id   = {c["id"]: c for c in DB}

    only_code = sorted(set(code_by_id) - set(db_by_id))
    only_db   = sorted(set(db_by_id) - set(code_by_id))
    if only_code:
        print(f"!! in CODE but NOT in DB ({len(only_code)}): {only_code}")
    if only_db:
        print(f"!! in DB but NOT in CODE ({len(only_db)}): {only_db}")

    diffs = []
    extra_keys = set()
    for cid in sorted(set(code_by_id) & set(db_by_id)):
        c, d = code_by_id[cid], db_by_id[cid]
        extra_keys |= (set(d) - set(c))
        for k in sorted(c):
            cv, dv = c.get(k), d.get(k)
            if isinstance(cv, (int, float)) and isinstance(dv, (int, float)) \
                    and not isinstance(cv, bool):
                same = abs(float(cv) - float(dv)) < 1e-9
            else:
                same = cv == dv
            if not same:
                diffs.append((cid, k, cv, dv))

    if diffs:
        print(f"!! {len(diffs)} FIELD DIFFERENCE(S) -- DO NOT SWITCH THE SOLVER OVER:\n")
        for cid, k, cv, dv in diffs:
            print(f"   {cid:8s} {k:12s} code={cv!r:>28}   db={dv!r:>28}")
    else:
        print("No field differences on any key the solver reads.")

    if extra_keys:
        print(f"\nExtra columns in the DB, absent from the constant (additions, not diffs):")
        print(f"   {sorted(extra_keys)}")

    # The list field is the one most likely to break in a JSON round-trip.
    print("\nJSON round-trip spot-check on `series` (a list, stored as TEXT):")
    for cid in ("S102B", "ER856", "C9124"):
        c, d = code_by_id.get(cid), db_by_id.get(cid)
        if not c or not d:
            continue
        ok = isinstance(d.get("series"), list) and d["series"] == c["series"]
        print(f"   {'OK ' if ok else '!! '}{cid:8s} code={c['series']}  db={d['series']!r}")

    # Selection-critical fields, called out explicitly.
    print("\nSelection-critical fields (drive select_chain_auto's SF criterion):")
    for cid in sorted(set(code_by_id) & set(db_by_id)):
        c, d = code_by_id[cid], db_by_id[cid]
        ok = (c["WL_kg"] == d["WL_kg"] and c["n_strands"] == d["n_strands"]
              and c["wt_kg_m"] == d["wt_kg_m"])
        print(f"   {'OK ' if ok else '!! '}{cid:8s} WL={d['WL_kg']:>7} kg  "
              f"strands={d['n_strands']}  wt={d['wt_kg_m']:>5} kg/m")

    ok = not diffs and not only_code and not only_db
    print()
    if ok:
        print("CLEAN -- the DB reproduces CHAIN_SERIES exactly.")
        print("Safe to switch calculations.py over:")
        print("    replace the CHAIN_SERIES literal with:")
        print("        from catalog import CHAIN_SERIES")
        print("Then add `chains` to seed_all.py's TABLE_SPECS and")
        print("export_vectrix_db.py's TABLES, and add a /components/chains endpoint.")
    else:
        print("NOT CLEAN -- leave calculations.py alone and send me the output above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())