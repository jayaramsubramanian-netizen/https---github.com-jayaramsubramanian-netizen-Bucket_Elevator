"""
VECTRIX™ Root Cause Analysis Engine — root_cause.py
AKSHAYVIPRA EL-MEC · VECTOMEC™

analyse(results, inputs) → list[RootCauseFinding]

For every failed or warned engineering check, this module:

  1. Identifies which input parameters are the dominant drivers
  2. Applies closed-form analytical relationships (no re-solve required)
     to compute the exact parameter value that would just pass the check
  3. Maps that value to the nearest practical standard size / setting
  4. Ranks all corrective options by impact and ease of application
  5. Returns structured data consumed by RootCausePanel.jsx and the PDF report

Philosophy
──────────
Results over generics.  Every finding specifies WHAT to change and BY HOW MUCH,
not just "increase belt speed".  A correction like:
    "Set n_rpm = 72 (currently 60, +20%) → capacity 103 t/h ≥ 100 t/h required"
is a commercial-grade recommendation.  A correction like "increase RPM" is noise.

Analytical relationships used (all CEMA 375-2017 / ASME / ISO 281):
  Capacity:      Q = v/s × V × η × ρ × 3.6
  Belt speed:    v = π × D × n / 60
  CR:            CR = v² / (g × r)
  Euler slip:    e^(μθ) — minimum T3 from belt-pulley friction
  Shaft torque:  T = P × 1000 / ω
  Shaft stress:  d_min from Von Mises combined (τ + σ_b) criterion
  Bearing L10:   L10 = (C/R)^p × 10^6 / (60n)  [ISO 281]
  Bolt Goodman:  ratio = σ_a/σ_e + σ_m/σ_u      [Goodman criterion]
  Casing CR:     CR_max from x0 = r·sin(acos(1/CR)) ≤ wall_x
  Screw Euler:   d_core from F_euler = π²EI/L² ≥ 3×F_screw
  Plate:         t_min from Timoshenko plate theory δ = α·q·a⁴/(E·t³)
"""

import math
from typing import Any

# ─── Physical constants ────────────────────────────────────────────────────────
_G   = 9.81        # m/s²
_PI  = math.pi
_E   = 200e9       # Pa, steel Young's modulus

# Standard commercial bar diameters (mm) for shaft recommendations
_STD_SHAFT_MM  = [20,25,30,35,40,45,50,55,60,65,70,75,80,90,100,110,120]
# Standard screw core diameters (mm)
_STD_SCREW_MM  = [20,25,32,40,50,63,80,100]
_STD_HYD_MM    = [25,32,40,50,63,80,100,125]
# Standard plate thicknesses (mm)
_STD_PLATE_MM  = [3,4,5,6,8,10,12,16,20]
# Standard belt widths (mm)
_STD_BW_MM     = [300,350,400,450,500,600,650,750,800,900,1000,1200]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _s(v, default=0.0):
    """Safe float conversion with fallback."""
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _next_std(value, std_list):
    """Return the smallest standard size ≥ value."""
    for s in sorted(std_list):
        if s >= value:
            return s
    return sorted(std_list)[-1]


def _v_from_rpm(n_rpm, D_mm):
    return _PI * (D_mm / 1000.0) * n_rpm / 60.0


def _rpm_from_v(v_ms, D_mm):
    denom = _PI * max(D_mm, 1) / 1000.0
    return v_ms * 60.0 / denom


def _cr(v_ms, D_mm):
    r = D_mm / 2000.0
    return v_ms ** 2 / (_G * max(r, 1e-6))


def _v_for_cr(cr_target, D_mm):
    r = D_mm / 2000.0
    return math.sqrt(cr_target * _G * r)


def _pct_change(current, target):
    if abs(current) < 1e-9:
        return 0.0
    return (target - current) / current * 100.0


def _dir_label(noun: str, current: float, target: float) -> str:
    """
    Return 'Increase {noun}', 'Reduce {noun}', or 'Specify {noun}' based on
    whether the target is higher, lower, or equal to the current value.
    Avoids hardcoded 'Reduce' labels on corrections that actually increase the parameter.
    """
    if abs(current) < 1e-9:
        return f"Set {noun}"
    ratio = target / current
    if ratio > 1.02:
        return f"Increase {noun}"
    if ratio < 0.98:
        return f"Reduce {noun}"
    return f"Specify {noun}"


def _correction(param, label, current, target, unit, note, priority):
    """Build a standardised correction dict."""
    return {
        "param":       param,
        "label":       label,
        "current":     round(current, 2) if isinstance(current, float) else current,
        "target":      round(target, 2)  if isinstance(target, float)  else target,
        "unit":        unit,
        "change_pct":  round(_pct_change(current, target), 1)
                       if isinstance(current, (int, float)) else 0,
        "note":        note,
        "priority":    priority,
    }


def _driver(param, label, current, unit, impact_desc, priority):
    """Build a standardised driver dict."""
    return {
        "param":    param,
        "label":    label,
        "current":  round(current, 2) if isinstance(current, float) else current,
        "unit":     unit,
        "impact":   impact_desc,
        "priority": priority,
    }


def _finding(index, msg, severity, metric, drivers, corrections, explanation):
    return {
        "check_index":    index,
        "check_msg":      msg,
        "severity":       severity,
        "failure_metric": metric,
        "primary_driver": drivers[0]["param"] if drivers else "—",
        "drivers":        drivers,
        "corrections":    sorted(corrections, key=lambda c: c["priority"]),
        "explanation":    explanation,
    }


# ─── Main entry point ─────────────────────────────────────────────────────────

def _detect_conflicts(findings: list[dict]) -> list[dict]:
    """
    Cross-check corrections across all findings for conflicting direction.
    When Finding A says "increase fill_pct" and Finding B says "reduce fill_pct",
    mark both corrections with a conflict note so the engineer knows.

    This catches the common limestone-powder scenario: capacity check wants
    higher fill, chute plugging check wants lower fill — both are valid but
    mutually exclusive for a given design.
    """
    # Collect (param, direction, finding_index, correction_index) tuples
    # direction: +1 = increase, -1 = decrease
    param_directions: dict[str, list[tuple]] = {}

    for fi, f in enumerate(findings):
        for ci, c in enumerate(f["corrections"]):
            param = c.get("param")
            cur   = c.get("current")
            tgt   = c.get("target")
            if not param or cur is None or tgt is None:
                continue
            try:
                direction = 1 if float(tgt) > float(cur) * 1.02 else (
                            -1 if float(tgt) < float(cur) * 0.98 else 0)
            except (TypeError, ValueError):
                continue
            if direction == 0:
                continue
            param_directions.setdefault(param, []).append((direction, fi, ci))

    # Find params with conflicting directions
    conflicts: dict[tuple, str] = {}   # (fi, ci) → conflict message
    for param, entries in param_directions.items():
        dirs = {e[0] for e in entries}
        if len(dirs) < 2:
            continue   # all same direction — no conflict
        for direction, fi, ci in entries:
            other_checks = [
                f["check_msg"][:50] for (d, f_i, c_i) in entries
                if d != direction
                for f in [findings[f_i]]
            ]
            verb = "increasing" if direction == 1 else "reducing"
            conflicts[(fi, ci)] = (
                f"Conflicts with: {other_checks[0] if other_checks else 'another check'} "
                f"({verb} {param} worsens that check)"
            )

    # Annotate findings with conflict notes
    for (fi, ci), note in conflicts.items():
        c = findings[fi]["corrections"][ci]
        c["conflict"] = note

    return findings


def analyse(results: dict, inputs: dict) -> list[dict]:
    """
    Analyse all failed/warned engineering checks and return root-cause findings.

    Parameters
    ----------
    results : dict    — output of solve_elevator()
    inputs  : dict    — BucketElevatorInput.model_dump()

    Returns
    -------
    list of RootCauseFinding dicts (one per failed/warned check).
    Empty list when all checks pass.
    """
    r   = results or {}
    inp = inputs  or {}

    checks = r.get("checks", [])
    if not checks:
        return []

    # ── Extract result values ─────────────────────────────────────────────────
    Q       = _s(r.get("Q"))
    v       = _s(r.get("v"))
    cr      = _s(r.get("cr"))
    d_mm    = _s(r.get("d_mm"))
    L10     = _s(r.get("L10"))
    T1      = _s(r.get("T1"))
    T2      = _s(r.get("T2"))
    T3      = _s(r.get("T3"))
    F_eff   = _s(r.get("F_eff"))
    R_head  = _s(r.get("R_headshaft"))
    T_Nm    = _s(r.get("T_Nm"))
    P_total = _s(r.get("P_total"))
    spacing = _s(r.get("spacing"), 0.25)
    rho     = _s(r.get("rho"), 750)
    belt_w  = _s(r.get("belt_w"), 400)
    euler_chk = r.get("euler_check") or {}
    bf      = r.get("bolt_fatigue") or {}
    ts      = r.get("takeup_screw") or {}
    th      = r.get("takeup_hydraulic") or {}
    cc      = r.get("casing_clearance") or {}
    cp      = r.get("casing_panel") or {}
    dc      = r.get("discharge_chute") or {}
    bucket  = r.get("bucket") or {}
    mat     = r.get("mat") or {}
    # FIX (Jay: "make sure checks and design review backend and frontend
    # code are updated to have all new components... boot pulley/shaft,
    # take-up, shaft design, discharge, feed design, bucket styles, chain
    # elements accounted for"): boot_pulley and chain_selected were never
    # extracted here, so the boot bearing and chain SF/speed checks (both
    # real, computed elsewhere in calculations.py -- confirmed directly,
    # not assumed) had no corresponding root-cause finding at all.
    bp        = r.get("boot_pulley") or {}
    L10_boot  = _s(bp.get("L10_boot_h"))
    R_boot    = _s(bp.get("R_boot_N"))
    chain_sel = r.get("chain_selected") or {}
    chain_SF_actual = _s(r.get("chain_SF_actual"))
    chain_v_ok = r.get("chain_v_ok")
    chain_sf_req = _s(inp.get("chain_sf"), 6.0)

    # ── Extract input values ──────────────────────────────────────────────────
    Q_req     = _s(inp.get("Q_req"), 100)
    H_m       = _s(inp.get("H_m"), 25)
    D_mm      = _s(inp.get("D_mm"), 500)
    n_rpm     = _s(inp.get("n_rpm"), 60)
    fill_pct  = _s(inp.get("fill_pct"), 75)
    mu        = _s(inp.get("mu"), 0.35)
    wrap_deg  = _s(inp.get("wrap_deg"), 180)
    sf        = _s(inp.get("sf"), 1.25)
    K_takeup  = _s(inp.get("K_takeup"), 0.7)

    V_bkt    = _s(bucket.get("V"), 3.3)
    v_min_bkt = _s(bucket.get("v_min"), 1.0)
    v_max_bkt = _s(bucket.get("v_max"), 2.5)
    bkt_id   = bucket.get("id", "B")
    bw_kg    = _s(r.get("bucket_mass_kg"), 2.5)

    # Casing inner wall x-coord (half BW + 50mm)
    casing_wall_x = belt_w / 2000.0 + 0.050

    findings = []

    for i, check in enumerate(checks):
        sev = check.get("type", "ok")
        if sev not in ("fail", "warn"):
            continue
        msg = check.get("msg", "")
        ml  = msg.lower()

        # ─── 1. Capacity insufficient ────────────────────────────────────────
        if "capacity" in ml and ("< required" in ml or "< " in ml):
            # Minimum belt speed to meet Q_req
            if spacing > 0 and V_bkt > 0 and fill_pct > 0 and rho > 0:
                v_need = Q_req * spacing / (V_bkt / 1000.0 * fill_pct / 100.0 * rho * 3.6)
            else:
                v_need = v * (Q_req / max(Q, 0.1))
            n_need = _rpm_from_v(v_need, D_mm)
            n_std  = math.ceil(n_need / 5) * 5   # round up to next 5 rpm

            # Alternative: increase fill_pct
            fill_need = fill_pct * (Q_req / max(Q, 0.1)) if Q > 0 else fill_pct
            fill_std  = min(math.ceil(fill_need / 5) * 5, 90)

            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"↑{n_std - n_rpm:.0f} rpm raises Q from {Q:.1f} to {Q_req:.0f} t/h", 1),
                _driver("fill_pct", "Bucket fill", fill_pct, "%",
                    f"↑{fill_std - fill_pct:.0f}% raises capacity proportionally", 2),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed", n_rpm, float(n_std)),
                    n_rpm, n_std, "rpm",
                    f"v = {_v_from_rpm(n_std, D_mm):.2f} m/s — check CR and bucket speed limits after change",
                    1),
                _correction("fill_pct", _dir_label("fill factor", fill_pct, float(fill_std)),
                    fill_pct, fill_std, "%",
                    "Verify material flowability allows higher fill without bridging",
                    2),
            ]
            findings.append(_finding(i, msg, sev,
                f"Q = {Q:.1f} t/h < {Q_req:.0f} t/h required",
                drivers, corrections,
                f"Capacity is {Q:.1f} t/h, {Q_req - Q:.1f} t/h short of requirement. "
                f"At current fill {fill_pct:.0f}% and bucket series {bkt_id}, "
                f"minimum belt speed is {v_need:.2f} m/s (n = {n_need:.0f} rpm). "
                f"Check that the new speed is within bucket series limits "
                f"({v_min_bkt:.2f}–{v_max_bkt:.2f} m/s)."))

        # ─── 2. Belt speed below v_min ────────────────────────────────────────
        # FIX: previously matched on bare "below" + ("speed" or "v_min" or
        # "back-legging") anywhere in ANY check message -- confirmed live
        # this false-matched the discharge-section CR check's own corrective
        # instruction ("Reduce belt speed below v = 2.45 m/s", a ceiling to
        # aim FOR, not a report that current speed is below the floor),
        # causing this branch to fire and assert "v=1.70 < v_min=0.50" when
        # v was actually 3.4x ABOVE v_min. Now requires the exact phrase from
        # the genuine back-legging check (calculations.py ~L3173/3180/3186)
        # that this branch is actually designed to react to.
        elif "below cema min" in ml:
            n_need = _rpm_from_v(v_min_bkt * 1.05, D_mm)  # 5% margin above v_min
            n_std  = math.ceil(n_need / 5) * 5
            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"Currently {v:.2f} m/s < v_min {v_min_bkt:.2f} m/s for {bkt_id} bucket", 1),
                _driver("D_mm", "Head pulley dia", D_mm, "mm",
                    "Smaller D_mm reduces v at same RPM — opposite effect needed here", 2),
            ]
            corrections = [
                _correction("n_rpm", "Increase shaft speed",
                    n_rpm, n_std, "rpm",
                    f"v = {_v_from_rpm(n_std, D_mm):.2f} m/s ≥ v_min {v_min_bkt:.2f} m/s (5% margin)",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"v = {v:.2f} m/s < v_min {v_min_bkt:.2f} m/s for {bkt_id} bucket",
                drivers, corrections,
                f"Belt speed {v:.2f} m/s is below the CEMA minimum {v_min_bkt:.2f} m/s "
                f"for {bkt_id} series buckets. Back-legging risk: material slides back "
                f"before reaching the discharge point. Raise n_rpm to {n_std} rpm."))

        # ─── 3. Belt speed above v_max ────────────────────────────────────────
        # FIX: hardened the same way as branch 2 -- requires the exact
        # phrase from the genuine check (calculations.py ~L3191) instead of
        # a loose keyword union that could similarly false-match other
        # checks' corrective wording.
        elif "exceeds cema max" in ml:
            n_need = _rpm_from_v(v_max_bkt * 0.95, D_mm)  # 5% margin below v_max
            n_std  = math.floor(n_need / 5) * 5
            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"Currently {v:.2f} m/s > v_max {v_max_bkt:.2f} m/s for {bkt_id} bucket", 1),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed", n_rpm, float(n_std)),
                    n_rpm, n_std, "rpm",
                    f"v = {_v_from_rpm(n_std, D_mm):.2f} m/s ≤ v_max {v_max_bkt:.2f} m/s (5% margin)",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"v = {v:.2f} m/s > v_max {v_max_bkt:.2f} m/s for {bkt_id} bucket",
                drivers, corrections,
                f"Belt speed {v:.2f} m/s exceeds the CEMA maximum {v_max_bkt:.2f} m/s "
                f"for {bkt_id} series. Material scatter risk increases significantly above v_max. "
                f"Reduce n_rpm to {n_std} rpm."))

        # ─── 3b. CR ≥ 1.0 on a continuous (HF/MF/SC) bucket ──────────────────
        # NEW: this genuine fail (calculations.py ~L3204, "CR=X >= 1.0 --
        # centrifugal discharge occurring in HF elevator") previously had no
        # dedicated branch at all -- it only ever produced a finding by
        # accident, via branch 4's bug below (which asserted the OPPOSITE
        # relationship, "CR < 1.0", and recommended RAISING speed when this
        # check actually needs speed LOWERED). Now handled correctly and
        # directly, targeting the same CR=0.5 HF midpoint used by the
        # auto-bucket CR-target redesign (see calculations.py is_chain/
        # auto_bucket section) for consistency.
        elif "centrifugal discharge occurring in hf elevator" in ml:
            cr_target = 0.5
            v_need = _v_for_cr(cr_target, D_mm)
            n_need = _rpm_from_v(v_need, D_mm)
            n_std  = math.floor(n_need / 5) * 5
            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"CR = v²/(g·r) = {cr:.3f}; need < 1.0 for continuous (HF) discharge", 1),
                _driver("D_mm", "Head pulley dia", D_mm, "mm",
                    "Larger D_mm reduces CR at same v — alternative to lowering speed", 2),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed to CR=0.50", n_rpm, float(n_std)),
                    n_rpm, n_std, "rpm",
                    f"v = {v_need:.2f} m/s → CR = {cr_target:.2f} (HF optimal range 0.3-0.7)",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"CR = {cr:.3f} ≥ 1.0 (centrifugal discharge in HF elevator)",
                drivers, corrections,
                f"CR = v²/(g·r) = {cr:.3f}. HF/continuous discharge requires CR < 1.0 -- "
                f"material is being thrown rather than poured, defeating the design intent. "
                f"At D_mm = {D_mm:.0f}mm, target speed is {v_need:.2f} m/s "
                f"(n = {n_std} rpm) for CR = {cr_target:.2f}."))

        # ─── 4. CR < 1 (gravity/mixed discharge) ─────────────────────────────
        # FIX: previously matched on bare "< 1" anywhere in the message --
        # confirmed live this false-matched a CR=1.181 >= 1.0 FAIL check
        # ("HF design requires CR < 1.0 (reduce belt speed or increase
        # pulley D)") because "< 1" appears in that check's EXPLANATORY
        # clause describing the requirement, not in a statement that the
        # current CR is actually below 1. Confirmed live: this rendered
        # "CR = 1.181 < 1.0" -- a literally false headline, since 1.181 is
        # not less than 1.0 -- and recommended RAISING rpm when the real
        # check wanted rpm LOWERED to bring CR back under 1.0. Now requires
        # the exact phrase from the genuine low-CR check (calculations.py
        # ~L3222) this branch is actually designed for.
        elif "gravity/mixed discharge" in ml:
            cr_target = 1.25
            v_need = _v_for_cr(cr_target, D_mm)
            n_need = _rpm_from_v(v_need, D_mm)
            n_std  = math.ceil(n_need / 5) * 5
            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"CR = v²/(g·r) = {cr:.3f}; need ≥ 1.0 for centrifugal discharge", 1),
                _driver("D_mm", "Head pulley dia", D_mm, "mm",
                    "Smaller D_mm raises CR at same v — reduces required RPM", 2),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed to CR=1.25", n_rpm, float(n_std)),
                    n_rpm, n_std, "rpm",
                    f"v = {v_need:.2f} m/s → CR = {cr_target:.2f} (optimal centrifugal range)",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"CR = {cr:.3f} < 1.0 (gravity/mixed discharge mode)",
                drivers, corrections,
                f"CR = v²/(g·r) = {cr:.3f}. For clean centrifugal discharge, CR ≥ 1.0 is required "
                f"(optimal: 1.2–1.5). At D_mm = {D_mm:.0f}mm, minimum speed is "
                f"{v_need:.2f} m/s (n = {n_std} rpm) for CR = {cr_target:.2f}."))

        # ─── 5. CR > 2.5 (excessive scatter) ────────────────────────────────
        # FIX: hardened the same way -- requires the exact phrase from the
        # genuine check (calculations.py ~L3228) instead of a loose keyword
        # union ("scatter" alone could otherwise match other checks' use of
        # the same word in a different context).
        elif "excessive scatter risk" in ml:
            cr_target = 1.80
            v_need = _v_for_cr(cr_target, D_mm)
            n_need = _rpm_from_v(v_need, D_mm)
            n_std  = math.floor(n_need / 5) * 5
            D_need = D_mm * (cr / cr_target)   # larger D at same n
            D_std  = _next_std(D_need, _STD_BW_MM[:6])  # rough pulley sizes
            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"CR = {cr:.3f} > 2.5; reduce speed to bring CR to 1.5–1.8 range", 1),
                _driver("D_mm", "Head pulley dia", D_mm, "mm",
                    f"Larger D reduces CR at same v (CR ∝ v²/r, r = D/2)", 2),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed to CR=1.80", n_rpm, float(n_std)),
                    n_rpm, n_std, "rpm",
                    f"v = {v_need:.2f} m/s → CR = {cr_target:.2f}",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"CR = {cr:.3f} > 2.5 (excessive scatter risk)",
                drivers, corrections,
                f"CR = {cr:.3f} causes material to scatter into the casing head section "
                f"before entering the chute. CEMA recommends CR ≤ 2.5 for standard service. "
                f"Reduce n_rpm to {n_std} rpm for CR = {cr_target:.2f}."))

        # ─── 6. Belt slip (Euler-Eytelwein) ──────────────────────────────────
        elif "slip" in ml or "euler" in ml:
            T3_euler = _s(euler_chk.get("T2_minimum"), T3 * 1.2)
            e_ratio  = _s(euler_chk.get("euler_ratio"), math.exp(mu * wrap_deg * _PI / 180))
            T3_deficit = T3_euler - T3

            # Required mu at current wrap and tension ratio
            ratio = F_eff / max(T3, 1)
            mu_req = math.log(max(ratio, 1.001)) / (wrap_deg * _PI / 180) if wrap_deg > 0 else mu
            # Required wrap at current mu
            wrap_req = math.log(max(ratio, 1.001)) / max(mu, 0.01) * 180 / _PI if mu > 0 else wrap_deg
            wrap_req = min(wrap_req, 240)
            # Required K_takeup to increase T3
            K_need = K_takeup * (T3_euler / max(T3, 1))
            K_need = min(K_need, 0.9)

            drivers = [
                _driver("mu", "Lagging friction coeff", mu, "—",
                    f"Required μ = {mu_req:.3f} at wrap {wrap_deg:.0f}° to prevent slip", 1),
                _driver("wrap_deg", "Wrap angle", wrap_deg, "°",
                    f"Required wrap = {wrap_req:.0f}° at μ = {mu:.2f} to prevent slip", 2),
                _driver("K_takeup", "Take-up factor K", K_takeup, "—",
                    f"Increasing K raises T3; required T3 = {T3_euler:.0f} N vs current {T3:.0f} N", 3),
            ]
            corrections = [
                _correction("mu", "Upgrade lagging to ceramic (μ≈0.50)",
                    mu, 0.50, "—",
                    f"Ceramic lagging μ = 0.50 provides e^(μθ) = {math.exp(0.50 * wrap_deg * _PI / 180):.2f} "
                    f"vs required {e_ratio:.2f}",
                    1),
                _correction("wrap_deg", "Add snub pulley — increase wrap angle",
                    wrap_deg, round(wrap_req + 5), "°",
                    f"Snub pulley raises wrap from {wrap_deg:.0f}° to ~{wrap_req+5:.0f}°; "
                    f"verify geometry allows snub placement",
                    2),
                _correction("K_takeup", "Increase take-up tension factor",
                    K_takeup, round(K_need, 2), "—",
                    f"Raises T3 to ≥ {T3_euler:.0f} N required for no-slip; "
                    f"gravity take-up: increase counterweight",
                    3),
            ]
            findings.append(_finding(i, msg, sev,
                f"T3 = {T3:.0f} N < Euler min {T3_euler:.0f} N (deficit {T3_deficit:.0f} N)",
                drivers, corrections,
                f"The drive pulley will slip under load. T3 = {T3:.0f} N is "
                f"{T3_deficit:.0f} N below the Euler-Eytelwein minimum of {T3_euler:.0f} N "
                f"(μ={mu:.2f}, wrap={wrap_deg:.0f}°, e^μθ={e_ratio:.2f}). "
                f"Primary fix: upgrade lagging to ceramic (μ≈0.50). "
                f"Secondary: add snub pulley to increase wrap angle."))

        # ─── 7. Headshaft load ───────────────────────────────────────────────
        elif "headshaft load" in ml:
            T_total = T1 + T2 + T3
            limit   = 80000 if "80" in ml else 50000
            excess  = T_total - limit
            # % reduction needed
            pct_red = excess / T_total * 100
            # Required fill to reduce by pct_red (T1 ∝ Q ∝ fill)
            fill_red = fill_pct * (1.0 - pct_red / 200)  # partial — fill only affects T1
            fill_red = max(fill_red, 40)

            drivers = [
                _driver("fill_pct", "Bucket fill", fill_pct, "%",
                    f"T1 (material) ∝ fill_pct; reducing fill by {pct_red/2:.0f}% reduces T1 proportionally", 1),
                _driver("Q_req", "Required capacity", Q_req, "t/h",
                    "Lower Q_req reduces material tension T1 and power", 2),
                _driver("H_m", "Lift height", H_m, "m",
                    "H_m is a process constraint — typically not adjustable", 3),
            ]
            corrections = [
                _correction("fill_pct", "Reduce fill factor",
                    fill_pct, round(fill_red), "%",
                    "Reduces material mass per bucket → lower T1; verify capacity still meets Q_req",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"T_total = {T_total/1000:.1f} kN (T1={T1/1000:.1f} + T2={T2/1000:.1f} + T3={T3/1000:.1f} kN)",
                drivers, corrections,
                f"Total headshaft tension {T_total/1000:.1f} kN exceeds the recommended limit. "
                f"The dominant component is T1 (material tension = {T1/1000:.1f} kN), "
                f"driven by capacity and lift height. Consider a heavier-duty belt rating "
                f"or reducing fill factor to {fill_red:.0f}%."))

        # ─── 8. Shaft sizing ─────────────────────────────────────────────────
        elif "shaft" in ml and ("governed" in ml or "stress" in ml or "deflect" in ml):
            # At higher n_rpm, same power → lower torque → smaller required shaft
            # T_Nm = P × 1000 / ω; ω = 2π × n/60
            # If we increase n_rpm by factor k, T_Nm reduces by factor k
            d_calc_min = _s(r.get("d_stress_mm"), d_mm)
            d_need     = d_calc_min * 1.05   # 5% design margin
            d_std      = _next_std(d_need, _STD_SHAFT_MM)

            # RPM needed to reduce T_Nm so that current d_mm is adequate
            # d ∝ (T_Nm)^(1/3); to reduce d_min by factor (d_mm/d_calc_min):
            # need T_Nm reduced by factor (d_mm/d_calc_min)^3
            if d_calc_min > d_mm and d_mm > 0:
                torque_reduction_factor = (d_mm / d_calc_min) ** 3
                # T_Nm = P × 1000 / (2π × n / 60) → n_need = n × (1/reduction_factor)
                n_for_shaft = n_rpm / torque_reduction_factor
                n_for_shaft = math.ceil(n_for_shaft / 5) * 5
            else:
                n_for_shaft = n_rpm

            drivers = [
                _driver("shaft_d_override_mm", "Shaft diameter override", d_mm, "mm",
                    f"Specify d ≥ {d_std} mm (calc min {d_calc_min:.0f} mm + 5% margin)", 1),
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"Higher n_rpm → lower T_Nm at same power → smaller d_min required", 2),
            ]
            corrections = [
                _correction("shaft_d_override_mm", "Specify shaft diameter",
                    d_mm, float(d_std), "mm",
                    f"Next standard bar above calc min {d_calc_min:.0f} mm (+5% margin = {d_need:.0f} mm). "
                    f"Hub and key will be re-checked against this diameter.",
                    1),
                _correction("n_rpm", _dir_label("shaft speed", n_rpm, float(n_for_shaft)),
                    n_rpm, float(n_for_shaft), "rpm",
                    f"Higher n_rpm reduces T_Nm = P·1000/ω; verify CR and capacity after change",
                    2),
            ]
            findings.append(_finding(i, msg, sev,
                f"d_min = {d_calc_min:.0f} mm, current shaft = {d_mm:.0f} mm",
                drivers, corrections,
                f"The calculated minimum shaft diameter is {d_calc_min:.0f} mm (governed by "
                f"{r.get('governed_by','combined stress')}). "
                f"Specify shaft_d_override_mm = {d_std} mm in Design Overrides "
                f"(next standard commercial bar size above {d_need:.0f} mm with 5% margin)."))

        # ─── 9. Bearing L10 ──────────────────────────────────────────────────
        elif "bearing" in ml and "l10" in ml and "boot" not in ml:
            L10_target = 40000  # h design target
            # Proportional: L10 ∝ 1/n (constant load) → n_for_target = n × L10_actual / L10_target
            n_for_L10  = n_rpm * (L10 / max(L10_target, 1))
            n_std_L10  = max(int(n_for_L10 // 5) * 5, 10)
            practical  = n_std_L10 >= 35   # below 35 rpm impractical for bucket elevators

            # Bearing upgrade: C needed for L10_target at current n and R
            # L10 = (C/R)^3 × 10^6 / (60n) → C_need = R × (L10_target × 60n / 10^6)^(1/3)
            C_need_kN = R_head / 1000.0 * (L10_target * 60.0 * n_rpm / 1e6) ** (1.0 / 3.0)

            if practical:
                drivers = [
                    _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                        f"L10 ∝ 1/n; reduce from {n_rpm} to {n_std_L10} rpm "
                        f"→ L10 ≈ {L10_target:,}h (proportional scaling)", 1),
                    _driver("R_headshaft", "Headshaft radial load", round(R_head/1000,1), "kN",
                        f"L10 ∝ (C/R)³; lower load by reducing fill_pct reduces R", 2),
                ]
                corrections = [
                    _correction("n_rpm", "Reduce shaft speed",
                        n_rpm, float(n_std_L10), "rpm",
                        f"L10 ∝ 1/n → estimated L10 ≈ {L10_target:,}h. "
                        f"Verify capacity ≥ Q_req after change.", 1),
                ]
            else:
                # RPM fix impractical — bearing upgrade is primary correction
                drivers = [
                    _driver("bearing", "Bearing catalogue selection", "current", "—",
                        f"L10 = {L10:,.0f}h << {L10_target:,}h target. "
                        f"Upgrading to C ≥ {C_need_kN:.0f} kN resolves without RPM change", 1),
                    _driver("fill_pct", "Bucket fill", fill_pct, "%",
                        "Lower fill → lower R_head → higher L10 (partial fix)", 2),
                    _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                        f"Reducing to {n_std_L10} rpm would achieve target but is impractical", 3),
                ]
                corrections = [
                    _correction("fill_pct", "Reduce fill to lower headshaft load",
                        fill_pct, max(fill_pct - 10, 40), "%",
                        f"Reduces R_head proportionally; combine with bearing upgrade for full fix", 1),
                ]

            findings.append(_finding(i, msg, sev,
                f"L10 = {L10:,.0f} h < {20000:,} h minimum",
                drivers, corrections,
                f"Bearing L10 = {L10:,.0f} h is below the 20,000 h minimum "
                f"(design target ≥ {L10_target:,} h). "
                + (f"Reduce n_rpm to {n_std_L10} rpm (L10 ∝ 1/n)."
                   if practical else
                   f"RPM reduction to {n_std_L10} rpm is impractical. "
                   f"Primary fix: specify a bearing frame with C ≥ {C_need_kN:.0f} kN "
                   f"for bore {d_mm:.0f}mm (consult SKF/NSK catalogue). "
                   f"Also reduce fill_pct to lower headshaft radial load.")))

        # ─── 9b. Boot Bearing L10 (new this round -- mirrors #9 above,
        # boot side. Confirmed directly: boot_pulley.L10_boot_h is a real
        # computed quantity, only ever produced a warn() in calculations.py
        # with no corresponding root-cause finding until now.) ───────────
        elif "boot bearing" in ml and "l10" in ml:
            L10_boot_target = 20000  # matches the warn() threshold itself, not the stricter 40,000h head target
            n_for_boot = n_rpm * (L10_boot / max(L10_boot_target, 1)) if L10_boot else n_rpm
            n_std_boot = max(int(n_for_boot // 5) * 5, 10)
            practical_boot = n_std_boot >= 35

            if practical_boot:
                drivers = [
                    _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                        f"L10 ∝ 1/n; reduce from {n_rpm} to {n_std_boot} rpm "
                        f"→ boot L10 ≈ {L10_boot_target:,}h (proportional scaling)", 1),
                    _driver("boot_pulley_D_mm", "Boot pulley diameter",
                        _s(inp.get("boot_pulley_D_mm"), 300), "mm",
                        "Increasing boot diameter reduces R_boot for the same duty", 2),
                ]
                corrections = [
                    _correction("n_rpm", "Reduce shaft speed",
                        n_rpm, float(n_std_boot), "rpm",
                        f"L10 ∝ 1/n → estimated boot L10 ≈ {L10_boot_target:,}h. "
                        f"Verify head-side L10 and capacity are still adequate after change.", 1),
                ]
            else:
                drivers = [
                    _driver("bearing", "Boot bearing catalogue selection", "current", "—",
                        f"Boot L10 = {L10_boot:,.0f}h << {L10_boot_target:,}h target. "
                        f"Upgrading the boot bearing frame resolves without RPM change", 1),
                    _driver("boot_pulley_D_mm", "Boot pulley diameter",
                        _s(inp.get("boot_pulley_D_mm"), 300), "mm",
                        "Larger boot diameter lowers R_boot (partial fix)", 2),
                ]
                corrections = [
                    _correction("boot_pulley_D_mm", "Increase boot pulley diameter",
                        _s(inp.get("boot_pulley_D_mm"), 300),
                        _s(inp.get("boot_pulley_D_mm"), 300) + 50, "mm",
                        "Reduces boot bearing radial load; combine with a bearing upgrade for full fix.", 1),
                ]

            findings.append(_finding(i, msg, sev,
                f"Boot L10 = {L10_boot:,.0f} h < {L10_boot_target:,} h minimum",
                drivers, corrections,
                f"Boot shaft bearing L10 = {L10_boot:,.0f} h is below the {L10_boot_target:,} h minimum "
                f"(R_boot = {R_boot:,.0f} N at {n_rpm:.0f} rpm). "
                + (f"Reduce n_rpm to {n_std_boot} rpm (L10 ∝ 1/n)."
                   if practical_boot else
                   f"RPM reduction to {n_std_boot} rpm is impractical -- specify an upgraded "
                   f"boot bearing frame, or increase boot pulley diameter to reduce R_boot.")))

        # ─── 9c. Chain Safety Factor (new this round -- chain elevators
        # had NO root-cause coverage at all before this. Confirmed
        # directly: chain_SF_actual is a real computed quantity, the
        # corresponding fail()/warn() in calculations.py had nothing
        # downstream of it.) ────────────────────────────────────────────
        elif "chain sf" in ml:
            sf_deficit_pct = (chain_sf_req - chain_SF_actual) / max(chain_sf_req, 0.1) * 100
            drivers = [
                _driver("chain_series", "Chain series", chain_sel.get("name", "auto"), "—",
                    f"SF = WL / chain pull; a heavier-rated chain series directly raises SF", 1),
                _driver("chain_n_strands", "Chain strand count",
                    int(_s(inp.get("chain_n_strands"), 1)), "—",
                    "Adding a strand roughly doubles working load capacity (2-strand SC option)", 2),
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    "Lower speed reduces chain pull force proportionally", 3),
            ]
            corrections = [
                _correction("chain_n_strands", "Add a chain strand",
                    int(_s(inp.get("chain_n_strands"), 1)),
                    min(int(_s(inp.get("chain_n_strands"), 1)) + 1, 2), "—",
                    f"SF deficit is {sf_deficit_pct:.0f}% -- an additional strand is the most direct fix "
                    f"if the bucket style/sprocket support multi-strand mounting.", 1),
            ]
            findings.append(_finding(i, msg, sev,
                f"Chain SF = {chain_SF_actual:.2f} < required {chain_sf_req:.1f}",
                drivers, corrections,
                f"Chain safety factor {chain_SF_actual:.2f} is below the required {chain_sf_req:.1f} "
                f"for {chain_sel.get('name', 'the selected chain')}. Upgrade to a heavier chain series, "
                f"add a strand, or reduce chain pull by lowering speed or fill."))

        # ─── 9d. Chain Speed Exceeded (new this round, same reasoning as
        # 9c -- chain_v_ok is real but had no root-cause finding) ────────
        elif "chain speed" in ml and "exceeds" in ml:
            v_max_chain = _s(chain_sel.get("v_max_ms"), 1.0)
            n_for_vmax = n_rpm * (v_max_chain / max(v, 0.01))
            n_std_vmax = max(int(n_for_vmax // 5) * 5, 10)
            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"v ∝ n; reduce to {n_std_vmax} rpm to bring chain speed within "
                    f"{chain_sel.get('name', 'rated')} limit of {v_max_chain:.2f} m/s", 1),
                _driver("chain_series", "Chain series", chain_sel.get("name", "auto"), "—",
                    "A chain series rated for higher speed avoids reducing RPM at all", 2),
            ]
            corrections = [
                _correction("n_rpm", "Reduce shaft speed",
                    n_rpm, float(n_std_vmax), "rpm",
                    f"Brings chain speed to ≈{v_max_chain:.2f} m/s. Verify capacity ≥ Q_req after change.", 1),
            ]
            findings.append(_finding(i, msg, sev,
                f"Chain speed {v:.2f} m/s > rated {v_max_chain:.2f} m/s",
                drivers, corrections,
                f"Chain speed {v:.2f} m/s exceeds {chain_sel.get('name', 'the selected chain')}'s rated "
                f"maximum {v_max_chain:.2f} m/s. Reduce shaft speed or specify a chain series rated for "
                f"higher speed."))

        # ─── 10. Bolt fatigue (Goodman) ───────────────────────────────────────
        elif "bolt" in ml and ("fatigue" in ml or "goodman" in ml):
            goodman = _s(bf.get("goodman_ratio"), 1.1)
            # Goodman ∝ σ_a ∝ F_dynamic ∝ CR (for same bucket mass)
            # Need CR for Goodman = 0.70 (safe)
            target_goodman = 0.70
            cr_target_bf   = cr * (target_goodman / max(goodman, 0.01))
            cr_target_bf   = max(1.10, min(cr_target_bf, 2.5))  # must stay centrifugal
            v_for_bf       = _v_for_cr(cr_target_bf, D_mm)
            n_for_bf       = _rpm_from_v(v_for_bf, D_mm)
            n_std_bf       = round(n_for_bf / 5) * 5

            bolt_dia    = _s(bf.get("bolt_dia_mm"), 12)
            n_bolts     = _s(bf.get("n_bolts"), 2)
            bolt_grade  = bf.get("bolt_grade", "8.8")
            # Upgrading to grade 10.9 raises σ_e → lower Goodman
            new_grade   = "10.9" if "8.8" in str(bolt_grade) else "12.9"

            drivers = [
                _driver("cr", "Centrifugal ratio (CR)", cr, "—",
                    f"F_dynamic = m_bucket × CR × g; Goodman ∝ CR. "
                    f"Target CR = {cr_target_bf:.2f} for Goodman = {target_goodman:.2f}", 1),
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"CR = v²/(g·r), v = π·D·n/60; reducing n_rpm reduces CR and bolt stress", 2),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed", n_rpm, float(n_std_bf)),
                    n_rpm, float(n_std_bf), "rpm",
                    f"Lowers CR from {cr:.3f} to {cr_target_bf:.3f} → estimated Goodman ≈ {target_goodman:.2f}",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"Goodman ratio = {goodman:.3f} > 1.0 (infinite life)",
                drivers, corrections,
                f"Bucket bolt fatigue: Goodman ratio {goodman:.3f} exceeds 1.0 "
                f"(grade {bolt_grade}, {n_bolts:.0f}×M{bolt_dia:.0f} per bucket). "
                f"The dynamic load F = m×CR×g is driven by CR = {cr:.3f}. "
                f"Reducing n_rpm to {n_std_bf} rpm lowers CR to {cr_target_bf:.3f}. "
                f"Alternative: specify grade {new_grade} bolts in the BOM."))

        # ─── 11. Casing clearance (stream strikes wall) ───────────────────────
        elif "casing clearance" in ml or ("stream" in ml and "strikes" in ml):
            wall_x  = _s(cc.get("casing_wall_x_m"), casing_wall_x)
            max_x   = _s(cc.get("max_x_m"), wall_x * 2)   # actual stream extent
            r_pulley = D_mm / 2000.0

            # ── Speed correction ──────────────────────────────────────────────
            # The trajectory max_x (not just the release point x0) must stay
            # inside the casing wall.  max_x ≈ v × t_flight + x0; since the
            # flight time is roughly constant, max_x scales with v.
            # v_safe = v_current × (wall_x / max_x) × 0.95 (5% margin)
            # This correctly gives a LOWER speed when max_x > wall_x.
            if max_x > 0 and max_x > wall_x:
                v_safe = v * (wall_x / max_x) * 0.95
            else:
                v_safe = v * 0.85   # generic 15% reduction if no data
            n_safe = _rpm_from_v(v_safe, D_mm)
            n_std  = max(int(n_safe // 5) * 5, 10)

            # ── Belt/casing width correction ──────────────────────────────────
            # Casing inner wall must be beyond max_x with 50mm clearance.
            # wall_x = BW/2000 + 0.050  →  BW ≥ (max_x + 0.050) × 2000
            BW_need = (max_x + 0.050) * 2000   # mm — use actual stream extent
            BW_std  = _next_std(BW_need, _STD_BW_MM)

            x_release = r_pulley * math.sqrt(max(0, 1.0 - 1.0 / max(cr ** 2, 0.01)))

            drivers = [
                _driver("n_rpm", "Shaft speed", n_rpm, "rpm",
                    f"Stream max extent = {max_x*1000:.0f}mm > casing wall at {wall_x*1000:.0f}mm. "
                    f"Reduce speed so trajectory stays inside casing.", 1),
                _driver("belt_width_override_mm", "Belt / casing width", belt_w, "mm",
                    f"Wider head-section casing moves inner wall to ≥ {max_x*1000:.0f}mm; "
                    f"need BW ≥ {BW_std:.0f}mm", 2),
            ]
            corrections = [
                _correction("n_rpm", _dir_label("shaft speed", n_rpm, float(n_std)),
                    n_rpm, float(n_std), "rpm",
                    f"Scales trajectory from {max_x*1000:.0f}mm to ≈ {wall_x*1000:.0f}mm. "
                    f"Note: if n_std < {_rpm_from_v(_v_for_cr(1.0, D_mm), D_mm):.0f} rpm "
                    f"(CR < 1.0), the elevator switches to gravity discharge — "
                    f"consider widening casing instead.",
                    1),
                _correction("belt_width_override_mm",
                    _dir_label("belt / casing width", belt_w, float(BW_std)),
                    belt_w, float(BW_std), "mm",
                    f"Head-section inner wall at {BW_std/2 + 50:.0f}mm from centreline — "
                    f"clears stream at {max_x*1000:.0f}mm with 50mm margin.",
                    2),
            ]
            findings.append(_finding(i, msg, sev,
                f"Stream max x = {max_x*1000:.0f}mm > casing wall at {wall_x*1000:.0f}mm",
                drivers, corrections,
                f"The discharge stream reaches {max_x*1000:.0f}mm from the pulley centreline "
                f"(release point x0 = {x_release*1000:.0f}mm, then extends further by centrifugal throw). "
                f"The casing inner wall is at {wall_x*1000:.0f}mm (BW = {belt_w:.0f}mm + 50mm clearance). "
                f"Fix 1: widen belt/casing to {BW_std}mm (practical for centrifugal elevators). "
                f"Fix 2: reduce shaft speed to {n_std} rpm "
                f"{'(note: CR < 1.0 — switches to gravity discharge)' if n_std < _rpm_from_v(_v_for_cr(1.0, D_mm), D_mm) else ''}. "))

        # ─── 12. Discharge chute plugging ─────────────────────────────────────
        elif ("chute" in ml or "discharge" in ml) and ("plugging" in ml or "funnel" in ml):
            perf   = dc.get("performance") or {}
            maint  = dc.get("maintenance") or {}
            angle  = _s(perf.get("chute_angle_deg"), 65)
            min_a  = _s(perf.get("min_angle_deg"), 55)
            mass_a = _s(perf.get("mass_flow_angle_deg"), 70)
            # Target must clear BOTH thresholds: min flow angle AND mass-flow angle
            target_angle = max(min_a, mass_a) + 5

            aor = _s(mat.get("angle_repose"), 35)
            drivers = [
                _driver("discharge chute angle", "Back-plate angle", angle, "°",
                    f"Mass-flow requires ≥ {mass_a:.0f}°; currently {angle:.0f}° — "
                    f"steepen by {target_angle - angle:.0f}°", 1),
                _driver("fill_pct", "Bucket fill", fill_pct, "%",
                    "Lower fill reduces material head pressure on chute — less plugging risk", 2),
            ]
            # Chute angle is a fabrication parameter -- but the fabricator
            # needs a number to build to, and the solver needs to evaluate
            # the angle actually being built, not just an auto-derived one.
            # chute_angle_override_deg (models.py) makes this a real,
            # settable input now, not just narrative advice.
            fill_target = max(fill_pct - 10, 40)
            # FIX (Jay: "no input to adjust this"): chute_angle_override_deg
            # now exists (models.py) specifically so this can be a real,
            # applicable correction rather than just narrative text telling
            # the user to go fabricate something different with no way to
            # actually model that choice first. Listed first (priority 1)
            # since it directly addresses the angle the finding is about;
            # fill_pct (priority 2) remains as the secondary lever.
            corrections = [
                _correction("chute_angle_override_deg", "Steepen back-plate angle",
                    angle, float(target_angle), "°",
                    "Directly sets the fabrication angle so the mass-flow check "
                    "evaluates what you actually intend to build, not the "
                    "trajectory-derived default",
                    1),
                _correction("fill_pct", "Reduce fill factor",
                    fill_pct, float(fill_target), "%",
                    "Reduces chute loading and cohesive arch formation risk",
                    2),
            ]
            findings.append(_finding(i, msg, sev,
                f"Chute angle {angle:.0f}° — flow regime at risk (min {min_a:.0f}°, mass-flow {mass_a:.0f}°)",
                drivers, corrections,
                f"Discharge chute back-plate angle {angle:.0f}° is insufficient for mass flow "
                f"(requires {mass_a:.0f}°+). This is driven by the material's angle of repose "
                f"({aor:.0f}°) and cohesion. "
                f"Corrective action is primarily a fabrication change: steepen back-plate to {target_angle:.0f}°. "
                f"Also reduce fill_pct to {fill_target:.0f}% to lower cohesive bridging risk."))

        # ─── 13. Screw take-up buckling ──────────────────────────────────────
        elif "screw" in ml and ("buckling" in ml or "fail" in ml):
            SF_cur   = _s(ts.get("SF_buckling"), 1.0)
            d_min    = _s(ts.get("d_core_min_mm"), 30)
            d_rec    = _s(ts.get("d_core_recommend_mm"), _next_std(d_min, _STD_SCREW_MM))
            F_screw  = _s(ts.get("F_screw_N"), T3 * 2)
            span_m   = _s(ts.get("travel_m"), 0.5) + 0.1

            # Diameter for SF = 3.0:
            # F_euler = π²EI/L² ≥ 3 × F_screw
            # I = π/64 × d^4; F_euler = π³E×d^4 / (64 × L²)
            # d = (3 × F_screw × 64 × L² / (π³ × E))^0.25
            d_sf3 = (3.0 * F_screw * 64.0 * span_m ** 2 / (_PI ** 3 * _E)) ** 0.25 * 1000  # mm
            d_sf3_std = _next_std(d_sf3, _STD_SCREW_MM)

            drivers = [
                _driver("takeup_screw_d_mm", "Screw core diameter", d_min, "mm",
                    f"Required d ≥ {d_sf3:.0f}mm for SF_buckling ≥ 3.0 at span {span_m:.2f}m", 1),
                _driver("takeup_screw_len_m", "Screw span length", span_m, "m",
                    "Shorter effective length (guide support) raises F_euler → better SF", 2),
            ]
            corrections = [
                _correction("takeup_screw_d_mm", "Specify screw core diameter",
                    d_min, float(d_sf3_std), "mm",
                    f"SF_buckling ≥ 3.0 requires d ≥ {d_sf3:.0f}mm. "
                    f"Next standard size {d_sf3_std}mm from TR (ACME/Tr thread series).",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"SF_buckling = {SF_cur:.2f} < 3.0 (d_core = {d_min:.0f}mm, span = {span_m:.2f}m)",
                drivers, corrections,
                f"Screw take-up buckling SF = {SF_cur:.2f} is below the required 3.0. "
                f"The screw core diameter {d_min:.0f}mm is insufficient for the "
                f"Euler column load {F_screw:.0f}N over span {span_m:.2f}m. "
                f"Set takeup_screw_d_mm = {d_sf3_std}mm in Design Overrides."))

        # ─── 13b. Hydraulic take-up buckling ─────────────────────────────────
        # Mirrors rule 13 (screw) — same Euler column-buckling physics, but
        # solved for cylinder BORE rather than core diameter, since the rod
        # diameter is derived as 0.5×bore (hydraulic_takeup()'s ram-cylinder
        # convention) rather than being the diameter under load directly.
        elif "hydraulic" in ml and ("buckling" in ml or "fail" in ml):
            SF_cur     = _s(th.get("SF_buckling"), 1.0)
            bore_min   = _s(th.get("d_bore_min_mm"), 40)
            F_cyl      = _s(th.get("F_cylinder_N"), T3 * 2 / 0.95)
            stroke_m   = _s(th.get("stroke_mm"), 500) / 1000.0

            # Bore for SF = 3.0, with rod_d = 0.5 × bore (see hydraulic_takeup()):
            # F_euler = π²EI_rod/L² ≥ 3 × F_cyl
            # I_rod = π/64 × (0.5×bore)^4 = π×bore^4 / 1024
            # F_euler = π³E×bore^4 / (1024 × L²)
            # bore = (3 × F_cyl × 1024 × L² / (π³ × E))^0.25
            bore_sf3 = (3.0 * F_cyl * 1024.0 * stroke_m ** 2 / (_PI ** 3 * _E)) ** 0.25 * 1000  # mm
            bore_sf3_std = _next_std(bore_sf3, _STD_HYD_MM)

            drivers = [
                _driver("takeup_hydraulic_bore_mm", "Cylinder bore diameter", bore_min, "mm",
                    f"Required bore ≥ {bore_sf3:.0f}mm for SF_buckling ≥ 3.0 at stroke {stroke_m:.2f}m", 1),
                _driver("takeup_hydraulic_pressure_bar", "Operating pressure", _s(th.get("operating_bar"), 100), "bar",
                    "Higher pressure reduces required bore for the same force → smaller, "
                    "stiffer rod at the same buckling margin", 2),
            ]
            corrections = [
                _correction("takeup_hydraulic_bore_mm", "Specify cylinder bore diameter",
                    bore_min, float(bore_sf3_std), "mm",
                    f"SF_buckling ≥ 3.0 requires bore ≥ {bore_sf3:.0f}mm. "
                    f"Next standard hydraulic cylinder bore {bore_sf3_std}mm.",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"SF_buckling = {SF_cur:.2f} < 3.0 (bore = {bore_min:.0f}mm, stroke = {stroke_m:.2f}m)",
                drivers, corrections,
                f"Hydraulic take-up buckling SF = {SF_cur:.2f} is below the required 3.0. "
                f"The cylinder bore {bore_min:.0f}mm gives a rod too slender for the "
                f"Euler column load {F_cyl:.0f}N over stroke {stroke_m:.2f}m. "
                f"Set takeup_hydraulic_bore_mm = {bore_sf3_std}mm in Design Overrides, "
                f"or use a guided/telescopic cylinder to reduce effective rod length."))

        # ─── 14. Casing panel deflection ─────────────────────────────────────
        elif "casing panel" in ml or "panel" in ml and "δ" in ml:
            delta_a  = _s(cp.get("delta_actual_mm"), 10)
            delta_l  = _s(cp.get("delta_allow_mm"), 5)
            t_use    = _s(cp.get("t_use_mm"), 5)
            a_mm     = _s(cp.get("a_mm"), 600)
            # δ ∝ 1/t³ (Timoshenko plate); need t_new³ = t_use³ × δ_actual/δ_allow
            t_need   = t_use * (delta_a / max(delta_l, 0.01)) ** (1.0 / 3.0)
            t_std    = _next_std(t_need, _STD_PLATE_MM)

            # Alt: reduce panel span — δ ∝ a⁴; a_need = a × (δ_allow/δ_actual)^0.25
            a_need   = a_mm * (delta_l / max(delta_a, 0.01)) ** 0.25
            a_need   = math.floor(a_need / 50) * 50  # round to nearest 50mm

            drivers = [
                _driver("casing_t_override_mm", "Casing plate thickness", t_use, "mm",
                    f"δ ∝ 1/t³; need t ≥ {t_need:.1f}mm for δ ≤ L/360", 1),
            ]
            corrections = [
                _correction("casing_t_override_mm", "Specify plate thickness",
                    t_use, float(t_std), "mm",
                    f"Next standard plate above {t_need:.1f}mm. "
                    f"Reduces δ from {delta_a:.1f}mm to ≤{delta_l:.1f}mm (L/360 limit).",
                    1),
            ]
            findings.append(_finding(i, msg, sev,
                f"δ = {delta_a:.1f}mm > L/360 = {delta_l:.1f}mm at {a_mm:.0f}mm panel span",
                drivers, corrections,
                f"Casing panel deflection {delta_a:.1f}mm exceeds the L/360 = {delta_l:.1f}mm "
                f"serviceability limit at {a_mm:.0f}mm stiffener pitch with t = {t_use:.0f}mm plate. "
                f"Plate deflection scales as 1/t³ — increasing from {t_use:.0f}mm to "
                f"{t_std}mm reduces δ by a factor of ({t_std}/{t_use:.0f})³ = "
                f"{(t_std/max(t_use,1))**3:.1f}×. "
                f"Set casing_t_override_mm = {t_std} in Design Overrides."))

    return _detect_conflicts(findings)