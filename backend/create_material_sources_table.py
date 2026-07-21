"""
backend/create_material_sources_table.py -- Table 7: material_sources.
═══════════════════════════════════════════════════════════════════════════
ENGINEERING CONFIGURATION MANAGEMENT -- not merely provenance. Every engineering
value in the material database is traceable to WHERE it came from, WHAT the
source published, WHAT VECTRIX accepted, and WHY. Answers: "Why is Portland
Cement stored as 1400 kg/m3?" -> CEMA says 1440, customer measured 1398,
Engineering accepted 1400, approved by JS, 2026-08-03.

RELATIONSHIP: 1-to-MANY. Many source rows per material -- one (or more) per
traced property. source_id is the PK; material_id is a non-unique FK.

SCHEMA-EVOLUTION SAFE (Jay's key call): the traced property is identified by
`property_name` ONLY (e.g. 'rho_loose'), NOT by (table_name, field_name). If a
property moves between engineering tables in a future version, provenance records
do NOT break. The Engineering Field Dictionary knows which table a property
currently lives in; provenance stays independent of that.

TWO VALUES, EXPLICIT MEANINGS (Jay's Option C+):
  source_value   -- what the source PUBLISHED. Immutable, historical.
  accepted_value -- what VECTRIX ADOPTED. This is what material_core echoes.
A divergence between them is not a bug -- it is a DOCUMENTED override, explained
by override_reason + decision_type.

FOUR STATE FIELDS, answering different questions:
  is_active     -- is this SOURCE still valid?          (CEMA 7th ed -> 0 when superseded)
  is_current    -- did this record produce TODAY's value? (exactly one =1 per property)
  decision_type -- HOW the accepted value came to be     (published/measured/.../overridden)
  verification_status -- review state of this record

Example (Jay's):
  CEMA 8th      is_active=1 is_current=1   -> today's value
  CEMA 7th      is_active=0 is_current=0   -> obsolete source
  Customer Test is_active=1 is_current=0   -> valid source, but Engineering chose CEMA

The solver NEVER reads this table. It only explains what material_core contains.

STRICT + CHECK, FK to materials_v2. NULL allowed except the identity fields.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

SOURCE_TYPE = ["CEMA","OEM","ASTM","ISO","Lab Test","Customer",
               "Engineering Estimate","Regression"]
DECISION_TYPE = ["published","measured","calculated","estimated","overridden"]
VERIFICATION_STATUS = ["unverified","in_review","verified","rejected","superseded"]


def ddl() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS material_sources (
    source_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id         INTEGER NOT NULL,
    mat_id              TEXT    NOT NULL,          -- text code (non-unique: many rows)

    -- Which property this record traces. property_name ONLY -- schema-evolution safe.
    property_name       TEXT    NOT NULL,          -- e.g. 'rho_loose'
    units               TEXT,                       -- e.g. 'kg/m3', 'deg'

    -- The two values, distinct meanings
    source_value        TEXT,                       -- what the source published (historical)
    accepted_value      TEXT,                       -- what VECTRIX adopted (echoed in core)

    -- Source information
    source_type         TEXT,
    source_name         TEXT,                       -- e.g. 'CEMA Standard 550'
    source_document     TEXT,
    source_edition      TEXT,                       -- e.g. '7th Edition'
    page_number         TEXT,
    table_number        TEXT,
    figure_number       TEXT,

    -- Decision / confidence
    decision_type       TEXT,                       -- published/measured/calculated/estimated/overridden
    override_reason     TEXT,                       -- required in spirit when decision_type='overridden'
    confidence          INTEGER,                    -- 1..5 (5=published standard, 1=user entry)
    verification_status TEXT,

    -- Date tracking / people
    entered_by          TEXT,
    entered_date        TEXT,                       -- ISO date
    verified_by         TEXT,
    verified_date       TEXT,
    review_due          TEXT,

    -- State
    is_current          INTEGER NOT NULL DEFAULT 0, -- produced today's engineering value?
    is_active           INTEGER NOT NULL DEFAULT 1, -- is the source still valid?

    comments            TEXT,

    FOREIGN KEY (material_id) REFERENCES materials_v2(material_id) ON DELETE CASCADE,

    CONSTRAINT chk_source_type  CHECK (source_type IS NULL OR source_type IN
        ({", ".join("'"+s+"'" for s in SOURCE_TYPE)})),
    CONSTRAINT chk_decision     CHECK (decision_type IS NULL OR decision_type IN
        ({", ".join("'"+d+"'" for d in DECISION_TYPE)})),
    CONSTRAINT chk_verif        CHECK (verification_status IS NULL OR verification_status IN
        ({", ".join("'"+v+"'" for v in VERIFICATION_STATUS)})),
    CONSTRAINT chk_confidence   CHECK (confidence IS NULL OR (confidence >= 1 AND confidence <= 5)),
    CONSTRAINT chk_is_current   CHECK (is_current IN (0,1)),
    CONSTRAINT chk_is_active    CHECK (is_active IN (0,1))
) STRICT;
"""

# A partial UNIQUE index enforcing: at most ONE is_current=1 row per (material, property).
# This is the integrity rule that makes is_current meaningful -- you cannot have two
# records both claiming to have produced today's value for the same property.
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_src_mat_id   ON material_sources(mat_id);",
    "CREATE INDEX IF NOT EXISTS idx_src_property ON material_sources(property_name);",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_src_current "
    "ON material_sources(material_id, property_name) WHERE is_current = 1;",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    if args.show:
        print(ddl()); [print(i) for i in INDEXES]; return 0

    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 37, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} too old for STRICT (need >=3.37).")
    print(f"SQLite {sqlite3.sqlite_version} -- STRICT supported.")

    con = sqlite3.connect(args.db)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='materials_v2'").fetchone():
            sys.exit("materials_v2 does not exist. Run create_materials_table.py first.")
        con.executescript(ddl())
        for ix in INDEXES:
            con.execute(ix)
        con.commit()
        is_strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='material_sources'").fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(material_sources)")]
        print(f"\nmaterial_sources created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO'}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())