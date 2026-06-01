"""
VECTRIX™ — CEMA No. 375-2017 Compliant Bucket Elevator Physics Engine
AKSHAYVIPRA EL-MEC · VECTOMEC™ Module

CHANGES FROM PREVIOUS VERSION
──────────────────────────────
1. Duplicate constants removed — SHAFT_*, CEMA_MAX_SLOPE were re-defined here
   and silently overrode constants.py. Now imported from constants.py.

2. Physics functions now delegate to physics.py (rim-offset fix preserved):
   belt_speed, centrifugal_ratio, release_angle_deg → DischargePhysics
   discharge_trajectory → thin wrapper converting tuples→dicts for the API

3. Shaft sizing now delegates to structural.py:
   calc_headshaft_diameter_stress/deflection → StructuralStressEngine

4. Tension calculations now delegate to dynamics.py:
   calc_headshaft_tensions → DynamicLoadEngine
"""

import math
from typing import List, Dict
from models import BucketElevatorInput, OptimizerRequest

# ── Import from our corrected engine modules ──────────────────────────────────
from constants import (
    CEMA_MAX_SHAFT_SLOPE, SHAFT_Su_PA, SHAFT_Ka, SHAFT_Kc, SHAFT_Kd, SHAFT_FS,
    SHAFT_E_PA, LEQ_DEFAULT, CEFF_BELT,
)
from physics import DischargePhysics
from structural import StructuralStressEngine
from dynamics import DynamicLoadEngine

# ═══════════════════════════════════════════════════════════════════════════════
# ANSI/CEMA 550-2020 COMPLIANT MATERIAL DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

MATERIALS = [
    {"id":"wheat",     "name":"Wheat",
     "rho_loose":769,  "rho_vib":833,  "angle_repose":28, "angle_surcharge":10,
     "angle_internal_friction":30, "moisture_pct":12.0,
     "abr_code":1, "flowability":2, "size_code":"B", "hazard_codes":[],
     "cema_code":"45B225", "Km":1.0, "Ceff_default":1.15, "Leq_default":7},
    {"id":"corn",      "name":"Corn (Maize)",
     "rho_loose":720,  "rho_vib":785,  "angle_repose":25, "angle_surcharge":5,
     "angle_internal_friction":28, "moisture_pct":14.0,
     "abr_code":1, "flowability":2, "size_code":"B", "hazard_codes":[],
     "cema_code":"45B225", "Km":1.0, "Ceff_default":1.15, "Leq_default":7},
    {"id":"soybeans",  "name":"Soybeans",
     "rho_loose":769,  "rho_vib":800,  "angle_repose":29, "angle_surcharge":12,
     "angle_internal_friction":31, "moisture_pct":13.0,
     "abr_code":1, "flowability":2, "size_code":"B", "hazard_codes":[],
     "cema_code":"45B225", "Km":1.0, "Ceff_default":1.15, "Leq_default":7},
    {"id":"rice",      "name":"Rice (rough)",
     "rho_loose":577,  "rho_vib":625,  "angle_repose":38, "angle_surcharge":20,
     "angle_internal_friction":40, "moisture_pct":14.0,
     "abr_code":2, "flowability":3, "size_code":"B", "hazard_codes":[],
     "cema_code":"36B335", "Km":1.1, "Ceff_default":1.15, "Leq_default":8},
    {"id":"sugar",     "name":"Sugar (granulated)",
     "rho_loose":849,  "rho_vib":961,  "angle_repose":35, "angle_surcharge":15,
     "angle_internal_friction":38, "moisture_pct":0.5,
     "abr_code":1, "flowability":2, "size_code":"A", "hazard_codes":["B8","B11"],
     "cema_code":"54A225BF", "Km":1.0, "Ceff_default":1.15, "Leq_default":7},
    {"id":"salt",      "name":"Salt (fine)",
     "rho_loose":1201, "rho_vib":1362, "angle_repose":32, "angle_surcharge":15,
     "angle_internal_friction":35, "moisture_pct":0.2,
     "abr_code":3, "flowability":3, "size_code":"A", "hazard_codes":["B4"],
     "cema_code":"75A336C", "Km":1.1, "Ceff_default":1.20, "Leq_default":8},
    {"id":"cement",    "name":"Cement (dry)",
     "rho_loose":1506, "rho_vib":1762, "angle_repose":40, "angle_surcharge":20,
     "angle_internal_friction":42, "moisture_pct":0.1,
     "abr_code":5, "flowability":4, "size_code":"A", "hazard_codes":["B1","B8"],
     "cema_code":"94A446BD", "Km":1.4, "Ceff_default":1.25, "Leq_default":10},
    {"id":"limestone", "name":"Limestone (crushed)",
     "rho_loose":1442, "rho_vib":1602, "angle_repose":38, "angle_surcharge":20,
     "angle_internal_friction":40, "moisture_pct":2.0,
     "abr_code":6, "flowability":3, "size_code":"D", "hazard_codes":["B8"],
     "cema_code":"90D336", "Km":1.2, "Ceff_default":1.20, "Leq_default":9},
    {"id":"coal",      "name":"Coal (bituminous)",
     "rho_loose":833,  "rho_vib":913,  "angle_repose":38, "angle_surcharge":20,
     "angle_internal_friction":38, "moisture_pct":8.0,
     "abr_code":5, "flowability":3, "size_code":"D",
     "hazard_codes":["B6","B8","B10","B11"],
     "cema_code":"50D335LNXY", "Km":1.1, "Ceff_default":1.20, "Leq_default":9},
    {"id":"ironore",   "name":"Iron Ore (fines)",
     "rho_loose":2002, "rho_vib":2243, "angle_repose":42, "angle_surcharge":25,
     "angle_internal_friction":45, "moisture_pct":5.0,
     "abr_code":7, "flowability":4, "size_code":"A", "hazard_codes":[],
     "cema_code":"125A447", "Km":1.4, "Ceff_default":1.25, "Leq_default":11},
    {"id":"sand",      "name":"Sand (dry)",
     "rho_loose":1602, "rho_vib":1762, "angle_repose":35, "angle_surcharge":15,
     "angle_internal_friction":37, "moisture_pct":0.5,
     "abr_code":6, "flowability":2, "size_code":"A", "hazard_codes":["B8"],
     "cema_code":"100A236", "Km":1.2, "Ceff_default":1.20, "Leq_default":9},
    {"id":"clinker",   "name":"Clinker",
     "rho_loose":1298, "rho_vib":1442, "angle_repose":45, "angle_surcharge":25,
     "angle_internal_friction":48, "moisture_pct":0.1,
     "abr_code":7, "flowability":4, "size_code":"E", "hazard_codes":["B8"],
     "cema_code":"81E447", "Km":1.5, "Ceff_default":1.30, "Leq_default":12},
    {"id":"flyash",    "name":"Fly Ash",
     "rho_loose":801,  "rho_vib":961,  "angle_repose":42, "angle_surcharge":22,
     "angle_internal_friction":44, "moisture_pct":0.5,
     "abr_code":3, "flowability":4, "size_code":"A", "hazard_codes":["B1","B8"],
     "cema_code":"50A346BD", "Km":1.2, "Ceff_default":1.20, "Leq_default":9},
    {"id":"phosphate", "name":"Phosphate Rock",
     "rho_loose":1201, "rho_vib":1362, "angle_repose":38, "angle_surcharge":20,
     "angle_internal_friction":40, "moisture_pct":3.0,
     "abr_code":5, "flowability":3, "size_code":"C", "hazard_codes":[],
     "cema_code":"75C336", "Km":1.3, "Ceff_default":1.20, "Leq_default":10},
    {"id":"woodchips", "name":"Wood Chips",
     "rho_loose":240,  "rho_vib":290,  "angle_repose":40, "angle_surcharge":20,
     "angle_internal_friction":42, "moisture_pct":25.0,
     "abr_code":1, "flowability":4, "size_code":"E",
     "hazard_codes":["B6","B11"],
     "cema_code":"15E146F", "Km":1.1, "Ceff_default":1.15, "Leq_default":8},
    {"id":"custom",    "name":"Custom Material",
     "rho_loose":1000, "rho_vib":1100, "angle_repose":35, "angle_surcharge":15,
     "angle_internal_friction":37, "moisture_pct":0.0,
     "abr_code":3, "flowability":3, "size_code":"B", "hazard_codes":[],
     "cema_code":"62B335", "Km":1.1, "Ceff_default":1.15, "Leq_default":8},
]

# ═══════════════════════════════════════════════════════════════════════════════
# CEMA 375 BUCKET SERIES — with per-type CEMA §6 speed limits
# ═══════════════════════════════════════════════════════════════════════════════

BUCKET_SERIES = [
    {"id":"AA","name":"Series AA — Super Capacity", "W":305,"H":203,"P":190,"V":7.4,
     "type":"CC","v_min":1.14,"v_max":1.91,"v_opt":1.52},
    {"id":"A", "name":"Series A — Extra Capacity",  "W":254,"H":178,"P":165,"V":5.0,
     "type":"CC","v_min":1.14,"v_max":1.91,"v_opt":1.52},
    {"id":"B", "name":"Series B — Medium Capacity", "W":203,"H":152,"P":140,"V":3.3,
     "type":"CC","v_min":1.02,"v_max":2.54,"v_opt":1.78},
    {"id":"C", "name":"Series C — Centrifugal",     "W":152,"H":127,"P":115,"V":1.9,
     "type":"CC","v_min":1.02,"v_max":3.05,"v_opt":2.03},
    {"id":"D", "name":"Series D — Centrifugal Sm.", "W":102,"H": 89,"P": 89,"V":0.77,
     "type":"CC","v_min":1.02,"v_max":3.56,"v_opt":2.54},
    {"id":"MF","name":"Series MF — Milk of Lime",   "W":254,"H":152,"P":152,"V":4.0,
     "type":"CC","v_min":0.51,"v_max":4.57,"v_opt":1.78},
    {"id":"PF","name":"Series PF — Pellet/Feed",    "W":305,"H":203,"P":178,"V":6.5,
     "type":"CC","v_min":0.51,"v_max":4.57,"v_opt":1.52},
    {"id":"HF","name":"Series HF — High Capacity",  "W":356,"H":254,"P":229,"V":11.2,
     "type":"HF","v_min":0.76,"v_max":1.52,"v_opt":1.14},
]

BELT_WIDTHS = [102,127,152,178,203,254,305,356,406,457,508,610,762,914]
MOTOR_SIZES = [0.37,0.55,0.75,1.1,1.5,2.2,3.0,4.0,5.5,7.5,
               11,15,18.5,22,30,37,45,55,75,90,110,132,160,200,250,315,400]


# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL HELPERS — thin wrappers around engine modules
# ═══════════════════════════════════════════════════════════════════════════════

def belt_speed(D_mm: float, n_rpm: float) -> float:
    return DischargePhysics.belt_speed(D_mm / 1000.0, n_rpm)


def centrifugal_ratio(v_ms: float, D_mm: float) -> float:
    return DischargePhysics.centrifugal_ratio(v_ms, D_mm / 2000.0)


def release_angle_deg(v_ms: float, D_mm: float) -> float:
    import math
    r = D_mm / 2000.0
    if v_ms <= 0:
        return 90.0
    cos_theta = (9.81 * r) / (v_ms ** 2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_theta))))


def discharge_trajectory(v_ms: float, D_mm: float, steps: int = 60) -> List[Dict]:
    """
    Wraps DischargePhysics.trajectory() (rim-offset fixed version) and
    converts output from List[Tuple(m)] to List[Dict{x_mm, y_mm}] for the API.
    """
    r = D_mm / 2000.0
    pts = DischargePhysics.trajectory(v_ms, r)
    return [{"x": round(p[0] * 1000, 1), "y": round(p[1] * 1000, 1)} for p in pts]


def calc_capacity(v_ms: float, spacing_m: float, V_bucket_L: float,
                  fill_pct: float, rho_kgm3: float) -> float:
    Vb_m3 = V_bucket_L / 1000.0
    eta   = fill_pct / 100.0
    return (v_ms / spacing_m) * Vb_m3 * eta * rho_kgm3 * 3.6


def calc_power_cema375(Q_th: float, H_m: float, D_boot_m: float,
                       Leq: float, Ceff: float) -> Dict:
    G_kgs        = Q_th / 3.6
    P_lift       = G_kgs * 9.81 * H_m / 1000
    P_digging    = G_kgs * 9.81 * (D_boot_m * Leq) / 1000
    P_total      = (P_lift + P_digging) * Ceff
    P_drive_loss = P_total - (P_lift + P_digging)
    return {"P_lift": P_lift, "P_digging": P_digging,
            "P_drive_loss": P_drive_loss, "P_total": P_total}


def calc_headshaft_tensions(Q_th, H_m, v_ms, bw_kg, bs_m,
                             BW_mm, PIW_kgm, K_takeup=0.7) -> Dict:
    """Delegates to DynamicLoadEngine."""
    T1 = DynamicLoadEngine.material_tension(Q_th, H_m, v_ms)
    T2 = DynamicLoadEngine.belt_catenary_tension(BW_mm, bw_kg / 1.5, bs_m, H_m, PIW_kgm)
    T3 = DynamicLoadEngine.slack_side_tension(T1, T2, K_takeup)
    return {"T1": T1, "T2": T2, "T3": T3,
            "F_eff": T1 + T2, "R_headshaft": T1 + T2 + T3}


def calc_torsional_moment(P_kw: float, n_rpm: float) -> float:
    import math
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


def select_bucket_auto(Q_th, rho, v_ms, bucket_gap) -> Dict:
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


def get_material(mat_id: str) -> Dict:
    for m in MATERIALS:
        if m["id"] == mat_id:
            return m
    return MATERIALS[0]


# ═══════════════════════════════════════════════════════════════════════════════
# FULL CEMA 375 SOLVER
# ═══════════════════════════════════════════════════════════════════════════════

def solve_elevator(inp: BucketElevatorInput) -> dict:
    mat  = get_material(inp.mat_id)
    rho  = inp.custom_rho if inp.custom_rho > 0 else mat["rho_loose"]
    v    = belt_speed(inp.D_mm, inp.n_rpm)

    if inp.auto_bucket:
        bucket = select_bucket_auto(inp.Q_req, rho, v, inp.bucket_gap)
    else:
        bucket = next((b for b in BUCKET_SERIES if b["id"] == inp.bucket_id), BUCKET_SERIES[2])

    spacing  = (bucket["P"] + inp.bucket_gap) / 1000.0
    Q        = calc_capacity(v, spacing, bucket["V"], inp.fill_pct, rho)

    D_boot_m = inp.boot_pulley_D_mm / 1000.0
    Leq      = inp.Leq  if inp.Leq  > 0 else mat["Leq_default"]
    Ceff     = inp.Ceff if inp.Ceff > 0 else mat["Ceff_default"]
    pwr      = calc_power_cema375(Q, inp.H_m, D_boot_m, Leq, Ceff)
    P_total  = pwr["P_total"]

    bw_kg  = bucket["V"] * 1.5
    BW_mm  = select_belt_width(bucket["W"])
    PIW    = 1.5
    tens   = calc_headshaft_tensions(Q, inp.H_m, v, bw_kg, spacing, BW_mm, PIW, inp.K_takeup)
    T1, T2, T3 = tens["T1"], tens["T2"], tens["T3"]
    F_eff  = tens["F_eff"]
    R_head = tens["R_headshaft"]

    T_Nm   = calc_torsional_moment(P_total, inp.n_rpm)
    A_m, B_m = 0.080, 0.400
    M_Nm   = R_head * A_m
    gov    = StructuralStressEngine.shaft_diameter_governing(
                 T_Nm, M_Nm, R_head, A_m, B_m)
    d_mm         = gov["d_governing_mm"]
    d_stress_mm  = gov["d_stress_mm"]
    d_deflect_mm = gov["d_deflect_mm"]
    governed_by  = gov["governed_by"]

    belt_w   = BW_mm
    motor_kw = select_motor(P_total, inp.sf)
    cr       = centrifugal_ratio(v, inp.D_mm)
    theta_rel = release_angle_deg(v, inp.D_mm)
    trajectory = discharge_trajectory(v, inp.D_mm, 60)
    L10      = calc_bearing_life(R_head, inp.n_rpm)
    belt_ply = math.ceil(F_eff / (belt_w / 25.4 * 4450 * 0.5))

    # ── Engineering checks ────────────────────────────────────────
    checks = []
    v_min, v_max = bucket["v_min"], bucket["v_max"]

    if Q < inp.Q_req:
        checks.append({"type":"fail","msg":f"Capacity {Q:.1f} t/h < required {inp.Q_req} t/h [CEMA 375 §4]"})
    else:
        checks.append({"type":"ok","msg":f"Capacity OK: {Q:.1f} t/h ≥ {inp.Q_req} t/h [CEMA 375 §4]"})

    if v < v_min:
        checks.append({"type":"warn","msg":f"Speed {v:.2f} m/s below CEMA min {v_min:.2f} m/s for bucket {bucket['id']} — back-legging risk [CEMA 375 §6]"})
    elif v > v_max:
        checks.append({"type":"fail","msg":f"Speed {v:.2f} m/s exceeds CEMA max {v_max:.2f} m/s for bucket {bucket['id']} — scatter [CEMA 375 §6]"})
    else:
        checks.append({"type":"ok","msg":f"Speed {v:.2f} m/s within CEMA range {v_min:.2f}–{v_max:.2f} m/s [CEMA 375 §6]"})

    if cr < 1.0:
        checks.append({"type":"warn","msg":f"CR={cr:.3f} < 1.0 — gravity/mixed discharge [CEMA 375 §3]"})
    elif cr <= 1.8:
        checks.append({"type":"ok","msg":f"CR={cr:.3f} — optimal centrifugal range 1.0–1.8 [CEMA 375 §3]"})
    elif cr <= 2.5:
        checks.append({"type":"info","msg":f"CR={cr:.3f} — centrifugal discharge acceptable [CEMA 375 §3]"})
    else:
        checks.append({"type":"warn","msg":f"CR={cr:.3f} > 2.5 — excessive scatter risk [CEMA 375 §3]"})

    T_total = T1 + T2 + T3
    if T_total > 80000:
        checks.append({"type":"fail","msg":f"Headshaft load {T_total/1000:.1f} kN — verify belt/pulley ratings [CEMA 375 §4]"})
    elif T_total > 50000:
        checks.append({"type":"warn","msg":f"Headshaft load {T_total/1000:.1f} kN — approaching heavy-duty belt [CEMA 375 §4]"})
    else:
        checks.append({"type":"ok","msg":f"Headshaft load {T_total/1000:.1f} kN — within standard belt capacity [CEMA 375 §4]"})

    checks.append({"type":"info","msg":
        f"Shaft governed by {governed_by}: {d_mm:.1f} mm "
        f"(stress {d_stress_mm:.1f} mm, deflection {d_deflect_mm:.1f} mm) [CEMA 375 §4]"})

    if L10 < 20000:
        checks.append({"type":"warn","msg":f"Bearing L10={L10:.0f} h < 20,000 h minimum [CEMA 375 §4]"})
    elif L10 < 40000:
        checks.append({"type":"info","msg":f"Bearing L10={L10:.0f} h — acceptable [CEMA 375 §4]"})
    else:
        checks.append({"type":"ok","msg":f"Bearing L10={L10:.0f} h — excellent [CEMA 375 §4]"})

    if Ceff > 1.25:
        checks.append({"type":"warn","msg":f"Ceff={Ceff:.2f} — high drive losses [CEMA 375 §4]"})

    abr = mat["abr_code"]
    if abr >= 6:
        checks.append({"type":"warn","msg":f"Abrasive code {abr}/7 — AR-steel or ceramic bucket/casing [CEMA 550]"})
    elif abr >= 4:
        checks.append({"type":"info","msg":f"Abrasive code {abr}/7 — hardened bucket lip recommended [CEMA 550]"})

    hazards = mat.get("hazard_codes", [])
    if "B10" in hazards or "B11" in hazards:
        checks.append({"type":"warn","msg":"Explosive/flammable — ATEX/NEC Class II design, anti-static belt [CEMA 550]"})
    if "B1" in hazards:
        checks.append({"type":"info","msg":"Material aerates — dust control and venting required [CEMA 550]"})

    # ── Sweep data ────────────────────────────────────────────────
    speed_sweep = []
    for n in range(20, 201, 10):
        vn  = belt_speed(inp.D_mm, n)
        Qn  = calc_capacity(vn, spacing, bucket["V"], inp.fill_pct, rho)
        pn  = calc_power_cema375(Qn, inp.H_m, D_boot_m, Leq, Ceff)
        crn = centrifugal_ratio(vn, inp.D_mm)
        speed_sweep.append({"rpm":n, "speed":round(vn,2), "capacity":round(Qn,1),
                             "power":round(pn["P_total"],2), "cr":round(crn,3)})

    fill_sweep = [{"fill":f, "capacity":round(calc_capacity(v, spacing, bucket["V"], f, rho),1)}
                  for f in range(30, 101, 5)]

    return {
        "Q": round(Q,2), "v": round(v,4), "spacing": round(spacing,4),
        "P_lift": round(pwr["P_lift"],3), "P_digging": round(pwr["P_digging"],3),
        "P_drive_loss": round(pwr["P_drive_loss"],3), "P_total": round(P_total,3),
        "Leq": Leq, "Ceff": Ceff, "motor_kw": motor_kw,
        "T1": round(T1,1), "T2": round(T2,1), "T3": round(T3,1),
        "F_eff": round(F_eff,1), "R_headshaft": round(R_head,1),
        "T_Nm": round(T_Nm,2), "d_mm": round(d_mm,1),
        "d_stress_mm": round(d_stress_mm,1), "d_deflect_mm": round(d_deflect_mm,1),
        "governed_by": governed_by, "belt_ply": belt_ply, "belt_w": belt_w,
        "cr": round(cr,4), "theta_rel": round(theta_rel,2),
        "trajectory": trajectory, "L10": round(L10,0),
        "speed_sweep": speed_sweep, "fill_sweep": fill_sweep,
        "checks": checks, "bucket": bucket, "mat": mat, "rho": rho,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

def run_optimizer(req: OptimizerRequest) -> List[dict]:
    inp      = req.base_input
    mat      = get_material(inp.mat_id)
    rho      = inp.custom_rho if inp.custom_rho > 0 else mat["rho_loose"]
    D_boot_m = inp.boot_pulley_D_mm / 1000.0
    Leq      = inp.Leq  if inp.Leq  > 0 else mat["Leq_default"]
    Ceff     = inp.Ceff if inp.Ceff > 0 else mat["Ceff_default"]
    objective = req.objective
    candidates = []

    for bucket in BUCKET_SERIES:
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
                bw_kg  = bucket["V"] * 1.5
                BW_mm  = select_belt_width(bucket["W"])
                tens   = calc_headshaft_tensions(Q, inp.H_m, v, bw_kg, spacing, BW_mm, 1.5, inp.K_takeup)
                T_total = tens["T1"] + tens["T2"] + tens["T3"]
                cr     = centrifugal_ratio(v, inp.D_mm)
                motor  = select_motor(P_total, inp.sf)
                cr_pen = 1000 if (cr < 1.0 or cr > 2.5) else 0

                if objective == "power":     score = P_total + cr_pen
                elif objective == "tension": score = T_total / 1000 + cr_pen
                elif objective == "motor":   score = motor + cr_pen
                else: score = P_total/10 + T_total/100000 + motor/5 + cr_pen

                candidates.append({
                    "rpm": rpm, "bucket_id": bucket["id"], "fill": fill,
                    "speed": round(v,2), "capacity": round(Q,1),
                    "power": round(P_total,2), "motor_kw": motor,
                    "T1_kN": round(T_total/1000,2), "cr": round(cr,3),
                    "score": round(score,4),
                })

    candidates.sort(key=lambda c: c["score"])
    for i, c in enumerate(candidates[:20]):
        c["rank"] = i + 1
    return candidates[:20]
