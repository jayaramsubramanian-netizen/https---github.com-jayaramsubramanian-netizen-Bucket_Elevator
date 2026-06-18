"""
VECTRIX™ — Structural Stress Engine
CEMA No. 375-2017 §4 & §7, ASME B17.1, ISO 281

v1.1.0 — FBD, Hub, Keyway, Bucket Plate Bending
─────────────────────────────────────────────────────────────────────────────
1. NEW      shaft_reactions() — proper free-body diagram for head shaft.
            Resolves T1, T2 angles + pulley weight + optional drive overhang
            into bearing reactions RA, RB, resultant radial load, and
            bending moment at pulley.  shaft_diameter_governing() and
            shaft_diameter_deflection() now accept its output directly.

2. NEW      hub_diameter() — hub OD and length from keyway bearing stress
            and thick-wall margin.  Replaces the missing hub sizing.

3. NEW      key_stress_check() — ASME B17.1 standard key lookup by shaft
            diameter; shear and bearing stress checks with pass/fail.

4. IMPROVED bucket_thickness() — replaced sqrt(F/(σ·w)) tension-plate
            formula with plate-bending model:
              t = L · sqrt(0.75 · q / σ_allow)
            where q = bucket_back_pressure() [Pa] and L = bolt spacing [m].
            Abrasion wear allowance added by class (0–3 mm).

5. NEW      bucket_back_pressure() — centrifugal + gravity pressure on
            bucket back wall at the head pulley [Pa].

6. NEW      bucket_bolt_shear() — shear stress at bucket mounting bolts
            from centrifugal pull-out load.

7. IMPROVED pulley_shell_thickness() — now returns dict; adds belt-tension
            criterion (hoop pressure) alongside CEMA minimum.

8. NEW      bearing_equivalent_load() — ISO 281 combined radial + axial
            load model P = X·Fr + Y·Fa with shock factor f_d.

─────────────────────────────────────────────────────────────────────────────
Still flagged as out of scope for this revision (tracked for next increment):
  • Pulley end-disc / hub stress (requires pulley face-width + weld data)
  • Head section frame structural model (requires frame geometry)
  • Weld engine (future weld_engine.py)
  • Material flow physics (loading_efficiency, digging_force,
    bucket_fill_factor — will follow in calculations.py / material_flow.py)
─────────────────────────────────────────────────────────────────────────────
"""

import math
import warnings
from typing import Optional


# ── Lazy constant reads (avoid baked-in defaults at class definition time) ────
# This was the original class-level default bug — constants are now read at
# call time so changes to constants.py are reflected immediately.

def _allowable_stress() -> float:
    try:
        from .constants import STEEL_ALLOWABLE_STRESS
    except ImportError:
        from constants import STEEL_ALLOWABLE_STRESS
    return STEEL_ALLOWABLE_STRESS

def _cema_max_slope() -> float:
    try:
        from .constants import CEMA_MAX_SHAFT_SLOPE
    except ImportError:
        from constants import CEMA_MAX_SHAFT_SLOPE
    return CEMA_MAX_SHAFT_SLOPE

def _shaft_E() -> float:
    try:
        from .constants import SHAFT_E_PA
    except ImportError:
        from constants import SHAFT_E_PA
    return SHAFT_E_PA

def _gravity() -> float:
    try:
        from .constants import GRAVITY
    except ImportError:
        from constants import GRAVITY
    return GRAVITY


# ── ASME B17.1 Standard Key Dimensions (shaft diameter → b × h) [mm] ─────────
# Source: ASME B17.1-1967 (R2013) Table 1.  Paired key width b and height h.
# Lookup by: find the smallest d_max that is ≥ shaft diameter.

_B17_KEYS: list[tuple[float, float, float]] = [
    # (d_max_mm, b_mm, h_mm)
    (6,   2,  2),  (8,   3,  3),  (10,  3,  3),  (12,  4,  4),
    (14,  4,  4),  (17,  5,  5),  (19,  5,  5),  (22,  6,  6),
    (25,  6,  6),  (28,  7,  7),  (30,  8,  7),  (35,  8,  7),
    (38,  10, 8),  (44,  10, 8),  (50,  14, 9),  (58,  16, 10),
    (65,  16, 10), (75,  18, 11), (85,  20, 12), (95,  22, 14),
    (110, 25, 14), (130, 28, 16), (150, 32, 18), (170, 36, 20),
    (200, 40, 22), (230, 45, 25), (260, 50, 28), (290, 56, 32),
]

def _b17_key(d_shaft_mm: float) -> tuple[float, float]:
    """Return (b, h) in mm for the ASME B17.1 key matching shaft diameter d."""
    for d_max, b, h in _B17_KEYS:
        if d_shaft_mm <= d_max:
            return b, h
    # Larger than table maximum: extend linearly
    return _B17_KEYS[-1][1], _B17_KEYS[-1][2]


class StructuralStressEngine:

    # ── 1. Shaft — Free Body Diagram ──────────────────────────────────────────

    @staticmethod
    def shaft_reactions(
        T1:            float,
        T2:            float,
        angle_T1_deg:  float = 45.0,
        angle_T2_deg:  float = 135.0,
        W_pulley_N:    float = 0.0,
        a_pulley_m:    float = 0.200,
        span_m:        float = 0.400,
        W_drive_N:     float = 0.0,
        a_drive_m:     Optional[float] = None,
    ) -> dict:
        """
        Free-body diagram — CEMA 375 §4 head shaft analysis.

        Replaces the single-load approximation in v1.0 shaft_diameter_deflection().
        The head shaft carries:
          • Belt tension T1 (tight side) at angle_T1_deg from horizontal
          • Belt tension T2 (slack/return side) at angle_T2_deg from horizontal
          • Pulley dead weight W_pulley_N (downward, at pulley centre)
          • Optional drive sprocket or coupling weight W_drive_N
            (downward, at a_drive_m from bearing A — for cantilever drive)

        All belt tension angles measured from horizontal; positive = upward.
        Bearing A is at x = 0; Bearing B is at x = span_m.
        Pulley centre is at x = a_pulley_m from A.

        Model: simply-supported beam, loads at single axial position.
        For the general multi-position model, call with multiple (F, x) pairs
        summed externally (superposition) and combine moments.

        Parameters
        ----------
        T1, T2          Belt tensions [N]
        angle_T1_deg    Tight-side tension angle from horizontal [°]
        angle_T2_deg    Return-side tension angle from horizontal [°].
                        For typical tight-side below, return-side above:
                          angle_T1 = −45°, angle_T2 = +135°
        W_pulley_N      Pulley dead weight [N] (acts downward at a_pulley_m)
        a_pulley_m      Pulley centre position from bearing A [m]
        span_m          Bearing A to B span [m]
        W_drive_N       Drive sprocket weight at a_drive_m [N] (cantilever)
        a_drive_m       Drive load position from A [m].  If None, ignored.

        Returns
        -------
        {
            "F_resultant_N":  float   Net radial load at pulley [N]
            "RA_N":           float   Bearing A reaction [N]
            "RB_N":           float   Bearing B reaction [N]
            "M_pulley_Nm":    float   Bending moment at pulley centre [N·m]
            "M_drive_Nm":     float   Bending moment at drive position [N·m]
            "M_max_Nm":       float   Maximum bending moment along shaft [N·m]
            "Fx_N":           float   Horizontal resultant at pulley [N]
            "Fy_N":           float   Vertical resultant at pulley [N]
        }
        """
        a1 = math.radians(angle_T1_deg)
        a2 = math.radians(angle_T2_deg)

        # Belt forces at pulley + pulley dead weight → resultant vertical/horizontal
        Fx = T1 * math.cos(a1) + T2 * math.cos(a2)
        Fy = T1 * math.sin(a1) + T2 * math.sin(a2) - W_pulley_N
        F_res = math.sqrt(Fx ** 2 + Fy ** 2)

        # Simply-supported: take moments about A
        b_pul = span_m - a_pulley_m
        sum_moment_A = F_res * a_pulley_m

        if W_drive_N > 0 and a_drive_m is not None:
            sum_moment_A += W_drive_N * a_drive_m

        RB = sum_moment_A / max(span_m, 0.001)
        RA = F_res + (W_drive_N if a_drive_m is not None else 0.0) - RB

        # Bending moments (simply-supported, single transverse load at each position)
        M_pul   = RA * a_pulley_m
        M_drive = RA * a_drive_m - F_res * max(0.0, a_drive_m - a_pulley_m) \
            if (a_drive_m is not None and W_drive_N > 0) else 0.0
        M_max   = max(abs(M_pul), abs(M_drive))

        return {
            "F_resultant_N": round(F_res,   1),
            "RA_N":          round(RA,      1),
            "RB_N":          round(RB,      1),
            "M_pulley_Nm":   round(M_pul,   2),
            "M_drive_Nm":    round(M_drive, 2),
            "M_max_Nm":      round(M_max,   2),
            "Fx_N":          round(Fx,      1),
            "Fy_N":          round(Fy,      1),
        }

    # ── 2. Shaft — Diameter Selection ─────────────────────────────────────────

    @staticmethod
    def equivalent_torque(
        moment:  float,
        torque:  float,
        kb:      float = 1.5,
        kt:      float = 1.0,
    ) -> float:
        """
        ASME B17.1 / CEMA 375 §4 — Combined equivalent torque [N·m].
        Te = √((kb·M)² + (kt·T)²)
        kb = 1.5  fatigue concentration at keyway (ASME B17.1)
        kt = 1.0  torsional concentration (no-shock default)
        Unchanged from v1.0.
        """
        return math.sqrt((kb * moment) ** 2 + (kt * torque) ** 2)

    @staticmethod
    def shaft_diameter(
        moment:    float,
        torque:    float,
        allowable: Optional[float] = None,
    ) -> float:
        """
        CEMA 375 §4 — Minimum shaft diameter from torsional stress [m].
        d = (16·Te / (π·τ_allow))^(1/3)
        Reads allowable from constants at call time (v1.0 baked-in-default fix).
        """
        tau = allowable if allowable is not None else _allowable_stress()
        Te  = StructuralStressEngine.equivalent_torque(moment, torque)
        return ((16.0 * Te) / (math.pi * tau)) ** (1.0 / 3.0)

    @staticmethod
    def shaft_diameter_deflection(
        radial_load_N: float,
        overhang_A_m:  float = 0.080,
        span_B_m:      float = 0.400,
    ) -> float:
        """
        CEMA 375 §4 / CEMA Pulley Standard — Minimum shaft diameter from
        deflection limit [m].

        Max allowable slope at pulley bushing: α_max = 0.0015 rad (CEMA §4).
        Simply-supported beam with point load at pulley centre:
          α = R·A·(B² − A²) / (6·E·I·B)
        Solving for d:
          d = [64·R·A·(B² − A²) / (6·E·B·α_max·π)]^(1/4)

        RECOMMENDED: pass radial_load_N from shaft_reactions()["F_resultant_N"]
        rather than calculating independently, to ensure the same loading
        assumptions drive both criteria in shaft_diameter_governing().

        Parameters
        ----------
        radial_load_N  Total radial load at pulley [N]
        overhang_A_m   Pulley centre to bearing A [m]
        span_B_m       Bearing A to B span [m]
        """
        E         = _shaft_E()
        alpha_max = _cema_max_slope()
        R = max(radial_load_N, 1.0)
        A = max(overhang_A_m, 0.001)
        B = max(span_B_m, 0.001)
        numer = 64.0 * R * A * (B ** 2 - A ** 2)
        denom = 6.0 * E * B * alpha_max * math.pi
        return (numer / denom) ** 0.25

    @staticmethod
    def shaft_diameter_governing(
        moment:         float,
        torque:         float,
        radial_load_N:  float,
        overhang_A_m:   float = 0.080,
        span_B_m:       float = 0.400,
        allowable:      Optional[float] = None,
    ) -> dict:
        """
        CEMA 375 §4 — Governing shaft diameter: larger of stress or deflection.

        RECOMMENDED WORKFLOW:
            fbd    = StructuralStressEngine.shaft_reactions(T1, T2, ...)
            result = StructuralStressEngine.shaft_diameter_governing(
                         moment       = fbd["M_max_Nm"],
                         torque       = drive_torque,
                         radial_load_N = fbd["F_resultant_N"],
                     )

        Returns both criteria, governing value, and mm equivalents.
        """
        d_s = StructuralStressEngine.shaft_diameter(moment, torque, allowable)
        d_d = StructuralStressEngine.shaft_diameter_deflection(
            radial_load_N, overhang_A_m, span_B_m
        )
        d_g = max(d_s, d_d)

        return {
            "d_stress_m":     round(d_s,  5),
            "d_deflect_m":    round(d_d,  5),
            "d_governing_m":  round(d_g,  5),
            "d_stress_mm":    round(d_s  * 1000, 1),
            "d_deflect_mm":   round(d_d  * 1000, 1),
            "d_governing_mm": round(d_g  * 1000, 1),
            "governed_by":    "stress" if d_s >= d_d else "deflection (CEMA 0.0015 rad)",
        }

    @staticmethod
    def shaft_diameter_governing_hollow(
        moment:         float,
        torque:         float,
        radial_load_N:  float,
        bore_ratio:     float = 0.0,
        overhang_A_m:   float = 0.080,
        span_B_m:       float = 0.400,
        allowable:      Optional[float] = None,
    ) -> dict:
        """
        v1.9.8 — Hollow-shaft equivalent of shaft_diameter_governing().

        bore_ratio = 0 reduces exactly to the solid-shaft case (delegates to
        shaft_diameter_governing() directly) — this lets the same call site
        handle both configurations with one parameter.

        For a hollow section with bore ratio k = d_i / d_o, both governing
        formulas substitute the hollow section/polar modulus for the solid
        one. Because the (1 - k^4) term is a constant once k is fixed, both
        closed-form solves extend cleanly — no iteration required:

        Stress (torsion + bending combined, ASME-style):
            Z_hollow = (pi/16) * d_o^3 * (1 - k^4)     [vs pi/16 * d^3 solid]
            d_o = ( 16*Te / (pi * tau_allow * (1-k^4)) )^(1/3)

        Deflection (CEMA max bushing slope):
            I_hollow = (pi/64) * d_o^4 * (1 - k^4)     [vs pi/64 * d^4 solid]
            d_o = [ 64*R*A*(B^2-A^2) / (6*E*B*alpha_max*pi*(1-k^4)) ]^(1/4)

        A hollow shaft of the same OD as an equivalent solid shaft is always
        WEAKER (less material), so for a given load the solver must report a
        LARGER outer diameter than the solid case — this is the expected and
        correct trade a designer makes for weight reduction, not a deficiency.

        Parameters
        ----------
        bore_ratio   d_i/d_o, 0 = solid (no hollow penalty), typical hollow
                     shaft range 0.4-0.7. CEMA does not publish a standard
                     bore ratio for bucket elevator head shafts — this is an
                     OEM/customer-specified design choice, not a code value.

        Returns
        -------
        Same keys as shaft_diameter_governing(), plus:
            "bore_ratio":   float
            "d_inner_mm":   float,  implied bore diameter at the governing OD
            "mass_saving_pct": float, approx cross-sectional area reduction
                                vs an equivalent solid shaft at the same OD
        """
        k = max(0.0, min(bore_ratio, 0.85))   # cap at 0.85 — thin-wall practicality limit
        if k <= 0.001:
            # Degenerates to the solid case — delegate directly, no hollow penalty.
            solid = StructuralStressEngine.shaft_diameter_governing(
                moment, torque, radial_load_N, overhang_A_m, span_B_m, allowable
            )
            solid["bore_ratio"]      = 0.0
            solid["d_inner_mm"]      = 0.0
            solid["mass_saving_pct"] = 0.0
            return solid

        hollow_factor = 1.0 - k ** 4

        tau = allowable if allowable is not None else _allowable_stress()
        Te  = StructuralStressEngine.equivalent_torque(moment, torque)
        d_s = ((16.0 * Te) / (math.pi * tau * hollow_factor)) ** (1.0 / 3.0)

        E         = _shaft_E()
        alpha_max = _cema_max_slope()
        R = max(radial_load_N, 1.0)
        A = max(overhang_A_m, 0.001)
        B = max(span_B_m, 0.001)
        numer = 64.0 * R * A * (B ** 2 - A ** 2)
        denom = 6.0 * E * B * alpha_max * math.pi * hollow_factor
        d_d = (numer / denom) ** 0.25

        d_g = max(d_s, d_d)
        d_i_mm = d_g * k * 1000.0

        # Cross-sectional area reduction vs an equivalent SOLID shaft at the
        # same outer diameter d_g (illustrates the weight-saving trade-off,
        # not a comparison against the solid-required diameter from above).
        mass_saving_pct = k ** 2 * 100.0

        return {
            "d_stress_m":     round(d_s,  5),
            "d_deflect_m":    round(d_d,  5),
            "d_governing_m":  round(d_g,  5),
            "d_stress_mm":    round(d_s  * 1000, 1),
            "d_deflect_mm":   round(d_d  * 1000, 1),
            "d_governing_mm": round(d_g  * 1000, 1),
            "governed_by":    "stress" if d_s >= d_d else "deflection (CEMA 0.0015 rad)",
            "bore_ratio":      round(k, 3),
            "d_inner_mm":      round(d_i_mm, 1),
            "mass_saving_pct": round(mass_saving_pct, 1),
        }

    # ── 3. Shaft — Hub and Keyway ─────────────────────────────────────────────

    @staticmethod
    def hub_diameter(
        shaft_diameter_m:      float,
        torque_Nm:             float,
        key_length_m:          Optional[float] = None,
        sigma_bearing_pa:      float = 115e6,
        min_wall_mm:           float = 6.0,
    ) -> dict:
        """
        Hub outer diameter and length — AGMA 9002 / ASME B17.1 approach.

        Hub OD from two criteria:
          1. Keyway wall clearance:
             d_hub ≥ d_shaft + 2·h_key + 2·min_wall
          2. Thick-wall ratio minimum (industry practice):
             d_hub ≥ 1.5 × d_shaft

        Hub length from bearing stress on key:
          σ_bearing = 4T / (d · h_key · L_hub)
          L_hub = 4T / (d · h_key · σ_bearing_allow)
          Minimum: 1.25 × d_shaft (AGMA 9002 minimum engagement)

        Parameters
        ----------
        shaft_diameter_m     Governing shaft diameter from shaft_diameter_governing()
        torque_Nm            Drive torque at shaft
        key_length_m         If None, hub length is derived from bearing stress.
                             If provided, L_hub = max(key_length, stress_requirement).
        sigma_bearing_pa     Allowable bearing stress on key face [Pa].
                             115 MPa for Class 1 steel key in steel shaft (AGMA).
        min_wall_mm          Minimum hub wall thickness beyond keyway [mm].

        Returns
        -------
        {
            "d_hub_mm":   float   Hub outer diameter [mm]
            "L_hub_mm":   float   Hub length [mm]
            "b_key_mm":   float   Key width (ASME B17.1) [mm]
            "h_key_mm":   float   Key height (ASME B17.1) [mm]
            "d_hub_m":    float   Hub outer diameter [m]
            "L_hub_m":    float   Hub length [m]
        }
        """
        d    = shaft_diameter_m
        d_mm = d * 1000.0
        b_mm, h_mm = _b17_key(d_mm)

        # Hub OD
        d_hub_wall = d_mm + 2.0 * h_mm + 2.0 * min_wall_mm
        d_hub_ratio = 1.5 * d_mm
        d_hub_mm = max(d_hub_wall, d_hub_ratio)

        # Hub length from bearing stress
        L_stress = 4.0 * torque_Nm / (d * (h_mm / 1000.0) * sigma_bearing_pa)
        L_min    = 1.25 * d
        L_hub_m  = max(L_stress, L_min)

        if key_length_m is not None:
            L_hub_m = max(L_hub_m, key_length_m)

        return {
            "d_hub_mm": round(d_hub_mm,          1),
            "L_hub_mm": round(L_hub_m  * 1000.0, 1),
            "b_key_mm": b_mm,
            "h_key_mm": h_mm,
            "d_hub_m":  round(d_hub_mm / 1000.0, 5),
            "L_hub_m":  round(L_hub_m,            5),
        }

    @staticmethod
    def key_stress_check(
        shaft_diameter_m:  float,
        torque_Nm:         float,
        key_length_m:      float,
        tau_allow_pa:      float = 100e6,
        sigma_allow_pa:    float = 215e6,
    ) -> dict:
        """
        ASME B17.1 — Key shear and bearing stress check.

        Key dimensions looked up from ASME B17.1 Table 1 by shaft diameter.
        Shear:   τ = 2·T / (d · b · L)    ≤ τ_allow  (key shear on midplane)
        Bearing: σ = 4·T / (d · h · L)    ≤ σ_allow  (key bearing on shaft/hub)

        Default allowables (AGMA 9002 Class I, heat-treated steel key):
          τ_allow  = 100 MPa shear
          σ_allow  = 215 MPa bearing

        Parameters
        ----------
        shaft_diameter_m  Shaft diameter [m]
        torque_Nm         Transmitted torque [N·m]
        key_length_m      Key engagement length [m] (hub length or actual key L)
        tau_allow_pa      Allowable shear stress [Pa]
        sigma_allow_pa    Allowable bearing stress [Pa]

        Returns
        -------
        {
            "b_key_mm":        float
            "h_key_mm":        float
            "tau_actual_MPa":  float
            "tau_allow_MPa":   float
            "sigma_actual_MPa":float
            "sigma_allow_MPa": float
            "shear_pass":      bool
            "bearing_pass":    bool
            "pass":            bool   True if both checks pass
            "recommendation":  str
        }
        """
        d_mm     = shaft_diameter_m * 1000.0
        b_mm, h_mm = _b17_key(d_mm)
        b = b_mm / 1000.0
        h = h_mm / 1000.0
        d = shaft_diameter_m
        L = max(key_length_m, 0.001)

        tau   = 2.0 * torque_Nm / (d * b * L)
        sigma = 4.0 * torque_Nm / (d * h * L)

        sh_pass = tau   <= tau_allow_pa
        br_pass = sigma <= sigma_allow_pa
        ok      = sh_pass and br_pass

        if not ok:
            parts = []
            if not sh_pass:
                parts.append(f"shear {tau/1e6:.1f} MPa > limit {tau_allow_pa/1e6:.0f} MPa")
            if not br_pass:
                parts.append(f"bearing {sigma/1e6:.1f} MPa > limit {sigma_allow_pa/1e6:.0f} MPa")
            rec = "FAIL — " + "; ".join(parts) + ". Increase key length or upgrade to splined shaft."
        else:
            rec = f"PASS — shear {tau/1e6:.1f} MPa, bearing {sigma/1e6:.1f} MPa within limits."

        return {
            "b_key_mm":         b_mm,
            "h_key_mm":         h_mm,
            "tau_actual_MPa":   round(tau   / 1e6, 2),
            "tau_allow_MPa":    round(tau_allow_pa  / 1e6, 1),
            "sigma_actual_MPa": round(sigma / 1e6, 2),
            "sigma_allow_MPa":  round(sigma_allow_pa / 1e6, 1),
            "shear_pass":       sh_pass,
            "bearing_pass":     br_pass,
            "pass":             ok,
            "recommendation":   rec,
        }

    @staticmethod
    def weld_throat_sizing(
        shaft_diameter_m:  float,
        torque_Nm:         float,
        radial_load_N:     float = 0.0,
        weld_allow_pa:     float = 96e6,
    ) -> dict:
        """
        v1.9.8 — Welded-hub alternative to key_stress_check().

        Bucket elevator head shafts are conventionally keyed (the default
        path, see key_stress_check()). A welded hub is an alternative used
        when the shop prefers all-welded fabrication over keyway machining,
        or for low-torque/light-duty designs where a keyway stress
        concentration is undesirable relative to shaft diameter.

        Models a circumferential fillet weld around the shaft OD, sized for
        torsion (primary load) with radial/bending load as a secondary
        check using the standard weld throat shear-stress approach:

            Polar section modulus of a thin circumferential fillet weld,
            throat thickness t, mean radius r = d/2:
                J_weld  = 2 * pi * r^3 * t      (thin-ring approximation)
                tau_T   = T * r / J_weld = T / (2 * pi * r^2 * t)

            Solving for required throat thickness:
                t_req = T / (2 * pi * r^2 * tau_allow)

        Radial load is checked as a secondary shear-on-throat-area check
        (conservative — does not combine vectorially with torsional shear,
        since the controlling location around the weld differs for each):
                tau_R = radial_load_N / (2 * pi * r * t)

        Default weld_allow_pa = 96 MPa corresponds to E70xx electrode fillet
        weld allowable shear (AWS D1.1, 0.3 x 70ksi UTS, converted to SI).
        This is independent of the shaft material grade — weld metal
        strength governs, not parent metal — so this allowable does NOT
        change with shaft_material selection the way key_stress_check()'s
        tau_allow_key_Pa does.

        Parameters
        ----------
        shaft_diameter_m  Shaft OD at the weld location [m]
        torque_Nm         Transmitted torque [N.m]
        radial_load_N     Radial load at the hub for the secondary check [N]
        weld_allow_pa     Allowable weld shear stress [Pa], E70xx default

        Returns
        -------
        {
            "t_throat_torsion_mm": float,  required throat from torsion alone
            "t_throat_radial_mm":  float,  required throat from radial shear alone
            "t_throat_mm":         float,  governing (larger of the two)
            "governed_by":         "torsion" | "radial_shear"
            "tau_torsion_MPa":     float,  actual stress at t_throat_mm
            "weld_allow_MPa":      float,
            "recommendation":      str
        }
        """
        r = max(shaft_diameter_m / 2.0, 0.005)
        T = max(torque_Nm, 0.0)
        R = max(radial_load_N, 0.0)

        t_torsion = T / (2.0 * math.pi * r ** 2 * weld_allow_pa) if T > 0 else 0.0
        t_radial  = R / (2.0 * math.pi * r * weld_allow_pa) if R > 0 else 0.0

        if t_torsion >= t_radial:
            t_gov = t_torsion
            gov_by = "torsion"
        else:
            t_gov = t_radial
            gov_by = "radial_shear"

        # Practical minimum: a fillet weld throat below ~4mm is rarely
        # specified on shafts of this size range (fabrication practicality,
        # not a stress requirement) — floor the recommendation accordingly.
        t_gov_practical = max(t_gov, 0.004)

        tau_check = T / (2.0 * math.pi * r ** 2 * max(t_gov_practical, 1e-6))

        return {
            "t_throat_torsion_mm": round(t_torsion * 1000.0, 2),
            "t_throat_radial_mm":  round(t_radial * 1000.0, 2),
            "t_throat_mm":         round(t_gov_practical * 1000.0, 2),
            "governed_by":         gov_by,
            "tau_torsion_MPa":     round(tau_check / 1e6, 2),
            "weld_allow_MPa":      round(weld_allow_pa / 1e6, 1),
            "recommendation": (
                f"Specify {round(t_gov_practical*1000.0,1)}mm fillet throat, "
                f"E70xx or equivalent, full 360° around shaft OD. "
                f"Governed by {gov_by.replace('_',' ')}."
            ),
        }

    @staticmethod
    def head_shaft_critical_speed(
        shaft_diameter_m: float,
        span_m:           float,
        overhang_load_N:  float = 0.0,
        overhang_arm_m:   float = 0.0,
        E_pa:             float = 205e9,
        rho_steel_kgm3:   float = 7850.0,
    ) -> dict:
        """
        First lateral (whirling) critical speed of the head shaft, modelled as a
        simply-supported uniform beam with an optional overhung point mass
        (pulley + belt load reaction acting between the bearings is already
        captured by the supported-beam term; the overhang term covers any load
        acting outside the bearing span, e.g. a coupling or outboard sprocket).

        Two contributions combined by Dunkerley's method (conservative, no
        cross-coupling assumed — adequate for a preliminary check):

        1. Self-weight of the shaft (uniform simply-supported beam):
               n_c1 = (pi/2) * sqrt(E*I*g / (w*L^4)) * 60/(2*pi)   [rpm]
           using the standard first-mode result for a u.d.l. simply-supported
           beam, n_c1 [rad/s] = pi^2 * sqrt(E*I/(w*L^4)) ; w = mass per length.

        2. Point load deflection at midspan (Rayleigh estimate) if an overhang
           load is supplied:
               delta = F*L^3 / (48*E*I)   (midspan point load, simply supported)
               n_c2  = sqrt(g/delta) * 60/(2*pi)   [rpm]

        Dunkerley:  1/n_c^2 = 1/n_c1^2 + 1/n_c2^2

        This is a preliminary screening calculation, not a full rotor-dynamics
        analysis. It ignores bearing stiffness, gyroscopic effects, and coupled
        torsional-lateral modes. Use to flag designs that warrant a full rotor
        dynamics study, not as a final acceptance criterion.

        Parameters
        ----------
        shaft_diameter_m   Governing shaft diameter [m]
        span_m             Bearing-to-bearing span [m]
        overhang_load_N    Point load between bearings to include in Rayleigh
                            term (0 = self-weight only)
        overhang_arm_m     Unused placeholder for future outboard-load term
        E_pa               Young's modulus, steel default 205 GPa
        rho_steel_kgm3     Shaft material density, steel default 7850 kg/m3

        Returns
        -------
        {
            "n_critical_rpm":   float,
            "n_critical_self_rpm":   float,  self-weight-only mode
            "n_critical_point_rpm":  float | None,  point-load mode (if load > 0)
            "operating_ratio":  float,   n_operating / n_critical
            "status":           "ok" | "warn" | "fail"
            "note":             str
        }
        """
        import math as _m
        d  = max(shaft_diameter_m, 0.001)
        L  = max(span_m, 0.01)
        I  = _m.pi * d**4 / 64.0                       # second moment of area [m^4]
        A  = _m.pi * d**2 / 4.0                          # cross-section area [m^2]
        w  = rho_steel_kgm3 * A                           # mass per unit length [kg/m]
        g  = 9.81

        # Mode 1 — self-weight, simply-supported uniform beam, first mode
        # omega_1 = pi^2 * sqrt(E*I / (w*L^4))   [rad/s]
        omega_self = _m.pi**2 * _m.sqrt((E_pa * I) / (w * L**4))
        n_self_rpm = omega_self * 60.0 / (2.0 * _m.pi)

        # Mode 2 — point load at midspan (Rayleigh), only if a load is given
        n_point_rpm = None
        if overhang_load_N > 0:
            delta = overhang_load_N * L**3 / (48.0 * E_pa * I)   # [m]
            if delta > 0:
                omega_point = _m.sqrt(g / delta)
                n_point_rpm = omega_point * 60.0 / (2.0 * _m.pi)

        # Dunkerley combination (conservative — combined frequency is always
        # lower than either individual mode)
        if n_point_rpm:
            n_crit_rpm = 1.0 / _m.sqrt((1.0/n_self_rpm)**2 + (1.0/n_point_rpm)**2)
        else:
            n_crit_rpm = n_self_rpm

        return {
            "n_critical_rpm":       round(n_crit_rpm, 0),
            "n_critical_self_rpm":  round(n_self_rpm, 0),
            "n_critical_point_rpm": round(n_point_rpm, 0) if n_point_rpm else None,
            "shaft_diameter_mm":    round(d * 1000.0, 1),
            "span_mm":              round(L * 1000.0, 0),
            "note": (
                "Preliminary Dunkerley/Rayleigh estimate — simply-supported "
                "uniform shaft, no bearing stiffness or gyroscopic effects. "
                "Verify with full rotor-dynamics analysis for n_operating > "
                "0.6 x n_critical or any high-speed (> 150 rpm) application."
            ),
        }

    # ── 4. Buckets ────────────────────────────────────────────────────────────

    @staticmethod
    def bucket_back_pressure(
        belt_speed_mps:      float,
        head_radius_m:       float,
        fill_ratio:          float = 0.75,
        bucket_projection_m: float = 0.14,
        bulk_density_kgm3:   float = 1000.0,
    ) -> float:
        """
        Pressure on bucket back wall at head pulley [Pa].

        At the point of maximum centrifugal loading (near top of head pulley),
        the material inside the bucket presses against the back wall with both
        centrifugal and gravity contributions:

            q = ρ · h_fill · (v² / r + g)

        where h_fill = fill_ratio × bucket_projection (effective material depth).

        This pressure is the load input to bucket_thickness() plate bending model.

        Parameters
        ----------
        belt_speed_mps      Belt speed [m/s]
        head_radius_m       Head pulley radius [m]
        fill_ratio          Fraction of bucket projection occupied by material
        bucket_projection_m Radial depth of bucket from belt to lip [m]
        bulk_density_kgm3   Material bulk density [kg/m³]
        """
        h_fill    = fill_ratio * bucket_projection_m
        a_centri  = (belt_speed_mps ** 2) / max(head_radius_m, 0.001)
        return bulk_density_kgm3 * h_fill * (a_centri + _gravity())

    @staticmethod
    def bucket_thickness(
        belt_speed_mps:      float,
        head_radius_m:       float,
        bucket_width_mm:     float = 200.0,
        bolt_spacing_mm:     float = 100.0,
        fill_ratio:          float = 0.75,
        bucket_projection_m: float = 0.14,
        bulk_density_kgm3:   float = 1000.0,
        abrasion_class:      int   = 1,
        allowable_stress_pa: float = 140e6,
    ) -> dict:
        """
        CEMA 375 §7 — Bucket back-plate thickness [mm].

        PHYSICAL MODEL (plate bending, not tension plate)
        ──────────────────────────────────────────────────
        v1.0 used  t = sqrt(F / (σ · w)) — a uniaxial tension formula.
        A bucket back wall is a simply-supported plate loaded by uniform
        pressure; the correct model is plate bending:

            t = L · sqrt(0.75 · q / σ_allow)

        where:
          q = bucket_back_pressure()          [Pa]
          L = bolt_spacing_mm / 1000          [m]  ← unsupported plate span
          0.75 = strip plate bending coefficient (M = qL²/8, σ = 6M/t²)

        The critical unsupported span is the bolt spacing, not the bucket
        width.  Bucket width enters only through the pressure calculation
        (fill_ratio × projection assumptions are unchanged).

        Abrasion wear allowance added to calculated structural minimum:
          Class 1 (light — grain, flour):       +0 mm
          Class 2 (moderate — coal, sand):      +1 mm
          Class 3 (heavy — gravel, clinker):    +2 mm
          Class 4 (very heavy — ore, limestone):+3 mm

        CEMA 375 §7 hard minimums: 3 mm light, 5 mm heavy.  Enforced last.

        Parameters
        ----------
        bolt_spacing_mm  Centre-to-centre bolt pitch along bucket width [mm].
                         This is the unsupported span of the plate between
                         fastener rows.  Typical: 80–120 mm.
        abrasion_class   1–4 per CEMA 375 material abrasion classification.

        Returns
        -------
        {
            "q_Pa":              float   Pressure on back wall [Pa]
            "t_structural_mm":   float   Calculated plate-bending thickness [mm]
            "t_abrasion_mm":     float   Wear allowance added [mm]
            "t_total_mm":        float   Structural + wear [mm]
            "t_governing_mm":    float   Final after CEMA §7 minimum [mm]
            "governed_by":       str
        }
        """
        if abrasion_class not in (1, 2, 3, 4):
            abrasion_class = max(1, min(4, abrasion_class))
        wear_mm = [0, 0, 1, 2, 3][abrasion_class]    # index 0 unused

        q   = StructuralStressEngine.bucket_back_pressure(
            belt_speed_mps, head_radius_m,
            fill_ratio, bucket_projection_m, bulk_density_kgm3,
        )
        L   = max(bolt_spacing_mm, 20.0) / 1000.0    # [m] plate span
        t_m = L * math.sqrt(0.75 * q / max(allowable_stress_pa, 1.0))
        t_structural = t_m * 1000.0                   # → mm
        t_total      = t_structural + wear_mm

        # CEMA 375 §7 minimum thickness
        if bulk_density_kgm3 < 800 and bucket_width_mm <= 200:
            t_cema_min = 3.0
        elif bulk_density_kgm3 >= 1500 or bucket_width_mm > 350:
            t_cema_min = 5.0
        else:
            t_cema_min = 4.0

        t_governing = max(t_total, t_cema_min)
        governed_by = (
            "CEMA_minimum" if t_cema_min > t_total else
            f"plate_bending + abrasion_class_{abrasion_class}"
        )

        return {
            "q_Pa":             round(q,            1),
            "t_structural_mm":  round(t_structural, 2),
            "t_abrasion_mm":    float(wear_mm),
            "t_total_mm":       round(t_total,      2),
            "t_governing_mm":   round(t_governing,  1),
            "governed_by":      governed_by,
        }

    @staticmethod
    def bucket_bolt_shear(
        belt_speed_mps:      float,
        head_radius_m:       float,
        bucket_mass_kg:      float,
        fill_mass_kg:        float,
        n_bolts:             int   = 2,
        bolt_diameter_mm:    float = 12.0,
        allowable_shear_pa:  float = 80e6,
    ) -> dict:
        """
        Bucket mounting bolt shear check — centrifugal pull-out load [N].

        At the head pulley, the combined centrifugal force on bucket + material
        must be resisted by the mounting bolts in shear.

        F_centrifugal = (m_bucket + m_fill) × v² / r

        Bolt shear area (single shear per bolt):
          A_bolt = π/4 × d²

        τ = F_centrifugal / (n_bolts × A_bolt)

        Parameters
        ----------
        bucket_mass_kg   Actual bucket mass from catalogue [kg]
        fill_mass_kg     Material mass in fully loaded bucket [kg]
        n_bolts          Number of mounting bolts (per bucket)
        bolt_diameter_mm Bolt shank diameter (not thread minor) [mm]
        """
        F_centri = (bucket_mass_kg + fill_mass_kg) * (belt_speed_mps ** 2) / max(head_radius_m, 0.001)
        A_bolt   = math.pi / 4.0 * (bolt_diameter_mm / 1000.0) ** 2
        tau      = F_centri / max(n_bolts * A_bolt, 1e-8)
        ok       = tau <= allowable_shear_pa

        return {
            "F_centrifugal_N":    round(F_centri, 1),
            "tau_MPa":            round(tau / 1e6, 2),
            "tau_allow_MPa":      round(allowable_shear_pa / 1e6, 1),
            "pass":               ok,
            "recommendation": (
                "PASS — bolts adequate for centrifugal pull-out."
                if ok else
                f"FAIL — τ {tau/1e6:.1f} MPa > {allowable_shear_pa/1e6:.0f} MPa. "
                "Increase bolt diameter, add bolts, or reduce belt speed."
            ),
        }

    # ── 5. Pulleys ────────────────────────────────────────────────────────────

    @staticmethod
    def pulley_shell_thickness(
        diameter_m:          float,
        T_total_N:           float = 0.0,
        face_width_mm:       float = 400.0,
        allowable_shell_pa:  float = 80e6,
    ) -> dict:
        """
        CEMA Pulley Standard — Pulley shell thickness [mm].

        Two criteria; governing (larger) applies:

        1. CEMA Pulley Standard minimum (diameter-based):
               t_cema = D/100 + 6  [mm]

        2. Hoop stress from belt wrap pressure:
               q  = T_total / (D × L_face)   [N/mm² = MPa]
               t  = q × D / (2 × σ_allow)    [mm]
           where D and L_face in mm, T_total in N.

        Note: for most bucket elevators, criterion 1 governs.  Criterion 2
        becomes relevant only for very wide, heavily loaded pulleys (large
        cement/potash applications).

        Previous v1.0 returned a float and only applied criterion 1.
        v1.1 returns a dict with both criteria and the governing value.

        Parameters
        ----------
        T_total_N      T1 + T2 total belt load [N].  Pass 0 to get CEMA minimum.
        face_width_mm  Pulley face width [mm]
        """
        D_mm   = diameter_m * 1000.0
        L_mm   = max(face_width_mm, 1.0)

        t_cema_mm = D_mm / 100.0 + 6.0

        if T_total_N > 0:
            q_MPa         = T_total_N / (D_mm * L_mm)   # [N/mm²]
            sigma_allow   = allowable_shell_pa / 1e6     # [MPa]
            t_pressure_mm = q_MPa * D_mm / (2.0 * sigma_allow)
        else:
            t_pressure_mm = 0.0

        t_governing_mm = max(t_cema_mm, t_pressure_mm, 6.0)
        governed_by    = "CEMA_minimum" if t_cema_mm >= t_pressure_mm else "belt_pressure"

        return {
            "t_cema_mm":       round(t_cema_mm,       1),
            "t_pressure_mm":   round(t_pressure_mm,   2),
            "t_governing_mm":  round(t_governing_mm,  1),
            "governed_by":     governed_by,
            "note": (
                "Pulley end-disc and hub stress require face width + weld geometry "
                "data — not yet implemented.  Use governing shell thickness for "
                "preliminary BOM only; verify against CEMA Pulley Standard."
            ),
        }

    # ── 6. Casing ─────────────────────────────────────────────────────────────

    @staticmethod
    def casing_plate_thickness(
        belt_width_mm:     float,
        bulk_density_kgm3: float = 1000.0,
        height_m:          float = 0.0,
    ) -> float:
        """
        CEMA 375 §7 — Casing plate thickness [m].
        Width/density matrix + height adjustment above 20 m.
        Unchanged from v1.0.
        """
        if belt_width_mm <= 200 and bulk_density_kgm3 < 800:
            t_mm = 3.0
        elif belt_width_mm <= 450 and bulk_density_kgm3 < 1500:
            t_mm = 5.0
        else:
            t_mm = 8.0

        if height_m > 20:
            t_mm += (height_m - 20) / 20.0

        return max(t_mm, 3.0) / 1000.0

    # ── 7. Bearings ───────────────────────────────────────────────────────────

    @staticmethod
    def bearing_equivalent_load(
        Fr:         float,
        Fa:         float = 0.0,
        X:          float = 1.0,
        Y:          float = 0.0,
        shock_fd:   float = 1.2,
    ) -> float:
        """
        ISO 281 — Equivalent dynamic bearing load P [N].
        P = f_d × (X·Fr + Y·Fa)

        X, Y — radial and axial load factors from bearing catalogue.
        Default X=1, Y=0 is pure radial load (most bucket elevator bearings).

        Common single-row deep groove (6000 series), e threshold:
          Fr/(C0) ≤ 0.014:  X=1.0, Y=2.3  (high axial fraction)
          Fr/(C0) ≥ 0.44:   X=0.56,Y=1.0

        Shock factor f_d (CEMA 375 §4, table 4-x):
          1.0  smooth, vibration-free operation
          1.2  light shock (normal bucket elevator, CEMA recommendation)
          1.5  moderate shock (abrasive, lump material)
          2.0  heavy shock (damp, sticky, hard lumps)

        Parameters
        ----------
        Fr       Radial bearing load from shaft_reactions() [RA or RB] [N]
        Fa       Axial load (thrust) on bearing [N]  (usually 0 for BE)
        X, Y     ISO 281 load factors from bearing catalogue
        shock_fd CEMA shock factor

        Returns
        -------
        float  Equivalent dynamic load P [N] for L10 calculation
        """
        return shock_fd * (X * Fr + Y * Fa)

    @staticmethod
    def bearing_l10(C: float, P: float, n_rpm: float) -> float:
        """
        ISO 281 — Bearing L10 life [hours].
        L10 = (C/P)³ × 10⁶ / (60 × n)
        Fixed from v1.0 which returned millions of revolutions, not hours.
        """
        L10_Mrev = (C / max(P, 1.0)) ** 3
        return L10_Mrev * 1e6 / (60.0 * max(n_rpm, 1.0))

    @staticmethod
    def bearing_l10_revolutions(C: float, P: float) -> float:
        """ISO 281 — Bearing L10 life [millions of revolutions]. Unchanged."""
        return (C / max(P, 1.0)) ** 3

    @staticmethod
    def bearing_life_assessment(L10_hours: float) -> str:
        """CEMA 375 §4 — Qualitative bearing life assessment.  Unchanged."""
        if L10_hours < 20_000:
            return f"INSUFFICIENT ({L10_hours:.0f} h) — upgrade bearing or reduce shaft load"
        elif L10_hours < 40_000:
            return f"ACCEPTABLE ({L10_hours:.0f} h) — suitable for ≤ 16 h/day"
        elif L10_hours < 80_000:
            return f"GOOD ({L10_hours:.0f} h) — suitable for 24/7 continuous duty"
        else:
            return f"EXCELLENT ({L10_hours:.0f} h) — exceeds standard requirements"

    # ── 8. Pulley Lagging Design ──────────────────────────────────────────────

    @staticmethod
    def pulley_lagging(
        material: dict,
        T_effective_N: float,
        T_slack_N: float,
        wrap_angle_deg: float = 180.0,
        environment: str = "dry",
        belt_type: str = "EP",
    ) -> dict:
        """
        CEMA 375 §4 / manufacturer practice — Head pulley lagging selection.

        Lagging serves two functions:
          1. Friction — increases belt-pulley μ to prevent slip at drive pulley
          2. Protection — shields shell from abrasion and corrosion

        The selection is driven by four independent factors (all must be satisfied):
          A. Material category (fine powder jams rubber grooves → ceramic)
          B. Moisture / environment (wet conditions → grooved or ceramic)
          C. Belt tension ratio (high ratio → high μ required → ceramic)
          D. Material abrasiveness (abr ≥ 6 → ceramic or armoured rubber)

        Selection matrix (conditions checked in priority order):
          Fine powder OR highly abrasive OR (wet + high tension):
            → ceramic_embedded_rubber   μ_dry=0.50  μ_wet=0.45  t=16mm
          Wet OR (humid + high tension):
            → rubber_diamond_groove     μ_dry=0.45  μ_wet=0.35  t=12mm
          Light duty dry (abr ≤ 2, moisture ≤ 10%, standard tension):
            → rubber_herringbone        μ_dry=0.40  μ_wet=0.28  t=10mm
          Standard (default):
            → rubber_herringbone        μ_dry=0.40  μ_wet=0.30  t=12mm

        Slip upgrade rule: if the selected lagging is still insufficient to
        prevent belt slip (actual T_tight/T_slack > e^(μ×θ)), the selection
        is automatically upgraded to ceramic_embedded_rubber and re-checked.

        Note for ST (steel cord) belts: diamond groove can cause resonant
        vibration at splice gaps; herringbone is preferred.

        Parameters
        ----------
        material       dict from MATERIALS database
        T_effective_N  Effective tension = T1+T2 [N] from the solver
        T_slack_N      Slack-side tension T3 [N] from the solver
        wrap_angle_deg Drive pulley wrap angle [deg] — default 180°
        environment    "dry" | "humid" | "wet" | "submerged"
        belt_type      "EP" | "ST"

        Returns
        -------
        {
            "lagging_type":             str
            "lagging_required":         bool
            "ceramic_required":         bool
            "thickness_mm":             float
            "mu_dry":                   float
            "mu_wet":                   float
            "mu_operating":             float   (wet or dry per environment)
            "euler_ratio_lagged":       float   e^(mu_oper × theta)
            "belt_ratio_tight_slack":   float   (T_eff + T_slack) / T_slack
            "slip_safe":                bool
            "cover_recommendation":     str
            "upgraded":                 bool    True if auto-upgraded for slip
        }
        """
        abr         = material.get("abr_code",     3)
        moisture    = material.get("moisture_pct", 0.0)
        flowability = material.get("flowability",  2)
        hazards     = material.get("hazard_codes", [])

        is_wet         = environment in ("wet", "submerged") or moisture > 20.0
        is_humid       = environment == "humid"              or moisture > 15.0
        is_corrosive   = "B4" in hazards
        is_fine_powder = flowability >= 4 and abr <= 5   # cement (abr=5), fly ash, flour
        is_high_abr    = abr >= 6

        # Belt tight-side load (T_tight = T_effective + T_slack in VECTRIX naming)
        T_tight = T_effective_N + T_slack_N
        ratio   = T_tight / max(T_slack_N, 1.0)

        def _make_selection(lagging_type, mu_dry, mu_wet, thickness_mm, ceramic):
            mu_op   = mu_wet if (is_wet or is_humid) else mu_dry
            theta   = math.radians(wrap_angle_deg)
            euler   = math.exp(mu_op * theta)
            safe    = ratio <= euler
            if lagging_type == "ceramic_embedded_rubber":
                cover = "Ceramic tile in rubber matrix (Rulmeca HiCer, Martin Engineering, or equiv.)"
            elif lagging_type == "rubber_diamond_groove":
                cover = "Diamond groove NR rubber, Shore 60-65A"
            else:
                cover = "Herringbone groove NR rubber, Shore 55-60A"
            if belt_type == "ST" and lagging_type == "rubber_diamond_groove":
                lagging_type = "rubber_herringbone"
                cover = "Herringbone NR rubber, Shore 60-65A (diamond groove not recommended for ST belt)"
            return lagging_type, mu_dry, mu_wet, thickness_mm, ceramic, mu_op, euler, safe, cover

        # Priority selection
        if is_fine_powder or is_high_abr or (is_wet and ratio > 2.5) or is_corrosive:
            t, mdry, mwet, tmm, cer, mop, eul, safe, cov = _make_selection(
                "ceramic_embedded_rubber", 0.50, 0.45, 16, True)
        elif is_wet or (is_humid and ratio > 2.2):
            t, mdry, mwet, tmm, cer, mop, eul, safe, cov = _make_selection(
                "rubber_diamond_groove", 0.45, 0.35, 12, False)
        elif abr <= 2 and not is_humid and ratio <= 2.0:
            t, mdry, mwet, tmm, cer, mop, eul, safe, cov = _make_selection(
                "rubber_herringbone", 0.40, 0.28, 10, False)
        else:
            t, mdry, mwet, tmm, cer, mop, eul, safe, cov = _make_selection(
                "rubber_herringbone", 0.40, 0.30, 12, False)

        # Slip upgrade — if primary selection can't prevent slip, upgrade to ceramic
        upgraded = False
        if not safe and not cer:
            t, mdry, mwet, tmm, cer, mop, eul, safe, cov = _make_selection(
                "ceramic_embedded_rubber", 0.50, 0.45, 16, True)
            upgraded = True

        return {
            "lagging_type":           t,
            "lagging_required":       True,
            "ceramic_required":       cer,
            "thickness_mm":           tmm,
            "mu_dry":                 mdry,
            "mu_wet":                 mwet,
            "mu_operating":           round(mop, 3),
            "euler_ratio_lagged":     round(eul, 3),
            "belt_ratio_tight_slack": round(ratio, 3),
            "slip_safe":              safe,
            "cover_recommendation":   cov,
            "upgraded":               upgraded,
            "note": (
                "μ values are nominal CEMA/manufacturer mid-range. "
                "Verify with belt and lagging supplier for actual service conditions."
            ),
        }

    # ── 9. Pulley End Disc ────────────────────────────────────────────────────

    @staticmethod
    def pulley_end_disc(
        pulley_diameter_m:   float,
        hub_od_m:            float,
        T_total_N:           float,
        face_width_m:        float = 0.400,
        allowable_stress_pa: float = 80e6,
    ) -> dict:
        """
        Pulley end disc preliminary thickness — CEMA Pulley Standard / Roark.

        The end disc transfers belt tension from the shell rim to the shaft hub.
        Two criteria are checked; the larger governs:

        1. Membrane (direct tension) at hub junction:
              σ_mem = F_disc / (π × D_hub × t)
              t_mem = F_disc / (π × D_hub × σ_allow)

        2. Plate bending (disc treated as cantilever, loaded at rim):
              M = F_disc × (R_shell − R_hub)   [N·m]
              Z = (1/6) × π × D_hub × t²
              σ_bend = M / Z
              t_bend = √(6 × F_disc × arm / (π × D_hub × σ_allow))

        where F_disc = T_total / 2 (two end discs share the belt tension load).

        Note: This is a simplified first-pass model.  A full Roark annular plate
        analysis or FEA is required for fabrication drawings.  The simplified
        cantilever overestimates arm length slightly (conservative for t).

        CEMA Pulley Standard minimum disc thicknesses enforced:
          t_min = 8 mm  for D_pulley < 500 mm
          t_min = 12 mm for D_pulley 500–800 mm
          t_min = 16 mm for D_pulley > 800 mm

        Parameters
        ----------
        pulley_diameter_m    Pulley shell OD [m]
        hub_od_m             Hub outer diameter from hub_diameter() [m]
        T_total_N            Total belt tight-side tension [N]
        face_width_m         Pulley face width [m] (used only for context)
        allowable_stress_pa  Allowable bending stress for A36 steel disc [Pa].
                             Typical: 80–100 MPa for welded construction.
        """
        R_shell = pulley_diameter_m / 2.0
        R_hub   = hub_od_m          / 2.0
        F_disc  = T_total_N / 2.0   # each end disc carries half the load

        # Criterion 1: membrane stress at hub bore
        circ_hub  = math.pi * hub_od_m
        t_mem     = F_disc / (circ_hub * allowable_stress_pa)

        # Criterion 2: bending (cantilever from hub to shell rim)
        arm     = R_shell - R_hub
        t_bend  = math.sqrt(
            6.0 * F_disc * arm / (math.pi * hub_od_m * allowable_stress_pa)
        )

        # CEMA Pulley Standard minimum
        D_mm = pulley_diameter_m * 1000.0
        if D_mm < 500:
            t_cema = 0.008
        elif D_mm <= 800:
            t_cema = 0.012
        else:
            t_cema = 0.016

        t_structural = max(t_mem, t_bend)
        t_final      = max(t_structural, t_cema)
        governed_by  = (
            "CEMA_minimum"  if t_cema   >= max(t_mem, t_bend) else
            "plate_bending" if t_bend   >= t_mem               else
            "membrane_tension"
        )

        # Actual stresses at governing thickness
        sig_mem  = F_disc / (math.pi * hub_od_m * t_final)
        sig_bend = 6.0 * F_disc * arm / (math.pi * hub_od_m * t_final ** 2)
        sig_max  = max(sig_mem, sig_bend)
        SF       = allowable_stress_pa / max(sig_max, 1.0)

        return {
            "t_membrane_mm":     round(t_mem  * 1000, 1),
            "t_bending_mm":      round(t_bend * 1000, 1),
            "t_cema_min_mm":     round(t_cema * 1000, 0),
            "t_governing_mm":    round(t_final * 1000, 1),
            # v1.9.9 — pre-computed spec thickness (+20% construction tolerance
            # allowance) so the frontend doesn't need Math.ceil(t * 1.20).
            "t_specified_mm":    math.ceil(t_final * 1000 * 1.20),
            "governed_by":       governed_by,
            "sigma_membrane_MPa":round(sig_mem  / 1e6, 1),
            "sigma_bending_MPa": round(sig_bend / 1e6, 1),
            "sigma_max_MPa":     round(sig_max  / 1e6, 1),
            "allowable_MPa":     round(allowable_stress_pa / 1e6, 0),
            "safety_factor":     round(SF, 2),
            "F_per_disc_N":      round(F_disc, 0),
            "arm_m":             round(arm, 4),
            "note": (
                "Simplified cantilever model — conservative preliminary sizing. "
                "Full Roark annular plate analysis or FEA required for fabrication."
            ),
        }

    # ── 10. Bucket Bolt Fatigue ───────────────────────────────────────────────

    @staticmethod
    def bucket_bolt_fatigue(
        belt_speed_mps:      float,
        head_radius_m:       float,
        bucket_mass_kg:      float,
        fill_mass_kg:        float,
        n_bolts:             int   = 2,
        bolt_diameter_mm:    float = 12.0,
        bolt_grade:          str   = "8.8",
        n_rpm:               float = 60.0,
        service_hours_yr:    float = 8760.0,
    ) -> dict:
        """
        Bucket mounting bolt fatigue assessment — Goodman diagram approach.

        Each bucket cycle through the head pulley applies a FULLY REVERSING
        centrifugal load to the mounting bolts:
          F_max = (m_bucket + m_fill) × v² / r   [N]  (at head pulley — maximum)
          F_min ≈ 0 N                                  (at boot — gravity loads belt,
                                                         not the bolt)

        Fatigue model (Goodman line, single-shear bolts):
          σ_mean      = F_max / (2 × n_bolts × A_bolt)
          σ_alt       = F_max / (2 × n_bolts × A_bolt)   (fully reversed ≈ same)
          Goodman:    σ_alt / S_e + σ_mean / S_ut ≤ 1.0

        Fatigue endurance limit S_e (metric bolts, machined surface, Kf=2.2):
          S_e = 0.5 × S_ut / Kf  for S_ut ≤ 1400 MPa
        Bolt grade ultimate strengths (ISO 898-1):
          8.8:  S_ut = 800 MPa,  S_y = 640 MPa
          10.9: S_ut = 1040 MPa, S_y = 940 MPa
          12.9: S_ut = 1220 MPa, S_y = 1100 MPa
          ASTM A325:  S_ut = 830 MPa
          ASTM A490:  S_ut = 1040 MPa

        Fatigue life estimate (Basquin, b = −0.085 for metric bolts):
          N = (S_e / σ_alt)^(1/b)   [cycles]

        Parameters
        ----------
        bucket_mass_kg   Actual catalogue bucket mass [kg]
        fill_mass_kg     Material mass in loaded bucket = V × η × ρ / 1000  [kg]
        n_bolts          Mounting bolts per bucket
        bolt_grade       ISO grade string or "A325" / "A490"
        n_rpm            Head shaft speed [rpm]
        service_hours_yr Annual operating hours

        Returns
        -------
        {
            "F_max_N":             float   Peak centrifugal bolt load [N]
            "sigma_mean_MPa":      float
            "sigma_alt_MPa":       float
            "S_e_MPa":             float   Endurance limit [MPa]
            "S_ut_MPa":            float   Ultimate strength [MPa]
            "goodman_ratio":       float   Must be ≤ 1.0 for infinite life
            "fatigue_life_Mcyc":   float   Estimated fatigue life [million cycles]
            "life_years":          float   At given rpm and hours/year
            "pass_infinite_life":  bool
            "recommendation":      str
        }
        """
        GRADES = {
            "8.8":  (800e6,  640e6),
            "10.9": (1040e6, 940e6),
            "12.9": (1220e6, 1100e6),
            "A325": (830e6,  635e6),
            "A490": (1040e6, 940e6),
        }
        Sut, Sy = GRADES.get(bolt_grade, GRADES["8.8"])

        # Bolt shear area
        A_bolt = math.pi / 4.0 * (bolt_diameter_mm / 1000.0) ** 2

        # Peak centrifugal load
        F_max = (bucket_mass_kg + fill_mass_kg) * (belt_speed_mps ** 2) / max(head_radius_m, 0.001)

        # Stresses (single shear per bolt)
        sigma_mean = F_max / (2.0 * n_bolts * A_bolt)  # fully reversed: mean = alt
        sigma_alt  = sigma_mean

        # Endurance limit with fatigue stress concentration Kf = 2.2 (threaded)
        Kf = 2.2
        Se = 0.5 * Sut / Kf

        # Goodman damage ratio
        goodman = sigma_alt / Se + sigma_mean / Sut
        pass_inf = goodman <= 1.0

        # Basquin fatigue life (b = −0.085 for grade 8.8 metric bolts)
        b = -0.085
        if sigma_alt > 0:
            N_cycles = (Se / sigma_alt) ** (1.0 / b)
        else:
            N_cycles = float("inf")

        # Convert to years
        cycles_per_year = n_rpm * 60.0 * service_hours_yr
        life_years = N_cycles / max(cycles_per_year, 1.0)

        if pass_inf:
            rec = (f"PASS — Goodman ratio {goodman:.3f} ≤ 1.0. "
                   f"Infinite fatigue life predicted for grade {bolt_grade} bolts.")
        elif life_years >= 10:
            rec = (f"CAUTION — Finite life {life_years:.1f} years. "
                   f"Increase bolt diameter or upgrade to grade 10.9.")
        else:
            rec = (f"FAIL — Fatigue life {life_years:.1f} years insufficient. "
                   f"Increase bolt diameter to {bolt_diameter_mm*1.25:.0f} mm, "
                   f"add bolts, or upgrade to grade 10.9/12.9.")

        return {
            "F_max_N":            round(F_max,       1),
            "sigma_mean_MPa":     round(sigma_mean / 1e6, 1),
            "sigma_alt_MPa":      round(sigma_alt  / 1e6, 1),
            "S_e_MPa":            round(Se          / 1e6, 1),
            "S_ut_MPa":           round(Sut         / 1e6, 0),
            "goodman_ratio":      round(goodman,     3),
            "fatigue_life_Mcyc":  round(N_cycles    / 1e6, 2) if N_cycles < 1e15 else None,
            "life_years":         round(life_years,  1)        if life_years < 1e9  else None,
            "pass_infinite_life": pass_inf,
            "recommendation":     rec,
            "bolt_grade":         bolt_grade,
            "n_bolts":            n_bolts,
            "bolt_dia_mm":        bolt_diameter_mm,
        }

    # ── 11. Take-Up Design ────────────────────────────────────────────────────

    @staticmethod
    def gravity_takeup(
        T_slack_N:      float,
        height_m:       float,
        belt_width_mm:  float,
        belt_Ekgm2:     float = 8.0,
    ) -> dict:
        """
        CEMA 375 §4 — Gravity take-up counterweight and travel sizing.

        The gravity take-up maintains constant T_slack by hanging a counterweight
        on the take-up pulley carriage.  Two strands of belt carry the pulley,
        so the counterweight must equal 2 × T_slack (net, minus carriage weight).

        Counterweight:
          W_cw = 2 × T_slack_N / g       [kg]  gross (add carriage tare ≈ 10%)

        Take-up travel:
          t_travel = t_thermal + t_elongation + t_minimum

          Thermal expansion:
            ΔL = α_steel × H_total × ΔT = 12e-6 × H_m × 80°C
          Belt elastic elongation at rated tension:
            ΔL_belt = T_slack / (E_belt × A_belt)  [m]
            (A_belt ≈ belt_width_mm × E_rating/1000 for EP belt — simplified)
          Minimum clearance: 300 mm (CEMA §4 minimum take-up travel)

        Parameters
        ----------
        T_slack_N     Required slack-side tension from Euler check [N]
        height_m      Elevator lift height [m]
        belt_width_mm Belt width [mm]
        belt_Ekgm2    Belt weight per m² [kg/m²] (default EP400 nominal)
        """
        g = _gravity()

        # Counterweight mass (2 × T3, both belt strands carry take-up pulley)
        W_cw_net  = 2.0 * T_slack_N / g          # kg net
        W_cw_gross = W_cw_net * 1.10              # +10% for carriage tare

        # Take-up travel
        alpha_steel   = 12e-6           # steel thermal expansion [/°C]
        delta_T       = 80.0            # °C temperature range
        L_thermal     = alpha_steel * 2.0 * height_m * delta_T  # both strands

        # Belt elongation approximation (EP belt: ε ≈ T/(E_rating × width))
        E_belt_Nm     = 400_000 * (belt_width_mm / 1000.0)   # EP400 stiffness [N]
        L_belt_elong  = T_slack_N / E_belt_Nm

        travel_m = max(L_thermal + L_belt_elong + 0.300, 0.300)

        return {
            "W_counterweight_kg_net":   round(W_cw_net,   1),
            "W_counterweight_kg_gross": round(W_cw_gross, 1),
            "travel_m":                 round(travel_m,   3),
            "travel_thermal_m":         round(L_thermal,  4),
            "travel_elongation_m":      round(L_belt_elong, 4),
            "travel_min_CEMA_m":        0.300,
            "note": (
                "Add 20% margin to travel for field adjustment headroom. "
                "Verify counterweight weight against structural take-up frame capacity."
            ),
        }

    @staticmethod
    def screw_takeup(
        T_slack_N:    float,
        screw_pitch_mm: float = 6.0,
        eta_screw:    float = 0.85,
        travel_m:     float = 0.500,
        screw_length_m: float = 0.600,
        preferred_d_mm: float = 0.0,
    ) -> dict:
        """
        CEMA 375 §4 — Screw take-up thread load and buckling check.

        v1.5.0: preferred_d_mm override.
        When preferred_d_mm > 0 (user-specified), the buckling SF is recalculated
        for that diameter and the result reports both the minimum required diameter
        and the user's specified diameter, making the pass/fail immediately visible.

        Parameters
        ----------
        preferred_d_mm  User-specified screw core diameter [mm]. 0 = auto.
        """
        E = _shaft_E()

        F_screw = 2.0 * T_slack_N / eta_screw

        # Minimum core diameter from direct compressive stress (conservative)
        sigma_allow = 60e6   # Pa, A36
        d_core_min  = math.sqrt(4.0 * F_screw / (math.pi * sigma_allow))  # m

        # Actual diameter to use: preferred (if given) or calculated minimum
        d_core_use  = (max(d_core_min, preferred_d_mm / 1000.0)
                       if preferred_d_mm > 0 else d_core_min)
        override_applied = preferred_d_mm > 0
        override_adequate = (preferred_d_mm / 1000.0) >= d_core_min if override_applied else True

        # Euler buckling check with actual diameter
        I_use       = math.pi * d_core_use ** 4 / 64.0
        F_euler     = (math.pi ** 2 * E * I_use) / (screw_length_m ** 2)
        SF_buckling = F_euler / max(F_screw, 1.0)
        buckling_ok = SF_buckling >= 3.0

        turns_required = travel_m / (screw_pitch_mm / 1000.0)

        # Recommended commercial diameter: next standard above d_core_min
        _stds = [20, 25, 32, 40, 50, 63, 80, 100]
        d_recommend_mm = next((s for s in _stds if s >= d_core_min * 1000), 100)

        if buckling_ok:
            rec = f"PASS — buckling SF={SF_buckling:.1f} ≥ 3.0"
        elif override_applied and not buckling_ok:
            rec = (
                f"FAIL — specified Ø{preferred_d_mm:.0f} mm gives "
                f"buckling SF={SF_buckling:.1f} < 3.0. "
                f"Increase to ≥ Ø{d_recommend_mm} mm "
                f"(set takeup_screw_d_mm = {d_recommend_mm}) "
                f"or add an intermediate guide support to halve the effective length."
            )
        else:
            rec = (
                f"FAIL — buckling SF={SF_buckling:.1f} < 3.0 "
                f"(auto min Ø{d_core_min*1000:.0f} mm). "
                f"Set takeup_screw_d_mm = {d_recommend_mm} in Design Overrides "
                f"or add an intermediate guide support."
            )

        return {
            "F_screw_N":         round(F_screw,              0),
            "d_core_min_mm":     round(d_core_min * 1000,    1),
            "d_core_use_mm":     round(d_core_use * 1000,    1),
            "d_core_recommend_mm": d_recommend_mm,
            "F_euler_N":         round(F_euler,               0),
            "SF_buckling":       round(SF_buckling,           2),
            "turns_required":    round(turns_required,        0),
            "travel_m":          travel_m,
            "override_applied":  override_applied,
            "override_adequate": override_adequate,
            "buckling_safe":     buckling_ok,
            "recommendation":    rec,
        }

    # ── 12. Casing Panel Deflection and Stiffeners ────────────────────────────

    @staticmethod
    def casing_panel_deflection(
        panel_width_m:  float,
        panel_height_m: float,
        plate_thickness_m: float,
        wind_pressure_pa: float = 800.0,
        internal_pressure_pa: float = 0.0,
    ) -> dict:
        """
        Casing panel deflection check under wind + internal suction loading.

        Casing panels are modelled as simply-supported rectangular plates.
        Maximum deflection at centre (Timoshenko plate formula, square plate approx.):

          δ_max = 0.0443 × q × a⁴ / (E × t³)   (for square panel, ν = 0.3)

        where a = shorter panel dimension [m], q = total applied pressure [Pa].

        Allowable deflection: L / 360  [AISC serviceability limit]

        For a non-square panel, conservative approximation uses the shorter span.

        Parameters
        ----------
        panel_width_m        Panel width between stiffeners [m]
        panel_height_m       Panel height between stiffeners [m]
        plate_thickness_m    Casing plate thickness from casing_plate_thickness() [m]
        wind_pressure_pa     External wind pressure [Pa]. Typical: 600–1200 Pa
                             (AS1170.2 / ASCE 7: industrial site, 50-yr wind)
        internal_pressure_pa Boot section internal pressure/suction [Pa].
                             Typically 0–500 Pa for sealed casings.
        """
        E    = _shaft_E()
        q    = wind_pressure_pa + internal_pressure_pa
        a    = min(panel_width_m, panel_height_m)     # shorter span governs
        t    = max(plate_thickness_m, 0.001)

        delta_actual = 0.0443 * q * a ** 4 / (E * t ** 3)
        delta_allow  = a / 360.0                       # L/360 serviceability

        sigma_max = 0.3078 * q * a ** 2 / t ** 2      # midspan bending stress [Pa]
        sigma_yield = 250e6                             # A36 Sy
        SF_stress = sigma_yield / max(sigma_max, 1.0)

        status = "ok" if delta_actual <= delta_allow else "fail"

        return {
            "delta_actual_mm":  round(delta_actual * 1000, 2),
            "delta_allow_mm":   round(delta_allow  * 1000, 2),
            "sigma_max_MPa":    round(sigma_max / 1e6, 1),
            "SF_yield":         round(SF_stress, 2),
            "status":           status,
            "a_mm":             round(a * 1000, 0),
            "t_mm":             round(t * 1000, 1),
            "q_Pa":             round(q, 0),
            "recommendation": (
                "Panel deflection within L/360 limit — stiffener spacing acceptable."
                if status == "ok" else
                f"Panel deflects {delta_actual*1000:.1f} mm > allowable {delta_allow*1000:.1f} mm. "
                f"Reduce stiffener spacing or increase plate thickness."
            ),
        }

    @staticmethod
    def casing_stiffener_spacing(
        plate_thickness_m: float,
        wind_pressure_pa:  float = 800.0,
        allowable_defl_ratio: float = 360.0,
    ) -> dict:
        """
        Maximum stiffener spacing for a casing plate at given loading.

        Inverts the Timoshenko plate deflection formula to find the maximum
        panel dimension a such that δ_max ≤ a / allowable_defl_ratio.

        Setting δ_allow = a / D:
          a / D = 0.0443 × q × a⁴ / (E × t³)
          a³ = E × t³ / (0.0443 × q × D)
          a  = ∛(E × t³ / (0.0443 × q × D))

        Parameters
        ----------
        plate_thickness_m    Casing plate thickness [m]
        wind_pressure_pa     Applied lateral pressure [Pa]
        allowable_defl_ratio L/n deflection limit (360 = L/360, 240 = L/240)

        Returns
        -------
        {
            "max_spacing_mm":  float   Maximum stiffener pitch [mm]
            "recommended_mm":  float   max_spacing × 0.85 safety margin [mm]
        }
        """
        E = _shaft_E()
        t = max(plate_thickness_m, 0.001)
        q = max(wind_pressure_pa,  0.001)
        D = allowable_defl_ratio

        a_max = (E * t ** 3 / (0.0443 * q * D)) ** (1.0 / 3.0)

        return {
            "max_spacing_mm":    round(a_max         * 1000, 0),
            "recommended_mm":    round(a_max * 0.85  * 1000, 0),
            "plate_thickness_mm":round(t              * 1000, 1),
            "wind_pressure_Pa":  round(q,              0),
            "defl_limit":        f"L / {D:.0f}",
            "note": (
                "Use recommended spacing (85% of maximum) to allow for "
                "construction tolerance and combined wind + seismic loading."
            ),
        }

    @staticmethod
    def casing_bolt_quantities(
        height_m:           float,
        belt_width_mm:      float,
        plate_thickness_mm: float,
        n_stiffener_sets:   int = 1,
        bolt_pitch_mm:      float = 150.0,
    ) -> dict:
        """
        v1.9.9 — Casing assembly bolt count and size.

        Distinct from bucket_bolt_fatigue()'s bolt_spacing_mm, which sizes
        the bucket-to-belt attachment bolts under cyclic fatigue loading.
        This sizes the STRUCTURAL ASSEMBLY bolts that join casing panel
        sections to each other and to the stiffener frame — a dust/wind
        seal and structural joint, not a fatigue-loaded fastener.

        Bolt size selected by plate thickness (standard shop practice —
        thin sheet doesn't need or support a large bolt; thick plate
        warrants a larger one for adequate bearing area):
            t <= 3mm  -> M8
            t <= 6mm  -> M10
            t <= 10mm -> M12
            t >  10mm -> M16

        Quantity estimated from total panel perimeter (4 vertical seams
        over the elevator height, approximating a rectangular casing cross
        section) divided by a standard bolt pitch, PLUS bolts at each
        stiffener band (panel-to-stiffener fixing, one bolt per
        panel-width increment at each stiffener elevation).

        This is a first-order fabrication estimate, not a structural
        connection design — actual bolt pattern depends on the OEM's
        panel module size and stiffener detail, which varies by shop
        practice.

        Parameters
        ----------
        height_m            Elevator lift height [m]
        belt_width_mm        Belt width [mm] (casing cross-section driver)
        plate_thickness_mm   Casing plate thickness [mm] (drives bolt size)
        n_stiffener_sets     Number of stiffener bands over the height
        bolt_pitch_mm         Standard bolt spacing along a seam [mm]

        Returns
        -------
        {
            "bolt_size":           str,   e.g. "M10"
            "n_bolts_seams":       int,   vertical seam bolts
            "n_bolts_stiffeners":  int,   panel-to-stiffener bolts
            "n_bolts_total":       int,
            "seam_length_m":       float,
        }
        """
        t = max(plate_thickness_mm, 1.0)
        if t <= 3.0:
            bolt_size = "M8"
        elif t <= 6.0:
            bolt_size = "M10"
        elif t <= 10.0:
            bolt_size = "M12"
        else:
            bolt_size = "M16"

        # 4 vertical seams (approximating a rectangular casing) over the
        # full lift height, each bolted at bolt_pitch_mm centres.
        n_seams        = 4
        seam_length_m  = height_m
        pitch_m        = max(bolt_pitch_mm, 25.0) / 1000.0
        n_bolts_seams  = max(4, round(n_seams * seam_length_m / pitch_m))

        # Panel-to-stiffener bolts: roughly 1 bolt per 150mm of girth at
        # each stiffener elevation (girth approximated from belt width,
        # consistent with the BOM's casing cross-section assumption).
        girth_m            = 2.0 * ((belt_width_mm + 120.0) / 1000.0 + 0.20)
        n_bolts_stiffeners = max(0, round(n_stiffener_sets * girth_m / pitch_m))

        n_bolts_total = n_bolts_seams + n_bolts_stiffeners

        return {
            "bolt_size":          bolt_size,
            "n_bolts_seams":      n_bolts_seams,
            "n_bolts_stiffeners": n_bolts_stiffeners,
            "n_bolts_total":      n_bolts_total,
            "seam_length_m":      round(seam_length_m, 2),
        }

    # ── 13. Design Recommendation Engine ─────────────────────────────────────

    @staticmethod
    def design_recommendations(results: dict, inputs: dict) -> list:
        """
        VECTRIX design recommendation engine — converts check failures into
        specific corrective actions the engineer can take immediately.

        For each failed or warned check in the solver results, generates one or
        more concrete recommendations with estimated parameter values.

        This is the 'Priority 3' item from the reviewer's structural audit:
        'users won't just see a failure — they'll immediately see how to fix it.'

        Parameters
        ----------
        results  dict from solve_elevator() — contains checks, Q, v, cr, etc.
        inputs   dict from BucketElevatorInput — user design parameters

        Returns
        -------
        list of dicts, each:
            {
                "check":    str    e.g. "CAPACITY", "SPEED", "CR"
                "status":   str    "fail" | "warn"
                "problem":  str    concise description
                "actions":  list   ordered list of corrective actions (strings)
            }
        """
        recs   = []
        Q      = float(results.get("Q")      or results.get("Q_th") or 0)
        v      = float(results.get("v")      or results.get("v_ms") or 0)
        cr     = float(results.get("cr")     or results.get("centrifugal_ratio") or 0)
        L10    = float(results.get("L10")    or results.get("L10_hours") or 0)
        d_mm   = float(results.get("d_mm")   or results.get("shaft_d_mm") or 0)
        P_tot  = float(results.get("P_total") or 0)
        R_head = float(results.get("R_headshaft") or 0)
        T3     = float(results.get("T3") or 0)
        euler  = float(results.get("euler_ratio") or 0)
        slip   = results.get("slip_safe")
        bucket = results.get("bucket") or {}

        Q_req  = float(inputs.get("Q_req",   100))
        n_rpm  = float(inputs.get("n_rpm",    60))
        D_mm   = float(inputs.get("D_mm",    500))
        fill   = float(inputs.get("fill_pct", 75))
        mu     = float(inputs.get("mu",      0.35))
        wrap   = float(inputs.get("wrap_deg",180))

        is_continuous = results.get("is_continuous", False)
        is_chain      = results.get("is_chain",      False)

        # ── Capacity ─────────────────────────────────────────────────────────
        if Q < Q_req:
            deficit_pct = (Q_req - Q) / Q_req * 100
            n_needed    = n_rpm * (Q_req / max(Q, 0.01)) ** 0.5   # approx
            fill_needed = min(fill * Q_req / max(Q, 0.01), 90)
            recs.append({
                "check":   "CAPACITY",
                "status":  "fail",
                "problem": f"Capacity {Q:.1f} t/h is {deficit_pct:.0f}% below {Q_req:.0f} t/h",
                "actions": [
                    f"Increase RPM from {n_rpm:.0f} to {n_needed:.0f} (within CEMA speed range for selected bucket)",
                    f"Increase fill factor from {fill:.0f}% to {fill_needed:.0f}% (check material suitability)",
                    "Select next larger bucket series (e.g. B → A → AA)",
                    f"Increase head pulley diameter from {D_mm:.0f} mm to {D_mm*1.15:.0f} mm to raise belt speed",
                ],
            })

        # ── Belt speed ────────────────────────────────────────────────────────
        v_min = bucket.get("v_min", 1.0)
        v_max = bucket.get("v_max", 3.0)
        if v < v_min:
            n_fix = n_rpm * v_min / max(v, 0.001) * 1.05
            recs.append({
                "check":   "SPEED",
                "status":  "warn",
                "problem": f"Belt speed {v:.2f} m/s below CEMA minimum {v_min:.2f} m/s — back-legging risk",
                "actions": [
                    f"Increase RPM from {n_rpm:.0f} to {n_fix:.0f} (minimum to reach v_min)",
                    f"Increase head pulley diameter from {D_mm:.0f} mm to {D_mm*v_min/max(v,0.001)*1.05:.0f} mm",
                    f"Switch to a bucket series with lower v_min than {v_min:.2f} m/s",
                ],
            })
        elif v > v_max:
            n_fix = n_rpm * v_max / max(v, 0.001) * 0.95
            recs.append({
                "check":   "SPEED",
                "status":  "fail",
                "problem": f"Belt speed {v:.2f} m/s exceeds CEMA maximum {v_max:.2f} m/s — scatter risk",
                "actions": [
                    f"Reduce RPM from {n_rpm:.0f} to {n_fix:.0f}",
                    f"Reduce head pulley diameter from {D_mm:.0f} mm to {D_mm*v_max/max(v,0.001)*0.95:.0f} mm",
                    f"Switch to bucket series with higher v_max (e.g. C or D series)",
                ],
            })

        # ── Centrifugal ratio ─────────────────────────────────────────────────
        # IMPORTANT: For continuous (HF/MF) bucket elevators, CR < 1.0 is
        # CORRECT and REQUIRED by design — do not raise this warning.
        # For centrifugal elevators, CR should be 1.0–1.8 for clean discharge.
        if not is_continuous and not is_chain:
            if cr < 1.0:
                recs.append({
                    "check":   "CR",
                    "status":  "warn",
                    "problem": f"CR = {cr:.3f} < 1.0 — mixed/gravity discharge, back-legging likely",
                    "actions": [
                        "Increase belt speed (increase RPM or pulley diameter)",
                        f"Target CR ≥ 1.2: requires v ≥ {math.sqrt(1.2 * 9.81 * (D_mm/2000)):.2f} m/s",
                        "Check material flowability — poor flow (flowability 4) needs higher CR",
                    ],
                })
            elif cr > 2.5:
                recs.append({
                    "check":   "CR",
                    "status":  "warn",
                    "problem": f"CR = {cr:.3f} > 2.5 — excessive scatter at head discharge",
                    "actions": [
                        "Reduce RPM or increase head pulley diameter to lower belt speed",
                        "Install curved discharge hood to capture scattered material",
                        f"Target CR ≤ 2.0: requires v ≤ {math.sqrt(2.0 * 9.81 * (D_mm/2000)):.2f} m/s",
                    ],
                })
        elif is_continuous and cr >= 1.0:
            # Continuous elevator running in centrifugal regime — this IS a problem
            recs.append({
                "check":   "CR",
                "status":  "fail",
                "problem": f"CR = {cr:.3f} ≥ 1.0 — centrifugal discharge in HF/MF elevator, material scatter and spillage",
                "actions": [
                    f"Reduce belt speed: target CR ≤ 0.7, need v ≤ {math.sqrt(0.7 * 9.81 * (D_mm/2000)):.2f} m/s",
                    f"Reduce RPM from {n_rpm:.0f} to {n_rpm * 0.7 / max(cr, 0.01):.0f}",
                    "Alternatively: switch to centrifugal bucket series (AC/AA) if duty allows",
                ],
            })

        # ── Chute angle (FABRICATION fix — not operational) ───────────────────
        # This check must appear BEFORE suggesting fill reduction to the user,
        # because reducing fill does NOT fix a chute angle problem and creates
        # a recursive loop if the RCA panel applies fill reductions repeatedly.
        dc   = results.get("discharge_chute") or {}
        perf = dc.get("performance") or {}
        mnt  = dc.get("maintenance") or {}
        regime_dc  = perf.get("flow_regime", "")
        chute_ang  = perf.get("chute_angle_deg", 0)
        mass_ang   = perf.get("mass_flow_angle_deg", 0)
        min_ang    = perf.get("min_angle_deg", 0)
        plug_risk  = mnt.get("plugging_risk", "LOW")
        liner_spec = mnt.get("liner_material", "mild steel")

        if regime_dc in ("FUNNEL_FLOW", "PLUGGING_RISK"):
            status_dc  = "fail" if regime_dc == "PLUGGING_RISK" else "warn"
            # Minimum fill that still meets capacity (floor for any fill suggestion)
            fill_floor = math.ceil(fill * Q_req / max(Q, 0.01) * 1.05)
            fill_floor = max(fill_floor, 30)
            recs.append({
                "check":   "CHUTE_ANGLE",
                "status":  status_dc,
                "problem": (
                    f"Chute back-plate {chute_ang:.0f}° — {regime_dc.replace('_',' ').lower()} "
                    f"(mass flow requires ≥ {mass_ang:.0f}°)"
                ),
                "actions": [
                    # PRIMARY fix is always a fabrication/geometry change
                    f"FABRICATION (primary): Steepen chute back-plate to ≥ {mass_ang:.0f}° "
                    f"(currently {chute_ang:.0f}° — steepen by {mass_ang - chute_ang:.0f}°). "
                    f"This does not require changing any operating parameter.",
                    # Liner can reduce the effective wall-friction angle
                    f"Specify {liner_spec} liner (reduces effective sticking angle by 5–10°)",
                    "Install air cannon or vibrator on chute back-plate for intermittent assist",
                    # Fill reduction is tertiary and must respect capacity floor
                    (f"SECONDARY only: reduce fill to {fill_floor}% to lower material "
                     f"head pressure on chute (floor = {fill_floor}% to maintain {Q_req:.0f} t/h). "
                     f"This alone cannot resolve a {mass_ang - chute_ang:.0f}° angle deficit.")
                    if fill > fill_floor + 5 else
                    f"Fill already near minimum for capacity — chute angle change is the only fix",
                ],
            })

        if plug_risk in ("HIGH", "SEVERE") and regime_dc not in ("FUNNEL_FLOW", "PLUGGING_RISK"):
            # Plugging risk despite adequate angle — liner / vibration issue
            recs.append({
                "check":   "PLUGGING",
                "status":  "warn",
                "problem": f"Chute plugging probability {plug_risk} despite adequate angle — cohesive material",
                "actions": [
                    f"Specify {liner_spec} liner to reduce surface adhesion",
                    "Install vibration motor or air cannon on chute back-plate",
                    "Consider chute geometry with steeper secondary slope",
                ],
            })

        # ── Belt slip ─────────────────────────────────────────────────────────
        if slip is False:
            euler_need = (R_head) / max(T3, 1.0)
            mu_need    = math.log(euler_need) / max(math.radians(wrap), 0.01)
            recs.append({
                "check":   "SLIP",
                "status":  "fail",
                "problem": f"Belt slips at drive pulley (ratio {(R_head/max(T3,1)):.3f} > Euler limit {euler:.3f})",
                "actions": [
                    f"Upgrade lagging: current μ={mu:.2f} → need μ ≥ {mu_need:.2f} "
                    f"(rubber→ceramic or add lagging)",
                    f"Add snub pulley to increase wrap from {wrap:.0f}° to {wrap+20:.0f}°",
                    f"Increase take-up tension T3 above {T3/1000:.1f} kN",
                    "Check Euler-Eytelwein output for specific minimum T3 required",
                ],
            })

        # ── Bearing life ──────────────────────────────────────────────────────
        if L10 < 20_000:
            recs.append({
                "check":   "BEARING",
                "status":  "fail",
                "problem": f"Bearing L10 = {L10:.0f} h < 20,000 h minimum for industrial duty",
                "actions": [
                    "Upgrade to next bearing size (increase C — basic dynamic rating)",
                    "Reduce shaft load: verify belt tensions and take-up setting",
                    "Consider spherical roller bearings for combined load tolerance",
                    f"Increase shaft diameter — reduces journal load concentration",
                ],
            })
        elif L10 < 40_000:
            recs.append({
                "check":   "BEARING",
                "status":  "warn",
                "problem": f"Bearing L10 = {L10:.0f} h — marginal for continuous 24/7 duty",
                "actions": [
                    "Consider one bearing size larger for continuous service",
                    "Ensure proper lubrication schedule and contamination control",
                ],
            })

        # ── Headshaft load ────────────────────────────────────────────────────
        if R_head > 80_000:
            recs.append({
                "check":   "HEADSHAFT",
                "status":  "fail",
                "problem": f"Headshaft radial load {R_head/1000:.1f} kN exceeds 80 kN — verify belt rating",
                "actions": [
                    "Increase belt class (PIW rating) to handle higher tensions",
                    "Increase head pulley diameter to reduce belt tensions",
                    "Split into two parallel elevators if load is structural not belt-limited",
                    "Verify T3 take-up setting — over-tensioned take-up increases R unnecessarily",
                ],
            })

        return recs