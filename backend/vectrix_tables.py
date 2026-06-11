"""
VECTRIX™ Unified ORM — vectrix_tables.py
─────────────────────────────────────────────────────────────────────────────
Merges the screw conveyor material/component schema with the bucket elevator
material schema.  Every column from both systems is present; columns that only
apply to one module are NULL for rows from the other module.

App tagging
───────────
Every row carries an `app` JSON array that declares which VECTRIX modules can
use it.  Standard tags:
  "be"   — AKSHAYVIPRA EL-MEC bucket elevator
  "sc"   — screw conveyor
  "conv" — generic conveyor (inherited from screw conveyor seed)
  "dry"  — drying process
  "mix"  — mixing process
  "feed" — metered feed application

Shared component tables (Bearing, Gearbox, Motor, Drive, CostItem) are copied
unchanged from the screw conveyor schema — they are used by both modules.

Version: 1.0.0
"""

from sqlalchemy import (  # type: ignore[import]
    Column, Integer, Float, String, Text, JSON, Boolean
)

try:
    from .vectrix_database import Base
except ImportError:
    from vectrix_database import Base


# ─── Materials ─────────────────────────────────────────────────────────────

class Material(Base):
    __tablename__ = "materials"

    # ── Identity ───────────────────────────────────────────────────────────
    id              = Column(Integer, primary_key=True, autoincrement=True)
    mat_id          = Column(String(40),  unique=True,  index=True)
    # Slug identifier used by the bucket elevator engine (e.g. "wheat", "cement").
    # Derived from the BE `id` field or slugified from `name` for SC materials.

    name            = Column(String(120), unique=True, nullable=False, index=True)
    category        = Column(String(60),  index=True)
    # Canonical short code: GRAIN/BIO/CHEM/CONST/FOOD/MIN/METAL/FERT/CEM/
    #                       COAL/GLASS/ENV/PHARM/PETRO/POLY/SALT

    category_full   = Column(String(60))
    # Verbose English name: "Agriculture", "Biomass", "Chemicals", etc.
    # Preserved from SC schema; derived for BE-only materials.

    # ── Bulk density ───────────────────────────────────────────────────────
    rho_bulk        = Column(Float, nullable=False)
    # Canonical loose bulk density [kg/m³].
    # Source: BE rho_loose directly; SC rho × 1000 (t/m³ → kg/m³).

    rho_min         = Column(Float)   # kg/m³ — from SC rho_min × 1000
    rho_max         = Column(Float)   # kg/m³ — from SC rho_max × 1000 or BE rho_vib
    rho_vib         = Column(Float)   # kg/m³ — vibrated / compacted density (BE)
    rho_sc_tm3      = Column(Float)   # t/m³  — original SC reference density (unconverted)

    # ── Flow properties ────────────────────────────────────────────────────
    flowability     = Column(Integer)
    # Canonical scale: 1=Very free, 2=Free, 3=Average, 4=Sluggish.
    # BE and SC use same 1-4 scale; SC rows with values 5-8 are clamped to 4.

    flowability_raw = Column(Integer)
    # Raw SC value (preserved so 5-8 entries are not silently altered).

    angle_repose         = Column(Float)   # ° — SC aor / BE angle_repose
    angle_surcharge      = Column(Float)   # ° — BE only
    angle_internal_friction = Column(Float) # ° — BE only
    wall_friction_deg    = Column(Float)   # ° — BE wall_friction_deg
    cohesion             = Column(Float)   # kPa
    bridging_risk        = Column(Float)   # 0.0–1.0 — SC only
    flow_regime          = Column(String(30))
    # mass_flow / funnel_flow / cohesive_flow — SC only; NULL for BE rows

    # ── Moisture & temperature ─────────────────────────────────────────────
    moisture_pct    = Column(Float)   # % — SC moist / BE moisture_pct
    temp_max        = Column(Float)   # °C — SC only; NULL for BE rows

    # ── Abrasiveness ───────────────────────────────────────────────────────
    abr_code        = Column(Integer)
    # Numeric 0–7 scale (VECTRIX BE standard).
    # Derived from SC abr text for SC materials; direct for BE materials.
    # Mapping: Low→1, Medium→3, High→5, Very High→7

    abr_text        = Column(String(20))
    # Verbose string: "Low" / "Medium" / "High" / "Very High".
    # Direct for SC; derived from abr_code for BE materials.

    # ── Particle properties ────────────────────────────────────────────────
    particle_class  = Column(String(10))
    # SC CEMA particle size class: A200/A100/A40/B6/C1/2/D3/D7

    size_code       = Column(String(20))
    # BE size code (internal descriptor)

    particle_size_mm = Column(Float)    # mm — BE only

    # ── CEMA 375 Bucket Elevator fields ───────────────────────────────────
    # NULL for SC-only materials.
    Leq_default          = Column(Float)
    # CEMA 375 §4 length equivalency factor (default for this material class)

    Ceff_default         = Column(Float)
    # CEMA 375 §4 drive efficiency factor

    vfi                  = Column(Integer)
    # Vectrix Flow Index — internal material flowability index for trajectory

    bucket_fill_factor   = Column(Float)
    # Maximum bucket fill fraction for centrifugal discharge

    stream_spread_factor = Column(Float)
    # Material stream spread factor for discharge trajectory envelope

    Km                   = Column(Float)
    # Material / trough friction coefficient (BE internal)

    hazard_codes         = Column(String(30))
    # BE hazard string (e.g. "EX,COR")

    # ── CEMA Screw Conveyor fields ─────────────────────────────────────────
    # NULL for BE-only materials.
    lambda_ref      = Column(Float)
    # CEMA 350 λ reference material factor for screw conveyor power calculation

    fill_max        = Column(Float)
    # Maximum trough fill fraction for screw conveyor (CEMA 350)

    cema_cls        = Column(String(5))
    # CEMA screw conveyor material class: I / II / III / IV

    cema_code       = Column(String(30))
    # Full CEMA code string (e.g. "46C1/212O")

    flags           = Column(String(20))
    # CEMA flag characters (e.g. "O", "U", "X")

    # ── Metadata ──────────────────────────────────────────────────────────
    confidence      = Column(Float)    # 0–1 data quality confidence
    source          = Column(String(30))
    note            = Column(Text)
    app             = Column(JSON)
    # JSON array of application tags.  Always a list, never NULL.
    # Minimum: ["be"] for BE-only, ["sc","conv",...] for SC-origin materials.

    custom          = Column(Boolean, default=False)
    # True = user-added entry; False = seeded from master database.
    # custom=False rows are replaced on --force re-seed.


# ─── Bearings ──────────────────────────────────────────────────────────────
# Unchanged from SC schema.  Used by both modules:
#   BE: head shaft pillow blocks (bore, C, L10 calculation)
#   SC: end bearings and hanger bearings (role: "end/hanger")

class Bearing(Base):
    __tablename__ = "bearings"

    id          = Column(Integer, primary_key=True)
    name        = Column(String(30), unique=True, nullable=False, index=True)
    mfr         = Column(String(20))
    type        = Column(String(20))
    bore        = Column(Float)          # mm
    od          = Column(Float)          # mm
    B           = Column(Float)          # mm  width / height
    C           = Column(Float)          # kN  basic dynamic load rating
    C0          = Column(Float)          # kN  basic static load rating
    p           = Column(Float)          # —   life exponent (3 ball, 10/3 roller)
    speed_g     = Column(Integer)        # rpm grease speed limit
    seal        = Column(String(20))     # open / sealed / shielded
    role        = Column(String(30))     # end/hanger / head / boot
    brg_insert  = Column(String(20))     # insert bearing designation
    mass_kg     = Column(Float)
    note        = Column(Text)
    custom      = Column(Boolean, default=False)


# ─── Gearboxes ─────────────────────────────────────────────────────────────
# Shared drive component.  Both modules select gearboxes by output torque.

class Gearbox(Base):
    __tablename__ = "gearboxes"

    id          = Column(Integer, primary_key=True)
    model       = Column(String(30), unique=True, nullable=False, index=True)
    type        = Column(String(5))      # W=worm / H=helical / B=bevel / P=planetary
    stages      = Column(Integer)
    Tn          = Column(Float)          # Nm  rated output torque
    Pkw         = Column(Float)          # kW  rated power at rated speed
    ratio_min   = Column(Float)
    ratio_max   = Column(Float)
    eta         = Column(Float)          # %   efficiency at full load
    mount       = Column(String(10))     # F=foot / B=flange / F/B=both
    ip          = Column(String(10))
    temp_max    = Column(Float)          # °C
    mass_kg     = Column(Float)
    note        = Column(Text)
    custom      = Column(Boolean, default=False)


# ─── Motors ────────────────────────────────────────────────────────────────

class Motor(Base):
    __tablename__ = "motors"

    id          = Column(Integer, primary_key=True)
    model       = Column(String(30), unique=True)
    frame       = Column(String(20))
    Pkw         = Column(Float)          # kW  rated power
    poles       = Column(Integer)        # pole count (4=1450rpm, 2=2900rpm)
    rpm_50hz    = Column(Float)          # rpm at 50 Hz full load
    efficiency  = Column(Float)          # % at full load
    ie_class    = Column(String(5))      # IE2 / IE3 / IE4
    ip          = Column(String(10))
    mass_kg     = Column(Float)
    note        = Column(Text)
    custom      = Column(Boolean, default=False)


# ─── Drives ────────────────────────────────────────────────────────────────

class Drive(Base):
    __tablename__ = "drives"

    id          = Column(Integer, primary_key=True)
    model       = Column(String(30), unique=True)
    type        = Column(String(5))      # VFD / SS / DOL / SD
    Pkw_max     = Column(Float)          # kW  max motor power
    Vrated      = Column(Float)          # V
    Irated      = Column(Float)          # A
    overload_pct = Column(Float)         # % e.g. 150
    control     = Column(String(30))     # V/f / SVC / FOC
    ip          = Column(String(10))
    features    = Column(Text)
    note        = Column(Text)
    custom      = Column(Boolean, default=False)


# ─── Cost reference ─────────────────────────────────────────────────────────

class CostItem(Base):
    __tablename__ = "cost_items"

    id              = Column(Integer, primary_key=True)
    item            = Column(String(60), unique=True, nullable=False, index=True)
    usd             = Column(Float, nullable=False)   # USD/kg reference price
    description     = Column(String(120))
    material_group  = Column(String(40))              # Steel / Stainless / Wear / Special
    custom          = Column(Boolean, default=False)
    note            = Column(Text)