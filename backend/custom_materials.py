"""
VECTRIX™ — Custom Materials CRUD
─────────────────────────────────────────────────────────────────────────────
Backs the Material Library tab (browse/copy/edit/delete custom materials).

Design notes
────────────
- Field set mirrors materials.py's MATERIALS entries exactly (21 fields) so
  a custom material is usable everywhere a built-in one is -- including
  pref_discharge_type/pref_bucket_style/pref_cr_min/pref_cr_max, which the
  auto-bucket CR-target selection (calculations.py) and the NSGA-II
  optimizer (vectrix_optimizer_v2.py) both read directly.
- Custom material IDs must not collide with a built-in material's id --
  enforced here via validate_custom_id(), not left to the database's
  PRIMARY KEY constraint alone, so the error message can actually say why.
- hazard_codes is stored as a JSON string in SQLite (no native array type)
  and converted to/from a real Python list at the CRUD boundary, matching
  how materials_lookup.py already does this for the (unused, table-absent)
  DB-backed materials path.
"""
from __future__ import annotations
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from database import get_connection

# Fields that make up the solver-facing material dict (excludes the
# bookkeeping-only based_on/created_at/updated_at columns).
MATERIAL_FIELDS = [
    "id", "name", "category", "rho_loose", "rho_vib", "angle_repose",
    "angle_surcharge", "angle_internal_friction", "moisture_pct", "cohesion",
    "abr_code", "flowability", "size_code", "hazard_codes", "Km",
    "Ceff_default", "Leq_default", "wall_friction_deg", "bucket_fill_factor",
    "pref_discharge_type", "pref_bucket_style", "pref_cr_min", "pref_cr_max",
]

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


def validate_custom_id(mat_id: str, builtin_ids: set[str]) -> str | None:
    """Return an error message if mat_id is invalid/colliding, else None."""
    if not mat_id or not _ID_RE.match(mat_id):
        return ("Material ID must start with a lowercase letter and contain "
                "only lowercase letters, numbers, and underscores (2-40 chars).")
    if mat_id in builtin_ids:
        return f"'{mat_id}' is a built-in material ID and cannot be reused."
    return None


def _row_to_material(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["hazard_codes"] = json.loads(d.get("hazard_codes") or "[]")
    return d


def list_custom_materials() -> list[dict]:
    con = get_connection()
    try:
        rows = con.execute(
            "SELECT * FROM custom_materials ORDER BY updated_at DESC"
        ).fetchall()
        return [_row_to_material(r) for r in rows]
    finally:
        con.close()


def get_custom_material(mat_id: str) -> dict | None:
    con = get_connection()
    try:
        row = con.execute(
            "SELECT * FROM custom_materials WHERE id = ?", (mat_id,)
        ).fetchone()
        return _row_to_material(row) if row else None
    finally:
        con.close()


def save_custom_material(data: dict[str, Any], builtin_ids: set[str],
                          is_update: bool = False) -> dict:
    """
    Insert (is_update=False) or update (is_update=True) a custom material.
    Raises ValueError with a user-facing message on validation failure.
    """
    mat_id = (data.get("id") or "").strip().lower()
    if not is_update:
        err = validate_custom_id(mat_id, builtin_ids)
        if err:
            raise ValueError(err)

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Material name is required.")

    try:
        rho_loose = float(data["rho_loose"])
        if rho_loose <= 0:
            raise ValueError("Bulk density (rho_loose) must be a positive number.")
    except (KeyError, TypeError, ValueError):
        raise ValueError("Bulk density (rho_loose) must be a positive number.")

    pref_discharge_type = data.get("pref_discharge_type", "centrifugal")
    if pref_discharge_type not in ("continuous", "centrifugal"):
        raise ValueError("pref_discharge_type must be 'continuous' or 'centrifugal'.")

    hazard_codes = data.get("hazard_codes", [])
    if not isinstance(hazard_codes, list):
        raise ValueError("hazard_codes must be a list.")

    now = datetime.now(timezone.utc).isoformat()
    con = get_connection()
    try:
        if is_update:
            existing = con.execute(
                "SELECT created_at FROM custom_materials WHERE id = ?", (mat_id,)
            ).fetchone()
            if not existing:
                raise ValueError(f"Custom material '{mat_id}' not found.")
            created_at = existing["created_at"]
        else:
            created_at = now

        con.execute("""
            INSERT OR REPLACE INTO custom_materials
                (id, name, category, rho_loose, rho_vib, angle_repose,
                 angle_surcharge, angle_internal_friction, moisture_pct,
                 cohesion, abr_code, flowability, size_code, hazard_codes,
                 Km, Ceff_default, Leq_default, wall_friction_deg,
                 bucket_fill_factor, pref_discharge_type, pref_bucket_style,
                 pref_cr_min, pref_cr_max, based_on, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mat_id, name,
            data.get("category", "MIN"),
            rho_loose,
            data.get("rho_vib"),
            float(data.get("angle_repose", 35)),
            data.get("angle_surcharge"),
            data.get("angle_internal_friction"),
            float(data.get("moisture_pct", 0)),
            float(data.get("cohesion", 0)),
            int(data.get("abr_code", 3)),
            int(data.get("flowability", 2)),
            data.get("size_code", "B"),
            json.dumps(hazard_codes),
            float(data.get("Km", 1.0)),
            float(data.get("Ceff_default", 1.15)),
            float(data.get("Leq_default", 8)),
            float(data.get("wall_friction_deg", 20)),
            float(data.get("bucket_fill_factor", 0.75)),
            pref_discharge_type,
            data.get("pref_bucket_style", "AA"),
            float(data.get("pref_cr_min", 1.2)),
            float(data.get("pref_cr_max", 1.5)),
            data.get("based_on"),
            created_at, now,
        ))
        con.commit()
        saved = get_custom_material(mat_id)  # re-read for a clean, typed response
        if saved is None:
            # Genuinely shouldn't happen -- the INSERT OR REPLACE just
            # committed successfully for this exact id. Raising explicitly
            # rather than returning None keeps the return type honest
            # (declared -> dict, not -> dict | None) and turns a silent
            # type-checker-only mismatch into a real, debuggable error if
            # this path is ever somehow reached.
            raise RuntimeError(f"Custom material '{mat_id}' vanished immediately after save.")
        return saved
    finally:
        con.close()


def delete_custom_material(mat_id: str) -> bool:
    con = get_connection()
    try:
        cur = con.execute("DELETE FROM custom_materials WHERE id = ?", (mat_id,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()