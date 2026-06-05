"""
VECTRIX™ — Material Behaviour Engine
ANSI/CEMA 550-2020 "Classification and Definitions of Bulk Materials"

v1.1.0 — Dict-Compatible Rewrite + Solver Integration API
─────────────────────────────────────────────────────────────────────────────
BREAKING CHANGES FROM v1.0.0
─────────────────────────────────────────────────────────────────────────────
1. DICT ACCESS — All methods now accept plain dicts from the materials database.
   v1.0.0 used attribute access (material.cohesion, material.internal_friction_deg)
   which crashed on every call because MATERIALS stores plain dicts, not objects.
   All methods now use material.get("field", default) throughout.

   Field name mapping (old → new):
     material.cohesion              → material.get("cohesion", COHESION_SLIGHT)
     material.internal_friction_deg → material.get("angle_internal_friction", 35.0)
     material.moisture_pct          → material.get("moisture_pct", 0.0)
     material.hazard_codes          → material.get("hazard_codes", [])

2. CHUTE FRICTION — chute_friction() now prefers the database field
   "wall_friction_deg" (material-to-steel) over the internal friction angle.
   CEMA research shows wall friction ≈ 0.55–0.70 × internal friction for
   smooth steel; the database captures this directly.

3. FLOWABILITY INDEX — documented as VECTRIX Flowability Index (VFI), not a
   CEMA equation. CEMA 550 §2.3 provides qualitative classifications only;
   the numeric index is a VECTRIX internal derivation for comparative use.

4. NEW METHODS — Solver integration API for solve_elevator():
     recommended_fill_pct(material, elevator_type)
     effective_cr_threshold(material)
     hazard_summary(material)
     apply_to_solver(material, elevator_type)

5. MOISTURE UNITS — Confirmed % by weight (0–100), not decimal.
   CEMA 550 §A-15 uses % by weight throughout.
─────────────────────────────────────────────────────────────────────────────
"""

import math


# ── CEMA 550 §A-10 — Cohesion numeric mapping ─────────────────────────────────
COHESION_NONE     = 0.00   # dry sand, granular grain  → flows freely
COHESION_SLIGHT   = 0.20   # damp coal, salt
COHESION_MODERATE = 0.50   # cement, moist clay-bearing ore
COHESION_EXTREME  = 1.00   # wet cement, sticky fly ash, filter cake

# ── CEMA 550 §2.3 — Flowability class codes ───────────────────────────────────
FLOWABILITY_VERY_FREE = 1   # Pellets, dry spherical grain
FLOWABILITY_FREE      = 2   # Wheat, corn, dry sand
FLOWABILITY_AVERAGE   = 3   # Coal, salt, gypsum
FLOWABILITY_POOR      = 4   # Cement, clinker, damp fines


class MaterialBehaviorEngine:
    """
    Applies CEMA 550-2020 material classification properties to predict
    bucket elevator behaviour.  All methods accept plain dict materials
    from the VECTRIX materials database.

    Integration pattern (in solve_elevator):
        behavior = MaterialBehaviorEngine.apply_to_solver(mat, "centrifugal")
        # then use behavior["recommended_fill_pct"], behavior["effective_cr"], etc.
    """

    # ── VECTRIX Flowability Index (VFI) ───────────────────────────────────────

    @staticmethod
    def flowability_index(material: dict) -> float:
        """
        VECTRIX Flowability Index (VFI) — dimensionless [0–1].
        Higher value = flows more freely.

        Not a CEMA equation — CEMA 550 §2.3 provides qualitative classes only.
        VFI is a VECTRIX internal index for comparative use across the engine.

        Derivation:
            VFI = (1 - cohesion) × cos(internal_friction)
            • Cohesion term: reduces flowability for sticky materials
            • Friction term: reduces flowability for high-friction powders

        Args:
            material: dict from MATERIALS database
        Returns:
            VFI in range [0.05, 1.0]
        """
        cohesion = material.get("cohesion", COHESION_SLIGHT)
        friction_deg = material.get("angle_internal_friction", 35.0)
        cohesion_factor = max(0.05, 1.0 - cohesion)
        friction_factor = math.cos(math.radians(friction_deg))
        return round(cohesion_factor * friction_factor, 4)

    # ── Bucket fill prediction ─────────────────────────────────────────────────

    @staticmethod
    def bucket_fill_efficiency(material: dict, elevator_type: str = "centrifugal") -> float:
        """
        Predicted bucket fill efficiency (η) — fraction of rated bucket volume
        actually achieved [0.35–0.95].

        Starts from CEMA §6 fill factor in the material database
        (bucket_fill_factor), then applies moisture and cohesion corrections.

        CEMA 550 §A-15: moisture_pct is % by weight (0–100).
        CEMA 375 §6: fill factor depends on elevator type and material class.

        Args:
            material:       dict from MATERIALS database
            elevator_type:  "continuous" | "centrifugal" (default)
        Returns:
            fill efficiency as a fraction [0.35–0.95]
        """
        # CEMA §6 table base — fall back to type default if not in DB
        if elevator_type == "continuous":
            base = material.get("bucket_fill_factor", 0.85)
        else:
            base = material.get("bucket_fill_factor", 0.75)

        cohesion     = material.get("cohesion", COHESION_SLIGHT)
        moisture_pct = material.get("moisture_pct", 0.0)

        # Cohesion penalty: 0–10% reduction  (cohesion=1.0 → −10%)
        cohesion_penalty = cohesion * 0.10
        # Moisture penalty: 0–20% reduction  (moisture=40% → −10% fill)
        moisture_penalty = min(moisture_pct / 100.0, 0.40) * 0.50

        efficiency = base - cohesion_penalty - moisture_penalty
        return round(max(0.35, min(0.95, efficiency)), 3)

    @staticmethod
    def recommended_fill_pct(material: dict, elevator_type: str = "centrifugal") -> float:
        """
        Recommended fill percentage (0–100 scale) to expose in the solver output.
        Converts bucket_fill_efficiency to a percentage for display.

        This does NOT override the user-entered inp.fill_pct in the solver —
        it is advisory output shown alongside the design result so engineers can
        see whether the user's fill assumption matches material behaviour.

        Args:
            material:       dict from MATERIALS database
            elevator_type:  "continuous" | "centrifugal"
        Returns:
            recommended fill as percentage [35.0–95.0]
        """
        return MaterialBehaviorEngine.bucket_fill_efficiency(material, elevator_type) * 100.0

    # ── Discharge / centrifugal behaviour ─────────────────────────────────────

    @staticmethod
    def rollback_factor(material: dict) -> float:
        """
        Material rollback tendency multiplier [1.0–1.50].
        Accounts for cohesion and moisture increasing the CR needed for clean
        centrifugal discharge.

        Usage in solve_elevator():
            rollback = MaterialBehaviorEngine.rollback_factor(mat)
            cr_effective = cr / rollback      # effective CR for this material
            # Warn if cr_effective < 1.0 even though nominal cr ≥ 1.0

        CEMA 550 §A-12: sticky and moist materials retain on the belt side
        longer than dry granular materials, requiring higher CR for clean release.

        Args:
            material: dict from MATERIALS database
        Returns:
            rollback multiplier ≥ 1.0
        """
        moisture_pct = material.get("moisture_pct", 0.0)
        cohesion     = material.get("cohesion", COHESION_SLIGHT)
        moisture_contribution = (moisture_pct / 100.0) * 0.20
        cohesion_contribution = cohesion * 0.30
        return round(1.0 + moisture_contribution + cohesion_contribution, 4)

    @staticmethod
    def effective_cr_threshold(material: dict) -> float:
        """
        Effective minimum CR threshold for clean centrifugal discharge.
        Standard CEMA: CR ≥ 1.0.  Cohesive/moist materials need CR higher
        than 1.0 to overcome surface adhesion and achieve clean bucket release.

        effective_cr_threshold = rollback_factor × 1.0
        If the actual CR < effective_cr_threshold, rollback / retention warning.

        Args:
            material: dict from MATERIALS database
        Returns:
            effective CR threshold [1.0–1.50]
        """
        return MaterialBehaviorEngine.rollback_factor(material)

    @staticmethod
    def stream_spread_factor(material: dict, speed: float) -> float:
        """
        Discharge stream spread multiplier — scales the physical spread of material
        leaving the head pulley.

        CEMA 550 §A-12 / CEMA 375 §3.
        Free-flowing, low-cohesion materials spread more at high speed.
        Cohesive or moist materials stay in a tighter stream.

        The current physics.py uses a fixed 0.5 spread factor ignoring material
        type.  Replacing with this function makes stream spread material-dependent.

        Args:
            material: dict from MATERIALS database
            speed:    belt speed [m/s]
        Returns:
            spread multiplier (multiply by bucket projection to get estimated
            stream half-width in metres)
        """
        vfi = MaterialBehaviorEngine.flowability_index(material)
        base_spread  = 0.50
        speed_factor = 0.05 * (speed ** 2) / 9.81
        # Free-flowing: full spread; cohesive: reduced spread × VFI
        return round(base_spread * vfi + speed_factor, 4)

    # ── Chute design ──────────────────────────────────────────────────────────

    @staticmethod
    def chute_friction(material: dict) -> float:
        """
        Material-to-steel wall friction coefficient (tan φ_wall).
        Used for minimum chute angle design in ChuteFlowEngine.

        CEMA 550 §A-2: wall friction (external) < internal friction.
        Typical ratio: φ_wall ≈ 0.55–0.70 × φ_internal for smooth steel.

        Priority:
          1. Use "wall_friction_deg" if stored in the material dict (preferred).
          2. Fall back to 0.65 × internal friction angle (CEMA ratio, smooth steel).

        Args:
            material: dict from MATERIALS database
        Returns:
            wall friction coefficient [dimensionless] = tan(φ_wall)
        """
        if "wall_friction_deg" in material and material["wall_friction_deg"] > 0:
            phi = material["wall_friction_deg"]
        else:
            phi_internal = material.get("angle_internal_friction", 35.0)
            phi = phi_internal * 0.65   # CEMA smooth-steel approximation
        return round(math.tan(math.radians(phi)), 4)

    @staticmethod
    def minimum_chute_angle(material: dict) -> float:
        """
        Minimum chute angle for reliable gravity flow [degrees].
        CEMA 550 §A-2: angle must exceed wall friction angle.
        With safety margin of +5° for surging and pulsating flow.

        Args:
            material: dict from MATERIALS database
        Returns:
            minimum chute angle [degrees]
        """
        if "wall_friction_deg" in material and material["wall_friction_deg"] > 0:
            phi_wall = material["wall_friction_deg"]
        else:
            phi_internal = material.get("angle_internal_friction", 35.0)
            phi_wall = phi_internal * 0.65
        return round(phi_wall + 5.0, 1)

    # ── Hazard detection ──────────────────────────────────────────────────────

    @staticmethod
    def is_explosive_or_flammable(material: dict) -> bool:
        """
        CEMA 550 §B-10 (explosive dust) / §B-11 (flammable vapour).
        Triggers ATEX / NEC Class II design requirements:
        anti-static belt, earth bonding, explosion venting.
        """
        codes = material.get("hazard_codes", [])
        return "B10" in codes or "B11" in codes

    @staticmethod
    def is_aeration_risk(material: dict) -> bool:
        """
        CEMA 550 §B-1 — Material aerates / fluidises easily (cement, fly ash).
        Requires dust control, boot venting, and head section sealing.
        """
        codes = material.get("hazard_codes", [])
        return "B1" in codes

    @staticmethod
    def is_corrosive(material: dict) -> bool:
        """CEMA 550 §B-4 — Corrosive to steel."""
        return "B4" in material.get("hazard_codes", [])

    @staticmethod
    def is_hygroscopic(material: dict) -> bool:
        """CEMA 550 §B-8 — Absorbs moisture (affects flowability and caking)."""
        return "B8" in material.get("hazard_codes", [])

    @staticmethod
    def hazard_summary(material: dict) -> dict:
        """
        Structured hazard flag summary for display in the UI and solver checks.

        Returns:
            dict with boolean flags and the raw code list.
            "atex_required": True → ATEX/NEC Class II design required
            "stainless_recommended": True → 316L or duplex casing/buckets
            "dust_control_required": True → sealed casing, boot vent, filter
        """
        codes = material.get("hazard_codes", [])
        explosive  = "B10" in codes
        flammable  = "B11" in codes
        aerates    = "B1"  in codes
        corrosive  = "B4"  in codes
        hygroscopic= "B8"  in codes
        biohazard  = "B5"  in codes
        return {
            "explosive":            explosive,
            "flammable":            flammable,
            "aerates":              aerates,
            "corrosive":            corrosive,
            "hygroscopic":          hygroscopic,
            "biohazard":            biohazard,
            "atex_required":        explosive or flammable,
            "dust_control_required":aerates or flammable,
            "stainless_recommended":corrosive,
            "anti_static_belt":     explosive or flammable,
            "bearing_temp_monitor": explosive,
            "codes":                codes,
        }

    # ── Solver integration ────────────────────────────────────────────────────

    @staticmethod
    def apply_to_solver(material: dict, elevator_type: str = "centrifugal") -> dict:
        """
        Single call that returns all material behaviour corrections for
        use in solve_elevator().  Avoids calling each method separately.

        Usage in solve_elevator():

            mat_behavior = MaterialBehaviorEngine.apply_to_solver(mat, "centrifugal")
            # Expose in output:
            result["mat_behavior"] = mat_behavior
            # Use for checks:
            if cr < mat_behavior["effective_cr_threshold"]:
                checks.append(warn("Rollback risk for this material even above CR 1.0"))
            # Advisory fill:
            result["recommended_fill_pct"] = mat_behavior["recommended_fill_pct"]

        Args:
            material:       dict from MATERIALS database
            elevator_type:  "continuous" | "centrifugal"
        Returns:
            dict of behaviour parameters for the solver and UI
        """
        eff         = MaterialBehaviorEngine.bucket_fill_efficiency(material, elevator_type)
        rollback    = MaterialBehaviorEngine.rollback_factor(material)
        vfi         = MaterialBehaviorEngine.flowability_index(material)
        hazards     = MaterialBehaviorEngine.hazard_summary(material)
        wall_mu     = MaterialBehaviorEngine.chute_friction(material)
        min_chute   = MaterialBehaviorEngine.minimum_chute_angle(material)
        cr_thresh   = MaterialBehaviorEngine.effective_cr_threshold(material)

        return {
            # Fill
            "fill_efficiency":       eff,
            "recommended_fill_pct":  round(eff * 100.0, 1),
            # Discharge
            "vfi":                   vfi,
            "rollback_factor":       rollback,
            "effective_cr_threshold":cr_thresh,
            # Chute
            "wall_friction_coeff":   wall_mu,
            "minimum_chute_angle_deg":min_chute,
            # Hazards
            "hazards":               hazards,
            # Advisory
            "abrasion_class":        material.get("abr_code", 3),
            "flowability_class":     material.get("flowability", 3),
        }

    # ── CEMA 550 material code decoder ────────────────────────────────────────

    @staticmethod
    def decode_cema_code(code: str) -> dict:
        """
        ANSI/CEMA 550-2020 Chapter II — Best-effort decode of a CEMA material code.
        Format: [bulk_density_code][size_code][flowability][abrasive][hazard_letters]
        Example: "45B225BF"
          45  → bulk density code (~720 kg/m³)
          B   → size code (1/8″–1/2″ granular)
          2   → flowability class (Free)
          2   → abrasive index
          BF  → hazard codes

        NOTE: Full decode requires the 15+ tables in CEMA 550.
        This method returns a best-effort decomposition for display only.
        Do not use for engineering calculations.
        """
        if not code or len(code) < 3:
            return {"raw": code, "note": "Code too short to decode"}
        # Density: leading digits
        density_str = ""
        for ch in code:
            if ch.isdigit():
                density_str += ch
            else:
                break
        rest = code[len(density_str):]
        # Size code: first alpha character
        size_code = rest[0] if rest and rest[0].isalpha() else "?"
        rest2 = rest[1:] if rest else ""
        return {
            "raw":                code,
            "bulk_density_code":  density_str,
            "size_code":          size_code,
            "remainder":          rest2,
            "full_code":          code,
            "note": "Best-effort parse only — refer to ANSI/CEMA 550-2020 Table 7",
        }