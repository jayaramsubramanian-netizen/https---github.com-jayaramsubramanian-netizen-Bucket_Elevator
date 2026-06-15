"""
VECTRIX™ — Chute Flow Engine
CEMA No. 375-2017 §5 / CEMA 550-2020

v1.1.0 — Engineering Upgrade
─────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1.0.0
─────────────────────────────────────────────────────────────────────────────
1. FIX  Dict-compatible throughout.
        All methods used attribute access (material.cohesion, material.abr_code).
        All MATERIALS are plain dicts — this crashed on every call.
        Fixed: all methods now use material.get("field", default).

2. FIX  chute_angle() now driven by wall friction (CEMA §5 primary criterion)
        and delegates to MaterialBehaviorEngine.chute_friction() which already
        distinguishes internal vs wall friction per material.
        Previous: θ = repose + fixed_margin (wall friction was never used).
        Current:  θ = max(φ_wall + margin, repose + 5°).
        Returns both minimum angle and the governing criterion for the report.

3. NEW  chute_exit_velocity() — kinematic velocity model.
        a = g·(sin θ − μ·cos θ).  v_exit² = v_entry² + 2·a·L.
        Detects stall condition (material stops in chute).
        Required for accurate wear, impact, and dust calculations.

4. NEW  chute_capacity_check() — cross-section verification.
        Computes required flow area, material stream depth, and loading ratio.
        Loading ratio > 60% → plugging risk flag.
        CEMA requirement not previously implemented.

5. NEW  flow_regime_classification() — mass flow / funnel flow / plugging.
        Simplified Jenike criterion using wall friction + cohesion penalty.
        Distinguishes the three industrial flow regimes with angle thresholds.

6. NEW  plugging_probability() — cohesion + moisture + flowability index.
        Uses all three MaterialBehaviorEngine properties the reviewer flagged.
        Returns index, risk level, and specific mitigation recommendation.

7. NEW  chute_liner_selection() — expanded to 8 liner materials.
        Wear index determines selection from:
        UHMW-PE → Mild steel → AR400 → AR500 → CCO →
        Cast basalt → Alumina ceramic → Silicon carbide.
        Cohesive materials routed to smooth UHMW/rubber liners regardless
        of wear index (self-cleaning surface more important than hardness).

8. NEW  dust_risk() — velocity × drop height × fines potential model.
        Suppressed by cohesion and moisture (wet/sticky = less airborne dust).
        Returns dust level and required control measures.

9. NEW  hood_spoon_geometry() — basic hood and spoon sizing.
        CEMA 375 §5 head chute geometry from pulley radius and CR.
        Preliminary geometry only — detailed CAD required for fabrication.

10. NEW design_summary() — integrated recommendations engine.
        Collects all sub-model outputs into a single structured dict with:
        performance, maintenance, telemetry, and actionable recommendations.
        This is the primary output the report generator and UI consume.

11. FIX discharge_chute_geometry() — replaced fragile trajectory.index()
        with enumerate() loop; now handles duplicate trajectory y-values.
─────────────────────────────────────────────────────────────────────────────
"""

import math
from typing import Optional
try:
    from .constants import GRAVITY
except ImportError:
    from constants import GRAVITY
try:
    from .material_behavior import MaterialBehaviorEngine
except ImportError:
    from material_behavior import MaterialBehaviorEngine


class ChuteFlowEngine:

    # ── 1. Inlet velocity (unchanged — formula was correct) ──────────────────

    @staticmethod
    def inlet_velocity(
        capacity_tph: float,
        density_kgm3: float,
        inlet_area_m2: float,
    ) -> float:
        """
        CEMA 375 §5 — Material velocity at boot inlet [m/s].
        v = Q_vol / A = (ṁ / ρ) / A
        """
        mass_flow       = capacity_tph * 1000.0 / 3600.0
        volumetric_flow = mass_flow / max(density_kgm3, 1.0)
        return volumetric_flow / max(inlet_area_m2, 1e-6)

    # ── 2. Chute minimum angle (wall-friction driven) ─────────────────────────

    @staticmethod
    def chute_angle(material: dict) -> dict:
        """
        CEMA 375 §5 — Minimum chute angle for reliable gravity flow [°].

        FIX v1.1.0: now governed by wall friction (the correct CEMA §5 criterion)
        not by angle of repose.  MaterialBehaviorEngine.chute_friction() returns
        tan(φ_wall), the material-to-steel friction coefficient.

        Minimum angle derivation:
            θ_wall  = arctan(μ_wall)          — angle below which material stalls
            θ_repose = material angle of repose — absolute lower bound
            margin  = abrasion-based safety factor
                      Low abrasion (1–3): +15° (steeper = faster throughput)
                      Medium (4–5):       +10° (balance flow vs liner wear)
                      High (6–7):         +5°  (protect liner; ceramic required)
            θ_min   = max(θ_wall + margin, θ_repose + 5°)

        Returns dict (not float) so the report can show governing criterion.
        """
        mu_wall       = MaterialBehaviorEngine.chute_friction(material)
        phi_wall_deg  = math.degrees(math.atan(mu_wall))
        angle_repose  = material.get("angle_repose", 35.0)

        abr = material.get("abr_code", 3)
        margin = 15.0 if abr <= 3 else (10.0 if abr <= 5 else 5.0)

        angle_from_wall   = phi_wall_deg + margin
        angle_from_repose = angle_repose + 5.0
        angle_min         = max(angle_from_wall, angle_from_repose)
        governed_by = "wall friction" if angle_from_wall >= angle_from_repose else "angle of repose"

        return {
            "angle_min_deg":      round(angle_min, 1),
            "phi_wall_deg":       round(phi_wall_deg, 1),
            "mu_wall":            round(mu_wall, 4),
            "angle_repose_deg":   angle_repose,
            "margin_deg":         margin,
            "governed_by":        governed_by,
            "note": f"CEMA 375 §5: chute must exceed wall friction angle {phi_wall_deg:.1f}° + {margin:.0f}° margin",
        }

    # ── 3. Exit velocity — kinematic model (NEW) ─────────────────────────────

    @staticmethod
    def chute_exit_velocity(
        v_entry_mps: float,
        chute_angle_deg: float,
        chute_length_m: float,
        mu_wall: float,
    ) -> dict:
        """
        CEMA 375 §5 — Material velocity at chute exit [m/s].

        Kinematic model:
            a = g·(sin θ − μ_wall·cos θ)   [m/s²]
            v_exit² = v_entry² + 2·a·L
            (positive a = accelerating; negative = decelerating)

        Stall check: if material decelerates, computes the distance at which
        it would stop.  v_exit = 0 if stall occurs within chute length.

        Parameters
        ----------
        v_entry_mps      Material velocity entering the chute [m/s]
        chute_angle_deg  Chute inclination from horizontal [°]
        chute_length_m   Chute length along slope [m]
        mu_wall          Wall friction coefficient (tan φ_wall)
        """
        theta = math.radians(chute_angle_deg)
        a     = GRAVITY * (math.sin(theta) - mu_wall * math.cos(theta))

        stall_distance_m = None
        stalls           = False
        if a < 0:
            # Material decelerates — check if it stops before chute exit
            L_stall = (v_entry_mps ** 2) / (2.0 * abs(a))
            if L_stall < chute_length_m:
                stalls           = True
                stall_distance_m = round(L_stall, 3)

        v_exit_sq = v_entry_mps ** 2 + 2.0 * a * chute_length_m
        v_exit    = math.sqrt(max(0.0, v_exit_sq)) if not stalls else 0.0

        result = {
            "v_entry_mps":       round(v_entry_mps, 3),
            "v_exit_mps":        round(v_exit,      3),
            "acceleration_mps2": round(a,            4),
            "accelerating":      a > 0,
            "chute_length_m":    chute_length_m,
            "stalls":            stalls,
        }
        if stalls:
            result["stall_distance_m"] = stall_distance_m
            result["warning"] = (
                f"Material stalls at {stall_distance_m} m — chute angle {chute_angle_deg:.0f}° "
                f"too shallow for μ_wall={mu_wall:.3f}.  Increase angle or reduce friction."
            )
        return result

    # ── 4. Capacity / loading check (NEW) ────────────────────────────────────

    @staticmethod
    def chute_capacity_check(
        capacity_tph:   float,
        density_kgm3:   float,
        chute_width_m:  float,
        chute_height_m: float,
        velocity_mps:   float,
    ) -> dict:
        """
        CEMA 375 §5 — Chute cross-section adequacy check.

        Computes the required flow area at the given velocity and compares
        it against the actual chute opening.

        Loading ratio = stream_depth / chute_height
            < 0.40 : OK — free flow with headroom
            0.40–0.60 : WARN — acceptable but monitor for surging
            > 0.60 : FAIL — plugging risk

        Uses 85% effective width factor to account for non-uniform flow
        distribution (stream occupies ~85% of chute width).
        """
        mass_flow      = capacity_tph * 1000.0 / 3600.0
        vol_flow       = mass_flow / max(density_kgm3, 1.0)

        A_required     = vol_flow / max(velocity_mps, 0.01)
        A_actual       = chute_width_m * chute_height_m

        eff_width      = chute_width_m * 0.85
        stream_depth   = A_required / max(eff_width, 0.001)
        loading_ratio  = stream_depth / max(chute_height_m, 0.001)

        if loading_ratio < 0.40:
            status = "ok"
        elif loading_ratio < 0.60:
            status = "warn"
        else:
            status = "fail"

        return {
            "vol_flow_m3s":     round(vol_flow,      5),
            "A_required_m2":    round(A_required,    5),
            "A_actual_m2":      round(A_actual,      5),
            "stream_depth_m":   round(stream_depth,  4),
            "loading_ratio":    round(loading_ratio, 3),
            "loading_pct":      round(loading_ratio * 100.0, 1),
            "status":           status,
            "note": "CEMA: loading < 40% preferred; > 60% = plugging risk [CEMA 375 §5]",
        }

    # ── 5. Residence time (unchanged — formula was correct) ──────────────────

    @staticmethod
    def chute_residence_time(length_m: float, velocity_mps: float) -> float:
        """Time material spends in chute [s].  t = L / v."""
        return length_m / max(velocity_mps, 0.001)

    # ── 6. Impact force (v_entry × sin θ fix preserved) ─────────────────────

    @staticmethod
    def impact_force(
        mass_flow_rate_kgs: float,
        velocity_mps: float,
        impact_angle_deg: float = 90.0,
    ) -> float:
        """
        CEMA 375 §5 — Impact force on chute wall [N].
        F = ṁ × v · sin(θ_impact)
        Default 90° = perpendicular (conservative).
        Pass chute_angle_deg for actual angled chute.
        """
        delta_v = velocity_mps * math.sin(math.radians(impact_angle_deg))
        return mass_flow_rate_kgs * delta_v

    # ── 7. Flow regime classification (NEW) ──────────────────────────────────

    @staticmethod
    def flow_regime_classification(material: dict, chute_angle_deg: float) -> dict:
        """
        CEMA 375 §5 / Jenike — Chute flow regime classification.

        Three regimes:
            MASS_FLOW   All material moves simultaneously — preferred.
                        Requires θ > φ_wall + 10° + cohesion_penalty.
            FUNNEL_FLOW Centre channel moves, sides stagnant — acceptable.
                        Requires θ > φ_wall + 3° + cohesion_penalty.
            PLUGGING    No flow — unacceptable.

        Simplified Jenike flow-factor criterion (full Jenike requires
        flow factor chart and cohesive strength test data).
        Cohesion penalty: more cohesive material requires steeper angle.
        """
        mu_wall        = MaterialBehaviorEngine.chute_friction(material)
        phi_wall_deg   = math.degrees(math.atan(mu_wall))
        cohesion       = material.get("cohesion", 0.2)
        cohesion_pen   = cohesion * 15.0      # up to 15° extra for extreme cohesion

        theta_mass     = phi_wall_deg + 10.0 + cohesion_pen
        theta_funnel   = phi_wall_deg +  3.0 + cohesion_pen

        if chute_angle_deg >= theta_mass:
            regime = "MASS_FLOW"
            note   = "All material moves uniformly — preferred. Clean discharge expected."
        elif chute_angle_deg >= theta_funnel:
            regime = "FUNNEL_FLOW"
            note   = "Central channel flows; sides stagnant. Monitor for build-up; add vibrators."
        else:
            regime = "PLUGGING_RISK"
            note   = (f"Angle {chute_angle_deg:.0f}° below funnel-flow threshold "
                      f"{theta_funnel:.0f}° — increase chute angle or add flow aids.")

        return {
            "regime":                regime,
            "chute_angle_deg":       chute_angle_deg,
            "theta_mass_flow_deg":   round(theta_mass,   1),
            "theta_funnel_flow_deg": round(theta_funnel,  1),
            "phi_wall_deg":          round(phi_wall_deg,  1),
            "cohesion_penalty_deg":  round(cohesion_pen,  1),
            "note":                  note,
        }

    # ── 8. Plugging probability (NEW) ────────────────────────────────────────

    @staticmethod
    def plugging_probability(material: dict) -> dict:
        """
        CEMA 375 §5 / CEMA 550 §A-10 — Blockage probability index.

        Uses three material properties from the VECTRIX database:
            cohesion     [0–1]  CEMA §A-10 sticky/cohesive tendency
            moisture_pct [0–100] CEMA §A-15 % by weight
            flowability  [1–4]  CEMA §2.3 (1=very free, 4=poor)

        Index = cohesion × 2 + moisture_pct/100 + (flowability − 1) / 3
        Range: 0 (dry free-flowing) → ~3 (wet, highly cohesive, poor flow)
        """
        cohesion    = material.get("cohesion",     0.2)
        moisture    = material.get("moisture_pct", 0.0)
        flowability = material.get("flowability",  2)

        index = cohesion * 2.0 + (moisture / 100.0) + (flowability - 1) / 3.0

        if index < 0.50:
            risk   = "LOW"
            rec    = "Standard chute geometry acceptable."
            action = []
        elif index < 0.80:
            risk   = "MODERATE"
            rec    = "Vibrators at boot section; inspect weekly."
            action = ["Boot vibrator", "Weekly visual inspection"]
        elif index < 1.30:
            risk   = "HIGH"
            rec    = "Air cannons or fluidising pads; steep chute angle required."
            action = ["Air cannons", "Fluidising pads", "Steepen angle", "Daily inspection"]
        else:
            risk   = "SEVERE"
            rec    = "Consider screw conveyor or live-bottom hopper — standard chute unreliable."
            action = ["Re-evaluate conveying method", "Live-bottom hopper", "Screw feeder"]

        return {
            "plugging_index":    round(index, 3),
            "plugging_risk":     risk,
            "cohesion":          cohesion,
            "moisture_pct":      moisture,
            "flowability_class": flowability,
            "recommendation":    rec,
            "actions":           action,
        }

    # ── 9. Blockage risk — legacy wrapper (dict-compatible fix) ──────────────

    @staticmethod
    def blockage_risk(material: dict, chute_angle_deg: float) -> str:
        """
        CEMA 375 §5 / CEMA 550 §A-10 — Simplified blockage risk (legacy).
        Use plugging_probability() for quantitative assessment.

        FIX v1.1.0: replaced attribute access with dict .get().
        """
        angle_repose = material.get("angle_repose", 35.0)
        cohesion     = material.get("cohesion",     0.2)

        if chute_angle_deg < angle_repose:
            return "HIGH"
        if cohesion > 0.5:
            return "MEDIUM"
        return "LOW"

    # ── 10. Chute wear rate (dict-compatible fix) ─────────────────────────────

    @staticmethod
    def chute_wear_rate(
        material: dict,
        velocity_mps: float,
        impact_angle_deg: float = 45.0,
    ) -> dict:
        """
        CEMA 375 §5 / CEMA 550 §A-1 — Chute lining wear rate estimate.
        Finnie erosion model: Wear ∝ v² · sin(2α) · abr_code

        FIX v1.1.0: replaced getattr() with dict .get().
        Returns dict (was string) so the report can use individual fields.
        """
        abr   = material.get("abr_code", 3)
        alpha = math.radians(impact_angle_deg)
        index = (velocity_mps ** 2) * math.sin(2.0 * alpha) * abr

        if index < 5.0:
            rating = "LOW"
        elif index < 15.0:
            rating = "MEDIUM"
        elif index < 35.0:
            rating = "HIGH"
        else:
            rating = "SEVERE"

        return {
            "wear_index":        round(index, 2),
            "wear_rating":       rating,
            "velocity_mps":      velocity_mps,
            "impact_angle_deg":  impact_angle_deg,
            "abr_code":          abr,
        }

    # ── 11. Liner selection — expanded to 8 materials (NEW) ──────────────────

    @staticmethod
    def chute_liner_selection(
        material: dict,
        velocity_mps: float,
        impact_angle_deg: float = 45.0,
    ) -> dict:
        """
        CEMA 375 §5 — Chute liner material selection.

        Selection matrix (Finnie wear index × cohesion routing):
            Cohesive (>0.5):      UHMW-PE or natural rubber (self-cleaning)
            Cohesive (0.3–0.5):   Natural rubber
            Low wear (<5):        Mild steel A36
            Moderate (<12):       AR400 (400 BHN)
            High (<22):           AR500 (500 BHN)
            Very high (<35):      Chrome carbide overlay (CCO, 60 HRC)
            Severe (<55):         Cast basalt (8–9 Mohs)
            Extreme (<80):        Alumina ceramic (92% Al₂O₃)
            Exceptional (≥80):    Silicon carbide (SiC)
        """
        abr      = material.get("abr_code",  3)
        cohesion = material.get("cohesion",  0.2)
        alpha    = math.radians(impact_angle_deg)
        idx      = (velocity_mps ** 2) * math.sin(2.0 * alpha) * abr

        # Cohesive materials: prioritise smooth self-cleaning surface
        if cohesion > 0.50 and idx < 12:
            return {
                "liner_name":      "UHMW-PE",
                "liner_grade":     "Ultra-High Molecular Weight Polyethylene",
                "wear_index":      round(idx, 2),
                "thickness_mm":    20,
                "note":            "Smooth, self-cleaning; suitable for sticky/cohesive Class 1–2 materials.",
            }
        if cohesion > 0.30 and idx < 22:
            return {
                "liner_name":      "Natural Rubber Lining",
                "liner_grade":     "NR 60–70 Shore A",
                "wear_index":      round(idx, 2),
                "thickness_mm":    12,
                "note":            "Resilient under impact; excellent for wet or sticky materials.",
            }

        # Abrasion-driven selection
        LINERS = [
            #  max_idx  name                    grade              note                                    t_mm
            (  5.0, "Mild Steel",           "ASTM A36 / S235",  "Class 1–2 materials, v < 1.5 m/s only",    6),
            ( 12.0, "AR400 Wear Plate",     "400 BHN",          "Standard abrasion liner, Class 1–3",        10),
            ( 22.0, "AR500 Wear Plate",     "500 BHN",          "Heavy abrasion, Class 3–5",                 12),
            ( 35.0, "Chrome Carbide Overlay","CCO 60 HRC",      "High impact + abrasion, Class 4–6",         14),
            ( 55.0, "Cast Basalt",          "8–9 Mohs",         "High abrasion, lower impact tolerance",     30),
            ( 80.0, "Alumina Ceramic Tile", "92–96% Al₂O₃",     "Extreme abrasion, Class 6–7",               25),
            (999.0, "Silicon Carbide",      "SiC, 9.5 Mohs",    "Exceptional abrasion + chemical resistance",25),
        ]
        for max_idx, name, grade, note, t_mm in LINERS:
            if idx <= max_idx:
                return {
                    "liner_name":  name,
                    "liner_grade": grade,
                    "wear_index":  round(idx, 2),
                    "thickness_mm": t_mm,
                    "note":        note,
                }
        # Fallback (should not reach here)
        return {
            "liner_name":  "Silicon Carbide",
            "liner_grade": "SiC ceramic tiles",
            "wear_index":  round(idx, 2),
            "thickness_mm": 25,
            "note":        "Extreme service — consult specialist.",
        }

    # ── 12. Dust risk (NEW) ───────────────────────────────────────────────────

    @staticmethod
    def dust_risk(
        material: dict,
        velocity_mps: float,
        drop_height_m: float,
    ) -> dict:
        """
        CEMA 375 §5 — Dust generation risk assessment.

        Dust generation ∝ v_impact × H_drop × fines_factor / suppression
            v_impact   = √(v² + 2gH)       kinematic impact velocity
            fines_factor = abr_code / 4.0   more abrasive = more fines generated
            suppression  = 1 + cohesion + 2·moisture/100  wet/sticky = less airborne

        Returns risk level and required control measures.
        """
        abr      = material.get("abr_code",     3)
        cohesion = material.get("cohesion",     0.2)
        moisture = material.get("moisture_pct", 0.0)

        v_impact     = math.sqrt(velocity_mps ** 2 + 2.0 * GRAVITY * drop_height_m)
        fines_factor = abr / 4.0
        suppression  = 1.0 + cohesion + 2.0 * (moisture / 100.0)
        dust_index   = (v_impact * drop_height_m * fines_factor) / suppression

        if dust_index < 2.0:
            level    = "LOW"
            controls = ["Standard casing sealing sufficient"]
        elif dust_index < 6.0:
            level    = "MEDIUM"
            controls = ["Sealed transfer point", "Bag filter or wet scrubber"]
        elif dust_index < 15.0:
            level    = "HIGH"
            controls = ["Pressurised hood enclosure", "High-capacity dust extraction", "HEPA filtration"]
        else:
            level    = "SEVERE"
            controls = [
                "Fully enclosed transfer chute",
                "Negative-pressure extraction system",
                "Continuous particulate monitoring",
                "ATEX assessment if material is flammable (B11)",
            ]

        return {
            "dust_index":    round(dust_index,  2),
            "dust_risk":     level,
            "v_impact_mps":  round(v_impact,    3),
            "drop_height_m": drop_height_m,
            "fines_factor":  round(fines_factor, 3),
            "suppression":   round(suppression,  3),
            "controls":      controls,
        }

    # ── 13. Discharge chute geometry (trajectory-based, index bug fixed) ──────

    @staticmethod
    def discharge_chute_geometry(
        trajectory: list,
        belt_speed_mps: float,
        head_pulley_radius_m: float,
        bucket_width_mm: float,
    ) -> dict:
        """
        CEMA 375 §5 — Head discharge chute geometry from trajectory data.

        FIX v1.1.0: replaced trajectory.index() (fragile with duplicates) with
        enumerate() loop.  Handles any trajectory point list from DischargePhysics.

        Uses trajectory to determine:
            1. Stream landing zone (where material crosses y=0)
            2. Back-plate tangent angle at landing point
            3. Minimum spout opening width
            4. Throat velocity check (plugging risk)

        trajectory: list of (x, y) tuples from DischargePhysics.trajectory()
                    x positive = away from pulley centreline [m]
                    y positive = above head pulley centre [m]
        """
        if not trajectory or len(trajectory) < 3:
            return {"error": "Insufficient trajectory points — run DischargePhysics.trajectory() first"}

        # FIX: find first point at or below y=0 using enumerate, not .index()
        landing_idx = None
        for i, (x, y) in enumerate(trajectory):
            if y <= 0.0:
                landing_idx = i
                break

        if landing_idx is None:
            land_x, land_y = trajectory[-1]
            landing_idx    = len(trajectory) - 1
        else:
            land_x, land_y = trajectory[landing_idx]

        # Back-plate angle: gradient of trajectory at landing
        if landing_idx > 0:
            x1, y1 = trajectory[landing_idx - 1]
            x2, y2 = land_x, land_y
            dx = x2 - x1
            dy = y2 - y1
            back_angle_deg = abs(math.degrees(math.atan2(abs(dy), max(abs(dx), 1e-6))))
        else:
            back_angle_deg = 60.0

        x_release      = trajectory[0][0]
        throw_distance = land_x - x_release

        spout_width_mm  = bucket_width_mm + 100.0   # +50mm each side per CEMA §5
        v_throat        = belt_speed_mps * math.cos(math.radians(back_angle_deg))

        return {
            "land_x_m":               round(land_x,          3),
            "land_y_m":               round(land_y,          3),
            "throw_distance_m":       round(throw_distance,   3),
            "back_plate_angle_deg":   round(back_angle_deg,   1),
            "spout_width_mm":         round(spout_width_mm,   0),
            "throat_velocity_mps":    round(v_throat,         3),
            "plugging_risk":          "HIGH" if v_throat < 0.5 else "LOW",
            "note": "CEMA 375 §5: back-plate should be tangent to trajectory at landing point",
        }

    # ── 14. Hood and spoon geometry (NEW) ─────────────────────────────────────

    @staticmethod
    def hood_spoon_geometry(
        belt_speed_mps: float,
        head_pulley_radius_m: float,
        centrifugal_ratio: float,
        release_angle_deg: float,
    ) -> dict:
        """
        CEMA 375 §5 — Basic hood and spoon sizing for centrifugal discharge.

        Hood: curved plate that captures the material stream leaving the pulley.
        Spoon: redirect surface that routes captured stream into the discharge chute.

        Geometry derivation:
            Release point on pulley: x_rel = r · sin(θ), y_rel = r·(1−cos θ)
            Stream velocity at release: tangential, split into vx/vy components
            Hood radius: 1.25 × pulley radius (stream clearance allowance)
            Hood angle:  30° for high-speed (CR > 1.5) → 45° for moderate-speed
            Spoon radius: 0.8 × pulley radius (tighter redirect)
            Capture efficiency: improves with CR (tighter, faster stream)

        This is a preliminary geometry guide. Detailed curved-surface CAD and
        CFD/DEM analysis are required for final fabrication drawings.
        """
        theta_rad = math.radians(release_angle_deg)

        # Release point
        rx = head_pulley_radius_m * math.sin(theta_rad)
        ry = head_pulley_radius_m * (1.0 - math.cos(theta_rad))

        # Velocity components at release (tangential to pulley)
        vx =  belt_speed_mps * math.cos(theta_rad)
        vy = -belt_speed_mps * math.sin(theta_rad)   # downward

        # Hood geometry
        hood_radius_m  = head_pulley_radius_m * 1.25
        hood_angle_deg = 30.0 if centrifugal_ratio > 1.5 else 45.0

        # Spoon geometry
        spoon_radius_m  = head_pulley_radius_m * 0.80
        spoon_angle_deg = 55.0 if centrifugal_ratio > 2.0 else 65.0

        # Simplified capture efficiency — higher CR = tighter, more predictable stream
        capture_eff = round(min(0.95, 0.72 + centrifugal_ratio * 0.08), 2)

        return {
            "hood_radius_m":      round(hood_radius_m,  3),
            "hood_angle_deg":     hood_angle_deg,
            "spoon_radius_m":     round(spoon_radius_m, 3),
            "spoon_angle_deg":    spoon_angle_deg,
            "capture_efficiency": capture_eff,
            "release_x_m":        round(rx, 4),
            "release_y_m":        round(ry, 4),
            "stream_vx_mps":      round(vx, 3),
            "stream_vy_mps":      round(vy, 3),
            "note": (
                "Preliminary sizing only. "
                "Detailed CAD + DEM/CFD analysis required for fabrication drawings."
            ),
        }

    # ── 15. Integrated design summary — recommendations engine (NEW) ──────────

    @staticmethod
    def design_summary(
        material: dict,
        capacity_tph: float,
        velocity_mps: float,
        drop_height_m: float = 1.0,
        chute_angle_deg: float | None = None,
        chute_width_m:  float | None = None,
        chute_height_m: float | None = None,
    ) -> dict:
        """
        CEMA 375 §5 — Integrated chute design output with recommendations.

        Runs all sub-models and assembles a structured result for the
        report generator, UI components, and telemetry planning.

        Parameters
        ----------
        material       : dict from MATERIALS database
        capacity_tph   : design capacity [t/h]
        velocity_mps   : belt/material entry velocity [m/s]
        drop_height_m  : free-fall height at transfer point [m]
        chute_angle_deg: actual proposed chute angle — if None, uses minimum
        chute_width_m  : chute opening width [m] — needed for capacity check
        chute_height_m : chute opening height [m] — needed for capacity check

        Returns
        -------
        {
            "performance":       { angle adequacy, flow regime },
            "maintenance":       { wear, liner, plugging risk },
            "telemetry":         { recommended sensor list },
            "recommendations":   [ actionable text strings ],
        }
        """
        # Compute minimum angle
        angle_info  = ChuteFlowEngine.chute_angle(material)
        angle_min   = angle_info["angle_min_deg"]
        chute_angle = chute_angle_deg if chute_angle_deg is not None else angle_min

        # Run all sub-models
        regime   = ChuteFlowEngine.flow_regime_classification(material, chute_angle)
        plugging = ChuteFlowEngine.plugging_probability(material)
        dust     = ChuteFlowEngine.dust_risk(material, velocity_mps, drop_height_m)
        wear     = ChuteFlowEngine.chute_wear_rate(material, velocity_mps)
        liner    = ChuteFlowEngine.chute_liner_selection(material, velocity_mps)

        # Optional capacity check
        cap_check = None
        if chute_width_m and chute_height_m:
            density = material.get("rho_loose", 1000.0)
            cap_check = ChuteFlowEngine.chute_capacity_check(
                capacity_tph, density, chute_width_m, chute_height_m, velocity_mps
            )

        # Telemetry sensor recommendations
        sensors = []
        if regime["regime"] in ("FUNNEL_FLOW", "PLUGGING_RISK"):
            sensors += ["plug_detection_switch", "chute_vibration_sensor"]
        if dust["dust_risk"] in ("HIGH", "SEVERE"):
            sensors += ["particulate_monitor", "dust_extraction_pressure"]
        if wear["wear_rating"] in ("HIGH", "SEVERE"):
            sensors += ["liner_wear_indicator"]
        if plugging["plugging_risk"] in ("HIGH", "SEVERE"):
            sensors += ["flow_sensor_acoustic", "chute_blockage_detector"]
        hazard_codes = material.get("hazard_codes", [])
        if "B10" in hazard_codes or "B11" in hazard_codes:
            sensors += ["atex_gas_detector", "explosion_vent_rupture_disc"]

        # Actionable recommendations — ordered by severity
        recs = []

        # Angle adequacy
        if chute_angle < angle_min:
            recs.append(
                f"CRITICAL — Increase chute angle to ≥ {angle_min}° "
                f"(current {chute_angle:.0f}° < wall-friction minimum {angle_info['phi_wall_deg']:.0f}° + {angle_info['margin_deg']:.0f}° margin)."
            )

        # Flow regime
        if regime["regime"] == "PLUGGING_RISK":
            recs.append(
                f"CRITICAL — Flow regime is PLUGGING RISK at {chute_angle:.0f}°. "
                f"Increase above funnel-flow threshold {regime['theta_funnel_flow_deg']:.0f}°."
            )
        elif regime["regime"] == "FUNNEL_FLOW":
            recs.append(
                f"Steepen to {regime['theta_mass_flow_deg']:.0f}° for mass flow; "
                "or add vibrators/air cannons to prevent side build-up."
            )

        # Plugging
        if plugging["plugging_risk"] in ("HIGH", "SEVERE"):
            recs.append(
                f"Plugging index {plugging['plugging_index']:.2f} ({plugging['plugging_risk']}) — "
                + plugging["recommendation"]
            )

        # Capacity
        if cap_check and cap_check["status"] == "fail":
            recs.append(
                f"Chute loading {cap_check['loading_pct']:.0f}% > 60% — increase chute cross-section "
                f"(required area {cap_check['A_required_m2']:.4f} m², actual {cap_check['A_actual_m2']:.4f} m²)."
            )
        elif cap_check and cap_check["status"] == "warn":
            recs.append(
                f"Chute loading {cap_check['loading_pct']:.0f}% — monitor for surging under peak flow."
            )

        # Dust
        if dust["dust_risk"] in ("HIGH", "SEVERE"):
            for ctrl in dust["controls"]:
                recs.append(f"Dust ({dust['dust_risk']}): {ctrl}")

        # Wear and liner
        if wear["wear_rating"] in ("HIGH", "SEVERE"):
            recs.append(
                f"Wear index {wear['wear_index']:.1f} ({wear['wear_rating']}) — "
                f"specify {liner['liner_name']} ({liner['liner_grade']}), {liner['thickness_mm']} mm thick."
            )
        elif wear["wear_rating"] == "MEDIUM":
            recs.append(
                f"Wear index {wear['wear_index']:.1f} (MEDIUM) — "
                f"{liner['liner_name']} liner recommended."
            )

        return {
            "performance": {
                "chute_angle_deg":   chute_angle,
                "min_angle_deg":     angle_min,
                "angle_adequate":    chute_angle >= angle_min,
                "governed_by":       angle_info["governed_by"],
                "phi_wall_deg":      angle_info["phi_wall_deg"],
                "flow_regime":       regime["regime"],
                "mass_flow_angle_deg": regime["theta_mass_flow_deg"],
                "capacity_check":    cap_check,
            },
            "maintenance": {
                "wear_index":         wear["wear_index"],
                "wear_rating":        wear["wear_rating"],
                "liner_material":     liner["liner_name"],
                "liner_grade":        liner["liner_grade"],
                "liner_thickness_mm": liner["thickness_mm"],
                "plugging_risk":      plugging["plugging_risk"],
                "plugging_index":     plugging["plugging_index"],
                "dust_risk":          dust["dust_risk"],
                "dust_index":         dust["dust_index"],
            },
            "telemetry": {
                "recommended_sensors": list(dict.fromkeys(sensors)),  # dedup, order preserved
            },
            "recommendations": recs,
        }