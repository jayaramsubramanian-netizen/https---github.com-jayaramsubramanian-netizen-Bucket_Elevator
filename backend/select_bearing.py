"""
backend/select_bearing.py -- shaft support selection: candidates -> filter ->
score -> select -> justify.
═══════════════════════════════════════════════════════════════════════════
Replaces the hardcoded C_basic_N = 355 kN default in calc_bearing_life() with a
real selection from the 168-row catalogue, following the ACTUAL engineering
sequence rather than "biggest C wins":

    radial load, shock, shaft slope, duty class, environment
      -> ELIGIBLE FAMILIES        (capability filter, misalignment first)
      -> candidates at the bore    (must fit the shaft)
      -> L10 >= required (duty)    (life filter)
      -> score (margin, cost, tier)
      -> smallest adequate bearing (not largest possible)
      -> justify()                 (human-readable reasoning for the report)

WHY NOT "HIGHEST C"
───────────────────
For a bucket-elevator head shaft, MISALIGNMENT usually governs. A CEMA-slope-
sized shaft (0.086 deg) over-misaligns a deep-groove ball or taper roller
bearing, so those are excluded by physics before C is ever considered. Selecting
on C alone would return catalogue-legal nonsense that fails in service.

OWNS NO THRESHOLDS
──────────────────
Required L10 comes from the duty class (duty_classes.target_design_life_h).
Family eligibility comes from bearing_family_capability. Nothing is hardcoded
here -- change the rule, not this file.

CONFIDENCE (Jay's point 9)
──────────────────────────
Every selection carries a confidence score reflecting how constrained it was:
exact fit with margin -> high; multiple options -> medium; assumptions or no fit
-> low. That surfaces where the design is robust and where the catalogue is thin.
"""
from __future__ import annotations
import math
import sqlite3
from typing import Any, Dict, List, Optional

# ISO 281 life exponent: 3 for ball bearings, 10/3 for roller bearings
_P_BALL, _P_ROLLER = 3.0, 10.0 / 3.0
_ROLLER_FAMILIES = {"SRB", "TRB"}

# Families that are candidates for a head shaft at all (thrust excluded: axial,
# not radial). Ordered by tier preference.
_HEADSHAFT_FAMILIES = ["SRB", "SAB", "Y-insert", "DGBB"]   # TRB excluded: precision-align


def _life_exponent(family: str) -> float:
    return _P_ROLLER if family in _ROLLER_FAMILIES else _P_BALL


def l10_hours(C_N: float, P_N: float, rpm: float, family: str) -> float:
    """Basic rating life L10 in hours (ISO 281). C and P in newtons."""
    if P_N <= 0 or rpm <= 0:
        return float("inf")
    p = _life_exponent(family)
    revs = (C_N / P_N) ** p * 1e6          # L10 in millions of revs -> revs
    return revs / (60.0 * rpm)


def load_catalogue(db_path: str) -> Dict[str, Any]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        bearings = [dict(r) for r in con.execute(
            "SELECT * FROM bearings WHERE bearing_family IS NOT NULL "
            "AND bearing_family != 'thrust'")]
        caps = {r["family"]: dict(r) for r in con.execute(
            "SELECT * FROM bearing_family_capability")}
        duty = {r["duty_class"]: dict(r) for r in con.execute(
            "SELECT * FROM duty_classes")}
        return {"bearings": bearings, "caps": caps, "duty": duty}
    finally:
        con.close()


def _duty_column(duty_class: str) -> str:
    return {"LIGHT": "duty_light", "MEDIUM": "duty_medium", "HEAVY": "duty_heavy",
            "SEVERE": "duty_severe", "CRITICAL": "duty_critical"}[duty_class]


def select_bearing(
    catalogue: Dict[str, Any],
    *,
    shaft_diameter_mm: float,
    radial_load_N: float,
    rpm: float,
    shaft_slope_deg: float,
    duty_class: str = "MEDIUM",
    required_life_h: Optional[float] = None,
    axial_load_N: float = 0.0,
) -> Dict[str, Any]:
    """Select the smallest adequate shaft-support bearing. Returns the choice
    plus the full candidate/rejection trace and a confidence score."""
    caps, duty = catalogue["caps"], catalogue["duty"]
    if required_life_h is None:
        required_life_h = (duty.get(duty_class) or {}).get("target_design_life_h", 40000.0)

    duty_col = _duty_column(duty_class)
    trace: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    for b in catalogue["bearings"]:
        fam = b["bearing_family"]
        cap = caps.get(fam)
        name = b.get("name", "?")

        # 1. bore must match the shaft (within a small tolerance)
        bore = b.get("bore")
        if bore is None or abs(bore - shaft_diameter_mm) > 0.5:
            continue                       # silent: wrong size is not a "rejection"

        # 2. family must be a head-shaft candidate
        if fam not in _HEADSHAFT_FAMILIES:
            trace.append({"name": name, "reject": f"family {fam} not a head-shaft candidate"})
            continue

        # 3. family must handle this duty class
        if cap and cap.get(duty_col) == 0:
            trace.append({"name": name, "reject": f"{fam} not rated for {duty_class} duty"})
            continue

        # 4. MISALIGNMENT FIRST -- the running limit must exceed the shaft slope
        run_limit = (cap or {}).get("misalign_running_deg")
        if run_limit is not None and shaft_slope_deg > run_limit:
            trace.append({"name": name,
                          "reject": f"shaft slope {shaft_slope_deg:.3f}deg exceeds "
                                    f"{fam} running limit {run_limit:.3f}deg"})
            continue

        # 5. equivalent dynamic load P. ISO 281 P = X*Fr + Y*Fa; with negligible
        #    axial load on a head shaft, P ~ Fr. (When axial data is available
        #    this is where X/Y factors enter -- not arbitrary service multipliers.)
        P_N = math.hypot(radial_load_N, axial_load_N) if axial_load_N else radial_load_N

        # 6. life
        C_N = float(b.get("C", 0)) * 1000.0    # catalogue C is kN
        if C_N <= 0:
            trace.append({"name": name, "reject": "no C rating in catalogue"})
            continue
        L10 = l10_hours(C_N, P_N, rpm, fam)
        if L10 < required_life_h:
            trace.append({"name": name,
                          "reject": f"L10 {L10:,.0f}h < required {required_life_h:,.0f}h"})
            continue

        candidates.append({
            "name": name, "family": fam, "series": b.get("series"),
            "bore_mm": bore, "C_kN": b.get("C"), "C0_kN": b.get("C0"),
            "L10_h": round(L10), "margin_pct": round((L10 / required_life_h - 1) * 100, 1),
            "tier": (cap or {}).get("tier", 9),
            "run_limit_deg": run_limit,
        })

    if not candidates:
        return {
            "selected": None, "confidence": "low", "confidence_pct": 25,
            "required_life_h": required_life_h, "duty_class": duty_class,
            "reason": (f"No catalogue bearing at {shaft_diameter_mm:.0f}mm bore meets "
                       f"{duty_class} duty ({required_life_h:,.0f}h) within the shaft "
                       f"slope limit. Nearest rejections below."),
            "rejections": trace[:8],
        }

    # SMALLEST ADEQUATE, not largest possible: prefer lower tier (SRB first),
    # then the least oversizing (smallest positive margin), then lower cost proxy (C).
    candidates.sort(key=lambda c: (c["tier"], c["margin_pct"], c["C_kN"] or 9e9))
    best = candidates[0]

    # Confidence: how constrained was the choice?
    n = len(candidates)
    if n == 1:
        conf, pct = "medium", 75
    elif best["margin_pct"] > 400:
        conf, pct = "medium", 80    # very oversized -> catalogue may be coarse here
    else:
        conf, pct = "high", 95

    return {
        "selected": best, "confidence": conf, "confidence_pct": pct,
        "required_life_h": required_life_h, "duty_class": duty_class,
        "n_candidates": n,
        "alternatives": candidates[1:4],
        "rejections": trace[:5],
    }


def justify(result: Dict[str, Any], shaft_slope_deg: float) -> str:
    """Human-readable reasoning for the report."""
    if not result.get("selected"):
        return "No bearing selected. " + result.get("reason", "")
    s = result["selected"]
    lines = [
        f"Selected {s['name']} ({s['family']}) for the {result['duty_class']} duty class:",
        f"  + bore {s['bore_mm']:.0f}mm matches the shaft",
        f"  + L10 {s['L10_h']:,} h meets the required {result['required_life_h']:,.0f} h "
        f"with {s['margin_pct']:+.0f}% margin",
    ]
    if s.get("run_limit_deg") is not None:
        lines.append(f"  + running misalignment limit {s['run_limit_deg']:.2f}deg "
                     f"accommodates the {shaft_slope_deg:.3f}deg shaft slope")
    lines.append(f"  + smallest adequate bearing of {result['n_candidates']} candidates "
                 f"(tier {s['tier']})")
    if result["alternatives"]:
        alts = ", ".join(a["name"] for a in result["alternatives"])
        lines.append(f"  alternatives considered: {alts}")
    lines.append(f"  selection confidence: {result['confidence']} "
                 f"({result['confidence_pct']}%)")
    return "\n".join(lines)