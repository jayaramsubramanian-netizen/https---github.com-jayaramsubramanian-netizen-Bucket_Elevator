"""
quarantine_chains.py -- flag the eight existing chains as UNVERIFIED.

WHY: the eight rows in CHAIN_SERIES (and now in the `chains` table) were
CONSTRUCTED BY A LANGUAGE MODEL. No manufacturer publishes N102B at 4990 kg
working load -- that number was generated, not sourced.

This matters more than an ordinary data-quality problem, because of HOW it is
used. select_chain_auto() sizes the chain on:

    WL_kg * 9.81 * n_strands / T_pull_N  >=  SF

and the SF is then computed FROM THE SAME WL_kg. A chain whose real working load
is half the invented figure still reports a comfortable SF ~ 6. The safety check
CANNOT catch the error, because the error is in its own input. This is a chain
holding buckets of clinker 25 m in the air.

This does NOT delete the chains -- that would break every saved chain design. It
makes the uncertainty VISIBLE, exactly as the bucket catalogue already does with
punch_confirmed=False on the six AC estimates.
"""
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

UNVERIFIED = (
    "UNVERIFIED - LLM-generated placeholder. Not traceable to any manufacturer "
    "catalogue. Working load, weight and speed limit are NOT from Renold, "
    "Webster, Rexnord, Tsubaki or DIN. Do not use for a released design."
)

NEW_COLUMNS = [
    ("confirmed",  "INTEGER NOT NULL DEFAULT 0"),
    ("source",     "TEXT"),
    ("equivalent", "TEXT"),   # dual-ID: "DIN 8167 K2", "Webster X-200 K2"
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(a.db)
    con.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(chains)")}
        if not cols:
            sys.exit("No `chains` table. Run create_chains_table.py first.")
        to_add = [(c, d) for c, d in NEW_COLUMNS if c not in cols]
        print("columns to add:", [c for c, _ in to_add] or "none")

        rows = con.execute("SELECT chain_id, WL_kg, n_strands FROM chains").fetchall()
        print(f"\n{len(rows)} chain(s) to flag UNVERIFIED:\n")
        for r in rows:
            print(f"  {r['chain_id']:8s} WL={r['WL_kg']:>8.0f} kg  "
                  f"strands={r['n_strands']}  -> confirmed=0")

        if a.dry_run:
            print("\nDRY RUN -- nothing written.")
            return 0

        for c, d in to_add:
            con.execute(f"ALTER TABLE chains ADD COLUMN {c} {d}")
        con.execute(
            "UPDATE chains SET confirmed=0, source=? "
            "WHERE source IS NULL OR source=''", (UNVERIFIED,))
        con.commit()

        n = con.execute("SELECT COUNT(*) FROM chains WHERE confirmed=0").fetchone()[0]
        t = con.execute("SELECT COUNT(*) FROM chains").fetchone()[0]
        print(f"\n{n} of {t} chains flagged confirmed=0 with an explicit UNVERIFIED source.")
    finally:
        con.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())