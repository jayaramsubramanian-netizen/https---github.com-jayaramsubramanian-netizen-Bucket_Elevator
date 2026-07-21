"""
backend/create_material_particles_table.py -- L2.5 of the frozen hierarchy:
material_particles  (documentation name: Particle Characterization table).
═══════════════════════════════════════════════════════════════════════════
Everything that describes the PARTICLES THEMSELVES -- not the bulk material, not
the flow, not the equipment. PSD, size limits, distribution statistics, shape,
surface, composition-by-size, integrity, and particle-scale DEM inputs.

Split from material_core by ACCESS PATTERN: the bucket-elevator solver never
joins this table (it uses maximum_lump_size / particle_size_mm from core). Air
classifiers use d10/d50/d90; mills use the full PSD; DEM uses the particle-scale
friction/restitution fields here. Keeping them out of core keeps the elevator's
hot path lean while the schema stays complete for future modules.

DE-DUPLICATION (Jay -- these stay in material_core, NOT here):
  maximum_lump_size   -> core (engineering property used by conveyors)
  particle_size_mm    -> core
  particle_shape      -> core (categorical: Angular/Rounded/Fibrous)
This table stores the QUANTITATIVE particle values (sphericity=0.81), not the
categorical class.

STORAGE RULE: every field here is an INTRINSIC particle property (level 2) --
true for 1 kg of this material sent to any machine. DEM fields
(rolling_friction, restitution_coefficient, ...) live here, NOT in a separate DEM
table, because they are PARTICLE properties that DEM happens to consume.

MATURITY TIERS (Jay) -- the schema is complete now; the SEED populates by tier:
  A  populate now  : maximum_particle_size, nominal_top_size, mean_particle_size,
                     fines_percent (where available)
  B  as data comes : d10..d99, passing_* fractions, uniformity/span
  C  future modules: rolling/sliding friction, restitution, surface_energy,
                     breakage/attrition indices
Tiers are recorded in the field dictionary, not enforced by the DB.

STRICT + CHECK, FK to materials_v2, mat_id carried UNIQUE, NULL always allowed.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

PSD_METHOD = ["Sieve", "LaserDiffraction", "ImageAnalysis", "Sedimentation",
              "Calculated", "User"]

# fields that are a percentage 0..100 -> get a range CHECK
PCT_FIELDS = [
    "passing_75um","passing_150um","passing_300um","passing_600um",
    "passing_1mm","passing_2mm","passing_5mm","passing_10mm","passing_20mm","passing_50mm",
    "fines_percent","coarse_percent","oversize_percent","undersize_percent",
]
# fields that are a 0..1 fraction/ratio -> range CHECK
FRAC_FIELDS = ["sphericity","roundness","restitution_coefficient","surface_porosity"]


def _pct_checks():
    return ",\n    ".join(
        f"CONSTRAINT chk_{f} CHECK ({f} IS NULL OR ({f} >= 0 AND {f} <= 100))"
        for f in PCT_FIELDS)

def _frac_checks():
    return ",\n    ".join(
        f"CONSTRAINT chk_{f} CHECK ({f} IS NULL OR ({f} >= 0 AND {f} <= 1))"
        for f in FRAC_FIELDS)


def ddl() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS material_particles (
    material_id     INTEGER PRIMARY KEY,          -- 1:1 FK -> materials_v2
    mat_id          TEXT    NOT NULL UNIQUE,

    -- Section 1: PSD (mm) -- ISO 13320 / ASTM E11 style
    d10 REAL, d20 REAL, d30 REAL, d40 REAL, d50 REAL,
    d60 REAL, d70 REAL, d80 REAL, d90 REAL, d95 REAL, d99 REAL,

    -- Section 2: size limits (mm). maximum_lump_size + particle_size_mm stay in core.
    minimum_particle_size   REAL,
    mean_particle_size      REAL,
    median_particle_size    REAL,
    maximum_particle_size   REAL,
    nominal_top_size        REAL,

    -- Section 3: distribution statistics
    uniformity_coefficient  REAL,
    curvature_coefficient   REAL,
    gradation_index         REAL,
    span                    REAL,
    sorting_coefficient     REAL,

    -- Section 4: shape (quantitative). particle_shape (categorical) stays in core.
    aspect_ratio            REAL,
    sphericity              REAL,   -- 0..1
    roundness               REAL,   -- 0..1
    angularity              REAL,
    elongation              REAL,
    flatness                REAL,
    flake_index             REAL,
    elongation_index        REAL,

    -- Section 5: surface
    surface_texture         TEXT,
    surface_roughness       REAL,
    specific_surface_area   REAL,   -- m2/g or m2/kg (record unit at seed)
    surface_porosity        REAL,   -- 0..1
    surface_energy          REAL,

    -- Section 6: composition by size (% passing)
    passing_75um  REAL, passing_150um REAL, passing_300um REAL, passing_600um REAL,
    passing_1mm   REAL, passing_2mm   REAL, passing_5mm   REAL, passing_10mm  REAL,
    passing_20mm  REAL, passing_50mm  REAL,

    -- Section 7: fractions (%)
    fines_percent      REAL,
    coarse_percent     REAL,
    oversize_percent   REAL,
    undersize_percent  REAL,

    -- Section 8: particle integrity (wear/degradation models later)
    friability_index   REAL,
    breakage_index     REAL,
    attrition_index    REAL,
    abrasion_index     REAL,

    -- Section 9: DEM particle-scale inputs (Tier C)
    rolling_friction        REAL,
    sliding_friction        REAL,
    restitution_coefficient REAL,   -- 0..1
    rolling_resistance      REAL,
    particle_density        REAL,   -- kg/m3 (true/solid density, not bulk)
    poissons_ratio          REAL,

    -- traceability
    psd_method              TEXT,

    FOREIGN KEY (material_id) REFERENCES materials_v2(material_id) ON DELETE CASCADE,
    CONSTRAINT chk_psd_method CHECK (psd_method IS NULL OR psd_method IN
        ({", ".join("'"+m+"'" for m in PSD_METHOD)})),
    CONSTRAINT chk_poisson CHECK (poissons_ratio IS NULL OR (poissons_ratio > -1 AND poissons_ratio < 0.5)),
    {_pct_checks()},
    {_frac_checks()}
) STRICT;
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_part_mat_id ON material_particles(mat_id);",
    "CREATE INDEX IF NOT EXISTS idx_part_d50    ON material_particles(d50);",
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
        is_strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='material_particles'").fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(material_particles)")]
        print(f"\nmaterial_particles created: {len(cols)} columns, "
              f"STRICT={'yes' if is_strict and is_strict[0] else 'NO'}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())