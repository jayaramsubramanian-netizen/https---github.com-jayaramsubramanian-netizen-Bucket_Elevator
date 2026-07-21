"""
backend/create_material_hazards_table.py -- Table 7 (Level 2B): material_hazards.
═══════════════════════════════════════════════════════════════════════════
SAFETY, REGULATORY, and COMPLIANCE metadata -- a fundamentally different CLASS of
information from engineering or handling properties.

WHY STANDALONE (Jay's Level 2B reasoning):
Handling descriptors (sticky, bridges, abrasive) change the ENGINEERING
CALCULATION. Hazards do NOT. Corn starch's horsepower is identical whether or not
it is combustible dust -- but its EQUIPMENT SPECIFICATION changes dramatically
(explosion vents, ATEX motor, spark detection, speed/alignment switches,
anti-static belt). Hazards therefore have a different audience (Safety /
Compliance), a different lifecycle (regulatory revisions), and a different
consumer (the future automatic specification generator), so they are a sibling of
material_handling, not part of it.

The solver does NOT read this table for sizing. The specification generator and
compliance/reporting layers do. Example output it enables:
  "Material is classified as combustible dust (Kst=165 bar.m/s, Pmax=8.6 bar).
   Recommend explosion venting, ATEX-compliant electrical equipment, belt
   alignment monitoring, and speed monitoring per applicable standards."

This is the SEVENTH and final foundational material table. Per Jay: no further
foundational material tables after these seven -- equipment-specific data lives in
its own modules referencing material_id.

STRICT + CHECK, 1:1 FK to materials_v2, mat_id UNIQUE, NULL always allowed
(most hazard fields blank until sourced from SDS / NFPA / test data).
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

# St dust-explosion class (ISO/IEC): St0 (none), St1, St2, St3
DUST_CLASS = ["St0", "St1", "St2", "St3"]
# NFPA 704 ratings are 0..4 on health/flammability/reactivity (handled via CHECK)
FIRE_CLASS = ["A", "B", "C", "D", "K"]          # NFPA fire classes
BINARY = [
    "combustible_dust","flammable","oxidizer","toxic","carcinogenic",
    "respiratory_hazard","skin_irritant","eye_irritant","environmental_hazard",
    "water_reactive","air_reactive","corrosive","radioactive",
]


def ddl() -> str:
    binary_cols = "\n    ".join(f"{f:22s} INTEGER," for f in BINARY)
    binary_chk = ",\n    ".join(
        f"CONSTRAINT chk_{f} CHECK ({f} IS NULL OR {f} IN (0,1))" for f in BINARY)
    return f"""
CREATE TABLE IF NOT EXISTS material_hazards (
    material_id     INTEGER PRIMARY KEY,          -- 1:1 FK -> materials_v2
    mat_id          TEXT    NOT NULL UNIQUE,

    -- Dust explosion (combustible dust parameters)
    combustible_dust        INTEGER,               -- 0/1
    dust_class              TEXT,                   -- St0/St1/St2/St3
    kst                     REAL,                   -- bar.m/s  (deflagration index)
    pmax                    REAL,                   -- bar      (max explosion pressure)
    mec                     REAL,                   -- g/m3     (min explosible concentration)
    mit_cloud               REAL,                   -- degC     (min ignition temp, cloud)
    mit_layer               REAL,                   -- degC     (min ignition temp, layer)
    minimum_ignition_energy REAL,                   -- mJ

    -- Fire
    flash_point             REAL,                   -- degC
    autoignition_temperature REAL,                  -- degC
    fire_class              TEXT,                   -- NFPA A/B/C/D/K
    flammable               INTEGER,                -- 0/1
    oxidizer                INTEGER,                -- 0/1

    -- Health
    toxic                   INTEGER,
    carcinogenic            INTEGER,
    respiratory_hazard      INTEGER,
    skin_irritant           INTEGER,
    eye_irritant            INTEGER,
    osha_class              TEXT,

    -- Environmental
    environmental_hazard    INTEGER,
    water_reactive          INTEGER,
    air_reactive            INTEGER,
    corrosive               INTEGER,
    radioactive             INTEGER,

    -- Compliance / references
    sds_reference           TEXT,
    nfpa_health             INTEGER,                -- NFPA 704: 0..4
    nfpa_flammability       INTEGER,                -- 0..4
    nfpa_reactivity         INTEGER,                -- 0..4
    nfpa_special            TEXT,                   -- OX / W / SA etc.
    atex_zone               TEXT,                   -- e.g. 'Zone 20/21/22'
    ghs_classification      TEXT,
    un_number               TEXT,

    hazard_notes            TEXT,

    FOREIGN KEY (material_id) REFERENCES materials_v2(material_id) ON DELETE CASCADE,

    CONSTRAINT chk_dust_class CHECK (dust_class IS NULL OR dust_class IN
        ({", ".join("'"+d+"'" for d in DUST_CLASS)})),
    CONSTRAINT chk_fire_class CHECK (fire_class IS NULL OR fire_class IN
        ({", ".join("'"+f+"'" for f in FIRE_CLASS)})),
    CONSTRAINT chk_nfpa_h CHECK (nfpa_health IS NULL OR (nfpa_health >= 0 AND nfpa_health <= 4)),
    CONSTRAINT chk_nfpa_f CHECK (nfpa_flammability IS NULL OR (nfpa_flammability >= 0 AND nfpa_flammability <= 4)),
    CONSTRAINT chk_nfpa_r CHECK (nfpa_reactivity IS NULL OR (nfpa_reactivity >= 0 AND nfpa_reactivity <= 4)),
    CONSTRAINT chk_kst  CHECK (kst  IS NULL OR kst  >= 0),
    CONSTRAINT chk_pmax CHECK (pmax IS NULL OR pmax >= 0),
    {binary_chk}
) STRICT;
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_haz_mat_id      ON material_hazards(mat_id);",
    "CREATE INDEX IF NOT EXISTS idx_haz_combustible ON material_hazards(combustible_dust);",
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
        is_strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='material_hazards'").fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(material_hazards)")]
        print(f"\nmaterial_hazards created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO'}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())