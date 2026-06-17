"""
VECTRIX™ — AKSHAYVIPRA EL-MEC VECTOMEC™ Design Platform
FastAPI Backend — Bucket Elevator Module

v1.1.0 — Engineering Platform Hardening
────────────────────────────────────────────────────────────────────────────────
 1. Response envelope     {meta, data, warnings} on all calculation endpoints.
 2. _solver_meta()        Central version / standard / timestamp / input-hash.
 3. _collect_warnings()   Non-fatal CEMA 375-2017 advisory flags alongside
                          results rather than raising HTTP 422.
 4. Structured errors     ErrorDetail(code, field, standard_clause) replaces
                          bare HTTPException strings.
 5. /api/v1 prefix        APIRouter for forward-compatible versioning; old
                          /api/* kept as hidden compat aliases.
 6. lru_cache             Reference data payloads cached at module level —
                          no realloc on every GET.
 7. Audit table           calc_audit written via BackgroundTasks (never
                          blocks the HTTP response).
 8. CORS regex            VECTRIX_CORS_REGEX env var for internal wildcard
                          sub-domains alongside the origins list.
 9. calc_schema_version   Stored per design record; enables forward-compat
                          migration when equations evolve.
10. _err() helper         Single raise site for structured HTTP errors;
                          annotated -> Never so type-checkers flag dead code.
────────────────────────────────────────────────────────────────────────────────
"""

import hashlib
import io
import json
import traceback as _traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
import os
import sqlite3
from typing import Any, Never, Optional

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

try:
    from .database import get_db, init_db
except ImportError:
    from database import get_db, init_db
try:
    from .models import BucketElevatorInput, DesignRecord, OptimizerRequest
except ImportError:
    from models import BucketElevatorInput, DesignRecord, OptimizerRequest
try:
    from .calculations import solve_elevator, run_optimizer, MATERIALS, BUCKET_SERIES, MOTOR_SIZES
except ImportError:
    from calculations import solve_elevator, run_optimizer, MATERIALS, BUCKET_SERIES, MOTOR_SIZES
try:
    from .generate_report import build_report, build_variant_report
except ImportError:
    from generate_report import build_report, build_variant_report


# ── Constants ─────────────────────────────────────────────────────────────────

CALC_SCHEMA_VERSION = "1.1.0"
CEMA_STANDARD       = "CEMA 375-2017"

# Must match the DB path used in database.py.  Override via env if needed.
_DB_PATH = os.getenv("VECTRIX_DB", "vectrix.db")


# ── Improvement 2 — Solver metadata helper ─────────────────────────────────────
#
# Every calculation response includes this block.
# input_hash is a truncated SHA-256 of the canonicalised input dict:
#   • clients can skip re-sending a request when the hash matches a cache entry
#   • audit records can be joined back to calc_audit by hash alone
#   • regression test suites can assert on hash stability across solver versions

def _solver_meta(inp_dict: dict | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "solver_version": CALC_SCHEMA_VERSION,
        "cema_reference": CEMA_STANDARD,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }
    if inp_dict:
        raw = json.dumps(inp_dict, sort_keys=True, default=str).encode()
        meta["input_hash"] = hashlib.sha256(raw).hexdigest()[:16]
    return meta


# ── Improvement 1 — Response envelope ──────────────────────────────────────────
#
# Why a dedicated model rather than a plain dict?
#   • FastAPI validates and documents the shape automatically in OpenAPI.
#   • Front-end clients can switch on response.warnings.length without
#     guessing whether the field will exist.
#   • Adding new top-level keys (e.g. "debug") in future is non-breaking.

class CalcResponse(BaseModel):
    """
    Standard wrapper for all calculation endpoints.

    meta     — solver_version, cema_reference, timestamp, input_hash
    data     — raw solver output (shape varies per endpoint)
    warnings — non-fatal CEMA advisory notes; empty list when all clear
    """
    meta:     dict[str, Any]
    data:     Any
    warnings: list[str] = Field(default_factory=list)


# ── Improvement 4 — Structured error model ─────────────────────────────────────
#
# Returning a bare string in HTTPException.detail is fine for development but
# breaks clients that try to parse errors programmatically.  With ErrorDetail:
#   • code      — machine-readable constant (e.g. "SOLVER_ERROR")
#   • field     — which input field caused the problem, if applicable
#   • standard_clause — CEMA section that defines the violated constraint
#
# _err() is annotated -> Never so mypy / pyright know it never returns.
# Any code in the same branch after _err() is flagged as unreachable.

class ErrorDetail(BaseModel):
    code:            str
    message:         str
    field:           str | None = None
    standard_clause: str | None = None


def _err(
    code:   str,
    msg:    str,
    field:  str | None = None,
    clause: str | None = None,
    status: int = 422,
) -> Never:
    raise HTTPException(
        status_code=status,
        detail=ErrorDetail(
            code=code, message=msg,
            field=field, standard_clause=clause,
        ).model_dump(),
    )


# ── Improvement 3 — Warning accumulator ────────────────────────────────────────
#
# Design warnings are different from validation errors:
#   • Validation errors    → refuse to solve; return HTTP 422 immediately.
#   • Engineering warnings → solve anyway; flag the advisory alongside results.
#
# This distinction matters on real projects.  An engineer may knowingly run
# a slightly over-filled elevator to compare HPR; blocking them with a 422
# forces them to game the inputs instead of reading the warning.
#
# Field names below (bucket_fill_pct, belt_speed_fpm, discharge_type, …)
# must match the keys returned by solve_elevator().  Extend this list as the
# physics layer gains additional tracked quantities.

def _collect_warnings(inp: BucketElevatorInput, results: dict[str, Any]) -> list[str]:
    w: list[str] = []

    fill = results.get("bucket_fill_pct", 0.0)
    if fill > 80.0:
        w.append(
            f"Bucket fill {fill:.1f} % exceeds recommended 80 % "
            f"(CEMA 375-2017 §6.4). Consider larger bucket series or reduced belt speed."
        )

    speed  = results.get("belt_speed_fpm", 0.0)
    d_type = results.get("discharge_type", "centrifugal")

    if d_type == "centrifugal":
        if speed > 225.0:
            w.append(
                f"Belt speed {speed:.0f} fpm exceeds centrifugal-discharge upper limit "
                f"of 225 fpm (CEMA 375-2017 §7.2). Verify pulley diameter and RPM."
            )
        elif speed < 100.0:
            w.append(
                f"Belt speed {speed:.0f} fpm may be insufficient for centrifugal "
                f"discharge (CEMA 375-2017 §7.2 recommends ≥ 100 fpm)."
            )

    # Motor oversizing flag — more than 25 % above calculated requirement
    # is worth flagging for energy-efficiency review.
    motor_hp     = results.get("motor_hp",          0.0)
    sel_motor_hp = results.get("selected_motor_hp", 0.0)
    if sel_motor_hp > 0 and sel_motor_hp > motor_hp * 1.25:
        w.append(
            f"Selected motor ({sel_motor_hp:.1f} hp) is more than 25 % oversized "
            f"relative to calculated requirement ({motor_hp:.2f} hp). "
            f"Verify motor selection or consider a smaller standard frame."
        )

    return w


# ── Improvement 7 — Calculation audit log ──────────────────────────────────────
#
# Every POST /calculate is persisted to calc_audit for:
#   • Project traceability (who ran what, when)
#   • Regression testing (replay a hash, compare results across versions)
#   • Debugging (compare inputs_json to what the solver actually received)
#
# _audit_calc opens its own SQLite connection because the request-scoped `db`
# dependency may already be closed when the background task runs.
# BackgroundTasks.add_task() means this write never delays the HTTP response.

def _init_audit_table() -> None:
    """Create calc_audit if absent.  Called once during lifespan startup."""
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS calc_audit (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            input_hash    TEXT    NOT NULL,
            module        TEXT    NOT NULL,
            schema_ver    TEXT    NOT NULL,
            inputs_json   TEXT,
            results_json  TEXT,
            warnings_json TEXT,
            created_at    TEXT    NOT NULL
        )
    """)
    con.commit()
    con.close()


def _init_versions_table() -> None:
    """Create design_versions table for revision history.  Called at startup."""
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS design_versions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            design_id       TEXT    NOT NULL,
            version         INTEGER NOT NULL,
            module          TEXT    NOT NULL,
            name            TEXT    NOT NULL,
            inputs_json     TEXT,
            results_json    TEXT,
            notes           TEXT,
            calc_schema_ver TEXT,
            saved_at        TEXT    NOT NULL
        )
    """)
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_dv_design_id ON design_versions (design_id)"
    )
    con.commit()
    con.close()


def _audit_calc(
    module:     str,
    inp_dict:   dict,
    results:    Any,
    warnings:   list[str],
    input_hash: str,
) -> None:
    con = sqlite3.connect(_DB_PATH)
    try:
        con.execute("""
            INSERT INTO calc_audit
                (input_hash, module, schema_ver,
                 inputs_json, results_json, warnings_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            input_hash,
            module,
            CALC_SCHEMA_VERSION,
            json.dumps(inp_dict,  default=str),
            json.dumps(results,   default=str),
            json.dumps(warnings),
            datetime.now(timezone.utc).isoformat(),
        ))
        con.commit()
    finally:
        con.close()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _init_audit_table()        # create audit table alongside designs table
    _init_versions_table()     # create design revision history table
    yield


# ── Improvement 8 — CORS (origins list + optional regex) ──────────────────────
#
# VECTRIX_CORS_ORIGINS  — comma-separated explicit origins (existing behaviour)
# VECTRIX_CORS_REGEX    — Python regex for internal wildcard sub-domains, e.g.
#                         r"https://.*\.akshayvipra\.internal"
#
# Both are additive; neither is required in development (localhost fallback).

_cors_env = os.getenv("VECTRIX_CORS_ORIGINS", "")
CORS_ORIGINS: list[str] = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else ["http://localhost:3000", "http://localhost:5173"]
)
CORS_ORIGIN_REGEX: str | None = os.getenv("VECTRIX_CORS_REGEX") or None


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="VECTRIX™ Design Platform API",
    description="AKSHAYVIPRA EL-MEC — VECTOMEC™ Bucket Elevator & Conveyor Design",
    version=CALC_SCHEMA_VERSION,
    lifespan=lifespan,
)

_cors_kw: dict[str, Any] = dict(
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if CORS_ORIGIN_REGEX:
    _cors_kw["allow_origin_regex"] = CORS_ORIGIN_REGEX

app.add_middleware(CORSMiddleware, **_cors_kw)


# ── Improvement 5 — Versioned router ───────────────────────────────────────────
#
# All new routes live under /api/v1.
# The compat block at the bottom re-registers every route at /api/* with
# include_in_schema=False so existing frontends keep working without appearing
# in OpenAPI docs.  Remove the compat block when the frontend is updated.

v1 = APIRouter(prefix="/api/v1")


# ── Improvement 6 — Reference data (cached) ────────────────────────────────────
#
# MATERIALS, BUCKET_SERIES, MOTOR_SIZES are module-level constants in
# calculations.py.  Wrapping them in lru_cache(maxsize=1) avoids rebuilding
# the response dict on every GET — cheap but eliminates any repeated allocation.

@lru_cache(maxsize=1)
def _materials_payload():     return {"materials":     MATERIALS}

@lru_cache(maxsize=1)
def _bucket_series_payload(): return {"bucket_series": BUCKET_SERIES}

@lru_cache(maxsize=1)
def _motor_sizes_payload():   return {"motor_sizes":   MOTOR_SIZES}


@v1.get("/materials")
def get_materials():     return _materials_payload()


@v1.get("/materials/search")
def search_materials_api(
    q:        str = "",
    category: str = "",
    app:      str = "",   # no filter: all modules searchable
    limit:    int = 40,
):
    """
    Live material search for the frontend dropdown.
    Returns compact rows: {mat_id, name, category, rho_loose, abr_code, flowability}.

    Query params
    ────────────
    q         Partial name match (case-insensitive, empty = all)
    category  Filter by category code (e.g. GRAIN, MIN, CHEM) — empty = all
    app       Module tag filter: "be" (bucket elevator), "sc" (screw), "" (all)
    limit     Max results (default 40, max 200)
    """
    try:
        from .materials_lookup import search_materials
    except ImportError:
        from materials_lookup import search_materials
    return search_materials(
        query    = q,
        category = category,
        app      = app,
        limit    = min(int(limit), 200),
    )


@v1.get("/materials/categories")
def list_material_categories(app: str = "be"):
    """
    Return sorted distinct category codes for the given module.
    Used to populate category filter chips in the material search UI.
    """
    try:
        from .materials_lookup import list_categories
    except ImportError:
        from materials_lookup import list_categories
    return {"categories": list_categories(app=app)}


@v1.get("/materials/{mat_id}")
def get_material_by_id(mat_id: str):
    """Return a single material dict by its slug ID (e.g. 'wheat')."""
    try:
        from .materials_lookup import get_material
    except ImportError:
        from materials_lookup import get_material
    mat = get_material(mat_id)
    if not mat or mat.get("_source") == "fallback":
        raise HTTPException(status_code=404, detail=f"Material '{mat_id}' not found")
    return mat

@v1.get("/bucket-series")
def get_bucket_series(): return _bucket_series_payload()

@v1.get("/motor-sizes")
def get_motor_sizes():   return _motor_sizes_payload()


# ── Components ────────────────────────────────────────────────────────────────
# Query the component catalogue tables (bearings, gearboxes, motors, drives)
# with constraint-based filtering so the frontend only shows options that are
# adequate for the calculated design — e.g. bearings with bore ≥ shaft d_mm.
# All four endpoints use Depends(get_db) for the same SQLite connection that
# serves design records.

@v1.get("/components/motors")
def list_motors(
    pkw_min: float = 0.0,
    pkw_max: float = 9999.0,
    db: sqlite3.Connection = Depends(get_db),
):
    """Standard IEC motors filtered by power range [kW], ordered smallest first."""
    rows = db.execute(
        "SELECT * FROM motors WHERE Pkw >= ? AND Pkw <= ? ORDER BY Pkw",
        (pkw_min, pkw_max),
    ).fetchall()
    return {"motors": [dict(r) for r in rows], "count": len(rows)}


@v1.get("/components/gearboxes")
def list_gearboxes(
    torque_min: float = 0.0,
    ratio_min:  float = 0.0,
    ratio_max:  float = 9999.0,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Shaft-mount gearboxes where:
      Tn  ≥ torque_min   [Nm]  — rated output torque covers required torque
      ratio range overlaps [ratio_min, ratio_max]
    Ordered by Tn ascending (smallest adequate first).
    """
    rows = db.execute(
        """SELECT * FROM gearboxes
           WHERE Tn >= ?
             AND ratio_max >= ?
             AND ratio_min <= ?
           ORDER BY Tn""",
        (torque_min, ratio_min, ratio_max),
    ).fetchall()
    return {"gearboxes": [dict(r) for r in rows], "count": len(rows)}


@v1.get("/components/bearings")
def list_bearings(
    bore_min: float = 0.0,
    bore_max: float = 9999.0,
    role:     str   = "",
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Pillow-block bearings filtered by bore range [mm] and optional role tag.
    role="" returns all; role="head" filters to head-shaft pillow blocks.
    Ordered by bore ASC, basic dynamic load C DESC (best life first).
    """
    if role:
        rows = db.execute(
            """SELECT * FROM bearings
               WHERE bore >= ? AND bore <= ? AND role LIKE ?
               ORDER BY bore, C DESC""",
            (bore_min, bore_max, f"%{role}%"),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT * FROM bearings
               WHERE bore >= ? AND bore <= ?
               ORDER BY bore, C DESC""",
            (bore_min, bore_max),
        ).fetchall()
    return {"bearings": [dict(r) for r in rows], "count": len(rows)}


@v1.get("/components/drives")
def list_drives(
    pkw_min: float = 0.0,
    db: sqlite3.Connection = Depends(get_db),
):
    """Drive/starter units where rated power ≥ pkw_min [kW], ordered smallest first."""
    rows = db.execute(
        "SELECT * FROM drives WHERE Pkw_max >= ? ORDER BY Pkw_max",
        (pkw_min,),
    ).fetchall()
    return {"drives": [dict(r) for r in rows], "count": len(rows)}

@v1.post("/bucket-elevator/calculate", response_model=CalcResponse)
def calculate(
    inp:              BucketElevatorInput,
    background_tasks: BackgroundTasks,
    db:               sqlite3.Connection = Depends(get_db),
):
    """
    Full CEMA 375-2017 bucket elevator design calculation.

    Returns CalcResponse{meta, data, warnings}.
    warnings is a list of non-fatal engineering advisory notes;
    an empty list means all CEMA checks passed cleanly.
    """
    inp_dict = inp.model_dump()
    meta     = _solver_meta(inp_dict)

    try:
        results = solve_elevator(inp)
    except ValueError as e:
        # ValueError is the convention for domain validation failures
        # in the calculation layer (e.g. negative height, zero capacity).
        _err("VALIDATION_ERROR", str(e))
    except Exception as e:
        _tb = _traceback.format_exc()
        # ── Print to uvicorn terminal — visible without opening Network tab ──
        print(f"\n{'='*64}\nSOLVER 500 — full traceback\n{_tb}{'='*64}\n", flush=True)
        _err("SOLVER_ERROR", "Internal calculation error — see server log for details.", status=500)

    warnings = _collect_warnings(inp, results)

    # Audit write deferred — never delays the response.
    background_tasks.add_task(
        _audit_calc,
        "bucket_elevator", inp_dict, results, warnings, meta["input_hash"],
    )

    return CalcResponse(meta=meta, data=results, warnings=warnings)


@v1.post("/bucket-elevator/optimize", response_model=CalcResponse)
def optimize(req: OptimizerRequest):
    """Grid-search optimizer over RPM × Bucket × Fill space."""
    meta = _solver_meta()
    try:
        candidates = run_optimizer(req)
    except Exception as e:
        _err("OPTIMIZER_ERROR", str(e))

    return CalcResponse(
        meta=meta,
        data={"candidates": candidates, "count": len(candidates)},
    )


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    results: dict
    inputs:  dict
    project: str | None = ""
    ref:     str | None = ""


@v1.post("/bucket-elevator/report")
def generate_report(data: ReportRequest):
    """Generate A4 portrait PDF engineering report."""
    try:
        pdf = build_report(
            data.results, data.inputs,
            project=data.project or "",
            doc_ref=data.ref or "",
        )
    except Exception as e:
        _err("REPORT_ERROR", str(e), status=500)

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="elevator_report.pdf"'},
    )


class VariantReportRequest(BaseModel):
    candidates: list
    inputs:     dict
    project:    str | None = ""
    ref:        str | None = ""


@v1.post("/bucket-elevator/report-variants")
def generate_variant_report(data: VariantReportRequest):
    """Generate A4 PDF comparing multiple optimizer candidate variants."""
    try:
        pdf = build_variant_report(
            data.candidates, data.inputs,
            project=data.project or "",
            doc_ref=data.ref or "",
        )
    except Exception as e:
        _err("REPORT_ERROR", str(e), status=500)

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="elevator_variants.pdf"'},
    )


# ── Designs ───────────────────────────────────────────────────────────────────

@v1.post("/designs/save")
def save_design(record: DesignRecord, db: sqlite3.Connection = Depends(get_db)):
    """
    Persist a named design to SQLite.

    Improvement 9: calc_schema_version is stored alongside the record.
    When solve_elevator() equations change in a future release, old designs
    remain queryable — you can filter by schema_ver to identify which records
    need recalculation or migration.
    """
    now = datetime.now(timezone.utc).isoformat()
    cur = db.cursor()

    # Upsert current design record (unchanged — frontend always loads latest)
    cur.execute("""
        INSERT OR REPLACE INTO designs
            (id, module, name, project, inputs_json, results_json,
             notes, calc_schema_version, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.id, record.module, record.name, record.project,
        record.inputs_json, record.results_json, record.notes,
        CALC_SCHEMA_VERSION,
        record.created_at or now, now,
    ))

    # Append to design_versions — one row per save, never overwritten
    # Version number = max existing version for this design_id + 1
    ver_row = cur.execute(
        "SELECT COALESCE(MAX(version),0) FROM design_versions WHERE design_id = ?",
        (record.id,)
    ).fetchone()
    next_ver = (ver_row[0] if ver_row else 0) + 1

    cur.execute("""
        INSERT INTO design_versions
            (design_id, version, module, name,
             inputs_json, results_json, notes, calc_schema_ver, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.id, next_ver, record.module, record.name,
        record.inputs_json, record.results_json, record.notes,
        CALC_SCHEMA_VERSION, now,
    ))

    db.commit()
    return {
        "saved":              True,
        "id":                 record.id,
        "version":            next_ver,
        "calc_schema_version": CALC_SCHEMA_VERSION,
    }


@v1.get("/designs")
def list_designs(
    module:  str | None = None,
    project: str | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    cur   = db.cursor()
    query = (
        "SELECT id, module, name, project, notes, "
        "calc_schema_version, created_at, updated_at "
        "FROM designs WHERE 1=1"
    )
    params: list = []
    if module:
        query += " AND module = ?";  params.append(module)
    if project:
        query += " AND project = ?"; params.append(project)
    query += " ORDER BY updated_at DESC"
    return {"designs": [dict(r) for r in cur.execute(query, params).fetchall()]}


@v1.get("/designs/{design_id}")
def get_design(design_id: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.cursor().execute(
        "SELECT * FROM designs WHERE id = ?", (design_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Design not found")
    return dict(row)


@v1.get("/designs/{design_id}/versions")
def list_design_versions(
    design_id: str,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Return all saved revisions for a design in reverse-chronological order.

    Each revision contains: version number, inputs_json, results_json,
    calc_schema_ver, and saved_at timestamp.  The frontend can use this to
    implement a "restore revision" workflow (load older inputs_json and re-run).
    """
    rows = db.cursor().execute(
        "SELECT version, name, notes, calc_schema_ver, saved_at "
        "FROM design_versions WHERE design_id = ? ORDER BY version DESC",
        (design_id,),
    ).fetchall()
    return {"design_id": design_id, "versions": [dict(r) for r in rows]}


@v1.get("/designs/{design_id}/versions/{version}")
def get_design_version(
    design_id: str,
    version:   int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Return full inputs_json + results_json for a specific revision."""
    row = db.cursor().execute(
        "SELECT * FROM design_versions WHERE design_id = ? AND version = ?",
        (design_id, version),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    return dict(row)


@v1.delete("/designs/{design_id}")
def delete_design(design_id: str, db: sqlite3.Connection = Depends(get_db)):
    db.cursor().execute("DELETE FROM designs WHERE id = ?", (design_id,))
    db.cursor().execute("DELETE FROM design_versions WHERE design_id = ?", (design_id,))
    db.commit()
    return {"deleted": True, "id": design_id}


# ── Projects ──────────────────────────────────────────────────────────────────

@v1.get("/projects")
def list_projects(db: sqlite3.Connection = Depends(get_db)):
    rows = db.cursor().execute(
        "SELECT DISTINCT project FROM designs "
        "WHERE project IS NOT NULL ORDER BY project"
    ).fetchall()
    return {"projects": [r["project"] for r in rows]}


# ── Design comparison ────────────────────────────────────────────────────────


class CompareRequest(BaseModel):
    """Two designs to compare side-by-side."""
    base:      BucketElevatorInput
    candidate: BucketElevatorInput
    labels:    list[str] = Field(
        default_factory=list,
        description="Optional display labels: ['Current design', 'Proposed design']",
    )


@v1.post("/calculate/compare")
def compare_designs(req: CompareRequest, bg: BackgroundTasks):
    """
    Run two BucketElevatorInput designs through solve_elevator() and return a
    structured side-by-side comparison.  Useful for:
      - Evaluating a proposed change (wider pulley, different bucket series)
      - Variant selection during preliminary design
      - Before / after documentation for engineering change notes

    Returns a delta dict for every numeric KPI so the frontend can render
    colour-coded improvement / regression indicators.
    """
    try:
        r_base = solve_elevator(req.base)
        r_cand = solve_elevator(req.candidate)
    except Exception as e:
        _err("COMPARE_ERROR", f"Solver error during comparison: {e}", status=500)

    labels = (req.labels + ["Base", "Candidate"])[:2]

    # KPIs to compare — (key, label, unit, lower_is_better)
    KPI_DEFS = [
        ("Q",            "Capacity",         "t/h",  False),
        ("v",            "Belt speed",        "m/s",  None),
        ("cr",           "Centrifugal ratio", "—",    None),
        ("P_total",      "Total power",       "kW",   True),
        ("motor_kw",     "Motor size",        "kW",   True),
        ("L10",          "Bearing L10",       "h",    False),
        ("d_mm",         "Shaft diameter",    "mm",   None),
        ("T3",           "Take-up tension",   "N",    True),
        ("R_headshaft",  "Headshaft load",    "N",    True),
        ("recommended_fill_pct", "Rec. fill", "%",    None),
    ]

    kpi_rows = []
    for key, label, unit, lower_better in KPI_DEFS:
        v_b = r_base.get(key)
        v_c = r_cand.get(key)
        if v_b is None and v_c is None:
            continue
        try:
            f_b = float(v_b) if v_b is not None else None
            f_c = float(v_c) if v_c is not None else None
            if f_b is not None and f_c is not None and f_b != 0:
                delta_pct = round((f_c - f_b) / abs(f_b) * 100, 1)
                if lower_better is True:
                    direction = "better" if delta_pct < 0 else "worse"
                elif lower_better is False:
                    direction = "better" if delta_pct > 0 else "worse"
                else:
                    direction = "neutral"
            else:
                delta_pct = None
                direction = "neutral"
        except (TypeError, ValueError):
            f_b = f_c = delta_pct = None
            direction = "neutral"
        kpi_rows.append({
            "key":       key,
            "label":     label,
            "unit":      unit,
            "base":      round(f_b, 3) if f_b is not None else None,
            "candidate": round(f_c, 3) if f_c is not None else None,
            "delta_pct": delta_pct,
            "direction": direction,
        })

    # Check-level summary
    def _check_summary(r: dict) -> dict:
        chks = r.get("checks", [])
        return {
            "pass": sum(1 for c in chks if c["type"] == "ok"),
            "warn": sum(1 for c in chks if c["type"] == "warn"),
            "fail": sum(1 for c in chks if c["type"] == "fail"),
            "info": sum(1 for c in chks if c["type"] == "info"),
        }

    now = datetime.now(timezone.utc).isoformat()
    return {
        "meta": {
            "solver_version": CALC_SCHEMA_VERSION,
            "timestamp":      now,
            "labels":         labels,
        },
        "kpis":    kpi_rows,
        "checks": {
            labels[0]: _check_summary(r_base),
            labels[1]: _check_summary(r_cand),
        },
        "full": {
            labels[0]: r_base,
            labels[1]: r_cand,
        },
    }


# ── Health ────────────────────────────────────────────────────────────────────

@v1.get("/health")
def health():
    import os as _os
    _db_ok = False
    try:
        import sqlite3 as _sq
        _conn = _sq.connect(_DB_PATH, timeout=2)
        _conn.execute("SELECT 1")
        _conn.close()
        _db_ok = True
    except Exception:
        pass
    return {
        "status":               "ok" if _db_ok else "degraded",
        "product":              "VECTRIX™",
        "solver_version":       CALC_SCHEMA_VERSION,
        "calc_schema_version":  CALC_SCHEMA_VERSION,
        "cema_reference":       CEMA_STANDARD,
        "database_connected":   _db_ok,
        "database_file":        _os.path.basename(_DB_PATH),
        "cors_origins":         CORS_ORIGINS,
        "timestamp":            datetime.now(timezone.utc).isoformat(),
    }


# ── Register versioned router ─────────────────────────────────────────────────

app.include_router(v1)


# ── Backward-compat /api/* aliases ────────────────────────────────────────────
#
# IMPORTANT — why calculate/optimize are NOT in add_api_route here:
#
#   The v1 calculate() and optimize() functions return CalcResponse{meta, data,
#   warnings}.  Wiring them via add_api_route would expose the envelope at the
#   old /api/* paths too, breaking any frontend that reads response.speed_sweep,
#   response.motor_hp, etc. directly.
#
#   The two explicit wrappers below call the v1 functions and strip .data,
#   restoring the original flat-dict response the frontend expects.
#
#   All other endpoints (reference data, reports, designs, health) do not wrap
#   results in an envelope, so they are safe to alias directly.
#
#   Remove this entire block once the frontend has been updated to /api/v1/*.

_compat = APIRouter(prefix="/api", tags=["deprecated — migrate to /api/v1"])
_R: dict[str, Any] = {"include_in_schema": False}   # typed Any — Pylance needs this for **_R spread

_compat.add_api_route("/materials",                       get_materials,           methods=["GET"],    **_R)
_compat.add_api_route("/bucket-series",                   get_bucket_series,       methods=["GET"],    **_R)
_compat.add_api_route("/motor-sizes",                     get_motor_sizes,         methods=["GET"],    **_R)
_compat.add_api_route("/components/motors",               list_motors,             methods=["GET"],    **_R)
_compat.add_api_route("/components/gearboxes",            list_gearboxes,          methods=["GET"],    **_R)
_compat.add_api_route("/components/bearings",             list_bearings,           methods=["GET"],    **_R)
_compat.add_api_route("/components/drives",               list_drives,             methods=["GET"],    **_R)
_compat.add_api_route("/bucket-elevator/report",          generate_report,         methods=["POST"],   **_R)
_compat.add_api_route("/bucket-elevator/report-variants", generate_variant_report, methods=["POST"],   **_R)
_compat.add_api_route("/designs/save",                    save_design,             methods=["POST"],   **_R)
_compat.add_api_route("/designs",                         list_designs,            methods=["GET"],    **_R)
_compat.add_api_route("/designs/{design_id}",             get_design,              methods=["GET"],    **_R)
_compat.add_api_route("/designs/{design_id}",             delete_design,           methods=["DELETE"], **_R)
_compat.add_api_route("/projects",                        list_projects,           methods=["GET"],    **_R)
_compat.add_api_route("/health",                          health,                  methods=["GET"],    **_R)

app.include_router(_compat)


# ── Compat wrappers for enveloped endpoints ───────────────────────────────────
#
# calculate() → CalcResponse.data is the raw solve_elevator() dict:
#   {"speed_sweep": [...], "motor_hp": ..., "belt_speed_fpm": ..., ...}
#
# optimize()  → CalcResponse.data is {"candidates": [...], "count": N}
#
# Stripping .data here gives the frontend exactly what it received from v1.0.0.
# These are registered on `app` directly (not _compat) because add_api_route
# does not preserve the CalcResponse → dict unwrapping we need.

@app.post("/api/bucket-elevator/calculate", include_in_schema=False)
def _compat_calculate(
    inp:              BucketElevatorInput,
    background_tasks: BackgroundTasks,
    db:               sqlite3.Connection = Depends(get_db),
):
    """Compat shim — returns raw solver dict, not CalcResponse envelope."""
    return calculate(inp, background_tasks, db).data


@app.post("/api/bucket-elevator/optimize", include_in_schema=False)
def _compat_optimize(req: OptimizerRequest):
    """Compat shim — returns {candidates, count}, not CalcResponse envelope."""
    return optimize(req).data