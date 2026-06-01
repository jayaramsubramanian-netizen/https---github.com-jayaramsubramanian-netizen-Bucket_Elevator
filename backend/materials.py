"""
VECTRIX™ — Material Behaviour Engine
Aligned with ANSI/CEMA 550-2020 "Classification and Definitions of Bulk Materials"

CHANGES FROM ORIGINAL
─────────────────────
1. moisture handling: CEMA 550 §A-15 defines moisture as % by weight (0–100),
   not a decimal (0–1). Original code treated it as decimal, making the
   moisture penalty 100× too sensitive (e.g. wheat at 12% moisture was
   treated as 1200% moisture). Fixed: all methods now expect moisture_pct.

2. cohesion handling: CEMA 550 §A-10 defines cohesion qualitatively.
   Mapped to numeric scale: None=0.0, Slight=0.2, Moderate=0.5, Extreme=1.0.
   Original used a 0–1 float with no defined scale — preserved but documented.

3. Added CEMA 550 material code decoder: parse the standard code string
   (e.g. "45B225BF") into its component fields for display and DB storage.

4. Added hazard flag checks for ATEX / NEC Class II design decisions,
   referencing CEMA 550 §B-10 (explosive) and §B-11 (flammable).

5. stream_spread_factor(): new method — physically scales discharge stream
   spread based on material flowability and moisture per CEMA 550 §A-12.
"""

import math


# ── CEMA 550 §A-10 Cohesion numeric mapping ──────────────────────────────────
COHESION_NONE     = 0.00   # e.g. dry sand, grain
COHESION_SLIGHT   = 0.20   # e.g. slightly damp coal
COHESION_MODERATE = 0.50   # e.g. moist clay-bearing ore
COHESION_EXTREME  = 1.00   # e.g. wet cement, sticky fly ash

# ── CEMA 550 §2.3 Flowability code to numeric ────────────────────────────────
FLOWABILITY_VERY_FREE = 1   # e.g. dry granular grain
FLOWABILITY_FREE      = 2   # e.g. wheat, corn
FLOWABILITY_AVERAGE   = 3   # e.g. coal, salt
FLOWABILITY_POOR      = 4   # e.g. cement, clinker, wet fly ash


class MaterialBehaviorEngine:

    @staticmethod
    def flowability_index(material) -> float:
        """
        Dimensionless flowability index [0–1], higher = flows more freely.
        Based on CEMA 550 §A-10 (cohesion) and §A-3 (internal friction).

        material.cohesion         : float 0.0–1.0 (use COHESION_* constants)
        material.internal_friction_deg : float, degrees
        """
        cohesion_factor  = max(0.1, 1.0 - material.cohesion)
        friction_factor  = math.cos(math.radians(material.internal_friction_deg))
        return cohesion_factor * friction_factor

    @staticmethod
    def bucket_fill_efficiency(material, elevator_type: str) -> float:
        """
        CEMA 375 §4 / CEMA 550 §A-12 — Bucket fill factor (η) [0.35–0.95].

        FIX: moisture_pct is now % by weight (CEMA 550 §A-15).
        Original used material.moisture as decimal → 100× error.

        elevator_type: "continuous" or "centrifugal"
        material.cohesion     : float 0.0–1.0
        material.moisture_pct : float 0–100 (% by weight)
        """
        base = 0.85 if elevator_type == "continuous" else 0.65

        cohesion_penalty = material.cohesion * 0.10
        # moisture_pct is 0–100; penalty scaled so 20% moisture = 0.10 penalty
        moisture_penalty = (material.moisture_pct / 100.0) * 0.50

        efficiency = base - cohesion_penalty - moisture_penalty
        return max(0.35, min(0.95, efficiency))

    @staticmethod
    def rollback_factor(material) -> float:
        """
        Factor accounting for material rollback tendency on the return run.
        Higher cohesion and moisture increase rollback risk.

        FIX: moisture_pct in % (CEMA 550 §A-15), not decimal.
        Original: material.moisture * 0.15 with decimal → now /100 * 0.15
        """
        moisture_contribution = (material.moisture_pct / 100.0) * 0.15
        cohesion_contribution  = material.cohesion * 0.20
        return 1.0 + moisture_contribution + cohesion_contribution

    @staticmethod
    def chute_friction(material) -> float:
        """
        CEMA 550 §A-2 — Wall friction coefficient (tan of external friction angle).
        Used for chute angle design in ChuteFlowEngine.
        material.internal_friction_deg approximates external friction for
        smooth steel chute surfaces (conservative).
        """
        return math.tan(math.radians(material.internal_friction_deg))

    @staticmethod
    def stream_spread_factor(material, speed: float) -> float:
        """
        NEW — CEMA 550 §A-12 / CEMA 375 §3.
        Discharge stream spread factor — scales the physical spread of
        material leaving the head pulley based on flowability and speed.

        Free-flowing, low-cohesion materials spread more at high speed.
        Cohesive, moist materials tend to stay in a tighter stream.

        Returns spread multiplier (multiply by bucket projection to get
        estimated stream half-width in metres).
        """
        # Base: 50% of bucket projection as spread
        base_spread = 0.50
        # More flowable = more spread; cohesive = tighter stream
        flow_factor = MaterialBehaviorEngine.flowability_index(material)
        # Speed term: v²/g contribution (same as our physics engine formula)
        speed_factor = 0.05 * (speed ** 2) / 9.81
        return base_spread * flow_factor + speed_factor

    @staticmethod
    def is_explosive_or_flammable(material) -> bool:
        """
        CEMA 550 §B-10 / §B-11 — Check if material requires
        ATEX / NEC Class II design (anti-static belt, earthed casing).
        material.hazard_codes: list of CEMA B-series strings e.g. ["B10", "B11"]
        """
        codes = getattr(material, "hazard_codes", [])
        return "B10" in codes or "B11" in codes

    @staticmethod
    def is_aeration_risk(material) -> bool:
        """
        CEMA 550 §B-1 — Aerates/fluidises easily (cement, fly ash).
        Requires dust control and venting at head and boot.
        """
        codes = getattr(material, "hazard_codes", [])
        return "B1" in codes

    @staticmethod
    def decode_cema_code(code: str) -> dict:
        """
        ANSI/CEMA 550-2020 Chapter II — Decode a CEMA material code string.
        Format: [bulk_density_code][size_code][flowability][abrasive][hazards]
        Example: "45B225BF"
          45  → bulk density code (45 lb/ft³ = ~720 kg/m³)
          B   → size code (1/8″–1/2″ granular)
          2   → flowability (Free)
          2   → abrasive code
          5   → (part of abrasive or hazard)
          BF  → hazard codes (B=builds up, F=flammable)
        Returns a best-effort dict; full decode requires the CEMA 550 tables.
        """
        if not code or len(code) < 3:
            return {"raw": code, "note": "Code too short to decode"}
        return {
            "raw":            code,
            "bulk_density_code": code[:2] if code[:2].isdigit() else code[:3],
            "size_code":      next((c for c in code if c.isalpha()), "?"),
            "full_code":      code,
            "note":           "Refer to ANSI/CEMA 550-2020 Table 7 for full decode",
        }
