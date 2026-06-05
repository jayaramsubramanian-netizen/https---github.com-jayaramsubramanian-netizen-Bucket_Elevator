"""
VECTRIX™ — Engineering Constants
Aligned with CEMA No. 375-2017 and ANSI/CEMA 550-2020

CHANGES FROM ORIGINAL
─────────────────────
1. STEEL_ALLOWABLE_STRESS: 40 MPa → 55 MPa (shear, A36)
   CEMA 375 §4 shaft design uses τ_allow = 55 MPa for A36 mild steel
   (Sy = 250 MPa, Ssy = 0.577 × 250 = 144 MPa, with FS = 2.6 → 55 MPa)

2. DEFAULT_SHOCK_FACTOR removed — CEMA 375 does not define a separate
   shock factor. Shock loads are absorbed into DEFAULT_SERVICE_FACTOR.
   Using both simultaneously double-counts and over-sizes the motor.

3. DEFAULT_SERVICE_FACTOR: kept at 1.5 — correct for chain-type;
   use 1.25 for belt-type. Caller should pass explicitly.

4. Added: CEMA_MAX_SHAFT_SLOPE, SHAFT_E_PA, SHAFT_Su_PA, SHAFT_Sy_PA
   Required by CEMA 375 §4 combined stress + deflection shaft design.

5. Added: BELT_PIW_DEFAULT, BUCKET_STEEL_DENSITY
   Required by CEMA 375 §4 T2 (up-side belt/bucket weight) calculation.

6. Added: LEQ_DEFAULT, CEFF_BELT, CEFF_CHAIN
   Required by CEMA 375 §4 Length Equivalency power method.
"""

# ── Gravity ─────────────────────────────────────────────────────────────────
GRAVITY = 9.81                  # m/s²

# ── Service & startup factors (CEMA 375 §4) ─────────────────────────────────
DEFAULT_SERVICE_FACTOR  = 1.25  # belt-type; use 1.50 for chain
DEFAULT_SERVICE_FACTOR_CHAIN = 1.50
DEFAULT_STARTUP_FACTOR  = 2.0   # CEMA 375 §4: 1.5–2.0 belt, 2.0–2.5 chain
                                # Original 2.2 was high-end chain value; 2.0 is correct default

# ── Shaft material — ASTM A36 mild steel (CEMA 375 §4) ──────────────────────
STEEL_ALLOWABLE_STRESS  = 55e6  # Pa — allowable shear/torsion stress, A36
                                # Original was 40 MPa (27% too conservative → oversized shafts)
SHAFT_Sy_PA             = 250e6 # Pa — yield strength, A36
SHAFT_Su_PA             = 400e6 # Pa — ultimate tensile strength, A36
SHAFT_E_PA              = 200e9 # Pa — modulus of elasticity (steel)
SHAFT_Ka                = 0.80  # surface factor (machined finish)
SHAFT_Kc                = 0.897 # reliability factor (99%)
SHAFT_Kd                = 1.0   # temperature factor (−70°F to 400°F)
SHAFT_FS                = 2.0   # CEMA-recommended safety factor for head shaft

# ── CEMA pulley standard — max shaft slope at bushing ───────────────────────
CEMA_MAX_SHAFT_SLOPE    = 0.0015  # in/in (dimensionless) per CEMA pulley std

# ── Belt weight (CEMA 375 §4, T2 calculation) ───────────────────────────────
BELT_WEIGHT_DEFAULT = 8.0    # kg/m²
BELT_PIW_DEFAULT    = BELT_WEIGHT_DEFAULT   # deprecated alias

# ── Bucket material density ──────────────────────────────────────────────────
BUCKET_STEEL_DENSITY    = 7850  # kg/m³ — for bucket self-weight estimation

# ── CEMA 375 §4 — LEQ power method defaults ─────────────────────────────────
LEQ_DEFAULT             = 7     # length equivalency factor, spaced-bucket centrifugal
LEQ_CONTINUOUS          = 4     # length equivalency factor, continuous bucket
CEFF_BELT               = 1.15  # drive efficiency factor, belt + shaft-mount gearbox
CEFF_CHAIN              = 1.25  # drive efficiency factor, chain + sprocket

# ── Air & environment ────────────────────────────────────────────────────────
AIR_DENSITY             = 1.225 # kg/m³ at sea level, 15°C
