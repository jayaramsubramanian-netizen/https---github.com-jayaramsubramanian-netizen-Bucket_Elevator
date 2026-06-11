"""
VECTRIX™ — Reliability & Maintenance Schedule Generator
AKSHAYVIPRA EL-MEC · VECTOMEC™

maintenance_schedule(results, inputs) → structured schedule dict

Generates recommended maintenance intervals from:
  • Bearing L10 life (ISO 281)
  • Belt class and fill factor
  • Material abrasiveness (abr_code 0–7)
  • Material moisture and cohesion (plugging risk)
  • Lagging type and thickness
  • Liner wear rating from chute_flow.py

All intervals follow CEMA 375-2017 Appendix C guidance and standard
industrial conveyor maintenance practice (24/7 = 8,760 h/yr baseline).

Output dict structure
─────────────────────
{
    "schedule":     [MaintenanceItem, ...],   # periodic actions
    "replacements": [ReplacementItem, ...],   # life-based replacements
    "kpis": {
        "L10_hours":        float,
        "belt_life_h":      float,
        "liner_life_h":     float,
        "mtbf_h":           float,   # min replacement interval
        "annual_stops":     float,   # planned maintenance stops/year
    },
    "notes": [str, ...],
    "version": "1.0.0",
}

MaintenanceItem keys
────────────────────
task          str   Description of the maintenance task
interval_h    int   Interval in operating hours
interval_wk   int   Approximate interval in weeks (at operating_h_per_day)
category      str   "LUBRICATION" | "INSPECTION" | "ADJUSTMENT" | "CLEANING"
component     str   Specific component
trigger       str   Reason / standard reference
priority      str   "CRITICAL" | "ROUTINE" | "ADVISORY"

ReplacementItem keys
────────────────────
component     str
estimated_life_h  int
action        str
material_spec str
notes         str
priority      str
"""

import math

# ─── Operating hours baseline ────────────────────────────────────────────────
_H_PER_YEAR_CONT = 8_760    # 24/7
_H_PER_YEAR_2SHT = 6_000    # 2 shifts × 300 days
_H_PER_YEAR_1SHT = 3_000    # 1 shift

# ─── Bearing grease interval table (hours) by bearing bore and speed ─────────
# Based on ISO 281 / SKF grease life tables
# key: shaft speed bracket (rpm) → interval (h)
_BEARING_GREASE_H = {
    (0,   30):  8_000,
    (30,  60):  4_000,
    (60, 100):  3_000,
    (100,200):  2_000,
    (200,500):  1_500,
}

def _grease_interval(n_rpm: float) -> int:
    for (lo, hi), h in _BEARING_GREASE_H.items():
        if lo <= n_rpm < hi:
            return h
    return 1_500


# ─── Belt life estimates (h) by belt class and abrasiveness ─────────────────
# Conservatively based on OEM data sheets for elevated-temperature dry service
_BELT_LIFE_BASE_H = {
    "EP": 40_000,
    "ST": 60_000,
}

def _belt_life(belt_type: str, abr_code: int, fill_pct: float) -> int:
    base = _BELT_LIFE_BASE_H.get(belt_type, 40_000)
    # Abrasion penalty: each code above 3 reduces life 15%
    abr_pen = max(0, abr_code - 3) * 0.15
    # Overfill penalty: each 10% above 80% fill reduces life 10%
    fill_pen = max(0, (fill_pct - 80.0) / 10.0) * 0.10
    return int(base * (1.0 - abr_pen - fill_pen))


# ─── Liner life estimate (h) ─────────────────────────────────────────────────
_LINER_LIFE_BY_RATING = {
    "LOW":      20_000,
    "MEDIUM":   10_000,
    "HIGH":      4_000,
    "SEVERE":    2_000,
}

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _f(v, dp=1, fb="—"):
    try:
        return round(float(v), dp)
    except (TypeError, ValueError):
        return fb

def _h_to_wk(h: int, h_per_day: float) -> int:
    if h_per_day <= 0:
        return 9999
    return max(1, int(h / (h_per_day * 7)))


# ─── Main function ────────────────────────────────────────────────────────────

def maintenance_schedule(
    results: dict,
    inputs:  dict,
    operating_h_per_day: float = 20.0,
) -> dict:
    """
    Generate a reliability and maintenance schedule.

    Parameters
    ----------
    results             : solve_elevator() result dict
    inputs              : BucketElevatorInput dict / model_dump()
    operating_h_per_day : Planned daily operating hours (default 20h = 2 shifts + standby)
    """
    r   = results or {}
    inp = inputs  or {}
    mat = r.get("mat") or r.get("material") or {}
    lag = r.get("lagging") or {}
    dc  = r.get("discharge_chute") or {}
    mnt = dc.get("maintenance") or {}
    bf  = r.get("bolt_fatigue") or {}
    tg  = r.get("takeup_gravity") or {}

    n_rpm     = float(inp.get("n_rpm") or 60)
    belt_type = inp.get("belt_type") or "EP"
    fill_pct  = float(inp.get("fill_pct") or 75)
    abr_code  = int(mat.get("abr_code") or 3)
    moisture  = float(mat.get("moisture_pct") or 0)
    cohesion  = float(mat.get("cohesion") or 0)
    H_m       = float(inp.get("H_m") or 25)

    L10          = float(r.get("L10") or r.get("L10_hours") or 20_000)
    wear_rating  = mnt.get("wear_rating") or "MEDIUM"
    plug_risk    = mnt.get("plugging_risk") or "LOW"
    dust_risk    = mnt.get("dust_risk") or "LOW"
    lag_type     = (lag.get("lagging_type") or "rubber_herringbone").replace("_", " ")
    lag_t_mm     = float(lag.get("thickness_mm") or 12)
    goodman      = float(bf.get("goodman_ratio") or 0.5)
    inf_life     = bf.get("pass_infinite_life", True)

    grease_h   = _grease_interval(n_rpm)
    belt_life  = _belt_life(belt_type, abr_code, fill_pct)
    liner_life = _LINER_LIFE_BY_RATING.get(wear_rating, 10_000)

    # Bearing replacement: L10 at 90% confidence → schedule at 0.7 × L10
    bearing_repl_h = int(L10 * 0.70)

    # Lagging replacement: rubber wears through at ~0.5mm per 2000h on abrasive
    if "rubber" in lag_type.lower():
        lag_life_h = int(lag_t_mm / max(abr_code, 1) * 2_000)
    elif "ceramic" in lag_type.lower():
        lag_life_h = int(lag_t_mm * 3_000)
    else:
        lag_life_h = 30_000

    # Bucket bolt inspection: more frequent for high Goodman ratio
    bolt_inspect_h = 2_000 if goodman > 0.70 else (4_000 if goodman > 0.40 else 8_000)

    # Take-up inspection
    takeup_inspect_h = 2_000

    # Chute cleaning: moisture + cohesion drive frequency
    if cohesion > 0.5 or moisture > 15:
        chute_clean_h = 500
    elif cohesion > 0.2 or moisture > 10:
        chute_clean_h = 1_000
    else:
        chute_clean_h = 2_000

    # ── Build schedule ───────────────────────────────────────────────────────
    schedule = []

    def add_task(task, interval_h, category, component, trigger, priority="ROUTINE"):
        schedule.append({
            "task":         task,
            "interval_h":  interval_h,
            "interval_wk": _h_to_wk(interval_h, operating_h_per_day),
            "category":    category,
            "component":   component,
            "trigger":     trigger,
            "priority":    priority,
        })

    # ── LUBRICATION ──────────────────────────────────────────────────────────
    add_task(
        f"Re-grease head shaft bearings ({grease_h:,}h interval)",
        grease_h,
        "LUBRICATION",
        "Head shaft pillow blocks × 2",
        f"ISO 281 grease life at {n_rpm:.0f} rpm; NLGI 2 lithium-complex grease",
        "CRITICAL",
    )
    add_task(
        "Re-grease boot / tail shaft bearings",
        grease_h,
        "LUBRICATION",
        "Boot shaft bearings × 2",
        f"Same interval as head shaft; use same grease specification",
        "CRITICAL",
    )
    add_task(
        "Check / top-up gearbox oil level",
        2_000,
        "LUBRICATION",
        "Helical-bevel gearbox",
        "Oil consumption and seal check; ISO VG 220 synthetic gear oil typical",
        "ROUTINE",
    )
    add_task(
        "Gearbox oil change",
        8_000,
        "LUBRICATION",
        "Helical-bevel gearbox",
        "Contaminant buildup regardless of oil condition; drain and flush",
        "ROUTINE",
    )

    # ── INSPECTION ────────────────────────────────────────────────────────────
    add_task(
        "Belt visual inspection — splice, cover condition, edge fraying",
        500,
        "INSPECTION",
        f"Elevator belt ({belt_type} {r.get('belt_ply','—')} PLY)",
        f"Abrasion code {abr_code}/7; belt life estimate {belt_life:,}h",
        "CRITICAL" if abr_code >= 5 else "ROUTINE",
    )
    add_task(
        "Bucket condition + bolt torque check",
        bolt_inspect_h,
        "INSPECTION",
        "Buckets + M12 attachment bolts",
        f"Goodman ratio {goodman:.3f}; "
        f"{'below infinite life — inspect more frequently' if not inf_life else 'within infinite life'}",
        "CRITICAL" if not inf_life else "ROUTINE",
    )
    add_task(
        "Lagging thickness measurement + adhesion check",
        4_000,
        "INSPECTION",
        f"Head pulley {lag_type} lagging",
        f"Min remaining thickness = {lag_t_mm*0.4:.0f}mm (40% of new {lag_t_mm:.0f}mm); "
        f"replace at 40% remaining",
        "ROUTINE",
    )
    add_task(
        "Take-up carriage travel and guide rail check",
        takeup_inspect_h,
        "INSPECTION",
        "Gravity take-up frame",
        "Verify counterweight moves freely; check rails for wear and alignment",
        "ROUTINE",
    )
    add_task(
        "Casing panel and bolted joint inspection",
        4_000,
        "INSPECTION",
        "Casing structure",
        "Check stiffener welds, access door seals, and panel distortion",
        "ROUTINE",
    )
    add_task(
        "Drive coupling alignment check",
        8_000,
        "INSPECTION",
        "Motor-gearbox coupling",
        "Thermal expansion can cause misalignment after initial run-in period",
        "ROUTINE",
    )

    # ── ADJUSTMENT ────────────────────────────────────────────────────────────
    add_task(
        "Belt tension re-adjustment after stretch (new belt only)",
        250,
        "ADJUSTMENT",
        "Take-up counterweight",
        "New belts settle during first 250h; verify T3 ≥ minimum Euler value",
        "CRITICAL",
    )
    add_task(
        "Belt tracking check and centralising adjustment",
        1_000,
        "ADJUSTMENT",
        "Belt / casing",
        "Edge contact with casing accelerates wear; centralise using boot pulley shimming",
        "ROUTINE",
    )

    # ── CLEANING ─────────────────────────────────────────────────────────────
    add_task(
        "Discharge chute clean-out and blockage check",
        chute_clean_h,
        "CLEANING",
        "Discharge chute",
        f"Material: cohesion={cohesion:.2f}, moisture={moisture:.0f}% — "
        f"plugging risk {plug_risk}",
        "CRITICAL" if plug_risk in ("HIGH","SEVERE") else "ROUTINE",
    )
    if dust_risk in ("HIGH", "SEVERE"):
        add_task(
            "Dust extraction filter check / blow-down",
            500,
            "CLEANING",
            "Dust extraction system",
            f"Dust risk {dust_risk} for this material; filter blind-off risk",
            "CRITICAL",
        )
    add_task(
        "Boot section clean-out (material spillage)",
        2_000,
        "CLEANING",
        "Boot / feed section",
        "Accumulated fines can overload belt return and damage boot pulley bearings",
        "ROUTINE",
    )

    # ── REPLACEMENTS ─────────────────────────────────────────────────────────
    replacements = []

    def add_repl(component, life_h, action, spec, notes, priority="ROUTINE"):
        replacements.append({
            "component":          component,
            "estimated_life_h":   life_h,
            "estimated_life_yr":  round(life_h / (operating_h_per_day * 365), 1),
            "action":             action,
            "material_spec":      spec,
            "notes":              notes,
            "priority":           priority,
        })

    add_repl(
        "Head and boot shaft bearings",
        bearing_repl_h,
        "Replace both bearing sets",
        "Match OEM bore and outside diameter; upgrade to sealed bearings if possible",
        f"Scheduled at 70% of L10={L10:,.0f}h; actual replacement triggered by "
        f"vibration level or temperature rise",
        "CRITICAL",
    )
    add_repl(
        f"Elevator belt ({belt_type})",
        belt_life,
        "Full belt replacement + splice",
        f"{belt_type} belt, BW={r.get('belt_w','—')}mm, "
        f"{r.get('belt_ply','—')} PLY, minimum rated tension ≥ T1+T2+T3",
        f"Abr code {abr_code}/7, fill {fill_pct:.0f}% — estimate ±30%; "
        f"condition-monitor splice and cover",
        "CRITICAL",
    )
    add_repl(
        f"Head pulley lagging ({lag_type})",
        lag_life_h,
        "Strip and re-lag (hot vulcanised preferred) or replace pulley",
        f"{lag_type.capitalize()} lagging t={lag_t_mm:.0f}mm",
        f"Replace when <{lag_t_mm*0.4:.0f}mm remaining or if slip events increase",
        "ROUTINE",
    )
    add_repl(
        "Discharge chute wear liner",
        liner_life,
        f"Replace liner panels — {mnt.get('liner_material','mild steel')}",
        f"{mnt.get('liner_material','mild steel')} t={mnt.get('liner_thickness_mm','—')}mm",
        f"Wear rating {wear_rating}; measure residual thickness at 50% of estimated life",
        "CRITICAL" if wear_rating in ("HIGH","SEVERE") else "ROUTINE",
    )
    add_repl(
        "Bucket set (full replacement)",
        belt_life * 1.5,
        "Replace all buckets and attachment bolts simultaneously",
        f"Series {r.get('bucket',{}).get('id','—')} HDPE / steel; "
        f"M12 A2-70 stainless bolt set",
        "Buckets outlast belt on most materials; inspect at each belt change",
        "ROUTINE",
    )

    # ── KPIs ─────────────────────────────────────────────────────────────────
    min_repl_h = min(
        bearing_repl_h, belt_life, lag_life_h, liner_life
    )
    annual_h = operating_h_per_day * 365
    annual_stops = round(annual_h / min_repl_h, 1)

    kpis = {
        "L10_hours":            round(L10, 0),
        "bearing_repl_h":       bearing_repl_h,
        "belt_life_h":          belt_life,
        "lagging_life_h":       lag_life_h,
        "liner_life_h":         liner_life,
        "grease_interval_h":    grease_h,
        "mtbf_h":               min_repl_h,
        "operating_h_per_day":  operating_h_per_day,
        "annual_operating_h":   round(annual_h, 0),
        "annual_planned_stops": annual_stops,
    }

    notes = [
        f"Bearing grease interval: {grease_h:,}h at {n_rpm:.0f} rpm (ISO 281 grease life).",
        f"Belt life estimate: {belt_life:,}h for {belt_type} belt at abrasion code {abr_code}/7 "
        f"and {fill_pct:.0f}% fill (±30% — condition-monitor in service).",
        f"Liner life estimate: {liner_life:,}h for {wear_rating.lower()} wear rating.",
        "All intervals assume clean, dry operating environment. Adjust for moisture, "
        "temperature extremes, or abrasive ingress.",
        "Critical items (CRITICAL priority) must be completed on schedule. "
        "Deferral may void bearing and belt warranties.",
        "Operating hours per day assumed: " + str(operating_h_per_day) + "h "
        "(adjust intervals proportionally for different utilisation).",
    ]

    # Sort schedule by interval (shortest first)
    schedule.sort(key=lambda x: x["interval_h"])

    return {
        "schedule":     schedule,
        "replacements": replacements,
        "kpis":         kpis,
        "notes":        notes,
        "version":      "1.0.0",
    }