"""
backend/resolve_c_series_basis.py -- resolve the C-series V_L mixed-basis finding.
═══════════════════════════════════════════════════════════════════════════
THE FINDING
───────────
add_bucket_volumes.py flagged 5 invariant violations: for every C-series bucket,
the transcribed X-X (water-line) volume EQUALS the DB's V_L. Analysis confirms
this is systematic, not coincidence:

  - 5 of 5 C-series V_L values are identical to X-X, to two decimals
  - C-series fills ~40% of its bounding box; heaped styles (AA/MF/SC) fill ~47%

So `V_L` holds a MIXED BASIS: Y-Y (heaped) for AA/AC/HF/MF/SC, but X-X
(water-line) for style C. One column, two meanings -- the same two-sources-of-
truth class the material-table rebuild exists to eliminate. If the solver treats
V_L as heaped everywhere, C-series capacity is understated against every other
style, and any design that selected a C bucket was sized on a different basis.

THIS SCRIPT DOES NOT GUESS THE FIX
──────────────────────────────────
It cannot: the correct Y-Y volumes for style C are catalogue data. What it does
is make the resolution a single command AFTER you check the Martin catalogue
page for style C, with two documented paths:

  --mode heaped-supplied   You read Y-Y from the catalogue. Provide them; the
                           script writes them to V_L, moves the existing (X-X)
                           value to water_level_V_L, and the invariant passes.

  --mode single-volume     The catalogue publishes only ONE volume for style C
                           (some elevator-bucket styles do). Then C genuinely
                           has no separate heaped figure, and forcing X-X < Y-Y
                           is wrong. This records that V_L == water_level_V_L is
                           INTENTIONAL for style C via a per-style basis flag,
                           so the invariant check skips C with a documented reason
                           instead of failing.

Either way the outcome is EXPLICIT and provenance-tagged -- never a silent edit.

Run --inspect first to see the current state and the exact numbers to look up.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))


def ensure_basis_column(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(buckets)")}
    if "volume_basis" not in cols:
        con.execute("ALTER TABLE buckets ADD COLUMN volume_basis TEXT")
        con.commit()
        print("added buckets.volume_basis column")


def inspect(con):
    print("current C-series state:\n")
    print(f"  {'bucket':10s} {'V_L':>7s} {'water_level_V_L':>15s}  note")
    for r in con.execute("SELECT bucket_id, V_L, water_level_V_L FROM buckets "
                         "WHERE style='C' ORDER BY V_L"):
        wl = r[2] if r[2] is not None else None
        note = ("V_L == water-line (mixed basis)" if wl is not None and abs(wl - r[1]) < 0.01
                else "")
        print(f"  {r[0]:10s} {r[1]:7.2f} {str(wl):>15s}  {note}")
    print("\nTO RESOLVE: open the Martin catalogue page for style C.")
    print("  * If it lists BOTH X-X and Y-Y columns -> --mode heaped-supplied")
    print("    (provide the Y-Y values; V_L currently holds X-X mislabelled)")
    print("  * If it lists only ONE volume for style C -> --mode single-volume")
    print("    (C has no separate heaped figure; the invariant exception is correct)")


def heaped_supplied(con, pairs):
    """pairs: {bucket_id: yy_litres}. Move current V_L -> water_level_V_L (it is
    X-X), write the supplied Y-Y to V_L. Verify X-X < Y-Y after."""
    ensure_basis_column(con)
    n = 0
    for bid, yy in pairs.items():
        row = con.execute("SELECT V_L FROM buckets WHERE bucket_id=?", (bid,)).fetchone()
        if not row:
            print(f"  ! {bid} not found"); continue
        xx = row[0]
        if yy <= xx:
            print(f"  ! {bid}: supplied Y-Y {yy} <= current X-X {xx} — refusing "
                  f"(heaped must exceed water-line)")
            continue
        con.execute("UPDATE buckets SET water_level_V_L=?, V_L=?, "
                    "volume_basis='Y-Y (heaped); X-X in water_level_V_L' "
                    "WHERE bucket_id=?", (xx, yy, bid))
        n += 1
        print(f"  {bid}: X-X {xx} -> water_level_V_L, Y-Y {yy} -> V_L")
    con.commit()
    print(f"\nupdated {n} rows. Re-run add_bucket_volumes.py to confirm the invariant.")


def single_volume(con):
    """Style C publishes one volume. Record that V_L == water_level_V_L is
    INTENTIONAL for C, so the invariant check documents an exception rather than
    failing. Nothing is fabricated -- the values stand; only their basis is
    labelled."""
    ensure_basis_column(con)
    n = con.execute(
        "UPDATE buckets SET volume_basis='single published volume (X-X == V_L)' "
        "WHERE style='C'").rowcount
    con.commit()
    print(f"tagged {n} C-series rows: single-volume basis is INTENTIONAL.")
    print("The X-X < Y-Y invariant should now SKIP style C with this documented")
    print("reason. Update add_bucket_volumes.py's check to honour volume_basis.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--mode", choices=["heaped-supplied", "single-volume"])
    # Y-Y values for --mode heaped-supplied, e.g. --yy C_6x4=1.10 C_8x4=1.45 ...
    ap.add_argument("--yy", nargs="*", default=[],
                    help="bucket_id=litres pairs of catalogue Y-Y volumes")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        if not con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                          "AND name='buckets'").fetchone():
            sys.exit("no `buckets` table in this database — wrong vectrix.db?")

        if args.inspect or not args.mode:
            inspect(con)
            if not args.mode:
                return 0

        if args.mode == "heaped-supplied":
            if not args.yy:
                sys.exit("--mode heaped-supplied needs --yy bucket=litres pairs "
                         "(read from the catalogue).")
            pairs = {}
            for tok in args.yy:
                k, _, v = tok.partition("=")
                pairs[k.strip()] = float(v)
            heaped_supplied(con, pairs)
        elif args.mode == "single-volume":
            single_volume(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())