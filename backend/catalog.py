"""
backend/catalog.py -- the single read path for component catalogue data.
═══════════════════════════════════════════════════════════════════════════
WHAT THIS REPLACES AND WHY
──────────────────────────
Bucket data currently lives in FIVE places:

  1. calculations.py:158        BUCKET_SERIES              <- what the SOLVER reads
  2. calculations_bucket_punching_patch.py:31  BUCKET_PUNCHING
                                (merged into #1 at import, calculations.py:483)
  3. the `buckets` DB table     <- what /components/buckets SERVES
  4. InputSidebar.jsx           BUCKET_CATALOG (hardcoded again)
  5. desktop-poc BUCKET_STYLE_INFO (style descriptions only -- dimensions
                                already come live from the API)

The DB table is COMPLETE: 40 rows, all 40 carrying punch data, and verified
identical to BUCKET_PUNCHING (AA_6x4 -> B1/76.2/2/confirmed in both; AA_14x8 ->
B7/101.6/4/confirmed in both). So the seed already ran AFTER apply_punching_data().
There is no data divergence to reconcile -- only a redundancy to remove.

main.py's own /components/buckets docstring says as much:

    "not yet what select_bucket_auto()/the manual picker actually read from
     (those still use the in-code BUCKET_SERIES list directly) ... ahead of
     actually switching the solver's own read path over."

This module IS that switch.

WHY A LOADER AND NOT ~10 REWRITTEN CALL SITES
─────────────────────────────────────────────
BUCKET_SERIES is read in about ten places across calculations.py (select_bucket_
auto, the manual picker, _BUCKET_BY_ID, the mass lookup, line 4591's sweep) and
vectrix_optimizer_v2.py (_BUCKET_IDS). Rewriting each into a SQL query would be a
large diff through working engineering code, and would leave the optimizer free to
drift into becoming a FOURTH source of truth.

Instead this returns a list of dicts in EXACTLY the shape BUCKET_SERIES has today.
Then calculations.py:158 becomes one import line, every existing read
(b["id"], bucket["P"], bucket["V"] ...) keeps working untouched, and the optimizer
inherits DB data for free.

    -  from catalog import BUCKET_SERIES      # <- replaces 300 lines of literal
    -  apply_punching_data(BUCKET_SERIES)     # <- DELETE: DB already has punch cols

DO NOT SHIP THIS WITHOUT RUNNING verify_buckets.py FIRST.
The DB column names differ from the keys the code reads (bucket_id -> id,
W_mm -> W, V_L -> V ...). One wrong key silently mis-sizes a bucket, which
propagates into capacity, spacing, belt width and the CAD bolt pattern. The
verifier asserts the DB-derived list is field-for-field identical to the current
constant. Only delete the constant once it passes.
"""
from __future__ import annotations

import os
import json
import sqlite3
from functools import lru_cache

# Same resolution order main.py uses; override with VECTRIX_DB for tests.
_DB_PATH = os.environ.get(
    "VECTRIX_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectrix.db"),
)


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(db_path or _DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── Bucket column mapping ────────────────────────────────────────────────
# DB column               -> key the existing code reads.
# Everything not listed here is passed through under its own name, so any column
# added to the table later (a new punch field, a VECTOMEC model number) shows up
# in the dict automatically without touching this map.
_BUCKET_RENAMES = {
    "bucket_id": "id",
    "W_mm":      "W",
    "P_mm":      "P",
    "H_mm":      "H",
    "V_L":       "V",
}

# Stored as JSON TEXT in SQLite (same handling /components/buckets does).
_BUCKET_JSON_COLS = ("recommended_materials",)


def _row_to_bucket(row: sqlite3.Row) -> dict:
    d = dict(row)
    for col in _BUCKET_JSON_COLS:
        if col in d:
            try:
                d[col] = json.loads(d[col] or "[]")
            except (TypeError, ValueError):
                d[col] = []
    out = {}
    for k, v in d.items():
        out[_BUCKET_RENAMES.get(k, k)] = v
    # punch_confirmed / custom are INTEGER 0|1 in SQLite; the code treats them as
    # booleans (elevation_view checks `is not False`, so a 0 would read as
    # truthy-adjacent and silently suppress the "unconfirmed bolt pattern"
    # disclaimer on the CAD drawing). Coerced explicitly.
    for flag in ("punch_confirmed", "custom"):
        if flag in out and out[flag] is not None:
            out[flag] = bool(out[flag])

    # BUCKET_SERIES carried the bucket depth under TWO keys -- "H" and "depth_mm"
    # -- holding the same value (AA_6x4: H=108, depth_mm=108). The DB stores it
    # once, as H_mm. Emit both so every existing reader keeps working, including
    # any that reaches for depth_mm FIRST.
    #
    # Caught by verify_buckets.py: without this, all 40 buckets came back with
    # depth_mm=None. It would NOT have thrown -- elevation_view.py does
    # `bkt.get("H") or bkt.get("depth_mm")` and would have been fine -- while
    # anything checking depth_mm first would have silently fallen back to a
    # default and put a wrong bucket depth on a drawing. This single alias is the
    # entire reason the verifier was worth writing.
    if "H" in out:
        out["depth_mm"] = out["H"]
    return out


# ── Chains ───────────────────────────────────────────────────────────────
# DB column -> the key the existing code reads.
_CHAIN_RENAMES = {"chain_id": "id"}
_CHAIN_JSON_COLS = ("series",)   # CEMA elevator series list, stored as JSON TEXT


def _row_to_chain(row: sqlite3.Row) -> dict:
    d = dict(row)
    for col in _CHAIN_JSON_COLS:
        if col in d:
            try:
                d[col] = json.loads(d[col] or "[]")
            except (TypeError, ValueError):
                d[col] = []
    out = {_CHAIN_RENAMES.get(k, k): v for k, v in d.items()}
    if "custom" in out and out["custom"] is not None:
        out["custom"] = bool(out["custom"])
    return out


@lru_cache(maxsize=1)
def load_chains(db_path: str | None = None) -> tuple:
    """All chains, ordered as CHAIN_SERIES is: by strand count, then working load.

    select_chain_auto() filters to matching n_strands and sorts by WL ascending,
    so it does not depend on this order -- but keeping it stable makes the DB
    round-trip diffable against the constant.
    """
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM chains ORDER BY n_strands, WL_kg"
        ).fetchall()
    if not rows:
        raise RuntimeError(
            f"catalog: the `chains` table is empty or missing at "
            f"{db_path or _DB_PATH}. Run create_chains_table.py."
        )
    return tuple(_row_to_chain(r) for r in rows)


# ── Motors ───────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_motor_sizes(db_path: str | None = None) -> tuple:
    """The standard motor kW ladder -- DISTINCT Pkw from the `motors` table.

    calculations.py's motor pick walks this ascending and takes the first rating
    at or above the required power. It only ever needs the kW LADDER, not whole
    motor rows -- the DB has several models at the same kW (different poles,
    frames), so those collapse to one rung.

    This replaces a hardcoded list in calculations.py. Same divergence as buckets:
    the Components Library let you add a motor and the solver would never select
    it, because motor selection read the constant while the library read the DB.
    """
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT DISTINCT Pkw FROM motors WHERE Pkw IS NOT NULL ORDER BY Pkw"
        ).fetchall()
    if not rows:
        raise RuntimeError(
            f"catalog: the `motors` table has no Pkw values at {db_path or _DB_PATH}. "
            f"Motor selection has no ratings to choose from. Run seed_all.py."
        )
    return tuple(float(r["Pkw"]) for r in rows)


@lru_cache(maxsize=1)
def load_buckets(db_path: str | None = None) -> tuple:
    """All buckets, ordered exactly as BUCKET_SERIES is (style, then volume).

    Cached: this is read once per process, like the constant it replaces. Custom
    buckets added at runtime need load_buckets.cache_clear() -- see reload().
    """
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM buckets ORDER BY style, V_L"
        ).fetchall()
    if not rows:
        raise RuntimeError(
            f"catalog: the `buckets` table is empty at {db_path or _DB_PATH}. "
            f"The solver has no bucket catalogue to select from. Run seed_all.py."
        )
    return tuple(_row_to_bucket(r) for r in rows)


def reload():
    """Drop the cache so a newly-created custom bucket is visible without a
    restart. Call this from the POST /components handler that creates one."""
    load_buckets.cache_clear()


# ── The name calculations.py imports ─────────────────────────────────────
# A list, not the cached tuple, because the existing code does list things to it
# (BUCKET_SERIES[4], BUCKET_SERIES[-1], list comprehensions). Same object shape as
# before; nothing downstream can tell the difference.
BUCKET_SERIES = list(load_buckets())

_BUCKET_BY_ID = {b["id"]: b for b in BUCKET_SERIES}


def get_bucket(bucket_id: str) -> dict | None:
    return _BUCKET_BY_ID.get(bucket_id)


# NOTE -- there is deliberately NO module-level MOTOR_SIZES here.
#
# The `motors` table cannot be used yet: all 52 rows have Pkw = NULL, and the
# nulls are in the SOURCE data (vectrix_export/vectrix_db_export.json), so
# re-seeding reproduces them. The kW rating exists only as text inside the model
# and note strings, and parsing it back out would be inferring engineering data
# from a label -- one oddly-formatted model string and a real motor silently gets
# the wrong rating.
#
# So calculations.py keeps its hardcoded kW ladder for now (flagged in place),
# and load_motor_sizes() above sits ready for the day Pkw is populated properly.
#
# Exporting MOTOR_SIZES at module level here was also an ACTIVE BUG: it made
# `import catalog` raise whenever the motors table was bad, which took bucket
# loading -- and therefore the entire solver -- down with it. The catalogues must
# fail independently.