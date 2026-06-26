"""
VECTRIX™ — SQLite Database Layer
Shared across Bucket Elevator and Screw Conveyor modules.
"""

import os
import sqlite3
from pathlib import Path

# ── DB path ───────────────────────────────────────────────────────────────────
# Resolve once at import time.
# Priority: VECTRIX_DB env var → sibling vectrix.db (standard deployment).
# The explicit str() cast + "vectrix.db" default narrows the type to str,
# preventing the Pylance reportArgumentType error on sqlite3.connect().
_DB_PATH: str = os.getenv("VECTRIX_DB", str(Path(__file__).parent / "vectrix.db"))

DB_PATH = Path(_DB_PATH)   # Path version for display / existence checks


def get_connection() -> sqlite3.Connection:
    # check_same_thread=False: FastAPI's contextmanager_in_threadpool runs
    # the finally-block (conn.close) in a different thread than where the
    # connection was created.  Without this flag sqlite3 raises
    # ProgrammingError on every request teardown even though the 200 OK
    # has already been sent.  The connection is request-scoped so there is
    # no shared-state concurrency risk.
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    """FastAPI dependency — yields a connection and closes it after."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist. Run at startup."""
    conn = get_connection()

    # ── Migration: the original custom_materials table (scaffolded, never
    # wired to any endpoint or frontend code) used a minimal, incompatible
    # schema (rho/angle/abr-as-text/flow-as-text, missing category,
    # pref_discharge_type, pref_cr_min/max, hazard_codes, and a dozen other
    # fields a real material needs to actually drive the solver correctly).
    # Table was confirmed empty (0 rows) and unreferenced anywhere except
    # this file before this change -- safe to drop and recreate with the
    # complete schema rather than attempt a column-by-column ALTER TABLE
    # migration for data that doesn't exist.
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(custom_materials)").fetchall()]
        if cols and "rho_loose" not in cols:
            conn.execute("DROP TABLE custom_materials")
    except Exception:
        pass

    conn.executescript("""
        -- ─── DESIGNS TABLE ─────────────────────────────────────────────
        -- Stores serialised inputs + results for any conveyor module.
        CREATE TABLE IF NOT EXISTS designs (
            id                  TEXT PRIMARY KEY,
            module              TEXT NOT NULL,
            name                TEXT NOT NULL,
            project             TEXT,
            inputs_json         TEXT NOT NULL,
            results_json        TEXT NOT NULL,
            notes               TEXT,
            calc_schema_version TEXT,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        );

        -- ─── CUSTOM MATERIALS TABLE (user-defined, full schema) ────────
        -- Field set mirrors materials.py's MATERIALS entries exactly (21
        -- fields) so a custom material is a first-class citizen everywhere
        -- a built-in one is -- including pref_discharge_type/pref_bucket_
        -- style/pref_cr_min/pref_cr_max, which the auto-bucket CR-target
        -- selection (round 7) and the NSGA-II optimizer (round 3+) both
        -- depend on. based_on/created_at/updated_at are bookkeeping, not
        -- part of the solver-facing material dict.
        CREATE TABLE IF NOT EXISTS custom_materials (
            id                       TEXT PRIMARY KEY,
            name                     TEXT NOT NULL,
            category                 TEXT NOT NULL DEFAULT 'MIN',
            rho_loose                REAL NOT NULL,
            rho_vib                  REAL,
            angle_repose             REAL NOT NULL DEFAULT 35,
            angle_surcharge          REAL,
            angle_internal_friction  REAL,
            moisture_pct             REAL NOT NULL DEFAULT 0,
            cohesion                 REAL NOT NULL DEFAULT 0,
            abr_code                 INTEGER NOT NULL DEFAULT 3,
            flowability              INTEGER NOT NULL DEFAULT 2,
            size_code                TEXT DEFAULT 'B',
            hazard_codes             TEXT NOT NULL DEFAULT '[]',
            Km                       REAL NOT NULL DEFAULT 1.0,
            Ceff_default             REAL NOT NULL DEFAULT 1.15,
            Leq_default              REAL NOT NULL DEFAULT 8,
            wall_friction_deg        REAL NOT NULL DEFAULT 20,
            bucket_fill_factor       REAL NOT NULL DEFAULT 0.75,
            pref_discharge_type      TEXT NOT NULL DEFAULT 'centrifugal',
            pref_bucket_style        TEXT NOT NULL DEFAULT 'AA',
            pref_cr_min              REAL NOT NULL DEFAULT 1.2,
            pref_cr_max              REAL NOT NULL DEFAULT 1.5,
            based_on                 TEXT,
            created_at               TEXT NOT NULL,
            updated_at               TEXT NOT NULL
        );

        -- ─── CALCULATION LOG (optional audit trail) ────────────────────
        CREATE TABLE IF NOT EXISTS calc_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            module       TEXT NOT NULL,
            inputs_json  TEXT NOT NULL,
            results_json TEXT NOT NULL,
            ts           TEXT NOT NULL
        );

        -- ─── INDEXES ───────────────────────────────────────────────────
        CREATE INDEX IF NOT EXISTS idx_designs_module   ON designs(module);
        CREATE INDEX IF NOT EXISTS idx_designs_project  ON designs(project);
        CREATE INDEX IF NOT EXISTS idx_calclog_module   ON calc_log(module);
    """)
    conn.commit()
    conn.close()
    print("✅ VECTRIX™ DB initialised at", DB_PATH)