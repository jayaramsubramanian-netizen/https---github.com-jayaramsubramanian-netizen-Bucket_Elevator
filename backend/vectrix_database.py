"""
VECTRIX™ Unified Database — vectrix_database.py
─────────────────────────────────────────────────────────────────────────────
Single SQLite database shared by:
  • JAYVEECONS bucket elevator (BE)
  • Screw conveyor module (SC)

Swap DATABASE_URL env var for PostgreSQL in production.
SQLite is the default and works with both modules during development.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from pathlib import Path

# FIX (Jay's question: "where does the data exist now... where does the
# stray main/vectrix.db come from"): this previously defaulted to
# "sqlite:///./vectrix.db" -- a path relative to the process's CURRENT
# WORKING DIRECTORY, not anchored to this file's own location the way
# database.py (the raw-sqlite3 layer actually used by main.py) already
# correctly is. Running/importing this module from any directory other
# than backend/ created a stray, separate vectrix.db wherever that working
# directory happened to be. Anchored the same way database.py is, so both
# layers always resolve to the exact same physical file regardless of CWD.
_DB_FILE = Path(__file__).parent / "vectrix.db"
DATABASE_URL = os.getenv("VECTRIX_DB_URL", f"sqlite:///{_DB_FILE}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables (safe to call repeatedly — uses CREATE IF NOT EXISTS)."""
    try:
        from .vectrix_tables import (
            Material, Bearing, Gearbox, Motor, Drive, CostItem,
            Bucket, MaterialGrade, Belt, Screw, Bolt,
        )
    except ImportError:
        from vectrix_tables import (
            Material, Bearing, Gearbox, Motor, Drive, CostItem,
            Bucket, MaterialGrade, Belt, Screw, Bolt,
        )
    # Migration: buckets was created in an earlier round before the bolt-
    # punching columns (punch/boltA_mm/etc.) existed on the Bucket model.
    # CREATE TABLE IF NOT EXISTS doesn't alter an existing table's columns,
    # so the old, narrower table would otherwise stick around and every
    # query against the new column set would fail outright (confirmed live:
    # "no such column: buckets.punch"). Safe to drop and recreate -- this
    # table is a re-syncable mirror of BUCKET_SERIES (see seed_catalog.py),
    # not a source of truth, so there's no irreplaceable data to lose.
    try:
        with engine.connect() as conn:
            cols = [r[1] for r in conn.exec_driver_sql(
                "PRAGMA table_info(buckets)").fetchall()]
            if cols and "punch" not in cols:
                conn.exec_driver_sql("DROP TABLE buckets")
                conn.commit()
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)