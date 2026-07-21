"""
backend/generate_field_dictionary.py -- emit the VECTRIX Engineering Field
Dictionary from the live database schema.
═══════════════════════════════════════════════════════════════════════════
THE ENGINEERING CONTRACT. Jay's requirement: a document, not a table, recording
what every field MEANS, its units, and who uses it -- so that if someone changes
a field, they change the contract, not the solver.

GENERATED, NOT HAND-WRITTEN. A hand-maintained dictionary drifts the moment a
column is added. This reads the actual schema (PRAGMA table_info) and merges it
with the curated meaning/units/used-by/tier metadata below, so the document is
always in step with the database. Any column present in the DB but MISSING from
the metadata is reported as UNDOCUMENTED -- that is the mechanism that stops the
contract silently going stale.

USAGE (from backend/):
    python generate_field_dictionary.py                     # -> FIELD_DICTIONARY.md
    python generate_field_dictionary.py --out docs/fd.md
    python generate_field_dictionary.py --check             # exit 1 if undocumented
"""
from __future__ import annotations
import argparse, os, sqlite3, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
_DB = os.environ.get("VECTRIX_DB", os.path.join(HERE, "vectrix.db"))

TABLES = ["materials_v2","material_core","material_particles","material_handling",
          "material_hazards","material_model_coefficients","material_sources"]

TABLE_DESC = {
    "materials_v2": ("L1", "Identity & classification. No engineering values."),
    "material_core": ("L2", "Intrinsic physical + flow properties. True for 1 kg sent to ANY machine."),
    "material_particles": ("L2.5", "Particle characterization: PSD, shape, surface, DEM inputs."),
    "material_handling": ("L2.75", "CEMA 550 handling behaviour & operational tendencies."),
    "material_hazards": ("L2B", "Safety / regulatory / compliance. Changes equipment SPEC, not calculations."),
    "material_model_coefficients": ("L3", "Model calibration constants. VERSIONED (1-to-many). EMPTY in Phase 1."),
    "material_sources": ("--", "Provenance & engineering configuration management."),
}

# field -> (meaning, units, used_by, tier)
# tier: A = populate now, B = as data arrives, C = future modules, - = n/a
META = {
    # ---- identity
    "material_id": ("Surrogate primary key", "-", "ALL", "A"),
    "mat_id": ("Stable internal material code (canonical join key)", "-", "ALL", "A"),
    "material_name": ("Official material name", "-", "ALL", "A"),
    "common_name": ("Alternate / common name", "-", "UI", "A"),
    "category": ("Industry category (Cement, Mining, Food...)", "-", "UI, filtering", "A"),
    "subcategory": ("Sub-classification (Clinker, Fly Ash...)", "-", "UI", "A"),
    "cema_material_code": ("Full CEMA material code, e.g. 100B36M", "-", "Classification", "A"),
    "material_class": ("Form factor (Powder/Granular/Pellet/...)", "-", "UI, filtering", "A"),
    "material_family": ("Mineral/Organic/Metal/Agricultural/...", "-", "UI", "A"),
    # ---- core: density
    "rho_loose": ("Loose-poured bulk density", "kg/m3", "ALL solvers", "A"),
    "rho_bulk": ("Operating bulk density", "kg/m3", "Bucket, Screw", "A"),
    "rho_vib": ("Vibrated / tapped density", "kg/m3", "Screw, Air classifier", "B"),
    "rho_min": ("Density range minimum", "kg/m3", "Tolerance studies", "B"),
    "rho_max": ("Density range maximum", "kg/m3", "Tolerance studies", "B"),
    "specific_gravity": ("Specific gravity (dimensionless)", "-", "General", "B"),
    # ---- core: moisture / flow
    "moisture": ("Typical moisture content", "%", "Flow, carryback", "A"),
    "moisture_max": ("Maximum moisture content", "%", "Flow", "B"),
    "free_moisture": ("Free (unbound) moisture", "%", "Carryback, plugging", "C"),
    "angle_repose": ("Angle of repose", "deg", "Bucket, Screw, Belt, Hopper", "A"),
    "angle_surcharge": ("Surcharge angle", "deg", "Belt, Bucket", "A"),
    "dynamic_angle_repose": ("Dynamic angle of repose", "deg", "Discharge trajectory", "B"),
    "flowability": ("Flowability index 1=excellent .. 4=poor", "1-4", "Calculations, fill factor", "A"),
    "flow_regime": ("Categorical flow class (Free Flowing/Cohesive/...)", "-", "Reports, UI", "A"),
    "flowability_method": ("How flowability was determined (traceability)", "-", "QA", "A"),
    "cohesion": ("Cohesion index", "kPa", "Screw, Hopper, trajectory", "B"),
    "compressibility": ("Compressibility", "-", "Storage, hopper", "C"),
    "porosity": ("Porosity (0-1)", "-", "Air classifier", "C"),
    "void_fraction": ("Void fraction (0-1)", "-", "Air classifier, DEM", "C"),
    "mohs_hardness": ("Mohs hardness", "1-10", "Wear models", "B"),
    "temp_max": ("Maximum service temperature", "degC", "Belt selection, drive advisory", "A"),
    "particle_class": ("CEMA lump-size class A/B/C/D", "-", "Bucket, Screw", "A"),
    "particle_size_mm": ("Representative particle size", "mm", "Bucket, Screw", "A"),
    "maximum_lump_size": ("Maximum lump size (engineering property)", "mm", "Bucket, Screw clearance", "A"),
    # ---- handling
    "abr_code": ("Abrasion rating 1=negligible .. 7=extreme", "1-7", "Wear, liner, ALL", "A"),
    "dust_level": ("Dustiness severity 0=none .. 5=severe", "0-5", "Dust control spec", "B"),
    "corrosion_level": ("Corrosivity severity", "0-5", "Material of construction", "B"),
    "stickiness_index": ("Stickiness severity", "0-5", "Discharge, carryback", "B"),
    "bridging_index": ("Bridging tendency severity", "0-5", "Hopper, boot", "B"),
    "caking_index": ("Caking severity", "0-5", "Storage", "C"),
    "segregation_index": ("Segregation severity", "0-5", "Blending", "C"),
    "fluidization_index": ("Fluidization severity", "0-5", "Powder handling", "C"),
    "wear_mode": ("Dominant wear mechanism", "-", "Liner selection", "B"),
    # ---- hazards
    "combustible_dust": ("Classified as combustible dust", "0/1", "Spec generator, safety", "A"),
    "dust_class": ("Dust explosion class St0-St3", "-", "Explosion protection", "B"),
    "kst": ("Deflagration index Kst", "bar.m/s", "Vent sizing", "B"),
    "pmax": ("Maximum explosion pressure", "bar", "Vent sizing", "B"),
    "mec": ("Minimum explosible concentration", "g/m3", "Safety", "C"),
    "mit_cloud": ("Minimum ignition temperature (cloud)", "degC", "Safety", "C"),
    "mit_layer": ("Minimum ignition temperature (layer)", "degC", "Safety", "C"),
    "minimum_ignition_energy": ("Minimum ignition energy", "mJ", "Static control", "C"),
    "atex_zone": ("ATEX zone classification", "-", "Electrical spec", "B"),
    "nfpa_health": ("NFPA 704 health rating", "0-4", "Compliance", "B"),
    "nfpa_flammability": ("NFPA 704 flammability rating", "0-4", "Compliance", "B"),
    "nfpa_reactivity": ("NFPA 704 reactivity rating", "0-4", "Compliance", "B"),
    # ---- model coefficients (Phase 1: all empty)
    "model_version": ("VECTRIX model version these coefficients tune", "-", "Physics engine", "-"),
    "km": ("Material flow coefficient", "-", "Physics engine", "-"),
    "lambda_ref": ("Reference flow decay coefficient", "-", "Physics engine", "-"),
    "stream_spread_factor": ("Dispersion tendency INPUT coefficient (not the calculated spread)", "-", "Trajectory model", "-"),
    # ---- sources
    "property_name": ("Which property this record traces (schema-evolution safe)", "-", "QA", "A"),
    "source_value": ("Value the source PUBLISHED (immutable, historical)", "varies", "QA", "A"),
    "accepted_value": ("Value VECTRIX ADOPTED (echoed in the engineering table)", "varies", "QA", "A"),
    "decision_type": ("published / measured / calculated / estimated / overridden", "-", "QA", "A"),
    "is_current": ("This record produced today's engineering value (one per property)", "0/1", "QA", "A"),
    "is_active": ("Source still considered valid", "0/1", "QA", "A"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--out", default=os.path.join(HERE, "FIELD_DICTIONARY.md"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any column lacks documentation")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    undocumented = []
    lines = [
        "# VECTRIX Engineering Field Dictionary",
        "",
        f"*Generated from the live schema on {date.today().isoformat()}. "
        "Do not edit by hand -- edit `generate_field_dictionary.py` and regenerate.*",
        "",
        "This is the engineering contract. If a field's meaning changes, change it "
        "here -- not in the solver.",
        "",
        "**Tier**: A = populate now &nbsp;|&nbsp; B = as data becomes available "
        "&nbsp;|&nbsp; C = future modules &nbsp;|&nbsp; - = not populated in Phase 1",
        "",
    ]
    try:
        for t in TABLES:
            info = con.execute(f"PRAGMA table_info('{t}')").fetchall()
            if not info:
                lines.append(f"## {t}\n\n*(table not present in {os.path.basename(args.db)})*\n")
                continue
            lvl, desc = TABLE_DESC.get(t, ("", ""))
            lines += [f"## `{t}`  &nbsp;&nbsp;*{lvl}*", "", desc, "",
                      "| Field | Type | Meaning | Units | Used by | Tier |",
                      "|---|---|---|---|---|---|"]
            for _, name, typ, notnull, _dflt, pk in info:
                meaning, units, used, tier = META.get(
                    name, ("_(undocumented)_", "?", "?", "?"))
                if name not in META:
                    undocumented.append(f"{t}.{name}")
                flag = " **PK**" if pk else (" *NOT NULL*" if notnull else "")
                lines.append(f"| `{name}`{flag} | {typ} | {meaning} | {units} | {used} | {tier} |")
            lines.append("")
    finally:
        con.close()

    if undocumented:
        lines += ["## Undocumented columns", "",
                  "These exist in the database but have no dictionary entry. "
                  "Add them to `META` in `generate_field_dictionary.py`:", ""]
        lines += [f"- `{u}`" for u in undocumented]
        lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"wrote {args.out}")
    print(f"undocumented columns: {len(undocumented)}")
    if undocumented and args.check:
        for u in undocumented[:20]:
            print("   ", u)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())