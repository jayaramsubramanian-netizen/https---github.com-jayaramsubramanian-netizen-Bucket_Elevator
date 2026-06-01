"""
VECTRIX™ — AKSHAYVIPRA EL-MEC VECTOMEC™ Design Platform
FastAPI Backend — Bucket Elevator Module

CHANGES FROM ORIGINAL
─────────────────────
1. ImportError fixed: 'OptimizerResult' and 'BucketElevatorResult' removed
   from model imports — neither is defined in models.py.

2. @app.on_event('startup') replaced with lifespan context manager
   (deprecated since FastAPI 0.93, removed in 0.115+).

3. datetime.utcnow() replaced with datetime.now(timezone.utc)
   (deprecated since Python 3.12, user is on 3.14).

4. CORS allow_origins now reads from VECTRIX_CORS_ORIGINS env variable
   with localhost fallback for development.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from database import get_db, init_db
from models import BucketElevatorInput, DesignRecord, OptimizerRequest
from calculations import solve_elevator, run_optimizer, MATERIALS, BUCKET_SERIES, MOTOR_SIZES


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# ── CORS origins from env (safe for production) ───────────────────────────────
_cors_env = os.getenv("VECTRIX_CORS_ORIGINS", "")
CORS_ORIGINS = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else ["http://localhost:3000", "http://localhost:5173"]
)


app = FastAPI(
    title="VECTRIX™ Design Platform API",
    description="AKSHAYVIPRA EL-MEC — VECTOMEC™ Bucket Elevator & Conveyor Design",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REFERENCE DATA ──────────────────────────────────────────────────────────

@app.get("/api/materials")
def get_materials():
    return {"materials": MATERIALS}


@app.get("/api/bucket-series")
def get_bucket_series():
    return {"bucket_series": BUCKET_SERIES}


@app.get("/api/motor-sizes")
def get_motor_sizes():
    return {"motor_sizes": MOTOR_SIZES}


# ─── CALCULATIONS ─────────────────────────────────────────────────────────────

@app.post("/api/bucket-elevator/calculate")
def calculate(inp: BucketElevatorInput):
    """Full CEMA 375-2017 bucket elevator design calculation."""
    try:
        return solve_elevator(inp)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/bucket-elevator/optimize")
def optimize(req: OptimizerRequest):
    """Grid-search optimizer over RPM × Bucket × Fill space."""
    try:
        candidates = run_optimizer(req)
        return {"candidates": candidates, "count": len(candidates)}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


# ─── DESIGNS ──────────────────────────────────────────────────────────────────

@app.post("/api/designs/save")
def save_design(record: DesignRecord, db: sqlite3.Connection = Depends(get_db)):
    """Persist a named design to SQLite."""
    cur = db.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO designs
        (id, module, name, project, inputs_json, results_json, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.id, record.module, record.name, record.project,
        record.inputs_json, record.results_json, record.notes,
        record.created_at or datetime.now(timezone.utc).isoformat(),
        datetime.now(timezone.utc).isoformat(),
    ))
    db.commit()
    return {"saved": True, "id": record.id}


@app.get("/api/designs")
def list_designs(
    module: Optional[str] = None,
    project: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.cursor()
    query  = "SELECT id, module, name, project, notes, created_at, updated_at FROM designs WHERE 1=1"
    params = []
    if module:
        query += " AND module = ?"; params.append(module)
    if project:
        query += " AND project = ?"; params.append(project)
    query += " ORDER BY updated_at DESC"
    return {"designs": [dict(r) for r in cur.execute(query, params).fetchall()]}


@app.get("/api/designs/{design_id}")
def get_design(design_id: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.cursor().execute("SELECT * FROM designs WHERE id = ?", (design_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Design not found")
    return dict(row)


@app.delete("/api/designs/{design_id}")
def delete_design(design_id: str, db: sqlite3.Connection = Depends(get_db)):
    db.cursor().execute("DELETE FROM designs WHERE id = ?", (design_id,))
    db.commit()
    return {"deleted": True, "id": design_id}


# ─── PROJECTS ────────────────────────────────────────────────────────────────

@app.get("/api/projects")
def list_projects(db: sqlite3.Connection = Depends(get_db)):
    rows = db.cursor().execute(
        "SELECT DISTINCT project FROM designs WHERE project IS NOT NULL ORDER BY project"
    ).fetchall()
    return {"projects": [r["project"] for r in rows]}


# ─── HEALTH ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "product": "VECTRIX™", "version": "1.0.0",
            "cors_origins": CORS_ORIGINS}
