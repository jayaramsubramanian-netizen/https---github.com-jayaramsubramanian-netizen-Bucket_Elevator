"""
VECTRIX™ — Dynamic Load Engine
Aligned with CEMA No. 375-2017 §4

CHANGES FROM ORIGINAL
─────────────────────
1. startup_tension(): default factor 2.2 → imports DEFAULT_STARTUP_FACTOR
   from constants.py (2.0 belt / 2.5 chain). Hardcoded 2.2 was inconsistent.

2. shock_loaded_tension() REMOVED as standalone multiplier.
   CEMA 375 §4 does not define a separate shock factor — shock loads are
   absorbed into the service/startup factor. Keeping both and applying
   sequentially over-specified the belt by 2.2 × 1.35 = 2.97×.
   Replaced with shock_load_check() which warns when startup factor
   already covers shock, and advises when explicit shock analysis is needed
   (e.g. jammed-bucket scenario on chain elevators).

3. chain_tension(): CRITICAL BUG FIXED — dimensionally wrong.
   Original: mass × g × height × factor  → gives N·m (energy), not N (force)
   CEMA 375 §4: T1 = (G [kg/s] × H [m] × g) / v [m/s]
   Fixed formula returns correct tension in Newtons.

4. transient_power() removed — duplicate of startup_tension() logic.
   startup_power() replaces it with correct naming and constant import.

5. Added: belt_catenary_tension() — additional tension component from
   belt/bucket self-weight on carrying run (CEMA 375 §4, T2 component).
"""

import math
from constants import (
    GRAVITY,
    DEFAULT_STARTUP_FACTOR,
    DEFAULT_SERVICE_FACTOR,
    DEFAULT_SERVICE_FACTOR_CHAIN,
)


class DynamicLoadEngine:

    @staticmethod
    def startup_tension(running_tension: float,
                        startup_factor: float = None) -> float:
        """
        CEMA 375 §4 — Peak tension during startup [N].
        startup_factor: 1.5–2.0 for belt, 2.0–2.5 for chain.
        Defaults to DEFAULT_STARTUP_FACTOR from constants.py.
        """
        factor = startup_factor if startup_factor is not None else DEFAULT_STARTUP_FACTOR
        return running_tension * factor

    @staticmethod
    def shock_load_check(startup_factor: float,
                          elevator_type: str = "belt") -> dict:
        """
        CEMA 375 §4 — Shock load advisory (replaces shock_loaded_tension).

        CEMA 375 does NOT define a separate shock multiplier. Shock loads
        (bucket jam, sudden restart) are managed through:
          - Adequate startup factor (covers normal shock)
          - Shear-pin or torque-limiter on chain elevators for jam shock
          - Backstop device to prevent rollback shock

        Returns advisory dict — does NOT return a tension multiplier.
        """
        adequate_for_shock = startup_factor >= 2.0
        return {
            "startup_factor": startup_factor,
            "adequate_for_normal_shock": adequate_for_shock,
            "recommendation": (
                "Startup factor ≥ 2.0 covers normal shock loads. "
                "For chain elevators, fit shear-pin or torque-limiter "
                "for bucket-jam protection (CEMA 375 §4)."
                if adequate_for_shock else
                "Startup factor < 2.0 — consider torque-limiter and "
                "backstop device for shock protection (CEMA 375 §4)."
            ),
            "backstop_required": elevator_type == "chain",
        }

    @staticmethod
    def belt_tension(power_kw: float, speed_mps: float) -> float:
        """
        CEMA 375 §4 — Effective belt tension from drive power [N].
        F_eff = P [W] / v [m/s]
        ✓ Formula was correct in original — no change.
        """
        return (power_kw * 1000.0) / max(speed_mps, 0.001)

    @staticmethod
    def material_tension(capacity_tph: float,
                          height_m: float,
                          speed_mps: float) -> float:
        """
        CEMA 375 §4 — T1: tension due to material weight in carrying run [N].
        FIXED: original chain_tension() formula was dimensionally wrong.

        Original:  T1 = mass × g × height × factor   → N·m (energy, WRONG)
        Correct:   T1 = (G [kg/s] × H [m] × g) / v [m/s]  → N

        Derivation:
          Power to lift = G × g × H  [W]
          Effective tension = Power / v = G × g × H / v  [N]
        """
        G_kgs = capacity_tph * 1000.0 / 3600.0     # mass flow [kg/s]
        return G_kgs * GRAVITY * height_m / max(speed_mps, 0.001)

    @staticmethod
    def belt_catenary_tension(belt_width_mm: float,
                               bucket_volume_L: float,
                               bucket_spacing_m: float,
                               height_m: float,
                               PIW_kgm2: float = 1.5) -> float:
        """
        CEMA 375 §4 — T2: tension from up-side belt and bucket self-weight [N].
        T2 = (belt_mass/m + bucket_mass/m) × H × g

        PIW_kgm2: belt weight per unit area [kg/m²], default 1.5 for elevator belt.
        Bucket weight estimated as 1.5 kg/L of bucket volume (steel construction).
        """
        belt_mass_per_m   = (belt_width_mm / 1000.0) * PIW_kgm2       # kg/m
        bucket_mass_per_m = (bucket_volume_L * 1.5) / bucket_spacing_m # kg/m
        return (belt_mass_per_m + bucket_mass_per_m) * height_m * GRAVITY

    @staticmethod
    def slack_side_tension(T1: float, T2: float,
                            K_takeup: float = 0.7) -> float:
        """
        CEMA 375 §4 — T3: minimum slack-side tension to prevent belt slip [N].
        T3 = (T1 + T2) × K_takeup
        K_takeup: 0.5 screw take-up, 0.7 gravity take-up, 0.9 spring take-up.
        """
        return (T1 + T2) * K_takeup

    @staticmethod
    def acceleration_torque(inertia: float,
                             angular_acceleration: float) -> float:
        """
        Torque required to accelerate rotating mass [N·m].
        T = I × α
        ✓ Formula was correct in original — no change.
        """
        return inertia * angular_acceleration

    @staticmethod
    def startup_power(power_kw: float,
                       startup_factor: float = None) -> float:
        """
        CEMA 375 §4 — Peak power demand during startup [kW].
        Replaces transient_power() which was a duplicate of startup_tension logic.
        """
        factor = startup_factor if startup_factor is not None else DEFAULT_STARTUP_FACTOR
        return power_kw * factor
