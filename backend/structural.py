"""
VECTRIX™ — Structural Stress Engine
Aligned with CEMA No. 375-2017 §4 & §7, ASME B17.1, ISO 281

CHANGES FROM ORIGINAL
─────────────────────
1. shaft_diameter(): CRITICAL — allowable stress baked into default parameter
   at class definition time. Python evaluates default args ONCE at import,
   so updating constants.py had NO effect on this method's default.
   Fix: constant now read inside the method body, not as a default parameter.

2. shaft_diameter(): Missing deflection check.
   CEMA 375 §4 / CEMA Pulley Standard: shaft must satisfy BOTH stress AND
   deflection (max slope 0.0015 in/in at bushing). Only stress was checked.
   Fix: shaft_diameter_deflection() added; shaft_diameter_governing() returns
   the larger of stress or deflection diameter with the governing criterion named.

3. bucket_thickness(): Dimensionally incomplete.
   Formula sqrt(F/σ)×1000 implicitly assumes a 1m-wide plate strip.
   Real buckets are 100–360mm wide — result was up to √(1/0.1)=3.2× too thin.
   Fix: bucket_width_mm parameter added; CEMA 375 §7 minimum (3mm light,
   5mm heavy) enforced.

4. bearing_l10(): CRITICAL — returns millions of revolutions, not hours.
   ISO 281: L10 [Mrev] = (C/P)³ → L10 [hours] = L10_Mrev × 10⁶ / (60 × n)
   Fix: n_rpm parameter added; method now returns hours directly.
   L10_revolutions() preserved for callers that need the raw Mrev value.

5. casing_plate_thickness(): Added CEMA 375 §7 minimums and belt-width basis.
   Height-only formula replaced with belt-width + density basis.
   CEMA minimums: 3mm (light ≤200mm belt), 5mm (standard), 8mm (heavy).

6. pulley_shell_thickness(): Updated to match CEMA Pulley Standard formula
   t = D/100 + 6mm. Original gave ~27% thicker shell — conservative but wasteful.
"""

import math


def _allowable_stress():
    """Read STEEL_ALLOWABLE_STRESS from constants at call time, not import time."""
    from constants import STEEL_ALLOWABLE_STRESS
    return STEEL_ALLOWABLE_STRESS


def _cema_max_slope():
    from constants import CEMA_MAX_SHAFT_SLOPE
    return CEMA_MAX_SHAFT_SLOPE


def _shaft_E():
    from constants import SHAFT_E_PA
    return SHAFT_E_PA


class StructuralStressEngine:

    # ── Shaft — Stress ────────────────────────────────────────────────────────

    @staticmethod
    def equivalent_torque(moment: float, torque: float,
                           kb: float = 1.5, kt: float = 1.0) -> float:
        """
        ASME B17.1 / CEMA 375 §4 — Combined equivalent torque [N·m].
        Te = √( (kb·M)² + (kt·T)² )
        kb = 1.5  fatigue stress concentration factor (keyway, ASME B17.1)
        kt = 1.0  torsional stress concentration (no shock default)
        ✓ Was correct in original — no formula change.
        """
        return math.sqrt((kb * moment) ** 2 + (kt * torque) ** 2)

    @staticmethod
    def shaft_diameter(moment: float, torque: float,
                        allowable: float = None) -> float:
        """
        CEMA 375 §4 / ASME DE — Minimum shaft diameter from stress [m].
        d = ( 16·Te / (π·τ_allow) )^(1/3)

        FIX: allowable now read from constants at call time (not baked-in default).
        Original: allowable=STEEL_ALLOWABLE_STRESS evaluated ONCE at class definition.
        After changing constants.py the old default was still 40 MPa.

        Returns diameter in metres.
        """
        tau = allowable if allowable is not None else _allowable_stress()
        Te = StructuralStressEngine.equivalent_torque(moment, torque)
        return ((16.0 * Te) / (math.pi * tau)) ** (1.0 / 3.0)

    @staticmethod
    def shaft_diameter_deflection(radial_load_N: float,
                                   overhang_A_m: float = 0.080,
                                   span_B_m: float = 0.400) -> float:
        """
        CEMA 375 §4 / CEMA Pulley Standard — Minimum shaft diameter
        from deflection limit [m].

        Max allowable slope at pulley bushing: α_max = 0.0015 in/in
        (dimensionless — same value in m/m).

        From simply-supported beam with point loads at bushing seats:
          α = R·A·(B²-A²) / (6·E·I·B)  at bushing location
        Solving for I = π·d⁴/64:
          d = [ 64·R·A·(B²-A²) / (6·E·B·α_max·π) ]^(1/4)

        Args:
            radial_load_N  : total radial load at head shaft [N] = T1+T2+T3+pulley_wt
            overhang_A_m   : distance from bearing to pulley face [m], default 80mm
            span_B_m       : bearing-to-bearing span [m], default 400mm
        """
        E = _shaft_E()
        alpha_max = _cema_max_slope()
        R = max(radial_load_N, 1.0)
        A = max(overhang_A_m, 0.001)
        B = max(span_B_m, 0.001)
        numer = 64.0 * R * A * (B ** 2 - A ** 2)
        denom = 6.0 * E * B * alpha_max * math.pi
        return (numer / denom) ** 0.25

    @staticmethod
    def shaft_diameter_governing(moment: float, torque: float,
                                  radial_load_N: float,
                                  overhang_A_m: float = 0.080,
                                  span_B_m: float = 0.400,
                                  allowable: float = None) -> dict:
        """
        CEMA 375 §4 — Governing shaft diameter [m]: larger of stress or deflection.

        Returns dict with both diameters, governing criterion, and mm values.
        This is the method callers should use for final shaft sizing.
        """
        d_stress   = StructuralStressEngine.shaft_diameter(moment, torque, allowable)
        d_deflect  = StructuralStressEngine.shaft_diameter_deflection(
                         radial_load_N, overhang_A_m, span_B_m)
        d_govern   = max(d_stress, d_deflect)
        governed_by = "stress" if d_stress >= d_deflect else "deflection (CEMA 0.0015 in/in)"

        return {
            "d_stress_m":    round(d_stress,  5),
            "d_deflect_m":   round(d_deflect, 5),
            "d_governing_m": round(d_govern,  5),
            "d_stress_mm":   round(d_stress  * 1000, 1),
            "d_deflect_mm":  round(d_deflect * 1000, 1),
            "d_governing_mm":round(d_govern  * 1000, 1),
            "governed_by":   governed_by,
        }

    # ── Buckets ───────────────────────────────────────────────────────────────

    @staticmethod
    def bucket_thickness(bucket_load_N: float,
                          bucket_width_mm: float = 200.0,
                          allowable_stress: float = 140e6) -> float:
        """
        CEMA 375 §7 — Minimum bucket back-plate thickness [mm].

        FIX: original formula sqrt(F/σ)×1000 assumed a 1m-wide plate strip.
        Corrected: t = sqrt( F / (σ · w) ) × 1000
        where w = bucket_width_mm / 1000 [m] is the actual plate width.

        CEMA 375 §7 minimums enforced:
          Light duty  (load < 50 N):  3 mm min
          Standard    (load < 200 N): 4 mm min
          Heavy duty  (load ≥ 200 N): 5 mm min

        allowable_stress: 140 MPa is correct for mild steel plate in bending.
        """
        w_m = max(bucket_width_mm, 50.0) / 1000.0
        t_m = math.sqrt(bucket_load_N / (allowable_stress * w_m))
        t_mm = t_m * 1000.0

        # CEMA 375 §7 minimums
        if bucket_load_N < 50:
            t_min = 3.0
        elif bucket_load_N < 200:
            t_min = 4.0
        else:
            t_min = 5.0

        return max(t_mm, t_min)

    # ── Pulleys ───────────────────────────────────────────────────────────────

    @staticmethod
    def pulley_shell_thickness(diameter_m: float) -> float:
        """
        CEMA Pulley Standard — Pulley shell thickness [m].

        FIX: updated to match CEMA Pulley Standard formula:
          t = D/100 + 6mm
        Original formula (0.02·D + 0.004) gave ~27% thicker shell.

        Returns thickness in metres.
        """
        return (diameter_m / 100.0) + 0.006

    # ── Casing ────────────────────────────────────────────────────────────────

    @staticmethod
    def casing_plate_thickness(belt_width_mm: float,
                                bulk_density_kgm3: float = 1000.0,
                                height_m: float = 0.0) -> float:
        """
        CEMA 375 §7 — Casing plate thickness [m].

        FIX: original used height as the only input. CEMA 375 §7 bases
        casing thickness on belt/casing width and material bulk pressure.

        CEMA 375 §7 minimums:
          Light  (belt ≤ 200mm, ρ < 800 kg/m³):  3 mm
          Standard (belt ≤ 450mm, ρ < 1500 kg/m³): 5 mm
          Heavy  (belt > 450mm or ρ ≥ 1500 kg/m³): 8 mm

        Height is accepted as an optional secondary factor for very tall
        elevators (>40m) where wind/thermal loading may govern.
        """
        # CEMA §7 width/density matrix
        if belt_width_mm <= 200 and bulk_density_kgm3 < 800:
            t_mm = 3.0
        elif belt_width_mm <= 450 and bulk_density_kgm3 < 1500:
            t_mm = 5.0
        else:
            t_mm = 8.0

        # Height adjustment: add 1mm per 20m above 20m (tall elevator loading)
        if height_m > 20:
            t_mm += (height_m - 20) / 20.0

        return max(t_mm, 3.0) / 1000.0

    # ── Bearings ─────────────────────────────────────────────────────────────

    @staticmethod
    def bearing_l10(C: float, P: float, n_rpm: float) -> float:
        """
        ISO 281 — Bearing L10 life in HOURS.

        FIX: original returned (C/P)³ which is L10 in MILLIONS of revolutions.
        Must divide by (60 × n) to get hours.
          L10 [hours] = (C/P)³ × 10⁶ / (60 × n)

        Args:
            C      : basic dynamic load rating [N]
            P      : equivalent dynamic bearing load [N]
            n_rpm  : shaft speed [rpm]

        Returns L10 in hours.
        """
        L10_Mrev = (C / max(P, 1.0)) ** 3
        return L10_Mrev * 1e6 / (60.0 * max(n_rpm, 1.0))

    @staticmethod
    def bearing_l10_revolutions(C: float, P: float) -> float:
        """
        ISO 281 — Bearing L10 life in millions of revolutions (raw value).
        Preserved for callers that need the Mrev form.
        """
        return (C / max(P, 1.0)) ** 3

    @staticmethod
    def bearing_life_assessment(L10_hours: float) -> str:
        """
        CEMA 375 §4 — Qualitative bearing life assessment.
          < 20,000 h  : Insufficient — upgrade bearing or reduce load
          20,000–40,000 h : Acceptable for intermittent/light-continuous duty
          40,000–80,000 h : Good for continuous industrial duty
          > 80,000 h  : Excellent — standard for 24/7 heavy industry
        """
        if L10_hours < 20000:
            return f"INSUFFICIENT ({L10_hours:.0f} h) — upgrade bearing or reduce shaft load"
        elif L10_hours < 40000:
            return f"ACCEPTABLE ({L10_hours:.0f} h) — suitable for ≤16h/day operation"
        elif L10_hours < 80000:
            return f"GOOD ({L10_hours:.0f} h) — suitable for continuous 24/7 duty"
        else:
            return f"EXCELLENT ({L10_hours:.0f} h) — exceeds standard requirements"
