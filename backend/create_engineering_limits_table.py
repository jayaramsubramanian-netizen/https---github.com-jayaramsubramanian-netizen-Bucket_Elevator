"""
backend/create_engineering_limits_table.py -- engineering acceptance criteria
with PROVENANCE.
═══════════════════════════════════════════════════════════════════════════
Every warning and failure the software reports is a judgement against a LIMIT.
This table is where those limits live, and -- critically -- where they carry
their source. It applies to equipment limits exactly the philosophy
material_sources applies to material properties: a number without provenance is
an assertion, not engineering.

THE RULE
────────
Nothing should exist like  MAX_BUCKET_FILL = 0.85  in code. If a limit governs a
verdict shown to an engineer, it lives here with source, edition, and page, so
the UI can render "Source: CEMA 375 Sec 4" or, just as importantly,
"Source: VECTOMEC Design Standard -- engineering judgement".

Being explicit that a limit is judgement is NOT a weakness. It is the difference
between an engineer trusting the number and an engineer discovering later that a
"standard" was invented.

FOUR-ZONE MODEL
───────────────
Each limit defines up to four bounds, which produce the target / acceptable /
warning / fail zones:

    fail_min      warning_min      warning_max      fail_max
       |---- fail ----|--- warn ---|---- ok ----|--- warn ---|---- fail ----|

All four are nullable: a one-sided limit (bearing life >= 40,000 h) sets only
warning_min / fail_min. `direction` records which side is bad so the UI does not
have to infer it.

RELATIONSHIP TO THE SOLVER
──────────────────────────
calculations.py currently hardcodes the nine limits that were moved out of the
frontend earlier (headshaft_load_warn_N, l10_min_h, cr_opt_min/max,
motor_margin_ok_pct, startup_margin_ok, chain_SF_ok_min, chute_loading_ok_pct,
mtbf_min_h). Moving them into the backend was the right first step -- ONE copy
instead of ten. This table is the second step: give that one copy a source.
The cutover (solver reads limits from here) is deliberate and separate; the
table is built and seeded first so the values can be reviewed against their
sources BEFORE anything depends on them.

STRICT + CHECK, same discipline as the material tables.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

DECISION_TYPE = ["published", "derived", "measured", "estimated", "judgement",
                 "validated_by_testing"]
# COMPARISON SEMANTICS -- stored so ONE generic evaluator can handle every
# limit, instead of the UI carrying a special case per parameter.
#   min      lower bound is binding   (Bearing L10 >= 40,000 h)
#   max      upper bound is binding   (Motor load <= 90%)
#   range    two-sided band           (CR 1.0 - 1.8)
#   boolean  a condition must be False (backlegging present = fail)
#   target   an IDEAL value, not a limit -- deviation is reported, not failure
#            (motor efficiency target 96%: 95.8% and 96.3% are both fine)
#
# `target` is deliberately distinct from `range`. A range says where a value is
# ALLOWED; a target says where it is BEST. Conflating them turns "3% from ideal"
# into a spurious warning. A parameter may legitimately have both: bucket fill
# target 80%, acceptable range 70-90%.
DIRECTION = ["min", "max", "range", "boolean", "target"]
SOURCE_TYPE = ["CEMA", "ISO", "NEMA", "AGMA", "ASME", "DIN", "OEM",
               "VECTOMEC", "User", "Other"]


def ddl() -> str:
    return f"""
CREATE TABLE IF NOT EXISTS engineering_limits (
    limit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    limit_key       TEXT    NOT NULL UNIQUE,   -- stable code the solver looks up
    equipment       TEXT    NOT NULL,          -- bucket_elevator / screw / belt / any
    subsystem       TEXT,                       -- matches the checks[] subsystem tags
    parameter       TEXT    NOT NULL,          -- human name, e.g. "Head shaft radial load"
    units           TEXT,

    -- Four-zone bounds. All nullable: one-sided limits use only one side.
    fail_min        REAL,
    warning_min     REAL,
    warning_max     REAL,
    fail_max        REAL,
    target_min      REAL,                       -- optional "ideal" band inside ok
    target_max      REAL,
    direction       TEXT    NOT NULL,   -- min|max|range|boolean|target
    limit_class     TEXT    NOT NULL DEFAULT 'static',

    -- Provenance -- the entire point of this table
    decision_type   TEXT    NOT NULL,
    source_type     TEXT,
    source_name     TEXT,                       -- "CEMA Standard 375"
    source_edition  TEXT,                       -- "2017"
    source_section  TEXT,                       -- section / table / page
    rationale       TEXT,                       -- WHY, especially for judgement
    derived_from    TEXT,                       -- for limit_class='derived': what computes it
    confidence      TEXT,                       -- high | medium | low
    boolean_expect  INTEGER,                    -- for direction='boolean': the PASSING value (0/1)
    author          TEXT,                       -- who set a judgement limit
    revision        TEXT,                       -- revision/year of that judgement
    notes           TEXT,

    is_active       INTEGER NOT NULL DEFAULT 1,
    entered_by      TEXT,
    entered_date    TEXT,
    review_due      TEXT,

    CONSTRAINT chk_decision  CHECK (decision_type IN
        ({", ".join("'"+d+"'" for d in DECISION_TYPE)})),
    CONSTRAINT chk_class     CHECK (limit_class IN ('static','derived','provisional')),
    -- a DERIVED limit must say what computes it; a static number standing in for
    -- a derived one is the failure mode this column exists to prevent
    CONSTRAINT chk_derived   CHECK (
        limit_class != 'derived' OR (derived_from IS NOT NULL AND derived_from != '')),
    CONSTRAINT chk_direction CHECK (direction IN
        ({", ".join("'"+d+"'" for d in DIRECTION)})),
    CONSTRAINT chk_srctype   CHECK (source_type IS NULL OR source_type IN
        ({", ".join("'"+s+"'" for s in SOURCE_TYPE)})),
    CONSTRAINT chk_active    CHECK (is_active IN (0,1)),
    CONSTRAINT chk_confidence CHECK (confidence IS NULL OR confidence IN
        ('high','medium','low')),
    -- a judgement limit MUST explain itself; a published one must name a source
    CONSTRAINT chk_rationale CHECK (
        decision_type != 'judgement' OR (rationale IS NOT NULL AND rationale != '')),
    CONSTRAINT chk_published CHECK (
        decision_type != 'published' OR (source_name IS NOT NULL AND source_name != '')),
    -- bounds must be ordered where both are present
    CONSTRAINT chk_order_min CHECK (
        fail_min IS NULL OR warning_min IS NULL OR fail_min <= warning_min),
    CONSTRAINT chk_order_max CHECK (
        fail_max IS NULL OR warning_max IS NULL OR warning_max <= fail_max),
    -- a boolean limit is a condition, not a magnitude: no numeric bounds
    -- A boolean limit must state WHICH value passes. "hub fits = True" and
    -- "backlegging present = True" are opposite polarities; assuming one
    -- silently inverts the other's verdict.
    CONSTRAINT chk_boolean CHECK (
        direction != 'boolean' OR (fail_min IS NULL AND warning_min IS NULL
                                   AND warning_max IS NULL AND fail_max IS NULL
                                   AND boolean_expect IS NOT NULL)),
    CONSTRAINT chk_bool_val CHECK (boolean_expect IS NULL OR boolean_expect IN (0,1)),
    -- every non-boolean limit must define at least ONE bound, or it decides nothing
    -- Every limit must be able to DECIDE something. Exceptions:
    --   boolean/target  -- carry no numeric bounds by definition
    --   derived         -- bounds are supplied at solve time from the selected
    --                      component, so NULL here is correct, not incomplete
    --                      (chk_derived already forces derived_from to explain it)
    CONSTRAINT chk_has_bound CHECK (
        direction IN ('boolean','target') OR limit_class = 'derived'
        OR fail_min IS NOT NULL OR warning_min IS NOT NULL
        OR warning_max IS NOT NULL OR fail_max IS NOT NULL),
    -- a target limit must actually state its target
    CONSTRAINT chk_target CHECK (
        direction != 'target' OR target_min IS NOT NULL)
) STRICT;
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_limit_key       ON engineering_limits(limit_key);",
    "CREATE INDEX IF NOT EXISTS idx_limit_equipment ON engineering_limits(equipment);",
    "CREATE INDEX IF NOT EXISTS idx_limit_subsystem ON engineering_limits(subsystem);",
]

# ── Seed: ONLY the limits already live in calculations.py ────────────────────
# Each row records what the source ACTUALLY is. Where no source could be
# established, decision_type='judgement' and the rationale says so plainly
# rather than implying a standard. That honesty is the deliverable.
#
# cols: limit_key, equipment, subsystem, parameter, units, fail_min, warning_min,
#       warning_max, fail_max, target_min, target_max, direction, decision_type,
#       source_type, source_name, source_edition, source_section, rationale
SEED = [
    # ── STATIC limits: genuinely universal, not a function of what was selected
    dict(limit_key="centrifugal_ratio", equipment="bucket_elevator", subsystem="process",
         parameter="Centrifugal ratio (CR)", units="-", direction="range",
         limit_class="static", warning_min=1.0, warning_max=1.8,
         target_min=1.2, target_max=1.8,
         decision_type="published", source_type="CEMA", source_name="CEMA Standard 375",
         source_edition="2017", source_section="Sec 3 -- discharge", confidence="high",
         rationale="CR band for centrifugal discharge."),

    dict(limit_key="chain_safety_factor", equipment="bucket_elevator", subsystem="belt",
         parameter="Chain working-load safety factor", units="-", direction="min",
         limit_class="static", warning_min=5.0, target_min=6.0,
         decision_type="published", source_type="CEMA", source_name="CEMA Standard 375",
         source_edition="2017", source_section="Sec 4 -- method", confidence="high",
         rationale="SF CRITERION is CEMA. NOTE: the chain WORKING LOADS it is applied "
                   "to are NOT -- catalogue chain data is unverified placeholder data "
                   "and is flagged as such by the solver."),

    dict(limit_key="motor_power_margin", equipment="bucket_elevator", subsystem="drive",
         parameter="Motor power margin over calculated demand", units="%", direction="min",
         limit_class="static", warning_min=0.0, target_min=10.0,
         decision_type="judgement", source_type="VECTOMEC",
         source_name="VECTOMEC Design Standard", author="VECTOMEC", revision="2026",
         confidence="medium",
         rationale="10% margin target / 0% failure floor. NO published source "
                   "established. NEMA service factor is a related but DIFFERENT "
                   "concept (continuous overload capability, not selection margin) "
                   "and must not be cited here."),

    dict(limit_key="startup_torque_margin", equipment="bucket_elevator", subsystem="drive",
         parameter="Starting torque margin (available / required)", units="ratio",
         direction="min", limit_class="static", warning_min=1.0, target_min=1.1,
         decision_type="judgement", source_type="VECTOMEC",
         source_name="VECTOMEC Design Standard", author="VECTOMEC", revision="2026",
         confidence="medium",
         rationale="1.1 target / 1.0 floor. NO published source established. Was "
                   "previously duplicated in two UI files before consolidation."),

    dict(limit_key="chute_loading", equipment="bucket_elevator", subsystem="discharge",
         parameter="Discharge chute cross-section loading", units="%", direction="max",
         limit_class="static", warning_max=40.0, fail_max=60.0,
         decision_type="judgement", source_type="VECTOMEC",
         source_name="VECTOMEC Design Standard", author="VECTOMEC", revision="2026",
         confidence="low",
         rationale="40% warning / 60% failure of chute cross-section. NO published "
                   "source established. Chute sizing practice varies widely by "
                   "material; needs an OEM or CEMA 550 flow reference."),

    dict(limit_key="mtbf_minimum", equipment="bucket_elevator", subsystem="maintenance",
         parameter="Mean time between failures", units="h", direction="min",
         limit_class="static", warning_min=8000.0,
         decision_type="judgement", source_type="VECTOMEC",
         source_name="VECTOMEC Design Standard", author="VECTOMEC", revision="2026",
         confidence="low",
         rationale="8,000 h ~ one year of continuous operation. NO published source; "
                   "a round-year proxy, not a reliability standard."),

    # ── DERIVED limits: the bound comes from the COMPONENT the solver selected ──
    # These must not be fixed numbers. The allowable load on a head shaft is not a
    # universal constant -- it follows from the bearing, pedestal, shaft diameter,
    # material, keyway, bearing spacing and overhung load, all of which the solver
    # already knows. A static 50/80 kN here would silently override a correctly
    # computed component rating.
    dict(limit_key="bearing_l10_life", equipment="bucket_elevator", subsystem="bearing",
         parameter="Bearing L10 life", units="h", direction="min",
         limit_class="static", warning_min=40000.0, fail_min=20000.0,
         decision_type="published", source_type="ISO", source_name="ISO 281",
         source_edition="2007", source_section="Rating life", confidence="high",
         rationale="The REQUIRED life is a duty decision (40,000 h continuous "
                   "target; 20,000 h optimiser floor). The ACHIEVED life is derived "
                   "from the selected bearing -- that is the solver's L10 output, "
                   "not a limit."),

    dict(limit_key="headshaft_radial_load", equipment="bucket_elevator", subsystem="shaft",
         parameter="Head shaft radial load vs selected bearing rating", units="N",
         direction="max", limit_class="derived",
         derived_from="Dynamic/static rating of the SELECTED head bearing and "
                      "pedestal, at the solved shaft diameter and bearing spacing. "
                      "Populate warning_max/fail_max at solve time from the bearing "
                      "catalogue; do NOT store a fixed value here.",
         decision_type="derived", source_type="OEM", confidence="high",
         rationale="PREVIOUSLY a static 50 kN / 80 kN judgement limit. Reclassified: "
                   "allowable shaft load is not universal -- it depends on bearing, "
                   "pedestal, shaft diameter and material, keyway, bearing spacing "
                   "and overhung load. The solver knows all of these. Bounds are "
                   "intentionally NULL so a stale constant cannot mask the real "
                   "component rating; the margin renders NEUTRAL until wired."),

    # ── DERIVED stress limits: actual vs allowable already computed by the
    # solver. The ALLOWABLE is the limit and belongs here with provenance; the
    # ACTUAL is a solver output. These three allowables are currently hardcoded
    # as FUNCTION DEFAULTS in structural.py with no citation:
    #     key_stress_check(tau_allow_pa=100e6, sigma_allow_pa=215e6)
    #     weld_throat_sizing(weld_allow_pa=96e6)
    # They are recorded honestly as unsourced pending review, NOT dressed up as
    # ASME/AWS values -- the calculation METHOD is ASME B17.1 / AWS, but the
    # allowable STRESS depends on material grade and joint class, which the
    # solver does not yet ask for.
    dict(limit_key="key_shear_stress", equipment="bucket_elevator", subsystem="shaft",
         parameter="Key shear stress vs allowable", units="MPa", direction="max",
         limit_class="derived",
         derived_from="structural.key_stress_check -> tau_actual_MPa vs "
                      "tau_allow_MPa. Allowable depends on key material grade; "
                      "currently the 100 MPa function default.",
         decision_type="estimated", source_type="Other", confidence="low",
         rationale="Method is ASME B17.1. The 100 MPa allowable is an unsourced "
                   "default in structural.py:512 -- needs a key material grade "
                   "input and a cited allowable before release."),

    dict(limit_key="key_bearing_stress", equipment="bucket_elevator", subsystem="shaft",
         parameter="Key bearing stress vs allowable", units="MPa", direction="max",
         limit_class="derived",
         derived_from="structural.key_stress_check -> sigma_actual_MPa vs "
                      "sigma_allow_MPa. Currently the 215 MPa function default.",
         decision_type="estimated", source_type="Other", confidence="low",
         rationale="Method is ASME B17.1. The 215 MPa allowable is an unsourced "
                   "default in structural.py:513."),

    dict(limit_key="weld_stress", equipment="bucket_elevator", subsystem="shaft",
         parameter="Hub weld stress vs allowable", units="MPa", direction="max",
         limit_class="derived",
         derived_from="structural.weld_throat_sizing -> tau_torsion_MPa vs "
                      "weld_allow_MPa. Currently the 96 MPa function default.",
         decision_type="estimated", source_type="Other", confidence="low",
         rationale="The 96 MPa allowable is an unsourced default in "
                   "structural.py:591. Weld allowable depends on electrode "
                   "classification and joint type, neither of which is an input."),

    dict(limit_key="shell_buckling_sf", equipment="bucket_elevator", subsystem="pulley",
         parameter="Pulley shell buckling safety factor", units="-", direction="min",
         limit_class="derived",
         derived_from="structural shell buckling -> SF_buckling, computed from the "
                      "solved shell thickness, diameter and face width.",
         decision_type="derived", source_type="Other", confidence="medium",
         rationale="SF is computed from the selected shell geometry. The REQUIRED "
                   "minimum SF is a duty decision still to be set."),

    dict(limit_key="pulley_hub_fits_shell", equipment="bucket_elevator", subsystem="pulley",
         parameter="Hub fits within pulley shell", units=None, direction="boolean",
         limit_class="derived", boolean_expect=1,   # TRUE = fits = PASS
         derived_from="structural.pulley_end_disc -> hub_fits_in_shell. False means "
                      "the required hub is larger than the pulley -- geometrically "
                      "impossible, already raised as a FAIL check by the solver.",
         decision_type="derived", source_type="Other", confidence="high",
         rationale="Pure geometry: no threshold to source."),
]

# Limits that are DERIVED but not yet wired to their component rating. Listed so
# the gap is visible rather than silently absent from the dashboard.
DERIVED_PENDING = [
    "headshaft_radial_load",
]


def seed(con):
    n_new = 0
    for row in SEED:
        if con.execute("SELECT 1 FROM engineering_limits WHERE limit_key=?",
                       (row["limit_key"],)).fetchone():
            continue
        cols = ", ".join(row)
        con.execute(f"INSERT INTO engineering_limits ({cols}) "
                    f"VALUES ({', '.join(':' + k for k in row)})", row)
        n_new += 1
    con.commit()
    return n_new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="list limits grouped by provenance quality")
    args = ap.parse_args()

    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 37, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} too old for STRICT (need >=3.37).")

    con = sqlite3.connect(args.db)
    try:
        con.executescript(ddl())
        for ix in INDEXES:
            con.execute(ix)
        con.commit()
        if not args.no_seed:
            print(f"seeded {seed(con)} new limits")

        strict = con.execute(
            "SELECT strict FROM pragma_table_list WHERE name='engineering_limits'"
        ).fetchone()
        cols = [r[1] for r in con.execute("PRAGMA table_info(engineering_limits)")]
        print(f"engineering_limits: {len(cols)} columns, "
              f"STRICT={'yes' if strict and strict[0] else 'NO'}")

        print("\nlimit class:")
        for lc, n in con.execute(
                "SELECT limit_class, COUNT(*) FROM engineering_limits "
                "GROUP BY limit_class ORDER BY COUNT(*) DESC"):
            print(f"  {lc:12s} {n}")
        n_pending = con.execute(
            "SELECT COUNT(*) FROM engineering_limits WHERE limit_class='derived' "
            "AND warning_max IS NULL AND warning_min IS NULL").fetchone()[0]
        if n_pending:
            print(f"  -> {n_pending} DERIVED limit(s) have no bounds yet: they must be "
                  f"populated\n     at solve time from the selected component, and "
                  f"render NEUTRAL until then.")

        print("\nprovenance summary:")
        for dt, n in con.execute(
                "SELECT decision_type, COUNT(*) FROM engineering_limits "
                "GROUP BY decision_type ORDER BY COUNT(*) DESC"):
            print(f"  {dt:12s} {n}")
        n_judge = con.execute(
            "SELECT COUNT(*) FROM engineering_limits WHERE decision_type='judgement'"
        ).fetchone()[0]
        if n_judge:
            print(f"\n{n_judge} limits are ENGINEERING JUDGEMENT with no published "
                  f"source.\nThese are honestly labelled, not disguised as standards. "
                  f"Review before release:")
            for k, p in con.execute(
                    "SELECT limit_key, parameter FROM engineering_limits "
                    "WHERE decision_type='judgement' ORDER BY limit_key"):
                print(f"    - {k:24s} {p}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())