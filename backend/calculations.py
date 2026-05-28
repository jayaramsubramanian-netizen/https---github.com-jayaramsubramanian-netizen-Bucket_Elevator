"""
VECTRIX™ — CEMA Bucket Elevator Calculations
Ported from VECTOMEC™ HTML app physics engine.
"""

import math
from typing import List, Dict, Any
from models import (
    BucketElevatorInput, BucketElevatorResult,
    BucketData, MaterialData, CheckItem, TrajectoryPoint,
    SpeedSweepPoint, FillSweepPoint, OptimizerRequest, OptimizerCandidate
)

# ─── REFERENCE DATA ──────────────────────────────────────────────

MATERIALS = [
    {"id": "wheat",     "name": "Wheat",              "rho": 770,  "angle": 28, "abr": "A", "flow": "Free",    "Km": 1.0},
    {"id": "corn",      "name": "Corn (Maize)",        "rho": 720,  "angle": 25, "abr": "A", "flow": "Free",    "Km": 1.0},
    {"id": "soybeans",  "name": "Soybeans",            "rho": 770,  "angle": 29, "abr": "A", "flow": "Free",    "Km": 1.0},
    {"id": "rice",      "name": "Rice (rough)",        "rho": 580,  "angle": 38, "abr": "B", "flow": "Average", "Km": 1.1},
    {"id": "sugar",     "name": "Sugar (granulated)",  "rho": 850,  "angle": 35, "abr": "A", "flow": "Free",    "Km": 1.0},
    {"id": "salt",      "name": "Salt (fine)",         "rho": 1200, "angle": 32, "abr": "B", "flow": "Average", "Km": 1.1},
    {"id": "cement",    "name": "Cement (dry)",        "rho": 1500, "angle": 40, "abr": "D", "flow": "Poor",    "Km": 1.4},
    {"id": "limestone", "name": "Limestone (crushed)", "rho": 1450, "angle": 38, "abr": "C", "flow": "Average", "Km": 1.2},
    {"id": "coal",      "name": "Coal (bituminous)",   "rho": 850,  "angle": 38, "abr": "B", "flow": "Average", "Km": 1.1},
    {"id": "ironore",   "name": "Iron Ore (fines)",    "rho": 2000, "angle": 42, "abr": "D", "flow": "Poor",    "Km": 1.4},
    {"id": "sand",      "name": "Sand (dry)",          "rho": 1600, "angle": 35, "abr": "C", "flow": "Average", "Km": 1.2},
    {"id": "clinker",   "name": "Clinker",             "rho": 1300, "angle": 45, "abr": "D", "flow": "Poor",    "Km": 1.5},
    {"id": "flyash",    "name": "Fly Ash",             "rho": 800,  "angle": 42, "abr": "B", "flow": "Poor",    "Km": 1.2},
    {"id": "phosphate", "name": "Phosphate Rock",      "rho": 1200, "angle": 38, "abr": "C", "flow": "Average", "Km": 1.3},
    {"id": "woodchips", "name": "Wood Chips",          "rho": 250,  "angle": 40, "abr": "A", "flow": "Poor",    "Km": 1.1},
    {"id": "custom",    "name": "Custom Material",     "rho": 1000, "angle": 35, "abr": "B", "flow": "Average", "Km": 1.1},
]

BUCKET_SERIES = [
    {"id": "AA", "name": "Series AA — Super Capacity",  "W": 305, "H": 203, "P": 190, "V": 7.4,  "proj": "CC"},
    {"id": "A",  "name": "Series A — Extra Capacity",   "W": 254, "H": 178, "P": 165, "V": 5.0,  "proj": "CC"},
    {"id": "B",  "name": "Series B — Medium Capacity",  "W": 203, "H": 152, "P": 140, "V": 3.3,  "proj": "CC"},
    {"id": "C",  "name": "Series C — Centrifugal",      "W": 152, "H": 127, "P": 115, "V": 1.9,  "proj": "CC"},
    {"id": "D",  "name": "Series D — Centrifugal Sm.",  "W": 102, "H": 89,  "P": 89,  "V": 0.77, "proj": "CC"},
    {"id": "MF", "name": "Series MF — Milk of Lime",   "W": 254, "H": 152, "P": 152, "V": 4.0,  "proj": "CC"},
    {"id": "PF", "name": "Series PF — Pellet/Feed",    "W": 305, "H": 203, "P": 178, "V": 6.5,  "proj": "CC"},
    {"id": "HF", "name": "Series HF — High Capacity",  "W": 356, "H": 254, "P": 229, "V": 11.2, "proj": "CC"},
]

BELT_WIDTHS = [102, 127, 152, 178, 203, 254, 305, 356, 406, 457, 508, 610, 762, 914]
MOTOR_SIZES = [0.37,0.55,0.75,1.1,1.5,2.2,3,4,5.5,7.5,11,15,18.5,22,30,37,45,55,75,90,110,132,160,200,250]

# ─── PHYSICS FUNCTIONS ───────────────────────────────────────────

def belt_speed(D_mm: float, n_rpm: float) -> float:
    """Belt speed from head pulley diameter and RPM (m/s)."""
    return math.pi * D_mm / 1000 * n_rpm / 60


def centrifugal_ratio(v_ms: float, D_mm: float) -> float:
    """v² / (r·g) — >1 indicates centrifugal discharge."""
    r = D_mm / 2000
    return (v_ms ** 2) / (r * 9.81)


def release_angle_deg(v_ms: float, D_mm: float) -> float:
    """Material release angle from vertical (degrees)."""
    r = D_mm / 2000
    if v_ms <= 0:
        return 90.0
    cos_theta = (9.81 * r) / (v_ms ** 2)
    cos_theta = max(-1, min(1, cos_theta))
    return math.degrees(math.acos(cos_theta))


def discharge_trajectory(v_ms: float, D_mm: float, steps: int = 50) -> List[Dict]:
    """Projectile trajectory from release point (mm, relative to pulley centre)."""
    r = D_mm / 2000
    theta_rad = math.radians(release_angle_deg(v_ms, D_mm))
    rx0 = r * math.sin(theta_rad)
    ry0 = r * math.cos(theta_rad)
    vx = v_ms * math.cos(theta_rad)
    vy = v_ms * math.sin(theta_rad)
    pts = []
    dt = 0.04
    for i in range(steps + 1):
        t = i * dt
        x = rx0 + vx * t
        y = ry0 + vy * t - 0.5 * 9.81 * t * t
        pts.append({"x": round(x * 1000, 1), "y": round(y * 1000, 1)})
        if y < -r * 2:
            break
    return pts


def calc_capacity(v_ms: float, spacing_m: float, V_bucket_L: float,
                  fill_pct: float, rho: float) -> float:
    """CEMA capacity: Q [t/h] = (v/s) * Vb * eta * rho * 3.6"""
    Vb = V_bucket_L / 1000  # m³
    eta = fill_pct / 100
    return (v_ms / spacing_m) * Vb * eta * rho * 3.6


def calc_power(Q_th: float, H_m: float, Km: float, horiz_factor: float = 0.06):
    """CEMA elevator power (kW)."""
    P_lift = Q_th * H_m / 367
    P_frict = P_lift * horiz_factor * Km
    P_total = (P_lift + P_frict) * Km
    return P_lift, P_frict, P_total


def calc_tension(P_kw: float, v_ms: float, mu: float, wrap_deg: float):
    """Belt tension — Euler belt equation."""
    v_ms = max(v_ms, 0.01)
    F_eff = P_kw * 1000 / v_ms
    theta = math.radians(wrap_deg)
    emu = math.exp(mu * theta)
    T1 = F_eff * emu / (emu - 1)
    T2 = T1 / emu
    return T1, T2, F_eff, T1 / T2


def calc_shaft(P_kw: float, n_rpm: float, tau_pa: float = 55e6):
    """Shaft torque and minimum diameter (torsion only)."""
    omega = 2 * math.pi * n_rpm / 60
    T_Nm = P_kw * 1000 / max(omega, 0.01)
    d_m = (16 * T_Nm / (math.pi * tau_pa)) ** (1/3)
    return T_Nm, d_m * 1000


def calc_bearing_life(T_Nm: float, n_rpm: float, d_shaft_mm: float,
                      C_basic: float = 80000) -> float:
    """Approximate L10 bearing life (hours)."""
    P_load = T_Nm * 2 / max(d_shaft_mm / 1000, 0.001)
    L10 = (C_basic / max(P_load, 1)) ** 3 * 1e6 / (60 * n_rpm)
    return L10


def select_motor(P_kw: float, sf: float) -> float:
    req = P_kw * sf
    for m in MOTOR_SIZES:
        if m >= req:
            return m
    return MOTOR_SIZES[-1]


def select_bucket_auto(Q_th: float, rho: float, v_ms: float, bucket_gap: float) -> Dict:
    for b in BUCKET_SERIES:
        spacing = (b["P"] + bucket_gap) / 1000
        Q_est = calc_capacity(v_ms, spacing, b["V"], 75, rho)
        if Q_est >= Q_th:
            return b
    return BUCKET_SERIES[-1]


def select_belt_width(bucket_w_mm: float) -> int:
    for w in BELT_WIDTHS:
        if w >= bucket_w_mm + 25:
            return w
    return BELT_WIDTHS[-1]


def get_material(mat_id: str) -> Dict:
    for m in MATERIALS:
        if m["id"] == mat_id:
            return m
    return MATERIALS[0]


# ─── FULL SOLVER ──────────────────────────────────────────────────

def solve_elevator(inp: BucketElevatorInput) -> dict:
    mat = get_material(inp.mat_id)
    rho = inp.custom_rho if inp.custom_rho > 0 else mat["rho"]

    v = belt_speed(inp.D_mm, inp.n_rpm)

    if inp.auto_bucket:
        bucket = select_bucket_auto(inp.Q_req, rho, v, inp.bucket_gap)
    else:
        bucket = next((b for b in BUCKET_SERIES if b["id"] == inp.bucket_id), BUCKET_SERIES[2])

    spacing = (bucket["P"] + inp.bucket_gap) / 1000
    Q = calc_capacity(v, spacing, bucket["V"], inp.fill_pct, rho)

    P_lift, P_frict, P_total = calc_power(Q, inp.H_m, mat["Km"])
    T1, T2, F_eff, tension_ratio = calc_tension(P_total, v, inp.mu, inp.wrap_deg)
    T_Nm, d_mm = calc_shaft(P_total, inp.n_rpm)
    belt_w = select_belt_width(bucket["W"])
    motor_kw = select_motor(P_total, inp.sf)
    cr = centrifugal_ratio(v, inp.D_mm)
    theta_rel = release_angle_deg(v, inp.D_mm)
    trajectory = discharge_trajectory(v, inp.D_mm, 50)
    L10 = calc_bearing_life(T_Nm, inp.n_rpm, d_mm * 1.2)

    # Engineering checks
    checks = []
    if Q < inp.Q_req:
        checks.append({"type": "fail", "msg": f"Capacity {Q:.1f} t/h < required {inp.Q_req} t/h"})
    else:
        checks.append({"type": "ok", "msg": f"Capacity OK: {Q:.1f} t/h ≥ {inp.Q_req} t/h"})

    if v > 2.5:
        checks.append({"type": "warn", "msg": f"Belt speed {v:.2f} m/s may cause spillage"})
    if v < 0.5:
        checks.append({"type": "warn", "msg": f"Belt speed {v:.2f} m/s — risk of back-legging"})

    if cr < 0.8:
        checks.append({"type": "warn", "msg": f"Centrifugal ratio {cr:.2f} — gravity discharge (not centrifugal)"})
    elif cr > 2.5:
        checks.append({"type": "warn", "msg": f"Centrifugal ratio {cr:.2f} — may cause material scatter"})
    else:
        checks.append({"type": "ok", "msg": f"Centrifugal discharge OK (ratio {cr:.2f})"})

    if T1 > 50000:
        checks.append({"type": "fail", "msg": f"Tight side tension {T1/1000:.1f} kN — check belt rating"})
    if L10 < 20000:
        checks.append({"type": "warn", "msg": f"Bearing L10 life {L10:.0f} h — consider upgrade"})
    if d_mm > inp.D_mm * 0.4:
        checks.append({"type": "warn", "msg": f"Shaft dia {d_mm:.0f} mm large relative to pulley"})

    # Speed sweep (RPM 20–200)
    speed_sweep = []
    for n in range(20, 201, 10):
        vn = belt_speed(inp.D_mm, n)
        Qn = calc_capacity(vn, spacing, bucket["V"], inp.fill_pct, rho)
        _, _, Pn = calc_power(Qn, inp.H_m, mat["Km"])
        crn = centrifugal_ratio(vn, inp.D_mm)
        speed_sweep.append({"rpm": n, "speed": round(vn, 2), "capacity": round(Qn, 1),
                             "power": round(Pn, 2), "cr": round(crn, 3)})

    # Fill sweep
    fill_sweep = []
    for f in range(30, 101, 5):
        Qf = calc_capacity(v, spacing, bucket["V"], f, rho)
        fill_sweep.append({"fill": f, "capacity": round(Qf, 1)})

    return {
        "Q": round(Q, 2),
        "v": round(v, 4),
        "spacing": round(spacing, 4),
        "P_lift": round(P_lift, 3),
        "P_frict": round(P_frict, 3),
        "P_total": round(P_total, 3),
        "motor_kw": motor_kw,
        "T1": round(T1, 1),
        "T2": round(T2, 1),
        "F_eff": round(F_eff, 1),
        "tension_ratio": round(tension_ratio, 4),
        "T_Nm": round(T_Nm, 2),
        "d_mm": round(d_mm, 2),
        "L10": round(L10, 0),
        "belt_w": belt_w,
        "cr": round(cr, 4),
        "theta_rel": round(theta_rel, 2),
        "trajectory": trajectory,
        "speed_sweep": speed_sweep,
        "fill_sweep": fill_sweep,
        "checks": checks,
        "bucket": bucket,
        "mat": mat,
        "rho": rho,
    }


# ─── OPTIMIZER ────────────────────────────────────────────────────

def run_optimizer(req: OptimizerRequest) -> List[dict]:
    inp = req.base_input
    mat = get_material(inp.mat_id)
    rho = inp.custom_rho if inp.custom_rho > 0 else mat["rho"]
    objective = req.objective
    candidates = []

    for bucket in BUCKET_SERIES:
        for rpm in range(40, 161, 10):
            for fill in range(60, 91, 5):
                v = belt_speed(inp.D_mm, rpm)
                spacing = (bucket["P"] + inp.bucket_gap) / 1000
                Q = calc_capacity(v, spacing, bucket["V"], fill, rho)
                if Q < inp.Q_req:
                    continue
                if v < 0.5 or v > 3.0:
                    continue
                _, _, P_total = calc_power(Q, inp.H_m, mat["Km"])
                T1, _, _, _ = calc_tension(P_total, v, inp.mu, inp.wrap_deg)
                cr = centrifugal_ratio(v, inp.D_mm)
                motor = select_motor(P_total, inp.sf)

                if objective == "power":
                    score = P_total
                elif objective == "tension":
                    score = T1 / 1000
                elif objective == "motor":
                    score = motor
                else:
                    # balanced: normalised composite
                    score = P_total / 10 + T1 / 100000 + motor / 5

                candidates.append({
                    "rpm": rpm,
                    "bucket_id": bucket["id"],
                    "fill": fill,
                    "speed": round(v, 2),
                    "capacity": round(Q, 1),
                    "power": round(P_total, 2),
                    "motor_kw": motor,
                    "T1_kN": round(T1 / 1000, 2),
                    "cr": round(cr, 3),
                    "score": round(score, 4),
                })

    # Sort and rank
    candidates.sort(key=lambda c: c["score"])
    for i, c in enumerate(candidates[:20]):
        c["rank"] = i + 1

    return candidates[:20]
