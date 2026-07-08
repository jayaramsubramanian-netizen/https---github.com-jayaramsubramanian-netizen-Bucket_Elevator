"""
custom_components.py — VECTOMEC™ Custom Components Library
═══════════════════════════════════════════════════════════════════════════
CRUD for the custom components library. Eight component types, each with
its own field schema, all stored in a single table:

    custom_components(
        id          TEXT  PRIMARY KEY,   -- slug of description (unique per type)
        type        TEXT  NOT NULL,      -- belt|chain|bucket|motor|gearbox|vfd|liner|coupling
        description TEXT  NOT NULL,      -- human-readable name, also the unique identifier
        specs       TEXT  NOT NULL,      -- JSON blob of type-specific fields
        notes       TEXT  DEFAULT '',
        created_at  TEXT  NOT NULL,
        updated_at  TEXT  NOT NULL
    )

Part numbers are intentionally absent -- Jay will assign them later.
Description is the unique identifier within each component type for now.

FIELD SCHEMAS (defines the canonical fields for each type, used by the
UI to build the form and by callers who want to validate/default specs):
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ── Field schema definitions ──────────────────────────────────────────────────
# Each entry: (field_name, python_type, default_value, label, unit_or_hint)
COMPONENT_SCHEMAS: dict[str, list[tuple]] = {
    "belt": [
        ("belt_type",            str,   "EP",      "Belt type",           "EP / ST / CC / Nylon / Fabric"),
        ("width_mm",             float, 300.0,     "Width",               "mm"),
        ("ply_count",            int,   3,          "Ply count",           ""),
        ("rated_tension_kn",     float, 50.0,      "Rated tension",       "kN/m width"),
        ("max_temp_c",           float, 80.0,      "Max temperature",     "°C"),
        ("cover_grade",          str,   "M",       "Cover grade",         "M / N / W / HR"),
        ("top_cover_mm",         float, 4.0,       "Top cover thickness", "mm"),
        ("bottom_cover_mm",      float, 2.0,       "Bottom cover thickness", "mm"),
        ("total_thickness_mm",   float, 12.0,      "Total thickness",     "mm"),
        ("mass_per_m2_kg",       float, 10.0,      "Mass per m²",         "kg/m²"),
        ("elongation_pct",       float, 1.5,       "Elongation at rated tension", "%"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "chain": [
        ("chain_series",         str,   "",        "Chain series / catalog ID", "e.g. ER857, S110"),
        ("pitch_mm",             float, 150.0,     "Pitch",               "mm"),
        ("working_load_kn",      float, 50.0,      "Working load",        "kN"),
        ("breaking_load_kn",     float, 250.0,     "Min breaking load",   "kN"),
        ("max_speed_ms",         float, 1.35,      "Max speed",           "m/s"),
        ("n_strands",            int,   1,          "Number of strands",   ""),
        ("chain_type",           str,   "roller",  "Chain type",          "roller / bushed / MDC / pintle"),
        ("material",             str,   "carbon steel", "Material",        ""),
        ("wl_kg",                float, 5000.0,    "Working load",        "kg (alt unit)"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "bucket": [
        ("style",                str,   "AC",      "Style",               "AA / AC / C / HF / MF / SC"),
        ("width_mm",             float, 305.0,     "Width (L)",           "mm"),
        ("depth_mm",             float, 216.0,     "Depth (back wall H)", "mm"),
        ("projection_mm",        float, 203.0,     "Projection (P)",      "mm"),
        ("lip_height_mm",        float, 100.0,     "Lip / front wall height", "mm"),
        ("material",             str,   "carbon steel", "Material",        "e.g. carbon steel / AR400 / SS316"),
        ("struck_volume_L",      float, 8.58,      "Struck (water-level) volume", "L"),
        ("mass_kg",              float, 11.0,      "Mass per bucket",     "kg"),
        ("bolt_pattern",         str,   "B6",      "Belt punching / bolt pattern", "B6 / B7 / B8 / chain"),
        ("front_angle_deg",      float, 50.0,      "Front lip angle from horizontal", "°"),
        ("discharge_type",       str,   "centrifugal", "Discharge type",  "centrifugal / continuous"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "motor": [
        ("rated_kw",             float, 15.0,      "Rated power",         "kW"),
        ("rated_rpm",            int,   1450,       "Rated speed",         "rpm"),
        ("poles",                int,   4,          "Number of poles",     ""),
        ("voltage_v",            int,   415,        "Supply voltage",      "V"),
        ("frequency_hz",         int,   50,         "Frequency",           "Hz"),
        ("frame",                str,   "",        "Frame size",          "e.g. IEC 160M"),
        ("enclosure",            str,   "IP55",    "Enclosure",           "IP55 / IP65 / TEFC"),
        ("efficiency_class",     str,   "IE3",     "Efficiency class",    "IE1 / IE2 / IE3 / IE4"),
        ("service_factor",       float, 1.15,      "Service factor",      ""),
        ("insulation_class",     str,   "F",       "Insulation class",    "B / F / H"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "gearbox": [
        ("gearbox_type",         str,   "helical-bevel", "Type",          "helical-bevel / parallel shaft / worm"),
        ("ratio",                float, 20.0,      "Gear ratio",          ":1"),
        ("input_rpm",            int,   1450,       "Input speed",         "rpm"),
        ("output_rpm",           float, 72.0,      "Output speed",        "rpm"),
        ("rated_torque_nm",      float, 2000.0,    "Rated output torque", "Nm"),
        ("service_factor",       float, 1.5,       "Service factor",      "AGMA"),
        ("mounting",             str,   "foot",    "Mounting",            "foot / flange / shaft"),
        ("input_shaft_mm",       float, 42.0,      "Input shaft diameter","mm"),
        ("output_shaft_mm",      float, 80.0,      "Output shaft diameter","mm"),
        ("lubrication",          str,   "oil bath", "Lubrication",        "oil bath / grease"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "vfd": [
        ("rated_kw",             float, 15.0,      "Rated power",         "kW"),
        ("input_voltage_v",      int,   415,        "Input voltage",       "V"),
        ("input_phases",         int,   3,          "Input phases",        ""),
        ("rated_current_a",      float, 30.0,      "Rated output current","A"),
        ("overload_pct",         int,   150,        "Overload capacity",   "% for 60s"),
        ("control_type",         str,   "V/Hz",    "Control mode",        "V/Hz / vector / closed-loop"),
        ("ip_rating",            str,   "IP20",    "Enclosure rating",    "IP20 / IP54 / IP65"),
        ("braking_resistor",     str,   "no",      "Braking resistor",    "yes / no / internal"),
        ("comms",                str,   "",        "Communications",      "Modbus / Profibus / EtherNet/IP / none"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "liner": [
        ("liner_material",       str,   "AR400",   "Liner material",      "AR400 / AR500 / CCO / rubber / UHMWPE / ceramic"),
        ("thickness_mm",         float, 10.0,      "Thickness",           "mm"),
        ("hardness_hbw",         float, 400.0,     "Hardness",            "HBW (Brinell)"),
        ("application",          str,   "chute",   "Application",         "chute / casing / bucket / boot"),
        ("size_mm",              str,   "",        "Sheet size",          "e.g. 2000×1000mm"),
        ("mass_per_m2_kg",       float, 78.5,      "Mass per m²",         "kg/m²"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
    "coupling": [
        ("coupling_type",        str,   "flexible jaw", "Type",           "flexible jaw / fluid / gear / rigid / disc"),
        ("rated_torque_nm",      float, 500.0,     "Rated torque",        "Nm"),
        ("peak_torque_nm",       float, 1000.0,    "Peak torque",         "Nm"),
        ("bore_input_mm",        float, 50.0,      "Input bore",          "mm"),
        ("bore_output_mm",       float, 60.0,      "Output bore",         "mm"),
        ("max_rpm",              int,   3000,       "Max speed",           "rpm"),
        ("angular_misalign_deg", float, 1.0,       "Angular misalignment tolerance", "°"),
        ("supplier",             str,   "",        "Supplier / make",     ""),
    ],
}

COMPONENT_TYPES = list(COMPONENT_SCHEMAS.keys())

TYPE_LABELS = {
    "belt":     "Belts",
    "chain":    "Chains",
    "bucket":   "Buckets",
    "motor":    "Motors",
    "gearbox":  "Gearboxes",
    "vfd":      "VFDs / Drives",
    "liner":    "Liners / Wear Plates",
    "coupling": "Couplings",
}


def _slug(description: str) -> str:
    """Build a slug ID from a description string."""
    import re
    s = description.lower().strip()
    s = re.sub(r"[^a-z0-9\s_]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:60] or "component"


# ── Database helpers ───────────────────────────────────────────────────────────
def _get_db_path() -> Path:
    try:
        from database import DB_PATH
        return Path(DB_PATH)
    except ImportError:
        return Path("vectrix.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_components (
                id          TEXT PRIMARY KEY,
                type        TEXT NOT NULL,
                description TEXT NOT NULL,
                specs       TEXT NOT NULL DEFAULT '{}',
                notes       TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(type, description)
            )
        """)
        conn.commit()


_ensure_table()


# ── CRUD ───────────────────────────────────────────────────────────────────────
def list_components(component_type: Optional[str] = None) -> list[dict]:
    """Return all custom components, optionally filtered by type."""
    with _conn() as conn:
        if component_type:
            rows = conn.execute(
                "SELECT * FROM custom_components WHERE type=? ORDER BY description",
                (component_type,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM custom_components ORDER BY type, description"
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["specs"] = json.loads(d.get("specs") or "{}")
        result.append(d)
    return result


def get_component(component_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM custom_components WHERE id=?", (component_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["specs"] = json.loads(d.get("specs") or "{}")
    return d


def create_component(component_type: str, description: str,
                     specs: dict, notes: str = "") -> dict:
    if component_type not in COMPONENT_TYPES:
        raise ValueError(f"Unknown component type: {component_type}")
    now = datetime.now().isoformat()
    comp_id = f"{component_type}_{_slug(description)}"
    with _conn() as conn:
        conn.execute(
            """INSERT INTO custom_components
               (id, type, description, specs, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (comp_id, component_type, description, json.dumps(specs), notes, now, now)
        )
        conn.commit()
    result = get_component(comp_id)
    assert result is not None, f"Component '{comp_id}' not found immediately after insert"
    return result


def update_component(component_id: str, description: str,
                     specs: dict, notes: str = "") -> dict:
    now = datetime.now().isoformat()
    with _conn() as conn:
        conn.execute(
            """UPDATE custom_components
               SET description=?, specs=?, notes=?, updated_at=?
               WHERE id=?""",
            (description, json.dumps(specs), notes, now, component_id)
        )
        conn.commit()
    result = get_component(component_id)
    assert result is not None, f"Component '{component_id}' not found after update"
    return result


def delete_component(component_id: str) -> bool:
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM custom_components WHERE id=?", (component_id,)
        )
        conn.commit()
    return cursor.rowcount > 0


def default_specs(component_type: str) -> dict:
    """Return a dict of field_name -> default_value for a given type."""
    schema = COMPONENT_SCHEMAS.get(component_type, [])
    return {field: default for field, _, default, *_ in schema}