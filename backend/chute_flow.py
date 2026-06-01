"""
VECTRIX™ — Chute Flow Engine
Aligned with CEMA No. 375-2017 §5

CHANGES FROM ORIGINAL
─────────────────────
1. chute_angle(): fixed +10° regardless of material.
   CEMA 375 §5: angle margin above repose depends on abrasiveness.
   Abrasive materials (abr_code ≥ 5) need shallower angle (less margin)
   to limit wear on chute lining. Added abr_code-aware margin.

2. impact_force(): used absolute velocity v instead of velocity change Δv.
   For angled chutes, Δv = v · sin(impact_angle).
   Fixed: accepts optional impact_angle_deg parameter.

3. ADDED: discharge_chute_geometry() — CEMA 375 §5 head chute design.
   Calculates back-plate angle, spout width, and stream interception
   using trajectory data from DischargePhysics.trajectory().
   This was entirely missing from the original.

4. ADDED: chute_wear_rate() — CEMA 375 §5 / CEMA 550 abrasion index.
   Estimates relative wear rate on chute lining based on material
   abrasive code, velocity, and impact angle.
"""

import math
from constants import GRAVITY


class ChuteFlowEngine:

    @staticmethod
    def inlet_velocity(capacity_tph: float,
                        density_kgm3: float,
                        inlet_area_m2: float) -> float:
        """
        CEMA 375 §5 — Material velocity at boot inlet [m/s].
        v = Q_vol / A = (G [kg/s] / ρ) / A
        ✓ Formula was correct in original — no change.
        """
        mass_flow      = capacity_tph * 1000.0 / 3600.0   # kg/s
        volumetric_flow = mass_flow / density_kgm3         # m³/s
        return volumetric_flow / inlet_area_m2

    @staticmethod
    def chute_angle(material) -> float:
        """
        CEMA 375 §5 — Minimum chute angle [degrees].
        Must exceed angle of repose by a margin that depends on abrasiveness.

        FIX: original used fixed +10°. CEMA 375 §5 states:
          - Non/mildly abrasive (abr_code 1–3): +15° margin (steeper = faster flow)
          - Abrasive (abr_code 4–5): +10° margin (balance flow vs wear)
          - Highly abrasive (abr_code 6–7): +5° margin (minimise high-velocity
            impact on lining; use ceramic or AR-plate liner)

        material.repose_angle_deg : float
        material.abr_code         : int 1–7 (CEMA 550 §A-1); defaults to 3
        """
        abr = getattr(material, "abr_code", 3)
        if abr <= 3:
            margin = 15
        elif abr <= 5:
            margin = 10
        else:
            margin = 5
        return material.repose_angle_deg + margin

    @staticmethod
    def chute_residence_time(length_m: float, velocity_mps: float) -> float:
        """
        Time material spends in chute [s].
        ✓ Formula was correct in original — no change.
        """
        return length_m / max(velocity_mps, 0.001)

    @staticmethod
    def impact_force(mass_flow_rate_kgs: float,
                      velocity_mps: float,
                      impact_angle_deg: float = 90.0) -> float:
        """
        CEMA 375 §5 — Impact force on chute wall [N].

        FIX: original used absolute velocity. CEMA uses velocity change:
          F = ṁ × Δv = ṁ × v · sin(impact_angle)

        For a chute where material arrives at velocity v and decelerates:
          - impact_angle_deg = 90° → material hits perpendicularly (max force)
          - impact_angle_deg = chute_angle → material hits at chute angle

        impact_angle_deg defaults to 90° (conservative, original behaviour).
        """
        delta_v = velocity_mps * math.sin(math.radians(impact_angle_deg))
        return mass_flow_rate_kgs * delta_v

    @staticmethod
    def blockage_risk(material, chute_angle_deg: float) -> str:
        """
        CEMA 375 §5 / CEMA 550 §A-10 — Blockage risk assessment.
        cohesion threshold 0.5 = MODERATE per CEMA 550 §A-10 scale.
        ✓ Logic was correct — no change.
        """
        if chute_angle_deg < material.repose_angle_deg:
            return "HIGH"
        if material.cohesion > 0.5:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def discharge_chute_geometry(trajectory: list,
                                  belt_speed_mps: float,
                                  head_pulley_radius_m: float,
                                  bucket_width_mm: float) -> dict:
        """
        CEMA 375 §5 — NEW: Head discharge chute geometry design.

        Uses the trajectory (from DischargePhysics.trajectory()) to determine:
          1. Stream landing zone X range (where material hits back-plate)
          2. Required back-plate angle (tangent to trajectory at landing)
          3. Minimum spout opening width (stream width at landing)
          4. Chute throat velocity (to check non-plugging condition)

        Args:
            trajectory       : list of (x,y) tuples from DischargePhysics.trajectory()
            belt_speed_mps   : head pulley peripheral speed [m/s]
            head_pulley_radius_m : head pulley radius [m]
            bucket_width_mm  : bucket width [mm]

        Returns dict with chute design parameters.
        """
        if not trajectory or len(trajectory) < 3:
            return {"error": "Insufficient trajectory points"}

        # Find the point where stream drops to head-pulley-centre height (y=0)
        # This is where the back-plate of the discharge chute typically sits
        landing_pts = [(x, y) for x, y in trajectory if y <= 0]
        if not landing_pts:
            landing_pts = [trajectory[-1]]

        land_x, land_y = landing_pts[0]

        # Back-plate angle: tangent to trajectory at landing point
        # dy/dx at landing approximated from adjacent points
        idx = trajectory.index(landing_pts[0])
        if idx > 0:
            x1, y1 = trajectory[idx - 1]
            x2, y2 = landing_pts[0]
            dx = x2 - x1
            dy = y2 - y1
            back_angle_deg = abs(math.degrees(math.atan2(abs(dy), max(dx, 0.001))))
        else:
            back_angle_deg = 60.0  # default

        # Spout opening width: bucket width + 50mm clearance per side (CEMA 375 §5)
        spout_width_mm = bucket_width_mm + 100

        # Stream X range (from release to landing)
        x_release = trajectory[0][0]
        x_throw    = land_x - x_release

        # Throat velocity check: must be > 0.5 m/s to prevent plugging
        # Approximate: v_throat = belt_speed × cos(back_angle)
        v_throat = belt_speed_mps * math.cos(math.radians(back_angle_deg))

        return {
            "land_x_m":          round(land_x, 3),
            "land_y_m":          round(land_y, 3),
            "throw_distance_m":  round(x_throw, 3),
            "back_plate_angle_deg": round(back_angle_deg, 1),
            "spout_width_mm":    spout_width_mm,
            "throat_velocity_mps": round(v_throat, 3),
            "plugging_risk":     "HIGH" if v_throat < 0.5 else "LOW",
            "note": "CEMA 375 §5: back-plate angle should match trajectory tangent at landing",
        }

    @staticmethod
    def chute_wear_rate(material, velocity_mps: float,
                         impact_angle_deg: float = 45.0) -> str:
        """
        CEMA 375 §5 / CEMA 550 §A-1 — Relative chute lining wear rate.
        Based on CEMA 550 abrasive code and Finnie erosion model:
          Wear ∝ v² · sin(2α) · abr_code  (α = impact angle)

        Returns qualitative rating: LOW / MEDIUM / HIGH / SEVERE
        with lining material recommendation.
        """
        abr = getattr(material, "abr_code", 3)
        alpha = math.radians(impact_angle_deg)
        wear_index = (velocity_mps ** 2) * math.sin(2 * alpha) * abr

        if wear_index < 5:
            rating, lining = "LOW",    "Mild steel plate acceptable"
        elif wear_index < 15:
            rating, lining = "MEDIUM", "AR400 wear plate recommended"
        elif wear_index < 35:
            rating, lining = "HIGH",   "AR500 or ceramic tile liner required"
        else:
            rating, lining = "SEVERE", "Cast basalt or alumina ceramic liner required"

        return f"{rating} (index {wear_index:.1f}) — {lining}"
