"""
backend/create_material_handling_table.py -- L2.75 of the frozen hierarchy:
material_handling.
═══════════════════════════════════════════════════════════════════════════
Answers ONE question: "How does this material BEHAVE during handling?" Not its
physical properties (material_core), not its PSD (material_particles), not its
power draw (solver). This is the table that most resembles CEMA 550 itself.

THREE CLASSES OF FIELD (Jay's design):
  Class 1  Graded (ordinal severity)  -- abr_code, dust_level, stickiness_index...
           Stickiness/bridging/caking are rarely binary, so they are graded.
  Class 2  Binary (genuine yes/no)    -- sticky, corrosive, hygroscopic...
           INTEGER CHECK(v IN (0,1)). NO flag+level pairs anywhere -- one
           representation per property, so 'sticky=0 while stickiness_index=4'
           is impossible.
  Class 3  Descriptors / tendencies   -- handling_notes, arch_tendency...

NO flag+level pairs: abrasion is ONLY abr_code (graded); stickiness is graded
(stickiness_index) OR binary (sticky) but the two describe different granularity
and both are allowed to coexist meaningfully (sticky = is it sticky at all;
stickiness_index = how much). abrasion has no boolean twin -- abr_code alone.

CANONICAL NAME: abr_code preserved (the ONLY handling field the solver reads
today -- int(mat.get("abr_code", 3)), scale 1..7). Everything else here is new;
the solver does not read it yet, so these names become canonical going forward.

REMOVED from Jay's draft (his own final call): flow_condition -- it would
duplicate material_core.flow_regime. Intrinsic flow classification stays in core;
this table is strictly handling behaviour and operational tendencies.

SEED CONFIDENCE (recorded in field dictionary, not enforced):
  CEMA 550         : abr_code, sticky, corrosive, hygroscopic, fibrous, friable,
                     free_flowing, bridges, cakes, segregates, explosive, notes
  Eng. judgment/OEM: dust_level, stickiness_index, bridging_index, caking_index,
                     fluidization_index, wear_mode
  Future/measured  : arch_tendency, rathole_tendency, flooding_tendency,
                     particle_breakdown, dust_generation, static_prone

STRICT + CHECK, FK to materials_v2, mat_id UNIQUE, NULL always allowed.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

# Class 1 graded fields and their valid ranges. abr_code is 1..7 (CEMA/backend);
# the rest are 0..5 (0 = none).
GRADED = {
    "abr_code":           (1, 7),
    "dust_level":         (0, 5),
    "corrosion_level":    (0, 5),
    "stickiness_index":   (0, 5),
    "bridging_index":     (0, 5),
    "caking_index":       (0, 5),
    "segregation_index":  (0, 5),
    "fluidization_index": (0, 5),
}

# Class 2 binary fields
BINARY = [
    "sticky","corrosive","hygroscopic","fibrous","friable","interlocking",
    "free_flowing","aerates","packs","bridges","cakes","segregates","smears",
    "degradable","oxidizing","toxic","explosive","food_grade","recyclable",
    # wear/static/storage binaries
    "impact_sensitive","particle_breakdown","dust_generation",
    "static_prone","conductive","grounding_required",
    "long_term_caking","temperature_sensitive","freeze_sensitive",
]

# ordinal tendencies (0..5), Class 3-ish but numeric
TENDENCY = ["angle_stability","arch_tendency","rathole_tendency",
            "flooding_tendency","moisture_absorption"]

WEAR_MODE = ["Impact","Sliding","Abrasive","Erosive","Mixed"]


def ddl() -> str:
    graded_cols = "\n    ".join(f"{f:20s} INTEGER," for f in GRADED)
    binary_cols = "\n    ".join(f"{f:22s} INTEGER," for f in BINARY)
    tend_cols   = "\n    ".join(f"{f:20s} INTEGER," for f in TENDENCY)

    graded_chk = ",\n    ".join(
        f"CONSTRAINT chk_{f} CHECK ({f} IS NULL OR ({f} >= {lo} AND {f} <= {hi}))"
        for f,(lo,hi) in GRADED.items())
    binary_chk = ",\n    ".join(
        f"CONSTRAINT chk_{f} CHECK ({f} IS NULL OR {f} IN (0,1))" for f in BINARY)
    tend_chk = ",\n    ".join(
        f"CONSTRAINT chk_{f} CHECK ({f} IS NULL OR ({f} >= 0 AND {f} <= 5))" for f in TENDENCY)

    return f"""
CREATE TABLE IF NOT EXISTS material_handling (
    material_id  INTEGER PRIMARY KEY,          -- 1:1 FK -> materials_v2
    mat_id       TEXT    NOT NULL UNIQUE,

    -- Class 1: graded severity (ordinal). abr_code 1..7; others 0..5.
    {graded_cols}

    -- Class 2: binary yes/no (0 or 1). No flag+level contradictions possible.
    {binary_cols}

    -- Flow / storage tendencies (ordinal 0..5)
    {tend_cols}

    -- Class 3: descriptors for reports & engineering documentation
    wear_mode         TEXT,
    handling_notes    TEXT,
    storage_notes     TEXT,
    conveying_notes   TEXT,

    FOREIGN KEY (material_id) REFERENCES materials_v2(material_id) ON DELETE CASCADE,
    CONSTRAINT chk_wear_mode CHECK (wear_mode IS NULL OR wear_mode IN
        ({", ".join("'"+w+"'" for w in WEAR_MODE)})),
    {graded_chk},
    {binary_chk},
    {tend_chk}
) STRICT;
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_handling_mat_id   ON material_handling(mat_id);",
    "CREATE INDEX IF NOT EXISTS idx_handling_abr_code ON material_handling(abr_code);",
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
        is_strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='material_handling'").fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(material_handling)")]
        print(f"\nmaterial_handling created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO'}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())