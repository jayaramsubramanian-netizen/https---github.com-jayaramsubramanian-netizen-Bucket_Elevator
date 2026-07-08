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
  "be"   — JAYVEECONS bucket elevator
  "sc"   — screw conveyor
  "conv" — generic conveyor (inherited from screw conveyor seed)
  "dry"  — drying process
  "mix"  — mixing process
  "feed" — metered feed application

Shared component tables (Bearing, Gearbox, Motor, Drive, CostItem) are copied
unchanged from the screw conveyor schema — they are used by both modules.

Version: 1.1.0
FIX (Pylance reportAttributeAccessIssue in seed_catalog.py): every class
below previously declared columns the legacy way (`style = Column(String(10))`
directly as a class attribute). Pylance's static analysis sees that as the
CLASS-level type — literally Column[str] — and has no way to know that an
*instance* attribute assignment (`row.style = "HF"`) is actually handled by
SQLAlchemy's descriptor protocol and is perfectly valid; it just sees "str
assigned to something typed Column[str]" and flags it as a mismatch on every
single field, for every model, anywhere code constructs or mutates an
instance. This isn't a seed_catalog.py-specific issue and patching the
assignments there wouldn't have fixed it for the next script that touches
these models too. The actual fix is the modern SQLAlchemy 2.0 typed style
(Mapped[...] + mapped_column()), which gives Pylance the real instance-level
type directly -- converted every column in every class below, not just the
ones seed_catalog.py happened to touch.
"""

from typing import Optional, Any
from sqlalchemy import String, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

try:
    from .vectrix_database import Base
except ImportError:
    from vectrix_database import Base


# ─── Materials ─────────────────────────────────────────────────────────────

class Material(Base):
    __tablename__ = "materials"

    # ── Identity ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mat_id: Mapped[Optional[str]] = mapped_column(String(40), unique=True, index=True)
    # Slug identifier used by the bucket elevator engine (e.g. "wheat", "cement").
    # Derived from the BE `id` field or slugified from `name` for SC materials.

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    # Canonical short code: GRAIN/BIO/CHEM/CONST/FOOD/MIN/METAL/FERT/CEM/
    #                       COAL/GLASS/ENV/PHARM/PETRO/POLY/SALT

    category_full: Mapped[Optional[str]] = mapped_column(String(60))
    # Verbose English name: "Agriculture", "Biomass", "Chemicals", etc.
    # Preserved from SC schema; derived for BE-only materials.

    # ── Bulk density ───────────────────────────────────────────────────────
    rho_bulk: Mapped[float] = mapped_column()
    # Canonical loose bulk density [kg/m³].
    # Source: BE rho_loose directly; SC rho × 1000 (t/m³ → kg/m³).

    rho_min: Mapped[Optional[float]] = mapped_column()    # kg/m³ — from SC rho_min × 1000
    rho_max: Mapped[Optional[float]] = mapped_column()    # kg/m³ — from SC rho_max × 1000 or BE rho_vib
    rho_vib: Mapped[Optional[float]] = mapped_column()    # kg/m³ — vibrated / compacted density (BE)
    rho_sc_tm3: Mapped[Optional[float]] = mapped_column() # t/m³  — original SC reference density (unconverted)

    # ── Flow properties ────────────────────────────────────────────────────
    flowability: Mapped[Optional[int]] = mapped_column()
    # Canonical scale: 1=Very free, 2=Free, 3=Average, 4=Sluggish.
    # BE and SC use same 1-4 scale; SC rows with values 5-8 are clamped to 4.

    flowability_raw: Mapped[Optional[int]] = mapped_column()
    # Raw SC value (preserved so 5-8 entries are not silently altered).

    angle_repose: Mapped[Optional[float]] = mapped_column()   # ° — SC aor / BE angle_repose
    angle_surcharge: Mapped[Optional[float]] = mapped_column()   # ° — BE only
    angle_internal_friction: Mapped[Optional[float]] = mapped_column() # ° — BE only
    wall_friction_deg: Mapped[Optional[float]] = mapped_column()   # ° — BE wall_friction_deg
    cohesion: Mapped[Optional[float]] = mapped_column()   # kPa
    bridging_risk: Mapped[Optional[float]] = mapped_column()   # 0.0–1.0 — SC only
    flow_regime: Mapped[Optional[str]] = mapped_column(String(30))
    # mass_flow / funnel_flow / cohesive_flow — SC only; NULL for BE rows

    # ── Moisture & temperature ─────────────────────────────────────────────
    moisture_pct: Mapped[Optional[float]] = mapped_column()   # % — SC moist / BE moisture_pct
    temp_max: Mapped[Optional[float]] = mapped_column()   # °C — SC only; NULL for BE rows

    # ── Abrasiveness ───────────────────────────────────────────────────────
    abr_code: Mapped[Optional[int]] = mapped_column()
    # Numeric 0–7 scale (VECTRIX BE standard).
    # Derived from SC abr text for SC materials; direct for BE materials.
    # Mapping: Low→1, Medium→3, High→5, Very High→7

    abr_text: Mapped[Optional[str]] = mapped_column(String(20))
    # Verbose string: "Low" / "Medium" / "High" / "Very High".
    # Direct for SC; derived from abr_code for BE materials.

    # ── Particle properties ────────────────────────────────────────────────
    particle_class: Mapped[Optional[str]] = mapped_column(String(10))
    # SC CEMA particle size class: A200/A100/A40/B6/C1/2/D3/D7

    size_code: Mapped[Optional[str]] = mapped_column(String(20))
    # BE size code (internal descriptor)

    particle_size_mm: Mapped[Optional[float]] = mapped_column()    # mm — BE only

    # ── CEMA 375 Bucket Elevator fields ───────────────────────────────────
    # NULL for SC-only materials.
    Leq_default: Mapped[Optional[float]] = mapped_column()
    # CEMA 375 §4 length equivalency factor (default for this material class)

    Ceff_default: Mapped[Optional[float]] = mapped_column()
    # CEMA 375 §4 drive efficiency factor

    vfi: Mapped[Optional[int]] = mapped_column()
    # Vectrix Flow Index — internal material flowability index for trajectory

    bucket_fill_factor: Mapped[Optional[float]] = mapped_column()
    # Maximum bucket fill fraction for centrifugal discharge

    stream_spread_factor: Mapped[Optional[float]] = mapped_column()
    # Material stream spread factor for discharge trajectory envelope

    Km: Mapped[Optional[float]] = mapped_column()
    # Material / trough friction coefficient (BE internal)

    hazard_codes: Mapped[Optional[str]] = mapped_column(String(30))
    # BE hazard string (e.g. "EX,COR")

    # ── CEMA Screw Conveyor fields ─────────────────────────────────────────
    # NULL for BE-only materials.
    lambda_ref: Mapped[Optional[float]] = mapped_column()
    # CEMA 350 λ reference material factor for screw conveyor power calculation

    fill_max: Mapped[Optional[float]] = mapped_column()
    # Maximum trough fill fraction for screw conveyor (CEMA 350)

    cema_cls: Mapped[Optional[str]] = mapped_column(String(5))
    # CEMA screw conveyor material class: I / II / III / IV

    cema_code: Mapped[Optional[str]] = mapped_column(String(30))
    # Full CEMA code string (e.g. "46C1/212O")

    flags: Mapped[Optional[str]] = mapped_column(String(20))
    # CEMA flag characters (e.g. "O", "U", "X")

    # ── Metadata ──────────────────────────────────────────────────────────
    confidence: Mapped[Optional[float]] = mapped_column()    # 0–1 data quality confidence
    source: Mapped[Optional[str]] = mapped_column(String(30))
    note: Mapped[Optional[str]] = mapped_column(Text)
    app: Mapped[Optional[list]] = mapped_column(JSON)
    # JSON array of application tags.  Always a list, never NULL.
    # Minimum: ["be"] for BE-only, ["sc","conv",...] for SC-origin materials.

    custom: Mapped[bool] = mapped_column(Boolean, default=False)
    # True = user-added entry; False = seeded from master database.
    # custom=False rows are replaced on --force re-seed.


# ─── Bearings ──────────────────────────────────────────────────────────────
# Unchanged from SC schema.  Used by both modules:
#   BE: head shaft pillow blocks (bore, C, L10 calculation)
#   SC: end bearings and hanger bearings (role: "end/hanger")

class Bearing(Base):
    __tablename__ = "bearings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    mfr: Mapped[Optional[str]] = mapped_column(String(20))
    type: Mapped[Optional[str]] = mapped_column(String(20))
    bore: Mapped[Optional[float]] = mapped_column()          # mm
    od: Mapped[Optional[float]] = mapped_column()          # mm
    B: Mapped[Optional[float]] = mapped_column()          # mm  width / height
    C: Mapped[Optional[float]] = mapped_column()          # kN  basic dynamic load rating
    C0: Mapped[Optional[float]] = mapped_column()          # kN  basic static load rating
    p: Mapped[Optional[float]] = mapped_column()          # —   life exponent (3 ball, 10/3 roller)
    speed_g: Mapped[Optional[int]] = mapped_column()        # rpm grease speed limit
    seal: Mapped[Optional[str]] = mapped_column(String(20))     # open / sealed / shielded
    role: Mapped[Optional[str]] = mapped_column(String(30))     # end/hanger / head / boot
    brg_insert: Mapped[Optional[str]] = mapped_column(String(20))     # insert bearing designation
    mass_kg: Mapped[Optional[float]] = mapped_column()
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Gearboxes ─────────────────────────────────────────────────────────────
# Shared drive component.  Both modules select gearboxes by output torque.

class Gearbox(Base):
    __tablename__ = "gearboxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    type: Mapped[Optional[str]] = mapped_column(String(5))      # W=worm / H=helical / B=bevel / P=planetary
    stages: Mapped[Optional[int]] = mapped_column()
    Tn: Mapped[Optional[float]] = mapped_column()          # Nm  rated output torque
    Pkw: Mapped[Optional[float]] = mapped_column()          # kW  rated power at rated speed
    ratio_min: Mapped[Optional[float]] = mapped_column()
    ratio_max: Mapped[Optional[float]] = mapped_column()
    eta: Mapped[Optional[float]] = mapped_column()          # %   efficiency at full load
    mount: Mapped[Optional[str]] = mapped_column(String(10))     # F=foot / B=flange / F/B=both
    ip: Mapped[Optional[str]] = mapped_column(String(10))
    temp_max: Mapped[Optional[float]] = mapped_column()          # °C
    mass_kg: Mapped[Optional[float]] = mapped_column()
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Motors ────────────────────────────────────────────────────────────────

class Motor(Base):
    __tablename__ = "motors"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    frame: Mapped[Optional[str]] = mapped_column(String(20))
    Pkw: Mapped[Optional[float]] = mapped_column()          # kW  rated power
    poles: Mapped[Optional[int]] = mapped_column()        # pole count (4=1450rpm, 2=2900rpm)
    rpm_50hz: Mapped[Optional[float]] = mapped_column()          # rpm at 50 Hz full load
    efficiency: Mapped[Optional[float]] = mapped_column()          # % at full load
    ie_class: Mapped[Optional[str]] = mapped_column(String(5))      # IE2 / IE3 / IE4
    ip: Mapped[Optional[str]] = mapped_column(String(10))
    mass_kg: Mapped[Optional[float]] = mapped_column()
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Drives ────────────────────────────────────────────────────────────────

class Drive(Base):
    __tablename__ = "drives"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    type: Mapped[Optional[str]] = mapped_column(String(5))      # VFD / SS / DOL / SD
    Pkw_max: Mapped[Optional[float]] = mapped_column()          # kW  max motor power
    Vrated: Mapped[Optional[float]] = mapped_column()          # V
    Irated: Mapped[Optional[float]] = mapped_column()          # A
    overload_pct: Mapped[Optional[float]] = mapped_column()         # % e.g. 150
    control: Mapped[Optional[str]] = mapped_column(String(30))     # V/f / SVC / FOC
    ip: Mapped[Optional[str]] = mapped_column(String(10))
    features: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Cost reference ─────────────────────────────────────────────────────────

class CostItem(Base):
    __tablename__ = "cost_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    item: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    usd: Mapped[float] = mapped_column()   # USD/kg reference price
    description: Mapped[Optional[str]] = mapped_column(String(120))
    material_group: Mapped[Optional[str]] = mapped_column(String(40))              # Steel / Stainless / Wear / Special
    custom: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[Optional[str]] = mapped_column(Text)


# ─── Buckets (bucket elevator) ───────────────────────────────────────────────
# Mirrors calculations.py's BUCKET_SERIES exactly (40 seeded rows) -- this is
# the catalog select_bucket_auto()/run_optimizer()/the manual bucket picker
# all draw from. Seeded from the existing static list, not invented.

class Bucket(Base):
    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(primary_key=True)
    bucket_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # Catalog ID e.g. "HF_16x8" -- the slug calculations.py/models.py use.
    style: Mapped[Optional[str]] = mapped_column(String(10), index=True)   # HF/MF/SC/PF/AA/AC/C
    catalog: Mapped[Optional[str]] = mapped_column(String(30))                # display e.g. "HF 16x8x11"
    W_mm: Mapped[Optional[float]] = mapped_column()    # width
    H_mm: Mapped[Optional[float]] = mapped_column()    # height (depth_mm)
    P_mm: Mapped[Optional[float]] = mapped_column()    # projection
    V_L: Mapped[Optional[float]] = mapped_column()    # volume, litres
    front_angle_deg: Mapped[Optional[float]] = mapped_column()
    type: Mapped[Optional[str]] = mapped_column(String(10))     # HF/CC etc, legacy field
    discharge_type: Mapped[Optional[str]] = mapped_column(String(15))     # continuous / centrifugal
    v_min: Mapped[Optional[float]] = mapped_column()    # m/s, CEMA min belt speed
    v_max: Mapped[Optional[float]] = mapped_column()    # m/s, CEMA max belt speed
    v_opt: Mapped[Optional[float]] = mapped_column()
    pitch_mm: Mapped[Optional[float]] = mapped_column()
    bucket_mass_kg: Mapped[Optional[float]] = mapped_column()
    recommended_materials: Mapped[Optional[list]] = mapped_column(JSON)   # list of material category/id strings
    note: Mapped[Optional[str]] = mapped_column(Text)
    # Bolt mounting-flange / chain-pin data (industry-standard catalog data) -- AC and
    # SC are engineering estimates, not published dimensions (catalog says
    # not published for those two specifically) -- punch_confirmed
    # distinguishes the two so a confirmed B6/B7/B8 pattern isn't shown with
    # the same confidence as an estimate.
    punch: Mapped[Optional[str]] = mapped_column(String(10))          # B1/B6/B7/B8/chain
    boltA_mm: Mapped[Optional[float]] = mapped_column()                # hole-to-hole spacing
    boltB_mm: Mapped[Optional[float]] = mapped_column()                # row offset / edge inset
    boltDia_mm: Mapped[Optional[float]] = mapped_column()
    boltN: Mapped[Optional[int]] = mapped_column()
    punch_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Structural material grades (shaft / pulley / casing / chain) ───────────
# Currently only shafts have a real, multi-grade catalog at all
# (constants.py's SHAFT_MATERIALS, 4 grades) -- pulleys/casing/chains use a
# single hardcoded constant each (e.g. structural.py's `sigma_allow = 60e6
# # Pa, A36`), with no grade selection. One table, not four near-identical
# ones, since the properties needed (Sy/Su/E/density) are the same physics
# regardless of which component uses them -- component_types says which
# parts of the solver a grade is valid for, the same pattern Material
# already uses for app tagging.

class MaterialGrade(Base):
    __tablename__ = "material_grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    grade_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    # e.g. "A36", "4140_QT" -- matches constants.py's SHAFT_MATERIALS keys
    # for the existing shaft grades, so calculations.py's lookups don't need
    # to change to start reading from here.
    name: Mapped[str] = mapped_column(String(80))
    component_types: Mapped[list] = mapped_column(JSON)
    # Which components this grade is valid for: ["shaft"], ["pulley"],
    # ["casing"], ["chain"], or several at once e.g. ["shaft","pulley"].
    Sy_Pa: Mapped[float] = mapped_column()   # yield strength
    Su_Pa: Mapped[Optional[float]] = mapped_column()                   # ultimate strength
    E_Pa: Mapped[Optional[float]] = mapped_column()                   # elastic modulus
    density_kgm3: Mapped[Optional[float]] = mapped_column()
    tau_allow_key_Pa: Mapped[Optional[float]] = mapped_column()    # shaft-specific: keyed allowable shear
    tau_allow_no_key_Pa: Mapped[Optional[float]] = mapped_column()    # shaft-specific: plain allowable shear
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Belts ────────────────────────────────────────────────────────────────────
# NOT seeded -- there is currently no belt PRODUCT catalog anywhere in this
# codebase to seed it from. belt_ply is purely a formula result (4450 N per
# inch-width per ply) with no specific manufacturer products behind it.
# Schema is here and ready; populating it with real EP/ST belt product
# ratings (by ply count, by cord construction) is real catalog data that
# needs an actual source, not something to fabricate plausible-looking
# numbers for.

class Belt(Base):
    __tablename__ = "belts"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    belt_type: Mapped[Optional[str]] = mapped_column(String(5))      # EP / ST
    ply_or_cord: Mapped[Optional[str]] = mapped_column(String(20))      # e.g. "4 ply" or "ST 1000"
    rating_N_per_mm: Mapped[Optional[float]] = mapped_column()           # rated tension per mm width
    cover_grade: Mapped[Optional[str]] = mapped_column(String(5))       # M / N / W (DIN 22102)
    max_temp_c: Mapped[Optional[float]] = mapped_column()
    mass_kg_m2: Mapped[Optional[float]] = mapped_column()
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Screws (screw conveyor) ──────────────────────────────────────────────────
# NOT seeded -- this is the screw-conveyor module's own catalog; this
# backend doesn't have its source data. Schema mirrors the same app-tagging
# convention as Material so SC-origin rows can carry ["sc"] the same way.

class Screw(Base):
    __tablename__ = "screws"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    diameter_mm: Mapped[Optional[float]] = mapped_column()
    pitch_mm: Mapped[Optional[float]] = mapped_column()
    shaft_dia_mm: Mapped[Optional[float]] = mapped_column()
    flight_thickness_mm: Mapped[Optional[float]] = mapped_column()
    material: Mapped[Optional[str]] = mapped_column(String(40))
    max_torque_Nm: Mapped[Optional[float]] = mapped_column()
    note: Mapped[Optional[str]] = mapped_column(Text)
    app: Mapped[Optional[list]] = mapped_column(JSON)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)


# ─── Bolts / fasteners ────────────────────────────────────────────────────────
# NOT seeded -- no existing bolt catalog in this codebase (bolt_fatigue
# checks compute against a generic Goodman-line property set, not specific
# cataloged bolt grades/sizes). Schema ready for real fastener-standard data
# (ISO 898-1 property classes, ASTM grades, etc.) when available.

class Bolt(Base):
    __tablename__ = "bolts"

    id: Mapped[int] = mapped_column(primary_key=True)
    designation: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    # e.g. "M12 Class 8.8", "1/2-13 Grade 5"
    diameter_mm: Mapped[Optional[float]] = mapped_column()
    property_class: Mapped[Optional[str]] = mapped_column(String(10))     # 8.8 / 10.9 / Grade 5 / Grade 8 etc.
    Sy_Pa: Mapped[Optional[float]] = mapped_column()
    Su_Pa: Mapped[Optional[float]] = mapped_column()
    proof_load_N: Mapped[Optional[float]] = mapped_column()
    material: Mapped[Optional[str]] = mapped_column(String(40))     # Steel / Stainless 304 / 316 etc.
    note: Mapped[Optional[str]] = mapped_column(Text)
    custom: Mapped[bool] = mapped_column(Boolean, default=False)