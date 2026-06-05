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

from models import BucketElevatorInput, OptimizerRequest

# ── Engine modules ────────────────────────────────────────────────────────────
from constants import (
    CEMA_MAX_SHAFT_SLOPE, SHAFT_Su_PA, SHAFT_Ka, SHAFT_Kc, SHAFT_Kd, SHAFT_FS,
    SHAFT_E_PA, LEQ_DEFAULT, CEFF_BELT, BELT_WEIGHT_DEFAULT,
)
from physics   import DischargePhysics
from structural import StructuralStressEngine
from dynamics  import DynamicLoadEngine

# ── Material database (400+ entries) ─────────────────────────────────────────
from materials import (
    MATERIALS,
    get_material as _materials_get,
    search_materials,
    list_categories,
    materials_by_category,
    material_count,
)
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
    CEMA 375 §4 power method [kW].
    P_lift    = G·g·H / 1000
    P_digging = G·g·(D_boot·Leq) / 1000
    P_total   = (P_lift + P_digging) × Ceff
    """
    G_kgs     = Q_th / 3.6
    P_lift    = G_kgs * 9.81 * H_m / 1000.0
    P_digging = G_kgs * 9.81 * (D_boot_m * Leq) / 1000.0
    P_total   = (P_lift + P_digging) * Ceff
    return {
        "P_lift":       round(P_lift, 3),
        "P_digging":    round(P_digging, 3),
        "P_drive_loss": round(P_total - P_lift - P_digging, 3),
        "P_total":      round(P_total, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HEAD SHAFT TENSIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_headshaft_tensions(Q_th: float, H_m: float, v_ms: float,
                             bw_kg: float, bs_m: float,
                             BW_mm: float, K_takeup: float = 0.7) -> Dict:
    """
    CEMA 375 §4 head shaft tension breakdown [N].
    Delegates to DynamicLoadEngine.

    v1.2.0 FIX: PIW parameter removed — now reads BELT_WEIGHT_DEFAULT directly.
                Old default 1.5 kg/m² was 5–10× below real belt weights.
    """
    PIW_kgm2 = BELT_WEIGHT_DEFAULT   # 8.0 kg/m²  (EP400-EP500 representative)

    T1 = DynamicLoadEngine.material_tension(Q_th, H_m, v_ms)
    T2 = DynamicLoadEngine.belt_catenary_tension(BW_mm, bw_kg, bs_m, H_m, PIW_kgm2)
    T3 = DynamicLoadEngine.slack_side_tension(T1, T2, K_takeup)

    return {
        "T1": T1, "T2": T2, "T3": T3,
        "F_eff":       T1 + T2,
        "R_headshaft": T1 + T2 + T3,
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
    bw_kg = bucket.get("bucket_mass_kg", bucket["V"] * 1.5)
    BW_mm = select_belt_width(bucket["W"])
    tens  = calc_headshaft_tensions(Q, inp.H_m, v, bw_kg, spacing, BW_mm, inp.K_takeup)
    T1, T2, T3 = tens["T1"], tens["T2"], tens["T3"]
    F_eff  = tens["F_eff"]
    R_head = tens["R_headshaft"]

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

    # ── Belt & motor ──────────────────────────────────────────────────────────
    motor_kw = select_motor(P_total, inp.sf)
    belt_ply = math.ceil(F_eff / (BW_mm / 25.4 * 4450 * 0.5))

    # ── Discharge physics ─────────────────────────────────────────────────────
    cr = centrifugal_ratio(v, inp.D_mm)
    # v1.2.0: release point now from DischargePhysics (single source of truth)
    rp = DischargePhysics.calculate_release_point(v, inp.D_mm / 2000.0)
    theta_rel  = rp.theta_deg
    trajectory = discharge_trajectory(v, inp.D_mm)
    # Material-dependent stream spread
    stream_spread = MaterialBehaviorEngine.stream_spread_factor(mat, v)

    # ── Bearing life ──────────────────────────────────────────────────────────
    L10 = calc_bearing_life(R_head, inp.n_rpm)

    # ── Engineering checks ─────────────────────────────────────────────────────
    checks = _build_checks(
        inp, mat, mat_behavior, bucket, Q, v, cr, T1, T2, T3, F_eff,
        R_head, d_mm, d_stress_mm, d_deflect_mm, governed_by, L10, Ceff
    )

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
        # Power
        "P_lift": pwr["P_lift"], "P_digging": pwr["P_digging"],
        "P_drive_loss": pwr["P_drive_loss"], "P_total": round(P_total, 3),
        "Leq": Leq, "Ceff": Ceff, "motor_kw": motor_kw,
        # Tensions
        "T1": round(T1, 1), "T2": round(T2, 1), "T3": round(T3, 1),
        "F_eff": round(F_eff, 1), "R_headshaft": round(R_head, 1),
        # Shaft
        "T_Nm": round(T_Nm, 2), "d_mm": round(d_mm, 1),
        "d_stress_mm": round(d_stress_mm, 1), "d_deflect_mm": round(d_deflect_mm, 1),
        "governed_by": governed_by, "shaft_span_mm": round(span_m * 1000, 0),
        "shaft_A_mm": round(A_m * 1000, 0), "shaft_B_mm": round(B_m * 1000, 0),
        # Belt & buckets
        "belt_ply": belt_ply, "belt_w": BW_mm,
        "bucket_mass_kg": round(bw_kg, 2),
        # Discharge
        "cr": round(cr, 4), "theta_rel": round(theta_rel, 2),
        "stream_spread": round(stream_spread, 4),
        "trajectory": trajectory,
        # Bearing
        "L10": round(L10, 0),
        # Material behaviour (v1.2.0 — advisory, does not override user fill)
        "mat_behavior": mat_behavior,
        "recommended_fill_pct": mat_behavior["recommended_fill_pct"],
        # Sweep data
        "speed_sweep": speed_sweep, "fill_sweep": fill_sweep,
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
                  d_mm, d_stress_mm, d_deflect_mm, governed_by, L10, Ceff) -> list:
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

    # 11 — Hazard flags (v1.2.0 — from MaterialBehaviorEngine)
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

                if objective == "power":     score = P_total + cr_pen
                elif objective == "tension": score = T_total / 1000 + cr_pen
                elif objective == "motor":   score = motor + cr_pen
                else: score = P_total / 10 + T_total / 100000 + motor / 5 + cr_pen

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