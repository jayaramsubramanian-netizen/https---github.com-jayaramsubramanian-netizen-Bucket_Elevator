"""
VECTRIX™ — CEMA No. 375-2017 Compliant Bucket Elevator Physics Engine
AKSHAYVIPRA EL-MEC · VECTOMEC™ Module

v1.2.0 — Critical Engineering Fixes + Material Behaviour Integration
─────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1.1.0
─────────────────────────────────────────────────────────────────────────────
1. FIX  Materials imported from materials.py (400+ entries).
        Inline 16-material MATERIALS list removed.
        get_material() now delegates to materials.get_material().

2. FIX  release_angle_deg() removed from this module.
        v1.1.0 had TWO inconsistent release angle implementations:
          Here:        θ = acos(g·r / v²)  = acos(1/CR)  ← correct
          physics.py:  θ = acos(rg / v²)   = acos(1/CR)  ← also correct after §3 fix
        Having two sources breaks the single-source-of-truth principle.
        Now: trajectory, CR, θ_rel all delegate to DischargePhysics exclusively.

3. FIX  PIW / belt weight: was hardcoded 1.5 kg/m² (5–10× too low).
        Now uses BELT_WEIGHT_DEFAULT = 8.0 kg/m² from constants.py.
        Impacts: T2, shaft loads, bearing loads, startup inertia.

4. FIX  Bucket weight: was estimated as bucket["V"] * 1.5 kg (volume proxy).
        Now uses bucket["bucket_mass_kg"] (catalogue value added to BUCKET_SERIES).
        Fallback: 1.5 × V for any bucket entry missing the field.
        Audit flagged this as the single largest remaining source of error.

5. FIX  Shaft geometry: A_m = 0.080, B_m = 0.400 were magic numbers.
        Now derived from belt width: span = BW_m + 0.330, asymmetric split.
        Bending moment formula corrected to beam theory M = R·A·B / span.
        (Old: M = R·A overestimated moment by a factor of A / (A·B/span).)

6. NEW  MaterialBehaviorEngine integrated into solve_elevator().
        • mat_behavior block returned in result
        • effective_cr_threshold check added (CR rollback for cohesive materials)
        • recommended_fill_pct advisory in output
        • hazard flags drive ATEX / dust-control check messages
        • stream_spread_factor used in trajectory envelope

7. FIX  run_optimizer() updated with same PIW and bucket weight fixes.

─────────────────────────────────────────────────────────────────────────────
"""

import math
from typing import List, Dict

try:
    from .models import BucketElevatorInput, OptimizerRequest
except ImportError:
    from models import BucketElevatorInput, OptimizerRequest

# ── Engine modules ────────────────────────────────────────────────────────────
try:
    from .constants import (
        CEMA_MAX_SHAFT_SLOPE, SHAFT_Su_PA, SHAFT_Ka, SHAFT_Kc, SHAFT_Kd,
        SHAFT_E_PA, LEQ_DEFAULT, CEFF_BELT, BELT_WEIGHT_DEFAULT,
    )
except ImportError:
    from constants import (
        CEMA_MAX_SHAFT_SLOPE, SHAFT_Su_PA, SHAFT_Ka, SHAFT_Kc, SHAFT_Kd,
        SHAFT_E_PA, LEQ_DEFAULT, CEFF_BELT, BELT_WEIGHT_DEFAULT,
    )
try:
    from .physics import DischargePhysics
except ImportError:
    from physics import DischargePhysics
try:
    from .structural import StructuralStressEngine
except ImportError:
    from structural import StructuralStressEngine
try:
    from .dynamics import DynamicLoadEngine
except ImportError:
    from dynamics import DynamicLoadEngine
try:
    from .chute_flow import ChuteFlowEngine
except ImportError:
    from chute_flow import ChuteFlowEngine

# ── Material database (400+ entries) ─────────────────────────────────────────
try:
    from .materials_lookup import (
        MATERIALS,
        get_material as _materials_get,
        search_materials,
        list_categories,
        materials_by_category,
        material_count,
    )
except ImportError:
    from materials_lookup import (  # type: ignore[no-redef]
        MATERIALS,
        get_material as _materials_get,
        search_materials,
        list_categories,
        materials_by_category,
        material_count,
    )
try:
    from .root_cause import analyse as _rca
except ImportError:
    try:
        from root_cause import analyse as _rca
    except ImportError:
        def _rca(results, inputs):  # type: ignore[misc]
            """Stub — deploy root_cause.py to enable root cause analysis."""
            return []

try:
    from .bom import generate_bom  # type: ignore[assignment]
except ImportError:
    try:
        from bom import generate_bom  # type: ignore[assignment]
    except ImportError:
        def generate_bom(results, inputs):  # type: ignore[misc]
            """Stub — deploy bom.py to enable full BOM generation."""
            return None

try:
    from .reliability import maintenance_schedule  # type: ignore[assignment]
except ImportError:
    try:
        from reliability import maintenance_schedule  # type: ignore[assignment]
    except ImportError:
        def maintenance_schedule(results, inputs, **kwargs):  # type: ignore[misc]
            """Stub — deploy reliability.py to enable maintenance scheduling."""
            return None

try:
    from .material_behavior import MaterialBehaviorEngine
except ImportError:
    from material_behavior import MaterialBehaviorEngine


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC MATERIAL ACCESSOR — thin wrapper keeps existing callers unchanged
# ═══════════════════════════════════════════════════════════════════════════════

def get_material(mat_id: str) -> Dict:
    """Return material dict by id.  Delegates to materials.py (400+ entries)."""
    return _materials_get(mat_id)


# ═══════════════════════════════════════════════════════════════════════════════
# CEMA 375 BUCKET SERIES
# v1.2.0: Added bucket_mass_kg — catalogue mid-range for mild steel construction.
#         Source: CEMA 375 Table 1 / manufacturer catalogues (MAXI-LIFT, TAPCO).
#         AR400 buckets ≈ 1.25–1.30 × mild steel mass.
#         Elevator type: CC = centrifugal, HF = high-capacity slow-speed.
# ═══════════════════════════════════════════════════════════════════════════════

BUCKET_SERIES = [
    # ═══════════════════════════════════════════════════════════════════════════
    # STYLE AA — Centrifugal, curved bottom, general purpose
    # Source: Martin catalog H-146. front_angle≈30°.
    # Applications: grain, aggregate, sand, coal, fertiliser, salt
    # ═══════════════════════════════════════════════════════════════════════════
    {"id":"AA_6x4",  "style":"AA","catalog":"AA 6×4",
     "W":152,"H":108,"P":102,"V":0.85,"depth_mm":108,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":2.54,"v_opt":1.78,"pitch_mm":191,"bucket_mass_kg":1.8,
     "recommended_materials":["grain","seed","chemicals"],
     "note":"Small AA — fine granular, light duty"},

    {"id":"AA_8x5",  "style":"AA","catalog":"AA 8×5",
     "W":203,"H":140,"P":127,"V":1.98,"depth_mm":140,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":2.54,"v_opt":1.78,"pitch_mm":229,"bucket_mass_kg":3.2,
     "recommended_materials":["grain","fertiliser","sand","salt"],
     "note":"Medium-small AA — grain and fine minerals"},

    {"id":"AA_10x6", "style":"AA","catalog":"AA 10×6",
     "W":254,"H":159,"P":152,"V":3.40,"depth_mm":159,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":2.03,"v_opt":1.65,"pitch_mm":279,"bucket_mass_kg":4.4,
     "recommended_materials":["grain","fertiliser","aggregate","coal"],
     "note":"Medium AA — general grain and mineral service"},

    {"id":"AA_12x7", "style":"AA","catalog":"AA 12×7",
     "W":305,"H":184,"P":178,"V":5.38,"depth_mm":184,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,"pitch_mm":305,"bucket_mass_kg":6.3,
     "recommended_materials":["wheat","corn","aggregate","coal","fertiliser"],
     "note":"Standard AA — most common grain elevator size"},

    {"id":"AA_14x8", "style":"AA","catalog":"AA 14×8",
     "W":356,"H":216,"P":203,"V":9.06,"depth_mm":216,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,"pitch_mm":356,"bucket_mass_kg":8.5,
     "recommended_materials":["wheat","corn","soybeans","aggregate"],
     "note":"Large AA — high-capacity grain/mineral"},

    {"id":"AA_16x8", "style":"AA","catalog":"AA 16×8",
     "W":406,"H":216,"P":203,"V":10.21,"depth_mm":216,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,"pitch_mm":381,"bucket_mass_kg":9.8,
     "recommended_materials":["grain","aggregate","coal"],
     "note":"Extra-wide AA"},

    {"id":"AA_18x8", "style":"AA","catalog":"AA 18×8",
     "W":457,"H":216,"P":203,"V":11.33,"depth_mm":216,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,"pitch_mm":406,"bucket_mass_kg":10.3,
     "recommended_materials":["grain","minerals","potash"],
     "note":"Wide AA — high throughput centrifugal"},

    {"id":"AA_18x10","style":"AA","catalog":"AA 18×10",
     "W":457,"H":267,"P":254,"V":17.84,"depth_mm":267,"front_angle_deg":30,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.14,"v_max":1.91,"v_opt":1.52,"pitch_mm":457,"bucket_mass_kg":13.1,
     "recommended_materials":["grain","potash","aggregate"],
     "note":"Very large AA — maximum centrifugal capacity"},

    # ═══════════════════════════════════════════════════════════════════════════
    # STYLE AC — Centrifugal, 50° front angle, Added Capacity, hooded back
    # Source: Martin catalog H-147. Mill Duty series MDC/MDB.
    # Applications: cement, clinker, ore, shale, coal, asphalt, gypsum
    # ═══════════════════════════════════════════════════════════════════════════
    {"id":"AC_12x8",  "style":"AC","catalog":"AC 12×8×8",
     "W":305,"H":216,"P":203,"V":8.58,"depth_mm":216,"front_angle_deg":50,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":0.76,"v_max":2.03,"v_opt":1.27,"pitch_mm":305,"bucket_mass_kg":11.0,
     "recommended_materials":["cement","limestone","gypsum","shale"],
     "note":"AC — 50° face for clean discharge of abrasive minerals"},

    {"id":"AC_14x8",  "style":"AC","catalog":"AC 14×8×8",
     "W":356,"H":216,"P":203,"V":10.08,"depth_mm":216,"front_angle_deg":50,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":0.76,"v_max":2.03,"v_opt":1.27,"pitch_mm":305,"bucket_mass_kg":12.2,
     "recommended_materials":["cement","clinker","ore","coal"],
     "note":"Standard mill duty AC"},

    {"id":"AC_16x8",  "style":"AC","catalog":"AC 16×8×8",
     "W":406,"H":216,"P":203,"V":11.55,"depth_mm":216,"front_angle_deg":50,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":0.76,"v_max":2.03,"v_opt":1.27,"pitch_mm":330,"bucket_mass_kg":13.6,
     "recommended_materials":["cement","clinker","ore","asphalt","coke"],
     "note":"Wide mill duty AC"},

    {"id":"AC_18x10", "style":"AC","catalog":"AC 18×10×10",
     "W":457,"H":267,"P":254,"V":19.57,"depth_mm":267,"front_angle_deg":50,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":0.76,"v_max":2.03,"v_opt":1.27,"pitch_mm":381,"bucket_mass_kg":17.6,
     "recommended_materials":["cement","clinker","limestone","bauxite"],
     "note":"Large mill duty AC"},

    {"id":"AC_20x10", "style":"AC","catalog":"AC 20×10×10",
     "W":508,"H":267,"P":254,"V":21.75,"depth_mm":267,"front_angle_deg":50,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":0.76,"v_max":2.03,"v_opt":1.27,"pitch_mm":406,"bucket_mass_kg":19.1,
     "recommended_materials":["cement","clinker","limestone","ore"],
     "note":"Extra-large mill duty AC"},

    {"id":"AC_24x10", "style":"AC","catalog":"AC 24×10×10",
     "W":610,"H":267,"P":254,"V":26.08,"depth_mm":267,"front_angle_deg":50,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":0.76,"v_max":2.03,"v_opt":1.27,"pitch_mm":457,"bucket_mass_kg":23.9,
     "recommended_materials":["cement","clinker","ore"],
     "note":"Heavy duty wide AC — high capacity mineral service"},

    # ═══════════════════════════════════════════════════════════════════════════
    # STYLE C — Centrifugal, low profile, open front, angled sides
    # Source: Martin catalog H-148.
    # Applications: sugar, salt, wet grain, clay, powders, chemicals
    # ═══════════════════════════════════════════════════════════════════════════
    {"id":"C_6x4",   "style":"C","catalog":"C 6×4×4",
     "W":152,"H":102,"P":114,"V":0.74,"depth_mm":102,"front_angle_deg":0,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.02,"v_max":3.56,"v_opt":2.03,"pitch_mm":191,"bucket_mass_kg":1.7,
     "recommended_materials":["sugar","chemicals","fine_powders"],
     "note":"Small C — fine sticky or powdered materials"},

    {"id":"C_8x4",   "style":"C","catalog":"C 8×4×4",
     "W":203,"H":102,"P":114,"V":0.99,"depth_mm":102,"front_angle_deg":0,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.02,"v_max":3.56,"v_opt":2.03,"pitch_mm":229,"bucket_mass_kg":2.0,
     "recommended_materials":["sugar","salt","clay","starch"],
     "note":"C — wet/sticky, open front for clean discharge"},

    {"id":"C_10x5",  "style":"C","catalog":"C 10×5×4",
     "W":254,"H":102,"P":127,"V":1.47,"depth_mm":102,"front_angle_deg":0,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.02,"v_max":3.05,"v_opt":2.03,"pitch_mm":254,"bucket_mass_kg":2.6,
     "recommended_materials":["sugar","salt","wet_grain","clay","chemicals"],
     "note":"Medium C — sticky/wet materials, more buckets per metre"},

    {"id":"C_14x7",  "style":"C","catalog":"C 14×7×5",
     "W":356,"H":140,"P":178,"V":3.91,"depth_mm":140,"front_angle_deg":0,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.02,"v_max":3.05,"v_opt":1.78,"pitch_mm":305,"bucket_mass_kg":5.1,
     "recommended_materials":["sugar","salt","wet_grain","clay","flour","starch"],
     "note":"Large C — high throughput wet/sticky service"},

    {"id":"C_16x7",  "style":"C","catalog":"C 16×7×5",
     "W":406,"H":140,"P":178,"V":4.47,"depth_mm":140,"front_angle_deg":0,
     "type":"CC","discharge_type":"centrifugal",
     "v_min":1.02,"v_max":3.05,"v_opt":1.78,"pitch_mm":330,"bucket_mass_kg":5.9,
     "recommended_materials":["sugar","salt","chemicals"],
     "note":"Wide C — maximum sticky-material capacity"},

    # ═══════════════════════════════════════════════════════════════════════════
    # STYLE MF — Continuous discharge, 30° medium front, gentle handling
    # Source: Martin catalog H-149. CEMA Series 700/800.
    # Applications: gypsum, cement, pellets, grain, salt, fertiliser
    # ═══════════════════════════════════════════════════════════════════════════
    {"id":"MF_10x7",  "style":"MF","catalog":"MF 10×7×11",
     "W":254,"H":295,"P":178,"V":5.10,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":295,"bucket_mass_kg":7.5,
     "recommended_materials":["cement","gypsum","pellets","grain","lime"],
     "note":"MF — medium front, gentle handling"},

    {"id":"MF_12x7",  "style":"MF","catalog":"MF 12×7×11",
     "W":305,"H":295,"P":178,"V":6.17,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":305,"bucket_mass_kg":8.4,
     "recommended_materials":["cement","gypsum","grain","fertiliser"],
     "note":"Standard MF"},

    {"id":"MF_12x8",  "style":"MF","catalog":"MF 12×8×11",
     "W":305,"H":295,"P":203,"V":7.79,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":305,"bucket_mass_kg":9.0,
     "recommended_materials":["cement","gypsum","grain","salt","aggregate"],
     "note":"Wider projection MF"},

    {"id":"MF_14x8",  "style":"MF","catalog":"MF 14×8×11",
     "W":356,"H":295,"P":203,"V":9.20,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":330,"bucket_mass_kg":10.1,
     "recommended_materials":["gypsum","cement","grain","salt","aggregate","fertiliser"],
     "note":"Medium-large MF — common industrial size"},

    {"id":"MF_16x8",  "style":"MF","catalog":"MF 16×8×11",
     "W":406,"H":295,"P":203,"V":10.62,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":356,"bucket_mass_kg":11.0,
     "recommended_materials":["cement","gypsum","aggregate","potash"],
     "note":"Large MF"},

    {"id":"MF_18x8",  "style":"MF","catalog":"MF 18×8×11",
     "W":457,"H":295,"P":203,"V":11.89,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":381,"bucket_mass_kg":12.1,
     "recommended_materials":["cement","gypsum","salt","aggregate"],
     "note":"Wide MF — high capacity continuous"},

    {"id":"MF_24x10", "style":"MF","catalog":"MF 24×10×11",
     "W":610,"H":295,"P":254,"V":24.07,"depth_mm":295,"front_angle_deg":30,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.40,"v_max":1.27,"v_opt":0.76,"pitch_mm":457,"bucket_mass_kg":17.1,
     "recommended_materials":["cement","gypsum","potash","aggregate"],
     "note":"Extra-large MF — very high capacity"},

    # ═══════════════════════════════════════════════════════════════════════════
    # STYLE HF — Continuous discharge, 45° HIGH front, greater capacity
    # Source: Martin catalog H-150. CEMA Series 700/800.
    # ~8% higher volume than MF for same width due to higher front
    # Applications: grain, cement, pellets, fertiliser, fragile materials
    # ═══════════════════════════════════════════════════════════════════════════
    {"id":"HF_10x7",  "style":"HF","catalog":"HF 10×7×11",
     "W":254,"H":295,"P":178,"V":5.38,"depth_mm":295,"front_angle_deg":45,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.50,"v_max":1.52,"v_opt":1.02,"pitch_mm":295,"bucket_mass_kg":8.0,
     "recommended_materials":["grain","pellets","fragile_granules"],
     "note":"Small HF — high front, gentle continuous discharge"},

    {"id":"HF_12x7",  "style":"HF","catalog":"HF 12×7×11",
     "W":305,"H":295,"P":178,"V":6.80,"depth_mm":295,"front_angle_deg":45,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.50,"v_max":1.52,"v_opt":1.02,"pitch_mm":305,"bucket_mass_kg":9.2,
     "recommended_materials":["wheat","corn","pellets","gypsum"],
     "note":"Standard small HF"},

    {"id":"HF_14x7",  "style":"HF","catalog":"HF 14×7×11",
     "W":356,"H":295,"P":178,"V":7.93,"depth_mm":295,"front_angle_deg":45,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.50,"v_max":1.52,"v_opt":1.02,"pitch_mm":330,"bucket_mass_kg":10.3,
     "recommended_materials":["grain","pellets","gypsum","cement"],
     "note":"Medium HF"},

    {"id":"HF_14x8",  "style":"HF","catalog":"HF 14×8×11",
     "W":356,"H":295,"P":203,"V":9.91,"depth_mm":295,"front_angle_deg":45,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.50,"v_max":1.52,"v_opt":1.02,"pitch_mm":330,"bucket_mass_kg":11.3,
     "recommended_materials":["grain","salt","cement","fertiliser"],
     "note":"Medium HF, wider projection"},

    {"id":"HF_16x8",  "style":"HF","catalog":"HF 16×8×11",
     "W":406,"H":295,"P":203,"V":11.19,"depth_mm":295,"front_angle_deg":45,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.50,"v_max":1.52,"v_opt":1.02,"pitch_mm":356,"bucket_mass_kg":11.2,
     "recommended_materials":["wheat","corn","gypsum","cement","pellets","salt","fertiliser"],
     "note":"Standard HF — most common size for grain/mineral continuous elevators"},

    {"id":"HF_18x8",  "style":"HF","catalog":"HF 18×8×11",
     "W":457,"H":295,"P":203,"V":12.83,"depth_mm":295,"front_angle_deg":45,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.50,"v_max":1.52,"v_opt":1.02,"pitch_mm":381,"bucket_mass_kg":13.2,
     "recommended_materials":["grain","gypsum","salt","fertiliser"],
     "note":"Large HF — high capacity continuous"},

    # ═══════════════════════════════════════════════════════════════════════════
    # STYLE SC — Continuous, Super Capacity, DOUBLE CHAIN only
    # Source: Martin catalog H-151, H-136.
    # Applications: cement, gypsum, limestone, coal, salt, rock
    # Very slow speed, large lump tolerance, heavy abrasive duty
    # ═══════════════════════════════════════════════════════════════════════════
    {"id":"SC_12x8",  "style":"SC","catalog":"SC 12×8×11",
     "W":305,"H":295,"P":222,"V":15.29,"depth_mm":295,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.30,"v_max":0.76,"v_opt":0.51,"pitch_mm":305,"bucket_mass_kg":13.2,
     "recommended_materials":["cement","gypsum","salt","coal","aggregate"],
     "note":"SC — double chain, very slow speed, heavy abrasive duty"},

    {"id":"SC_14x8",  "style":"SC","catalog":"SC 14×8×11",
     "W":356,"H":295,"P":222,"V":17.84,"depth_mm":295,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.30,"v_max":0.76,"v_opt":0.51,"pitch_mm":305,"bucket_mass_kg":14.1,
     "recommended_materials":["cement","limestone","gypsum","coal"],
     "note":"SC medium"},

    {"id":"SC_16x8",  "style":"SC","catalog":"SC 16×8×11",
     "W":406,"H":295,"P":222,"V":20.39,"depth_mm":295,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.30,"v_max":0.76,"v_opt":0.51,"pitch_mm":305,"bucket_mass_kg":15.4,
     "recommended_materials":["cement","limestone","gypsum","coal","rocks"],
     "note":"SC large — standard super capacity size"},

    {"id":"SC_18x8",  "style":"SC","catalog":"SC 18×8×11",
     "W":457,"H":295,"P":222,"V":22.94,"depth_mm":295,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.30,"v_max":0.76,"v_opt":0.51,"pitch_mm":305,"bucket_mass_kg":16.3,
     "recommended_materials":["cement","limestone","coal","coke"],
     "note":"SC wide"},

    {"id":"SC_20x8",  "style":"SC","catalog":"SC 20×8×11",
     "W":508,"H":295,"P":222,"V":25.49,"depth_mm":295,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.30,"v_max":0.76,"v_opt":0.51,"pitch_mm":305,"bucket_mass_kg":17.6,
     "recommended_materials":["cement","limestone","gypsum"],
     "note":"SC extra-wide"},

    {"id":"SC_20x12", "style":"SC","catalog":"SC 20×12×17",
     "W":508,"H":448,"P":324,"V":54.93,"depth_mm":448,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.25,"v_max":0.64,"v_opt":0.43,"pitch_mm":457,"bucket_mass_kg":30.4,
     "recommended_materials":["cement_clinker","limestone","rock","ore"],
     "note":"SC deep — very high capacity, large lumps up to 200mm"},

    {"id":"SC_24x12", "style":"SC","catalog":"SC 24×12×17",
     "W":610,"H":448,"P":324,"V":65.98,"depth_mm":448,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.25,"v_max":0.64,"v_opt":0.43,"pitch_mm":457,"bucket_mass_kg":34.0,
     "recommended_materials":["cement_clinker","limestone","ore"],
     "note":"SC large deep — heavy duty, very high capacity"},

    {"id":"SC_30x12", "style":"SC","catalog":"SC 30×12×17",
     "W":762,"H":448,"P":324,"V":82.40,"depth_mm":448,"front_angle_deg":35,
     "type":"HF","discharge_type":"continuous",
     "v_min":0.25,"v_max":0.64,"v_opt":0.43,"pitch_mm":457,"bucket_mass_kg":40.0,
     "recommended_materials":["cement_clinker","limestone","ore"],
     "note":"SC maximum width — highest capacity super duty"},
]

# ── Lookup maps ────────────────────────────────────────────────────────────────
_BUCKET_BY_ID   = {b["id"]: b for b in BUCKET_SERIES}
_BUCKET_BY_STYLE: dict[str, list] = {}
for _b in BUCKET_SERIES:
    _BUCKET_BY_STYLE.setdefault(_b["style"], []).append(_b)

# ── Backward-compatibility aliases ────────────────────────────────────────────
# Old bucket_id values stored in saved designs continue to resolve correctly.
_LEGACY_ALIASES: dict[str, str] = {
    "AA":   "AA_12x7",   "AA-L": "AA_18x8",
    "A":    "AA_10x6",
    "B":    "AA_10x6",   # old "Series B" was essentially an AA_10x6
    "D":    "AA_8x5",    # old "Series D" small centrifugal
    "AC":   "AC_16x8",   "AC-L": "AC_24x10",
    "C":    "C_14x7",
    "MF":   "MF_14x8",   "MF-L": "MF_24x10",
    "HF":   "HF_16x8",   "HF-L": "HF_18x8",
    "PF":   "MF_12x7",   # PF was a pellet/feed variant close to MF_12x7
    "SC":   "SC_16x8",   "SC-L": "SC_24x12",
}
for _alias, _target in _LEGACY_ALIASES.items():
    if _alias not in _BUCKET_BY_ID and _target in _BUCKET_BY_ID:
        _BUCKET_BY_ID[_alias] = _BUCKET_BY_ID[_target]

BELT_WIDTHS = [102, 127, 152, 178, 203, 254, 305, 356, 406, 457, 508, 610, 762, 914]
MOTOR_SIZES = [
    0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5,
    11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110, 132, 160, 200, 250, 315, 400,
]


# ── Chain series catalogue ─────────────────────────────────────────────────────
# Source: Martin Engineering catalog H-131 thru H-137, CEMA 375-2017 §4.
#
# wt_kg_m   : chain weight per strand per metre [kg/m]
# WL_kg     : published working load per strand [kg]
# v_max_ms  : CEMA rated maximum chain speed [m/s]
# n_strands : 1 = single-strand; 2 = double-strand (SC series only)
# pitch_mm  : chain pitch [mm]
# series    : CEMA elevator series this chain is used in

CHAIN_SERIES = [
    # ── Centrifugal / continuous small (Series 100/200/700/800) ────────────────
    {
        "id": "N102B",
        "name": "N-102B  (4\" std, single)",
        "pitch_mm": 101.6, "WL_kg": 4990,  "wt_kg_m": 1.8,
        "v_max_ms": 1.27,  "n_strands": 1,
        "series": ["100", "200"],
        "note": "Light duty centrifugal — grain, fertiliser, light minerals",
    },
    {
        "id": "S102B",
        "name": "S-102B / 6102 (4\" heavy, single)",
        "pitch_mm": 101.6, "WL_kg": 6804,  "wt_kg_m": 2.1,
        "v_max_ms": 1.27,  "n_strands": 1,
        "series": ["100", "200", "700", "800"],
        "note": "Medium duty — grain, aggregate, light mineral; 4\" pitch",
    },
    {
        "id": "S110",
        "name": "S-110 / 6110  (6\" heavy, single)",
        "pitch_mm": 152.4, "WL_kg": 12474, "wt_kg_m": 4.5,
        "v_max_ms": 1.27,  "n_strands": 1,
        "series": ["100", "200", "700", "800"],
        "note": "Heavy centrifugal / continuous — cement, aggregate, salt",
    },
    # ── Mill duty MDC (Series MDC/MDB) ─────────────────────────────────────────
    {
        "id": "ER856",
        "name": "ER-856  (6\" MDC rollerless, single)",
        "pitch_mm": 152.4, "WL_kg": 18144, "wt_kg_m": 7.5,
        "v_max_ms": 1.35,  "n_strands": 1,
        "series": ["MDC", "MDB"],
        "note": "Mill duty — cement clinker, ore, shale; rollerless reduces maintenance",
    },
    {
        "id": "ER857",
        "name": "ER-857  (6\" MDC rollerless, single)",
        "pitch_mm": 152.4, "WL_kg": 22680, "wt_kg_m": 8.5,
        "v_max_ms": 1.35,  "n_strands": 1,
        "series": ["MDC"],
        "note": "Heavy mill duty — higher working load than ER-856",
    },
    # ── Super Capacity SC (double-strand) ──────────────────────────────────────
    {
        "id": "ER859",
        "name": "ER-859  (6\" SC double)",
        "pitch_mm": 152.4, "WL_kg": 31750, "wt_kg_m": 9.5,
        "v_max_ms": 0.64,  "n_strands": 2,
        "series": ["SC"],
        "note": "SC double chain — 6\" pitch, very slow speed",
    },
    {
        "id": "C6102",
        "name": "6102-1/2  (12\" SC double)",
        "pitch_mm": 304.8, "WL_kg": 27215, "wt_kg_m": 11.0,
        "v_max_ms": 0.51,  "n_strands": 2,
        "series": ["SC"],
        "note": "SC double chain — 12\" pitch; heavy lumpy minerals",
    },
    {
        "id": "C9124",
        "name": "9124  (9\" SC double)",
        "pitch_mm": 228.6, "WL_kg": 38100, "wt_kg_m": 14.0,
        "v_max_ms": 0.64,  "n_strands": 2,
        "series": ["SC"],
        "note": "SC double chain — 9\" pitch; maximum working load",
    },
]

_CHAIN_BY_ID = {c["id"]: c for c in CHAIN_SERIES}


def select_chain_auto(
    T_pull_N:  float,
    n_strands: int   = 1,
    sf:        float = 6.0,
) -> dict:
    """
    Select the smallest chain whose working load provides the required safety factor.

    Criterion (CEMA 375 §4):
        WL [kg] × 9.81 × n_strands / T_pull_N  ≥  sf
        → WL_required = T_pull_N × sf / (9.81 × n_strands)

    Candidates are filtered to matching n_strands and sorted smallest WL first.
    Returns the heaviest chain if none meets the criterion (forces an SF check fail).
    """
    req_WL_kg  = T_pull_N * sf / (9.81 * max(n_strands, 1))
    candidates = [c for c in CHAIN_SERIES if c["n_strands"] == n_strands]
    for ch in sorted(candidates, key=lambda x: x["WL_kg"]):
        if ch["WL_kg"] >= req_WL_kg:
            return ch
    return candidates[-1] if candidates else CHAIN_SERIES[0]


def sprocket_geometry(chain_pitch_mm: float, n_teeth: int) -> dict:
    """
    Standard sprocket pitch diameter from chain pitch and tooth count.

    Formula:  PD = pitch / sin(π / n_teeth)

    Also returns the standard ANSI tooth range (10–20 teeth recommended for
    smooth operation; < 10 causes polygonal chordal action; > 24 increases
    sprocket diameter steeply).
    """
    if n_teeth < 6:
        n_teeth = 6  # hard minimum to avoid geometry error
    PD_mm = chain_pitch_mm / math.sin(math.pi / n_teeth)
    return {
        "PD_mm":   round(PD_mm, 1),
        "n_teeth": n_teeth,
        "smooth":  10 <= n_teeth <= 20,
        "note": (
            f"{n_teeth}-tooth sprocket, PD = {PD_mm:.0f} mm. "
            + ("✓ within 10–20 tooth smooth-operation range."
               if 10 <= n_teeth <= 20
               else "⚠ < 10 teeth — chordal action increases chain wear."
               if n_teeth < 10
               else "✓ > 20 teeth — large PD, verify casing head-section clearance.")
        ),
    }


def _chain_catenary_tension(
    chain_wt_kg_m: float,
    n_strands:     int,
    bucket_mass_kg: float,
    spacing_m:     float,
    H_m:           float,
) -> float:
    """
    Self-weight tension for chain elevator [N].

    Components:
    • Chain weight (both up and return strands):
          chain_wt × n_strands × 2 × H × g
    • Bucket weight (going-up strand only — return is unloaded):
          bucket_mass / spacing × H × g

    Note: material weight T1 is computed separately by
    DynamicLoadEngine.material_tension() and is the same for belt and chain.
    """
    T_chain   = chain_wt_kg_m * n_strands * 2.0 * H_m * 9.81
    T_buckets = (bucket_mass_kg / max(spacing_m, 0.001)) * H_m * 9.81
    return T_chain + T_buckets

def belt_speed(D_mm: float, n_rpm: float) -> float:
    """Head pulley rim speed [m/s].  Delegates to DischargePhysics."""
    return DischargePhysics.belt_speed(D_mm / 1000.0, n_rpm)


def centrifugal_ratio(v_ms: float, D_mm: float) -> float:
    """CEMA CR = v²/(g·r).  Delegates to DischargePhysics."""
    return DischargePhysics.centrifugal_ratio(v_ms, D_mm / 2000.0)


# NOTE: release_angle_deg() removed — use DischargePhysics directly.
# Reason: two inconsistent implementations existed (see changelog §2).
# DischargePhysics.calculate_release_point() is the single source of truth.


def discharge_trajectory(v_ms: float, D_mm: float, steps: int = 60) -> List[Dict]:
    """
    Wraps DischargePhysics.trajectory() and converts tuple output to
    {x_mm, y_mm} dicts for the REST API response.
    """
    r = D_mm / 2000.0
    pts = DischargePhysics.trajectory(v_ms, r)
    return [{"x": round(p[0] * 1000, 1), "y": round(p[1] * 1000, 1)} for p in pts]


def _shaft_geometry(BW_mm: float) -> tuple[float, float, float]:
    """
    Derive head shaft geometry from belt width.
    Replaces the hardcoded A_m=0.080, B_m=0.400 (v1.1.0 bug).

    Geometry model (simply supported shaft):
        pulley_face  = BW + 50 mm  (belt width + crown/edge allowance)
        span         = BW + 330 mm (hub + bearing + housing, 165 mm each side)
        A_m          = span × 0.45 (slightly off-centre toward drive side)
        B_m          = span - A_m

    For a 305 mm belt:  span ≈ 635 mm, A_m ≈ 286 mm, B_m ≈ 350 mm.
    For a 610 mm belt:  span ≈ 940 mm, A_m ≈ 423 mm, B_m ≈ 517 mm.

    Returns:
        span_m, A_m, B_m  — all in metres
    """
    BW_m    = BW_mm / 1000.0
    span_m  = BW_m + 0.330                  # 165 mm each side: hub+bearing+housing
    A_m     = span_m * 0.45                 # drive side (shorter arm)
    B_m     = span_m - A_m
    return span_m, A_m, B_m


def _bending_moment(R_head_N: float, A_m: float, B_m: float) -> float:
    """
    Maximum bending moment [N·m] at the pulley for a simply supported shaft
    with a single transverse point load R_head at the pulley.

    Standard beam theory:
        M_max = R_head × A × B / (A + B)   (at the load point)

    v1.1.0 used M = R_head × A_m directly — this overestimated the moment
    when A_m was the full span rather than the shorter arm to the pulley.
    """
    span = A_m + B_m
    if span < 0.001:
        return R_head_N * A_m  # degenerate fallback
    return R_head_N * A_m * B_m / span


# ═══════════════════════════════════════════════════════════════════════════════
# CAPACITY & POWER
# ═══════════════════════════════════════════════════════════════════════════════

def calc_capacity(v_ms: float, spacing_m: float, V_bucket_L: float,
                  fill_pct: float, rho_kgm3: float) -> float:
    """
    CEMA 375 §4 capacity [t/h].
    Q = (v / spacing) × V × η × ρ × 3.6
    """
    Vb_m3 = V_bucket_L / 1000.0
    eta   = fill_pct / 100.0
    return (v_ms / spacing_m) * Vb_m3 * eta * rho_kgm3 * 3.6


def calc_power_cema375(Q_th: float, H_m: float, D_boot_m: float,
                       Leq: float, Ceff: float) -> Dict:
    """
    CEMA 375 §4 — Bucket elevator shaft and drive power [kW].

    CEMA LEQ (Length Equivalency) Method — validated decomposition
    ───────────────────────────────────────────────────────────────
    CEMA 375 §4 defines total equivalent lift height as:

        H_total = H_lift + H_equiv
        H_equiv = D_boot × Leq   [m]

    H_equiv is the equivalent extra lift height accounting for boot loading
    losses (scooping, digging, material acceleration in the boot section).
    It is NOT a drive loss — it is a shaft load, just like lifting material.

        G [kg/s] = Q_th × 1000 / 3600
        P_shaft  = G × g × H_total / 1000   [kW]  — required at head shaft

    The drive efficiency factor Ceff then covers losses between motor shaft
    and head shaft:
        P_total  = P_shaft × Ceff   [kW]  — required at motor shaft

    What Ceff covers (CEMA 375 §4 Table 4-x):
        • Gearbox / shaft-mount reducer losses  (~3–5%)
        • Head shaft bearing friction           (~1–2%)
        • Belt flexure around pulleys           (~1–2%)
        • Seal drag, minor incidentals          (~1–2%)
    Typical values: 1.10–1.15 belt / 1.20–1.30 chain

    ⚠ Double-counting note (from audit):
    P_digging is a SHAFT load (material being scooped from boot).
    Ceff is a DRIVE loss (motor-to-shaft efficiency).
    They act on different parts of the power chain — no double-counting.
    The old formula (P_lift + P_digging) × Ceff is mathematically identical
    to P_shaft × Ceff since P_shaft = G×g×H_total and H_total = H_lift + H_equiv.

    Leq values by elevator type (CEMA 375 §4):
        Spaced centrifugal (most common):   6–8
        Continuous bucket:                  4–5
        Very low-speed / gravity discharge: 3–4
        High-speed, abrasive material:      10–12
        Per material: use mat["Leq_default"] for DB-sourced value.

    Parameters
    ----------
    Q_th      Design capacity [t/h]
    H_m       Elevator lift height [m]
    D_boot_m  Boot pulley diameter [m]
    Leq       CEMA length equivalency factor (dimensionless)
    Ceff      Drive efficiency factor (≥ 1.0)

    Returns
    -------
    {
        "H_equiv":      float  Equivalent boot lift height = D_boot × Leq [m]
        "H_total":      float  H_lift + H_equiv [m]
        "P_shaft":      float  Shaft power = G×g×H_total / 1000 [kW]
        "P_lift":       float  Lift component only [kW]
        "P_digging":    float  Boot loading component [kW]
        "P_drive_loss": float  Motor-to-shaft losses = P_shaft × (Ceff−1) [kW]
        "P_total":      float  Total motor input power [kW]
    }
    """
    G_kgs    = Q_th / 3.6                              # mass flow [kg/s]
    H_equiv  = D_boot_m * Leq                          # equivalent boot height [m]
    H_total  = H_m + H_equiv                           # total equivalent height [m]

    # Component breakdown (for report and UI display)
    P_lift    = G_kgs * 9.81 * H_m     / 1000.0       # lift component [kW]
    P_digging = G_kgs * 9.81 * H_equiv / 1000.0       # boot component [kW]
    P_shaft   = P_lift + P_digging                     # = G×g×H_total/1000 [kW]
    P_total   = P_shaft * Ceff                         # motor input [kW]

    return {
        "H_equiv":      round(H_equiv,   3),
        "H_total":      round(H_total,   3),
        "P_shaft":      round(P_shaft,   3),
        "P_lift":       round(P_lift,    3),
        "P_digging":    round(P_digging, 3),
        "P_drive_loss": round(P_total - P_shaft, 3),   # = P_shaft × (Ceff − 1)
        "P_total":      round(P_total,   3),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HEAD SHAFT TENSIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_headshaft_tensions(Q_th: float, H_m: float, v_ms: float,
                             bw_kg: float, bs_m: float,
                             BW_mm: float, K_takeup: float = 0.7,
                             mu: float = 0.35, wrap_deg: float = 180.0) -> Dict:
    """
    CEMA 375 §4 head shaft tension breakdown [N].

    v1.2.0 FIX: PIW uses BELT_WEIGHT_DEFAULT (8.0 kg/m²); old default was 1.5.
    v1.2.1 FIX: mu and wrap_deg now actively drive T3 via Euler-Eytelwein.
                Previously collected in models.py but never used in calculation.

    Tension path
    ────────────
    T1          material_tension()          G·g·H / v               [N]
    T2          belt_catenary_tension()     (belt + bucket) × H × g [N]
    T3_prelim   slack_side_tension()        (T1+T2) × K_takeup      [N]  preliminary
    T3_euler    euler_eytelwein_check()     T_eff / (e^μθ − 1)      [N]  minimum for no-slip
    T3          max(T3_prelim, T3_euler)                             [N]  governing

    The Euler minimum ensures the drive pulley cannot slip even if the take-up
    tension is set too low.  For most correctly-designed elevators with gravity
    take-up (K=0.7) and rubber lagging (μ=0.35, 180°), K_takeup governs.
    """
    PIW_kgm2  = BELT_WEIGHT_DEFAULT   # 8.0 kg/m²

    T1        = DynamicLoadEngine.material_tension(Q_th, H_m, v_ms)
    T2        = DynamicLoadEngine.belt_catenary_tension(BW_mm, bw_kg, bs_m, H_m, PIW_kgm2)
    T_eff     = T1 + T2
    T3_prelim = DynamicLoadEngine.slack_side_tension(T1, T2, K_takeup)

    # Euler-Eytelwein: minimum T3 to prevent drive pulley slip (CEMA 375 §4)
    euler = DynamicLoadEngine.euler_eytelwein_check(
        T_effective    = T_eff,
        T_slack        = T3_prelim,
        wrap_angle_deg = wrap_deg,
        mu             = mu,
    )

    T3 = max(T3_prelim, euler["T2_minimum"])   # governing slack-side tension

    return {
        "T1":            round(T1,          1),
        "T2":            round(T2,          1),
        "T3":            round(T3,          1),
        "T3_ktakeup":    round(T3_prelim,   1),
        "T3_euler_min":  round(euler["T2_minimum"], 1),
        "F_eff":         round(T_eff,       1),
        "R_headshaft":   round(T_eff + T3,  1),
        "euler_check":   euler,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SELECTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_torsional_moment(P_kw: float, n_rpm: float) -> float:
    omega = 2.0 * math.pi * n_rpm / 60.0
    return P_kw * 1000.0 / max(omega, 0.01)


def calc_bearing_life(R_N: float, n_rpm: float, C_basic_N: float = 355000) -> float:
    return StructuralStressEngine.bearing_l10(C_basic_N, max(R_N, 1.0), n_rpm)


def select_motor(P_kw: float, sf: float) -> float:
    req = P_kw * sf
    for m in MOTOR_SIZES:
        if m >= req:
            return m
    return MOTOR_SIZES[-1]


def select_bucket_auto(Q_th: float, rho: float, v_ms: float,
                       bucket_gap: float,
                       discharge_type: str = "centrifugal") -> Dict:
    """
    Auto-select the smallest bucket series that meets Q_req.
    Filters by discharge_type so HF elevators only consider continuous styles.
    """
    candidates = [
        b for b in BUCKET_SERIES
        if b.get("discharge_type", "centrifugal") == discharge_type
        and b.get("style") not in ("SC",)  # SC excluded from auto (double-chain only)
    ] or BUCKET_SERIES  # fallback: consider all if filter yields nothing

    for b in sorted(candidates, key=lambda x: x["V"]):  # smallest volume first
        spacing = (b["P"] + bucket_gap) / 1000.0
        if calc_capacity(v_ms, spacing, b["V"], 75.0, rho) >= Q_th:
            return b
    return candidates[-1]   # largest available


def select_belt_width(bucket_w_mm: float) -> int:
    for w in BELT_WIDTHS:
        if w >= bucket_w_mm + 50:
            return w
    return BELT_WIDTHS[-1]


# ═══════════════════════════════════════════════════════════════════════════════
# ADVISORY ENGINES — 3.7 / 3.8 / 3.9
# These produce recommendation dicts that are included in the solve result.
# They never change the core calculation — engineers can accept or override.
# ═══════════════════════════════════════════════════════════════════════════════

def bucket_recommendation(material: dict, Q_req: float = 0.0) -> dict:
    """
    3.7 — Material → Bucket Style Recommendation Engine.

    Maps material properties to the most appropriate bucket style with
    plain-English reasoning.  Based on Martin catalog application guides
    (H-146 thru H-151) and CEMA 375-2017 §6.

    Decision hierarchy
    ──────────────────
    1. Fragile / grain-family            → HF (continuous, gentle)
    2. Very heavy + highly abrasive      → SC (super-capacity double chain)
    3. Continuous preference materials   → MF (general continuous)
    4. Wet / sticky / cohesive           → C  (open front centrifugal)
    5. Moderately abrasive minerals      → AC (mill duty, 50° front)
    6. General free-flowing              → AA (standard centrifugal)
    """
    abr      = int(material.get("abr_code",     3) or 3)
    cohesion = float(material.get("cohesion",   0) or 0)
    moisture = float(material.get("moisture_pct", 0) or 0)
    flow     = int(material.get("flowability",  2) or 2)
    rho      = float(material.get("rho_bulk", material.get("rho_loose", 0)) or 0)
    cat      = (material.get("category") or "").upper()

    # Material character flags
    is_fragile      = cat in ("GRAIN", "FOOD") or flow <= 1
    is_sticky       = cohesion > 0.35 or moisture > 15
    is_heavy        = rho > 1500
    is_very_abrasive= abr >= 5
    is_mineral_heavy= is_very_abrasive and cat in ("MIN", "CEM", "CONST", "COAL", "GLASS")
    is_super_duty   = is_heavy and is_very_abrasive

    notes    = []
    alt      = "AA"

    if is_fragile:
        style  = "HF"
        reason = (
            "Continuous high-front (HF) — grain and fragile materials require gentle "
            "handling. 45° front face pours material cleanly at low speed (CR < 1.0). "
            "Minimises kernel damage and dust generation."
        )
        alt    = "MF"
    elif is_super_duty and cat in ("MIN", "CEM", "CONST", "COAL"):
        style  = "SC"
        reason = (
            "Super-capacity double-chain (SC) — very heavy, highly abrasive materials "
            "require the slow-speed SC design. Double-strand chain absorbs impact; "
            "very slow belt speed reduces wear on chain, sprockets, and casing."
        )
        alt    = "AC"
    elif cat in ("GRAIN", "FOOD", "FERT") and not is_sticky:
        style  = "MF"
        reason = (
            "Continuous medium-front (MF) — good general-purpose continuous discharge "
            "for free-flowing granular materials. 30° face angle, boot loading leg required."
        )
        alt    = "HF"
    elif is_sticky:
        style  = "C"
        reason = (
            "Low-profile open-front (C) — open front and angled sides prevent material "
            "build-up. Essential for wet, sticky, or cohesive materials that would pack "
            "in closed-back buckets. More buckets per metre than AA."
        )
        alt    = "AA"
    elif is_mineral_heavy:
        style  = "AC"
        reason = (
            "Mill-duty added-capacity (AC) — 50° hooded-back face angle cleans out "
            "abrasive minerals efficiently. Higher capacity than AA for same width. "
            "Specify AR400 or AR500 front plate for hard minerals."
        )
        alt    = "AA"
    else:
        style  = "AA"
        reason = (
            "General-purpose centrifugal (AA) — curved bottom and reinforced lip "
            "for clean centrifugal discharge. Widest size range; most common choice "
            "for free-flowing materials up to moderate abrasiveness."
        )
        alt    = "AC" if abr >= 3 else "AA"

    # Add supplementary notes
    if abr >= 5:
        notes.append(f"Abrasion class {abr}/7 — specify AR400 or harder front plate")
    if abr >= 6:
        notes.append("Consider tungsten carbide hard-facing on bucket lip (abr class 6–7)")
    if cohesion > 0.30:
        notes.append(f"Cohesion {cohesion:.2f} kPa — add vent holes to bucket back plate")
    if moisture > 12:
        notes.append(f"Moisture {moisture:.0f}% — monitor fill efficiency; use lower fill_pct")
    if style in ("MF", "HF", "SC"):
        notes.append("Continuous discharge — CR must be < 1.0. Boot loading leg required.")
    if style == "SC":
        notes.append("SC is CHAIN ONLY — not compatible with belt mount")

    return {
        "recommended_style":   style,
        "alternative_style":   alt,
        "discharge_type":      "continuous" if style in ("MF","HF","SC") else "centrifugal",
        "reasoning":           reason,
        "notes":               notes,
        "material_flags": {
            "fragile":       is_fragile,
            "sticky":        is_sticky,
            "very_abrasive": is_very_abrasive,
            "super_duty":    is_super_duty,
        },
    }


def dynamic_fill_efficiency(
    bucket:         dict,
    spacing_m:      float,
    flowability:    int,
    belt_speed_mps: float,
    elevator_type:  str = "centrifugal",
) -> dict:
    """
    3.8 — Dynamic Fill Efficiency Model.

    Computes recommended fill percentage from operating conditions rather
    than relying on a fixed user-entered value.

    Based on CEMA 375-2017 §6 and OEM design practice (BEUMER/Tapco):
        • Optimal spacing: 1.8× projection (centrifugal) or 1.0× depth (continuous)
        • Too-close spacing → poor boot loading, recirculation, lower fill
        • Too-wide spacing  → inter-bucket spill, lower effective fill
        • Poor flowability → lower fill: material bridges across bucket opening
        • Very slow speed  → under-filling (bucket exits boot before full)
        • Very high speed  → over-spill at discharge, effective fill drops

    Returns recommended fill % for advisory display; does NOT override inp.fill_pct.
    """
    P_m     = (bucket.get("P") or 150) / 1000.0
    depth_m = (bucket.get("depth_mm") or bucket.get("H") or 300) / 1000.0

    # Optimal spacing per CEMA §6
    if elevator_type == "centrifugal":
        optimal_m  = P_m * 1.8
        base_fill  = 0.82       # 82% base for well-designed centrifugal
    else:
        optimal_m  = depth_m * 1.0   # continuous: ~P ≈ depth
        base_fill  = 0.75       # 75% base for continuous (gentle loading)

    # Spacing factor — bell-curve centred on optimal
    ratio = spacing_m / max(optimal_m, 0.001)
    if 0.75 <= ratio <= 1.80:
        k_spacing = 1.0
    elif ratio < 0.75:
        k_spacing = 0.70 + 0.40 * (ratio / 0.75)   # under-spaced → drops to 0.70
    else:
        k_spacing = max(0.70, 1.0 - 0.12 * (ratio - 1.80))  # over-spaced → drops

    # Flowability factor (CEMA 1=very free, 4=sluggish)
    _k_flow_map = {1: 1.00, 2: 0.95, 3: 0.85, 4: 0.70}
    k_flow      = _k_flow_map.get(max(1, min(int(flowability), 4)), 0.85)

    # Speed factor
    if belt_speed_mps < 0.60:
        k_speed = 0.88   # very slow → incomplete filling
    elif belt_speed_mps > 2.50:
        k_speed = 0.90   # very fast → splash/spill at discharge
    else:
        k_speed = 1.00

    rec_fill = min(95.0, max(40.0, base_fill * k_spacing * k_flow * k_speed * 100.0))

    spacing_status = (
        "optimal"   if 0.75 <= ratio <= 1.80 else
        "too_close" if ratio < 0.75          else "too_wide"
    )

    _min_flow_map  = {1: 40, 2: 40, 3: 45, 4: 55}
    _max_spill_map = {1: 95, 2: 90, 3: 85, 4: 75}
    min_fill = float(_min_flow_map.get(max(1, min(int(flowability), 4)), 45))
    max_fill = float(_max_spill_map.get(max(1, min(int(flowability), 4)), 85))
    if belt_speed_mps < 0.80:
        min_fill = min(min_fill + 10.0, 65.0)
    if spacing_status == "too_wide":
        max_fill = min(max_fill, 80.0)
    min_fill = round(min_fill, 0)
    max_fill = round(max_fill, 0)
    return {
        "recommended_fill_pct": round(rec_fill, 1),
        "min_fill_pct":         min_fill,
        "max_fill_pct":         max_fill,
        "optimal_spacing_mm":   round(optimal_m * 1000, 0),
        "current_spacing_mm":   round(spacing_m * 1000, 0),
        "spacing_ratio":        round(ratio, 2),
        "spacing_status":       spacing_status,
        "k_spacing":            round(k_spacing, 3),
        "k_flow":               round(k_flow, 3),
        "k_speed":              round(k_speed, 3),
        "note": (
            f"Range {int(min_fill)}\u2013{int(max_fill)}%  \u00b7  "
            f"Optimum {rec_fill:.1f}%  \u00b7  "
            f"CEMA \u00a76 optimal spacing {optimal_m*1000:.0f}mm "
            f"({'1.8\u00d7proj' if elevator_type=='centrifugal' else '1.0\u00d7depth'}). "
            f"Current {spacing_m*1000:.0f}mm (ratio {ratio:.2f})."
        ),
    }


def _required_wrap_angle(
    T_effective_N: float,
    T_slack_N:     float,
    mu:            float,
    margin:        float = 1.05,
) -> dict:
    """
    3.9 — Wrap Angle Recommendation Engine.

    Inverse Euler-Eytelwein: given the effective tension, slack tension,
    and lagging friction coefficient, compute the MINIMUM wrap angle
    that prevents belt slip.

    Standard Euler formula:
        T_tight / T_slack = e^(μ·θ)
        where T_tight = T_effective + T_slack

    Rearranging:
        θ_min = ln((T_eff + T_slack) / T_slack) / μ
               = ln(T_eff / T_slack + 1) / μ

    A 5% margin is applied by default (margin=1.05) to give a comfortable
    operating band above the theoretical minimum.

    Standard snub configurations for bucket elevators:
        180°  — no snub pulley (standard)
        210°  — single snub pulley on return side
        240°  — two snub pulleys
        240°+ — rarely used; consider ceramic lagging instead
    """
    if T_slack_N <= 0 or mu <= 0 or T_effective_N <= 0:
        return {
            "required_deg": 180.0,
            "adequate":     True,
            "note":         "Cannot compute — zero slack tension or friction coefficient.",
        }

    # Minimum wrap from Euler inverse
    ratio_min = (T_effective_N + T_slack_N) / T_slack_N
    theta_min_rad = math.log(ratio_min) / mu
    theta_req_deg = math.degrees(theta_min_rad * margin)

    # Practical recommendation
    if theta_req_deg <= 180:
        snub_rec = "No snub pulley needed — 180° wrap is sufficient."
        config   = "180°"
    elif theta_req_deg <= 210:
        snub_rec = "Add one snub pulley on return side to achieve ≥210°."
        config   = "210° (single snub)"
    elif theta_req_deg <= 240:
        snub_rec = "Add two snub pulleys or a large-diameter drive pulley to achieve ≥240°."
        config   = "240° (two snub)"
    else:
        snub_rec = (
            f"Required wrap {theta_req_deg:.0f}° is impractical. "
            "Increase take-up tension, upgrade to ceramic lagging, or reduce belt speed."
        )
        config   = "240°+ (impractical — review design)"

    return {
        "required_deg":   round(theta_req_deg, 1),
        "ratio_required": round(ratio_min, 3),
        "config":         config,
        "adequate":       True,   # actual adequacy checked in _build_checks against inp.wrap_deg
        "recommendation": snub_rec,
        "note": (
            f"Euler inverse: T_tight/T_slack = {ratio_min:.2f} "
            f"→ θ_min = {theta_req_deg:.1f}° at μ={mu:.2f} (+{int((margin-1)*100)}% margin)."
        ),
    }


def feed_design(
    Q_th:           float,
    rho:            float,
    belt_width_mm:  float,
    bucket:         dict,
    v_belt_mps:     float,
    elev_type:      str,
    boot_D_mm:      float,
    aor_deg:        float = 35.0,
    boot_outlet_h:  float = 0.0,
) -> dict:
    """
    CEMA 375 §4 — Boot Feed Design.

    Sizing the boot inlet opening and surge volume so that material can
    enter buckets without restriction.  The two loading modes are
    physically distinct and require different boot geometries:

    Centrifugal (digging) — CC, AA, AC, C bucket styles
    ────────────────────────────────────────────────────
    Buckets scoop (dig) material from a boot pit.  Material is stored
    in the boot to a depth that matches the bucket projection P.
    The effective "digging zone" spans roughly 90° of the boot pulley arc.

    Inlet opening:
        Width  = belt width  (buckets sweep the full belt width)
        Height = material depth = 0.75 × bucket projection
                 (empirical CEMA value: keeps buckets ≥75% full at entry)

    Inlet area check:
        A_req = Q_vol / v_material  where v_material ≈ 0.30 m/s
        (low velocity avoids splash and reduces wear at inlet)

    Continuous (loading leg) — MF, HF, SC bucket styles
    ────────────────────────────────────────────────────
    Buckets are filled by a spout/chute — they do NOT dig.
    A loading leg delivers pre-fed material into the open bucket mouth
    as each bucket passes horizontally through the boot section.

    Spout geometry:
        Height = 2 × bucket depth  (allows two buckets to be filling)
        Width  = bucket width + 50mm clearance each side
        Angle  ≥ angle_of_repose + 10° (typically ≥ 45°)

    Inlet opening:
        A_req = Q_vol / v_spout  where v_spout ≈ 0.40 m/s

    Surge volume (both types)
    ─────────────────────────
    CEMA recommends a boot surge buffer of 2–5 seconds of volumetric flow
    to absorb feed rate fluctuations without starving the elevator:
        V_surge = Q_vol × t_surge

    Boot casing height (from boot pulley centre to floor)
    ─────────────────────────────────────────────────────
        Centrifugal:  h = R_boot + P_bucket + clearance_50mm
        Continuous:   h = R_boot + P_bucket + loading_leg_height + clearance_25mm

    Parameters
    ──────────────────────────────────────────────────────────────────────
    Q_th            Design capacity [t/h]
    rho             Bulk density [kg/m³]
    belt_width_mm   Belt / casing width [mm]
    bucket          Bucket dict (P, depth_mm, W, V, discharge_type)
    v_belt_mps      Belt speed [m/s]
    elev_type       "centrifugal" | "continuous"
    boot_D_mm       Boot pulley diameter [mm]
    aor_deg         Material angle of repose [°]
    boot_outlet_h   Engineer override for outlet height [mm]; 0 = auto
    """
    BW_m    = belt_width_mm / 1000.0
    Q_m3s   = Q_th / (rho * 3.6)          # volumetric flow [m³/s]

    P_mm    = bucket.get("P")     or 178   # projection [mm]
    H_mm    = bucket.get("depth_mm") or bucket.get("H") or 295  # bucket depth [mm]
    W_mm    = bucket.get("W")     or 406   # bucket width [mm]
    P_m     = P_mm  / 1000.0
    H_m_bkt = H_mm  / 1000.0
    W_m     = W_mm  / 1000.0
    R_boot  = boot_D_mm / 2000.0          # boot pulley radius [m]

    t_surge_s = 3.0   # CEMA recommended surge buffer [s]

    if elev_type == "continuous":
        # ── Continuous — loading leg (spout feed) ─────────────────────────
        loading_type = "Loading Leg — Spout Feed"
        v_feed_mps   = 0.40   # m/s at spout outlet

        # Inlet sizing
        A_inlet_m2   = Q_m3s / v_feed_mps
        h_inlet_m    = A_inlet_m2 / max(BW_m, 0.1)

        # Loading leg dimensions
        leg_height_m = max(2.0 * H_m_bkt, 0.40)   # 2× bucket depth min 400mm
        leg_width_m  = W_m + 0.100                 # bucket width + 50mm each side
        spout_angle  = max(aor_deg + 10.0, 45.0)   # angle of repose + margin

        clearance_m  = 0.025
        boot_min_h_m = R_boot + P_m + leg_height_m + clearance_m

        loading_note = (
            f"Continuous elevators require a loading leg — material is fed "
            f"into open bucket mouths via a spout as they pass horizontally. "
            f"Leg height ≥ {leg_height_m*1000:.0f}mm (2×bucket depth). "
            f"Spout angle ≥ {spout_angle:.0f}° (AoR {aor_deg:.0f}° + 10° margin). "
            f"Do NOT allow buckets to dig — use a feeder upstream."
        )
        warnings = []
        if v_belt_mps > 1.3:
            warnings.append(
                f"Belt speed {v_belt_mps:.2f} m/s is high for a loading leg — "
                f"material transit time through leg is short. "
                f"Verify spout can deliver material fast enough."
            )

        return {
            "loading_type":          loading_type,
            "loading_note":          loading_note,
            "elev_type":             elev_type,
            # Flow rates
            "Q_volumetric_m3s":      round(Q_m3s,        5),
            "Q_volumetric_m3h":      round(Q_m3s * 3600, 2),
            "v_feed_mps":            round(v_feed_mps,   2),
            # Inlet / opening
            "A_inlet_m2":            round(A_inlet_m2,   5),
            "inlet_width_mm":        round(BW_m * 1000,  0),
            "inlet_height_mm":       round(h_inlet_m * 1000, 0),
            "inlet_height_used_mm":  round(
                boot_outlet_h if boot_outlet_h > 0 else h_inlet_m * 1000, 0
            ),
            # Loading leg
            "loading_leg_height_mm": round(leg_height_m * 1000, 0),
            "loading_leg_width_mm":  round(leg_width_m  * 1000, 0),
            "spout_angle_deg":       round(spout_angle, 1),
            # Surge
            "V_surge_m3":            round(Q_m3s * t_surge_s, 5),
            "V_surge_litres":        round(Q_m3s * t_surge_s * 1000, 1),
            "t_surge_s":             t_surge_s,
            # Boot geometry
            "boot_casing_height_mm": round(boot_min_h_m * 1000, 0),
            "boot_pulley_radius_mm": round(R_boot * 1000, 0),
            "bucket_projection_mm":  P_mm,
            "clearance_mm":          round(clearance_m * 1000, 0),
            "warnings":              warnings,
        }

    else:
        # ── Centrifugal — digging ────────────────────────────────────────
        loading_type = "Centrifugal — Digging / Scooping"
        v_feed_mps   = 0.30   # m/s horizontal material flow in boot pit

        # Material depth in boot pit = 0.75 × projection (CEMA empirical)
        material_depth_m = P_m * 0.75

        # Inlet area (horizontal cross-section of boot pit at material level)
        A_inlet_m2   = Q_m3s / v_feed_mps
        h_inlet_m    = material_depth_m   # depth determines fill, not area
        inlet_width_m = BW_m

        clearance_m  = 0.050   # 50mm minimum boot floor clearance
        boot_min_h_m = R_boot + P_m + H_m_bkt + clearance_m

        # Dig volume — volume of material in the active digging zone
        # CEMA: digging zone ≈ 90° arc at boot → length ≈ π/2 × R_boot
        dig_zone_length_m = math.pi / 2.0 * R_boot
        V_dig_m3 = inlet_width_m * material_depth_m * dig_zone_length_m

        loading_note = (
            f"Centrifugal elevators dig material from the boot pit. "
            f"Buckets scoop as they round the boot pulley (90° arc). "
            f"Maintain material depth ≈ {material_depth_m*1000:.0f}mm "
            f"(0.75×projection {P_mm}mm) for consistent filling. "
            f"Boot floor clearance ≥ {clearance_m*1000:.0f}mm."
        )
        warnings = []
        if v_belt_mps > 2.0:
            warnings.append(
                f"Belt speed {v_belt_mps:.2f} m/s is high for a digging elevator — "
                f"material scatter in boot may reduce fill efficiency. "
                f"Consider increasing bucket gap or reducing speed."
            )
        if material_depth_m < 0.050:
            warnings.append(
                "Bucket projection is very small — maintain boot material level carefully."
            )

        return {
            "loading_type":          loading_type,
            "loading_note":          loading_note,
            "elev_type":             elev_type,
            # Flow rates
            "Q_volumetric_m3s":      round(Q_m3s,        5),
            "Q_volumetric_m3h":      round(Q_m3s * 3600, 2),
            "v_feed_mps":            round(v_feed_mps,   2),
            # Inlet / opening
            "A_inlet_m2":            round(A_inlet_m2,   5),
            "inlet_width_mm":        round(inlet_width_m * 1000, 0),
            "inlet_height_mm":       round(material_depth_m * 1000, 0),
            "inlet_height_used_mm":  round(
                boot_outlet_h if boot_outlet_h > 0 else material_depth_m * 1000, 0
            ),
            # Digging zone
            "material_depth_mm":     round(material_depth_m * 1000, 0),
            "dig_zone_length_mm":    round(dig_zone_length_m * 1000, 0),
            "V_dig_m3":              round(V_dig_m3, 5),
            "V_dig_litres":          round(V_dig_m3 * 1000, 1),
            # Surge
            "V_surge_m3":            round(Q_m3s * t_surge_s, 5),
            "V_surge_litres":        round(Q_m3s * t_surge_s * 1000, 1),
            "t_surge_s":             t_surge_s,
            # Boot geometry
            "boot_casing_height_mm": round(boot_min_h_m * 1000, 0),
            "boot_pulley_radius_mm": round(R_boot * 1000, 0),
            "bucket_projection_mm":  P_mm,
            "bucket_depth_mm":       H_mm,
            "clearance_mm":          round(clearance_m * 1000, 0),
            "warnings":              warnings,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FULL CEMA 375 SOLVER
# ═══════════════════════════════════════════════════════════════════════════════

def solve_elevator(inp: BucketElevatorInput) -> dict:
    # ── Material & density ────────────────────────────────────────────────────
    mat = get_material(inp.mat_id)
    rho = inp.custom_rho if inp.custom_rho > 0 else mat["rho_loose"]

    # ── Custom material property overrides (v1.6.0) ───────────────────────────
    # Engineer-supplied values take precedence over the DB entry.
    # All accesses use getattr() so calculations.py is safe regardless of
    # which version of models.py is deployed (Pylance-clean).
    _overrides: dict = {}
    _c_aor  = getattr(inp, "custom_aor",         0)
    _c_abr  = getattr(inp, "custom_abr",         0)
    _c_flow = getattr(inp, "custom_flowability",  0)
    _c_mois = getattr(inp, "custom_moisture",    -1)
    _c_coh  = getattr(inp, "custom_cohesion",    -1)
    _c_name = getattr(inp, "custom_mat_name",    "")
    if _c_aor  > 0:  _overrides["angle_repose"] = _c_aor
    if _c_abr  > 0:  _overrides["abr_code"]     = int(_c_abr)
    if _c_flow > 0:  _overrides["flowability"]  = int(_c_flow)
    if _c_mois >= 0: _overrides["moisture_pct"] = _c_mois
    if _c_coh  >= 0: _overrides["cohesion"]     = _c_coh
    if _c_name:      _overrides["name"]         = _c_name
    if _overrides:
        mat = {**mat, **_overrides}

    # ── Boot pulley diameter — same-as-head toggle ────────────────────────────
    _same = getattr(inp, "boot_pulley_same_as_head", False)
    _boot_D_mm = inp.D_mm if _same else inp.boot_pulley_D_mm

    # v1.9.0: auto-calculate wrap angle from pulley geometry
    # wrap = 180° + 2·arcsin((R_head − R_boot) / C)  — always ≈180° for tall elevators
    _R_hw = float(inp.D_mm) / 2.0
    _R_bw = float(_boot_D_mm) / 2.0
    _C_mm = inp.H_m * 1000.0 + _R_hw + _R_bw
    _sin  = max(-1.0, min(1.0, (_R_hw - _R_bw) / max(_C_mm, 1.0)))
    _wrap_geom = 180.0 + 2.0 * math.degrees(math.asin(_sin))
    _wrap_inp  = float(getattr(inp, "wrap_deg", 0) or 0)
    if _wrap_inp >= 90.0:                                   # explicit override
        _wrap_eff = _wrap_inp
    elif getattr(inp, "snub_pulley", False):
        _wrap_eff = min(_wrap_geom + 30.0, 240.0)           # one snub pulley
    else:
        _wrap_eff = _wrap_geom                              # pure geometry
    _wrap_eff = round(_wrap_eff, 1)


    # ── Material behaviour corrections (v1.2.0 integration) ──────────────────
    #    elevator_type for fill: "continuous" for HF-style, "centrifugal" for CC
    bucket_id = inp.bucket_id if not inp.auto_bucket else None
    is_hf = (bucket_id in ("HF", "HF-L", "MF", "MF-L", "PF", "SC", "SC-L")) if bucket_id else False
    elev_type = "continuous" if is_hf else "centrifugal"
    try:
        mat_behavior = MaterialBehaviorEngine.apply_to_solver(mat, elev_type)
    except Exception as _mbe:
        # Safe fallback — bad material entry must not crash the solver
        mat_behavior = {
            "fill_efficiency":           0.75,
            "recommended_fill_pct":      float(inp.fill_pct),
            "vfi":                       3,
            "rollback_factor":           0.0,
            "effective_cr_threshold":    1.0,
            "wall_friction_coeff":       0.35,
            "minimum_chute_angle_deg":   45.0,
            "hazards":                   {},
            "abrasion_class":            3,
            "flowability_class":         3,
            "_error":                    str(_mbe),
        }

    # ── Belt speed ─────────────────────────────────────────────────────────────
    v = belt_speed(inp.D_mm, inp.n_rpm)

    # ── Bucket selection ───────────────────────────────────────────────────────
    if inp.auto_bucket:
        bucket = select_bucket_auto(
            inp.Q_req, rho, v, inp.bucket_gap,
            discharge_type=elev_type,
        )
    else:
        bucket = _BUCKET_BY_ID.get(inp.bucket_id) or next(
            (b for b in BUCKET_SERIES if b["id"] == inp.bucket_id),
            BUCKET_SERIES[4],   # fallback: Series B
        )

    # ── Spacing & capacity ────────────────────────────────────────────────────
    spacing = (bucket["P"] + inp.bucket_gap) / 1000.0
    Q = calc_capacity(v, spacing, bucket["V"], inp.fill_pct, rho)

    # ── 3.7 — Bucket recommendation (advisory only) ───────────────────────────
    bucket_rec = bucket_recommendation(mat, inp.Q_req)

    # ── 3.8 — Dynamic fill efficiency (advisory only) ─────────────────────────
    fill_eff = dynamic_fill_efficiency(
        bucket, spacing,
        flowability    = int(mat.get("flowability", 2) or 2),
        belt_speed_mps = v,
        elevator_type  = elev_type,
    )

    # ── Power ─────────────────────────────────────────────────────────────────
    # HF continuous elevators use Leq = 4–5 (CEMA 375 §4).
    # Centrifugal elevators use Leq = 6–8 (default from material DB or LEQ_DEFAULT).
    _leq_hf_default = 4.5   # midpoint of CEMA 375 continuous range
    D_boot_m = _boot_D_mm / 1000.0
    Leq  = (inp.Leq if inp.Leq > 0
            else mat.get("Leq_default", _leq_hf_default if is_hf else LEQ_DEFAULT))
    Ceff = inp.Ceff if inp.Ceff > 0 else mat.get("Ceff_default", CEFF_BELT)
    pwr  = calc_power_cema375(Q, inp.H_m, D_boot_m, Leq, Ceff)
    P_total = pwr["P_total"]

    # ── Tensions ──────────────────────────────────────────────────────────────
    # v1.2.0 FIX: actual catalogue bucket mass (not V × 1.5)
    # v1.2.1 FIX: mu and wrap_deg now passed through to Euler check
    bw_kg = bucket.get("bucket_mass_kg", bucket["V"] * 1.5)

    # ── Belt width / casing width ─────────────────────────────────────────────
    _bw_override = getattr(inp, "belt_width_override_mm", 0) or 0
    BW_mm = int(_bw_override) if _bw_override > 0 else select_belt_width(bucket["W"])

    # ── v1.8.0 — Belt vs Chain tension branch ────────────────────────────────
    is_chain      = getattr(inp, "conveyor_type", "belt") == "chain"
    chain_n_str   = int(getattr(inp, "chain_n_strands", 1) or 1)
    chain_ser_id  = (getattr(inp, "chain_series", "") or "").strip()
    chain_sf_req  = float(getattr(inp, "chain_sf", 6.0) or 6.0)
    chain_n_teeth = int(getattr(inp, "chain_sprocket_teeth", 0) or 0)
    tens: dict = {}   # populated in belt branch; empty dict for chain (safe subscript via .get())

    if is_chain:
        # ── Chain T2: chain self-weight + bucket weight ───────────────────────
        _chain_prelim = (
            _CHAIN_BY_ID.get(chain_ser_id)
            if chain_ser_id and chain_ser_id in _CHAIN_BY_ID else None
        )
        _chain_wt_prelim = _chain_prelim["wt_kg_m"] if _chain_prelim else 4.5

        T1     = DynamicLoadEngine.material_tension(Q, inp.H_m, v)
        T2     = _chain_catenary_tension(_chain_wt_prelim, chain_n_str, bw_kg, spacing, inp.H_m)
        F_eff  = T1 + T2
        T3     = F_eff * inp.K_takeup
        R_head = F_eff + T3

        euler_chk = {
            "euler_ratio": None, "T2_minimum": 0.0, "slip_safe": True,
            "note": "N/A — chain drive: slip check replaced by working load check",
        }

        # Select chain and refine T2 with actual chain weight
        if _chain_prelim:
            chain_selected = _chain_prelim
        else:
            chain_selected = select_chain_auto(F_eff, chain_n_str, chain_sf_req)

        T2     = _chain_catenary_tension(chain_selected["wt_kg_m"], chain_n_str, bw_kg, spacing, inp.H_m)
        F_eff  = T1 + T2
        T3     = F_eff * inp.K_takeup
        R_head = F_eff + T3

        # ── Sprocket geometry ─────────────────────────────────────────────────
        if chain_n_teeth > 0:
            sprocket = sprocket_geometry(chain_selected["pitch_mm"], chain_n_teeth)
        else:
            _pitch   = chain_selected["pitch_mm"]
            _sin_arg = min(0.9999, _pitch / max(inp.D_mm, _pitch))
            _n_est   = max(6, round(math.pi / math.asin(_sin_arg)))
            sprocket = sprocket_geometry(_pitch, _n_est)

        chain_pull_N = F_eff
        chain_SF_act = chain_selected["WL_kg"] * 9.81 * chain_n_str / max(chain_pull_N, 1.0)
        chain_v_ok   = v <= chain_selected["v_max_ms"]
        belt_ply     = None
        belt_PIW     = None

        wrap_rec = {
            "required_deg": None, "config": "N/A (chain drive)", "adequate": True,
            "recommendation": "Chain cannot slip on sprocket — Euler wrap check not applicable.",
            "note": "Chain pull working load check replaces Euler-Eytelwein.",
        }

    else:
        # ── Belt elevator ─────────────────────────────────────────────────────
        tens  = calc_headshaft_tensions(
            Q, inp.H_m, v, bw_kg, spacing, BW_mm, inp.K_takeup,
            mu=inp.mu, wrap_deg=_wrap_eff,
        )
        T1, T2, T3 = tens["T1"], tens["T2"], tens["T3"]
        F_eff      = tens["F_eff"]
        R_head     = tens["R_headshaft"]
        euler_chk  = tens["euler_check"]

        chain_selected = None
        chain_SF_act   = None
        chain_pull_N   = None
        chain_v_ok     = None
        sprocket       = None

        # 3.9 — Wrap angle recommendation
        wrap_rec = _required_wrap_angle(F_eff, T3, inp.mu)

    # ── Shaft sizing ──────────────────────────────────────────────────────────
    T_Nm = calc_torsional_moment(P_total, inp.n_rpm)
    # v1.2.0 FIX: geometry derived from BW_mm; bending moment from beam theory
    span_m, A_m, B_m = _shaft_geometry(BW_mm)
    M_Nm = _bending_moment(R_head, A_m, B_m)

    gov = StructuralStressEngine.shaft_diameter_governing(
        T_Nm, M_Nm, R_head, A_m, B_m
    )
    d_mm_calc    = gov["d_governing_mm"]
    d_stress_mm  = gov["d_stress_mm"]
    d_deflect_mm = gov["d_deflect_mm"]
    governed_by  = gov["governed_by"]

    # v1.5.0 shaft diameter override ─────────────────────────────────────────
    # If the engineer specifies a preferred shaft diameter, use it and flag
    # adequacy against the calculated minimum.  Hub/key are re-derived from
    # the actual diameter so all downstream checks remain consistent.
    _shaft_override = getattr(inp, "shaft_d_override_mm", 0) or 0
    if _shaft_override > 0:
        d_mm = float(_shaft_override)
        governed_by = f"user override ({_shaft_override:.0f}mm, calc min {d_mm_calc:.1f}mm)"
    else:
        d_mm = d_mm_calc

    # Use the governing m-value consistently for hub/key (recalc if override)
    d_governing_m = d_mm / 1000.0

    # ── Hub sizing & keyway check ─────────────────────────────────────────────
    hub = StructuralStressEngine.hub_diameter(
        shaft_diameter_m = d_governing_m,
        torque_Nm        = T_Nm,
    )
    key = StructuralStressEngine.key_stress_check(
        shaft_diameter_m = d_governing_m,
        torque_Nm        = T_Nm,
        key_length_m     = hub["L_hub_m"],
    )

    # ── Pulley lagging selection ───────────────────────────────────────────────
    environment = getattr(inp, "environment", "dry")
    belt_type   = getattr(inp, "belt_type",   "EP")
    lagging = StructuralStressEngine.pulley_lagging(
        material       = mat,
        T_effective_N  = F_eff,
        T_slack_N      = T3,
        wrap_angle_deg = _wrap_eff,
        environment    = environment,
        belt_type      = belt_type,
    )

    # ── Pulley end disc ───────────────────────────────────────────────────────
    end_disc = StructuralStressEngine.pulley_end_disc(
        pulley_diameter_m = inp.D_mm / 1000.0,
        hub_od_m          = hub["d_hub_m"],
        T_total_N         = T1 + T2 + T3,
        face_width_m      = BW_mm / 1000.0 + 0.050,
    )

    # ── Bucket bolt fatigue ───────────────────────────────────────────────────
    fill_mass_kg = bucket["V"] / 1000.0 * inp.fill_pct / 100.0 * rho
    n_bolts_bkt  = 3 if bucket["W"] > 350 else 2
    bolt_dia_mm  = 16 if bucket["W"] > 350 else 12
    bolt_fatigue = StructuralStressEngine.bucket_bolt_fatigue(
        belt_speed_mps   = v,
        head_radius_m    = inp.D_mm / 2000.0,
        bucket_mass_kg   = bw_kg,
        fill_mass_kg     = fill_mass_kg,
        n_bolts          = n_bolts_bkt,
        bolt_diameter_mm = bolt_dia_mm,
        n_rpm            = inp.n_rpm,
    )

    # ── Take-up design ────────────────────────────────────────────────────────
    # v1.5.0: takeup_type, takeup_screw_d_mm, takeup_screw_len_m overrides.
    # "gravity" → counterweight design; "screw" → screw design; "auto" → H_m threshold.
    _takeup_type  = getattr(inp, "takeup_type",       "gravity") or "gravity"
    _screw_d_mm   = getattr(inp, "takeup_screw_d_mm", 0)  or 0
    _screw_len_m  = getattr(inp, "takeup_screw_len_m", 0) or 0

    # Auto-select: gravity for H ≥ 15m, screw otherwise
    if _takeup_type == "auto":
        _takeup_type = "gravity" if inp.H_m >= 15.0 else "screw"

    takeup_gravity = StructuralStressEngine.gravity_takeup(T3, inp.H_m, BW_mm)

    # Screw take-up — always calculated (shown as "alternative" when gravity chosen)
    _screw_travel_m = takeup_gravity.get("travel_m", 0.5)          # match required travel
    _screw_span_m   = float(_screw_len_m) if _screw_len_m > 0 else max(_screw_travel_m + 0.1, 0.6)
    takeup_screw    = StructuralStressEngine.screw_takeup(
        T_slack_N      = T3,
        travel_m       = _screw_travel_m,
        screw_length_m = _screw_span_m,
        preferred_d_mm = float(_screw_d_mm),
    )
    # Tag which take-up is the primary selection
    takeup_gravity["primary"] = _takeup_type == "gravity"
    takeup_screw["primary"]   = _takeup_type == "screw"

    # ── Casing structural ─────────────────────────────────────────────────────
    # v1.5.0: casing_t_override_mm — engineer can specify preferred plate thickness.
    wind_pa = getattr(inp, "wind_pressure_pa", 800.0)
    _casing_t_override = getattr(inp, "casing_t_override_mm", 0) or 0
    casing_t_m_calc = StructuralStressEngine.casing_plate_thickness(BW_mm, rho, inp.H_m)
    casing_t_m      = (float(_casing_t_override) / 1000.0
                       if _casing_t_override > 0 else casing_t_m_calc)
    # FIX v1.8.1: Stiffener spacing must be derived from the CALCULATED MINIMUM
    # plate thickness, not the override. This decouples the panel span (a fixed
    # structural reference) from the plate thickness being evaluated.
    # Result: thicker override → LESS deflection (correct physics).
    #         thinner override → MORE deflection (correct — should fail the check).
    # Previously both used casing_t_m, creating a circular dependency where the
    # panel span scaled with the plate so δ ≈ constant × L/360 for any thickness.
    casing_stiffener = StructuralStressEngine.casing_stiffener_spacing(casing_t_m_calc, wind_pa)
    panel_span_m = casing_stiffener["recommended_mm"] / 1000.0
    casing_panel = StructuralStressEngine.casing_panel_deflection(
        panel_span_m, panel_span_m, casing_t_m, wind_pa,
    )
    # Expose override status in casing_panel result
    casing_panel["override_applied"] = _casing_t_override > 0
    casing_panel["t_calc_mm"]        = round(casing_t_m_calc * 1000, 1)
    casing_panel["t_use_mm"]         = round(casing_t_m * 1000, 1)

    # ── Belt & motor ──────────────────────────────────────────────────────────
    motor_kw = select_motor(P_total, inp.sf)
    belt_ply = math.ceil(F_eff / (BW_mm / 25.4 * 4450 * 0.5))

    # ── Discharge physics — branched on elevator type ─────────────────────────
    # v1.5.0: HF (continuous discharge) elevators use a pour-curve model.
    #          Centrifugal (CC) elevators use the existing stream_envelope model.
    #
    # is_continuous is True when:
    #   • auto_bucket=False and bucket_id="HF"
    #   • auto_bucket=True  and selected bucket type == "HF"
    #
    # Continuous discharge physics differences:
    #   • CR must be < 1.0 (opposite of centrifugal — CR ≥ 1.0 is a FAIL)
    #   • No centrifugal release angle — material pours as bucket inverts
    #   • Stream is a short curtain, not a parabolic throw
    #   • Casing check: CR < 1.0 confirmed; no stream-strike risk

    is_continuous = (
        bucket.get("discharge_type") == "continuous"
        or bucket.get("type") == "HF"
        or elev_type == "continuous"
    )

    if is_continuous:
        # ── Continuous discharge (HF) ─────────────────────────────────────────
        # CR = v²/(g·r) must be < 1.0. Record it for check branching below.
        cr = v ** 2 / (9.81 * (inp.D_mm / 2000.0))
        theta_rel = 0.0   # no centrifugal release angle for continuous discharge

        cont_curve = DischargePhysics.continuous_discharge_curve(
            v_belt  = v,
            D_mm    = inp.D_mm,
            aor_deg = float(mat.get("angle_repose", 35.0) or 35.0),
        )
        traj_center   = cont_curve["center"]
        traj_upper    = cont_curve["upper"]
        traj_lower    = cont_curve["lower"]
        stream_spread = 0.060   # 60mm fixed spread for continuous pour
        traj_metrics  = {
            "onset_angle_deg": cont_curve.get("onset_angle_deg"),
            "land_x_m":        cont_curve.get("land_x_m"),
            "land_y_m":        cont_curve.get("land_y_m"),
            "discharge_type":  "continuous",
        }

        # Casing clearance: for HF, check CR < 1.0 rather than stream-strike
        _BW_for_cas     = float(BW_mm or 400)
        _casing_inner_x = _BW_for_cas / 2000.0 + 0.050
        casing_clearance = DischargePhysics.continuous_casing_check(
            v_belt    = v,
            D_mm      = inp.D_mm,
            belt_w_mm = float(BW_mm),
        )

        # Stream interception: for HF the chute is fixed behind the head pulley
        # The chute always intercepts the continuous pour — use chute_rec geometry
        chute_rec = cont_curve.get("chute_rec", {})
        stream_chute = {
            "intercepted":         True,
            "discharge_type":      "continuous",
            "chute_angle_rec_deg": chute_rec.get("back_plate_angle_deg", 65.0),
            "note":                chute_rec.get("description", ""),
        }

    else:
        # ── Centrifugal discharge (CC/standard) ───────────────────────────────
        rp    = DischargePhysics.calculate_release_point(v, inp.D_mm / 2000.0)
        cr    = rp.cr
        theta_rel = rp.theta_deg

        envelope = DischargePhysics.stream_envelope(
            speed                  = v,
            radius                 = inp.D_mm / 2000.0,
            bucket_projection_m    = (bucket.get("P") or 140) / 1000.0,
            bucket_front_angle_deg = float(bucket.get("front_angle_deg", 30)),
            cohesion_index         = mat.get("cohesion", 0.0),
            elevator_type          = "centrifugal",
            material               = mat,
        )
        traj_center   = envelope["center"]
        traj_upper    = envelope["upper"]
        traj_lower    = envelope["lower"]
        stream_spread = envelope["spread_m"]
        traj_metrics  = envelope.get("metrics", {})

        _BW_for_cas     = float(BW_mm or 400)
        _casing_inner_x = _BW_for_cas / 2000.0 + 0.050
        casing_clearance = DischargePhysics.casing_clearance_check(
            trajectory          = traj_center,
            casing_half_width_m = _casing_inner_x,
        )

        _rp_chute   = DischargePhysics.calculate_release_point(v, inp.D_mm / 2000.0)
        _chute_x    = _casing_inner_x - 0.010
        _chute_ytop = _rp_chute.y0 + 0.020
        _chute_ybot = _rp_chute.y0 - inp.D_mm / 500.0
        stream_chute = DischargePhysics.stream_intersects_chute(
            trajectory    = traj_center,
            chute_x0_m   = _chute_x,
            chute_y0_m   = _chute_ytop,
            chute_x1_m   = _chute_x,
            chute_y1_m   = _chute_ybot,
            release_speed = v,
        )

    # ── Legacy trajectory format for report + chute_flow ─────────────────────
    def _to_mm_dicts(pts):
        return [{"x": round(p[0] * 1000, 1), "y": round(p[1] * 1000, 1)} for p in pts]

    trajectory       = _to_mm_dicts(traj_center)
    trajectory_upper = _to_mm_dicts(traj_upper)
    trajectory_lower = _to_mm_dicts(traj_lower)

    # ── Bearing life ──────────────────────────────────────────────────────────
    L10 = calc_bearing_life(R_head, inp.n_rpm)

    # ── Discharge chute design ────────────────────────────────────────────────
    # traj_center is already the raw (x, y) tuple list in metres from stream_envelope()
    bkt_w_mm   = float(bucket.get("W") or BW_mm)
    drop_h_m   = max(inp.D_mm / 1000.0 * 1.5, 0.50)

    chute_geom = ChuteFlowEngine.discharge_chute_geometry(
        trajectory           = traj_center,
        belt_speed_mps       = v,
        head_pulley_radius_m = inp.D_mm / 2000.0,
        bucket_width_mm      = bkt_w_mm,
    )
    hood_spoon  = ChuteFlowEngine.hood_spoon_geometry(
        belt_speed_mps       = v,
        head_pulley_radius_m = inp.D_mm / 2000.0,
        centrifugal_ratio    = cr,
        release_angle_deg    = theta_rel,
    )
    # Chute sizing: back-plate angle from trajectory; width from bucket + clearance
    chute_angle_auto = chute_geom.get("back_plate_angle_deg")
    chute_w_m        = (bkt_w_mm + 100.0) / 1000.0   # CEMA §5: +50mm each side
    chute_h_m        = chute_w_m * 0.75

    try:
        _liner_id = getattr(inp, "chute_liner_id", "auto") or "auto"
        discharge_chute = ChuteFlowEngine.design_summary(
            material        = mat,
            capacity_tph    = Q,
            velocity_mps    = v,
            drop_height_m   = drop_h_m,
            chute_angle_deg = float(chute_angle_auto) if chute_angle_auto is not None else 65.0,
            chute_width_m   = chute_w_m,
            chute_height_m  = chute_h_m,
            liner_override  = _liner_id,
        )
    except Exception as _ce:
        discharge_chute = {"_error": str(_ce), "performance": {}, "maintenance": {}, "recommendations": []}
    discharge_chute["geometry"]   = chute_geom
    discharge_chute["hood_spoon"] = hood_spoon

    # ── Boot pulley analysis (v1.6.0) ─────────────────────────────────────────
    # Must be computed BEFORE _build_checks so boot_analysis kwarg is bound.
    _boot_r_m     = _boot_D_mm / 2000.0
    _cr_boot      = v ** 2 / (9.81 * max(_boot_r_m, 0.001))
    _R_boot_N     = 2.0 * T3
    _L10_boot     = calc_bearing_life(_R_boot_N, inp.n_rpm)
    _D_ratio      = _boot_D_mm / max(inp.D_mm, 1.0)
    _H_equiv_boot = D_boot_m * Leq
    _same_dia     = abs(_boot_D_mm - inp.D_mm) < 1.0

    boot_pulley_analysis = {
        "head_D_mm":      round(inp.D_mm, 0),
        "boot_D_mm":      round(_boot_D_mm, 0),
        "same_diameter":  _same_dia,
        "D_ratio":        round(_D_ratio, 3),
        "cr_boot":        round(_cr_boot, 4),
        "R_boot_N":       round(_R_boot_N, 1),
        "L10_boot_h":     round(_L10_boot, 0),
        "H_equiv_m":      round(_H_equiv_boot, 3),
        "P_digging_kW":   round(pwr["P_digging"], 3),
        "note": (
            f"Head = Boot = {inp.D_mm:.0f}mm (matched diameters — balanced shaft loads)"
            if _same_dia else
            f"Boot {_boot_D_mm:.0f}mm vs Head {inp.D_mm:.0f}mm (ratio {_D_ratio:.2f})"
        ),
        "digging_note": (
            f"Digging loss H_equiv = {_H_equiv_boot:.2f}m "
            f"(= D_boot {_boot_D_mm:.0f}mm × Leq {Leq:.1f})"
        ),
    }

    # ── Feed design (2f) ──────────────────────────────────────────────────────
    _boot_outlet_h = float(getattr(inp, "boot_outlet_height_mm", 0) or 0)
    feed_result = feed_design(
        Q_th          = Q,
        rho           = rho,
        belt_width_mm = float(BW_mm),
        bucket        = bucket,
        v_belt_mps    = v,
        elev_type     = "continuous" if is_continuous else "centrifugal",
        boot_D_mm     = float(_boot_D_mm),
        aor_deg       = float(mat.get("angle_repose", 35.0) or 35.0),
        boot_outlet_h = _boot_outlet_h,
    )

    # ── Engineering checks ─────────────────────────────────────────────────────
    checks = _build_checks(
        inp, mat, mat_behavior, bucket, Q, v, cr, T1, T2, T3, F_eff,
        R_head, d_mm, d_stress_mm, d_deflect_mm, governed_by, L10, Ceff,
        euler_chk        = euler_chk,
        key_check        = key,
        lagging          = lagging,
        end_disc         = end_disc,
        bolt_fatigue     = bolt_fatigue,
        takeup_grav      = takeup_gravity,
        casing_panel     = casing_panel,
        discharge_chute  = discharge_chute,
        casing_clearance = casing_clearance,
        stream_chute     = stream_chute,
        is_continuous    = is_continuous,
        boot_analysis    = boot_pulley_analysis,
        # v1.8.0 chain checks
        is_chain         = is_chain,
        chain_selected   = chain_selected,
        chain_pull_N     = chain_pull_N,
        chain_SF_actual  = chain_SF_act,
        chain_v_ok       = chain_v_ok,
        sprocket         = sprocket,
    )

    # ── Design recommendations ────────────────────────────────────────────────
    _partial = {
        "Q": round(Q, 2), "v": round(v, 4), "cr": round(cr, 4),
        "L10": round(L10, 0), "d_mm": round(d_mm, 1),
        "P_total": round(P_total, 3), "R_headshaft": round(R_head, 1),
        "T3": round(T3, 1), "euler_ratio": euler_chk["euler_ratio"],
        "slip_safe": euler_chk["slip_safe"], "bucket": bucket,
        # v1.8.1: required for CR-continuous branch and chute recommendations
        "is_continuous":    is_continuous,
        "is_chain":         is_chain,
        "discharge_chute":  discharge_chute,
    }
    _inp_dict = {
        "Q_req": inp.Q_req, "n_rpm": inp.n_rpm, "D_mm": inp.D_mm,
        "fill_pct": inp.fill_pct, "mu": inp.mu, "wrap_deg": _wrap_eff,
    }
    try:
        design_recs = StructuralStressEngine.design_recommendations(_partial, _inp_dict)
    except Exception:
        design_recs = []

    # ── BOM + Maintenance schedule (Tier 2) ────────────────────────────────────
    # Pass a populated sub-dict so bom.py and reliability.py don't need the full
    # result object (which hasn't been assembled yet).
    _r_for_tier2 = {
        "d_mm":             round(d_mm, 1),
        "belt_w":           BW_mm,
        "belt_ply":         belt_ply,
        "bucket":           bucket,
        "bucket_mass_kg":   round(bw_kg, 2),
        "hub":              hub,
        "lagging":          lagging,
        "end_disc":         end_disc,
        "bolt_fatigue":     bolt_fatigue,
        "takeup_gravity":   takeup_gravity,
        "takeup_screw":     takeup_screw,
        "discharge_chute":  discharge_chute,
        "casing_t_mm":      round(casing_t_m * 1000, 1),
        "casing_panel":     casing_panel,
        "casing_stiffener": casing_stiffener,
        "shaft_span_mm":    round(span_m * 1000, 0),
        "motor_kw":         motor_kw,
        "T_Nm":             round(T_Nm, 2),
        "L10":              round(L10, 0),
        "mat":              mat,
        "spacing":          round(spacing, 4),
    }
    _inp_for_tier2 = {
        "Q_req":            inp.Q_req,
        "H_m":              inp.H_m,
        "D_mm":             inp.D_mm,
        "n_rpm":            inp.n_rpm,
        "boot_pulley_D_mm": getattr(inp, "boot_pulley_D_mm", 300),
        "fill_pct":         inp.fill_pct,
        "sf":               inp.sf,
        "mu":               inp.mu,
        "wrap_deg":         _wrap_eff,
        "belt_type":        getattr(inp, "belt_type", "EP"),
        "environment":      getattr(inp, "environment", "dry"),
        "wind_pressure_pa": getattr(inp, "wind_pressure_pa", 800),
    }
    try:
        bom_result = generate_bom(_r_for_tier2, _inp_for_tier2)
    except Exception:
        bom_result = None
    try:
        maintenance_result = maintenance_schedule(_r_for_tier2, _inp_for_tier2)
    except Exception:
        maintenance_result = None

    # ── Sweep data ────────────────────────────────────────────────────────────
    speed_sweep = []
    for n in range(20, 201, 10):
        vn  = belt_speed(inp.D_mm, n)
        Qn  = calc_capacity(vn, spacing, bucket["V"], inp.fill_pct, rho)
        pn  = calc_power_cema375(Qn, inp.H_m, D_boot_m, Leq, Ceff)
        crn = centrifugal_ratio(vn, inp.D_mm)
        speed_sweep.append({
            "rpm": n, "speed": round(vn, 2), "capacity": round(Qn, 1),
            "power": round(pn["P_total"], 2), "cr": round(crn, 3),
        })

    fill_sweep = [
        {"fill": f, "capacity": round(calc_capacity(v, spacing, bucket["V"], f, rho), 1)}
        for f in range(30, 101, 5)
    ]

    # ── Result ────────────────────────────────────────────────────────────────
    return {
        # Capacity
        "Q": round(Q, 2), "v": round(v, 4), "spacing": round(spacing, 4),
        # Frontend aliases — some components reference these names
        "Q_th": round(Q, 2), "capacity": round(Q, 2),
        "v_ms": round(v, 4), "belt_speed": round(v, 4),
        # Power — CEMA 375 §4 LEQ method (Task 3 validated decomposition)
        "P_lift":       pwr["P_lift"],
        "P_digging":    pwr["P_digging"],
        "P_shaft":      pwr["P_shaft"],
        "P_drive_loss": pwr["P_drive_loss"],
        "P_total":      round(P_total, 3),
        "H_equiv":      pwr["H_equiv"],
        "H_total":      pwr["H_total"],
        "Leq": Leq, "Ceff": Ceff, "motor_kw": motor_kw,
        # Tensions
        "T1": round(T1, 1), "T2": round(T2, 1), "T3": round(T3, 1),
        "T3_ktakeup":   tens.get("T3_ktakeup",   round(T3, 1)),
        "T3_euler_min": tens.get("T3_euler_min",  0.0),
        "F_eff": round(F_eff, 1), "R_headshaft": round(R_head, 1),
        "euler_ratio":  euler_chk["euler_ratio"],
        "slip_safe":    euler_chk["slip_safe"],
        "mu":           inp.mu, "wrap_deg": _wrap_eff,
        # Shaft
        "T_Nm": round(T_Nm, 2), "d_mm": round(d_mm, 1),
        "d_stress_mm": round(d_stress_mm, 1), "d_deflect_mm": round(d_deflect_mm, 1),
        "governed_by": governed_by, "shaft_span_mm": round(span_m * 1000, 0),
        "shaft_A_mm": round(A_m * 1000, 0), "shaft_B_mm": round(B_m * 1000, 0),
        # Belt & buckets
        "belt_ply": belt_ply, "belt_w": BW_mm,
        "bucket_mass_kg": round(bw_kg, 2),
        # Discharge — stream envelope (v1.4.0 replaces single trajectory)
        "cr": round(cr, 4), "theta_rel": round(theta_rel, 2),
        "discharge_type":   "continuous" if is_continuous else "centrifugal",
        "is_continuous":    is_continuous,
        # Boot pulley analysis — v1.6.0
        "boot_pulley":      boot_pulley_analysis,
        "stream_spread":    round(stream_spread, 4),
        "trajectory":       trajectory,           # centre line, mm dicts (legacy)
        "trajectory_upper": trajectory_upper,     # upper bound, mm dicts
        "trajectory_lower": trajectory_lower,     # lower bound, mm dicts
        "trajectory_metrics": traj_metrics,       # throw_distance, impact_v, etc.
        # Bearing
        "L10": round(L10, 0),
        # Material behaviour (v1.2.0 — advisory, does not override user fill)
        "mat_behavior":          mat_behavior,
        "recommended_fill_pct":  mat_behavior["recommended_fill_pct"],
        "min_fill_pct":          mat_behavior.get("min_fill_pct", 40),
        "max_fill_pct":          mat_behavior.get("max_fill_pct", 95),
        # Wrap angle geometry (v1.9.0)
        "wrap_geom_deg":         round(_wrap_geom, 1),
        "wrap_effective_deg":    _wrap_eff,
        # Sweep data
        "speed_sweep": speed_sweep, "fill_sweep": fill_sweep,
        # Structural detail — v1.3.0
        "hub":               hub,
        "key_check":         key,
        "lagging":           lagging,
        "end_disc":          end_disc,
        "bolt_fatigue":      bolt_fatigue,
        "takeup_gravity":    takeup_gravity,
        "takeup_screw":      takeup_screw,
        "casing_t_mm":       round(casing_t_m * 1000.0, 1),
        "casing_panel":      casing_panel,
        "casing_stiffener":  casing_stiffener,
        "design_recommendations": design_recs,
        # Chute flow — v1.4.0
        "discharge_chute":   discharge_chute,
        # Casing clearance + stream interception — v1.4.0 (wired from physics.py)
        "casing_clearance":  casing_clearance,
        "stream_chute":      stream_chute,
        # BOM + Maintenance schedule — Tier 2
        "bom":               bom_result,
        "maintenance":       maintenance_result,
        "root_cause":        _rca(
            # Pass the result dict built so far — checks must be present
            # (checks is assembled in _build_checks above and referenced here)
            {**{k: v for k, v in {
                "Q":Q, "v":v, "cr":cr, "d_mm":d_mm, "L10":L10,
                "T1":T1, "T2":T2, "T3":T3, "F_eff":F_eff,
                "R_headshaft":R_head, "T_Nm":T_Nm, "P_total":P_total,
                "spacing":spacing, "rho":rho, "belt_w":BW_mm,
                "bucket":bucket, "mat":mat,
                "euler_check":euler_chk, "bolt_fatigue":bolt_fatigue,
                "takeup_screw":takeup_screw,
                "casing_clearance":casing_clearance,
                "casing_panel":casing_panel,
                "discharge_chute":discharge_chute,
                "bucket_mass_kg":bw_kg,
                "governed_by":governed_by,
                "d_stress_mm":d_stress_mm,
            }.items()}, "checks": checks},
            inp.model_dump(),
        ),
        # Checks
        "checks": checks,
        # Context
        "bucket": bucket, "mat": mat, "rho": rho,
        # v1.7.0 — bucket geometry for UI / report
        "bucket_style":              bucket.get("style"),
        "bucket_front_angle":        bucket.get("front_angle_deg"),
        "bucket_depth_mm":           bucket.get("depth_mm"),
        "bucket_discharge_type":     bucket.get("discharge_type"),
        "bucket_recommended_materials": bucket.get("recommended_materials", []),
        # ── Advisory outputs (3.7 / 3.8 / 3.9) ─────────────────────────────
        "bucket_recommendation":  bucket_rec,
        "dynamic_fill":           fill_eff,
        "wrap_recommendation":    wrap_rec,
        # ── Feed design (2f) ─────────────────────────────────────────────────
        "feed_design":     feed_result,
        # ── v1.8.0 Chain outputs ─────────────────────────────────────────────
        "is_chain":        is_chain,
        "chain_selected":  chain_selected,
        "chain_pull_N":    chain_pull_N,
        "chain_SF_actual": chain_SF_act,
        "chain_v_ok":      chain_v_ok,
        "sprocket":        sprocket,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINEERING CHECKS — separated for readability
# ═══════════════════════════════════════════════════════════════════════════════

def _build_checks(inp, mat, mat_behavior, bucket, Q, v, cr,
                  T1, T2, T3, F_eff, R_head,
                  d_mm, d_stress_mm, d_deflect_mm, governed_by, L10, Ceff,
                  euler_chk:        "dict | None" = None,
                  key_check:        "dict | None" = None,
                  lagging:          "dict | None" = None,
                  end_disc:         "dict | None" = None,
                  bolt_fatigue:     "dict | None" = None,
                  takeup_grav:      "dict | None" = None,
                  casing_panel:     "dict | None" = None,
                  discharge_chute:  "dict | None" = None,
                  casing_clearance: "dict | None" = None,
                  stream_chute:     "dict | None" = None,
                  is_continuous:    bool           = False,
                  boot_analysis:    "dict | None" = None,
                  # v1.8.0 chain params
                  is_chain:         bool           = False,
                  chain_selected:   "dict | None" = None,
                  chain_pull_N:     "float | None" = None,
                  chain_SF_actual:  "float | None" = None,
                  chain_v_ok:       "bool | None"  = None,
                  sprocket:         "dict | None" = None,
                  **kwargs,                         # absorb future additions
                  ) -> list:
    checks = []
    ok   = lambda msg: {"type": "ok",   "msg": msg}
    warn = lambda msg: {"type": "warn", "msg": msg}
    fail = lambda msg: {"type": "fail", "msg": msg}
    info = lambda msg: {"type": "info", "msg": msg}

    v_min, v_max = bucket["v_min"], bucket["v_max"]
    bkt_id = bucket.get("id", "?")

    # 1 — Capacity
    if Q < inp.Q_req:
        checks.append(fail(f"Capacity {Q:.1f} t/h < required {inp.Q_req} t/h [CEMA 375 §4]"))
    else:
        checks.append(ok(f"Capacity OK: {Q:.1f} t/h ≥ {inp.Q_req} t/h [CEMA 375 §4]"))

    # 2 — Belt speed vs bucket limits
    if v < v_min:
        checks.append(warn(
            f"Speed {v:.2f} m/s below CEMA min {v_min:.2f} m/s "
            f"for bucket {bkt_id} — back-legging risk [CEMA 375 §6]"))
    elif v > v_max:
        checks.append(fail(
            f"Speed {v:.2f} m/s exceeds CEMA max {v_max:.2f} m/s "
            f"for bucket {bkt_id} — scatter risk [CEMA 375 §6]"))
    else:
        checks.append(ok(
            f"Speed {v:.2f} m/s within CEMA range {v_min:.2f}–{v_max:.2f} m/s "
            f"[CEMA 375 §6]"))

    # 3 — Centrifugal ratio — logic REVERSED for HF continuous discharge
    if is_continuous:
        # For HF elevators: CR must be BELOW 1.0. Any CR ≥ 1.0 causes centrifugal
        # discharge (material is thrown, not poured) — defeats the HF design intent.
        if cr >= 1.0:
            checks.append(fail(
                f"CR={cr:.3f} ≥ 1.0 — centrifugal discharge occurring in HF elevator. "
                f"HF design requires CR < 1.0 (reduce belt speed or increase pulley D) "
                f"[CEMA 375 §3.3]"))
        elif cr >= 0.7:
            checks.append(warn(
                f"CR={cr:.3f} approaching 1.0 — centrifugal discharge onset risk in HF mode. "
                f"Optimal HF range: CR 0.3–0.7 [CEMA 375 §3.3]"))
        elif cr >= 0.3:
            checks.append(ok(
                f"CR={cr:.3f} — continuous discharge confirmed (HF optimal range 0.3–0.7) "
                f"[CEMA 375 §3.3]"))
        else:
            checks.append(warn(
                f"CR={cr:.3f} < 0.3 — very low belt speed; "
                f"check material back-flow and filling efficiency [CEMA 375 §3.3]"))
    else:
        # Standard centrifugal discharge (CC, A, B, etc.)
        if cr < 1.0:
            checks.append(warn(f"CR={cr:.3f} < 1.0 — gravity/mixed discharge [CEMA 375 §3]"))
        elif cr <= 1.8:
            checks.append(ok(f"CR={cr:.3f} — optimal centrifugal range 1.0–1.8 [CEMA 375 §3]"))
        elif cr <= 2.5:
            checks.append(info(f"CR={cr:.3f} — centrifugal discharge acceptable [CEMA 375 §3]"))
        else:
            checks.append(warn(f"CR={cr:.3f} > 2.5 — excessive scatter risk [CEMA 375 §3]"))

    # 4 — Effective CR for cohesive/moist materials (v1.2.0 — centrifugal only)
    cr_eff_threshold = mat_behavior["effective_cr_threshold"]
    if not is_continuous and cr_eff_threshold > 1.05:
        cr_eff = cr / cr_eff_threshold
        if cr_eff < 1.0:
            checks.append(warn(
                f"Material rollback factor={cr_eff_threshold:.2f} "
                f"— effective CR={cr_eff:.3f} < 1.0; "
                f"bucket retention / spillage risk for cohesive/moist material [CEMA 550 §A-12]"))
        else:
            checks.append(info(
                f"Material rollback factor={cr_eff_threshold:.2f} "
                f"— effective CR={cr_eff:.3f} — adequate for this material [CEMA 550 §A-12]"))
    elif is_continuous:
        # For HF: cohesion affects how cleanly material pours from the inverted bucket
        cohesion = float(mat.get("cohesion", 0) or 0)
        if cohesion > 0.5:
            checks.append(warn(
                f"Material cohesion {cohesion:.2f} kPa — bridging risk in inverted bucket. "
                f"Consider vibrators on head-section casing [CEMA 550 §A-12]"))
        elif cohesion > 0.2:
            checks.append(info(
                f"Material cohesion {cohesion:.2f} kPa — monitor bucket discharge; "
                f"some residual retention expected [CEMA 550 §A-12]"))

    # 5 — Advisory fill vs material recommendation
    rec_fill = mat_behavior["recommended_fill_pct"]
    if inp.fill_pct > rec_fill + 10.0:
        checks.append(warn(
            f"User fill {inp.fill_pct:.0f}% > material-recommended {rec_fill:.0f}% "
            f"— overflow / spillage risk [CEMA 550 §A-12]"))
    elif inp.fill_pct < rec_fill - 15.0:
        checks.append(info(
            f"User fill {inp.fill_pct:.0f}% — material allows up to {rec_fill:.0f}% "
            f"— capacity headroom available"))

    # 6 — Headshaft load
    T_total = T1 + T2 + T3
    if T_total > 80000:
        checks.append(fail(
            f"Headshaft load {T_total/1000:.1f} kN — verify belt/pulley ratings [CEMA 375 §4]"))
    elif T_total > 50000:
        checks.append(warn(
            f"Headshaft load {T_total/1000:.1f} kN — approaching heavy-duty belt [CEMA 375 §4]"))
    else:
        checks.append(ok(
            f"Headshaft load {T_total/1000:.1f} kN — within standard belt capacity [CEMA 375 §4]"))

    # 6b — Belt slip (Euler-Eytelwein) — skipped for chain elevators
    if euler_chk is not None and not is_chain:
        e_ratio = euler_chk.get("euler_ratio")
        t3_min  = euler_chk.get("T2_minimum", 0)
        if e_ratio is None:
            pass  # ratio not computed (e.g. CR < 1 continuous mode)
        elif euler_chk.get("slip_safe") is True:
            checks.append(ok(
                f"Belt slip check: T3={T3:.0f} N ≥ Euler min {t3_min:.0f} N "
                f"(e^μθ={e_ratio:.3f}, μ={inp.mu}, wrap={inp.wrap_deg or 180:.0f}°) — no slip [CEMA 375 §4]"))
        else:
            checks.append(fail(
                f"BELT SLIP RISK: T3={T3:.0f} N < Euler min {t3_min:.0f} N "
                f"(e^μθ={e_ratio:.3f}, μ={inp.mu}, wrap={inp.wrap_deg or 180:.0f}°). "
                f"Increase take-up tension, add snub pulley, or upgrade lagging [CEMA 375 §4]"))

    # 7 — Shaft sizing
    checks.append(info(
        f"Shaft governed by {governed_by}: {d_mm:.1f} mm "
        f"(stress {d_stress_mm:.1f} mm, deflection {d_deflect_mm:.1f} mm) [CEMA 375 §4]"))

    # 8 — Bearing life
    if L10 < 20000:
        checks.append(warn(f"Bearing L10={L10:.0f} h < 20,000 h minimum [CEMA 375 §4]"))
    elif L10 < 40000:
        checks.append(info(f"Bearing L10={L10:.0f} h — acceptable [CEMA 375 §4]"))
    else:
        checks.append(ok(f"Bearing L10={L10:.0f} h — excellent [CEMA 375 §4]"))

    # 9 — Drive efficiency
    if Ceff > 1.25:
        checks.append(warn(f"Ceff={Ceff:.2f} — high drive losses [CEMA 375 §4]"))

    # 10 — Abrasion
    abr = mat.get("abr_code", 3)
    if abr >= 6:
        checks.append(warn(
            f"Abrasion class {abr}/7 — AR400/AR500 buckets and casing liners "
            f"strongly recommended [CEMA 550]"))
    elif abr >= 4:
        checks.append(info(
            f"Abrasion class {abr}/7 — hardened bucket lip recommended [CEMA 550]"))

    # 11 — Hazard flags (v1.2.0)
    hazards = mat_behavior["hazards"]
    if hazards.get("atex_required", False):
        checks.append(warn(
            "Explosive/flammable material — ATEX/NEC Class II: "
            "anti-static belt, earth bonding, explosion venting [CEMA 550 §B-10/B-11]"))
    if hazards.get("dust_control_required", False):
        checks.append(info(
            "Material aerates or is flammable — dust control and boot venting "
            "required [CEMA 550 §B-1/B-11]"))
    if hazards.get("stainless_recommended", False):
        checks.append(warn(
            "Corrosive material — 316L stainless or coated casings/buckets [CEMA 550 §B-4]"))
    if hazards.get("hygroscopic", False):
        checks.append(info(
            "Hygroscopic material — seal casing openings; monitor moisture "
            "content in storage [CEMA 550 §B-8]"))

    # 12 — Hub & keyway [ASME B17.1]
    if key_check:
        if key_check["pass"]:
            checks.append(ok(
                f"Keyway: shear {key_check['tau_actual_MPa']} MPa, "
                f"bearing {key_check['sigma_actual_MPa']} MPa — "
                f"{key_check['b_key_mm']}x{key_check['h_key_mm']}mm key within limits [ASME B17.1]"))
        else:
            checks.append(fail(
                f"Keyway FAIL — {key_check['recommendation']} [ASME B17.1]"))

    # 13 — Pulley lagging
    if lagging:
        lag = lagging["lagging_type"].replace("_", " ")
        if not lagging["slip_safe"]:
            checks.append(fail(
                f"Lagging slip FAIL: belt ratio {lagging['belt_ratio_tight_slack']:.3f} "
                f"> Euler {lagging['euler_ratio_lagged']:.3f} even with {lag}. "
                f"Increase T3 or add snub pulley [CEMA 375 §4]"))
        elif lagging["upgraded"]:
            checks.append(warn(
                f"Lagging auto-upgraded to ceramic (slip prevention). "
                f"Verify {lag}, t={lagging['thickness_mm']}mm with supplier [CEMA 375 §4]"))
        else:
            checks.append(info(
                f"Lagging: {lag}, t={lagging['thickness_mm']}mm, "
                f"μ={lagging['mu_operating']:.2f} — slip safe "
                f"(ratio {lagging['belt_ratio_tight_slack']:.3f} < "
                f"Euler {lagging['euler_ratio_lagged']:.3f}) [CEMA 375 §4]"))

    # 14 — Pulley end disc [CEMA Pulley Standard]
    if end_disc:
        SF = end_disc["safety_factor"]
        t  = end_disc["t_governing_mm"]
        t_specified = round(t * 1.20, 0)   # 20% design margin on structural minimum
        # SF ≈ 1.0 is the correct result for calculated minimum thickness.
        # The check always reports the minimum and the recommended specified thickness.
        # Only fail if geometry produces SF < 0.95 (numerical or input error).
        if SF < 0.95:
            checks.append(fail(
                f"End disc geometry error: SF={SF:.2f} < 1.0 at t={t}mm. "
                f"Check hub OD vs pulley diameter inputs [CEMA Pulley Standard]"))
        else:
            checks.append(info(
                f"End disc: min t={t}mm (governed by {end_disc['governed_by']}). "
                f"Specify t={t_specified:.0f}mm in drawings (+20% margin). "
                f"Full Roark or FEA required for fabrication [CEMA Pulley Standard]"))

    # 15 — Bucket bolt fatigue [CEMA 375 §7]
    if bolt_fatigue:
        gr = bolt_fatigue["goodman_ratio"]
        if not bolt_fatigue["pass_infinite_life"]:
            life = bolt_fatigue.get("life_years") or 0
            checks.append(fail(
                f"Bolt fatigue FAIL: Goodman {gr:.3f} > 1.0 "
                f"(life {life:.0f} yr) — upgrade grade or increase diameter [CEMA 375 §7]"))
        elif gr > 0.7:
            checks.append(warn(
                f"Bolt fatigue: Goodman {gr:.3f} — consider grade 10.9 "
                f"({bolt_fatigue['n_bolts']}x M{bolt_fatigue['bolt_dia_mm']:.0f}) [CEMA 375 §7]"))
        else:
            checks.append(ok(
                f"Bolt fatigue: Goodman {gr:.3f} — infinite life "
                f"(grade {bolt_fatigue['bolt_grade']}, "
                f"{bolt_fatigue['n_bolts']}x M{bolt_fatigue['bolt_dia_mm']:.0f}) [CEMA 375 §7]"))

    # 16 — Take-up
    if takeup_grav:
        W  = takeup_grav["W_counterweight_kg_gross"]
        tr = takeup_grav["travel_m"] * 1000
        checks.append(info(
            f"Gravity take-up: counterweight {W:.0f} kg (gross), "
            f"travel {tr:.0f} mm required [CEMA 375 §4]"))

    # 17 — Casing panel deflection
    if casing_panel:
        da = casing_panel["delta_actual_mm"]
        dl = casing_panel["delta_allow_mm"]
        if casing_panel["status"] == "fail":
            checks.append(warn(
                f"Casing panel: δ={da:.1f}mm > L/360={dl:.1f}mm — "
                f"reduce stiffener spacing [CEMA 375 §7]"))
        else:
            checks.append(ok(
                f"Casing panel OK: δ={da:.1f}mm < L/360={dl:.1f}mm "
                f"at {casing_panel['a_mm']:.0f}mm pitch [CEMA 375 §7]"))

    # 18-20 — Discharge chute (ChuteFlowEngine v1.4.0)
    if discharge_chute:
        perf   = discharge_chute.get("performance", {})
        maint  = discharge_chute.get("maintenance", {})
        regime = perf.get("flow_regime", "—")
        angle  = perf.get("chute_angle_deg", 0)
        min_a  = perf.get("min_angle_deg", 0)
        mass_a = perf.get("mass_flow_angle_deg", 0)
        dust   = maint.get("dust_risk", "LOW")
        plug   = maint.get("plugging_risk", "LOW")
        liner  = maint.get("liner_material", "—")

        # 18 — Flow regime
        if regime == "PLUGGING_RISK":
            checks.append(fail(
                f"Discharge chute: PLUGGING RISK at {angle:.0f}° "
                f"(wall-friction minimum = {min_a:.0f}°) [CEMA 375 §5]"))
        elif regime == "FUNNEL_FLOW":
            checks.append(warn(
                f"Discharge chute: funnel flow at {angle:.0f}° — "
                f"steepen to {mass_a:.0f}° for mass flow [CEMA 375 §5]"))
        else:
            checks.append(ok(
                f"Discharge chute: mass flow at {angle:.0f}° "
                f"(min {min_a:.0f}°) [CEMA 375 §5]"))

        # 19 — Dust risk
        if dust in ("HIGH", "SEVERE"):
            checks.append(warn(
                f"Chute dust risk {dust} — extraction or suppression system required "
                f"[CEMA 550 §B]"))
        else:
            checks.append(info(f"Chute dust risk {dust}"))

        # 20 — Plugging & liner
        if plug in ("HIGH", "SEVERE"):
            checks.append(warn(
                f"Chute plugging probability {plug} (index "
                f"{maint.get('plugging_index','—'):.2f}) — "
                f"vibrators / air cannons required; specify {liner} liner [CEMA 375 §5]"))
        else:
            checks.append(ok(
                f"Chute plugging: {plug} risk — {liner} liner specified"))

    # 21 — Casing clearance — different logic for continuous vs centrifugal
    if casing_clearance:
        if is_continuous:
            # HF: check is CR < 1.0 (continuous_casing_check result)
            cent_risk = casing_clearance.get("centrifugal_risk", False)
            cr_val    = casing_clearance.get("cr", cr)
            if cent_risk:
                checks.append(fail(
                    f"HF casing: CR={cr_val:.3f} ≥ 1.0 — centrifugal discharge "
                    f"will occur. Reduce belt speed below "
                    f"v = {9.81 * inp.D_mm / 2000.0:.2f} m/s [CEMA 375 §3.3]"))
            else:
                checks.append(ok(
                    f"HF casing: CR={cr_val:.3f} < 1.0 — continuous discharge "
                    f"confirmed; no stream-strike risk [CEMA 375 §3.3]"))
        else:
            # Centrifugal: check stream vs casing wall (existing logic)
            clears    = casing_clearance.get("clears", True)
            clearance = casing_clearance.get("clearance_m", 0.0)
            max_x     = casing_clearance.get("max_x_m", 0.0)
            wall_x    = casing_clearance.get("casing_wall_x_m", 0.0)
            if not clears:
                sx = casing_clearance.get("strike_x_m")
                sy = casing_clearance.get("strike_y_m")
                loc = f" at x={sx:.3f}m, y={sy:.3f}m" if sx is not None else ""
                checks.append(fail(
                    f"Casing clearance: stream strikes casing wall{loc} "
                    f"(stream max x={max_x:.3f}m, wall at {wall_x:.3f}m) — "
                    f"increase casing width or reduce belt speed [CEMA 375 §7]"))
            elif clearance < 0.020:
                checks.append(warn(
                    f"Casing clearance: only {clearance*1000:.0f}mm margin "
                    f"(stream max x={max_x:.3f}m, wall at {wall_x:.3f}m) — "
                    f"borderline; verify at maximum speed [CEMA 375 §7]"))
            else:
                checks.append(ok(
                    f"Casing clearance: {clearance*1000:.0f}mm — stream clears "
                    f"casing wall by adequate margin [CEMA 375 §7]"))

    # 22 — Stream interception (does discharge stream enter the chute?)
    if stream_chute:
        intercepted = stream_chute.get("intercepted", False)
        if is_continuous:
            # HF chute always intercepts the pour (positioned behind the head pulley)
            angle_rec = stream_chute.get("chute_angle_rec_deg")
            note      = stream_chute.get("note", "")
            ang_str   = f"Back plate ≥ {angle_rec:.0f}°" if angle_rec else ""
            checks.append(ok(
                f"Stream interception: HF continuous discharge — chute positioned "
                f"behind head pulley captures pour. {ang_str} [CEMA 375 §5]"))
        elif intercepted:
            ang = stream_chute.get("impact_angle_deg")
            vel = stream_chute.get("impact_velocity_mps")
            ang_str = f"{ang:.1f}°" if ang is not None else "—"
            vel_str = f"{vel:.2f} m/s" if vel is not None else "—"
            checks.append(ok(
                f"Stream interception: chute captures discharge "
                f"(impact angle={ang_str}, impact velocity={vel_str}) [CEMA 375 §5]"))
        else:
            note = stream_chute.get("note", "Stream does not reach chute inlet")
            checks.append(warn(
                f"Stream interception: {note} — "
                f"review chute position or increase belt speed [CEMA 375 §5]"))

    # 22b — Head:boot pulley diameter ratio (CEMA §3.2)
    _boot_D_mm_chk = (inp.D_mm if getattr(inp, "boot_pulley_same_as_head", False)
                      else inp.boot_pulley_D_mm)
    _D_ratio_check = inp.D_mm / max(_boot_D_mm_chk, 1.0)
    if _D_ratio_check > 2.5:
        checks.append(fail(
            f"Head:boot pulley ratio {_D_ratio_check:.2f} > 2.5 — severe belt flex fatigue. "
            f"Increase boot pulley to \u2265 {inp.D_mm/2.5:.0f}mm [CEMA 375 \u00a73.2]"))
    elif _D_ratio_check > 2.0:
        checks.append(warn(
            f"Head:boot pulley ratio {_D_ratio_check:.2f} — CEMA recommends ≤ 2.0. "
            f"Increase boot pulley to ≥ {inp.D_mm/2.0:.0f}mm [CEMA 375 §3.2]"))
    else:
        checks.append(ok(
            f"Head:boot pulley ratio {_D_ratio_check:.2f} — within CEMA limit [CEMA 375 §3.2]"))

    # 23 — Boot pulley CR check (v1.6.0)
    if boot_analysis:
        cr_boot = boot_analysis.get("cr_boot", 0)
        boot_D  = boot_analysis.get("boot_D_mm", 300)
        head_D  = boot_analysis.get("head_D_mm", 500)
        L10_b   = boot_analysis.get("L10_boot_h", 0)
        same    = boot_analysis.get("same_diameter", False)

        if cr_boot >= 1.0:
            checks.append(warn(
                f"Boot pulley CR={cr_boot:.3f} ≥ 1.0 — material may be centrifugally "
                f"re-distributed in boot section. Consider larger boot pulley D or lower speed "
                f"[CEMA 375 §4]"))
        elif same:
            checks.append(ok(
                f"Boot = Head = {boot_D:.0f}mm — matched pulleys, balanced shaft loads "
                f"[CEMA 375 §4]"))
        else:
            ratio = boot_D / max(head_D, 1)
            if ratio < 0.5:
                checks.append(warn(
                    f"Boot pulley {boot_D:.0f}mm = {ratio:.2f}× head {head_D:.0f}mm — "
                    f"very small boot increases belt scooping impact [CEMA 375 §4]"))
            else:
                checks.append(info(
                    f"Boot {boot_D:.0f}mm vs Head {head_D:.0f}mm (ratio {ratio:.2f}) — "
                    f"{boot_analysis.get('note','')[:60]} [CEMA 375 §4]"))

        if L10_b > 0:
            if L10_b < 20000:
                checks.append(warn(
                    f"Boot bearing L10={L10_b:,.0f}h < 20,000h — review boot shaft load "
                    f"or upgrade bearing [CEMA 375 §4]"))
            else:
                checks.append(info(
                    f"Boot bearing L10={L10_b:,.0f}h [CEMA 375 §4]"))

    # ── v1.8.0 Chain elevator checks ─────────────────────────────────────────
    _chain_pull_N = chain_pull_N or 0.0
    _chain_sf_req = float(getattr(inp, "chain_sf", 6.0) or 6.0)

    if is_chain and chain_selected:
        _chain_sel    = chain_selected
        _chain_SF_act = chain_SF_actual
        # Chain working load safety factor
        if _chain_SF_act is not None:
            if _chain_SF_act < _chain_sf_req:
                checks.append(fail(
                    f"Chain SF = {_chain_SF_act:.2f} < required {_chain_sf_req:.1f} "
                    f"— chain pull {_chain_pull_N/1000:.1f}kN exceeds "
                    f"{_chain_sel['name']} working load / SF. "
                    f"Upgrade to heavier chain series [CEMA 375 §4]."))
            elif _chain_SF_act < _chain_sf_req * 1.10:
                checks.append(warn(
                    f"Chain SF = {_chain_SF_act:.2f} — within 10% of minimum "
                    f"{_chain_sf_req:.1f}. Monitor chain elongation [CEMA 375 §4]."))
            else:
                checks.append(ok(
                    f"Chain SF = {_chain_SF_act:.2f} ≥ {_chain_sf_req:.1f} "
                    f"({_chain_sel['name']}, pull {_chain_pull_N/1000:.1f}kN) [CEMA 375 §4]"))

        # Chain speed vs rated maximum
        if chain_v_ok is not None:
            if not chain_v_ok:
                checks.append(fail(
                    f"Belt speed {v:.2f} m/s exceeds {_chain_sel['name']} "
                    f"rated maximum {_chain_sel['v_max_ms']:.2f} m/s — "
                    f"reduce RPM or use heavier chain series [CEMA 375 §4]."))
            else:
                checks.append(ok(
                    f"Chain speed {v:.2f} m/s ≤ rated {_chain_sel['v_max_ms']:.2f} m/s "
                    f"[CEMA 375 §4]"))

        # Sprocket tooth count
        if sprocket:
            if not sprocket["smooth"]:
                checks.append(warn(
                    f"Sprocket teeth = {sprocket['n_teeth']} "
                    f"— recommend 10–20 teeth for smooth chain engagement. "
                    f"PD = {sprocket['PD_mm']:.0f}mm [CEMA 375 §4]."))
            else:
                checks.append(ok(
                    f"Sprocket: {sprocket['n_teeth']} teeth, "
                    f"PD = {sprocket['PD_mm']:.0f}mm ✓ [CEMA 375 §4]"))

    return checks


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

def run_optimizer(req: OptimizerRequest) -> List[dict]:
    """
    Grid-search optimizer: RPM × Bucket Series × Fill factor.

    v1.4.0 improvements
    ────────────────────
    • "discharge" objective added — scores on CR proximity to ideal 1.2–1.5 range
    • "balanced" weights rebalanced to include discharge quality (D factor)
    • Euler slip check on every candidate — slip_ok and slip_margin in output
    • Bearing life quick estimate per candidate (L10 from ISO 281 simplified)
    • All design parameters used: mu, wrap_deg, environment, belt_type, sf
    • CR penalty refined — soft quadratic penalty outside [1.0, 2.5],
      hard exclusion outside [0.7, 3.0]
    • Returns top 20 candidates sorted by score; each has rank field

    Objective weights
    ─────────────────
    Each term is normalised over a representative range, then weighted.
    Weights sum to 1.0 within each objective.

    Objective   P (power)  T (tension)  M (motor)  D (discharge)
    ──────────────────────────────────────────────────────────────
    power         0.70        0.15        0.10        0.05
    tension       0.15        0.70        0.10        0.05
    motor         0.15        0.15        0.70        0.00
    discharge     0.15        0.20        0.15        0.50
    balanced      0.35        0.30        0.20        0.15

    Normalisation ranges (cover 95%+ of practical elevators):
      P: 0–400 kW    T: 0–400 kN    M: 0–400 kW    D: 0–1 (penalty)
    """
    import math as _math

    inp  = req.base_input
    mat  = get_material(inp.mat_id)
    rho  = inp.custom_rho if inp.custom_rho > 0 else mat["rho_loose"]
    D_boot_m  = inp.boot_pulley_D_mm / 1000.0
    Leq  = inp.Leq  if inp.Leq  > 0 else mat.get("Leq_default", LEQ_DEFAULT)
    Ceff = inp.Ceff if inp.Ceff > 0 else mat.get("Ceff_default", CEFF_BELT)
    objective = (req.objective or "balanced").lower()

    # Design parameters — all used for slip and bearing checks
    mu_use       = getattr(inp, "mu",               0.35)
    # Compute effective wrap the same way as solve_elevator (wrap_deg=0 means auto)
    _Dh_opt = float(inp.D_mm or 500)
    _Db_opt = float(inp.boot_pulley_D_mm or 300)
    _C_opt  = inp.H_m * 1000.0 + _Dh_opt/2.0 + _Db_opt/2.0
    _sin_o  = max(-1.0, min(1.0, (_Dh_opt/2.0 - _Db_opt/2.0) / max(_C_opt, 1.0)))
    _wg_opt = 180.0 + 2.0 * math.degrees(math.asin(_sin_o))
    _wi_opt = float(getattr(inp, "wrap_deg", 0) or 0)
    if _wi_opt >= 90.0:
        wrap_use = _wi_opt
    elif getattr(inp, "snub_pulley", False):
        wrap_use = min(_wg_opt + 30.0, 240.0)
    else:
        wrap_use = _wg_opt
    K_takeup     = getattr(inp, "K_takeup",           0.7)
    belt_type    = getattr(inp, "belt_type",          "EP")
    environment  = getattr(inp, "environment",       "dry")
    sf           = getattr(inp, "sf",                1.25)

    # Euler limit from lagging type + environment (fast lookup — no full solve)
    # Wet/submerged service degrades rubber friction: apply 0.85 factor
    env_factor   = 0.85 if environment in ("wet", "submerged") else \
                   0.92 if environment == "humid" else 1.0
    mu_eff       = mu_use * env_factor
    euler_limit  = _math.exp(mu_eff * wrap_use * _math.pi / 180.0)

    # Objective weight tables
    OBJ_WEIGHTS = {
        "power":     {"P": 0.70, "T": 0.15, "M": 0.10, "D": 0.05},
        "tension":   {"P": 0.15, "T": 0.70, "M": 0.10, "D": 0.05},
        "motor":     {"P": 0.15, "T": 0.15, "M": 0.70, "D": 0.00},
        "discharge": {"P": 0.15, "T": 0.20, "M": 0.15, "D": 0.50},
        "balanced":  {"P": 0.35, "T": 0.30, "M": 0.20, "D": 0.15},
    }
    W = OBJ_WEIGHTS.get(objective, OBJ_WEIGHTS["balanced"])

    candidates = []

    for bucket in BUCKET_SERIES:
        bw_kg = bucket.get("bucket_mass_kg", bucket["V"] * 1.5)

        for rpm in range(40, 161, 10):
            for fill in range(60, 91, 5):
                v = belt_speed(inp.D_mm, rpm)

                # Hard speed limits
                if v < bucket["v_min"] or v > bucket["v_max"]:
                    continue

                spacing = (bucket["P"] + inp.bucket_gap) / 1000.0
                Q = calc_capacity(v, spacing, bucket["V"], fill, rho)
                if Q < inp.Q_req:
                    continue

                pwr    = calc_power_cema375(Q, inp.H_m, D_boot_m, Leq, Ceff)
                P_total = pwr["P_total"]
                BW_mm  = select_belt_width(bucket["W"])
                tens   = calc_headshaft_tensions(
                    Q, inp.H_m, v, bw_kg, spacing, BW_mm, K_takeup,
                )
                T1, T2, T3 = tens["T1"], tens["T2"], tens["T3"]
                T_head  = T1 + T2 + T3
                cr      = centrifugal_ratio(v, inp.D_mm)
                motor   = select_motor(P_total, sf)

                # ── Euler slip check ─────────────────────────────────────────
                T3_euler_min = T1 / euler_limit if euler_limit > 0 else 0
                slip_ok      = T3 >= T3_euler_min
                slip_margin  = (T3 / T3_euler_min - 1.0) * 100 \
                               if T3_euler_min > 0 else 100.0
                slip_penalty = 0 if slip_ok else 500.0    # hard exclusion

                # ── Discharge quality score ──────────────────────────────────
                # CR ideal range: 1.20–1.50 (clean centrifugal at minimal energy)
                # Quadratic penalty rising outside that range, capped at 1.0
                CR_IDEAL_LO, CR_IDEAL_HI = 1.20, 1.50
                CR_HARD_LO,  CR_HARD_HI  = 0.70, 3.00
                _bkt_type_o = (bucket.get("type") or "").upper()
                _is_cont_o  = _bkt_type_o in ("HF", "MF", "SC")
                if _is_cont_o:
                    # Continuous: CR must be < 1.0; target 0.30–0.70
                    if cr >= 1.0 or cr < 0.20:
                        continue
                    d_penalty = 0.0 if 0.30 <= cr <= 0.70 else min(1.0, ((abs(cr - 0.50)) / 0.30)**2)
                else:
                    # Centrifugal: CR must be ≥ 1.0; target 1.20–1.50
                    if cr < CR_HARD_LO or cr > CR_HARD_HI:
                        continue
                    if CR_IDEAL_LO <= cr <= CR_IDEAL_HI:
                        d_penalty = 0.0
                    elif cr < CR_IDEAL_LO:
                        d_penalty = min(1.0, ((CR_IDEAL_LO - cr) / 0.50) ** 2)
                    else:
                        d_penalty = min(1.0, ((cr - CR_IDEAL_HI) / 1.00) ** 2)

                # ── Bearing life quick estimate (ISO 281 simplified) ─────────
                # Approximate radial load as headshaft resultant (2 × T_head)
                R_approx   = 2.0 * T_head          # [N] — conservative
                # Representative catalogue value for medium-bore pillow block
                # (SKF SY 60 TF class: C ≈ 75kN basic dynamic)
                C_bearing  = 75_000.0
                L10_h_est  = 0
                if R_approx > 0:
                    L10_h_est = int(
                        (C_bearing / R_approx) ** 3
                        * 1_000_000 / (60.0 * max(rpm, 1))
                    )

                # ── Normalised scores ────────────────────────────────────────
                P_norm = P_total  / 400.0
                T_norm = T_head   / 400_000.0
                M_norm = motor    / 400.0
                D_norm = d_penalty                # already in [0, 1]

                score = (
                    W["P"] * P_norm
                    + W["T"] * T_norm
                    + W["M"] * M_norm
                    + W["D"] * D_norm
                    + slip_penalty
                )

                candidates.append({
                    # Identity
                    "rpm":         rpm,
                    "bucket_id":   bucket["id"],
                    "fill":        fill,
                    # Performance
                    "speed":       round(v, 2),
                    "capacity":    round(Q, 1),
                    "cr":          round(cr, 3),
                    # Power
                    "power":       round(P_total, 2),
                    "motor_kw":    motor,
                    # Tension
                    "headshaft_kN":round(T_head / 1000, 2),
                    "T1_kN":       round(T_head / 1000, 2),  # backward compat
                    "T3_kN":       round(T3 / 1000, 2),
                    "T3_min_kN":   round(T3_euler_min / 1000, 2),
                    # Feasibility
                    "slip_ok":     slip_ok,
                    "slip_margin_pct": round(slip_margin, 1),
                    "L10_est_h":   L10_h_est,
                    "cr_discharge_penalty": round(d_penalty, 4),
                    # Score
                    "score":       round(score, 4),
                    "objective":   objective,
                })

    # Sort, rank, return top 20
    candidates.sort(key=lambda c: c["score"])
    # Exclude slip failures from ranking (still include at bottom for reference)
    ranked  = [c for c in candidates if c.get("slip_ok", True)]
    slipped = [c for c in candidates if not c.get("slip_ok", True)]

    final = ranked[:20] + slipped[:max(0, 20 - len(ranked[:20]))]
    for i, c in enumerate(final[:20]):
        c["rank"] = i + 1
    return final[:20]