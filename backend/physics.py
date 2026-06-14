"""
VECTRIX™ — Discharge Physics Engine
CEMA No. 375-2017 §3

v1.1.0 — Physics Accuracy Audit
─────────────────────────────────────────────────────────────────────────────
1. CRITICAL  Velocity vy sign corrected.
             v1.0: vy = +v·sin θ — material moves UPWARD after top (wrong).
             v1.1: vy = -v·sin θ — correct tangential for clockwise rotation.

2. CRITICAL  Release angle formula corrected.
             v1.0: θ = acos(CR)   = acos(v²/rg) — collapses to 0° for all CR>1.
             v1.1: θ = acos(1/CR) = acos(rg/v²) — yields 60-75° at CR 2-3,
                   consistent with CEMA 375 §3 centrifugal discharge zone.

3. NEW       discharge_class() — maps CR → CEMA §3 regime string.

4. NEW       retention_factor() — cohesion + moisture bucket-retention model;
             scales effective launch velocity before trajectory computation.

5. NEW       calculate_release_point() — replaces centrifugal_release_angle();
             returns frozen ReleasePoint dataclass with θ, position, velocity,
             CR, discharge class, and retention factor.

6. UPDATED   trajectory() — uses calculate_release_point() for both position
             and velocity; floor_y replaces the -radius×3 proxy stop condition;
             elevator_type parameter added.

7. UPDATED   stream_envelope() — spread now accounts for particle_size_mm and
             cohesion_index; narrow for cohesive fines, wide for coarse.

8. UPDATED   backlegging_check() — return_leg_y parameter added; check is now
             |y − return_leg_y| ≤ belt_half_width instead of |y| ≤ constant.

9. DEPRECATED centrifugal_release_angle() — preserved for caller compatibility;
              internally delegates to calculate_release_point(), emits warning.
─────────────────────────────────────────────────────────────────────────────
"""

import math
import warnings
from dataclasses import dataclass
from typing import Literal

try:
    from .constants import GRAVITY
except ImportError:
    from constants import GRAVITY


# ── CEMA 375 §3 centrifugal ratio boundary values ─────────────────────────────

_CR_CONTINUOUS_MAX  = 0.80   # below → gravity / positive displacement
_CR_TRANSITION_MAX  = 1.00   # 0.80–1.00 → unstable / transition
_CR_OPTIMAL_MAX     = 1.80   # 1.00–1.80 → centrifugal, clean discharge (target)
_CR_HIGH_MAX        = 2.50   # 1.80–2.50 → centrifugal, increasing scatter
                              # > 2.50    → excessive scatter, casing impact risk

DischargeType = Literal["centrifugal", "continuous", "positive"]


# ── Release point result type ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ReleasePoint:
    """
    Complete material release state at the head pulley.

    Coordinate convention
    ─────────────────────
    Origin  : pulley centre
    x-axis  : horizontal, positive toward the discharge side
    y-axis  : vertical, positive upward
    θ       : angle from vertical, positive clockwise (toward discharge).
              θ = 0° → top of pulley; θ = 90° → side (belt-run level).
    """
    theta_rad:     float   # release angle [rad]
    theta_deg:     float   # release angle [°]
    x0:            float   # x-position from pulley centre [m]
    y0:            float   # y-position from pulley centre [m]
    vx:            float   # x-velocity at release [m/s]
    vy:            float   # y-velocity at release [m/s]  (negative = downward)
    cr:            float   # centrifugal ratio [-]
    discharge_cls: str     # CEMA §3 classification
    retention:     float   # retention factor applied to belt speed


class DischargePhysics:

    # ── Unchanged base utilities ─────────────────────────────────────────────

    @staticmethod
    def belt_speed(diameter_m: float, rpm: float) -> float:
        """
        Peripheral belt speed  v = π · D · n / 60  [m/s].
        CEMA 375 §3 — verified correct, no change from v1.0.
        """
        return math.pi * diameter_m * rpm / 60.0

    @staticmethod
    def centrifugal_ratio(speed: float, radius: float) -> float:
        """
        CR = v² / (r · g).
        Interpretation boundaries — see discharge_class().
        CEMA 375 §3 — no change from v1.0.
        """
        return (speed ** 2) / (radius * GRAVITY)

    @staticmethod
    def release_condition(speed: float, radius: float) -> float:
        """
        Centrifugal acceleration at pulley rim = v² / r  [m/s²].
        CR > 1 ↔ release_condition > g.
        CEMA 375 §3 — no change from v1.0.
        """
        return (speed ** 2) / radius

    # ── Issue #7 — Discharge classification ──────────────────────────────────

    @staticmethod
    def discharge_class(cr: float) -> str:
        """
        Map centrifugal ratio to CEMA 375 §3 regime name.

        Returns
        -------
        "continuous"             CR < 0.80  — gravity / positive displacement
        "transition"             0.80–1.00  — neither regime; avoid by design
        "centrifugal_optimal"    1.00–1.80  — design target; clean throw
        "centrifugal_high"       1.80–2.50  — acceptable; scatter increasing
        "centrifugal_excessive"  > 2.50     — material impacts casing
        """
        if cr < _CR_CONTINUOUS_MAX:  return "continuous"
        if cr < _CR_TRANSITION_MAX:  return "transition"
        if cr < _CR_OPTIMAL_MAX:     return "centrifugal_optimal"
        if cr < _CR_HIGH_MAX:        return "centrifugal_high"
        return "centrifugal_excessive"

    # ── Issue #6 — Material retention model ──────────────────────────────────

    @staticmethod
    def retention_factor(
        cohesion_index:    float = 0.0,
        moisture_pct:      float = 0.0,
        surface_roughness: float = 0.5,
        material:          "dict | None" = None,
    ) -> float:
        """
        Effective launch-velocity retention factor [0.0–1.0].

        Material that clings to the bucket lip leaves at a reduced effective
        speed.  This factor multiplies belt speed before trajectory calculation.

        v1.2.0: accepts an optional material dict (from MATERIALS database).
        When provided, cohesion, moisture, and roughness are derived internally
        instead of requiring the caller to pre-extract them.  This eliminates
        the intermediate conversion step in calculations.py and makes the
        factor correctly material-aware for all 400 database entries.

        Parameters
        ----------
        cohesion_index     0 = free-flowing dry sand, 1 = wet clay / flyash cake
        moisture_pct       Gravimetric moisture content [%]
        surface_roughness  0 = polished steel bucket, 1 = rubber-lined
        material           If provided: all three parameters are derived from
                           the material dict; the individual arguments are ignored.
        """
        if material is not None:
            cohesion_index    = float(material.get("cohesion",     0.0))
            moisture_pct      = float(material.get("moisture_pct", 0.0))
            abr               = float(material.get("abr_code",     3))
            surface_roughness = min(1.0, abr / 10.0)   # abr 0→smooth, 7→rough

        k_cohesion  = 1.0 - 0.15 * min(1.0, max(0.0, cohesion_index))
        k_moisture  = 1.0 - 0.004 * min(20.0, max(0.0, moisture_pct))
        k_roughness = 1.0 - 0.02  * min(1.0,  max(0.0, surface_roughness))
        return k_cohesion * k_moisture * k_roughness   # full precision; round at caller

    # ── Issues #1 + #2 — Corrected release point ──────────────────────────────

    @staticmethod
    def calculate_release_point(
        speed:                  float,
        radius:                 float,
        bucket_projection_m:    float = 0.14,
        bucket_front_angle_deg: float = 30.0,
        elevator_type:          DischargeType = "centrifugal",
        cohesion_index:         float = 0.0,
        moisture_pct:           float = 0.0,
    ) -> ReleasePoint:
        """
        Full material release state — CEMA 375 §3.

        ═══════════════════════════════════════════════════════════════════
        ISSUE #1 FIX — Centrifugal release angle
        ─────────────────────────────────────────
        v1.0 formula:  cos(θ) = CR = v²/(rg)
          → acos has no real solution for CR > 1
          → code clamped CR to 1, giving θ = 0° for EVERY fast elevator
          → result: all centrifugal elevators released horizontally from top

        Correct CEMA 375 §3 formula:  cos(θ) = 1/CR = rg/v²
          →  θ = acos(rg/v²)
          →  CR = 1.0:  θ = 0°   (release at top)              ✓
          →  CR = 2.0:  θ = 60°  (60° past top, downward)      ✓
          →  CR = 3.12: θ = 71°  (throw aimed at chute)        ✓

        Physical meaning: as CR increases, material exits the bucket geometry
        further down the descending side, directing the throw progressively
        into the lower discharge chute.

        ═══════════════════════════════════════════════════════════════════
        ISSUE #2 FIX — Velocity vector
        ────────────────────────────────
        At angle θ (clockwise from top), the tangential unit vector for a
        clockwise-rotating pulley is  t̂ = (cos θ, −sin θ).

        v1.0:  vx = v·cos θ,  vy = +v·sin θ   ← wrong sign on vy
          → at θ = 60°: vy = +0.87v (material going UPWARD)    ✗

        v1.1:  vx = v·cos θ,  vy = −v·sin θ   ← corrected
          → at θ = 0°  (top) : vx = v,    vy = 0    (horizontal)  ✓
          → at θ = 60°        : vx = 0.5v, vy = −0.87v (mostly down) ✓
          → at θ = 90° (side) : vx = 0,   vy = −v   (straight down) ✓
        ═══════════════════════════════════════════════════════════════════

        v1.3.0 — bucket_front_angle_deg replaces projection-based approximation
        ────────────────────────────────────────────────────────────────────────
        For continuous discharge the onset angle is now taken directly from the
        bucket face angle (Martin catalog H-149/H-150):
            MF bucket: front_angle_deg = 30° → onset θ ≈ 30°
            HF bucket: front_angle_deg = 45° → onset θ ≈ 45°
            SC bucket: front_angle_deg = 35° → onset θ ≈ 35°

        This replaces the old approximation:
            proj_adj_deg = min(10, projection_m × 40)
            theta = max(20, 35 − proj_adj_deg)
        which produced the same ~25–35° for all continuous styles regardless
        of their actual face geometry.

        Parameters
        ----------
        speed                   Belt speed [m/s]
        radius                  Head pulley radius [m]
        bucket_projection_m     Radial projection of bucket from belt [m]
                                Used for stream spread in stream_envelope().
        bucket_front_angle_deg  Bucket face angle from vertical [°].
                                From Martin catalog: MF=30, HF=45, SC=35, AA=30.
                                Used as discharge onset angle for continuous elevators.
        elevator_type           "centrifugal" | "continuous" | "positive"
        cohesion_index          0 = free-flowing, 1 = highly cohesive
        moisture_pct            Material moisture content [%]
        """
        cr      = DischargePhysics.centrifugal_ratio(speed, radius)
        d_class = DischargePhysics.discharge_class(cr)
        r_fac   = DischargePhysics.retention_factor(cohesion_index, moisture_pct)
        v_eff   = speed * r_fac

        # ── Resolve release angle θ ───────────────────────────────────────────

        if elevator_type == "centrifugal":
            if cr < 1.0:
                warnings.warn(
                    f"Centrifugal elevator has CR = {cr:.3f} < 1.0. "
                    "Material will not discharge centrifugally at this speed. "
                    "Verify belt speed or switch to elevator_type='continuous'.",
                    UserWarning,
                    stacklevel=2,
                )
                theta = 0.0   # approximate: release near top
            else:
                # CEMA §3 centrifugal discharge angle — corrected formula
                theta = math.acos(1.0 / cr)

        elif elevator_type == "continuous":
            # CEMA §3.3: material discharges as bucket inverts at head pulley.
            # The bucket face angle from vertical (from Martin catalog) gives
            # the onset angle directly — steeper face = later release.
            #   MF (30°): gentle slope → pours at ~30° past 12 o'clock
            #   HF (45°): steeper face → pours at ~45° past 12 o'clock
            #   SC (35°): intermediate
            # Clamped to [20°, 60°] — below 20° the belt is still rising,
            # above 60° the bucket is over-rotated past the practical discharge zone.
            theta = math.radians(max(20.0, min(60.0, bucket_front_angle_deg)))

        elif elevator_type == "positive":
            # Very slow, mechanically displaced — near-vertical at top of casing
            theta = math.radians(15.0)

        else:
            theta = math.radians(30.0)   # safe fallback

        # ── Derive position and velocity ──────────────────────────────────────

        x0 =  radius * math.sin(theta)
        y0 =  radius * math.cos(theta)
        vx =  v_eff  * math.cos(theta)
        vy = -v_eff  * math.sin(theta)   # corrected sign: negative = downward

        return ReleasePoint(
            theta_rad     = theta,
            theta_deg     = math.degrees(theta),
            x0            = x0,
            y0            = y0,
            vx            = vx,
            vy            = vy,
            cr            = cr,
            discharge_cls = d_class,
            retention     = r_fac,
        )

    # ── Issue #3 — Trajectory (floor_y + elevator_type) ──────────────────────

    @staticmethod
    def trajectory(
        speed:                  float,
        radius:                 float,
        dt:                     float = 0.005,
        floor_y:                float | None = None,
        elevator_type:          DischargeType = "centrifugal",
        cohesion_index:         float = 0.0,
        moisture_pct:           float = 0.0,
        bucket_front_angle_deg: float = 30.0,
    ) -> list[tuple[float, float]]:
        """
        CEMA 375 §3 — Projectile trajectory from head pulley.

        Parameters
        ----------
        speed                   Belt speed [m/s]
        radius                  Head pulley radius [m]
        dt                      Time step [s].
        floor_y                 Terminate when y drops below this value [m].
        elevator_type           "centrifugal" | "continuous" | "positive"
        cohesion_index          0 = free-flowing, 1 = highly cohesive
        moisture_pct            Moisture content [%]
        bucket_front_angle_deg  Bucket face angle [°] — passed to
                                calculate_release_point() for continuous mode.
        """
        rp     = DischargePhysics.calculate_release_point(
            speed, radius,
            elevator_type          = elevator_type,
            cohesion_index         = cohesion_index,
            moisture_pct           = moisture_pct,
            bucket_front_angle_deg = bucket_front_angle_deg,
        )
        stop_y = floor_y if floor_y is not None else -3.0 * radius

        points: list[tuple[float, float]] = []
        t = 0.0
        while t < 5.0:
            x = rp.x0 + rp.vx * t
            y = rp.y0 + rp.vy * t - 0.5 * GRAVITY * t ** 2
            points.append((x, y))
            if y < stop_y:
                break
            t = round(t + dt, 6)

        return points

    # ── Issues #4 + #5 — Stream envelope ─────────────────────────────────────

    @staticmethod
    def stream_envelope(
        speed:                  float,
        radius:                 float,
        bucket_projection_m:    float = 0.14,
        bucket_front_angle_deg: float = 30.0,
        particle_size_mm:       float = 10.0,
        cohesion_index:         float = 0.0,
        elevator_type:          DischargeType = "centrifugal",
        floor_y:                float | None = None,
        material:               "dict | None" = None,
    ) -> dict:
        """
        CEMA 375 §3 — Discharge stream envelope (centre, upper, lower bounds).

        v1.2.0 changes
        ──────────────
        • Accepts optional material dict. When provided, MaterialBehaviorEngine
          .stream_spread_factor() is applied to scale the base spread by the
          material's actual flow properties (cohesion, moisture, particle shape).
          This replaces the generic k_mat = 1 − cohesion_index approximation.
        • Output points are full precision — rounding is the caller's responsibility.
        • trajectory_metrics block added to the return dict.

        Spread model
        ────────────
        base_spread = 0.5 · bucket_projection
                    + 0.04 · v² / g
                    + k_mat · particle_size_mm / 1000

        k_mat = max(0, 1 − cohesion_index) when no material dict given.

        When material dict is provided:
            spread *= MaterialBehaviorEngine.stream_spread_factor(material, speed)

        Physical rationale for each term
        ──────────────────────────────────
        0.5 · proj          Half bucket projection → initial stream half-width
        0.04 · v²/g         Velocity-proportional throw dispersion (empirical)
        k_mat · d / 1000    Particle-size scatter; larger lumps disperse wider

        Parameters
        ----------
        material    Optional material dict from MATERIALS database.  When present,
                    cohesion and particle size are extracted automatically and
                    MaterialBehaviorEngine.stream_spread_factor() is applied.
        """
        # Derive cohesion and particle size from material dict if available
        if material is not None:
            cohesion_index   = float(material.get("cohesion",         cohesion_index))
            particle_size_mm = float(material.get("particle_size_mm", particle_size_mm)
                                     if material.get("particle_size_mm") else particle_size_mm)

        k_mat = max(0.0, 1.0 - cohesion_index)
        base_spread = (
            0.5  * bucket_projection_m
            + 0.04 * (speed ** 2) / GRAVITY
            + k_mat * particle_size_mm / 1000.0
        )

        # Scale by MaterialBehaviorEngine if material dict provided
        if material is not None:
            try:
                from .material_behavior import MaterialBehaviorEngine
                behavior_factor = MaterialBehaviorEngine.stream_spread_factor(material, speed)
                spread = base_spread * behavior_factor
            except Exception:
                spread = base_spread
        else:
            spread = base_spread

        center = DischargePhysics.trajectory(
            speed, radius,
            elevator_type          = elevator_type,
            cohesion_index         = cohesion_index,
            floor_y                = floor_y,
            bucket_front_angle_deg = bucket_front_angle_deg,
        )

        # Full precision — no rounding in physics layer
        upper = [(x, y + spread) for x, y in center]
        lower = [(x, y - spread) for x, y in center]

        # Trajectory metrics derived from center line
        metrics = DischargePhysics.trajectory_metrics(center, speed)

        return {
            "center":   center,
            "upper":    upper,
            "lower":    lower,
            "spread_m": spread,
            "metrics":  metrics,
        }

    # ── Issue #4 (cont.) — Backlegging check ─────────────────────────────────

    @staticmethod
    def backlegging_check(
        trajectory:      list[tuple[float, float]],
        return_leg_x:    float,
        return_leg_y:    float = 0.0,
        belt_half_width: float = 0.15,
    ) -> bool:
        """
        CEMA 375 §3 — Backlegging risk assessment.

        Returns True when any trajectory point falls within the return belt
        height band AND is at or beyond the return belt x-position.

        v1.0 FIX: Original checked |y| ≤ casing_half_width, which assumed the
        return belt is always centred at y = 0.  This caused false positives
        when material flew high and crossed x = return_leg_x well above the
        actual belt.

        Corrected condition: x ≥ return_leg_x AND |y − return_leg_y| ≤ half_w

        Parameters
        ----------
        trajectory       List of (x, y) tuples from DischargePhysics.trajectory()
        return_leg_x     Horizontal distance to return belt centreline [m]
        return_leg_y     Vertical position of return belt centreline [m from
                         pulley centre].  v1.0 hardcoded this as 0.
        belt_half_width  Half the physical belt width plus clearance band [m].
                         Default 150 mm is typical for medium-duty casing.

        Returns
        -------
        True if material is predicted to strike the return belt.
        """
        for x, y in trajectory:
            if x >= return_leg_x and abs(y - return_leg_y) <= belt_half_width:
                return True
        return False

    # ── Trajectory metrics ────────────────────────────────────────────────────

    @staticmethod
    def trajectory_metrics(
        points:        list[tuple[float, float]],
        release_speed: float,
        dt:            float = 0.005,
    ) -> dict:
        """
        Summary metrics derived from a trajectory point list.

        All values are full precision — round at the API layer (calculations.py).

        Parameters
        ----------
        points         List of (x, y) tuples from trajectory() [m]
        release_speed  Belt speed at release [m/s] (used for energy conservation)
        dt             Time step used to generate the trajectory [s].
                       Default 0.005 matches trajectory() default.

        Returns
        -------
        {
            "throw_distance_m":    x_land − x_release  [m]
            "max_height_m":        highest y above release point [m]
            "impact_velocity_mps": v at landing (energy conservation) [m/s]
            "flight_time_s":       n_points × dt [s]
            "land_x_m":            x coordinate of last point [m]
            "land_y_m":            y coordinate of last point [m]
        }
        """
        if not points or len(points) < 2:
            return {}

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        x_release = xs[0]
        y_release = ys[0]
        x_land    = xs[-1]
        y_land    = ys[-1]

        throw_distance = x_land - x_release
        max_height     = max(ys) - y_release       # positive if stream rises first
        flight_time    = len(points) * dt

        # Impact speed from energy conservation: v² = v₀² + 2g·Δh
        delta_h  = y_release - y_land              # positive when material falls
        v_impact = math.sqrt(max(0.0, release_speed ** 2 + 2.0 * GRAVITY * delta_h))

        return {
            "throw_distance_m":    throw_distance,
            "max_height_m":        max_height,
            "impact_velocity_mps": v_impact,
            "flight_time_s":       flight_time,
            "land_x_m":            x_land,
            "land_y_m":            y_land,
        }

    # ── Stream interception analysis ──────────────────────────────────────────

    @staticmethod
    def stream_intersects_chute(
        trajectory:    list[tuple[float, float]],
        chute_x0_m:   float,
        chute_y0_m:   float,
        chute_x1_m:   float,
        chute_y1_m:   float,
        release_speed: float = 2.0,
    ) -> dict:
        """
        Check whether the discharge stream trajectory intersects a chute opening.

        The chute opening is defined as a straight line segment from
        (chute_x0_m, chute_y0_m) to (chute_x1_m, chute_y1_m), all coordinates
        relative to the head pulley centre [m].

        Uses parametric 2D line-segment intersection:
            P(t) = P1 + t·(P2 − P1),  t ∈ [0, 1]   — trajectory segment
            C(s) = C0 + s·(C1 − C0),  s ∈ [0, 1]   — chute segment
        Intersection requires both t and s in [0, 1].

        Parameters
        ----------
        trajectory      List of (x, y) tuples from trajectory() [m]
        chute_x0_m …    Chute opening endpoints [m] — pulley-centre reference frame
        release_speed   Belt speed at release [m/s] — for impact velocity

        Returns
        -------
        {
            "intercepted":       bool
            "impact_x_m":        float | None
            "impact_y_m":        float | None
            "impact_angle_deg":  float | None   angle between stream and chute normal
            "impact_velocity_mps": float | None  energy-conservation estimate
            "trajectory_fraction": float | None  how far along trajectory (0–1)
            "note":              str
        }
        """
        cx0, cy0 = chute_x0_m, chute_y0_m
        cx1, cy1 = chute_x1_m, chute_y1_m
        cdx, cdy = cx1 - cx0, cy1 - cy0

        for i in range(len(trajectory) - 1):
            px1, py1 = trajectory[i]
            px2, py2 = trajectory[i + 1]
            tdx, tdy = px2 - px1, py2 - py1

            denom = tdx * cdy - tdy * cdx
            if abs(denom) < 1e-12:
                continue            # parallel segments

            t = ((cx0 - px1) * cdy - (cy0 - py1) * cdx) / denom
            s = ((cx0 - px1) * tdy - (cy0 - py1) * tdx) / denom

            if 0.0 <= t <= 1.0 and 0.0 <= s <= 1.0:
                ix = px1 + t * tdx
                iy = py1 + t * tdy

                # Impact angle: between trajectory direction and chute normal
                chute_len = math.sqrt(cdx**2 + cdy**2)
                if chute_len > 1e-9:
                    # Chute normal (rotate 90°): (-cdy, cdx) / len
                    nx, ny = -cdy / chute_len, cdx / chute_len
                    traj_len = math.sqrt(tdx**2 + tdy**2)
                    if traj_len > 1e-9:
                        tx, ty = tdx / traj_len, tdy / traj_len
                        dot = abs(tx * nx + ty * ny)
                        impact_angle = math.degrees(math.asin(min(1.0, dot)))
                    else:
                        impact_angle = 90.0
                else:
                    impact_angle = 90.0

                # Impact velocity from energy conservation
                delta_h  = trajectory[0][1] - iy
                v_impact = math.sqrt(max(0.0, release_speed**2 + 2.0 * GRAVITY * delta_h))

                traj_frac = (i + t) / max(len(trajectory) - 1, 1)

                return {
                    "intercepted":          True,
                    "impact_x_m":           ix,
                    "impact_y_m":           iy,
                    "impact_angle_deg":     impact_angle,
                    "impact_velocity_mps":  v_impact,
                    "trajectory_fraction":  traj_frac,
                    "note": "Stream intersects chute at computed point.",
                }

        return {
            "intercepted":          False,
            "impact_x_m":           None,
            "impact_y_m":           None,
            "impact_angle_deg":     None,
            "impact_velocity_mps":  None,
            "trajectory_fraction":  None,
            "note": "Stream does not intersect the specified chute opening.",
        }

    # ── Casing clearance check ────────────────────────────────────────────────

    @staticmethod
    def casing_clearance_check(
        trajectory:           list[tuple[float, float]],
        casing_half_width_m:  float,
        casing_inner_x_m:     float | None = None,
    ) -> dict:
        """
        Check whether the discharge stream clears the elevator casing wall.

        Real-world problem: at high CR (> 2.5) or with very wide buckets, the
        material stream can strike the casing head section before entering the
        discharge chute, causing wear, blockage, and structural damage.

        The casing wall is modelled as a vertical plane at
        x = casing_half_width_m (measured from pulley centre).

        Parameters
        ----------
        trajectory           List of (x, y) tuples from trajectory() [m]
        casing_half_width_m  Half the internal casing width at head [m].
                             Typical: belt_width / 2 + casing_plate_thickness
        casing_inner_x_m     Override for non-symmetric casings [m].
                             If None: uses casing_half_width_m.

        Returns
        -------
        {
            "clears":          bool   True if stream stays inside casing
            "max_x_m":         float  Maximum x reached by stream [m]
            "clearance_m":     float  casing_wall_x − max_x  (negative = strike)
            "strike_x_m":      float | None  x at first wall contact
            "strike_y_m":      float | None  y at first wall contact
            "casing_wall_x_m": float  the wall position used for the check
        }
        """
        wall_x = casing_inner_x_m if casing_inner_x_m is not None else casing_half_width_m

        max_x      = max((p[0] for p in trajectory), default=0.0)
        clearance  = wall_x - max_x
        clears     = clearance >= 0.0

        strike_x = strike_y = None
        if not clears:
            # High-CR case: release point already starts beyond the casing wall.
            # No inside→outside transition exists in the trajectory — use the
            # first point as the entry strike (material exits directly through wall).
            if trajectory and trajectory[0][0] >= wall_x:
                strike_x = trajectory[0][0]
                strike_y = trajectory[0][1]
            else:
                for i in range(len(trajectory) - 1):
                    x1, y1 = trajectory[i]
                    x2, y2 = trajectory[i + 1]
                    if x1 <= wall_x <= x2 or x2 <= wall_x <= x1:
                        if abs(x2 - x1) > 1e-9:
                            frac     = (wall_x - x1) / (x2 - x1)
                            strike_x = wall_x
                            strike_y = y1 + frac * (y2 - y1)
                        break

        # Build recommendation — guard against None strike coords
        if not clears:
            if strike_x is not None and strike_y is not None:
                _rec = (
                    f"Stream strikes casing at x={strike_x:.3f} m, "
                    f"y={strike_y:.3f} m. "
                    "Consider reducing belt speed, increasing casing width, "
                    "or adding a curved hood to redirect the stream."
                )
            else:
                _rec = (
                    f"Stream exceeds casing wall (stream max x={max_x:.3f} m, "
                    f"wall at {wall_x:.3f} m) — strike point not interpolated. "
                    "Increase casing width or reduce belt speed."
                )
        else:
            _rec = "Stream clears casing — no head-section impact risk."

        return {
            "clears":           clears,
            "max_x_m":          max_x,
            "clearance_m":      clearance,
            "strike_x_m":       strike_x,
            "strike_y_m":       strike_y,
            "casing_wall_x_m":  wall_x,
            "recommendation":   _rec,
        }

    # ── Deprecated — retained for backward compatibility ──────────────────────

    # ─── Continuous (HF) discharge model ────────────────────────────────────
    #
    # For HF (high-capacity continuous discharge) elevators:
    #   • Buckets are closely spaced (back-to-back or slight overlap)
    #   • Belt speed is low — CR = v²/(g·r) is typically 0.3–0.7
    #   • At the head pulley, buckets invert.  Material pours under gravity +
    #     belt kinematics rather than being thrown centrifugally.
    #   • The discharge stream is a short, nearly-vertical curtain, not a
    #     parabolic throw envelope.
    #   • The receiving chute is positioned above/behind the head pulley
    #     to catch the pour.
    #
    # CEMA 375-2017 §3.3 notes that for continuous discharge the trajectory
    # model of §3.2 (centrifugal) does not apply; the design check is instead
    # that CR is BELOW 1.0 (any higher triggers centrifugal discharge, which
    # defeats the gentle-handling purpose of the HF design).

    @staticmethod
    def continuous_discharge_curve(
        v_belt:    float,
        D_mm:      float,
        n_points:  int   = 40,
        aor_deg:   float = 35.0,
    ) -> dict:
        """
        Model the material stream from a continuous (HF) discharge elevator.

        For continuous discharge the bucket inverts at the top of the head
        pulley and material pours out under gravity.  This is NOT a parabolic
        throw; the stream is a short curtain that falls nearly vertically.

        The model sweeps the bucket mouth from onset (θ_onset, where the
        bucket has tilted enough for the material surface to reach the lip) to
        θ = 90° (bucket fully inverted), collecting the path of material
        leaving the bucket mouth at each orientation.

        Parameters
        ----------
        v_belt   Belt speed [m/s]
        D_mm     Head pulley diameter [mm]
        n_points Number of trajectory points
        aor_deg  Material angle of repose [°] — controls onset angle

        Returns
        -------
        {
            center:          [(x, y), ...]  — stream centreline
            upper:           [(x, y), ...]  — upper stream bound
            lower:           [(x, y), ...]  — lower stream bound (near belt)
            cr:              float           — centrifugal ratio (should be < 1)
            onset_angle_deg: float           — bucket tilt at which pour begins
            chute_rec:       dict            — recommended chute geometry
        }
        """
        import math as _m
        g = GRAVITY
        r = D_mm / 2000.0                       # head pulley radius [m]
        cr = v_belt ** 2 / (g * r) if r > 0 else 0

        # Onset angle: bucket tilts until material surface reaches lip
        # Approximation: onset ≈ AoR (material starts to slide at AoR tilt)
        theta_onset = _m.radians(min(aor_deg, 60.0))
        theta_end   = _m.radians(90.0)

        # Belt tangential velocity at any point on the pulley gives:
        #   v_x = v_belt × sin(θ)  (horizontal, away from belt)
        #   v_y = v_belt × cos(θ)  (vertical, downward on discharge side)
        # as the bucket mouth passes angle θ from the 12-o'clock position.

        dt = 0.005   # time step for free-fall [s]

        center_pts = []
        upper_pts  = []
        lower_pts  = []

        # Simulate material leaving at each bucket angle during inversion
        n_angles = n_points // 2
        for i in range(n_angles):
            frac  = i / max(n_angles - 1, 1)
            theta = theta_onset + frac * (theta_end - theta_onset)

            # Bucket mouth position at angle θ from top
            x0 = r * _m.sin(theta)
            y0 = r * _m.cos(theta)

            # Initial velocity of material leaving the bucket mouth
            # (tangential to pulley circumference, modified by gravity component)
            vx0 =  v_belt * _m.sin(theta)   # positive = away from belt
            vy0 = -v_belt * _m.cos(theta)   # negative = downward

            # Follow this parcel for a short time (until it hits y = -r)
            x, y = x0, y0
            vx, vy = vx0, vy0
            for _ in range(n_points):
                x  += vx * dt
                y  += vy * dt
                vy -= g * dt   # gravity
                if y < -r:     # below boot level — clamp
                    break

            center_pts.append((round(x0, 4), round(y0, 4)))
            upper_pts.append((round(x0 + 0.03, 4), round(y0, 4)))    # ±30mm spread
            lower_pts.append((round(x0 - 0.03, 4), round(y0 - 0.05, 4)))

        # The bottom of the stream: where the curtain lands
        # Material from θ = θ_onset falls freely from (x0, y0)
        x_land = r * _m.sin(theta_onset) + v_belt * _m.sin(theta_onset) * 0.3
        y_land = r * _m.cos(theta_onset) - 0.5 * g * 0.3 ** 2

        # Recommended chute back-plate position (behind pulley)
        # Back plate perpendicular to the mean discharge direction
        chute_x = -r * 0.8     # slightly behind (negative x = behind belt)
        chute_angle = max(aor_deg + 10, 60.0)   # steeper than AoR

        return {
            "center":          center_pts,
            "upper":           upper_pts,
            "lower":           lower_pts,
            "cr":              round(cr, 4),
            "onset_angle_deg": round(_m.degrees(theta_onset), 1),
            "land_x_m":        round(x_land, 4),
            "land_y_m":        round(y_land, 4),
            "chute_rec": {
                "back_plate_x_m":    round(chute_x, 3),
                "back_plate_angle_deg": round(chute_angle, 1),
                "description": (
                    f"Back plate at x={chute_x*1000:.0f}mm behind centreline, "
                    f"angled at {chute_angle:.0f}° (AoR + 10°). "
                    f"Spout should be centered on the inverted bucket sweep "
                    f"(θ = {_m.degrees(theta_onset):.0f}° to 90°)."
                ),
            },
        }

    @staticmethod
    def continuous_casing_check(v_belt: float, D_mm: float,
                                 belt_w_mm: float) -> dict:
        """
        Casing clearance for continuous (HF) discharge.

        For HF elevators, the concern is not stream strike but bucket
        clearance at the head pulley. The minimum casing width is set by
        bucket width + standard CEMA 50mm clearance each side.

        Returns pass/fail with minimum required casing width.
        """
        cr = v_belt ** 2 / (GRAVITY * max(D_mm / 2000.0, 0.001))
        centrifugal_risk = cr >= 1.0

        return {
            "cr": round(cr, 4),
            "centrifugal_risk": centrifugal_risk,
            "clears": not centrifugal_risk,
            "recommendation": (
                f"CR = {cr:.3f} — centrifugal discharge onset risk. "
                f"Reduce belt speed: v_max = {GRAVITY * D_mm/2000.0:.2f} m/s for CR < 1.0."
                if centrifugal_risk else
                f"CR = {cr:.3f} < 1.0 — continuous discharge confirmed. "
                f"Verify casing width ≥ bucket width + 100mm for clearance."
            ),
        }



    @staticmethod
    def centrifugal_release_angle(speed: float, radius: float) -> float:
        """
        DEPRECATED since v1.1.0 — use calculate_release_point() instead.

        This method now delegates to calculate_release_point() and returns
        theta_rad using the CORRECTED formula  acos(1/CR), NOT the v1.0
        erroneous acos(CR).  Callers that depended on the old (wrong) clamped
        behaviour should migrate to calculate_release_point() directly.

        If you explicitly need the old broken value for comparison:
            math.acos(min(1.0, speed**2 / (GRAVITY * radius)))
        """
        warnings.warn(
            "DischargePhysics.centrifugal_release_angle() is deprecated. "
            "Use calculate_release_point() for the full ReleasePoint result. "
            "IMPORTANT: the formula has changed from acos(CR) → acos(1/CR). "
            "Trajectories computed from this angle will differ from v1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return DischargePhysics.calculate_release_point(speed, radius).theta_rad