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

    # Head pulley
    D_mm:           float = Field(500,   ge=100,  le=1500,  description="Head pulley diameter (mm)")
    n_rpm:          float = Field(60,    ge=10,   le=300,   description="Head shaft speed (rpm)")

    # Boot pulley (CEMA 375 LEQ method requires boot diameter)
    boot_pulley_D_mm: float = Field(300, ge=100,  le=1000,  description="Boot (tail) pulley diameter (mm)")

    # Bucket
    fill_pct:       float = Field(75,    ge=30,   le=100,   description="Bucket fill factor (%)")
    bucket_gap:     float = Field(25,    ge=0,    le=200,   description="Extra gap added to bucket projection for spacing (mm)")
    auto_bucket:    bool  = Field(True,                      description="Auto-select bucket series from required capacity")
    bucket_id:      str   = Field("B",                       description="Manual bucket series ID (used when auto_bucket=False)")

    # CEMA 375 §4 power method parameters
    Leq:            float = Field(0,     ge=0,    le=20,    description="CEMA length equivalency factor (0 = auto from material database)")
    Ceff:           float = Field(0,     ge=0,    le=2.0,   description="Drive efficiency factor (0 = auto, typical 1.10–1.30)")

    # Belt & drive
    K_takeup:       float = Field(0.7,   ge=0.4,  le=0.9,   description="Take-up tension factor K (0.5 screw, 0.7 gravity)")
    mu:             float = Field(0.35,  ge=0.1,  le=0.6,   description="Belt-pulley friction coefficient μ")
    wrap_deg:       float = Field(180,   ge=90,   le=240,   description="Belt wrap angle at drive pulley (°)")
    sf:             float = Field(1.25,  ge=1.0,  le=2.0,   description="Motor service factor")

    # ── v1.3.0 — Structural module inputs ──────────────────────────────────────
    # Previously read by solve_elevator() via getattr(inp, field, default).
    # Now proper validated fields — exposed in FastAPI /docs and passed
    # explicitly by the frontend (DEFAULT_INPUTS updated accordingly).

    environment: Literal["dry", "humid", "wet", "submerged"] = Field(
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