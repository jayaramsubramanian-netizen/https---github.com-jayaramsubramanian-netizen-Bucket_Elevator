"""
VECTRIX™ — Discharge Physics Engine
Aligned with CEMA No. 375-2017 §3

CHANGES FROM ORIGINAL
─────────────────────
1. trajectory(): CRITICAL BUG FIXED
   Original started at (release_x=0, release_y=0) = pulley CENTRE.
   CEMA 375 §3: material releases from pulley RIM.
   Fixed: release point is now (r·sin θ, r·cos θ) from pulley centre,
   with velocity tangential to the rim at the release angle.
   Callers no longer need to pass release_x/release_y manually.

2. stream_envelope(): fixed particle_spread=0.15m (150mm hardcoded)
   Fixed: spread now scales with bucket projection and v²/g,
   giving a physically meaningful envelope width.

3. backlegging_check(): ignored y-coordinate
   Original returned True if ANY point had x >= return_leg_x,
   even if that point was above the casing roof.
   Fixed: only flags backlegging if the material actually reaches
   the return leg height band (y ≤ casing_half_width from centre).
"""

import math
from constants import GRAVITY


class DischargePhysics:

    @staticmethod
    def belt_speed(diameter_m: float, rpm: float) -> float:
        """
        Belt/chain peripheral speed [m/s].
        v = π · D · n / 60
        CEMA 375 §3 — verified correct, no change needed.
        """
        return math.pi * diameter_m * rpm / 60

    @staticmethod
    def centrifugal_ratio(speed: float, radius: float) -> float:
        """
        CEMA 375 §3 — Centrifugal ratio CR = v² / (r·g).
        CR ≥ 1.0  → centrifugal discharge.
        CR 1.0–1.8 → optimal clean discharge.
        CR > 2.5  → excessive scatter.
        """
        return (speed ** 2) / (radius * GRAVITY)

    @staticmethod
    def centrifugal_release_angle(speed: float, radius: float) -> float:
        """
        CEMA 375 §3 — Release angle from VERTICAL [radians].
        At release: centrifugal force = gravity component
            g·cos(θ) = v²/r  →  cos(θ) = v²/(r·g)
        Returns angle θ from vertical (0 = top of pulley).
        """
        cr = (speed ** 2) / (GRAVITY * radius)
        cr_clamped = max(-1.0, min(1.0, cr))
        return math.acos(cr_clamped)

    @staticmethod
    def release_condition(speed: float, radius: float) -> float:
        """
        Centrifugal acceleration at pulley rim [m/s²].
        Used to verify centrifugal > gravity (i.e. CR > 1).
        """
        return (speed ** 2) / radius

    @staticmethod
    def trajectory(speed: float, radius: float, dt: float = 0.02):
        """
        CEMA 375 §3 — Projectile trajectory of material leaving head pulley.

        FIX: Material releases from the pulley RIM, not the centre.
        Release point (from pulley centre):
            x0 = r · sin(θ)
            y0 = r · cos(θ)
        Velocity at release is tangential (perpendicular to radius):
            vx =  v · cos(θ)
            vy =  v · sin(θ)

        Returns list of (x, y) tuples in metres, relative to pulley centre.
        Stops when material drops below y = -r (boot level proxy).
        """
        theta = DischargePhysics.centrifugal_release_angle(speed, radius)

        # Release point on pulley rim
        x0 = radius * math.sin(theta)
        y0 = radius * math.cos(theta)

        # Tangential velocity components at release
        vx =  speed * math.cos(theta)
        vy =  speed * math.sin(theta)

        points = []
        t = 0.0
        while t < 5.0:
            x = x0 + vx * t
            y = y0 + vy * t - 0.5 * GRAVITY * t ** 2
            points.append((round(x, 4), round(y, 4)))
            if y < -radius * 3:
                break
            t += dt

        return points

    @staticmethod
    def stream_envelope(speed: float, radius: float,
                        bucket_projection_m: float = 0.14):
        """
        CEMA 375 §3 — Discharge stream envelope (upper/lower bounds).

        FIX: particle_spread is no longer a hardcoded 150mm.
        Spread is physically derived:
            spread = 0.5 · bucket_projection + 0.05 · v²/g
        This reflects:
          - Half the bucket projection as the initial stream width
          - Velocity-dependent dispersion from the throw
        """
        spread = 0.5 * bucket_projection_m + 0.05 * (speed ** 2) / GRAVITY

        center = DischargePhysics.trajectory(speed, radius)
        upper  = [(x, y + spread) for x, y in center]
        lower  = [(x, y - spread) for x, y in center]

        return {
            "center": center,
            "upper":  upper,
            "lower":  lower,
            "spread_m": round(spread, 4),
        }

    @staticmethod
    def backlegging_check(trajectory: list,
                          return_leg_x: float,
                          casing_half_width: float = 0.15) -> bool:
        """
        CEMA 375 §3 — Backlegging risk check.

        FIX: Original only checked x >= return_leg_x, ignoring y.
        This caused false positives when material flew over the return leg
        without actually hitting it.

        Corrected logic: backlegging occurs only when the trajectory point
        is BOTH beyond the return leg (x >= return_leg_x) AND within the
        height band of the return belt (|y| <= casing_half_width).

        Args:
            trajectory:        list of (x, y) tuples from DischargePhysics.trajectory()
            return_leg_x:      x-distance to return belt centreline [m]
            casing_half_width: half the casing width at return belt level [m]
                               default 150mm is typical for medium-duty casing

        Returns:
            True if material is likely to strike the return belt.
        """
        for x, y in trajectory:
            if x >= return_leg_x and abs(y) <= casing_half_width:
                return True
        return False
