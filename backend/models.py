"""
VECTRIX™ Pydantic Models — Python 3.14 compatible (pydantic>=2.11)
CEMA 375-2017 + ANSI/CEMA 550-2020 aligned schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any


# ─── INPUT ───────────────────────────────────────────────────────

class BucketElevatorInput(BaseModel):
    # Process requirements
    Q_req:          float = Field(100,   ge=1,    le=5000,  description="Required capacity (t/h)")
    H_m:            float = Field(25,    ge=1,    le=200,   description="Lift height (m)")
    mat_id:         str   = Field("wheat",                  description="Material ID")
    custom_rho:     float = Field(0,     ge=0,    le=5000,  description="Custom density kg/m³ (0=use DB)")

    # Head pulley
    D_mm:           float = Field(500,   ge=100,  le=1500,  description="Head pulley diameter (mm)")
    n_rpm:          float = Field(60,    ge=10,   le=300,   description="Head shaft speed (rpm)")

    # Boot pulley (CEMA 375 LEQ method requires boot diameter)
    boot_pulley_D_mm: float = Field(300, ge=100,  le=1000,  description="Boot (tail) pulley diameter (mm)")

    # Bucket
    fill_pct:       float = Field(75,    ge=30,   le=100,   description="Bucket fill factor (%)")
    bucket_gap:     float = Field(25,    ge=0,    le=200,   description="Extra gap added to bucket projection (mm)")
    auto_bucket:    bool  = Field(True,                      description="Auto-select bucket from capacity")
    bucket_id:      str   = Field("B",                       description="Manual bucket series")

    # CEMA 375 §4 power method parameters
    Leq:            float = Field(0,     ge=0,    le=20,    description="Length equivalency factor (0=auto from material)")
    Ceff:           float = Field(0,     ge=0,    le=2.0,   description="Drive efficiency factor (0=auto, typical 1.10–1.30)")

    # Belt & drive
    K_takeup:       float = Field(0.7,   ge=0.4,  le=0.9,   description="Take-up tension factor K (0.5 screw, 0.7 gravity)")
    mu:             float = Field(0.35,  ge=0.1,  le=0.6,   description="Belt-pulley friction μ")
    wrap_deg:       float = Field(180,   ge=90,   le=240,   description="Belt wrap angle (°)")
    sf:             float = Field(1.25,  ge=1.0,  le=2.0,   description="Motor service factor")


class OptimizerRequest(BaseModel):
    base_input: BucketElevatorInput
    objective:  str = Field("power", description="power | tension | motor | balanced")


# ─── PERSISTENCE ─────────────────────────────────────────────────

class DesignRecord(BaseModel):
    id:           str
    module:       str              = "bucket_elevator"
    name:         str
    project:      Optional[str]    = None
    inputs_json:  str
    results_json: str
    notes:        Optional[str]    = None
    created_at:   Optional[str]    = None
