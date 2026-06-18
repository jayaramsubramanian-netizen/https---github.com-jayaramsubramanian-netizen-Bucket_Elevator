"""
VECTRIX™ Pydantic Models — Python 3.14 compatible (pydantic>=2.11)
CEMA 375-2017 + ANSI/CEMA 550-2020 aligned schemas

v1.1.0 — Added three v1.3.0 structural-module input fields
─────────────────────────────────────────────────────────────────────────────
NEW  environment      "dry"|"humid"|"wet"|"submerged"
         Used by structural.pulley_lagging() to select lagging type and μ.
         Previously getattr(inp, "environment", "dry") — now a proper field
         with Literal validation and FastAPI /docs exposure.

NEW  belt_type        "EP"|"ST"
         Used by structural.pulley_lagging() to choose groove pattern.
         Diamond groove is not recommended for ST (steel cord) belts due to
         resonant vibration at splice crossings; herringbone is preferred.

NEW  wind_pressure_pa  float, ge=0, le=5000
         Used by structural.casing_stiffener_spacing() and
         structural.casing_panel_deflection().  Default 800 Pa matches a
         typical industrial site at 50-yr return period (AS1170.2 / ASCE 7).
─────────────────────────────────────────────────────────────────────────────
"""

from pydantic import BaseModel, Field
from typing   import Optional, List, Any, Literal


# ─── INPUT ───────────────────────────────────────────────────────

class BucketElevatorInput(BaseModel):
    # Process requirements
    Q_req:          float = Field(100,   ge=1,    le=5000,  description="Required capacity (t/h)")
    H_m:            float = Field(25,    ge=1,    le=200,   description="Lift height (m)")
    mat_id:         str   = Field("wheat",                  description="Material ID (from VECTRIX material database)")
    custom_rho:     float = Field(0,     ge=0,    le=5000,  description="Custom bulk density kg/m³ (0 = use material database value)")

    # ── Custom material property overrides (v1.6.0) ──────────────────────────
    # These fields allow the engineer to specify site-specific material
    # properties that override or supplement the database values.
    # All default to sentinel values meaning "use DB value".

    custom_mat_name:    str   = Field("", description="Display name for a non-DB or custom material")
    custom_aor:         float = Field(0,   ge=0,   le=90,   description="Angle of repose override [°] (0 = use DB value)")
    custom_abr:         int   = Field(0,   ge=0,   le=7,    description="Abrasiveness code override 1-7 (0 = use DB value)")
    custom_flowability: int   = Field(0,   ge=0,   le=4,    description="Flowability class override 1-4: 1=very free, 4=sluggish (0 = use DB value)")
    custom_moisture:    float = Field(-1,  ge=-1,  le=100,  description="Moisture content override [%] (-1 = use DB value)")
    custom_cohesion:    float = Field(-1,  ge=-1,  le=100,  description="Cohesion index override [kPa] (-1 = use DB value)")
    custom_particle_size_mm: float = Field(
        -1, ge=-1, le=500,
        description=(
            "Particle size override [mm] (-1 = use DB value). "
            "Affects: stream envelope spread, chute wear index, liner selection. "
            "Examples: fly ash 0.05 mm, cement 0.01 mm, coal 25 mm, rock 50 mm."
        ),
    )

    # Head pulley
    D_mm:           float = Field(500,   ge=100,  le=1500,  description="Head pulley diameter (mm)")
    n_rpm:          float = Field(60,    ge=10,   le=300,   description="Head shaft speed (rpm)")

    # Boot pulley (CEMA 375 LEQ method requires boot diameter)
    boot_pulley_D_mm:       float = Field(300, ge=100,  le=1000,  description="Boot (tail) pulley diameter (mm)")
    boot_pulley_same_as_head: bool = Field(False, description="Lock boot pulley diameter to match head pulley")

    # Bucket
    # Bucket
    bucket_thickness_override_mm: float = Field(
        0.0, ge=0.0, le=20.0,
        description=(
            "Bucket plate thickness override [mm]. "
            "0 = use catalogue standard gauge for the selected bucket series "
            "(varies by style: AA ~4.5mm, AC ~6.4mm, HF ~4.7mm, SC ~5.7mm). "
            "Set to a preferred plate gauge — bucket mass is scaled linearly "
            "from the catalogue reference, which adjusts T2, headshaft load, "
            "bearing load, and startup inertia accordingly. Use a heavier "
            "gauge for added wear allowance; a lighter gauge reduces dead "
            "load but is not validated against bucket structural adequacy "
            "(see bucket_bolt_fatigue() and casing checks for load-path limits)."
        ),
    )

    fill_pct:       float = Field(75,    ge=30,   le=100,   description="Bucket fill factor (%)")
    bucket_gap:     float = Field(25,    ge=0,    le=600,   description="Extra gap added to bucket projection for spacing (mm)")
    auto_bucket:    bool  = Field(True,                      description="Auto-select bucket series from required capacity")
    bucket_id:      str   = Field("B",                       description="Manual bucket series ID (used when auto_bucket=False)")

    # CEMA 375 §4 power method parameters
    Leq:            float = Field(0,     ge=0,    le=20,    description="CEMA length equivalency factor (0 = auto from material database)")
    Ceff:           float = Field(0,     ge=0,    le=2.0,   description="Drive efficiency factor (0 = auto, typical 1.10–1.30)")

    # Belt & drive
    K_takeup:       float = Field(0.7,   ge=0.4,  le=0.9,   description="Take-up tension factor K (0.5 screw, 0.7 gravity)")
    mu:             float = Field(0.35,  ge=0.1,  le=0.6,   description="Belt-pulley friction coefficient μ")
    wrap_deg:       float = Field(0,     ge=0,    le=240,   description="Belt wrap angle at drive pulley (°). 0 = auto-calculate from pulley geometry.")
    snub_pulley:    bool  = Field(False, description="Add snub pulley on return side (+30° wrap)")
    chute_liner_id: str   = Field("auto", description="Discharge chute liner selection. 'auto' = CEMA wear index selection")
    sf:             float = Field(1.25,  ge=1.0,  le=2.0,   description="Motor service factor")

    # ── v1.3.0 — Structural module inputs ──────────────────────────────────────
    # Previously read by solve_elevator() via getattr(inp, field, default).
    # Now proper validated fields — exposed in FastAPI /docs and passed
    # explicitly by the frontend (DEFAULT_INPUTS updated accordingly).

    environment: Literal["dry", "humid", "wet", "submerged", "corrosive"] = Field(
        "dry",
        description=(
            "Service environment — drives pulley_lagging() selection. "
            "dry: standard indoor; humid: moisture > 15% or condensing; "
            "wet: water spray / washdown; submerged: submerged boot section."
        ),
    )

    belt_type: Literal["EP", "ST"] = Field(
        "EP",
        description=(
            "Belt construction type. "
            "EP: fabric ply (standard bucket elevator); "
            "ST: steel cord (high-tension, long-centre applications). "
            "Diamond groove lagging is not recommended for ST belts — "
            "pulley_lagging() auto-routes ST to herringbone pattern."
        ),
    )

    wind_pressure_pa: float = Field(
        800.0,
        ge=0.0,
        le=5000.0,
        description=(
            "Design wind pressure for casing panel deflection check [Pa]. "
            "Used by casing_stiffener_spacing() and casing_panel_deflection(). "
            "Typical: 600 Pa (sheltered), 800 Pa (open industrial), "
            "1200 Pa (exposed coastal). Ref: AS1170.2 / ASCE 7-22."
        ),
    )

    # ── v1.5.0 — Design overrides ─────────────────────────────────────────────
    # All override fields default to 0 (= auto-calculate from first principles).
    # When a non-zero value is supplied the solver uses that value and reports
    # whether it satisfies the calculated minimum — giving the engineer full
    # control over every dimension shown in the Equipment Tree.

    # Take-up selection
    takeup_type: Literal["gravity", "screw", "auto"] = Field(
        "gravity",
        description=(
            "Take-up system type. "
            "gravity: counterweight take-up (recommended for H > 15 m); "
            "screw: threaded screw take-up (short elevators, H ≤ 15 m); "
            "auto: solver selects based on H_m threshold."
        ),
    )
    takeup_screw_d_mm: float = Field(
        0.0, ge=0.0, le=200.0,
        description=(
            "Screw take-up core diameter override [mm]. "
            "0 = auto-calculate from tension and buckling check. "
            "Set to a standard commercial size (e.g. 32, 40, 50, 63, 80) "
            "to specify and verify — solver reports pass/fail against calculated minimum."
        ),
    )
    takeup_screw_len_m: float = Field(
        0.0, ge=0.0, le=10.0,
        description=(
            "Screw take-up unsupported shank length for buckling check [m]. "
            "0 = auto-derived from required travel (CEMA §4). "
            "Set explicitly when the physical installation length is known."
        ),
    )

    # Shaft
    shaft_material: Literal["A36", "1045_HR", "1045_CD", "4140_QT"] = Field(
        "A36",
        description=(
            "Head shaft material grade — drives allowable shear stress for the "
            "torsion/bending sizing calculation (ASME B17.1 keyed-shaft basis). "
            "A36: mild steel, default, most bucket elevators (τ_allow=42MPa); "
            "1045_HR: hot-rolled medium carbon, step-up for higher-capacity or "
            "impact service (τ_allow=52MPa); "
            "1045_CD: cold-drawn, precision-machined shafts (τ_allow=70MPa); "
            "4140_QT: quenched & tempered alloy steel, heavy-duty/high-impact/"
            "abrasive service (τ_allow=110MPa). Higher grades allow a smaller "
            "shaft diameter for the same load, at higher material cost."
        ),
    )

    shaft_d_override_mm: float = Field(
        0.0, ge=0.0, le=500.0,
        description=(
            "Head shaft diameter override [mm]. "
            "0 = auto-calculate from torsion + bending stress. "
            "Set to a preferred commercial bar diameter — solver reports whether "
            "the specified diameter meets the calculated minimum."
        ),
    )

    # Belt width
    belt_width_override_mm: float = Field(
        0.0, ge=0.0, le=1200.0,
        description=(
            "Belt width override [mm]. "
            "0 = auto-select next standard width above bucket width. "
            "Set to a specific value to check adequacy and fix belt selection."
        ),
    )

    # Casing plate thickness
    casing_t_override_mm: float = Field(
        0.0, ge=0.0, le=50.0,
        description=(
            "Casing plate thickness override [mm]. "
            "0 = auto-calculate from panel deflection analysis. "
            "Set to a preferred standard plate thickness (e.g. 3, 4, 5, 6, 8) — "
            "solver re-checks deflection with specified thickness."
        ),
    )

    # Pulley shell thickness
    pulley_shell_t_override_mm: float = Field(
        0.0, ge=0.0, le=50.0,
        description=(
            "Pulley shell plate thickness override [mm]. "
            "0 = auto-calculate from CEMA Pulley Standard minimum and belt-"
            "pressure hoop stress criteria (whichever governs). "
            "Set to a preferred standard plate thickness (e.g. 6, 8, 10, 12) — "
            "solver reports PASS/FAIL against the calculated minimum required "
            "for the actual belt tension and face width."
        ),
    )

    # ── v1.8.0 — Chain elevator configuration ────────────────────────────────
    # Set conveyor_type = "chain" to switch from belt to chain drive.
    # All belt-specific outputs (belt_ply, euler_ratio, lagging) become N/A.
    # Chain-specific outputs (chain_pull, chain_sf, sprocket_PD) are added.

    conveyor_type: Literal["belt", "chain"] = Field(
        "belt",
        description=(
            "Drive element type. "
            "'belt': fabric/steel-cord belt on pulley (default). "
            "'chain': engineering-class chain on toothed sprocket. "
            "Switches T2 calculation, removes Euler slip check, "
            "adds chain working load check."
        ),
    )

    chain_series: str = Field(
        "",
        description=(
            "Chain series ID for manual selection (e.g. 'S102B', 'S110', 'ER856'). "
            "Empty = auto-select smallest adequate chain by pull force."
        ),
    )

    chain_n_strands: int = Field(
        1, ge=1, le=4,   # le=4 for heavy-duty SC series (clinker, cement mill feed)
        description=(
            "Number of chain strands. "
            "1 = single-strand (standard centrifugal and continuous series). "
            "2 = double-strand (SC Super Capacity series only)."
        ),
    )

    chain_sprocket_teeth: int = Field(
        0, ge=0, le=32,
        description=(
            "Head sprocket tooth count override. "
            "0 = auto (solver picks n_teeth that gives closest standard PD to D_mm). "
            "Set to specify a standard sprocket."
        ),
    )

    chain_sf: float = Field(
        6.0, ge=3.0, le=12.0,
        description=(
            "Chain working load safety factor. "
            "CEMA 375 §4 default: 6.0 for standard service, "
            "8.0 for shock loading or abrasive service."
        ),
    )

    # ── v1.8.0 — Feed design (2f) ─────────────────────────────────────────────
    boot_outlet_height_mm: float = Field(
        0.0, ge=0.0, le=2000.0,
        description=(
            "Boot outlet / inlet height override [mm]. "
            "0 = auto-calculate from bucket projection (centrifugal) "
            "or loading leg dimensions (continuous). "
            "Set to a preferred standard opening height."
        ),
    )

    # ── v1.9.0 — Material & environment extensions ────────────────────────────

    material_temperature_c: float = Field(
        20.0, ge=-30.0, le=400.0,
        description=(
            "Material temperature at inlet [°C]. Default 20°C (ambient). "
            "Affects: belt temperature derating (EP max 80°C, ST max 120°C), "
            "bearing grease selection (standard grease limit 80°C), "
            "liner and bucket material compatibility. "
            "Set for hot materials: cement 80–120°C, clinker 150–300°C."
        ),
    )

    bucket_material: Literal[
        "steel", "SS304", "SS316", "AR400", "AR500", "HDPE"
    ] = Field(
        "steel",
        description=(
            "Bucket body material. "
            "steel: standard carbon steel (default, widest availability); "
            "SS304: stainless grade 304 (food, fertilizer, mild corrosive); "
            "SS316: stainless grade 316 (marine, chemical, salt); "
            "AR400: abrasion-resistant steel 400 HB (mining, aggregate); "
            "AR500: abrasion-resistant steel 500 HB (extreme abrasion, hard rock); "
            "HDPE: high-density polyethylene (food, pharmaceutical, light duty). "
            "Affects bucket mass (SS ~12% heavier; AR400/500 similar to steel; "
            "HDPE ~80% lighter), corrosion suitability, and wear life."
        ),
    )

    counterweight_mass_kg_override: float = Field(
        0.0, ge=0.0, le=50000.0,
        description=(
            "Gravity take-up counterweight mass override [kg]. "
            "0 = auto-calculate from T3 tension requirement. "
            "Set to a preferred commercial counterweight mass — solver reports "
            "PASS/WARN/FAIL against the calculated minimum and maximum (over-heavy "
            "counterweights increase T3 excessively, reducing belt life)."
        ),
    )

    # ── v1.7.0 — Component selector overrides ────────────────────────────────
    # When set, these lock a specific catalogue component instead of the
    # solver's auto-select.  All default to "" / 0 meaning "auto".
    # The solver reads these and reports pass/fail against the calculated
    # minimum — the engineer retains full control over every component.

    # Belt grade selection
    belt_grade: str = Field(
        "",
        description=(
            "Belt grade override. Empty = auto-select. "
            "Options: 'M' (abrasion-resistant), 'N' (general), 'W' (oil/heat). "
            "Used by belt_ply selection and BOM."
        ),
    )

    # Motor override — locks motor kW to a specific standard frame size
    motor_kw_override: float = Field(
        0.0, ge=0.0, le=1000.0,
        description=(
            "Motor kW override [kW]. 0 = auto-select next standard size above P_total × SF. "
            "Set to a specific standard size (e.g. 11, 15, 22, 30) to fix motor selection. "
            "Solver reports PASS/WARN if override is adequate for the calculated load."
        ),
    )

    # Gearbox selection — by model ID from the gearboxes table
    gearbox_model: str = Field(
        "",
        description=(
            "Gearbox model override. Empty = auto-select by output torque. "
            "Set to a model ID from the gearboxes database table (e.g. 'H3-250'). "
            "Solver verifies Tn ≥ required torque."
        ),
    )

    # Bearing selection — by name from the bearings table
    bearing_name: str = Field(
        "",
        description=(
            "Head shaft bearing override. Empty = auto-select by bore and C rating. "
            "Set to a bearing name from the bearings database table (e.g. 'SY 60 TF'). "
            "Solver verifies C/P ratio and L10 against design life."
        ),
    )

    # Drive (VFD/DOL/SS) selection
    drive_model: str = Field(
        "",
        description=(
            "Drive/starter model override. Empty = auto-select by motor kW. "
            "Set to a model ID from the drives database table."
        ),
    )

    # ── v1.9.4 — Drive starting method (for dynamic startup analysis) ────────
    drive_start_type: Literal["DOL", "soft_start", "VFD"] = Field(
        "soft_start",
        description=(
            "Motor starting method — drives the dynamic startup tension model. "
            "DOL (direct-on-line): fast start, 1-3s to full speed, highest "
            "inertia-driven peak tension; soft_start (reduced-voltage / "
            "soft-starter): moderate ramp, 3-8s, default for most bucket "
            "elevators; VFD (variable-frequency drive): controlled ramp, "
            "5-30s, lowest peak tension but highest equipment cost. "
            "Each type maps to a default startup_time_s unless overridden."
        ),
    )

    startup_time_s_override: float = Field(
        0.0, ge=0.0, le=60.0,
        description=(
            "Time to reach full belt speed [s]. 0 = auto from drive_start_type "
            "(DOL: 2s, soft_start: 5s, VFD: 15s). Set explicitly when the "
            "actual ramp profile from the VFD/soft-starter datasheet is known."
        ),
    )

    # Discharge type override — allows forcing continuous mode on non-HF buckets
    # or centrifugal on HF (engineer override for non-standard applications)
    discharge_type_override: Literal["", "centrifugal", "continuous"] = Field(
        "",
        description=(
            "Discharge type override. Empty = auto from bucket style. "
            "Use only when the bucket series alone does not determine the design intent."
        ),
    )


class OptimizerRequest(BaseModel):
    base_input: BucketElevatorInput
    objective:  str = Field(
        "balanced",
        description="Optimization objective: power | tension | motor | balanced",
    )


# ─── PERSISTENCE ─────────────────────────────────────────────────

class DesignRecord(BaseModel):
    id:           str
    module:       str           = "bucket_elevator"
    name:         str
    project:      Optional[str] = None
    inputs_json:  str
    results_json: str
    notes:        Optional[str] = None
    created_at:   Optional[str] = None
    updated_at:   Optional[str] = None  # main.py reads this from DB — must match schema