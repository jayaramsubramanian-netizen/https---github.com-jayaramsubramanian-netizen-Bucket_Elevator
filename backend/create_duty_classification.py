"""
backend/create_duty_classification.py -- data-driven duty classification.
═══════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT IN engineering_limits
──────────────────────────────────────
The two answer different questions:

    engineering_limits  ->  "Is this design ACCEPTABLE?"    (pass / warn / fail)
    duty classification ->  "How DEMANDING is this application?"  (a class)

A duty rule decides nothing on its own -- it selects which limit applies. Putting
it in engineering_limits would produce a row with no verdict, which that table's
chk_has_bound constraint correctly rejects. The flow is:

    operating_profile -> duty_class_rules -> duty_class -> engineering_limits
                                                              -> margins

WHY DATA AND NOT PYTHON
───────────────────────
    if annual_hours < 2000: duty = "LIGHT"
is exactly the unsourced-constant pattern this platform exists to eliminate.
Material properties, material limits, engineering limits and bearing
capabilities all carry provenance; duty classification must not suddenly become
an if-statement. Stored as rules, the classifier can also EXPLAIN itself:

    Duty Classification: HEAVY
      + annual operation 7,800 h/year
      + starts/hour 18
      + shock loading moderate
      + availability target 98%

which is far more useful to an engineer than "Duty = Heavy".

PROVENANCE
──────────
There is NO universally accepted definition of "heavy duty = 6,000 h/year".
That is a design PHILOSOPHY, not a published standard -- and this file says so.
Every rule is sourced to "VECTOMEC Engineering Standard 001 -- Duty
Classification Methodology, Rev 1.0", declared as engineering judgement, and
carries a rationale. Owning that openly is more defensible than implying a
standard that does not exist.

Comparison semantics (min | max | range | boolean) are deliberately the SAME
vocabulary as engineering_limits, so one evaluator serves both.
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

STANDARD = "VECTOMEC Engineering Standard 001 -- Duty Classification Methodology"
REVISION = "Rev 1.0"


def ddl() -> str:
    return """
-- ── The classes themselves: the corporate design standard ───────────────────
CREATE TABLE IF NOT EXISTS duty_classes (
    duty_class              TEXT PRIMARY KEY,   -- LIGHT|MEDIUM|HEAVY|SEVERE|CRITICAL
    rank                    INTEGER NOT NULL,   -- 1..5, ascending severity
    description             TEXT NOT NULL,
    target_design_life_h    REAL NOT NULL,      -- required L10 for this class
    typical_application     TEXT,
    source_type             TEXT NOT NULL,
    source_name             TEXT,
    source_revision         TEXT,
    rationale               TEXT NOT NULL,
    is_active               INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT chk_dc_class CHECK (duty_class IN
        ('LIGHT','MEDIUM','HEAVY','SEVERE','CRITICAL')),
    CONSTRAINT chk_dc_rank  CHECK (rank BETWEEN 1 AND 5),
    CONSTRAINT chk_dc_life  CHECK (target_design_life_h > 0),
    CONSTRAINT chk_dc_rat   CHECK (rationale != ''),
    CONSTRAINT chk_dc_act   CHECK (is_active IN (0,1))
) STRICT;

-- ── The classification logic, with provenance ───────────────────────────────
-- Multiple rules per class: the classifier is a WEIGHTED decision, not a single
-- threshold. `weighting` says how much a rule contributes when rules disagree.
CREATE TABLE IF NOT EXISTS duty_class_rules (
    rule_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    duty_class      TEXT NOT NULL,
    parameter       TEXT NOT NULL,      -- field on the operating profile
    comparison      TEXT NOT NULL,      -- min | max | range | boolean
    value_min       REAL,
    value_max       REAL,
    value_text      TEXT,               -- for categorical params (shock_loading)
    weighting       REAL NOT NULL DEFAULT 1.0,
    rationale       TEXT NOT NULL,
    source_type     TEXT NOT NULL,      -- judgement | industry_standard | client_spec | oem_practice
    source_name     TEXT,
    source_revision TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (duty_class) REFERENCES duty_classes(duty_class) ON DELETE CASCADE,
    CONSTRAINT chk_dr_cmp  CHECK (comparison IN ('min','max','range','boolean')),
    CONSTRAINT chk_dr_src  CHECK (source_type IN
        ('judgement','industry_standard','client_spec','oem_practice')),
    CONSTRAINT chk_dr_rat  CHECK (rationale != ''),
    CONSTRAINT chk_dr_wt   CHECK (weighting > 0),
    CONSTRAINT chk_dr_act  CHECK (is_active IN (0,1)),
    -- a rule must actually constrain something
    CONSTRAINT chk_dr_val  CHECK (
        comparison = 'boolean' OR value_min IS NOT NULL OR value_max IS NOT NULL
        OR value_text IS NOT NULL),
    CONSTRAINT chk_dr_order CHECK (
        value_min IS NULL OR value_max IS NULL OR value_min <= value_max)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_dr_class ON duty_class_rules(duty_class);
CREATE INDEX IF NOT EXISTS idx_dr_param ON duty_class_rules(parameter);
"""

# ── Classes: the design philosophy ───────────────────────────────────────────
CLASSES = [
    ("LIGHT",    1, "Intermittent service",  20000.0,
     "Seasonal / batch: grain intake, small feed mills",
     "Occasional operation with long idle periods. Bearing life is rarely the "
     "governing criterion; first cost usually dominates."),
    ("MEDIUM",   2, "Regular industrial",    40000.0,
     "Single-shift plants, general material handling",
     "The default industrial assumption, and the historical 40,000 h target "
     "used throughout VECTOMEC before duty classes existed."),
    ("HEAVY",    3, "Continuous production", 60000.0,
     "Two/three-shift production, aggregate, grain terminals",
     "Near-continuous operation where unplanned downtime has real production "
     "cost. Justifies larger bearings and better sealing."),
    ("SEVERE",   4, "Harsh continuous",      80000.0,
     "Cement, mining, clinker, abrasive/high-dust duty",
     "Continuous operation in abrasive, high-dust or high-temperature "
     "conditions where contamination shortens life independently of load."),
    ("CRITICAL", 5, "Mission critical",     100000.0,
     "Single-line plants, no installed spare, remote sites",
     "Failure stops the plant and no redundancy exists. Design life is set by "
     "consequence of failure, not by operating hours alone."),
]

# ── Rules: parameter -> class, each weighted and sourced ─────────────────────
# (duty_class, parameter, comparison, vmin, vmax, vtext, weight, rationale)
RULES = [
    # Annual operating hours -- the primary discriminator (high weight)
    ("LIGHT",    "annual_hours", "max",   None, 2000.0, None, 3.0,
     "Under ~2,000 h/year is seasonal or intermittent operation."),
    ("MEDIUM",   "annual_hours", "range", 2000.0, 5000.0, None, 3.0,
     "2,000-5,000 h/year is single-shift or extended single-shift operation."),
    ("HEAVY",    "annual_hours", "range", 5000.0, 7000.0, None, 3.0,
     "5,000-7,000 h/year implies multi-shift production."),
    ("SEVERE",   "annual_hours", "range", 7000.0, 8500.0, None, 3.0,
     "7,000-8,500 h/year is effectively continuous operation."),
    ("CRITICAL", "annual_hours", "min",   8500.0, None, None, 3.0,
     "Above 8,500 h/year leaves under ~260 h/year for all maintenance."),

    # Starting frequency -- fatigue and thermal cycling, independent of hours
    ("HEAVY",    "starts_per_hour", "min", 10.0, None, None, 2.0,
     "Above ~10 starts/hour, torque transients and thermal cycling drive "
     "component life more than steady running does."),
    ("SEVERE",   "starts_per_hour", "min", 20.0, None, None, 2.0,
     "Above ~20 starts/hour the drive train sees near-constant transient load."),

    # Shock loading -- categorical
    ("HEAVY",    "shock_loading", "boolean", None, None, "moderate", 2.0,
     "Moderate shock (lumpy or intermittent feed) raises equivalent load "
     "beyond the steady-state calculation."),
    ("SEVERE",   "shock_loading", "boolean", None, None, "high", 2.5,
     "High shock (large lumps, choke feeding, frequent jams) is a severe-duty "
     "indicator regardless of operating hours."),

    # Availability -- consequence of failure
    ("SEVERE",   "availability_target", "min", 97.0, None, None, 2.0,
     "A 97%+ availability target allows under ~260 h/year of total downtime."),
    ("CRITICAL", "availability_target", "min", 99.0, None, None, 3.0,
     "A 99%+ target means under ~88 h/year downtime -- effectively no window "
     "for unplanned bearing replacement."),

    # Reversing / VFD duty
    ("HEAVY",    "reversing", "boolean", None, None, "true", 1.5,
     "Reversing duty imposes load reversals the steady-state model does not "
     "capture."),

    # Ambient temperature -- lubrication life
    ("SEVERE",   "ambient_temperature_c", "min", 50.0, None, None, 1.5,
     "Above ~50 degC ambient, grease life falls sharply and relubrication "
     "intervals shorten independently of load."),
]


def seed(con):
    n_c = n_r = 0
    for dc, rank, desc, life, appl, why in CLASSES:
        if con.execute("SELECT 1 FROM duty_classes WHERE duty_class=?", (dc,)).fetchone():
            continue
        con.execute(
            "INSERT INTO duty_classes (duty_class,rank,description,target_design_life_h,"
            "typical_application,source_type,source_name,source_revision,rationale) "
            "VALUES (?,?,?,?,?,'judgement',?,?,?)",
            (dc, rank, desc, life, appl, STANDARD, REVISION, why))
        n_c += 1
    for dc, param, cmp_, vmin, vmax, vtext, wt, why in RULES:
        if con.execute("SELECT 1 FROM duty_class_rules WHERE duty_class=? AND parameter=? "
                       "AND COALESCE(value_text,'')=COALESCE(?,'')",
                       (dc, param, vtext)).fetchone():
            continue
        con.execute(
            "INSERT INTO duty_class_rules (duty_class,parameter,comparison,value_min,"
            "value_max,value_text,weighting,rationale,source_type,source_name,"
            "source_revision) VALUES (?,?,?,?,?,?,?,?,'judgement',?,?)",
            (dc, param, cmp_, vmin, vmax, vtext, wt, why, STANDARD, REVISION))
        n_r += 1
    con.commit()
    return n_c, n_r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--no-seed", action="store_true")
    args = ap.parse_args()

    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 37, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} too old for STRICT.")

    con = sqlite3.connect(args.db)
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript(ddl())
        if not args.no_seed:
            n_c, n_r = seed(con)
            print(f"seeded {n_c} duty classes, {n_r} classification rules")
        for t in ("duty_classes", "duty_class_rules"):
            strict = con.execute("SELECT strict FROM pragma_table_list WHERE name=?", (t,)).fetchone()
            cols = len(con.execute(f"PRAGMA table_info({t})").fetchall())
            rows = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:20s} {cols:2d} cols  {rows:3d} rows  "
                  f"STRICT={'yes' if strict and strict[0] else 'NO'}")
        print("\nduty classes and required design life:")
        for dc, rank, life, desc in con.execute(
                "SELECT duty_class, rank, target_design_life_h, description "
                "FROM duty_classes ORDER BY rank"):
            n = con.execute("SELECT COUNT(*) FROM duty_class_rules WHERE duty_class=?",
                            (dc,)).fetchone()[0]
            print(f"  {rank}. {dc:9s} {life:>8,.0f} h  {desc:22s} ({n} rules)")
        print(f"\nEVERY rule is engineering judgement, sourced to:")
        print(f"  {STANDARD}, {REVISION}")
        print("There is no published standard defining 'heavy duty = 6,000 h/year'.")
        print("This is VECTOMEC design philosophy, declared as such.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())