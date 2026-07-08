"""
seed_all.py — VECTRIX full catalog seed script.

Reads a JSON export (vectrix_db_export.json) and upserts every row into
vectrix.db via the SQLAlchemy ORM. Idempotent: safe to re-run, updates
existing rows in place by their natural key, never duplicates.

Also seeds the custom_components table (raw sqlite3, not ORM -- the table
is created by custom_components.py's _ensure_table(), not SQLAlchemy) with
54 representative starter entries across all 8 component types.

Replaces seed_catalog.py (which only seeded buckets + material_grades).
seed_catalog.py is now superseded and can be deleted.

Usage:
    cd backend && python seed_all.py [path/to/vectrix_db_export.json]

If no path is given, defaults to vectrix_export/vectrix_db_export.json
relative to the current working directory.
"""

import json
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

from vectrix_database import SessionLocal, create_tables
from vectrix_tables import (
    Material, Bucket, Bearing, Motor, Gearbox, Drive,
    Belt, Screw, Bolt, CostItem, MaterialGrade,
)

DEFAULT_JSON_PATH = "vectrix_export/vectrix_db_export.json"

# table_name -> (ORM class, upsert key column, list of non-id columns)
TABLE_SPECS = {
    "materials": (
        Material, "mat_id",
        ["mat_id","name","category","category_full","rho_bulk","rho_min","rho_max",
         "rho_vib","rho_sc_tm3","flowability","flowability_raw","angle_repose",
         "angle_surcharge","angle_internal_friction","wall_friction_deg","cohesion",
         "bridging_risk","flow_regime","moisture_pct","temp_max","abr_code","abr_text",
         "particle_class","size_code","particle_size_mm","Leq_default","Ceff_default",
         "vfi","bucket_fill_factor","stream_spread_factor","Km","hazard_codes",
         "lambda_ref","fill_max","cema_cls","cema_code","flags","confidence",
         "source","note","app","custom"],
    ),
    "buckets": (
        Bucket, "bucket_id",
        ["bucket_id","style","catalog","W_mm","H_mm","P_mm","V_L","front_angle_deg",
         "type","discharge_type","v_min","v_max","v_opt","pitch_mm","bucket_mass_kg",
         "recommended_materials","note","punch","boltA_mm","boltB_mm","boltDia_mm",
         "boltN","punch_confirmed","custom"],
    ),
    "bearings": (
        Bearing, "name",
        ["name","mfr","type","bore","od","B","C","C0","p","speed_g","seal","role",
         "brg_insert","mass_kg","note","custom"],
    ),
    "motors": (
        Motor, "model",
        ["model","frame","Pkw","poles","rpm_50hz","efficiency","ie_class","ip",
         "mass_kg","note","custom"],
    ),
    "gearboxes": (
        Gearbox, "model",
        ["model","type","stages","Tn","Pkw","ratio_min","ratio_max","eta","mount",
         "ip","temp_max","mass_kg","note","custom"],
    ),
    "drives": (
        Drive, "model",
        ["model","type","Pkw_max","Vrated","Irated","overload_pct","control","ip",
         "features","note","custom"],
    ),
    "belts": (
        Belt, "model",
        ["model","belt_type","ply_or_cord","rating_N_per_mm","cover_grade",
         "max_temp_c","mass_kg_m2","note","custom"],
    ),
    "screws": (
        Screw, "model",
        ["model","diameter_mm","pitch_mm","shaft_dia_mm","flight_thickness_mm",
         "material","max_torque_Nm","note","app","custom"],
    ),
    "bolts": (
        Bolt, "designation",
        ["designation","diameter_mm","property_class","Sy_Pa","Su_Pa","proof_load_N",
         "material","note","custom"],
    ),
    "cost_items": (
        CostItem, "item",
        ["item","usd","description","material_group","custom","note"],
    ),
    "material_grades": (
        MaterialGrade, "grade_id",
        ["grade_id","name","component_types","Sy_Pa","Su_Pa","E_Pa","density_kgm3",
         "tau_allow_key_Pa","tau_allow_no_key_Pa","note","custom"],
    ),
}

# custom_materials holds user-created runtime data -- seed scripts must
# never touch it. custom_components is handled separately below.
SKIP_TABLES = {"custom_materials", "custom_components"}


def seed_table(session, table_name, rows):
    orm_class, key_col, columns = TABLE_SPECS[table_name]
    n_new = n_updated = 0
    for row in rows:
        key_value = row.get(key_col)
        existing = session.query(orm_class).filter_by(**{key_col: key_value}).first()
        instance = existing or orm_class(**{key_col: key_value})
        for col in columns:
            if col == key_col:
                continue
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


# ── Custom components (raw sqlite3, not ORM) ──────────────────────────────────
_NOW = datetime.now().isoformat()


def _comp_id(ctype, desc):
    import re
    s = re.sub(r"[^a-z0-9\s_]", "", desc.lower().strip())
    s = re.sub(r"\s+", "_", s)
    return f"{ctype}_{s[:60]}"


def _insert_comp(conn, ctype, desc, specs):
    conn.execute(
        """INSERT OR IGNORE INTO custom_components
           (id, type, description, specs, notes, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?)""",
        (_comp_id(ctype, desc), ctype, desc, json.dumps(specs), "", _NOW, _NOW)
    )


def seed_custom_components(db_path: str):
    """Seed the custom_components table with 54 representative starter
    entries across all 8 component types. INSERT OR IGNORE -- existing
    rows are never overwritten."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_components (
            id TEXT PRIMARY KEY, type TEXT NOT NULL,
            description TEXT NOT NULL, specs TEXT NOT NULL DEFAULT '{}',
            notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, UNIQUE(type, description)
        )
    """)

    SEED = {
        "belt": [
            ("EP 315/3 + 3/1.5 Grade M",   {"belt_type":"EP","width_mm":400,"ply_count":3,"rated_tension_kn":315,"max_temp_c":80,"cover_grade":"M","top_cover_mm":3,"bottom_cover_mm":1.5,"total_thickness_mm":10,"mass_per_m2_kg":9.5,"elongation_pct":1.5,"supplier":""}),
            ("EP 400/3 + 4/2 Grade M",      {"belt_type":"EP","width_mm":400,"ply_count":3,"rated_tension_kn":400,"max_temp_c":80,"cover_grade":"M","top_cover_mm":4,"bottom_cover_mm":2,"total_thickness_mm":12,"mass_per_m2_kg":11.0,"elongation_pct":1.5,"supplier":""}),
            ("EP 500/4 + 4/2 Grade M",      {"belt_type":"EP","width_mm":500,"ply_count":4,"rated_tension_kn":500,"max_temp_c":80,"cover_grade":"M","top_cover_mm":4,"bottom_cover_mm":2,"total_thickness_mm":14,"mass_per_m2_kg":13.0,"elongation_pct":1.5,"supplier":""}),
            ("EP 630/4 + 5/2.5 Grade M",    {"belt_type":"EP","width_mm":500,"ply_count":4,"rated_tension_kn":630,"max_temp_c":80,"cover_grade":"M","top_cover_mm":5,"bottom_cover_mm":2.5,"total_thickness_mm":16,"mass_per_m2_kg":15.0,"elongation_pct":1.5,"supplier":""}),
            ("EP 400/3 + 4/2 Grade W HT",   {"belt_type":"EP","width_mm":400,"ply_count":3,"rated_tension_kn":400,"max_temp_c":120,"cover_grade":"W","top_cover_mm":4,"bottom_cover_mm":2,"total_thickness_mm":12,"mass_per_m2_kg":11.5,"elongation_pct":1.5,"supplier":""}),
            ("ST 500 + 4/2 Grade N",        {"belt_type":"ST","width_mm":400,"ply_count":1,"rated_tension_kn":500,"max_temp_c":120,"cover_grade":"N","top_cover_mm":4,"bottom_cover_mm":2,"total_thickness_mm":14,"mass_per_m2_kg":14.0,"elongation_pct":0.25,"supplier":""}),
            ("Nylon 3-ply 250/3 Grade M",   {"belt_type":"Nylon","width_mm":300,"ply_count":3,"rated_tension_kn":250,"max_temp_c":80,"cover_grade":"M","top_cover_mm":3,"bottom_cover_mm":1.5,"total_thickness_mm":9,"mass_per_m2_kg":8.5,"elongation_pct":2.0,"supplier":""}),
        ],
        "chain": [
            ("N102B — 4in Standard Single", {"chain_series":"N102B","pitch_mm":101.6,"working_load_kn":22.2,"breaking_load_kn":111.0,"max_speed_ms":1.27,"n_strands":1,"chain_type":"roller","material":"carbon steel","wl_kg":2268,"supplier":""}),
            ("S102B — 4in Single",          {"chain_series":"S102B","pitch_mm":101.6,"working_load_kn":24.9,"breaking_load_kn":124.5,"max_speed_ms":1.27,"n_strands":1,"chain_type":"roller","material":"carbon steel","wl_kg":2540,"supplier":""}),
            ("S110 — 6in Heavy Single",     {"chain_series":"S110","pitch_mm":152.4,"working_load_kn":36.5,"breaking_load_kn":182.5,"max_speed_ms":1.27,"n_strands":1,"chain_type":"roller","material":"carbon steel","wl_kg":3720,"supplier":""}),
            ("ER856 — 6in Mill Duty Single",{"chain_series":"ER856","pitch_mm":152.4,"working_load_kn":44.5,"breaking_load_kn":222.5,"max_speed_ms":1.35,"n_strands":1,"chain_type":"MDC rollerless","material":"alloy steel","wl_kg":4536,"supplier":""}),
            ("ER857 — 6in Heavy Mill Duty", {"chain_series":"ER857","pitch_mm":152.4,"working_load_kn":89.0,"breaking_load_kn":445.0,"max_speed_ms":1.35,"n_strands":1,"chain_type":"MDC rollerless","material":"alloy steel","wl_kg":9072,"supplier":""}),
            ("ER859 — 9in Double Strand",   {"chain_series":"ER859","pitch_mm":228.6,"working_load_kn":80.1,"breaking_load_kn":400.5,"max_speed_ms":0.64,"n_strands":2,"chain_type":"MDC rollerless","material":"alloy steel","wl_kg":8165,"supplier":""}),
            ("C6102 — 12in SC Double",      {"chain_series":"C6102","pitch_mm":304.8,"working_load_kn":71.2,"breaking_load_kn":356.0,"max_speed_ms":0.51,"n_strands":2,"chain_type":"SC pintle","material":"carbon steel","wl_kg":7257,"supplier":""}),
        ],
        "bucket": [
            ("AA 6x4 Centrifugal",          {"style":"AA","width_mm":152,"depth_mm":108,"projection_mm":102,"lip_height_mm":54,"material":"carbon steel","struck_volume_L":0.85,"mass_kg":1.1,"bolt_pattern":"B4","front_angle_deg":30,"discharge_type":"centrifugal","supplier":""}),
            ("AA 12x7 Centrifugal",         {"style":"AA","width_mm":305,"depth_mm":184,"projection_mm":178,"lip_height_mm":92,"material":"carbon steel","struck_volume_L":5.38,"mass_kg":7.0,"bolt_pattern":"B6","front_angle_deg":30,"discharge_type":"centrifugal","supplier":""}),
            ("AC 12x8 Mill Duty",           {"style":"AC","width_mm":305,"depth_mm":216,"projection_mm":203,"lip_height_mm":108,"material":"carbon steel","struck_volume_L":8.58,"mass_kg":11.0,"bolt_pattern":"B6","front_angle_deg":50,"discharge_type":"centrifugal","supplier":""}),
            ("AC 16x8 Mill Duty Wide",      {"style":"AC","width_mm":406,"depth_mm":216,"projection_mm":203,"lip_height_mm":108,"material":"carbon steel","struck_volume_L":11.5,"mass_kg":14.5,"bolt_pattern":"B7","front_angle_deg":50,"discharge_type":"centrifugal","supplier":""}),
            ("HF 12x7 Continuous",          {"style":"HF","width_mm":305,"depth_mm":295,"projection_mm":178,"lip_height_mm":100,"material":"carbon steel","struck_volume_L":6.80,"mass_kg":9.2,"bolt_pattern":"B6","front_angle_deg":45,"discharge_type":"continuous","supplier":""}),
            ("MF 12x8 Mill Duty Continuous",{"style":"MF","width_mm":305,"depth_mm":295,"projection_mm":203,"lip_height_mm":100,"material":"carbon steel","struck_volume_L":7.79,"mass_kg":9.0,"bolt_pattern":"B6","front_angle_deg":45,"discharge_type":"continuous","supplier":""}),
            ("SC 12x8 Super Capacity",      {"style":"SC","width_mm":305,"depth_mm":216,"projection_mm":203,"lip_height_mm":108,"material":"carbon steel","struck_volume_L":8.58,"mass_kg":11.0,"bolt_pattern":"chain","front_angle_deg":0,"discharge_type":"continuous","supplier":""}),
        ],
        "motor": [
            ("7.5 kW IE3 4P IEC 132M",  {"rated_kw":7.5,"rated_rpm":1460,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 132M","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("11 kW IE3 4P IEC 160M",   {"rated_kw":11,"rated_rpm":1460,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 160M","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("15 kW IE3 4P IEC 160L",   {"rated_kw":15,"rated_rpm":1460,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 160L","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("18.5 kW IE3 4P IEC 180M", {"rated_kw":18.5,"rated_rpm":1460,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 180M","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("22 kW IE3 4P IEC 180L",   {"rated_kw":22,"rated_rpm":1460,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 180L","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("30 kW IE3 4P IEC 200L",   {"rated_kw":30,"rated_rpm":1470,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 200L","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("37 kW IE3 4P IEC 225M",   {"rated_kw":37,"rated_rpm":1470,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 225M","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
            ("45 kW IE3 4P IEC 225M",   {"rated_kw":45,"rated_rpm":1475,"poles":4,"voltage_v":415,"frequency_hz":50,"frame":"IEC 225M","enclosure":"IP55","efficiency_class":"IE3","service_factor":1.15,"insulation_class":"F","supplier":""}),
        ],
        "gearbox": [
            ("HB 10:1 15kW",  {"gearbox_type":"helical-bevel","ratio":10.0,"input_rpm":1460,"output_rpm":146,"rated_torque_nm":1200,"service_factor":1.5,"mounting":"foot","input_shaft_mm":38,"output_shaft_mm":65,"lubrication":"oil bath","supplier":""}),
            ("HB 14:1 15kW",  {"gearbox_type":"helical-bevel","ratio":14.0,"input_rpm":1460,"output_rpm":104,"rated_torque_nm":1700,"service_factor":1.5,"mounting":"foot","input_shaft_mm":38,"output_shaft_mm":75,"lubrication":"oil bath","supplier":""}),
            ("HB 20:1 15kW",  {"gearbox_type":"helical-bevel","ratio":20.0,"input_rpm":1460,"output_rpm":73, "rated_torque_nm":2400,"service_factor":1.5,"mounting":"foot","input_shaft_mm":38,"output_shaft_mm":80,"lubrication":"oil bath","supplier":""}),
            ("HB 25:1 22kW",  {"gearbox_type":"helical-bevel","ratio":25.0,"input_rpm":1460,"output_rpm":58, "rated_torque_nm":4500,"service_factor":1.5,"mounting":"foot","input_shaft_mm":48,"output_shaft_mm":90,"lubrication":"oil bath","supplier":""}),
            ("HB 35:1 30kW",  {"gearbox_type":"helical-bevel","ratio":35.0,"input_rpm":1470,"output_rpm":42, "rated_torque_nm":8500,"service_factor":1.5,"mounting":"foot","input_shaft_mm":55,"output_shaft_mm":100,"lubrication":"oil bath","supplier":""}),
            ("PS 15:1 Parallel",{"gearbox_type":"parallel shaft","ratio":15.0,"input_rpm":1460,"output_rpm":97,"rated_torque_nm":2000,"service_factor":1.5,"mounting":"foot","input_shaft_mm":38,"output_shaft_mm":75,"lubrication":"oil bath","supplier":""}),
        ],
        "vfd": [
            ("VFD 7.5kW 415V V/Hz IP20",  {"rated_kw":7.5,"input_voltage_v":415,"input_phases":3,"rated_current_a":18,"overload_pct":150,"control_type":"V/Hz","ip_rating":"IP20","braking_resistor":"external optional","comms":"Modbus RTU","supplier":""}),
            ("VFD 11kW 415V V/Hz IP20",   {"rated_kw":11, "input_voltage_v":415,"input_phases":3,"rated_current_a":25,"overload_pct":150,"control_type":"V/Hz","ip_rating":"IP20","braking_resistor":"external optional","comms":"Modbus RTU","supplier":""}),
            ("VFD 15kW 415V Vector IP20", {"rated_kw":15, "input_voltage_v":415,"input_phases":3,"rated_current_a":32,"overload_pct":150,"control_type":"vector","ip_rating":"IP20","braking_resistor":"external optional","comms":"Modbus RTU","supplier":""}),
            ("VFD 22kW 415V Vector IP20", {"rated_kw":22, "input_voltage_v":415,"input_phases":3,"rated_current_a":46,"overload_pct":150,"control_type":"vector","ip_rating":"IP20","braking_resistor":"external optional","comms":"Modbus RTU","supplier":""}),
            ("VFD 30kW 415V Vector IP54", {"rated_kw":30, "input_voltage_v":415,"input_phases":3,"rated_current_a":62,"overload_pct":150,"control_type":"vector","ip_rating":"IP54","braking_resistor":"internal","comms":"Modbus RTU / EtherNet/IP","supplier":""}),
            ("VFD 45kW 415V Vector IP54", {"rated_kw":45, "input_voltage_v":415,"input_phases":3,"rated_current_a":90,"overload_pct":150,"control_type":"vector","ip_rating":"IP54","braking_resistor":"internal","comms":"Modbus RTU / EtherNet/IP","supplier":""}),
        ],
        "liner": [
            ("Mild Steel 6mm Casing",   {"liner_material":"mild steel","thickness_mm":6, "hardness_hbw":180,"application":"casing","size_mm":"2000x1000","mass_per_m2_kg":47,  "supplier":""}),
            ("AR400 10mm Chute",        {"liner_material":"AR400",     "thickness_mm":10,"hardness_hbw":400,"application":"chute", "size_mm":"2000x1000","mass_per_m2_kg":78.5,"supplier":""}),
            ("AR400 12mm Boot",         {"liner_material":"AR400",     "thickness_mm":12,"hardness_hbw":400,"application":"boot",  "size_mm":"2000x1000","mass_per_m2_kg":94.2,"supplier":""}),
            ("AR500 10mm High Abrasion",{"liner_material":"AR500",     "thickness_mm":10,"hardness_hbw":500,"application":"chute", "size_mm":"2000x1000","mass_per_m2_kg":78.5,"supplier":""}),
            ("CCO 20+7mm Severe Abr",   {"liner_material":"CCO",       "thickness_mm":27,"hardness_hbw":700,"application":"chute", "size_mm":"1500x1000","mass_per_m2_kg":135, "supplier":""}),
            ("UHMWPE 20mm Low Friction",{"liner_material":"UHMWPE",    "thickness_mm":20,"hardness_hbw":70, "application":"chute", "size_mm":"2000x1000","mass_per_m2_kg":18.8,"supplier":""}),
            ("Natural Rubber 12mm",     {"liner_material":"rubber",    "thickness_mm":12,"hardness_hbw":0,  "application":"boot",  "size_mm":"1000x500", "mass_per_m2_kg":13.8,"supplier":""}),
        ],
        "coupling": [
            ("Flex Jaw 500Nm 38/42",    {"coupling_type":"flexible jaw","rated_torque_nm":500, "peak_torque_nm":1000,"bore_input_mm":38,"bore_output_mm":42, "max_rpm":3000,"angular_misalign_deg":1.0,"supplier":""}),
            ("Flex Jaw 1000Nm 50/60",   {"coupling_type":"flexible jaw","rated_torque_nm":1000,"peak_torque_nm":2000,"bore_input_mm":50,"bore_output_mm":60, "max_rpm":2500,"angular_misalign_deg":1.0,"supplier":""}),
            ("Flex Jaw 2000Nm 65/80",   {"coupling_type":"flexible jaw","rated_torque_nm":2000,"peak_torque_nm":4000,"bore_input_mm":65,"bore_output_mm":80, "max_rpm":2000,"angular_misalign_deg":1.0,"supplier":""}),
            ("Fluid Coupling 15kW",     {"coupling_type":"fluid",       "rated_torque_nm":1100,"peak_torque_nm":1650,"bore_input_mm":42,"bore_output_mm":42, "max_rpm":1500,"angular_misalign_deg":0.5,"supplier":""}),
            ("Fluid Coupling 30kW",     {"coupling_type":"fluid",       "rated_torque_nm":2200,"peak_torque_nm":3300,"bore_input_mm":55,"bore_output_mm":55, "max_rpm":1500,"angular_misalign_deg":0.5,"supplier":""}),
            ("Gear Coupling 5000Nm",    {"coupling_type":"gear",        "rated_torque_nm":5000,"peak_torque_nm":7500,"bore_input_mm":80,"bore_output_mm":100,"max_rpm":1500,"angular_misalign_deg":0.5,"supplier":""}),
        ],
    }

    total = 0
    for ctype, entries in SEED.items():
        for desc, specs in entries:
            _insert_comp(conn, ctype, desc, specs)
            total += 1
    conn.commit()

    rows = conn.execute(
        "SELECT type, COUNT(*) FROM custom_components GROUP BY type ORDER BY type"
    ).fetchall()
    conn.close()
    return total, rows


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
                summary_lines.append(f"  {table_name}: 0 rows (empty in export)")
                continue
            n_new, n_updated = seed_table(session, table_name, rows)
            summary_lines.append(
                f"  {table_name}: {n_new} new, {n_updated} updated"
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Resolve the db path for the raw sqlite3 component seed
    try:
        from database import DB_PATH
        db_path = str(DB_PATH)
    except ImportError:
        db_path = "vectrix.db"

    n_comp, comp_rows = seed_custom_components(db_path)
    summary_lines.append(f"  custom_components: {n_comp} entries seeded (INSERT OR IGNORE)")
    for ctype, count in comp_rows:
        summary_lines.append(f"    {ctype:10s}: {count} rows")

    print("Seed complete:")
    for line in summary_lines:
        print(line)


if __name__ == "__main__":
    json_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON_PATH
    run_seed(json_arg)