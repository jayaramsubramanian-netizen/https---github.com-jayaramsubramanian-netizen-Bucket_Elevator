"""
backend/create_material_model_coefficients_table.py -- L3 of the frozen hierarchy:
material_model_coefficients.
═══════════════════════════════════════════════════════════════════════════
Engineering MODEL COEFFICIENTS -- calibration constants that let the VECTRIX
physics engine model a material accurately. NOT physical properties, NOT handling
characteristics, NOT solver outputs.

THE TEST (Jay): "If I improve the VECTRIX solver next year, could this value
change even though the material itself hasn't changed?" If yes -> it belongs here.
km, stream_spread_factor, wear_factor all pass: improve the model and they
re-tune, though Portland Cement is unchanged.

*** RELATIONSHIP: 1-to-MANY (this is the ONLY material table that is not 1:1) ***
One material has one coefficient set PER MODEL VERSION. The composite primary key
(material_id, model_version) is what makes that possible:

    material         model_version     km      stream_spread_factor
    Portland Cement  VECTRIX_BE_1.0    0.92    1.05
    Portland Cement  VECTRIX_BE_2.0    0.89    0.98

The material has not changed -- only the mathematical model. A single-column
material_id PK (as in the draft column list) would allow only ONE row per
material and make this versioning impossible, so the PK is composite. This is the
implementation of the versioning Jay specified in the philosophy section.

*** POPULATION: NONE IN PHASE 1 (Jay's instruction) ***
This table is created empty and STAYS empty through Phase 1. Its coefficients
must be EVIDENCE-BASED -- validated against OEM catalogs and known installations
during bucket-elevator validation -- not guessed constants. Phase 1 builds the
authoritative material database (materials/core/particles/handling) from CEMA 550
and documented sources; these calibration coefficients come only after the solver
has been validated against real data. Until then: all NULL.

stream_spread_factor here is the INPUT coefficient (material dispersion
tendency), NOT the calculated stream_spread the solver outputs (that is L4, never
stored).

STRICT + CHECK, composite FK to materials_v2, NULL always allowed.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

CALIBRATION_SOURCE = ["CEMA", "Lab Test", "OEM", "User", "Regression"]

# All coefficient columns (REAL, all nullable). Grouped by model for readability.
COEFF = [
    # Flow model
    "km","lambda_ref","flow_decay_factor","stream_spread_factor",
    "trajectory_drag_factor","trajectory_scatter_factor",
    # Bucket elevator model
    "bucket_loading_bias","inlet_capture_factor","discharge_bias",
    "centrifugal_bias","rollback_factor","material_retention_factor",
    # Screw conveyor model
    "screw_loading_bias","power_bias","torque_bias","axial_flow_factor",
    "leakage_factor","surcharge_decay_factor",
    # Belt conveyor model
    "surcharge_angle_bias","skirt_loss_factor","carryback_factor",
    "loading_profile_factor",
    # Wear model
    "wear_factor","impact_factor","abrasion_multiplier","degradation_factor",
    "fines_generation_factor",
    # DEM / particle interaction (model coefficients, not intrinsic properties)
    "rolling_factor","collision_damping_factor","cohesion_decay_factor",
    "agglomeration_factor",
]


def ddl() -> str:
    coeff_cols = "\n    ".join(f"{c:26s} REAL," for c in COEFF)
    return f"""
CREATE TABLE IF NOT EXISTS material_model_coefficients (
    material_id         INTEGER NOT NULL,
    model_version       TEXT    NOT NULL,        -- e.g. VECTRIX_BE_1.0
    mat_id              TEXT    NOT NULL,          -- text code (NOT unique here: many versions)

    -- Model metadata
    calibration_source  TEXT,
    calibration_date    TEXT,                      -- ISO date
    confidence_level    INTEGER,                   -- 1..5
    verified            INTEGER NOT NULL DEFAULT 0, -- 0/1

    -- Coefficients (all nullable; Phase 1 leaves ALL of these NULL)
    {coeff_cols}

    -- Calibration provenance
    regression_dataset  TEXT,
    sample_count        INTEGER,
    calibration_notes   TEXT,

    -- Composite PK: one row per (material, model version) -- enables versioning.
    PRIMARY KEY (material_id, model_version),
    FOREIGN KEY (material_id) REFERENCES materials_v2(material_id) ON DELETE CASCADE,

    CONSTRAINT chk_calib_source CHECK (calibration_source IS NULL OR calibration_source IN
        ({", ".join("'"+s+"'" for s in CALIBRATION_SOURCE)})),
    CONSTRAINT chk_confidence CHECK (confidence_level IS NULL OR (confidence_level >= 1 AND confidence_level <= 5)),
    CONSTRAINT chk_verified   CHECK (verified IN (0,1)),
    CONSTRAINT chk_samplecount CHECK (sample_count IS NULL OR sample_count >= 0)
) STRICT;
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_coeff_mat_id  ON material_model_coefficients(mat_id);",
    "CREATE INDEX IF NOT EXISTS idx_coeff_version ON material_model_coefficients(model_version);",
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
        is_strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='material_model_coefficients'").fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(material_model_coefficients)")]
        print(f"\nmaterial_model_coefficients created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO'}")
        print("PHASE 1: this table is created EMPTY and stays empty until OEM validation.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())