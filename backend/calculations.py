"""
VECTRIX™ — CEMA No. 375-2017 Compliant Bucket Elevator Physics Engine
AKSHAYVIPRA EL-MEC · VECTOMEC™ Module

v1.2.0 — Critical Engineering Fixes + Material Behaviour Integration
─────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1.1.0
─────────────────────────────────────────────────────────────────────────────
1. FIX  Materials imported from materials.py (400+ entries).
        Inline 16-material MATERIALS list removed.
        get_material() now delegates to materials.get_material().

2. FIX  release_angle_deg() removed from this module.
        v1.1.0 had TWO inconsistent release angle implementations:
          Here:        θ = acos(g·r / v²)  = acos(1/CR)  ← correct
          physics.py:  θ = acos(rg / v²)   = acos(1/CR)  ← also correct after §3 fix
        Having two sources breaks the single-source-of-truth principle.
        Now: trajectory, CR, θ_rel all delegate to DischargePhysics exclusively.

3. FIX  PIW / belt weight: was hardcoded 1.5 kg/m² (5–10× too low).
        Now uses BELT_WEIGHT_DEFAULT = 8.0 kg/m² from constants.py.
        Impacts: T2, shaft loads, bearing loads, startup inertia.

4. FIX  Bucket weight: was estimated as bucket["V"] * 1.5 kg (volume proxy).
        Now uses bucket["bucket_mass_kg"] (catalogue value added to BUCKET_SERIES).
        Fallback: 1.5 × V for any bucket entry missing the field.
        Audit flagged this as the single largest remaining source of error.

5. FIX  Shaft geometry: A_m = 0.080, B_m = 0.400 were magic numbers.
        Now derived from belt width: span = BW_m + 0.330, asymmetric split.
        Bending moment formula corrected to beam theory M = R·A·B / span.
        (Old: M = R·A overestimated moment by a factor of A / (A·B/span).)

6. NEW  MaterialBehaviorEngine integrated into solve_elevator().
        • mat_behavior block returned in result
        • effective_cr_threshold check added (CR rollback for cohesive materials)
        • recommended_fill_pct advisory in output
        • hazard flags drive ATEX / dust-control check messages
        • stream_spread_factor used in trajectory envelope

7. FIX  run_optimizer() updated with same PIW and bucket weight fixes.

─────────────────────────────────────────────────────────────────────────────
"""

import math
from typing import List, Dict

try:
    from .models import BucketElevatorInput, OptimizerRequest
except ImportError:
    from models import BucketElevatorInput, OptimizerRequest

# ── Engine modules ────────────────────────────────────────────────────────────
try:
    from .constants import (
        CEMA_MAX_SHAFT_SLOPE, SHAFT_Su_PA, SHAFT_Ka, SHAFT_Kc, SHAFT_Kd,
        SHAFT_E_PA, LEQ_DEFAULT, CEFF_BELT, BELT_WEIGHT_DEFAULT,
    )
except ImportError:
    from constants import (
        CEMA_MAX_SHAFT_SLOPE, SHAFT_Su_PA, SHAFT_Ka, SHAFT_Kc, SHAFT_Kd,
        SHAFT_E_PA, LEQ_DEFAULT, CEFF_BELT, BELT_WEIGHT_DEFAULT,
    )
try:
    from .physics import DischargePhysics
except ImportError:
    from physics import DischargePhysics
try:
    from .structural import StructuralStressEngine
except ImportError:
    from structural import StructuralStressEngine
try:
    from .dynamics import DynamicLoadEngine
except ImportError:
    from dynamics import DynamicLoadEngine
try:
    from .chute_flow import ChuteFlowEngine
except ImportError:
    from chute_flow import ChuteFlowEngine

# ── Material database (400+ entries) ─────────────────────────────────────────
try:
    from .materials import (
        MATERIALS,
        get_material as _materials_get,
        search_materials,
        list_categories,
        materials_by_category,
        material_count,
    )
except ImportError:
    from materials import (
        MATERIALS,
        get_material as _materials_get,
        search_materials,
        list_categories,
        materials_by_category,
        material_count,
    )
try:
    from .material_behavior import MaterialBehaviorEngine
except ImportError:
    from material_behavior import MaterialBehaviorEngine


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC MATERIAL ACCESSOR — thin wrapper keeps existing callers unchanged
# ═══════════════════════════════════════════════════════════════════════════════

def get_material(mat_id: str) -> Dict:
    """Return material dict by id.  Delegates to materials.py (400+ entries)."""
    return _materials_get(mat_id)


# ═══════════════════════════════════════════════════════════════════════════════
# CEMA 375 BUCKET SERIES
# v1.2.0: Added bucket_mass_kg — catalogue mid-range for mild steel construction.
#         Source: CEMA 375 Table 1 / manufacturer catalogues (MAXI-LIFT, TAPCO).
#         AR400 buckets ≈ 1.25–1.30 × mild steel mass.
#         Elevator type: CC = centrifugal, HF = high-capacity slow-speed.
# ═══════════════════════════════════════════════════════════════════════════════

BUCKET_SERIES = [
    # id   W(mm) H(mm) P(mm)  V(L)  type  v_min v_max v_opt  mass(kg)
    {"id":"AA","name":"Series AA — Super Capacity",
     "W":305,"H":203,"P":190,"V": 7.4,"type":"CC",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,
     "bucket_mass_kg": 5.8,    # MAXI-LIFT AA-305, 4mm MS
     "note":"CEMA super-capacity, low-speed grain service"},

    {"id":"A", "name":"Series A — Extra Capacity",
     "W":254,"H":178,"P":165,"V": 5.0,"type":"CC",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,
     "bucket_mass_kg": 3.9,    # MAXI-LIFT A-254, 3.5mm MS
     "note":"High-capacity grain/feed service"},

    {"id":"B", "name":"Series B — Medium Capacity",
     "W":203,"H":152,"P":140,"V": 3.3,"type":"CC",
     "v_min":1.02,"v_max":2.54,"v_opt":1.78,
     "bucket_mass_kg": 2.6,    # standard B-203, 3mm MS
     "note":"General purpose — grain, fertiliser, light mineral"},

    {"id":"C", "name":"Series C — Centrifugal",
     "W":152,"H":127,"P":115,"V": 1.9,"type":"CC",
     "v_min":1.02,"v_max":3.05,"v_opt":2.03,
     "bucket_mass_kg": 1.5,    # C-152, 2.5mm MS
     "note":"Standard centrifugal — seed, granular chemicals"},

    {"id":"D", "name":"Series D — Centrifugal Sm.",
     "W":102,"H": 89,"P": 89,"V": 0.77,"type":"CC",
     "v_min":1.02,"v_max":3.56,"v_opt":2.54,
     "bucket_mass_kg": 0.7,    # D-102, 2mm MS
     "note":"Small/high-speed — pellets, fine chemicals"},

    {"id":"MF","name":"Series MF — Milk of Lime",
     "W":254,"H":152,"P":152,"V": 4.0,"type":"CC",
     "v_min":0.51,"v_max":4.57,"v_opt":1.78,
     "bucket_mass_kg": 3.2,    # MF-254, 3.5mm MS
     "note":"Lime, slurry, cohesive minerals"},

    {"id":"PF","name":"Series PF — Pellet/Feed",
     "W":305,"H":203,"P":178,"V": 6.5,"type":"CC",
     "v_min":0.51,"v_max":4.57,"v_opt":1.52,
     "bucket_mass_kg": 5.2,    # PF-305, 4mm MS
     "note":"Feed pellets, gentle handling"},

    {"id":"HF","name":"Series HF — High Capacity",
     "W":356,"H":254,"P":229,"V":11.2,"type":"HF",
     "v_min":0.76,"v_max":1.52,"v_opt":1.14,
     "bucket_mass_kg": 8.1,    # HF-356, 4.5mm MS
     "note":"Very high capacity, slow-speed continuous grain"},
]

BELT_WIDTHS = [102,127,152,178,203,254,305,356,406,457,508,610,762,914]
MOTOR_SIZES = [
    0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
    11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110, 132, 160, 200, 250, 315, 400
]


# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL HELPERS — thin wrappers / converters (no physics lives here)
# ═══════════════════════════════════════════════════════════════════════════════

def belt_speed(D_mm: float, n_rpm: float) -> float:
    """Head pulley rim speed [m/s].  Delegates to DischargePhysics."""
    return DischargePhysics.belt_speed(D_mm / 1000.0, n_rpm)


def centrifugal_ratio(v_ms: float, D_mm: float) -> float:
    """CEMA CR = v²/(g·r).  Delegates to DischargePhysics."""
    return DischargePhysics.centrifugal_ratio(v_ms, D_mm / 2000.0)


# NOTE: release_angle_deg() removed — use DischargePhysics directly.
# Reason: two inconsistent implementations existed (see changelog §2).
# DischargePhysics.calculate_release_point() is the single source of truth.


def discharge_trajectory(v_ms: float, D_mm: float, steps: int = 60) -> List[Dict]:
    """
    Wraps DischargePhysics.trajectory() and converts tuple output to
    {x_mm, y_mm} dicts for the REST API response.
    """
    r = D_mm / 2000.0
    pts = DischargePhysics.trajectory(v_ms, r)
    return [{"x": round(p[0] * 1000, 1), "y": round(p[1] * 1000, 1)} for p in pts]


def _shaft_geometry(BW_mm: float) -> tuple[float, float, float]:
    """
    Derive head shaft geometry from belt width.
    Replaces the hardcoded A_m=0.080, B_m=0.400 (v1.1.0 bug).

    Geometry model (simply supported shaft):
        pulley_face  = BW + 50 mm  (belt width + crown/edge allowance)
        span         = BW + 330 mm (hub + bearing + housing, 165 mm each side)
        A_m          = span × 0.45 (slightly off-centre toward drive side)
        B_m          = span - A_m

    For a 305 mm belt:  span ≈ 635 mm, A_m ≈ 286 mm, B_m ≈ 350 mm.
    For a 610 mm belt:  span ≈ 940 mm, A_m ≈ 423 mm, B_m ≈ 517 mm.

    Returns:
        span_m, A_m, B_m  — all in metres
    """
    BW_m    = BW_mm / 1000.0
    span_m  = BW_m + 0.330                  # 165 mm each side: hub+bearing+housing
    A_m     = span_m * 0.45                 # drive side (shorter arm)
    B_m     = span_m - A_m
    return span_m, A_m, B_m


def _bending_moment(R_head_N: float, A_m: float, B_m: float) -> float:
    """
    Maximum bending moment [N·m] at the pulley for a simply supported shaft
    with a single transverse point load R_head at the pulley.

    Standard beam theory:
        M_max = R_head × A × B / (A + B)   (at the load point)

    v1.1.0 used M = R_head × A_m directly — this overestimated the moment
    when A_m was the full span rather than the shorter arm to the pulley.
    """
    span = A_m + B_m
    if span < 0.001:
        return R_head_N * A_m  # degenerate fallback
    return R_head_N * A_m * B_m / span


# ═══════════════════════════════════════════════════════════════════════════════
# CAPACITY & POWER
# ═══════════════════════════════════════════════════════════════════════════════

def calc_capacity(v_ms: float, spacing_m: float, V_bucket_L: float,
                  fill_pct: float, rho_kgm3: float) -> float:
    """
    CEMA 375 §4 capacity [t/h].
    Q = (v / spacing) × V × η × ρ × 3.6
    """
    Vb_m3 = V_bucket_L / 1000.0
    eta   = fill_pct / 100.0
    return (v_ms / spacing_m) * Vb_m3 * eta * rho_kgm3 * 3.6


def calc_power_cema375(Q_th: float, H_m: float, D_boot_m: float,
                       Leq: float, Ceff: float) -> Dict:
    """
    CEMA 375 §4 — Bucket elevator shaft and drive power [kW].

    CEMA LEQ (Length Equivalency) Method — validated decomposition
    ───────────────────────────────────────────────────────────────
    CEMA 375 §4 defines total equivalent lift height as:

        H_total = H_lift + H_equiv
        H_equiv = D_boot × Leq   [m]

    H_equiv is the equivalent extra lift height accounting for boot loading
    losses (scooping, digging, material acceleration in the boot section).
    It is NOT a drive loss — it is a shaft load, just like lifting material.

        G [kg/s] = Q_th × 1000 / 3600
        P_shaft  = G × g × H_total / 1000   [kW]  — required at head shaft

    The drive efficiency factor Ceff then covers losses between motor shaft
    and head shaft:
        P_total  = P_shaft × Ceff   [kW]  — required at motor shaft

    What Ceff covers (CEMA 375 §4 Table 4-x):
        • Gearbox / shaft-mount reducer losses  (~3–5%)
        • Head shaft bearing friction           (~1–2%)
        • Belt flexure around pulleys           (~1–2%)
        • Seal drag, minor incidentals          (~1–2%)
    Typical values: 1.10–1.15 belt / 1.20–1.30 chain

    ⚠ Double-counting note (from audit):
    P_digging is a SHAFT load (material being scooped from boot).
    Ceff is a DRIVE loss (motor-to-shaft efficiency).
    They act on different parts of the power chain — no double-counting.
    The old formula (P_lift + P_digging) × Ceff is mathematically identical
    to P_shaft × Ceff since P_shaft = G×g×H_total and H_total = H_lift + H_equiv.

    Leq values by elevator type (CEMA 375 §4):
        Spaced centrifugal (most common):   6–8
        Continuous bucket:                  4–5
        Very low-speed / gravity discharge: 3–4
        High-speed, abrasive material:      10–12
        Per material: use mat["Leq_default"] for DB-sourced value.

    Parameters
    ----------
    Q_th      Design capacity [t/h]
    H_m       Elevator lift height [m]
    D_boot_m  Boot pulley diameter [m]
    Leq       CEMA length equivalency factor (dimensionless)
    Ceff      Drive efficiency factor (≥ 1.0)

    Returns
    -------
    {
        "H_equiv":      float  Equivalent boot lift height = D_boot × Leq [m]
        "H_total":      float  H_lift + H_equiv [m]
        "P_shaft":      float  Shaft power = G×g×H_total / 1000 [kW]
        "P_lift":       float  Lift component only [kW]
        "P_digging":    float  Boot loading component [kW]
        "P_drive_loss": float  Motor-to-shaft losses = P_shaft × (Ceff−1) [kW]
        "P_total":      float  Total motor input power [kW]
    }
    """
    G_kgs    = Q_th / 3.6                              # mass flow [kg/s]
    H_equiv  = D_boot_m * Leq                          # equivalent boot height [m]
    H_total  = H_m + H_equiv                           # total equivalent height [m]

    # Component breakdown (for report and UI display)
    P_lift    = G_kgs * 9.81 * H_m     / 1000.0       # lift component [kW]
    P_digging = G_kgs * 9.81 * H_equiv / 1000.0       # boot component [kW]
    P_shaft   = P_lift + P_digging                     # = G×g×H_total/1000 [kW]
    P_total   = P_shaft * Ceff                         # motor input [kW]

    return {
        "H_equiv":      round(H_equiv,   3),
        "H_total":      round(H_total,   3),
        "P_shaft":      round(P_shaft,   3),
        "P_lift":       round(P_lift,    3),
        "P_digging":    round(P_digging, 3),
        "P_drive_loss": round(P_total - P_shaft, 3),   # = P_shaft × (Ceff − 1)
        "P_total":      round(P_total,   3),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HEAD SHAFT TENSIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_headshaft_tensions(Q_th: float, H_m: float, v_ms: float,
                             bw_kg: float, bs_m: float,
                             BW_mm: float, K_takeup: float = 0.7,
                             mu: float = 0.35, wrap_deg: float = 180.0) -> Dict:
    """
    CEMA 375 §4 head shaft tension breakdown [N].

    v1.2.0 FIX: PIW uses BELT_WEIGHT_DEFAULT (8.0 kg/m²); old default was 1.5.
    v1.2.1 FIX: mu and wrap_deg now actively drive T3 via Euler-Eytelwein.
                Previously collected in models.py but never used in calculation.

    Tension path
    ────────────
    T1          material_tension()          G·g·H / v               [N]
    T2          belt_catenary_tension()     (belt + bucket) × H × g [N]
    T3_prelim   slack_side_tension()        (T1+T2) × K_takeup      [N]  preliminary
    T3_euler    euler_eytelwein_check()     T_eff / (e^μθ − 1)      [N]  minimum for no-slip
    T3          max(T3_prelim, T3_euler)                             [N]  governing

    The Euler minimum ensures the drive pulley cannot slip even if the take-up
    tension is set too low.  For most correctly-designed elevators with gravity
    take-up (K=0.7) and rubber lagging (μ=0.35, 180°), K_takeup governs.
    """
    PIW_kgm2  = BELT_WEIGHT_DEFAULT   # 8.0 kg/m²

    T1        = DynamicLoadEngine.material_tension(Q_th, H_m, v_ms)
    T2        = DynamicLoadEngine.belt_catenary_tension(BW_mm, bw_kg, bs_m, H_m, PIW_kgm2)
    T_eff     = T1 + T2
    T3_prelim = DynamicLoadEngine.slack_side_tension(T1, T2, K_takeup)

    # Euler-Eytelwein: minimum T3 to prevent drive pulley slip (CEMA 375 §4)
    euler = DynamicLoadEngine.euler_eytelwein_check(
        T_effective    = T_eff,
        T_slack        = T3_prelim,
        wrap_angle_deg = wrap_deg,
        mu             = mu,
    )

    T3 = max(T3_prelim, euler["T2_minimum"])   # governing slack-side tension

    return {
        "T1":            round(T1,          1),
        "T2":            round(T2,          1),
        "T3":            round(T3,          1),
        "T3_ktakeup":    round(T3_prelim,   1),
        "T3_euler_min":  round(euler["T2_minimum"], 1),
        "F_eff":         round(T_eff,       1),
        "R_headshaft":   round(T_eff + T3,  1),
        "euler_check":   euler,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SELECTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_torsional_moment(P_kw: float, n_rpm: float) -> float:
    omega = 2.0 * math.pi * n_rpm / 60.0
    return P_kw * 1000.0 / max(omega, 0.01)


def calc_bearing_life(R_N: float, n_rpm: float, C_basic_N: float = 355000) -> float:
    return StructuralStressEngine.bearing_l10(C_basic_N, max(R_N, 1.0), n_rpm)


def select_motor(P_kw: float, sf: float) -> float:
    req = P_kw * sf
    for m in MOTOR_SIZES:
        if m >= req:
            return m
    return MOTOR_SIZES[-1]


def select_bucket_auto(Q_th: float, rho: float, v_ms: float,
                       bucket_gap: float) -> Dict:
    for b in BUCKET_SERIES:
        spacing = (b["P"] + bucket_gap) / 1000.0
        if calc_capacity(v_ms, spacing, b["V"], 75.0, rho) >= Q_th:
            return b
    return BUCKET_SERIES[-1]


def select_belt_width(bucket_w_mm: float) -> int:
    for w in BELT_WIDTHS:
        if w >= bucket_w_mm + 50:
            return w
    return BELT_WIDTHS[-1]


# ═══════════════════════════════════════════════════════════════════════════════
# FULL CEMA 375 SOLVER
# ═══════════════════════════════════════════════════════════════════════════════

def solve_elevator(inp: BucketElevatorInput) -> dict:
    # ── Material & density ────────────────────────────────────────────────────
    mat = get_material(inp.mat_id)
    rho = inp.custom_rho if inp.custom_rho > 0 else mat["rho_loose"]

    # ── Material behaviour corrections (v1.2.0 integration) ──────────────────
    #    elevator_type for fill: "continuous" for HF-style, "centrifugal" for CC
    bucket_id = inp.bucket_id if not inp.auto_bucket else None
    is_hf = (bucket_id == "HF") if bucket_id else False
    elev_type = "continuous" if is_hf else "centrifugal"
    mat_behavior = MaterialBehaviorEngine.apply_to_solver(mat, elev_type)

    # ── Belt speed ─────────────────────────────────────────────────────────────
    v = belt_speed(inp.D_mm, inp.n_rpm)

    # ── Bucket selection ───────────────────────────────────────────────────────
    if inp.auto_bucket:
        bucket = select_bucket_auto(inp.Q_req, rho, v, inp.bucket_gap)
    else:
        bucket = next(
            (b for b in BUCKET_SERIES if b["id"] == inp.bucket_id),
            BUCKET_SERIES[2]
        )

    # ── Spacing & capacity ────────────────────────────────────────────────────
    spacing = (bucket["P"] + inp.bucket_gap) / 1000.0
    Q = calc_capacity(v, spacing, bucket["V"], inp.fill_pct, rho)

    # ── Power ─────────────────────────────────────────────────────────────────
    D_boot_m = inp.boot_pulley_D_mm / 1000.0
    Leq  = inp.Leq  if inp.Leq  > 0 else mat.get("Leq_default", LEQ_DEFAULT)
    Ceff = inp.Ceff if inp.Ceff > 0 else mat.get("Ceff_default", CEFF_BELT)
    pwr  = calc_power_cema375(Q, inp.H_m, D_boot_m, Leq, Ceff)
    P_total = pwr["P_total"]

    # ── Tensions ──────────────────────────────────────────────────────────────
    # v1.2.0 FIX: actual catalogue bucket mass (not V × 1.5)
    # v1.2.1 FIX: mu and wrap_deg now passed through to Euler check
    bw_kg = bucket.get("bucket_mass_kg", bucket["V"] * 1.5)
    BW_mm = select_belt_width(bucket["W"])
    tens  = calc_headshaft_tensions(
        Q, inp.H_m, v, bw_kg, spacing, BW_mm, inp.K_takeup,
        mu=inp.mu, wrap_deg=inp.wrap_deg,
    )
    T1, T2, T3 = tens["T1"], tens["T2"], tens["T3"]
    F_eff      = tens["F_eff"]
    R_head     = tens["R_headshaft"]
    euler_chk  = tens["euler_check"]

    # ── Shaft sizing ──────────────────────────────────────────────────────────
    T_Nm = calc_torsional_moment(P_total, inp.n_rpm)
    # v1.2.0 FIX: geometry derived from BW_mm; bending moment from beam theory
    span_m, A_m, B_m = _shaft_geometry(BW_mm)
    M_Nm = _bending_moment(R_head, A_m, B_m)

    gov = StructuralStressEngine.shaft_diameter_governing(
        T_Nm, M_Nm, R_head, A_m, B_m
    )
    d_mm         = gov["d_governing_mm"]
    d_stress_mm  = gov["d_stress_mm"]
    d_deflect_mm = gov["d_deflect_mm"]
    governed_by  = gov["governed_by"]

    # ── Hub sizing & keyway check ─────────────────────────────────────────────
    hub = StructuralStressEngine.hub_diameter(
        shaft_diameter_m = gov["d_governing_m"],
        torque_Nm        = T_Nm,
    )
    key = StructuralStressEngine.key_stress_check(
        shaft_diameter_m = gov["d_governing_m"],
        torque_Nm        = T_Nm,
        key_length_m     = hub["L_hub_m"],
    )

    # ── Pulley lagging selection ───────────────────────────────────────────────
    environment = getattr(inp, "environment", "dry")
    belt_type   = getattr(inp, "belt_type",   "EP")
    lagging = StructuralStressEngine.pulley_lagging(
        material       = mat,
        T_effective_N  = F_eff,
        T_slack_N      = T3,
        wrap_angle_deg = inp.wrap_deg,
        environment    = environment,
        belt_type      = belt_type,
    )

    # ── Pulley end disc ───────────────────────────────────────────────────────
    end_disc = StructuralStressEngine.pulley_end_disc(
        pulley_diameter_m = inp.D_mm / 1000.0,
        hub_od_m          = hub["d_hub_m"],
        T_total_N         = T1 + T2 + T3,
        face_width_m      = BW_mm / 1000.0 + 0.050,
    )

    # ── Bucket bolt fatigue ───────────────────────────────────────────────────
    fill_mass_kg = bucket["V"] / 1000.0 * inp.fill_pct / 100.0 * rho
    n_bolts_bkt  = 3 if bucket["W"] > 350 else 2
    bolt_dia_mm  = 16 if bucket["W"] > 350 else 12
    bolt_fatigue = StructuralStressEngine.bucket_bolt_fatigue(
        belt_speed_mps   = v,
        head_radius_m    = inp.D_mm / 2000.0,
        bucket_mass_kg   = bw_kg,
        fill_mass_kg     = fill_mass_kg,
        n_bolts          = n_bolts_bkt,
        bolt_diameter_mm = bolt_dia_mm,
        n_rpm            = inp.n_rpm,
    )

    # ── Take-up design ────────────────────────────────────────────────────────
    takeup_gravity = StructuralStressEngine.gravity_takeup(T3, inp.H_m, BW_mm)
    takeup_screw   = StructuralStressEngine.screw_takeup(T3)

    # ── Casing structural ─────────────────────────────────────────────────────
    casing_t_m = StructuralStressEngine.casing_plate_thickness(BW_mm, rho, inp.H_m)
    wind_pa    = getattr(inp, "wind_pressure_pa", 800.0)
    casing_stiffener = StructuralStressEngine.casing_stiffener_spacing(casing_t_m, wind_pa)
    panel_span_m = casing_stiffener["recommended_mm"] / 1000.0
    casing_panel = StructuralStressEngine.casing_panel_deflection(
        panel_span_m, panel_span_m, casing_t_m, wind_pa,
    )

    # ── Belt & motor ──────────────────────────────────────────────────────────
    motor_kw = select_motor(P_total, inp.sf)
    belt_ply = math.ceil(F_eff / (BW_mm / 25.4 * 4450 * 0.5))

    # ── Discharge physics — stream envelope replaces single trajectory ────────
    # v1.4.0: DischargePhysics.stream_envelope() returns centre + upper + lower
    # bounds with MaterialBehaviorEngine spread integration and trajectory metrics.
    # The three lines feed the frontend visualisation and chute_flow.py.
    rp    = DischargePhysics.calculate_release_point(v, inp.D_mm / 2000.0)
    cr    = rp.cr
    theta_rel = rp.theta_deg

    envelope = DischargePhysics.stream_envelope(
        speed               = v,
        radius              = inp.D_mm / 2000.0,
        bucket_projection_m = (bucket.get("P") or 140) / 1000.0,
        cohesion_index      = mat.get("cohesion", 0.0),
        elevator_type       = "centrifugal",
        material            = mat,
    )
    traj_center  = envelope["center"]
    traj_upper   = envelope["upper"]
    traj_lower   = envelope["lower"]
    stream_spread = envelope["spread_m"]
    traj_metrics  = envelope.get("metrics", {})

    # Legacy trajectory format for report + chute_flow (list of {x_mm, y_mm} dicts)
    def _to_mm_dicts(pts):
        return [{"x": round(p[0] * 1000, 1), "y": round(p[1] * 1000, 1)} for p in pts]

    trajectory       = _to_mm_dicts(traj_center)
    trajectory_upper = _to_mm_dicts(traj_upper)
    trajectory_lower = _to_mm_dicts(traj_lower)

    # ── Bearing life ──────────────────────────────────────────────────────────
    L10 = calc_bearing_life(R_head, inp.n_rpm)

    # ── Discharge chute design ────────────────────────────────────────────────
    # traj_center is already the raw (x, y) tuple list in metres from stream_envelope()
    bkt_w_mm   = float(bucket.get("W") or BW_mm)
    drop_h_m   = max(inp.D_mm / 1000.0 * 1.5, 0.50)

    chute_geom = ChuteFlowEngine.discharge_chute_geometry(
        trajectory           = traj_center,
        belt_speed_mps       = v,
        head_pulley_radius_m = inp.D_mm / 2000.0,
        bucket_width_mm      = bkt_w_mm,
    )
    hood_spoon  = ChuteFlowEngine.hood_spoon_geometry(
        belt_speed_mps       = v,
        head_pulley_radius_m = inp.D_mm / 2000.0,
        centrifugal_ratio    = cr,
        release_angle_deg    = theta_rel,
    )
    # Chute sizing: back-plate angle from trajectory; width from bucket + clearance
    chute_angle_auto = chute_geom.get("back_plate_angle_deg")
    chute_w_m        = (bkt_w_mm + 100.0) / 1000.0   # CEMA §5: +50mm each side
    chute_h_m        = chute_w_m * 0.75

    discharge_chute = ChuteFlowEngine.design_summary(
        material        = mat,
        capacity_tph    = Q,
        velocity_mps    = v,
        drop_height_m   = drop_h_m,
        chute_angle_deg = chute_angle_auto,
        chute_width_m   = chute_w_m,
        chute_height_m  = chute_h_m,
    )
    discharge_chute["geometry"]   = chute_geom
    discharge_chute["hood_spoon"] = hood_spoon

    # ── Engineering checks ─────────────────────────────────────────────────────
    checks = _build_checks(
        inp, mat, mat_behavior, bucket, Q, v, cr, T1, T2, T3, F_eff,
        R_head, d_mm, d_stress_mm, d_deflect_mm, governed_by, L10, Ceff,
        euler_chk       = euler_chk,
        key_check       = key,
        lagging         = lagging,
        end_disc        = end_disc,
        bolt_fatigue    = bolt_fatigue,
        takeup_grav     = takeup_gravity,
        casing_panel    = casing_panel,
        discharge_chute = discharge_chute,
    )

    # ── Design recommendations ────────────────────────────────────────────────
    _partial = {
        "Q": round(Q, 2), "v": round(v, 4), "cr": round(cr, 4),
        "L10": round(L10, 0), "d_mm": round(d_mm, 1),
        "P_total": round(P_total, 3), "R_headshaft": round(R_head, 1),
        "T3": round(T3, 1), "euler_ratio": euler_chk["euler_ratio"],
        "slip_safe": euler_chk["slip_safe"], "bucket": bucket,
    }
    _inp_dict = {
        "Q_req": inp.Q_req, "n_rpm": inp.n_rpm, "D_mm": inp.D_mm,
        "fill_pct": inp.fill_pct, "mu": inp.mu, "wrap_deg": inp.wrap_deg,
    }
    try:
        design_recs = StructuralStressEngine.design_recommendations(_partial, _inp_dict)
    except Exception:
        design_recs = []

    # ── Sweep data ────────────────────────────────────────────────────────────
    speed_sweep = []
    for n in range(20, 201, 10):
        vn  = belt_speed(inp.D_mm, n)
        Qn  = calc_capacity(vn, spacing, bucket["V"], inp.fill_pct, rho)
        pn  = calc_power_cema375(Qn, inp.H_m, D_boot_m, Leq, Ceff)
        crn = centrifugal_ratio(vn, inp.D_mm)
        speed_sweep.append({
            "rpm": n, "speed": round(vn, 2), "capacity": round(Qn, 1),
            "power": round(pn["P_total"], 2), "cr": round(crn, 3),
        })

    fill_sweep = [
        {"fill": f, "capacity": round(calc_capacity(v, spacing, bucket["V"], f, rho), 1)}
        for f in range(30, 101, 5)
    ]

    # ── Result ────────────────────────────────────────────────────────────────
    return {
        # Capacity
        "Q": round(Q, 2), "v": round(v, 4), "spacing": round(spacing, 4),
        # Frontend aliases — some components reference these names
        "Q_th": round(Q, 2), "capacity": round(Q, 2),
        "v_ms": round(v, 4), "belt_speed": round(v, 4),
        # Power — CEMA 375 §4 LEQ method (Task 3 validated decomposition)
        "P_lift":       pwr["P_lift"],
        "P_digging":    pwr["P_digging"],
        "P_shaft":      pwr["P_shaft"],
        "P_drive_loss": pwr["P_drive_loss"],
        "P_total":      round(P_total, 3),
        "H_equiv":      pwr["H_equiv"],
        "H_total":      pwr["H_total"],
        "Leq": Leq, "Ceff": Ceff, "motor_kw": motor_kw,
        # Tensions
        "T1": round(T1, 1), "T2": round(T2, 1), "T3": round(T3, 1),
        "T3_ktakeup":   tens["T3_ktakeup"],
        "T3_euler_min": tens["T3_euler_min"],
        "F_eff": round(F_eff, 1), "R_headshaft": round(R_head, 1),
        "euler_ratio":  euler_chk["euler_ratio"],
        "slip_safe":    euler_chk["slip_safe"],
        "mu":           inp.mu, "wrap_deg": inp.wrap_deg,
        # Shaft
        "T_Nm": round(T_Nm, 2), "d_mm": round(d_mm, 1),
        "d_stress_mm": round(d_stress_mm, 1), "d_deflect_mm": round(d_deflect_mm, 1),
        "governed_by": governed_by, "shaft_span_mm": round(span_m * 1000, 0),
        "shaft_A_mm": round(A_m * 1000, 0), "shaft_B_mm": round(B_m * 1000, 0),
        # Belt & buckets
        "belt_ply": belt_ply, "belt_w": BW_mm,
        "bucket_mass_kg": round(bw_kg, 2),
        # Discharge — stream envelope (v1.4.0 replaces single trajectory)
        "cr": round(cr, 4), "theta_rel": round(theta_rel, 2),
        "stream_spread":    round(stream_spread, 4),
        "trajectory":       trajectory,           # centre line, mm dicts (legacy)
        "trajectory_upper": trajectory_upper,     # upper bound, mm dicts
        "trajectory_lower": trajectory_lower,     # lower bound, mm dicts
        "trajectory_metrics": traj_metrics,       # throw_distance, impact_v, etc.
        # Bearing
        "L10": round(L10, 0),
        # Material behaviour (v1.2.0 — advisory, does not override user fill)
        "mat_behavior": mat_behavior,
        "recommended_fill_pct": mat_behavior["recommended_fill_pct"],
        # Sweep data
        "speed_sweep": speed_sweep, "fill_sweep": fill_sweep,
        # Structural detail — v1.3.0
        "hub":               hub,
        "key_check":         key,
        "lagging":           lagging,
        "end_disc":          end_disc,
        "bolt_fatigue":      bolt_fatigue,
        "takeup_gravity":    takeup_gravity,
        "takeup_screw":      takeup_screw,
        "casing_t_mm":       round(casing_t_m * 1000.0, 1),
        "casing_panel":      casing_panel,
        "casing_stiffener":  casing_stiffener,
        "design_recommendations": design_recs,
        # Chute flow — v1.4.0
        "discharge_chute":   discharge_chute,
        # Checks
        "checks": checks,
        # Context
        "bucket": bucket, "mat": mat, "rho": rho,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINEERING CHECKS — separated for readability
# ═══════════════════════════════════════════════════════════════════════════════

def _build_checks(inp, mat, mat_behavior, bucket, Q, v, cr,
                  T1, T2, T3, F_eff, R_head,
                  d_mm, d_stress_mm, d_deflect_mm, governed_by, L10, Ceff,
                  euler_chk:       dict = None,
                  key_check:       dict = None,
                  lagging:         dict = None,
                  end_disc:        dict = None,
                  bolt_fatigue:    dict = None,
                  takeup_grav:     dict = None,
                  casing_panel:    dict = None,
                  discharge_chute: dict = None,
                  ) -> list:
    checks = []
    ok   = lambda msg: {"type": "ok",   "msg": msg}
    warn = lambda msg: {"type": "warn", "msg": msg}
    fail = lambda msg: {"type": "fail", "msg": msg}
    info = lambda msg: {"type": "info", "msg": msg}

    v_min, v_max = bucket["v_min"], bucket["v_max"]

    # 1 — Capacity
    if Q < inp.Q_req:
        checks.append(fail(f"Capacity {Q:.1f} t/h < required {inp.Q_req} t/h [CEMA 375 §4]"))
    else:
        checks.append(ok(f"Capacity OK: {Q:.1f} t/h ≥ {inp.Q_req} t/h [CEMA 375 §4]"))

    # 2 — Belt speed vs bucket limits
    if v < v_min:
        checks.append(warn(
            f"Speed {v:.2f} m/s below CEMA min {v_min:.2f} m/s "
            f"for bucket {bucket['id']} — back-legging risk [CEMA 375 §6]"))
    elif v > v_max:
        checks.append(fail(
            f"Speed {v:.2f} m/s exceeds CEMA max {v_max:.2f} m/s "
            f"for bucket {bucket['id']} — scatter risk [CEMA 375 §6]"))
    else:
        checks.append(ok(
            f"Speed {v:.2f} m/s within CEMA range {v_min:.2f}–{v_max:.2f} m/s "
            f"[CEMA 375 §6]"))

    # 3 — Centrifugal ratio (nominal)
    if cr < 1.0:
        checks.append(warn(f"CR={cr:.3f} < 1.0 — gravity/mixed discharge [CEMA 375 §3]"))
    elif cr <= 1.8:
        checks.append(ok(f"CR={cr:.3f} — optimal centrifugal range 1.0–1.8 [CEMA 375 §3]"))
    elif cr <= 2.5:
        checks.append(info(f"CR={cr:.3f} — centrifugal discharge acceptable [CEMA 375 §3]"))
    else:
        checks.append(warn(f"CR={cr:.3f} > 2.5 — excessive scatter risk [CEMA 375 §3]"))

    # 4 — Effective CR for cohesive/moist materials (v1.2.0)
    cr_eff_threshold = mat_behavior["effective_cr_threshold"]
    if cr_eff_threshold > 1.05:
        cr_eff = cr / cr_eff_threshold
        if cr_eff < 1.0:
            checks.append(warn(
                f"Material rollback factor={cr_eff_threshold:.2f} "
                f"— effective CR={cr_eff:.3f} < 1.0; "
                f"bucket retention / spillage risk for cohesive/moist material [CEMA 550 §A-12]"))
        else:
            checks.append(info(
                f"Material rollback factor={cr_eff_threshold:.2f} "
                f"— effective CR={cr_eff:.3f} — adequate for this material [CEMA 550 §A-12]"))

    # 5 — Advisory fill vs material recommendation
    rec_fill = mat_behavior["recommended_fill_pct"]
    if inp.fill_pct > rec_fill + 10.0:
        checks.append(warn(
            f"User fill {inp.fill_pct:.0f}% > material-recommended {rec_fill:.0f}% "
            f"— overflow / spillage risk [CEMA 550 §A-12]"))
    elif inp.fill_pct < rec_fill - 15.0:
        checks.append(info(
            f"User fill {inp.fill_pct:.0f}% — material allows up to {rec_fill:.0f}% "
            f"— capacity headroom available"))

    # 6 — Headshaft load
    T_total = T1 + T2 + T3
    if T_total > 80000:
        checks.append(fail(
            f"Headshaft load {T_total/1000:.1f} kN — verify belt/pulley ratings [CEMA 375 §4]"))
    elif T_total > 50000:
        checks.append(warn(
            f"Headshaft load {T_total/1000:.1f} kN — approaching heavy-duty belt [CEMA 375 §4]"))
    else:
        checks.append(ok(
            f"Headshaft load {T_total/1000:.1f} kN — within standard belt capacity [CEMA 375 §4]"))

    # 6b — Belt slip (Euler-Eytelwein)
    if euler_chk is not None:
        e_ratio = euler_chk["euler_ratio"]
        t3_min  = euler_chk["T2_minimum"]
        if euler_chk.get("slip_safe") is True:
            checks.append(ok(
                f"Belt slip check: T3={T3:.0f} N ≥ Euler min {t3_min:.0f} N "
                f"(e^μθ={e_ratio:.3f}, μ={inp.mu}, wrap={inp.wrap_deg}°) — no slip [CEMA 375 §4]"))
        else:
            checks.append(fail(
                f"BELT SLIP RISK: T3={T3:.0f} N < Euler min {t3_min:.0f} N "
                f"(e^μθ={e_ratio:.3f}, μ={inp.mu}, wrap={inp.wrap_deg}°). "
                f"Increase take-up tension, add snub pulley, or upgrade lagging [CEMA 375 §4]"))

    # 7 — Shaft sizing
    checks.append(info(
        f"Shaft governed by {governed_by}: {d_mm:.1f} mm "
        f"(stress {d_stress_mm:.1f} mm, deflection {d_deflect_mm:.1f} mm) [CEMA 375 §4]"))

    # 8 — Bearing life
    if L10 < 20000:
        checks.append(warn(f"Bearing L10={L10:.0f} h < 20,000 h minimum [CEMA 375 §4]"))
    elif L10 < 40000:
        checks.append(info(f"Bearing L10={L10:.0f} h — acceptable [CEMA 375 §4]"))
    else:
        checks.append(ok(f"Bearing L10={L10:.0f} h — excellent [CEMA 375 §4]"))

    # 9 — Drive efficiency
    if Ceff > 1.25:
        checks.append(warn(f"Ceff={Ceff:.2f} — high drive losses [CEMA 375 §4]"))

    # 10 — Abrasion
    abr = mat.get("abr_code", 3)
    if abr >= 6:
        checks.append(warn(
            f"Abrasion class {abr}/7 — AR400/AR500 buckets and casing liners "
            f"strongly recommended [CEMA 550]"))
    elif abr >= 4:
        checks.append(info(
            f"Abrasion class {abr}/7 — hardened bucket lip recommended [CEMA 550]"))

    # 11 — Hazard flags (v1.2.0)
    hazards = mat_behavior["hazards"]
    if hazards["atex_required"]:
        checks.append(warn(
            "Explosive/flammable material — ATEX/NEC Class II: "
            "anti-static belt, earth bonding, explosion venting [CEMA 550 §B-10/B-11]"))
    if hazards["dust_control_required"]:
        checks.append(info(
            "Material aerates or is flammable — dust control and boot venting "
            "required [CEMA 550 §B-1/B-11]"))
    if hazards["stainless_recommended"]:
        checks.append(warn(
            "Corrosive material — 316L stainless or coated casings/buckets [CEMA 550 §B-4]"))
    if hazards["hygroscopic"]:
        checks.append(info(
            "Hygroscopic material — seal casing openings; monitor moisture "
            "content in storage [CEMA 550 §B-8]"))

    # 12 — Hub & keyway [ASME B17.1]
    if key_check:
        if key_check["pass"]:
            checks.append(ok(
                f"Keyway: shear {key_check['tau_actual_MPa']} MPa, "
                f"bearing {key_check['sigma_actual_MPa']} MPa — "
                f"{key_check['b_key_mm']}x{key_check['h_key_mm']}mm key within limits [ASME B17.1]"))
        else:
            checks.append(fail(
                f"Keyway FAIL — {key_check['recommendation']} [ASME B17.1]"))

    # 13 — Pulley lagging
    if lagging:
        lag = lagging["lagging_type"].replace("_", " ")
        if not lagging["slip_safe"]:
            checks.append(fail(
                f"Lagging slip FAIL: belt ratio {lagging['belt_ratio_tight_slack']:.3f} "
                f"> Euler {lagging['euler_ratio_lagged']:.3f} even with {lag}. "
                f"Increase T3 or add snub pulley [CEMA 375 §4]"))
        elif lagging["upgraded"]:
            checks.append(warn(
                f"Lagging auto-upgraded to ceramic (slip prevention). "
                f"Verify {lag}, t={lagging['thickness_mm']}mm with supplier [CEMA 375 §4]"))
        else:
            checks.append(info(
                f"Lagging: {lag}, t={lagging['thickness_mm']}mm, "
                f"μ={lagging['mu_operating']:.2f} — slip safe "
                f"(ratio {lagging['belt_ratio_tight_slack']:.3f} < "
                f"Euler {lagging['euler_ratio_lagged']:.3f}) [CEMA 375 §4]"))

    # 14 — Pulley end disc [CEMA Pulley Standard]
    if end_disc:
        SF = end_disc["safety_factor"]
        t  = end_disc["t_governing_mm"]
        t_specified = round(t * 1.20, 0)   # 20% design margin on structural minimum
        # SF ≈ 1.0 is the correct result for calculated minimum thickness.
        # The check always reports the minimum and the recommended specified thickness.
        # Only fail if geometry produces SF < 0.95 (numerical or input error).
        if SF < 0.95:
            checks.append(fail(
                f"End disc geometry error: SF={SF:.2f} < 1.0 at t={t}mm. "
                f"Check hub OD vs pulley diameter inputs [CEMA Pulley Standard]"))
        else:
            checks.append(info(
                f"End disc: min t={t}mm (governed by {end_disc['governed_by']}). "
                f"Specify t={t_specified:.0f}mm in drawings (+20% margin). "
                f"Full Roark or FEA required for fabrication [CEMA Pulley Standard]"))

    # 15 — Bucket bolt fatigue [CEMA 375 §7]
    if bolt_fatigue:
        gr = bolt_fatigue["goodman_ratio"]
        if not bolt_fatigue["pass_infinite_life"]:
            life = bolt_fatigue.get("life_years") or 0
            checks.append(fail(
                f"Bolt fatigue FAIL: Goodman {gr:.3f} > 1.0 "
                f"(life {life:.0f} yr) — upgrade grade or increase diameter [CEMA 375 §7]"))
        elif gr > 0.7:
            checks.append(warn(
                f"Bolt fatigue: Goodman {gr:.3f} — consider grade 10.9 "
                f"({bolt_fatigue['n_bolts']}x M{bolt_fatigue['bolt_dia_mm']:.0f}) [CEMA 375 §7]"))
        else:
            checks.append(ok(
                f"Bolt fatigue: Goodman {gr:.3f} — infinite life "
                f"(grade {bolt_fatigue['bolt_grade']}, "
                f"{bolt_fatigue['n_bolts']}x M{bolt_fatigue['bolt_dia_mm']:.0f}) [CEMA 375 §7]"))

    # 16 — Take-up
    if takeup_grav:
        W  = takeup_grav["W_counterweight_kg_gross"]
        tr = takeup_grav["travel_m"] * 1000
        checks.append(info(
            f"Gravity take-up: counterweight {W:.0f} kg (gross), "
            f"travel {tr:.0f} mm required [CEMA 375 §4]"))

    # 17 — Casing panel deflection
    if casing_panel:
        da = casing_panel["delta_actual_mm"]
        dl = casing_panel["delta_allow_mm"]
        if casing_panel["status"] == "fail":
            checks.append(warn(
                f"Casing panel: δ={da:.1f}mm > L/360={dl:.1f}mm — "
                f"reduce stiffener spacing [CEMA 375 §7]"))
        else:
            checks.append(ok(
                f"Casing panel OK: δ={da:.1f}mm < L/360={dl:.1f}mm "
                f"at {casing_panel['a_mm']:.0f}mm pitch [CEMA 375 §7]"))

    # 18-20 — Discharge chute (ChuteFlowEngine v1.4.0)
    if discharge_chute:
        perf   = discharge_chute.get("performance", {})
        maint  = discharge_chute.get("maintenance", {})
        regime = perf.get("flow_regime", "—")
        angle  = perf.get("chute_angle_deg", 0)
        min_a  = perf.get("min_angle_deg", 0)
        mass_a = perf.get("mass_flow_angle_deg", 0)
        dust   = maint.get("dust_risk", "LOW")
        plug   = maint.get("plugging_risk", "LOW")
        liner  = maint.get("liner_material", "—")

        # 18 — Flow regime
        if regime == "PLUGGING_RISK":
            checks.append(fail(
                f"Discharge chute: PLUGGING RISK at {angle:.0f}° "
                f"(wall-friction minimum = {min_a:.0f}°) [CEMA 375 §5]"))
        elif regime == "FUNNEL_FLOW":
            checks.append(warn(
                f"Discharge chute: funnel flow at {angle:.0f}° — "
                f"steepen to {mass_a:.0f}° for mass flow [CEMA 375 §5]"))
        else:
            checks.append(ok(
                f"Discharge chute: mass flow at {angle:.0f}° "
                f"(min {min_a:.0f}°) [CEMA 375 §5]"))

        # 19 — Dust risk
        if dust in ("HIGH", "SEVERE"):
            checks.append(warn(
                f"Chute dust risk {dust} — extraction or suppression system required "
                f"[CEMA 550 §B]"))
        else:
            checks.append(info(f"Chute dust risk {dust}"))

        # 20 — Plugging & liner
        if plug in ("HIGH", "SEVERE"):
            checks.append(warn(
                f"Chute plugging probability {plug} (index "
                f"{maint.get('plugging_index','—'):.2f}) — "
                f"vibrators / air cannons required; specify {liner} liner [CEMA 375 §5]"))
        else:
            checks.append(ok(
                f"Chute plugging: {plug} risk — {liner} liner specified"))

    return checks


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

def run_optimizer(req: OptimizerRequest) -> List[dict]:
    inp  = req.base_input
    mat  = get_material(inp.mat_id)
    rho  = inp.custom_rho if inp.custom_rho > 0 else mat["rho_loose"]
    D_boot_m  = inp.boot_pulley_D_mm / 1000.0
    Leq  = inp.Leq  if inp.Leq  > 0 else mat.get("Leq_default", LEQ_DEFAULT)
    Ceff = inp.Ceff if inp.Ceff > 0 else mat.get("Ceff_default", CEFF_BELT)
    objective = req.objective
    candidates = []

    for bucket in BUCKET_SERIES:
        # v1.2.0 FIX: actual bucket mass
        bw_kg = bucket.get("bucket_mass_kg", bucket["V"] * 1.5)

        for rpm in range(40, 161, 10):
            for fill in range(60, 91, 5):
                v = belt_speed(inp.D_mm, rpm)
                if v < bucket["v_min"] or v > bucket["v_max"]:
                    continue
                spacing = (bucket["P"] + inp.bucket_gap) / 1000.0
                Q = calc_capacity(v, spacing, bucket["V"], fill, rho)
                if Q < inp.Q_req:
                    continue

                pwr    = calc_power_cema375(Q, inp.H_m, D_boot_m, Leq, Ceff)
                P_total = pwr["P_total"]
                BW_mm  = select_belt_width(bucket["W"])
                # v1.2.0 FIX: correct belt weight
                tens   = calc_headshaft_tensions(
                    Q, inp.H_m, v, bw_kg, spacing, BW_mm, inp.K_takeup
                )
                T_total = tens["T1"] + tens["T2"] + tens["T3"]
                cr      = centrifugal_ratio(v, inp.D_mm)
                motor   = select_motor(P_total, inp.sf)
                cr_pen  = 1000 if (cr < 1.0 or cr > 2.5) else 0

                # ── Normalized objective score ────────────────────────────────
                # v1.3.0 — Task 4: normalized scoring replaces arbitrary scaling.
                #
                # Old: P_total/10 + T_total/100000 + motor/5
                #   Problem: weights were implicit and unit-biased. P_total in kW
                #   contributed differently depending on its absolute magnitude;
                #   no principled reason for /10, /100000, /5 divisors.
                #
                # New: each objective normalized to [0–1] over its expected range,
                #   then combined with explicit documented weights (sum = 1.0).
                #
                # Normalization ranges (covering 95%+ of practical elevators):
                #   Power:   0 – 400 kW   → /400
                #   Tension: 0 – 400 kN   → /400000 (N)
                #   Motor:   0 – 400 kW   → /400
                #
                # Balanced weights:
                #   40% power (primary operating cost driver)
                #   35% tension (belt and shaft cost / life)
                #   25% motor (capital cost, switchgear sizing)
                P_norm = P_total   / 400.0
                T_norm = T_total   / 400_000.0
                M_norm = motor     / 400.0

                if objective == "power":
                    score = P_norm + cr_pen
                elif objective == "tension":
                    score = T_norm + cr_pen
                elif objective == "motor":
                    score = M_norm + cr_pen
                else:   # balanced
                    score = (0.40 * P_norm + 0.35 * T_norm + 0.25 * M_norm) + cr_pen

                candidates.append({
                    "rpm": rpm, "bucket_id": bucket["id"], "fill": fill,
                    "speed": round(v, 2), "capacity": round(Q, 1),
                    "power": round(P_total, 2), "motor_kw": motor,
                    "T1_kN": round(T_total / 1000, 2), "cr": round(cr, 3),
                    "score": round(score, 4),
                })

    candidates.sort(key=lambda c: c["score"])
    for i, c in enumerate(candidates[:20]):
        c["rank"] = i + 1
    return candidates[:20]