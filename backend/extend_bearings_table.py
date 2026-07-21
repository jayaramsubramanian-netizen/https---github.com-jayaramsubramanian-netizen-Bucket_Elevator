"""
backend/extend_bearings_table.py -- add selection-critical columns to `bearings`.
═══════════════════════════════════════════════════════════════════════════
WHY THIS EXISTS
───────────────
calculations.py:2422 computes L10 as calc_bearing_life(R_head, inp.n_rpm) --
with NO C_basic_N argument, so every bearing life in the application uses the
function default of 355 kN. Meanwhile `bearings` holds 168 real SKF rows with
genuine C / C0 ratings that the solver never reads.

Measured impact (100 mm shaft, 45 kN radial, 60 rpm):
    assumed default   C=355 kN  ->  L10 = 136,378 h   (passes 40,000 h)
    SY100TF  (Y-PBU)  C=122 kN  ->  L10 =   5,535 h   (FAILS by 7x)
    22220E   (SRB)    C=345 kN  ->  L10 = 246,656 h
A 25x spread on a headline output that drives a PASS/FAIL verdict. Worse, 108 of
130 shaft-end bearings are BELOW 355 kN, and at 60/80 mm bores that rating is
not achievable at all (catalogue maxima 135 / 200 kN) -- the solver assumes a
bearing that does not exist.

BUT C MUST NOT DRIVE SELECTION
──────────────────────────────
Selecting "highest C that meets L10" would produce catalogue-legal nonsense: a
deep-groove ball bearing on a head shaft that sees real misalignment from casing
deflection. It would pass L10 and fail in service. For bucket elevators
MISALIGNMENT usually dominates, which is why spherical roller bearings in
plummer blocks are the conventional choice -- not because C is highest, but
because they tolerate reality.

The real design sequence is:
    radial + axial load, shock, misalignment, rpm, environment, life requirement
      -> ELIGIBLE FAMILIES  -> housing compatibility -> availability -> cost
L10 is one criterion, applied late.

The current table cannot express that: it has type/seal/role/speed_g but no
misalignment capability, shock rating, temperature range, housing or
availability. Selecting on misalignment when the column does not exist would
mean INFERRING it from `type` -- fabrication. So the schema comes first.

WHAT THIS SCRIPT DOES / DOES NOT DO
───────────────────────────────────
DOES:     adds the columns, NULL, non-destructively (ALTER TABLE ADD COLUMN).
          Existing rows and every existing query keep working unchanged.
DOES NOT: populate any engineering value. `--propose` PRINTS a typical
          type->capability mapping for review; `--apply-proposed` writes it only
          with data_confirmed=0 so it is visibly unverified, exactly like the
          chain-data quarantine.

Nothing here is treated as verified until someone checks it against a real SKF
catalogue and sets data_confirmed=1.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

# column -> (SQL type, purpose)
NEW_COLUMNS = [
    ("series",            "TEXT",    "catalogue series, e.g. '22220' — groups interchangeable sizes"),
    ("misalignment_deg",  "REAL",    "permissible angular misalignment, degrees — THE dominant criterion"),
    ("shock_suitability", "TEXT",    "light | moderate | heavy — shock/impact duty rating"),
    ("temp_min_c",        "REAL",    "minimum service temperature"),
    ("temp_max_c",        "REAL",    "maximum service temperature"),
    ("seal_type",         "TEXT",    "labyrinth | triple_lip | taconite | contact | shielded | open"),
    ("housing",           "TEXT",    "compatible housing designation, e.g. 'SNL520'"),
    ("adapter_sleeve",    "TEXT",    "adapter sleeve, e.g. 'H320'"),
    ("reference_speed",   "REAL",    "reference speed rpm (thermal), distinct from limiting speed"),
    ("availability",      "TEXT",    "global | regional | special_order"),
    ("price_class",       "TEXT",    "A(low) .. E(high) — relative, for cost-aware selection"),
    ("industry_ok",       "TEXT",    "comma list: food,cement,fertilizer,mining,general"),
    # provenance, same discipline as the chain quarantine
    ("data_confirmed",    "INTEGER", "1 = checked against a real catalogue; 0/NULL = UNVERIFIED"),
    ("data_source",       "TEXT",    "where the added values came from"),
]

# Typical published capabilities BY BEARING TYPE. These are PROPOSALS for review,
# never written unless --apply-proposed is passed, and then only with
# data_confirmed=0. Ranges are the widely published ones; the exact figure is
# size-dependent and must come from the manufacturer's own tables.
#   type -> (misalignment_deg, shock_suitability, note)
TYPE_PROPOSAL = {
    "SRB":     (1.5,  "heavy",    "Spherical roller: self-aligning, 1-2.5 deg typical. "
                                  "Conventional bucket-elevator head-shaft choice."),
    "SAB":     (2.5,  "moderate", "Self-aligning ball: high misalignment, lower load capacity."),
    "PBU-SN":  (1.5,  "heavy",    "SN plummer block housing an SRB — inherits SRB capability."),
    "Y-PBU":   (2.0,  "light",    "Y-bearing insert unit: generous INITIAL alignment, but "
                                  "NOT intended for continuous dynamic misalignment."),
    "DGBB":    (0.1,  "light",    "Deep groove ball: 2-10 arcmin only. Unsuitable where the "
                                  "shaft deflects."),
    "TRB":     (0.05, "moderate", "Taper roller: ~1-2 arcmin. Requires precise alignment; "
                                  "takes combined radial+axial load."),
}


def existing_columns(con):
    return {r[1] for r in con.execute("PRAGMA table_info(bearings)")}


def add_columns(con, dry_run=False):
    have = existing_columns(con)
    added = []
    for name, sqltype, purpose in NEW_COLUMNS:
        if name in have:
            continue
        added.append(name)
        if not dry_run:
            con.execute(f"ALTER TABLE bearings ADD COLUMN {name} {sqltype}")
    if not dry_run:
        con.commit()
    return added


def propose(con):
    print("PROPOSED type -> capability mapping (NOT written unless --apply-proposed):\n")
    print(f"  {'type':9s} {'rows':>5s}  {'misalign':>9s}  {'shock':10s} note")
    for t, (mis, shock, note) in TYPE_PROPOSAL.items():
        n = con.execute("SELECT COUNT(*) FROM bearings WHERE type=?", (t,)).fetchone()[0]
        print(f"  {t:9s} {n:>5d}  {mis:>7.2f}deg  {shock:10s} {note[:52]}")
    unknown = [r[0] for r in con.execute("SELECT DISTINCT type FROM bearings")
               if r[0] not in TYPE_PROPOSAL]
    if unknown:
        print(f"\n  NO PROPOSAL for type(s): {unknown} -- left NULL.")
    print("\nThese are TYPICAL PUBLISHED RANGES by bearing family, not per-size")
    print("catalogue values. The exact permissible misalignment varies with size")
    print("and series. Applying them sets data_confirmed=0 so every row remains")
    print("visibly unverified until checked against SKF's own tables.")


def apply_proposed(con):
    have = existing_columns(con)
    if "misalignment_deg" not in have:
        sys.exit("columns not added yet -- run without --propose first.")
    n = 0
    for t, (mis, shock, note) in TYPE_PROPOSAL.items():
        cur = con.execute(
            "UPDATE bearings SET misalignment_deg=?, shock_suitability=?, "
            "data_confirmed=0, data_source=? "
            "WHERE type=? AND misalignment_deg IS NULL",
            (mis, shock, f"TYPE-LEVEL PROPOSAL, UNVERIFIED: {note}", t))
        n += cur.rowcount
    con.commit()
    print(f"applied type-level proposals to {n} rows, ALL with data_confirmed=0")
    print("These MUST be verified per-size against the manufacturer catalogue.")


def report(con):
    have = existing_columns(con)
    total = con.execute("SELECT COUNT(*) FROM bearings").fetchone()[0]
    print(f"bearings: {total} rows, {len(have)} columns")
    missing = [c for c, _, _ in NEW_COLUMNS if c not in have]
    print(f"selection columns present: {len(NEW_COLUMNS)-len(missing)}/{len(NEW_COLUMNS)}")
    if missing:
        print(f"  still missing: {missing}")
        return
    print("\npopulation status of the added columns:")
    for name, _, purpose in NEW_COLUMNS:
        n = con.execute(f"SELECT COUNT(*) FROM bearings WHERE {name} IS NOT NULL").fetchone()[0]
        bar = "#" * int(20 * n / max(total, 1))
        print(f"  {name:18s} {n:>4d}/{total} {bar}")
    if "data_confirmed" in have:
        nconf = con.execute("SELECT COUNT(*) FROM bearings WHERE data_confirmed=1").fetchone()[0]
        nunconf = con.execute("SELECT COUNT(*) FROM bearings WHERE data_confirmed=0").fetchone()[0]
        print(f"\n  CONFIRMED   {nconf}")
        print(f"  UNVERIFIED  {nunconf}   <- must not be treated as engineering data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--propose", action="store_true",
                    help="print the type->capability mapping, write nothing")
    ap.add_argument("--apply-proposed", action="store_true",
                    help="write the proposals with data_confirmed=0 (UNVERIFIED)")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        if args.report:
            report(con); return 0
        if args.propose:
            propose(con); return 0

        added = add_columns(con, dry_run=args.dry_run)
        if added:
            print(f"{'WOULD ADD' if args.dry_run else 'ADDED'} {len(added)} columns: {added}")
        else:
            print("all selection columns already present")
        if args.apply_proposed and not args.dry_run:
            print()
            apply_proposed(con)
        print()
        report(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())