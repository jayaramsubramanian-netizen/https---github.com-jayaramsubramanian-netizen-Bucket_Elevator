"""
seed_all.py — VECTRIX full catalog seed script.

Reads a JSON export (vectrix_db_export.json) and upserts every row into
vectrix.db via the SQLAlchemy ORM. Idempotent: safe to re-run, updates
existing rows in place by their natural key, never duplicates.

Replaces seed_catalog.py (which only seeded buckets + material_grades).

Usage:
    cd backend && python seed_all.py [path/to/vectrix_db_export.json]

If no path is given, defaults to vectrix_export/vectrix_db_export.json
relative to the current working directory.
"""

import json
import sys
from pathlib import Path

from vectrix_database import SessionLocal, create_tables
from vectrix_tables import (
    Material,
    Bucket,
    Bearing,
    Motor,
    Gearbox,
    Drive,
    Belt,
    Screw,
    Bolt,
    CostItem,
    MaterialGrade,
)

DEFAULT_JSON_PATH = "vectrix_export/vectrix_db_export.json"

# table_name -> (ORM class, upsert key column, list of non-id columns)
TABLE_SPECS = {
    "materials": (
        Material,
        "mat_id",
        [
            "mat_id", "name", "category", "category_full", "rho_bulk", "rho_min",
            "rho_max", "rho_vib", "rho_sc_tm3", "flowability", "flowability_raw",
            "angle_repose", "angle_surcharge", "angle_internal_friction",
            "wall_friction_deg", "cohesion", "bridging_risk", "flow_regime",
            "moisture_pct", "temp_max", "abr_code", "abr_text", "particle_class",
            "size_code", "particle_size_mm", "Leq_default", "Ceff_default", "vfi",
            "bucket_fill_factor", "stream_spread_factor", "Km", "hazard_codes",
            "lambda_ref", "fill_max", "cema_cls", "cema_code", "flags", "confidence",
            "source", "note", "app", "custom",
        ],
    ),
    "buckets": (
        Bucket,
        "bucket_id",
        [
            "bucket_id", "style", "catalog", "W_mm", "H_mm", "P_mm", "V_L",
            "front_angle_deg", "type", "discharge_type", "v_min", "v_max", "v_opt",
            "pitch_mm", "bucket_mass_kg", "recommended_materials", "note", "punch",
            "boltA_mm", "boltB_mm", "boltDia_mm", "boltN", "punch_confirmed", "custom",
        ],
    ),
    "bearings": (
        Bearing,
        "name",
        [
            "name", "mfr", "type", "bore", "od", "B", "C", "C0", "p", "speed_g",
            "seal", "role", "brg_insert", "mass_kg", "note", "custom",
        ],
    ),
    "motors": (
        Motor,
        "model",
        [
            "model", "frame", "Pkw", "poles", "rpm_50hz", "efficiency", "ie_class",
            "ip", "mass_kg", "note", "custom",
        ],
    ),
    "gearboxes": (
        Gearbox,
        "model",
        [
            "model", "type", "stages", "Tn", "Pkw", "ratio_min", "ratio_max", "eta",
            "mount", "ip", "temp_max", "mass_kg", "note", "custom",
        ],
    ),
    "drives": (
        Drive,
        "model",
        [
            "model", "type", "Pkw_max", "Vrated", "Irated", "overload_pct",
            "control", "ip", "features", "note", "custom",
        ],
    ),
    "belts": (
        Belt,
        "model",
        [
            "model", "belt_type", "ply_or_cord", "rating_N_per_mm",
            "cover_grade", "max_temp_c", "mass_kg_m2", "note", "custom",
        ],
    ),
    "screws": (
        Screw,
        "model",
        [
            "model", "diameter_mm", "pitch_mm", "shaft_dia_mm",
            "flight_thickness_mm", "material", "max_torque_Nm", "note", "app", "custom",
        ],
    ),
    "bolts": (
        Bolt,
        "designation",
        [
            "designation", "diameter_mm", "property_class", "Sy_Pa", "Su_Pa",
            "proof_load_N", "material", "note", "custom",
        ],
    ),
    "cost_items": (
        CostItem,
        "item",
        ["item", "usd", "description", "material_group", "custom", "note"],
    ),
    "material_grades": (
        MaterialGrade,
        "grade_id",
        [
            "grade_id", "name", "component_types", "Sy_Pa", "Su_Pa", "E_Pa",
            "density_kgm3", "tau_allow_key_Pa", "tau_allow_no_key_Pa",
            "note", "custom",
        ],
    ),
}

# custom_materials is intentionally excluded — that table holds user-created
# runtime data and a seed script must never touch it.
SKIP_TABLES = {"custom_materials"}


def seed_table(session, table_name, rows):
    """Upsert all rows for a single table. Returns (n_new, n_updated)."""
    orm_class, key_col, columns = TABLE_SPECS[table_name]
    n_new = 0
    n_updated = 0

    for row in rows:
        key_value = row.get(key_col)
        existing = (
            session.query(orm_class)
            .filter_by(**{key_col: key_value})
            .first()
        )
        instance = existing or orm_class(**{key_col: key_value})

        for col in columns:
            if col == key_col:
                continue
            # Catalog data is never user-custom; force this regardless of
            # whatever value happens to be in the export.
            if col == "custom":
                setattr(instance, "custom", False)
                continue
            if col in row:
                setattr(instance, col, row[col])

        if not existing:
            session.add(instance)
            n_new += 1
        else:
            n_updated += 1

    return n_new, n_updated


def run_seed(json_path: str):
    path = Path(json_path)
    if not path.exists():
        print(f"ERROR: JSON export not found at {path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    create_tables()
    session = SessionLocal()
    summary_lines = []

    try:
        for table_name in TABLE_SPECS:
            if table_name in SKIP_TABLES:
                continue

            rows = data.get(table_name, [])
            if not rows:
                summary_lines.append(f"0 {table_name} (empty)")
                continue

            n_new, n_updated = seed_table(session, table_name, rows)
            summary_lines.append(
                f"{n_new} new {table_name}, {n_updated} {table_name} updated"
            )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print("Seed complete:")
    for line in summary_lines:
        print(f"  {line}")


if __name__ == "__main__":
    json_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON_PATH
    run_seed(json_arg)