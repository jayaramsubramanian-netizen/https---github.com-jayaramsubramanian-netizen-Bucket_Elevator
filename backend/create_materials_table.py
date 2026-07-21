"""
backend/create_materials_table.py -- Table 1 of 7: the bulk-material IDENTITY table.
═══════════════════════════════════════════════════════════════════════════
Part of the clean-rebuild of the material database. This table holds ONE record
per bulk material and carries ONLY identity + classification -- no engineering
values (density, angle of repose, fill factor, ...). Those live in tables 2-7,
linked by mat_id, so a material's identity is stable while its engineering data
can be revised independently and reused across every VECTRIX module.

WHY A FRESH TABLE, NOT AN ALTER OF THE OLD ONE
──────────────────────────────────────────────
The existing `materials` table has 864 rows that are two diverged CEMA extracts
(380 BE + 474 SC) with: mangled escaped-JSON in `app`/`hazard_codes`, empty
`cema_code` on all BE rows, NULL `particle_class` throughout, and conflicting
densities for the same material across the two extracts. It cannot be trusted as
a base. This builds the correct schema empty, to be populated deliberately from
the source-of-truth documents (CEMA 550 and others), with blanks flagged for the
engineer to resolve at design time.

The new table is named `materials_v2` so it can be built and populated ALONGSIDE
the live `materials` table without breaking the running app. The cutover (point
the API + ORM at v2, drop the old table) is a separate, deliberate step once v2
is populated and verified.

STRICT + CHECK -- the whole point of the rebuild
────────────────────────────────────────────────
SQLite is dynamically typed by default: that is HOW the old table accepted
'["be"]' as a string into a column meant for a tag, and mangled JSON into
hazard_codes. This table is declared STRICT (SQLite >= 3.37): every value must
match its declared type or the write is REJECTED. Enum columns carry CHECK
constraints against the lookup lists, so an out-of-vocabulary category (a typo)
is refused at write time rather than silently creating a new category. This is
the integrity the old table lacked.

FIELD-NAME RECONCILIATION (vs the existing backend, per Jay's review)
─────────────────────────────────────────────────────────────────────
  material_id        <- new surrogate PK (old table used `id`)
  mat_id             <- KEPT (Jay's decision). This IS the `material_code`
                        concept -- a short stable internal code (clinker_cement).
                        Renaming would break /materials/{mat_id} and every FK, for
                        no gain. Declared UNIQUE.
  material_name      <- old `name`. (Backend reads mat.get("name") in ~4 places;
                        those get updated at cutover, not now.)
  cema_material_code <- old `cema_code`
  description        <- old `note`
  category           <- KEPT (exact match)
  material_class     <- NEW form-factor axis (Powder/Granular/...). Deliberately
                        DISTINCT from the engineering table's `particle_class`
                        (CEMA lump size A/B/C/D) -- different axis, do not merge.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

# Lookup vocabularies (Jay's spec). CHECK constraints are built from these, so
# the DB itself rejects any value not in the list. NULL is allowed (a blank to be
# resolved at design time) -- only NON-NULL out-of-vocabulary values are refused.
CATEGORY = ["Cement","Mining","Aggregates","Coal","Power","Agriculture","Food",
            "Chemical","Petrochemical","Steel","Wood","Biomass","Waste",
            "Recycling","Ceramics","Glass","Fertilizer","Pharmaceutical","Other"]
MATERIAL_CLASS = ["Powder","Fine Powder","Granular","Pellet","Crystal","Flake",
                  "Chip","Fiber","Lump","Slurry","Paste","Liquid","Mixed"]
MATERIAL_FAMILY = ["Mineral","Organic","Metal","Agricultural","Chemical",
                   "Synthetic","Recycled"]
SOURCE_STANDARD = ["CEMA 550","CEMA 350","ASTM","OEM","User","Other"]


def _in_list(col, values):
    """Build a CHECK that allows NULL or a value from the list."""
    joined = ", ".join(f"'{v}'" for v in values)
    return f"({col} IS NULL OR {col} IN ({joined}))"


def ddl() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS materials_v2 (
    material_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    mat_id              TEXT    NOT NULL UNIQUE,   -- short stable code: clinker_cement
    material_name       TEXT    NOT NULL,          -- official display name
    common_name         TEXT,                      -- alternate / common name
    category            TEXT,
    subcategory         TEXT,                      -- Clinker, Fly Ash, Limestone...
    cema_material_code  TEXT,                      -- full CEMA code, e.g. 100B36M
    material_class      TEXT,                      -- form factor (Powder/Granular/...)
    material_family     TEXT,
    description         TEXT,
    source_standard     TEXT,
    source_reference    TEXT,                      -- table / page / report
    source_revision     TEXT,                      -- edition or revision
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_date        TEXT,                      -- ISO datetime
    modified_date       TEXT,                      -- ISO datetime
    revision            INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT chk_category       CHECK {_in_list('category', CATEGORY)},
    CONSTRAINT chk_material_class CHECK {_in_list('material_class', MATERIAL_CLASS)},
    CONSTRAINT chk_material_family CHECK {_in_list('material_family', MATERIAL_FAMILY)},
    CONSTRAINT chk_source         CHECK {_in_list('source_standard', SOURCE_STANDARD)},
    CONSTRAINT chk_is_active      CHECK (is_active IN (0, 1)),
    CONSTRAINT chk_revision       CHECK (revision >= 1)
) STRICT;
"""


INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_material_name     ON materials_v2(material_name);",
    "CREATE INDEX IF NOT EXISTS idx_material_category ON materials_v2(category);",
    "CREATE INDEX IF NOT EXISTS idx_material_cema     ON materials_v2(cema_material_code);",
    "CREATE INDEX IF NOT EXISTS idx_material_class    ON materials_v2(material_class);",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--show", action="store_true", help="print the DDL and exit")
    args = ap.parse_args()

    if args.show:
        print(ddl()); [print(i) for i in INDEXES]; return 0

    # STRICT requires SQLite >= 3.37
    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 37, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} is too old for STRICT tables "
                 f"(need >= 3.37). Upgrade Python/SQLite.")
    print(f"SQLite {sqlite3.sqlite_version} -- STRICT supported.")

    con = sqlite3.connect(args.db)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript(ddl())
        for ix in INDEXES:
            con.execute(ix)
        con.commit()

        # confirm it's really STRICT and the constraints exist
        is_strict = con.execute(
            "SELECT strict FROM pragma_table_list WHERE name='materials_v2'"
        ).fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(materials_v2)")]
        print(f"\nmaterials_v2 created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO -- check!'}")
        print("columns:", ", ".join(cols))

        # prove the CHECK actually rejects a bad category
        try:
            con.execute("INSERT INTO materials_v2(mat_id, material_name, category) "
                        "VALUES ('__test__', 'Test', 'NotACategory')")
            print("!! CHECK did NOT fire -- constraint is not working")
            con.execute("DELETE FROM materials_v2 WHERE mat_id='__test__'")
        except sqlite3.IntegrityError:
            print("CHECK verified: an out-of-vocabulary category was rejected.")
        con.commit()
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())