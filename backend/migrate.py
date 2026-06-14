"""
VECTRIX™ Database Migration — migrate.py
─────────────────────────────────────────────────────────────────────────────
One-shot script that merges:
  • screw_conveyor.db  — 484 materials, 168 bearings, 36 gearboxes,
                         52 motors, 37 drives, 6 cost items
  • materials.py       — 400 bucket elevator materials (VECTRIX internal dict)

into a single vectrix.db with the unified schema from vectrix_tables.py.

Merge rules
───────────────────────────────────────────────────────────────────────────
1. SC materials are inserted first with app tags from their existing `app`
   JSON field, plus "sc" if not already present.

2. For each BE material:
   a. Name match found in SC rows → UPDATE the existing row: add BE-specific
      columns (Leq_default, Ceff_default, vfi, wall_friction_deg, etc.) and
      append "be" to the app array.  SC-specific fields (lambda_ref, fill_max,
      cls, particle_class) are preserved.
   b. No name match → INSERT as a new row with app=["be"].

3. Component tables (bearings, gearboxes, motors, drives, cost_items) are
   copied verbatim from screw_conveyor.db — they are already usable by both
   modules.

Run
───────────────────────────────────────────────────────────────────────────
  cd <project_root>
  python -m backend.migrate                        # normal run
  python -m backend.migrate --force                # drop and rebuild from scratch
  python -m backend.migrate --sc-db path/to/sc.db # custom SC database path
  python -m backend.migrate --be-only              # re-merge only BE materials

Field mapping notes
───────────────────────────────────────────────────────────────────────────
  rho_bulk       ← BE rho_loose [kg/m³] or SC rho × 1000 [t/m³ → kg/m³]
  rho_sc_tm3     ← SC rho [t/m³] (preserved unconverted for SC calcs)
  rho_vib        ← BE rho_vib [kg/m³]
  flowability    ← both use 1–4 scale; SC values > 4 clamped and stored in
                   flowability_raw unchanged
  abr_code       ← BE direct; SC "Low"→1, "Medium"→3, "High"→5, "VH"→7
  abr_text       ← SC direct; BE derived from abr_code
  angle_repose   ← SC aor / BE angle_repose
  moisture_pct   ← SC moist / BE moisture_pct
  category       ← canonical short code (see CAT_SC_TO_CODE)
  category_full  ← verbose English name (see CAT_CODE_TO_FULL)
"""

import argparse
import json
import os
import sqlite3
import sys
import re
import types

# ─── Path setup ──────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

# ─── Lookup tables ───────────────────────────────────────────────────────────

# SC abrasiveness text → BE numeric abr_code (midpoint of each band)
ABR_TEXT_TO_CODE: dict[str, int] = {
    "low":       1,
    "medium":    3,
    "high":      5,
    "very high": 7,
}

# BE numeric abr_code → SC abrasiveness text
ABR_CODE_TO_TEXT: dict[int, str] = {
    0: "Low", 1: "Low",
    2: "Low", 3: "Medium",
    4: "Medium", 5: "High",
    6: "High", 7: "Very High",
}

# SC category (verbose) → canonical short code
CAT_SC_TO_CODE: dict[str, str] = {
    "Agriculture": "GRAIN",
    "Biomass":     "BIO",
    "Chemicals":   "CHEM",
    "Construction":"CONST",
    "Food":        "FOOD",
    "Mining":      "MIN",
}

# BE category code → verbose English name
CAT_CODE_TO_FULL: dict[str, str] = {
    "BIO":   "Biomass",
    "CEM":   "Construction",
    "CHEM":  "Chemicals",
    "COAL":  "Mining",
    "CONST": "Construction",
    "ENV":   "Chemicals",
    "FERT":  "Chemicals",
    "FOOD":  "Food",
    "GLASS": "Construction",
    "GRAIN": "Agriculture",
    "METAL": "Mining",
    "MIN":   "Mining",
    "PETRO": "Chemicals",
    "PHARM": "Chemicals",
    "POLY":  "Chemicals",
    "SALT":  "Mining",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """'Rock Salt (coarse)' → 'rock_salt_coarse'"""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:40]


def parse_app(raw) -> list:
    """Parse SC app field (stored as JSON string) into a Python list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else [str(v)]
    except (json.JSONDecodeError, TypeError):
        return [str(raw)]


def ensure_tag(app_list: list, tag: str) -> list:
    if tag not in app_list:
        app_list = list(app_list) + [tag]
    return app_list


def clamp_flowability(raw: int) -> int:
    """Clamp SC flowability values > 4 to 4 (they use a wider scale)."""
    return min(int(raw), 4) if raw else raw


# ─── SC material → unified row ────────────────────────────────────────────────

def sc_to_unified(m: dict) -> dict:
    """Convert a screw_conveyor.db Material row to unified schema dict."""
    app_list = parse_app(m.get("app"))
    app_list = ensure_tag(app_list, "sc")

    rho_tm3  = float(m.get("rho") or 0)
    rho_bulk = rho_tm3 * 1000.0    # t/m³ → kg/m³

    abr_raw  = (m.get("abr") or "Low").strip()
    abr_code = ABR_TEXT_TO_CODE.get(abr_raw.lower(), 3)
    abr_text = abr_raw

    fl_raw   = m.get("flowability") or 2
    fl_norm  = clamp_flowability(fl_raw)

    cat_full = m.get("category") or ""
    cat_code = CAT_SC_TO_CODE.get(cat_full, cat_full[:10].upper())

    mat_id   = slugify(m.get("name") or "")

    return {
        "mat_id":          mat_id,
        "name":            m.get("name"),
        "category":        cat_code,
        "category_full":   cat_full,
        # density
        "rho_bulk":        round(rho_bulk, 1),
        "rho_min":         round(float(m["rho_min"]) * 1000, 1) if m.get("rho_min") else None,
        "rho_max":         round(float(m["rho_max"]) * 1000, 1) if m.get("rho_max") else None,
        "rho_vib":         None,
        "rho_sc_tm3":      rho_tm3,
        # flow
        "flowability":     fl_norm,
        "flowability_raw": fl_raw,
        "angle_repose":    m.get("aor"),
        "angle_surcharge": None,
        "angle_internal_friction": None,
        "wall_friction_deg": None,
        "cohesion":        m.get("cohesion"),
        "bridging_risk":   m.get("bridging_risk"),
        "flow_regime":     m.get("flow_regime"),
        # moisture / temp
        "moisture_pct":    m.get("moist"),
        "temp_max":        m.get("temp_max"),
        # abrasiveness
        "abr_code":        abr_code,
        "abr_text":        abr_text,
        # particle
        "particle_class":  m.get("particle_class"),
        "size_code":       None,
        "particle_size_mm": None,
        # BE fields — empty until merged
        "Leq_default":     None,
        "Ceff_default":    None,
        "vfi":             None,
        "bucket_fill_factor": None,
        "stream_spread_factor": None,
        "Km":              None,
        "hazard_codes":    None,
        # SC fields
        "lambda_ref":      m.get("lambda_ref"),
        "fill_max":        m.get("fill_max"),
        "cema_cls":        m.get("cls"),
        "cema_code":       m.get("cema_code"),
        "flags":           m.get("flags"),
        # metadata
        "confidence":      m.get("confidence"),
        "source":          m.get("source", "sc_seed"),
        "note":            m.get("note"),
        "app":             json.dumps(app_list),
        "custom":          0,
    }


# ─── BE material → unified row ────────────────────────────────────────────────

def be_to_unified(m: dict) -> dict:
    """Convert a BE materials.py dict to unified schema dict."""
    abr_code = int(m.get("abr_code") or 3)
    abr_text = ABR_CODE_TO_TEXT.get(abr_code, "Medium")

    fl_raw   = int(m.get("flowability") or 2)
    fl_norm  = clamp_flowability(fl_raw)

    cat_code = m.get("category") or ""
    cat_full = CAT_CODE_TO_FULL.get(cat_code, cat_code.capitalize())

    rho_loose = float(m.get("rho_loose") or 0)
    rho_vib   = m.get("rho_vib")

    return {
        "mat_id":          m.get("id") or slugify(m.get("name", "")),
        "name":            m.get("name"),
        "category":        cat_code,
        "category_full":   cat_full,
        # density
        "rho_bulk":        rho_loose,
        "rho_min":         None,
        "rho_max":         float(rho_vib) if rho_vib else None,
        "rho_vib":         float(rho_vib) if rho_vib else None,
        "rho_sc_tm3":      None,
        # flow
        "flowability":     fl_norm,
        "flowability_raw": fl_raw,
        "angle_repose":    m.get("angle_repose"),
        "angle_surcharge": m.get("angle_surcharge"),
        "angle_internal_friction": m.get("angle_internal_friction"),
        "wall_friction_deg": m.get("wall_friction_deg"),
        "cohesion":        m.get("cohesion"),
        "bridging_risk":   None,
        "flow_regime":     None,
        # moisture / temp
        "moisture_pct":    m.get("moisture_pct"),
        "temp_max":        None,
        # abrasiveness
        "abr_code":        abr_code,
        "abr_text":        abr_text,
        # particle
        "particle_class":  None,
        "size_code":       m.get("size_code"),
        "particle_size_mm": None,
        # BE-specific
        "Leq_default":     m.get("Leq_default"),
        "Ceff_default":    m.get("Ceff_default"),
        "vfi":             m.get("vfi"),
        "bucket_fill_factor": m.get("bucket_fill_factor"),
        "stream_spread_factor": m.get("stream_spread_factor"),
        "Km":              m.get("Km"),
        "hazard_codes":    ",".join(m.get("hazard_codes", [])) if isinstance(m.get("hazard_codes"), list) else m.get("hazard_codes"),
        # SC-specific — empty for BE-only rows
        "lambda_ref":      None,
        "fill_max":        None,
        "cema_cls":        None,
        "cema_code":       None,
        "flags":           None,
        # metadata
        "confidence":      0.85,
        "source":          "be_internal",
        "note":            "",
        "app":             json.dumps(["be"]),
        "custom":          0,
    }


# ─── Main migration function ──────────────────────────────────────────────────

def migrate(sc_db_path: str, be_materials_path: str, out_db_path: str,
            force: bool = False, be_only: bool = False) -> None:

    # ── 1. Read source databases ──────────────────────────────────────────
    sc_mats = sc_brgs = sc_gbxs = sc_mots = sc_drvs = sc_costs = []

    if not be_only:
        sc_size = os.path.getsize(sc_db_path) if os.path.exists(sc_db_path) else 0
        if sc_size == 0:
            print(f"WARNING: {sc_db_path} is empty or missing — running in BE-only mode.")
            be_only = True

    if not be_only:
        print(f"Reading SC database: {sc_db_path}")
        sc_con = sqlite3.connect(sc_db_path)
        sc_con.row_factory = sqlite3.Row
        sc_mats  = [dict(r) for r in sc_con.execute("SELECT * FROM materials").fetchall()]
        sc_brgs  = [dict(r) for r in sc_con.execute("SELECT * FROM bearings").fetchall()]
        sc_gbxs  = [dict(r) for r in sc_con.execute("SELECT * FROM gearboxes").fetchall()]
        sc_mots  = [dict(r) for r in sc_con.execute("SELECT * FROM motors").fetchall()]
        sc_drvs  = [dict(r) for r in sc_con.execute("SELECT * FROM drives").fetchall()]
        sc_costs = [dict(r) for r in sc_con.execute("SELECT * FROM cost_items").fetchall()]
        sc_con.close()
        print(f"  {len(sc_mats)} materials, {len(sc_brgs)} bearings, "
              f"{len(sc_gbxs)} gearboxes, {len(sc_mots)} motors, "
              f"{len(sc_drvs)} drives, {len(sc_costs)} cost items")
    else:
        print("BE-only mode: skipping SC database.")

    print(f"Reading BE materials: {be_materials_path}")
    be_mod = types.ModuleType("be_materials")
    exec(open(be_materials_path, encoding="utf-8").read(), be_mod.__dict__)
    be_list = be_mod.MATERIALS
    print(f"  {len(be_list)} BE materials")

    # ── 2. Create / connect target database ───────────────────────────────
    if force and os.path.exists(out_db_path):
        os.remove(out_db_path)
        print(f"Dropped existing {out_db_path}")

    print(f"\nCreating unified database: {out_db_path}")
    out = sqlite3.connect(out_db_path)
    out.row_factory = sqlite3.Row

    # Create schema from vectrix_tables.py ORM definitions (DDL generation)
    out.executescript("""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS materials (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    mat_id              TEXT UNIQUE,
    name                TEXT UNIQUE NOT NULL,
    category            TEXT,
    category_full       TEXT,
    rho_bulk            REAL NOT NULL,
    rho_min             REAL,
    rho_max             REAL,
    rho_vib             REAL,
    rho_sc_tm3          REAL,
    flowability         INTEGER,
    flowability_raw     INTEGER,
    angle_repose        REAL,
    angle_surcharge     REAL,
    angle_internal_friction REAL,
    wall_friction_deg   REAL,
    cohesion            REAL,
    bridging_risk       REAL,
    flow_regime         TEXT,
    moisture_pct        REAL,
    temp_max            REAL,
    abr_code            INTEGER,
    abr_text            TEXT,
    particle_class      TEXT,
    size_code           TEXT,
    particle_size_mm    REAL,
    "Leq_default"       REAL,
    "Ceff_default"      REAL,
    vfi                 INTEGER,
    bucket_fill_factor  REAL,
    stream_spread_factor REAL,
    "Km"                REAL,
    hazard_codes        TEXT,
    lambda_ref          REAL,
    fill_max            REAL,
    cema_cls            TEXT,
    cema_code           TEXT,
    flags               TEXT,
    confidence          REAL,
    source              TEXT,
    note                TEXT,
    app                 TEXT,
    custom              INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_mat_name ON materials(name);
CREATE INDEX IF NOT EXISTS idx_mat_category ON materials(category);
CREATE INDEX IF NOT EXISTS idx_mat_id ON materials(mat_id);

CREATE TABLE IF NOT EXISTS bearings (
    id          INTEGER PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    mfr         TEXT,
    type        TEXT,
    bore        REAL,
    od          REAL,
    B           REAL,
    C           REAL,
    C0          REAL,
    p           REAL,
    speed_g     INTEGER,
    seal        TEXT,
    role        TEXT,
    brg_insert  TEXT,
    mass_kg     REAL,
    note        TEXT,
    custom      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gearboxes (
    id          INTEGER PRIMARY KEY,
    model       TEXT UNIQUE NOT NULL,
    type        TEXT,
    stages      INTEGER,
    Tn          REAL,
    Pkw         REAL,
    ratio_min   REAL,
    ratio_max   REAL,
    eta         REAL,
    mount       TEXT,
    ip          TEXT,
    temp_max    REAL,
    mass_kg     REAL,
    note        TEXT,
    custom      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS motors (
    id          INTEGER PRIMARY KEY,
    model       TEXT UNIQUE,
    frame       TEXT,
    Pkw         REAL,
    poles       INTEGER,
    rpm_50hz    REAL,
    efficiency  REAL,
    ie_class    TEXT,
    ip          TEXT,
    mass_kg     REAL,
    note        TEXT,
    custom      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS drives (
    id          INTEGER PRIMARY KEY,
    model       TEXT UNIQUE,
    type        TEXT,
    Pkw_max     REAL,
    Vrated      REAL,
    Irated      REAL,
    overload_pct REAL,
    control     TEXT,
    ip          TEXT,
    features    TEXT,
    note        TEXT,
    custom      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cost_items (
    id              INTEGER PRIMARY KEY,
    item            TEXT UNIQUE NOT NULL,
    usd             REAL NOT NULL,
    description     TEXT,
    material_group  TEXT,
    custom          INTEGER DEFAULT 0,
    note            TEXT
);
""")

    # ── 3. Insert SC materials ─────────────────────────────────────────────
    print(f"\nInserting {len(sc_mats)} SC materials…")
    unified_rows = {}   # name.lower() → row dict (for later merge lookup)
    sc_inserted = 0

    for m in sc_mats:
        row = sc_to_unified(m)
        nm  = (row["name"] or "").lower().strip()
        unified_rows[nm] = row
        try:
            out.execute("""
                INSERT INTO materials (
                    mat_id, name, category, category_full,
                    rho_bulk, rho_min, rho_max, rho_vib, rho_sc_tm3,
                    flowability, flowability_raw,
                    angle_repose, angle_surcharge, angle_internal_friction,
                    wall_friction_deg, cohesion, bridging_risk, flow_regime,
                    moisture_pct, temp_max,
                    abr_code, abr_text,
                    particle_class, size_code, particle_size_mm,
                    Leq_default, Ceff_default, vfi,
                    bucket_fill_factor, stream_spread_factor, Km, hazard_codes,
                    lambda_ref, fill_max, cema_cls, cema_code, flags,
                    confidence, source, note, app, custom
                ) VALUES (
                    :mat_id, :name, :category, :category_full,
                    :rho_bulk, :rho_min, :rho_max, :rho_vib, :rho_sc_tm3,
                    :flowability, :flowability_raw,
                    :angle_repose, :angle_surcharge, :angle_internal_friction,
                    :wall_friction_deg, :cohesion, :bridging_risk, :flow_regime,
                    :moisture_pct, :temp_max,
                    :abr_code, :abr_text,
                    :particle_class, :size_code, :particle_size_mm,
                    :Leq_default, :Ceff_default, :vfi,
                    :bucket_fill_factor, :stream_spread_factor, :Km, :hazard_codes,
                    :lambda_ref, :fill_max, :cema_cls, :cema_code, :flags,
                    :confidence, :source, :note, :app, :custom
                )""", row)
            sc_inserted += 1
        except sqlite3.IntegrityError:
            pass   # duplicate name — skip

    out.commit()
    print(f"  Inserted: {sc_inserted}")

    # ── 4. Merge BE materials ──────────────────────────────────────────────
    print(f"\nMerging {len(be_list)} BE materials…")
    be_updated = 0
    be_inserted = 0
    be_skipped  = 0

    for m in be_list:
        be_row = be_to_unified(m)
        nm     = (be_row["name"] or "").lower().strip()

        if nm in unified_rows:
            # ── Name match: UPDATE the SC row with BE fields ───────────────
            existing_app = parse_app(
                out.execute("SELECT app FROM materials WHERE name=? COLLATE NOCASE",
                            (be_row["name"],)).fetchone()["app"]
            )
            merged_app = ensure_tag(existing_app, "be")

            out.execute("""
                UPDATE materials SET
                    -- BE-specific enrichment fields
                    rho_vib              = COALESCE(rho_vib, :rho_vib),
                    angle_surcharge      = COALESCE(angle_surcharge, :angle_surcharge),
                    angle_internal_friction = COALESCE(angle_internal_friction, :angle_internal_friction),
                    wall_friction_deg    = COALESCE(wall_friction_deg, :wall_friction_deg),
                    size_code            = COALESCE(size_code, :size_code),
                    particle_size_mm     = COALESCE(particle_size_mm, :particle_size_mm),
                    Leq_default          = :Leq_default,
                    Ceff_default         = :Ceff_default,
                    vfi                  = :vfi,
                    bucket_fill_factor   = :bucket_fill_factor,
                    stream_spread_factor = :stream_spread_factor,
                    Km                   = :Km,
                    hazard_codes         = :hazard_codes,
                    -- matid: prefer BE id (slug)
                    mat_id               = COALESCE(mat_id, :mat_id),
                    -- App: merge tags
                    app                  = :merged_app
                WHERE name = :name COLLATE NOCASE
            """, {**be_row, "merged_app": json.dumps(merged_app)})
            be_updated += 1

        else:
            # ── No match: INSERT as new BE-only row ────────────────────────
            try:
                out.execute("""
                    INSERT INTO materials (
                        mat_id, name, category, category_full,
                        rho_bulk, rho_min, rho_max, rho_vib, rho_sc_tm3,
                        flowability, flowability_raw,
                        angle_repose, angle_surcharge, angle_internal_friction,
                        wall_friction_deg, cohesion, bridging_risk, flow_regime,
                        moisture_pct, temp_max,
                        abr_code, abr_text,
                        particle_class, size_code, particle_size_mm,
                        Leq_default, Ceff_default, vfi,
                        bucket_fill_factor, stream_spread_factor, Km, hazard_codes,
                        lambda_ref, fill_max, cema_cls, cema_code, flags,
                        confidence, source, note, app, custom
                    ) VALUES (
                        :mat_id, :name, :category, :category_full,
                        :rho_bulk, :rho_min, :rho_max, :rho_vib, :rho_sc_tm3,
                        :flowability, :flowability_raw,
                        :angle_repose, :angle_surcharge, :angle_internal_friction,
                        :wall_friction_deg, :cohesion, :bridging_risk, :flow_regime,
                        :moisture_pct, :temp_max,
                        :abr_code, :abr_text,
                        :particle_class, :size_code, :particle_size_mm,
                        :Leq_default, :Ceff_default, :vfi,
                        :bucket_fill_factor, :stream_spread_factor, :Km, :hazard_codes,
                        :lambda_ref, :fill_max, :cema_cls, :cema_code, :flags,
                        :confidence, :source, :note, :app, :custom
                    )""", be_row)
                be_inserted += 1
            except sqlite3.IntegrityError:
                be_skipped += 1

    out.commit()
    print(f"  SC rows updated with BE data : {be_updated}")
    print(f"  BE-only rows inserted        : {be_inserted}")
    print(f"  Skipped (duplicate name)     : {be_skipped}")

    # ── 5. Copy component tables ───────────────────────────────────────────
    print("\nCopying component tables from SC database…")

    def copy_table(rows: list, table: str, cols: list) -> int:
        inserted = 0
        for row in rows:
            vals = {c: row.get(c) for c in cols}
            ph   = ", ".join(f":{c}" for c in cols)
            col_str = ", ".join(cols)
            try:
                out.execute(f"INSERT INTO {table} ({col_str}) VALUES ({ph})", vals)
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        out.commit()
        return inserted

    n_brg  = copy_table(sc_brgs, "bearings",
        ["name","mfr","type","bore","od","B","C","C0","p",
         "speed_g","seal","role","brg_insert","mass_kg","note","custom"])
    n_gbx  = copy_table(sc_gbxs, "gearboxes",
        ["model","type","stages","Tn","Pkw","ratio_min","ratio_max",
         "eta","mount","ip","temp_max","mass_kg","note","custom"])
    n_mot  = copy_table(sc_mots, "motors",
        ["model","frame","Pkw","poles","rpm_50hz","efficiency",
         "ie_class","ip","mass_kg","note","custom"])
    n_drv  = copy_table(sc_drvs, "drives",
        ["model","type","Pkw_max","Vrated","Irated","overload_pct",
         "control","ip","features","note","custom"])
    n_cost = copy_table(sc_costs, "cost_items",
        ["item","usd","description","material_group","custom","note"])

    print(f"  Bearings  : {n_brg}")
    print(f"  Gearboxes : {n_gbx}")
    print(f"  Motors    : {n_mot}")
    print(f"  Drives    : {n_drv}")
    print(f"  Cost items: {n_cost}")

    # ── 6. Summary ────────────────────────────────────────────────────────
    total_mats = out.execute("SELECT count(*) FROM materials").fetchone()[0]
    both_mats  = out.execute(
        "SELECT count(*) FROM materials WHERE app LIKE '%be%' AND app LIKE '%sc%'"
    ).fetchone()[0]
    sc_only    = out.execute(
        "SELECT count(*) FROM materials WHERE app LIKE '%sc%' AND app NOT LIKE '%be%'"
    ).fetchone()[0]
    be_only    = out.execute(
        "SELECT count(*) FROM materials WHERE app LIKE '%be%' AND app NOT LIKE '%sc%'"
    ).fetchone()[0]

    out.close()

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅  Migration complete → {out_db_path}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Materials total   : {total_mats}
    Both BE + SC    : {both_mats}
    SC-only         : {sc_only}
    BE-only         : {be_only}
  Bearings          : {n_brg}
  Gearboxes         : {n_gbx}
  Motors            : {n_mot}
  Drives            : {n_drv}
  Cost items        : {n_cost}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


# ─── CLI entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate screw_conveyor.db + materials.py → vectrix.db"
    )
    parser.add_argument(
        "--sc-db",
        default=os.path.join(_DIR, "screw_conveyor.db"),
        help="Path to screw_conveyor.db (default: ./screw_conveyor.db)",
    )
    parser.add_argument(
        "--be-materials",
        default=os.path.join(_DIR, "materials.py"),
        help="Path to BE materials.py (default: ./materials.py)",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(_DIR, "vectrix.db"),
        help="Output database path (default: ./vectrix.db)",
    )
    parser.add_argument(
        "--be-only",
        action="store_true",
        help="Skip SC database — build vectrix.db from BE materials.py only",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and rebuild the output database from scratch",
    )
    args = parser.parse_args()
    migrate(
        sc_db_path       = args.sc_db,
        be_materials_path= args.be_materials,
        out_db_path      = args.out,
        force            = args.force,
        be_only          = args.be_only,
    )