"""
VECTRIX™ Unified Database — vectrix_database.py
─────────────────────────────────────────────────────────────────────────────
Single SQLite database shared by:
  • AKSHAYVIPRA EL-MEC bucket elevator (BE)
  • Screw conveyor module (SC)

Swap DATABASE_URL env var for PostgreSQL in production.
SQLite is the default and works with both modules during development.
"""
from sqlalchemy import create_engine  # type: ignore[import]
from sqlalchemy.ext.declarative import declarative_base  # type: ignore[import]
from sqlalchemy.orm import sessionmaker  # type: ignore[import]
import os

DATABASE_URL = os.getenv("VECTRIX_DB_URL", "sqlite:///./vectrix.db")

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
        from .vectrix_tables import Material, Bearing, Gearbox, Motor, Drive, CostItem
    except ImportError:
        from vectrix_tables import Material, Bearing, Gearbox, Motor, Drive, CostItem
    Base.metadata.create_all(bind=engine)