"""
VECTRIX™ — SQLite Database Layer
Shared across Bucket Elevator and Screw Conveyor modules.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "vectrix.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
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
    conn.executescript("""
        -- ─── DESIGNS TABLE ─────────────────────────────────────────────
        -- Stores serialised inputs + results for any conveyor module.
        CREATE TABLE IF NOT EXISTS designs (
            id          TEXT PRIMARY KEY,
            module      TEXT NOT NULL,           -- 'bucket_elevator' | 'screw_conveyor' | ...
            name        TEXT NOT NULL,
            project     TEXT,
            inputs_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            notes       TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        -- ─── MATERIALS TABLE (user-defined overrides) ──────────────────
        CREATE TABLE IF NOT EXISTS custom_materials (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            rho         REAL NOT NULL,
            angle       REAL NOT NULL DEFAULT 35,
            abr         TEXT NOT NULL DEFAULT 'B',
            flow        TEXT NOT NULL DEFAULT 'Average',
            Km          REAL NOT NULL DEFAULT 1.1,
            notes       TEXT,
            created_at  TEXT NOT NULL
        );

        -- ─── CALCULATION LOG (optional audit trail) ────────────────────
        CREATE TABLE IF NOT EXISTS calc_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            module      TEXT NOT NULL,
            inputs_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            ts          TEXT NOT NULL
        );

        -- ─── INDEXES ───────────────────────────────────────────────────
        CREATE INDEX IF NOT EXISTS idx_designs_module   ON designs(module);
        CREATE INDEX IF NOT EXISTS idx_designs_project  ON designs(project);
        CREATE INDEX IF NOT EXISTS idx_calclog_module   ON calc_log(module);
    """)
    conn.commit()
    conn.close()
    print("✅ VECTRIX™ DB initialised at", DB_PATH)
