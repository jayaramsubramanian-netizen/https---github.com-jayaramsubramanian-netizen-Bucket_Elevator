"""
backend/create_component_catalogs.py -- normalized shaft-support component
catalogs + deterministic assembly rules.
═══════════════════════════════════════════════════════════════════════════
WHY NORMALIZED CATALOGS, NOT CURATED ASSEMBLIES
────────────────────────────────────────────────
A support assembly (bearing + housing + adapter + seal + locking) is NOT primary
data to be transcribed 60-100 times. For standard SKF plummer-block assemblies
the relationships are DETERMINISTIC from the bearing series:

    22220  ->  bore 100mm  ->  SNL 520 housing  ->  H320 adapter  ->  TSN 520 seal

Verified against the live catalogue: 222xx -> SNL 5xx / H3xx / TSN 5xx holds for
every SRB row. So the assembly is a DERIVED result, and only the reusable
catalogs + the rules need storing. Adding FAG/NTN/Timken later means another
catalog + its rule, not thousands of new assembly rows.

WHAT IS STORED
──────────────
  bearing_family_capability  family-level attributes (one row per family, not
                             repeated across 168 bearings) -- misalignment,
                             shock, contamination, temperature, with provenance
  housing_catalog            plummer/flange housings; OWN the sealing + dust
                             protection (contamination belongs to housing+seal,
                             not the bearing)
  seal_catalog               seal kits by housing series
  adapter_catalog            adapter sleeves by bore
  environment_profile        application environment -> capability REQUIREMENTS
                             (washdown/food/dust/corrosion/atex), data-driven
  application_preference     CURATED engineering judgement catalogs cannot infer
                             (industry -> preferred family, environment ->
                             preferred seal). Explicitly provenance-tagged.

WHAT IS NOT STORED
──────────────────
  support_assembly           DERIVED at selection time by the assembly rule from
                             the chosen bearing. No table.

The existing `bearings` table is NOT modified destructively -- a `bearing_family`
column is added so each row joins to its capability row, and the old compound
`type` values (PBU-SN, Y-PBU) are decomposed: PBU-SN and Y-PBU are NOT bearing
families -- SN is a plummer-block housing, Y-PBU is a Y-insert in a pressed
housing. Family and housing are separated.

STRICT + CHECK + provenance, same discipline as the material and limits tables.
Populates capability rows and preference rows (they ARE engineering knowledge),
but writes NO per-bearing catalogue values as verified -- those stay for the
manufacturer-data pass.
"""
from __future__ import annotations
import argparse, os, re, sqlite3, sys

_DB = os.environ.get("VECTRIX_DB", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vectrix.db"))

FAMILIES = ["SRB", "SAB", "Y-insert", "DGBB", "TRB"]
DUTY_CLASSES = ["light", "medium", "heavy", "severe", "critical"]


def ddl() -> str:
    return """
-- ── Family capability: ONE row per family, not repeated per bearing ──────────
CREATE TABLE IF NOT EXISTS bearing_family_capability (
    family              TEXT PRIMARY KEY,
    tier                INTEGER,                 -- 1=primary industrial .. 5=special
    -- static vs running misalignment ARE different; running is the smaller,
    -- continuous-duty limit that governs a shaft deflecting under load
    misalign_static_deg     REAL,
    misalign_running_deg    REAL,
    shock_rating        TEXT,                    -- light | moderate | heavy
    -- duty capability, evaluated against the derived duty class
    duty_light          INTEGER, duty_medium INTEGER, duty_heavy INTEGER,
    duty_severe         INTEGER, duty_critical INTEGER,
    continuous_duty     INTEGER,
    notes               TEXT,
    source_type         TEXT,                    -- manufacturer | judgement
    source_reference    TEXT,
    verified            INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_fam   CHECK (family IN ('SRB','SAB','Y-insert','DGBB','TRB')),
    CONSTRAINT chk_shock CHECK (shock_rating IS NULL OR shock_rating IN
        ('light','moderate','heavy')),
    CONSTRAINT chk_dl CHECK (duty_light   IS NULL OR duty_light   IN (0,1)),
    CONSTRAINT chk_dm CHECK (duty_medium  IS NULL OR duty_medium  IN (0,1)),
    CONSTRAINT chk_dh CHECK (duty_heavy   IS NULL OR duty_heavy   IN (0,1)),
    CONSTRAINT chk_ds CHECK (duty_severe  IS NULL OR duty_severe  IN (0,1)),
    CONSTRAINT chk_dc CHECK (duty_critical IS NULL OR duty_critical IN (0,1)),
    CONSTRAINT chk_ver CHECK (verified IN (0,1))
) STRICT;

-- ── Housing catalog: OWNS sealing and dust/contamination protection ─────────
CREATE TABLE IF NOT EXISTS housing_catalog (
    housing_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    series              TEXT NOT NULL,           -- SNL | SD | SAF | SE | pressed | flange
    frame_size          TEXT,                    -- e.g. '520'
    bearing_series      TEXT,                    -- SRB series it accepts, e.g. '222'
    bore_min_mm         REAL,
    bore_max_mm         REAL,
    material            TEXT,                    -- cast_iron | steel | stainless
    split               INTEGER,                 -- 0/1 split housing
    seal_options        TEXT,                    -- comma list of seal series
    washdown            INTEGER,
    dust_rating         TEXT,                    -- standard | high | taconite
    source_type         TEXT,
    source_reference    TEXT,
    verified            INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_hver CHECK (verified IN (0,1)),
    CONSTRAINT chk_hwash CHECK (washdown IS NULL OR washdown IN (0,1))
) STRICT;

-- ── Seal catalog: contamination protection lives with the seal + housing ────
CREATE TABLE IF NOT EXISTS seal_catalog (
    seal_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    series              TEXT NOT NULL,           -- TSN | labyrinth | taconite | triple_lip | v_ring
    housing_series      TEXT,                    -- housing it fits
    frame_size          TEXT,
    seal_family         TEXT,                    -- labyrinth | contact | taconite | triple_lip
    temp_min_c          REAL, temp_max_c REAL,
    dust_rating         TEXT,
    food_grade          INTEGER,
    source_type         TEXT,
    source_reference    TEXT,
    verified            INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_sver CHECK (verified IN (0,1)),
    CONSTRAINT chk_sfood CHECK (food_grade IS NULL OR food_grade IN (0,1))
) STRICT;

-- ── Adapter sleeve catalog ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS adapter_catalog (
    adapter_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    designation         TEXT NOT NULL,           -- e.g. 'H320'
    shaft_diameter_mm   REAL,
    bearing_bore_mm     REAL,
    bearing_series      TEXT,
    source_type         TEXT,
    verified            INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_aver CHECK (verified IN (0,1))
) STRICT;

-- ── Environment profile: application -> capability REQUIREMENTS (data-driven) ─
CREATE TABLE IF NOT EXISTS environment_profile (
    environment         TEXT PRIMARY KEY,        -- grain | cement | food | fertilizer | marine | mining
    req_stainless       INTEGER,
    req_food_grade      INTEGER,
    req_washdown        INTEGER,
    dust_level          TEXT,                    -- low | medium | high | very_high
    corrosion_level     TEXT,                    -- low | medium | high | very_high
    atex                TEXT,                    -- none | dust | gas
    typical_hours_year  REAL,                    -- e.g. cement 8200, grain 1200
    notes               TEXT,
    source_type         TEXT,
    verified            INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_ever CHECK (verified IN (0,1))
) STRICT;

-- ── Application preference: CURATED engineering judgement ────────────────────
-- The knowledge catalogs cannot infer: which family/seal an industry prefers.
-- Explicitly judgement, explicitly sourced -- not dressed as a catalogue fact.
CREATE TABLE IF NOT EXISTS application_preference (
    pref_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    environment         TEXT NOT NULL,
    preferred_family    TEXT,                    -- preferred bearing family
    preferred_seal      TEXT,                    -- preferred seal family
    rationale           TEXT NOT NULL,           -- WHY -- judgement must explain itself
    source_type         TEXT NOT NULL DEFAULT 'judgement',
    author              TEXT,
    verified            INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT chk_pver CHECK (verified IN (0,1)),
    CONSTRAINT chk_prat CHECK (rationale != '')
) STRICT;
"""


def add_family_column(con):
    have = {r[1] for r in con.execute("PRAGMA table_info(bearings)")}
    if "bearing_family" not in have:
        con.execute("ALTER TABLE bearings ADD COLUMN bearing_family TEXT")
    if "housing_from_type" not in have:
        con.execute("ALTER TABLE bearings ADD COLUMN housing_from_type TEXT")
    con.commit()


# type -> (bearing_family, housing) -- decompose the compound values
TYPE_SPLIT = {
    "SRB":    ("SRB", None), "SAB": ("SAB", None),
    "DGBB":   ("DGBB", None), "TRB": ("TRB", None),
    "PBU-SN": ("SRB", "SNL"),        # SN plummer block housing an SRB
    "Y-PBU":  ("Y-insert", "pressed"),
    # THRUST bearings: carry AXIAL load, not the radial load a head shaft sees.
    # Correctly NOT head-shaft candidates -- but tagged explicitly so they read
    # as "excluded, thrust type" rather than silently NULL (which looks like a
    # classification gap). TBB = thrust ball (511xx), SRTB = spherical roller
    # thrust. A head-shaft selector must skip family='thrust'.
    "TBB":    ("thrust", None),
    "SRTB":   ("thrust", None),
}

# family capability PROPOSALS (Jay's capability matrix). verified=0.
#   family: tier, static, running, shock, (light,med,heavy,severe,critical), continuous
FAMILY_CAP = [
    ("SRB",      1, 2.5, 1.5, "heavy",    (1,1,1,1,1), 1,
     "Primary industrial solution; ~95% of heavy elevators. Chosen for "
     "misalignment tolerance + shock capability, not because C is highest."),
    ("SAB",      4, 3.0, 2.5, "moderate", (1,1,0,0,0), 1,
     "Self-aligning ball: highest misalignment, lower load capacity."),
    ("Y-insert", 3, 5.0, 0.5, "light",    (1,0,0,0,0), 1,
     "Agriculture / light food / grain elevators. 5deg STATIC alignment but "
     "only ~0.5deg RUNNING -- eliminated by load and L10, not misalignment."),
    ("DGBB",     2, 0.17, 0.05, "light",  (1,0,0,0,0), 0,
     "Deep groove ball, light duty. 2-10 arcmin running -- a CEMA-slope-sized "
     "shaft (0.086deg) already over-misaligns it."),
    ("TRB",      5, 0.05, 0.03, "moderate",(0,0,0,0,0), 0,
     "Taper roller: special thrust cases, normally avoided on elevator head "
     "shafts. Requires precise alignment the shaft slope cannot guarantee."),
]

# environment REQUIREMENTS (data-driven, Jay's table). verified=0.
ENVIRONMENTS = [
    ("grain",      0,0,0, "high",      "low",       "dust", 1200.0),
    ("cement",     0,0,0, "very_high", "low",       "dust", 8200.0),
    ("food",       1,1,1, "medium",    "medium",    "none", 4200.0),
    ("fertilizer", 0,0,0, "medium",    "high",      "none", 6000.0),
    ("marine",     1,0,0, "low",       "very_high", "none", 6000.0),
    ("mining",     0,0,0, "very_high", "medium",    "dust", 8600.0),
]

# application PREFERENCES (curated judgement, Jay's mapping). verified=0.
PREFERENCES = [
    ("cement",     "SRB",      "taconite",   "Very high dust; taconite seals + SRB in SNL are the industry standard."),
    ("mining",     "SRB",      "labyrinth",  "Heavy shock and dust; heavy SRB with labyrinth + purge."),
    ("food",       "Y-insert", "triple_lip", "Washdown + food contact; stainless Y-inserts, triple-lip seals, FDA lube. SRB where load demands."),
    ("fertilizer", "SRB",      "triple_lip", "Corrosive; triple-lip seals + corrosion protection."),
    ("marine",     "SRB",      "v_ring",     "Very high corrosion; stainless / v-ring sealing."),
    ("grain",      "Y-insert", "contact",    "Light duty, intermittent; Y-inserts are standard on grain elevators."),
]


def seed(con):
    n = {"family": 0, "env": 0, "pref": 0, "split": 0}
    # thrust bearings are tagged on the bearings row but get NO capability row --
    # they are not a head-shaft support family, so the selector excludes them.
    for fam, tier, ms, mr, shock, duty, cont, note in FAMILY_CAP:
        if con.execute("SELECT 1 FROM bearing_family_capability WHERE family=?", (fam,)).fetchone():
            continue
        con.execute(
            "INSERT INTO bearing_family_capability (family,tier,misalign_static_deg,"
            "misalign_running_deg,shock_rating,duty_light,duty_medium,duty_heavy,"
            "duty_severe,duty_critical,continuous_duty,notes,source_type,verified) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'judgement',0)",
            (fam, tier, ms, mr, shock, *duty, cont, note))
        n["family"] += 1
    for env, sst, food, wash, dust, corr, atex, hrs in ENVIRONMENTS:
        if con.execute("SELECT 1 FROM environment_profile WHERE environment=?", (env,)).fetchone():
            continue
        con.execute(
            "INSERT INTO environment_profile (environment,req_stainless,req_food_grade,"
            "req_washdown,dust_level,corrosion_level,atex,typical_hours_year,"
            "source_type,verified) VALUES (?,?,?,?,?,?,?,?,'judgement',0)",
            (env, sst, food, wash, dust, corr, atex, hrs))
        n["env"] += 1
    for env, fam, seal, why in PREFERENCES:
        if con.execute("SELECT 1 FROM application_preference WHERE environment=? AND preferred_family=?",
                       (env, fam)).fetchone():
            continue
        con.execute(
            "INSERT INTO application_preference (environment,preferred_family,"
            "preferred_seal,rationale,source_type,author,verified) "
            "VALUES (?,?,?,?,'judgement','VECTOMEC',0)", (env, fam, seal, why))
        n["pref"] += 1
    # decompose type -> family/housing on the bearings rows
    for t, (fam, hous) in TYPE_SPLIT.items():
        cur = con.execute(
            "UPDATE bearings SET bearing_family=?, housing_from_type=COALESCE(housing_from_type,?) "
            "WHERE type=? AND bearing_family IS NULL", (fam, hous, t))
        n["split"] += cur.rowcount
    con.commit()
    return n


def demo_assembly_rule(con):
    """Show that the assembly is DERIVABLE, not data. Verified against the
    live catalogue: 222xx SRB -> SNL 5xx / H3xx / TSN 5xx."""
    print("\nassembly rule (derived, not stored) -- sample of SRB rows:")
    rows = con.execute("SELECT name, bore FROM bearings WHERE type='SRB' "
                       "ORDER BY bore LIMIT 6").fetchall()
    for name, bore in rows:
        m = re.match(r"(22[023])(\d{2})", name or "")
        if not m:
            print(f"  {name:12s} -> (non-standard designation, needs explicit mapping)")
            continue
        size = m.group(2)
        print(f"  {name:12s} bore {int(bore):3d}mm -> SNL 5{size}  H3{size}  TSN 5{size}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=_DB)
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 37, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} too old for STRICT.")

    con = sqlite3.connect(args.db)
    try:
        con.executescript(ddl())
        add_family_column(con)
        if not args.no_seed:
            n = seed(con)
            print(f"seeded: {n['family']} families, {n['env']} environments, "
                  f"{n['pref']} preferences; {n['split']} bearings classified")
        for t in ("bearing_family_capability", "housing_catalog", "seal_catalog",
                  "adapter_catalog", "environment_profile", "application_preference"):
            strict = con.execute("SELECT strict FROM pragma_table_list WHERE name=?", (t,)).fetchone()
            cols = len(con.execute(f"PRAGMA table_info({t})").fetchall())
            rows = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:28s} {cols:2d} cols  {rows:3d} rows  STRICT={'yes' if strict and strict[0] else 'NO'}")
        nclass = con.execute("SELECT COUNT(*) FROM bearings WHERE bearing_family IS NOT NULL").fetchone()[0]
        print(f"\n  bearings classified to a family: {nclass}/168")
        for fam, n in con.execute("SELECT bearing_family, COUNT(*) FROM bearings "
                                  "WHERE bearing_family IS NOT NULL GROUP BY bearing_family "
                                  "ORDER BY COUNT(*) DESC"):
            print(f"    {fam:10s} {n}")
        demo_assembly_rule(con)
        print("\nAll capability/preference rows are verified=0 (engineering judgement,")
        print("pending review). No per-bearing catalogue value was written as verified.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())