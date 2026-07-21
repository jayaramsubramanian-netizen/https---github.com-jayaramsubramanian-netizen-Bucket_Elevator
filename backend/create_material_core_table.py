"""
backend/create_material_core_table.py -- Table L2 of the frozen hierarchy:
material_core -- INTRINSIC physical, flow, and behavioral-classification
properties of a bulk material.
═══════════════════════════════════════════════════════════════════════════
THE STORAGE RULE (frozen -- applies to every material table)
────────────────────────────────────────────────────────────
For every field, ask in order:
  1. Identity / classification?            -> materials
  2. Intrinsic -- true for 1 kg sent to ANY machine (bucket, screw, belt,
     hopper, air classifier)?              -> material_core / _particles / _handling
  3. A coefficient tuning a VECTRIX model? -> material_model_coefficients (versioned)
  4. Computed from machine geometry, operating conditions, or the solver?
                                           -> NOT STORED. Solver output only.

material_core holds ONLY level 2: intrinsic physical properties, intrinsic flow
properties, and intrinsic behavioral CLASSIFICATIONS. It contains NO model
coefficients (Km, lambda_ref, stream_spread_factor -> material_model_coefficients),
NO equipment defaults, and NO calculated outputs (bucket_fill_factor is L4 -- it
depends on bucket style/speed/feed geometry, so it is NEVER stored; it becomes a
solver output computed from an L3 fill-factor range).

CANONICAL NAMES (Strategy B -- frozen)
──────────────────────────────────────
The backend field names ARE the canonical VECTRIX engineering field names. `mat`
is passed through every solver with dozens of established reads, including hard
lookups (mat["rho_loose"]) that crash if renamed. The database speaks the
backend's language, not the reverse. So: rho_loose, rho_bulk, rho_vib, rho_min,
rho_max, angle_repose, angle_surcharge, cohesion, moisture, temp_max,
particle_class, particle_size_mm, flowability, flow_regime -- unchanged.

This table feeds a future Material() object (the "intelligence layer") at cutover:
Material.rho_bulk will return rho_bulk or rho_loose or rho_vib depending on what
is populated, so a missing field yields a sensible value instead of a KeyError --
retiring the hard-lookup crash class. The columns are named to map 1:1 onto that
object.

flowability vs flow_regime -- BOTH kept, independently (Jay):
  flowability : INTEGER engineering index (1=excellent .. 4=poor) -- what
                calculations use.
  flow_regime : TEXT categorical class (Free Flowing / Cohesive / Flooding /
                Aerated / ...) -- for reports, UI, filtering. NOT derived from
                flowability: a material can share a flowability index but differ
                in regime (e.g. aerated vs flooding).
  flowability_method : traceability -- HOW flowability was determined
                (CEMA550 / Jenike / ASTM / User / Vectrix). Does not affect the
                solver.

STRICT + CHECK, FK to materials_v2 (integer PK), mat_id carried UNIQUE. NULL is
always allowed -- most fields will legitimately be blank until sourced, to be
flagged for resolution at design time.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

# Intrinsic behavioral classifications (vocabularies evolve; constrained, NULL ok)
PARTICLE_CLASS = ["A", "B", "C", "D"]                       # CEMA lump size
FLOW_REGIME = ["Free Flowing", "Easy Flowing", "Average Flowing", "Sluggish",
               "Cohesive", "Very Cohesive", "Flooding", "Aerated",
               "Bridging", "Segregating"]
FLOWABILITY_METHOD = ["CEMA550", "Jenike", "ASTM", "User", "Vectrix"]


def _in_list(col, values):
    joined = ", ".join(f"'{v}'" for v in values)
    return f"({col} IS NULL OR {col} IN ({joined}))"


def ddl() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS material_core (
    material_id         INTEGER PRIMARY KEY,          -- 1:1 FK -> materials_v2
    mat_id              TEXT    NOT NULL UNIQUE,       -- canonical text code

    -- Density (SI, kg/m3). loose / operating / vibrated kept DISTINCT --
    -- they diverge for air-classifier & dryer modules.
    rho_loose           REAL,   -- loose-poured bulk density
    rho_bulk            REAL,   -- operating bulk density
    rho_vib             REAL,   -- vibrated / tapped density
    rho_min             REAL,   -- range support
    rho_max             REAL,   -- range support
    specific_gravity    REAL,   -- dimensionless

    -- Moisture (%)
    moisture            REAL,
    moisture_max        REAL,
    free_moisture       REAL,

    -- Size classification (intrinsic)
    particle_class          TEXT,   -- CEMA lump class A/B/C/D
    particle_size_mm        REAL,
    maximum_lump_size       REAL,   -- mm

    -- Flow angles (true material properties, degrees)
    angle_repose            REAL,
    angle_surcharge         REAL,
    dynamic_angle_repose    REAL,

    -- Flow classification (intrinsic) -- numeric index AND categorical regime,
    -- kept independent. flowability_method for traceability.
    flowability             INTEGER,   -- 1=excellent .. 4=poor
    flow_regime             TEXT,
    flowability_method      TEXT,

    -- Intrinsic physical behaviour
    cohesion                REAL,   -- cohesion index
    compressibility         REAL,
    porosity                REAL,
    void_fraction           REAL,

    -- Mechanical
    mohs_hardness           REAL,

    -- Thermal (intrinsic bound; dryers/coolers later)
    temp_max                REAL,   -- degC

    FOREIGN KEY (material_id) REFERENCES materials_v2(material_id) ON DELETE CASCADE,

    CONSTRAINT chk_pclass    CHECK {_in_list('particle_class', PARTICLE_CLASS)},
    CONSTRAINT chk_regime    CHECK {_in_list('flow_regime', FLOW_REGIME)},
    CONSTRAINT chk_flowmeth  CHECK {_in_list('flowability_method', FLOWABILITY_METHOD)},
    CONSTRAINT chk_flowidx   CHECK (flowability IS NULL OR (flowability >= 1 AND flowability <= 4)),

    -- physical sanity (NULL always allowed)
    CONSTRAINT chk_rho_loose CHECK (rho_loose IS NULL OR rho_loose > 0),
    CONSTRAINT chk_rho_bulk  CHECK (rho_bulk  IS NULL OR rho_bulk  > 0),
    CONSTRAINT chk_moist     CHECK (moisture  IS NULL OR (moisture >= 0 AND moisture <= 100)),
    CONSTRAINT chk_moist_max CHECK (moisture_max IS NULL OR (moisture_max >= 0 AND moisture_max <= 100)),
    CONSTRAINT chk_repose    CHECK (angle_repose IS NULL OR (angle_repose >= 0 AND angle_repose <= 90)),
    CONSTRAINT chk_surcharge CHECK (angle_surcharge IS NULL OR (angle_surcharge >= 0 AND angle_surcharge <= 90)),
    CONSTRAINT chk_porosity  CHECK (porosity IS NULL OR (porosity >= 0 AND porosity <= 1)),
    CONSTRAINT chk_void      CHECK (void_fraction IS NULL OR (void_fraction >= 0 AND void_fraction <= 1)),
    CONSTRAINT chk_mohs      CHECK (mohs_hardness IS NULL OR (mohs_hardness >= 0 AND mohs_hardness <= 10))
) STRICT;
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_core_mat_id      ON material_core(mat_id);",
    "CREATE INDEX IF NOT EXISTS idx_core_pclass      ON material_core(particle_class);",
    "CREATE INDEX IF NOT EXISTS idx_core_flowability ON material_core(flowability);",
    "CREATE INDEX IF NOT EXISTS idx_core_regime      ON material_core(flow_regime);",
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
        is_strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='material_core'").fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(material_core)")]
        print(f"\nmaterial_core created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO'}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())