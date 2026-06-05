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
    from constants import STEEL_ALLOWABLE_STRESS
    return STEEL_ALLOWABLE_STRESS

def _cema_max_slope() -> float:
    from constants import CEMA_MAX_SHAFT_SLOPE
    return CEMA_MAX_SHAFT_SLOPE

def _shaft_E() -> float:
    from constants import SHAFT_E_PA
    return SHAFT_E_PA

def _gravity() -> float:
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