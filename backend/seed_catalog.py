"""
VECTRIX™ — Seed catalog tables from existing in-code data
─────────────────────────────────────────────────────────────────────────────
Populates the new vectrix_tables.py tables from data that already exists as
Python lists/dicts in this codebase -- NOT fabricated. Run once (idempotent:
upserts by unique key, safe to re-run).

Seeded from real existing data:
  - Bucket         <- calculations.py BUCKET_SERIES (40 entries)
  - MaterialGrade   <- constants.py SHAFT_MATERIALS (4 entries, tagged
                       component_types=["shaft"] -- pulley/casing/chain
                       grades aren't seeded because no such catalog
                       currently exists anywhere in this codebase to seed
                       them from; adding real pulley/casing/chain grade
                       data is a separate task, not done here by guessing
                       at plausible-looking numbers)

Deliberately NOT seeded here (no real source data exists in this codebase):
  Motor, Gearbox, Bearing, Drive, Belt, Screw, Bolt, CostItem -- these
  tables exist and the API can read/write them, but they start empty.
  MOTOR_SIZES in calculations.py is a bare list of kW size-steps used for
  sizing math, not a real product catalog (no model numbers, frames,
  efficiency classes) -- seeding "fake" motor models from it would create
  the same problem this whole exercise is trying to fix: data that looks
  authoritative but isn't real. Populating these with actual manufacturer
  catalog data is the real next step.
"""
from __future__ import annotations
from vectrix_database import SessionLocal, create_tables
from vectrix_tables import Bucket, MaterialGrade


def seed_buckets(session) -> int:
    from calculations import BUCKET_SERIES
    n = 0
    for b in BUCKET_SERIES:
        existing = session.query(Bucket).filter_by(bucket_id=b["id"]).first()
        row = existing or Bucket(bucket_id=b["id"])
        row.style = b.get("style")
        row.catalog = b.get("catalog")
        row.W_mm = b.get("W")
        row.H_mm = b.get("depth_mm", b.get("H"))
        row.P_mm = b.get("P")
        row.V_L = b.get("V")
        row.front_angle_deg = b.get("front_angle_deg")
        row.type = b.get("type")
        row.discharge_type = b.get("discharge_type")
        row.v_min = b.get("v_min")
        row.v_max = b.get("v_max")
        row.v_opt = b.get("v_opt")
        row.pitch_mm = b.get("pitch_mm")
        row.bucket_mass_kg = b.get("bucket_mass_kg")
        row.recommended_materials = b.get("recommended_materials", [])
        row.note = b.get("note")
        row.punch = b.get("punch")
        row.boltA_mm = b.get("boltA_mm")
        row.boltB_mm = b.get("boltB_mm")
        row.boltDia_mm = b.get("boltDia_mm")
        row.boltN = b.get("boltN")
        row.punch_confirmed = bool(b.get("punch_confirmed", False))
        row.custom = False
        if not existing:
            session.add(row)
            n += 1
    return n


def seed_material_grades(session) -> int:
    from constants import SHAFT_MATERIALS
    n = 0
    for grade_id, m in SHAFT_MATERIALS.items():
        existing = session.query(MaterialGrade).filter_by(grade_id=grade_id).first()
        row = existing or MaterialGrade(grade_id=grade_id)
        # FIX (Pylance reportAttributeAccessIssue): name and Sy_Pa are the
        # two REQUIRED (non-Optional) fields on MaterialGrade -- .get()
        # returns T | None even though both keys are genuinely guaranteed
        # present in every SHAFT_MATERIALS entry (confirmed: constants.py's
        # 4 entries all define both). Direct indexing matches that real
        # guarantee instead of claiming a possibility (missing key) that
        # can't actually happen here, and resolves the type mismatch at the
        # same time -- not just a type-checker workaround. The other
        # fields below stay on .get() since they map to genuinely Optional
        # columns (Su_Pa/E_Pa/density_kgm3/tau_allow_*).
        row.name = m["name"]
        row.component_types = ["shaft"]
        row.Sy_Pa = m["Sy_Pa"]
        row.Su_Pa = m.get("Su_Pa")
        row.E_Pa = m.get("E_Pa")
        row.density_kgm3 = m.get("density_kgm3")
        row.tau_allow_key_Pa = m.get("tau_allow_key_Pa")
        row.tau_allow_no_key_Pa = m.get("tau_allow_no_key_Pa")
        row.note = m.get("note")
        row.custom = False
        if not existing:
            session.add(row)
            n += 1
    return n


def run_seed():
    create_tables()
    session = SessionLocal()
    try:
        n_buckets = seed_buckets(session)
        n_grades = seed_material_grades(session)
        session.commit()
        print(f"Seeded {n_buckets} new buckets, {n_grades} new material grades "
              f"(existing rows updated in place, not duplicated).")
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()