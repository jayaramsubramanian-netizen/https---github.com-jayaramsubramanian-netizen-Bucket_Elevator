"""
VECTRIX™ — Dynamic Load Engine
CEMA No. 375-2017 §4

v1.1.0 — Structural & Chain Dynamics Hardening
─────────────────────────────────────────────────────────────────────────────
1. FIXED    belt_catenary_tension()
            v1.0: bucket mass estimated as volume_L × 1.5 kg — inaccurate.
            v1.1: explicit bucket_mass_kg required; must come from bucket DB.
            PIW_kgm2 default corrected: 1.5 → 8.0 kg/m².
            Real elevator EP belting: 4–20 kg/m²; 1.5 was dangerously low
            and would underestimate T2, bearing load, and shaft load.

2. NEW      chain_tension() — dedicated chain elevator tension model.
            Includes strand self-weight and polygon-effect dynamic tension
            (CEMA 375 §4, chord-arc engagement relationship, z teeth).

3. NEW      startup_dynamic_tension() — integrates equivalent rotating inertia
            into peak startup tension alongside the flat startup factor.
            Returns T_peak, T_inertia_component, T_static_component, and
            the governing value so the caller knows which path controls.

4. NEW      rollback_torque() — backstop sizing torque for gravity rollback.
            Required for all elevators H > 5 m; mandatory for chain elevators
            per CEMA 375 §4.  Accepts T2 self-weight contribution.

5. NEW      euler_eytelwein_check() — belt slip analysis.
            Derives required minimum slack-side tension from T_effective,
            wrap angle, and friction coefficient.  Returns slip_safe flag
            and recommendation when actual T_slack is provided.

6. NEW      effective_tension_summary() — consolidates the tension path
            (T_material + T_self_weight + T_friction → T_effective) to
            prevent double-counting with belt_tension().

7. DEPRECATED bucket_mass_from_volume() — retained for backward compat;
               emits DeprecationWarning.  A 10 L bucket can weigh 4–12 kg;
               the volume × 1.5 proxy is unreliable across bucket series.

8. CLARIFIED belt_tension() — docstring now explicitly states this is a
             cross-check from total drive power, not additive with
             material_tension() or effective_tension_summary().
─────────────────────────────────────────────────────────────────────────────
"""

import math
import warnings
from typing import Optional

try:
    from .constants import (
        GRAVITY,
        DEFAULT_STARTUP_FACTOR,
        DEFAULT_SERVICE_FACTOR,
        DEFAULT_SERVICE_FACTOR_CHAIN,
    )
except ImportError:
    from constants import (
        GRAVITY,
        DEFAULT_STARTUP_FACTOR,
        DEFAULT_SERVICE_FACTOR,
        DEFAULT_SERVICE_FACTOR_CHAIN,
    )


# ── CEMA 375 §4 Tension Path Architecture ─────────────────────────────────────
#
# To prevent the double-counting risk raised in the audit, the tension path is:
#
#   FORWARD CALCULATION (build up from loads):
#     T_material   = material_tension()       ← G·g·H / v  [N]
#     T_self_wt    = belt_catenary_tension()  ← (belt + bucket) × H × g  [N]
#     T_friction   = friction_factor × (T_material + T_self_wt)  [N]
#     T_effective  = T_material + T_self_wt + T_friction  [N]
#
#   POWER CROSS-CHECK (from total drive kW):
#     T_check      = belt_tension(P_kw, v)    ← P×1000 / v  [N]
#     (T_check should ≈ T_effective; delta reveals friction losses)
#
#   SLACK SIDE:
#     T3_min       = euler_eytelwein_check()  ← T_eff / (e^μθ − 1)  [N]
#     T3_prelim    = slack_side_tension()     ← (T_eff) × K_takeup  [N]
#
#   TIGHT SIDE (belt rated tension):
#     T1           = T_effective + T3  [N]
#
#   STARTUP PEAK:
#     T_startup    = startup_dynamic_tension() or startup_tension()  [N]
#
#   CHAIN ELEVATORS — use chain_tension() which includes:
#     T_material + T_chain_self_weight + T_polygon_effect
#
#   ⚠ DO NOT add belt_tension() to material_tension() — they are at different
#     levels of analysis.  Use effective_tension_summary() to build T_effective
#     correctly and bell_tension() only as a cross-check of the final result.
# ─────────────────────────────────────────────────────────────────────────────


class DynamicLoadEngine:

    # ── 1. Base running tensions ──────────────────────────────────────────────

    @staticmethod
    def belt_tension(power_kw: float, speed_mps: float) -> float:
        """
        CEMA 375 §4 — Effective belt tension derived from total drive power [N].
        F_eff = P [W] / v [m/s]

        USE AS A CROSS-CHECK ONLY.
        This is the total effective tension back-calculated from power.
        It is NOT additive with material_tension() — both represent T_effective
        at different stages of the same calculation chain.
        Compare this result against effective_tension_summary()["T_effective"]
        to verify friction and loss assumptions.

        Formula was correct in v1.0 — no change.
        """
        return (power_kw * 1000.0) / max(speed_mps, 0.001)

    @staticmethod
    def material_tension(
        capacity_tph: float,
        height_m:     float,
        speed_mps:    float,
    ) -> float:
        """
        CEMA 375 §4 — Effective tension component from material in carrying run [N].

        Derivation:
            Power to lift material: P_mat = G [kg/s] × g × H  [W]
            Effective tension:      T_mat = P_mat / v          [N]

        G [kg/s] = capacity_tph × 1000 / 3600

        Fixed in v1.0 from the original dimensionally-wrong formula
        (mass × g × H × factor → N·m, not N).  No change in v1.1.
        """
        G_kgs = capacity_tph * 1000.0 / 3600.0
        return G_kgs * GRAVITY * height_m / max(speed_mps, 0.001)

    @staticmethod
    def belt_catenary_tension(
        belt_width_mm:    float,
        bucket_mass_kg:   float,
        bucket_spacing_m: float,
        height_m:         float,
        PIW_kgm2:         float = 8.0,
    ) -> float:
        """
        CEMA 375 §4 — T2: self-weight tension of belt and buckets
        on the carrying (ascending) run [N].

        T2 = (belt_mass/m + bucket_mass/m) × H × g

        FIX 1 — Bucket mass (Issue #2 from audit)
        ────────────────────────────────────────────
        v1.0 estimated bucket_mass_per_m = bucket_volume_L × 1.5 / spacing.
        This is unreliable: a 10 L bucket can weigh 4–12 kg depending on
        steel thickness, lip weldment, and bucket series.

        v1.1: bucket_mass_kg is an explicit required argument.
        Source it from the bucket database for the selected series.

        FIX 2 — Belt linear density PIW (Issue #3 from audit)
        ───────────────────────────────────────────────────────
        v1.0 default: 1.5 kg/m² — dangerously low.
        v1.1 default: 8.0 kg/m² — representative of medium EP elevator belt.
        Realistic range by belt construction:
            EP 315/3 (light):      ~6.0 kg/m²
            EP 500/4 (medium):     ~9.5 kg/m²
            EP 630/4 (heavy):     ~12.0 kg/m²
            ST steel cord:        ~15–25 kg/m²
        Always supply PIW_kgm2 from the belt specification, not this default.

        Parameters
        ----------
        belt_width_mm     Belt width [mm]
        bucket_mass_kg    Actual bucket mass from catalogue [kg per bucket]
        bucket_spacing_m  Centreline bucket spacing [m]
        height_m          Elevator lift height [m]
        PIW_kgm2          Belt mass per unit area [kg/m²]
        """
        belt_mass_per_m   = (belt_width_mm / 1000.0) * PIW_kgm2
        bucket_mass_per_m = bucket_mass_kg / max(bucket_spacing_m, 0.001)
        return (belt_mass_per_m + bucket_mass_per_m) * height_m * GRAVITY

    # ── 2. Effective tension summary ──────────────────────────────────────────

    @staticmethod
    def effective_tension_summary(
        capacity_tph:     float,
        height_m:         float,
        speed_mps:        float,
        belt_width_mm:    float,
        bucket_mass_kg:   float,
        bucket_spacing_m: float,
        PIW_kgm2:         float = 8.0,
        friction_factor:  float = 0.05,
    ) -> dict:
        """
        CEMA 375 §4 — Consolidated belt tension analysis.

        Addresses the double-counting risk raised in the audit:
        call this function rather than adding belt_tension() and
        material_tension() directly.

        Tension path
        ────────────
        T_material   = material_tension()
        T_self_wt    = belt_catenary_tension()
        T_friction   = friction_factor × (T_material + T_self_wt)
        T_effective  = T_material + T_self_wt + T_friction

        friction_factor covers losses from bearings, belt flexing around boot
        pulley, seal drag, and minor incidental loads.  Typical: 0.03–0.07.
        Default 0.05 is appropriate for preliminary design.

        Compare T_effective against belt_tension(P_total, v) to verify that
        drive power allows for the assumed friction losses.

        Returns
        -------
        {
            "T_material":    float [N],
            "T_self_weight": float [N],
            "T_friction":    float [N],
            "T_effective":   float [N],
            "friction_factor": float,
            "note": str,
        }
        """
        T_mat  = DynamicLoadEngine.material_tension(capacity_tph, height_m, speed_mps)
        T_swt  = DynamicLoadEngine.belt_catenary_tension(
            belt_width_mm, bucket_mass_kg, bucket_spacing_m, height_m, PIW_kgm2
        )
        T_fric = friction_factor * (T_mat + T_swt)
        T_eff  = T_mat + T_swt + T_fric

        return {
            "T_material":     round(T_mat,  1),
            "T_self_weight":  round(T_swt,  1),
            "T_friction":     round(T_fric, 1),
            "T_effective":    round(T_eff,  1),
            "friction_factor": friction_factor,
            "note": (
                "Cross-check: belt_tension(P_total_kw, speed_mps) "
                "should ≈ T_effective.  Delta reveals unaccounted losses."
            ),
        }

    # ── 3. Traction analysis ──────────────────────────────────────────────────

    @staticmethod
    def slack_side_tension(
        T1: float,
        T2: float,
        K_takeup: float = 0.7,
    ) -> float:
        """
        CEMA 375 §4 — T3: minimum slack-side tension from take-up type [N].
        T3 = (T1 + T2) × K_takeup

        K_takeup by take-up type:
            0.50 — screw take-up (fixed position)
            0.70 — gravity take-up (recommended for bucket elevators)
            0.90 — spring take-up (high-tension constant-force)

        For rigorous analysis, use euler_eytelwein_check() which derives
        the theoretical minimum T3 from wrap angle and friction coefficient.
        This K_takeup method remains appropriate for preliminary sizing.

        Formula correct in v1.0 — no change.
        """
        return (T1 + T2) * K_takeup

    @staticmethod
    def euler_eytelwein_check(
        T_effective: float,
        T_slack:     Optional[float] = None,
        wrap_angle_deg: float = 180.0,
        mu:          float = 0.35,
    ) -> dict:
        """
        CEMA 375 §4 — Belt slip analysis (Euler-Eytelwein traction equation).

        Theory:  T1 / T2 ≤ e^(μ × θ)
        Required:  T2_min = T_effective / (e^(μθ) − 1)

        Friction coefficients μ by lagging:
            Bare steel pulley:       0.20–0.25
            Rubber lagging (dry):    0.35–0.40
            Rubber lagging (wet):    0.25–0.30
            Ceramic lagging (wet):   0.35–0.45

        Standard wrap angles:
            Single reduction, no snub: 180° (π rad)
            With snub pulley:          200–220°

        Parameters
        ----------
        T_effective    Total effective tension = P_kw × 1000 / v  [N]
        T_slack        Actual slack-side tension from take-up [N].
                       If provided, returns slip_safe flag and recommendation.
        wrap_angle_deg Drive pulley wrap angle [°]
        mu             Belt–pulley friction coefficient

        Returns
        -------
        {
            "T2_minimum":   float   Minimum slack-side tension to prevent slip [N]
            "euler_ratio":  float   e^(μθ) — transmission capacity factor [-]
            "mu":           float
            "wrap_deg":     float
            "T2_actual":    float   (only if T_slack provided)
            "slip_safe":    bool    (only if T_slack provided)
            "recommendation": str  (only if T_slack provided)
        }
        """
        theta       = math.radians(wrap_angle_deg)
        euler_ratio = math.exp(mu * theta)
        T2_min      = T_effective / (euler_ratio - 1.0)

        result: dict = {
            "T2_minimum":  round(T2_min,      1),
            "euler_ratio": round(euler_ratio,  4),
            "mu":          mu,
            "wrap_deg":    wrap_angle_deg,
        }

        if T_slack is not None:
            slip_safe = T_slack >= T2_min
            result["T2_actual"]  = round(T_slack, 1)
            result["slip_safe"]  = slip_safe
            result["recommendation"] = (
                "Adequate traction — belt will not slip at drive pulley."
                if slip_safe else
                f"SLIP RISK: T_slack {T_slack:.0f} N < T2_min {T2_min:.0f} N. "
                "Increase take-up tension, add snub pulley to increase wrap, "
                "or upgrade lagging to improve μ (CEMA 375 §4)."
            )

        return result

    # ── 4. Startup and dynamic loads ──────────────────────────────────────────

    @staticmethod
    def startup_tension(
        running_tension: float,
        startup_factor:  Optional[float] = None,
    ) -> float:
        """
        CEMA 375 §4 — Peak belt tension during full-speed startup [N].
        Flat factor applied to running tension.

        startup_factor range: 1.5–2.0 belt, 2.0–2.5 chain.
        Defaults to DEFAULT_STARTUP_FACTOR from constants.py.

        For a more rigorous model that accounts for rotating inertia,
        see startup_dynamic_tension().
        """
        factor = startup_factor if startup_factor is not None else DEFAULT_STARTUP_FACTOR
        return running_tension * factor

    @staticmethod
    def startup_dynamic_tension(
        T_running:            float,
        mass_equivalent_kg:   float,
        belt_speed_mps:       float,
        startup_time_s:       float,
        startup_factor:       Optional[float] = None,
    ) -> dict:
        """
        CEMA 375 §4 — Peak startup tension with inertia contribution [N].

        Integrates rotating inertia into the startup model rather than
        relying solely on a flat multiplier.

        Inertia model
        ─────────────
        The belt-equivalent inertia of all rotating elements (motor, gearbox,
        head shaft, belt+buckets, material column) referred to the belt:

            T_inertia = m_equivalent × a
                      = m_equivalent × belt_speed_mps / startup_time_s

        m_equivalent is the total equivalent translating mass at the belt
        plane, derived from:
            m_eq = Σ(WR² / r_pulley²) for each rotating element [kg]

        Two governing approaches (CEMA §4):
            T_peak_factor   = T_running × startup_factor
            T_peak_inertia  = T_running + T_inertia

        The higher value governs.  At short startup times (direct-on-line
        start), inertia often governs.  With VFD, startup_factor governs.

        Parameters
        ----------
        T_running           Steady-state effective tension [N]
        mass_equivalent_kg  Total rotating mass referred to belt plane [kg].
                            Build from: Σ(I_element / r_head²) for each shaft.
        belt_speed_mps      Rated belt speed [m/s]
        startup_time_s      Time to reach full speed [s].
                            DOL: 1–3 s; VFD ramped: 5–30 s.
        startup_factor      Flat multiplier (default: DEFAULT_STARTUP_FACTOR)

        Returns
        -------
        {
            "T_inertia":          float  [N]   inertia tension component
            "T_peak_inertia":     float  [N]   T_running + T_inertia
            "T_peak_factor":      float  [N]   T_running × startup_factor
            "T_peak_governing":   float  [N]   max of both
            "governing_method":   str          "inertia" | "factor"
            "startup_factor":     float
            "startup_time_s":     float
        }
        """
        factor     = startup_factor if startup_factor is not None else DEFAULT_STARTUP_FACTOR
        accel      = belt_speed_mps / max(startup_time_s, 0.1)
        T_inertia  = mass_equivalent_kg * accel
        T_pk_iner  = T_running + T_inertia
        T_pk_fact  = T_running * factor
        governing  = max(T_pk_iner, T_pk_fact)

        return {
            "T_inertia":        round(T_inertia, 1),
            "T_peak_inertia":   round(T_pk_iner, 1),
            "T_peak_factor":    round(T_pk_fact, 1),
            "T_peak_governing": round(governing,  1),
            "governing_method": "inertia" if T_pk_iner >= T_pk_fact else "factor",
            "startup_factor":   factor,
            "startup_time_s":   startup_time_s,
        }

    @staticmethod
    def acceleration_torque(
        inertia: float,
        angular_acceleration: float,
    ) -> float:
        """
        Torque to accelerate rotating mass [N·m].  T = I × α.
        Formula correct in v1.0 — no change.
        """
        return inertia * angular_acceleration

    @staticmethod
    def startup_power(
        power_kw:      float,
        startup_factor: Optional[float] = None,
    ) -> float:
        """
        CEMA 375 §4 — Peak drive power during startup [kW].
        Replaces v1.0 transient_power() (duplicate of startup_tension logic).
        """
        factor = startup_factor if startup_factor is not None else DEFAULT_STARTUP_FACTOR
        return power_kw * factor

    @staticmethod
    def shock_load_check(
        startup_factor: float,
        elevator_type:  str = "belt",
    ) -> dict:
        """
        CEMA 375 §4 — Shock load advisory.

        CEMA 375 does not define a separate shock multiplier.  Shock loads
        (bucket jam, sudden restart, rollback arrest) are managed through:
          • Adequate startup factor (covers normal shock)
          • Shear-pin or torque-limiter for jam-shock on chain elevators
          • Backstop device to prevent rollback shock

        Applying both shock_factor and startup_factor sequentially would
        overspecify by 2.0 × 1.35 = 2.7× — the error removed in v1.0.

        Returns advisory dict; does NOT return a tension value.
        """
        adequate = startup_factor >= 2.0
        return {
            "startup_factor":            startup_factor,
            "adequate_for_normal_shock": adequate,
            "backstop_required":         elevator_type == "chain",
            "recommendation": (
                "Startup factor ≥ 2.0 covers normal shock loads. "
                "For chain elevators, fit shear-pin or torque-limiter "
                "for bucket-jam protection (CEMA 375 §4)."
                if adequate else
                "Startup factor < 2.0 — consider torque-limiter and "
                "backstop device for shock protection (CEMA 375 §4)."
            ),
        }

    # ── 5. Chain-specific dynamics ────────────────────────────────────────────

    @staticmethod
    def chain_tension(
        capacity_tph:        float,
        height_m:            float,
        speed_mps:           float,
        chain_mass_kg_per_m: float,
        sprocket_teeth:      int   = 8,
    ) -> dict:
        """
        CEMA 375 §4 — Chain elevator effective tension [N].

        Three additive components:

        T_material  (same as belt)
        ───────────────────────────
        T_mat = G·g·H / v

        T_chain_weight
        ───────────────────────────
        T_cwt = m_chain × H × g
        (ascending strand self-weight; return strand assumed approximately
        balanced so net chain weight contribution = carrying-run only)

        T_polygon — Sprocket polygon effect
        ───────────────────────────────────
        Chain engages sprocket teeth at discrete chord positions.  This causes
        a velocity variation that creates a dynamic tension fluctuation.

        Speed ratio:  v_max / v_avg = 1 / cos(π / z)
        Polygon tension: ΔT = m_chain × v² × (1/cos(π/z) − 1)

        Polygon factor k = 1/cos(π/z) − 1:
            z = 6:  k = 0.155  (15.5% — avoid where possible)
            z = 7:  k = 0.109
            z = 8:  k = 0.082  (typical for bucket elevator chain)
            z = 11: k = 0.043

        Parameters
        ----------
        chain_mass_kg_per_m  Total chain assembly weight [kg/m].
                             Includes BOTH strands + connecting links.
                             Typical ranges (double-strand):
                               Light duty (3" pitch):  ~10 kg/m
                               Medium duty (4" pitch): ~20 kg/m
                               Heavy duty (6" pitch):  ~45 kg/m
        sprocket_teeth       Head sprocket tooth count.
                             Minimum 6; 8–11 preferred per CEMA 375 §4.

        Returns
        -------
        {
            "T_material":     float [N],
            "T_chain_weight": float [N],
            "T_polygon":      float [N],
            "T_effective":    float [N],
            "polygon_factor": float [-],
            "sprocket_teeth": int,
        }
        """
        if sprocket_teeth < 6:
            warnings.warn(
                f"sprocket_teeth = {sprocket_teeth} is below the CEMA 375 §4 "
                "minimum of 6.  Polygon effect will cause severe dynamic loading "
                "and premature chain wear.",
                UserWarning,
                stacklevel=2,
            )

        T_mat  = DynamicLoadEngine.material_tension(capacity_tph, height_m, speed_mps)
        T_cwt  = chain_mass_kg_per_m * height_m * GRAVITY
        k_poly = (1.0 / math.cos(math.pi / sprocket_teeth)) - 1.0
        T_poly = chain_mass_kg_per_m * (speed_mps ** 2) * k_poly
        T_eff  = T_mat + T_cwt + T_poly

        return {
            "T_material":     round(T_mat,  1),
            "T_chain_weight": round(T_cwt,  1),
            "T_polygon":      round(T_poly, 1),
            "T_effective":    round(T_eff,  1),
            "polygon_factor": round(k_poly, 4),
            "sprocket_teeth": sprocket_teeth,
        }

    # ── 6. Backstop loads ─────────────────────────────────────────────────────

    @staticmethod
    def rollback_torque(
        capacity_tph:         float,
        height_m:             float,
        speed_mps:            float,
        head_pulley_radius_m: float,
        T_self_weight:        float = 0.0,
    ) -> dict:
        """
        CEMA 375 §4 — Rollback torque at head shaft for backstop sizing [N·m].

        When the drive is removed, the material column in the ascending leg
        creates a gravity-driven rollback force.  The backstop must resist
        the resultant torque at the head shaft.

        M_rollback = (T_material + T_self_weight) × r_head

        Required for:
          • All bucket elevators with H > 5 m (CEMA 375 §4)
          • All chain-type bucket elevators
          • Any elevator handling material with no angle of repose
            (pellets, spherical product, free-flowing powder)

        Parameters
        ----------
        capacity_tph          Design capacity [t/h]
        height_m              Lift height [m]
        speed_mps             Belt/chain speed [m/s]
        head_pulley_radius_m  Head pulley (or sprocket pitch) radius [m]
        T_self_weight         T2 from belt_catenary_tension() or chain_tension()
                              ["T_chain_weight"] [N].  Include for belt/chain
                              self-weight contribution to rollback load.

        Returns
        -------
        {
            "T_material":    float [N]
            "T_self_weight": float [N]
            "T_total":       float [N]
            "M_rollback":    float [N·m]  ← use this for backstop selection
            "backstop_note": str
        }
        """
        T_mat   = DynamicLoadEngine.material_tension(capacity_tph, height_m, speed_mps)
        T_total = T_mat + T_self_weight
        M_roll  = T_total * head_pulley_radius_m

        return {
            "T_material":    round(T_mat,    1),
            "T_self_weight": round(T_self_weight, 1),
            "T_total":       round(T_total,  1),
            "M_rollback":    round(M_roll,   1),
            "backstop_note": (
                f"Select backstop rated ≥ {M_roll * 1.25:.0f} N·m "
                f"(M_rollback × 1.25 safety factor)."
            ),
        }

    # ── 7. Deprecated ─────────────────────────────────────────────────────────

    @staticmethod
    def bucket_mass_from_volume(
        bucket_volume_L:      float,
        steel_density_factor: float = 1.5,
    ) -> float:
        """
        DEPRECATED since v1.1.0.

        Estimates bucket mass as volume_L × 1.5 kg.
        A 10 L bucket can weigh 4–12 kg depending on steel gauge, lip weld,
        and bucket series.  This proxy is unreliable for structural calculations.

        Use actual catalogue bucket_mass_kg from the bucket database instead.
        """
        warnings.warn(
            "bucket_mass_from_volume() is deprecated. "
            "Use the actual bucket mass from the VECTRIX bucket database "
            "(catalogue weight [kg], not a volume estimate). "
            "A 10 L bucket can weigh 4–12 kg — the 1.5 kg/L proxy is "
            "unreliable and will produce incorrect T2 and shaft loads.",
            DeprecationWarning,
            stacklevel=2,
        )
        return bucket_volume_L * steel_density_factor