"""
VECTRIX™ Materials Lookup — materials_lookup.py
─────────────────────────────────────────────────────────────────────────────
Drop-in replacement for the static materials.py MATERIALS list.

The bucket elevator engine (calculations.py) calls:
    from materials import get_material, MATERIALS
    mat = get_material(mat_id)

This module satisfies that interface using vectrix.db instead of a
hard-coded Python list.  The static list is still used as a FALLBACK
if the database file is not found, so the engine never goes offline.

Usage
─────────────────────────────────────────────────────────────────────────────
In calculations.py, change ONE import line:

  # OLD
  from materials import get_material, MATERIALS

  # NEW
  from materials_lookup import get_material, MATERIALS

No other changes required — the returned dict shape is identical.

DB path resolution order
─────────────────────────────────────────────────────────────────────────────
1. VECTRIX_DB env var (e.g. "sqlite:////data/vectrix.db")
2. ./vectrix.db (same directory as this file)
3. ../vectrix.db (one level up, for package structure)
4. ./screw_conveyor.db (backward compat — legacy SC DB)
5. Static materials.py MATERIALS list (final fallback, no DB required)
"""

from __future__ import annotations
import json
import os
import sqlite3
from functools import lru_cache
from typing import Any

# ─── DB path resolution ───────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

def _find_db() -> str | None:
    """Return the first database file that exists, or None."""
    env = os.getenv("VECTRIX_DB_URL", "")
    if env.startswith("sqlite:///"):
        p = env.replace("sqlite:///", "").replace("sqlite://", "")
        if os.path.exists(p):
            return p

    candidates = [
        os.path.join(_HERE, "vectrix.db"),
        os.path.join(_HERE, "..", "vectrix.db"),
        os.path.join(_HERE, "screw_conveyor.db"),   # legacy fallback
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


_DB_PATH = _find_db()


# ─── Row → BE material dict conversion ───────────────────────────────────────

def _row_to_be(row: dict) -> dict:
    """
    Convert a vectrix.db materials row to the BE engine dict format.
    The shape matches what materials.py returned so callers need no changes.
    """
    # Parse hazard_codes — stored as comma-separated string
    haz_raw = row.get("hazard_codes") or ""
    hazard_codes = [h.strip() for h in haz_raw.split(",") if h.strip()]

    return {
        # Identity
        "id":                   row.get("mat_id") or "",
        "name":                 row.get("name") or "",
        "category":             row.get("category") or "",

        # Density [kg/m³]
        "rho_loose":            float(row["rho_bulk"] or 500),
        "rho_vib":              float(row["rho_vib"] or 0) or None,

        # Abrasiveness
        "abr_code":             int(row["abr_code"] or 3),

        # Flowability (1=Very free, 2=Free, 3=Average, 4=Sluggish)
        "flowability":          int(row["flowability"] or 2),

        # Moisture
        "moisture_pct":         float(row["moisture_pct"] or 0),

        # Particle / friction
        "size_code":            row.get("size_code") or row.get("particle_class") or "",
        "particle_size_mm":     float(row["particle_size_mm"] or 0) if row.get("particle_size_mm") else None,
        "wall_friction_deg":    float(row["wall_friction_deg"] or 20) if row.get("wall_friction_deg") else 20.0,
        "angle_repose":         float(row["angle_repose"] or 35) if row.get("angle_repose") else 35.0,
        "angle_surcharge":      float(row["angle_surcharge"] or 0) if row.get("angle_surcharge") else None,
        "angle_internal_friction": float(row["angle_internal_friction"] or 0) if row.get("angle_internal_friction") else None,
        "cohesion":             float(row["cohesion"] or 0),

        # CEMA 375 BE power method
        "Leq_default":          float(row["Leq_default"] or 8) if row.get("Leq_default") else 8.0,
        "Ceff_default":         float(row["Ceff_default"] or 1.20) if row.get("Ceff_default") else 1.20,
        "Km":                   float(row["Km"] or 0.4) if row.get("Km") else 0.4,

        # VECTRIX internal
        "vfi":                  int(row["vfi"] or 3) if row.get("vfi") else 3,
        "bucket_fill_factor":   float(row["bucket_fill_factor"] or 0.75) if row.get("bucket_fill_factor") else 0.75,
        "stream_spread_factor": float(row["stream_spread_factor"] or 1.0) if row.get("stream_spread_factor") else 1.0,

        # Hazards
        "hazard_codes":         hazard_codes,

        # SC-sourced extras (available when material also has SC data)
        "lambda_ref":           float(row["lambda_ref"]) if row.get("lambda_ref") else None,
        "fill_max_sc":          float(row["fill_max"])   if row.get("fill_max")    else None,
        "cema_cls_sc":          row.get("cema_cls"),
        "cema_code":            row.get("cema_code"),
        "flow_regime":          row.get("flow_regime"),
        "bridging_risk":        float(row["bridging_risk"]) if row.get("bridging_risk") else None,
        "temp_max":             float(row["temp_max"]) if row.get("temp_max") else None,

        # App tags
        "_app":                 json.loads(row["app"]) if row.get("app") else [],
        "_source":              row.get("source") or "db",
    }


# ─── Low-level DB access ──────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_connection():
    """Cached read-only SQLite connection."""
    if not _DB_PATH:
        return None
    con = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True,
                          check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _query_one(where_clause: str, params: tuple) -> dict | None:
    con = _get_connection()
    if con is None:
        return None
    try:
        row = con.execute(
            f"SELECT * FROM materials WHERE {where_clause}", params
        ).fetchone()
        return _row_to_be(dict(row)) if row else None
    except Exception:
        return None


def _query_all(app_filter: str = "be") -> list[dict]:
    """Return all materials available to the given app module."""
    con = _get_connection()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT * FROM materials WHERE app LIKE ?",
            (f"%{app_filter}%",)
        ).fetchall()
        return [_row_to_be(dict(r)) for r in rows]
    except Exception:
        return []


# ─── Public API — matches materials.py interface exactly ──────────────────────

def get_material(mat_id: str) -> dict:
    """
    Return a BE material dict by mat_id slug (e.g. "wheat", "cement").
    Falls back to name search, then to static materials.py if DB unavailable.
    """
    # Try DB first — by mat_id slug
    result = _query_one("mat_id = ?", (mat_id,))

    # Fallback: search by name (case-insensitive)
    if result is None:
        result = _query_one("name = ? COLLATE NOCASE", (mat_id,))

    # Fallback: DB unavailable or mat not found — use static list
    if result is None:
        result = _get_static_material(mat_id)

    # Hard fallback: unknown material — return safe defaults
    if result is None:
        result = _unknown_material(mat_id)

    return result


def search_materials(
    query: str = "",
    category: str = "",
    app: str = "be",
    limit: int = 50,
) -> list[dict]:
    """
    Search materials by name/category for the frontend search dropdown.

    Parameters
    ----------
    query    : partial name match (case-insensitive)
    category : filter by category code (e.g. "GRAIN")
    app      : module filter ("be", "sc", or "" for all)
    limit    : max results

    Returns list of compact dicts: {mat_id, name, category, rho_loose, abr_code, flowability}
    """
    con = _get_connection()
    if con is None:
        # Fallback: search static list
        return _search_static(query, category, limit)

    filters = ["1=1"]
    params: list[Any] = []

    if app:
        filters.append("app LIKE ?")
        params.append(f"%{app}%")
    if query:
        filters.append("name LIKE ?")
        params.append(f"%{query}%")
    if category:
        filters.append("category = ?")
        params.append(category)

    sql = (
        f"SELECT mat_id, name, category, rho_bulk, abr_code, flowability "
        f"FROM materials WHERE {' AND '.join(filters)} "
        f"ORDER BY name LIMIT ?"
    )
    params.append(limit)

    try:
        rows = con.execute(sql, params).fetchall()
        return [
            {
                "mat_id":     r["mat_id"],
                "name":       r["name"],
                "category":   r["category"],
                "rho_loose":  r["rho_bulk"],
                "abr_code":   r["abr_code"],
                "flowability": r["flowability"],
            }
            for r in rows
        ]
    except Exception:
        return _search_static(query, category, limit)


def list_categories(app: str = "be") -> list[str]:
    """Return sorted list of distinct category codes for the given app module."""
    con = _get_connection()
    if con is None:
        return sorted({m.get("category","") for m in _STATIC_LIST})
    try:
        rows = con.execute(
            "SELECT DISTINCT category FROM materials WHERE app LIKE ? ORDER BY category",
            (f"%{app}%",)
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []


def get_bearing(name: str) -> dict | None:
    """Look up a bearing by designation (e.g. 'SY60TF')."""
    con = _get_connection()
    if con is None:
        return None
    row = con.execute("SELECT * FROM bearings WHERE name = ? COLLATE NOCASE",
                      (name,)).fetchone()
    return dict(row) if row else None


def get_gearbox(model: str) -> dict | None:
    """Look up a gearbox by model string."""
    con = _get_connection()
    if con is None:
        return None
    row = con.execute("SELECT * FROM gearboxes WHERE model = ? COLLATE NOCASE",
                      (model,)).fetchone()
    return dict(row) if row else None


def materials_by_category(category: str, app: str = "be") -> list[dict]:
    """
    Return all materials in a given category code (e.g. "GRAIN", "MIN").
    Filters by app module tag as well.
    """
    con = _get_connection()
    if con is None:
        return [m for m in _STATIC_LIST
                if m.get("category") == category]
    try:
        rows = con.execute(
            "SELECT * FROM materials WHERE category = ? AND app LIKE ? ORDER BY name",
            (category, f"%{app}%")
        ).fetchall()
        return [_row_to_be(dict(r)) for r in rows]
    except Exception:
        return [m for m in _STATIC_LIST if m.get("category") == category]


def material_count(app: str = "be") -> int:
    """Return total number of materials available for a given app module."""
    con = _get_connection()
    if con is None:
        return len(_STATIC_LIST)
    try:
        return con.execute(
            "SELECT count(*) FROM materials WHERE app LIKE ?",
            (f"%{app}%",)
        ).fetchone()[0]
    except Exception:
        return len(_STATIC_LIST)
    """Return bearings matching a given shaft bore with optional tolerance."""
    con = _get_connection()
    if con is None:
        return []
    rows = con.execute(
        "SELECT * FROM bearings WHERE bore BETWEEN ? AND ? ORDER BY bore, C DESC",
        (bore_mm - tolerance_mm, bore_mm + tolerance_mm)
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Backward-compatible MATERIALS list ───────────────────────────────────────
# Populated lazily on first access.  Used by any code that does:
#   for mat in MATERIALS: ...

class _LazyMaterials(list):
    """A list that loads from DB on first access."""
    _loaded = False

    def _load(self):
        if not self._loaded:
            data = _query_all("be") or _STATIC_LIST
            self.extend(data)
            self._loaded = True

    def __iter__(self):
        self._load()
        return super().__iter__()

    def __len__(self):
        self._load()
        return super().__len__()

    def __getitem__(self, idx):
        self._load()
        return super().__getitem__(idx)


MATERIALS = _LazyMaterials()


# ─── Static fallback ──────────────────────────────────────────────────────────
# Populated from the original materials.py if it can be imported.

_STATIC_LIST: list[dict] = []
_STATIC_BY_ID: dict[str, dict] = {}

try:
    import importlib.util, types as _types
    _spec = importlib.util.spec_from_file_location(
        "_mat_static",
        os.path.join(_HERE, "materials.py"),
    )
    if _spec:
        _m = _types.ModuleType("_mat_static")
        _spec.loader.exec_module(_m)  # type: ignore[union-attr]
        _STATIC_LIST = getattr(_m, "MATERIALS", [])
        _STATIC_BY_ID = {m["id"]: m for m in _STATIC_LIST if m.get("id")}
except Exception:
    pass


def _get_static_material(mat_id: str) -> dict | None:
    if mat_id in _STATIC_BY_ID:
        return _STATIC_BY_ID[mat_id]
    for m in _STATIC_LIST:
        if m.get("name", "").lower() == mat_id.lower():
            return m
    return None


def _search_static(query: str, category: str, limit: int) -> list[dict]:
    results = []
    for m in _STATIC_LIST:
        if category and m.get("category") != category:
            continue
        if query and query.lower() not in m.get("name", "").lower():
            continue
        results.append({
            "mat_id":    m.get("id", ""),
            "name":      m.get("name", ""),
            "category":  m.get("category", ""),
            "rho_loose": m.get("rho_loose", 0),
            "abr_code":  m.get("abr_code", 3),
            "flowability": m.get("flowability", 2),
        })
        if len(results) >= limit:
            break
    return results


def _unknown_material(mat_id: str) -> dict:
    """Safe defaults for an unknown material ID."""
    return {
        "id": mat_id, "name": mat_id, "category": "UNKNOWN",
        "rho_loose": 800, "rho_vib": None,
        "abr_code": 3, "flowability": 2,
        "moisture_pct": 0, "cohesion": 0,
        "size_code": "B6", "wall_friction_deg": 20.0,
        "angle_repose": 35.0, "angle_surcharge": None,
        "angle_internal_friction": None,
        "particle_size_mm": None,
        "Leq_default": 8.0, "Ceff_default": 1.20, "Km": 0.4,
        "vfi": 3, "bucket_fill_factor": 0.75, "stream_spread_factor": 1.0,
        "hazard_codes": [],
        "lambda_ref": None, "fill_max_sc": None, "cema_cls_sc": None,
        "cema_code": None, "flow_regime": None, "bridging_risk": None,
        "temp_max": None,
        "_app": [], "_source": "fallback",
    }


# ─── Quick self-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    db_status = f"DB: {_DB_PATH}" if _DB_PATH else "DB: NOT FOUND — using static fallback"
    print(db_status)
    w = get_material("wheat")
    print(f"wheat: rho_loose={w['rho_loose']} abr_code={w['abr_code']} "
          f"Leq={w['Leq_default']} flow={w['flowability']}")
    c = get_material("cement")
    print(f"cement: rho_loose={c['rho_loose']} abr_code={c['abr_code']} "
          f"lambda_ref={c.get('lambda_ref')} flow={c['flowability']}")
    print(f"Total in MATERIALS list: {len(MATERIALS)}")
    print(f"Sample search 'wheat': {search_materials('wheat', limit=3)}")