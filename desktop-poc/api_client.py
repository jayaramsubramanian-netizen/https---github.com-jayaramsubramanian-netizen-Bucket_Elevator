"""
api_client.py -- shared backend client, mirroring frontend/src/api/client.js.
═══════════════════════════════════════════════════════════════════════════
Every component fetches through here, not through its own copy of
requests.post(). One place to change the base URL, add auth headers, retry
logic, etc. later -- exactly the role client.js plays for the React app.
"""
import requests

API_BASE = "http://localhost:8000/api"
API_BASE_V1 = "http://localhost:8000/api/v1"   # MaterialSearchDropdown.jsx calls /api/v1 directly, not the /api compat shim


def fetch_design(payload: dict) -> dict:
    """POST to /bucket-elevator/calculate. Raises requests.HTTPError on a
    non-2xx response -- callers (the shell's run_calculation()) are
    responsible for catching this and showing it to the user, the same way
    useElevatorCalc.js surfaces `error` from a failed fetch."""
    resp = requests.post(f"{API_BASE}/bucket-elevator/calculate", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def search_materials(query: str = "", category: str = "", limit: int = 40) -> list:
    """Mirrors MaterialSearchDropdown.jsx's own search call."""
    params: dict[str, str | int] = {"limit": limit}
    if query:
        params["q"] = query
    if category:
        params["category"] = category
    resp = requests.get(f"{API_BASE_V1}/materials/search", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def list_material_categories() -> list:
    resp = requests.get(f"{API_BASE_V1}/materials/categories", timeout=15)
    resp.raise_for_status()
    return resp.json().get("categories", [])


def get_material(mat_id: str) -> dict | None:
    resp = requests.get(f"{API_BASE_V1}/materials/{mat_id}", timeout=15)
    if resp.status_code != 200:
        return None
    return resp.json()


def fetch_components(path: str, params: dict | None = None) -> list:
    """Mirrors ComponentPicker.jsx's own fetch: GET /api/v1{path}?{params},
    response is a dict with exactly one list-valued key (e.g.
    {"bearings": [...], "count": N}) -- find and return that list,
    same as the JSX's Object.values(data).find(v => Array.isArray(v))."""
    clean = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    resp = requests.get(f"{API_BASE_V1}{path}", params=clean, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    for v in data.values():
        if isinstance(v, list):
            return v
    return []

def optimize_elevator_v2(base_input: dict) -> dict:
    """POST to /bucket-elevator/optimize/v2 -- mirrors OptimizerPanel.jsx's
    optimizeElevatorV2(). Uses the /api compat path (not /api/v1), same as
    fetch_design() -- confirmed directly in main.py: the /api/v1 route
    returns the full CalcResponse{meta, data, warnings} envelope, while
    /api has a compat shim (_compat_optimize_v2) that strips .data, giving
    the bare {pareto_front, n_pareto_points, ...} dict this function
    returns, matching every other API client function in this file. A
    real NSGA-II run, confirmed directly to take ~3-30s depending on
    population/generation budget (backend default pop_size=200/n_gen=100,
    ~29s) -- timeout set well above the usual 15-30s used elsewhere in
    this file, since a premature client-side timeout here would abort a
    real in-progress optimization run, not just a slow request."""
    resp = requests.post(f"{API_BASE}/bucket-elevator/optimize/v2", json={"base_input": base_input}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def download_variant_report(candidates: list, inputs: dict, save_path: str) -> str:
    """POST to /bucket-elevator/report-variants and save the returned PDF
    to save_path. Mirrors OptimizerPanel.jsx's downloadVariantReport(),
    adapted for a desktop save-to-disk instead of a browser download."""
    resp = requests.post(
        f"{API_BASE}/bucket-elevator/report-variants",
        json={"candidates": candidates, "inputs": inputs},
        timeout=60,
    )
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    return save_path


# ── Materials Library CRUD ────────────────────────────────────────────────────
def fetch_all_materials() -> list:
    """GET /materials -- all built-in materials (full detail, not search-compressed).
    Confirmed response shape: {"materials": [400 items]}."""
    resp = requests.get(f"{API_BASE_V1}/materials", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("materials", [])


def list_custom_materials_api() -> list:
    """GET /materials/custom -- custom materials only."""
    resp = requests.get(f"{API_BASE_V1}/materials/custom", timeout=15)
    resp.raise_for_status()
    return resp.json().get("materials", [])


def create_custom_material(payload: dict) -> dict:
    """POST /materials/custom."""
    resp = requests.post(f"{API_BASE_V1}/materials/custom", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def update_custom_material(mat_id: str, payload: dict) -> dict:
    """PUT /materials/custom/{mat_id}."""
    resp = requests.put(f"{API_BASE_V1}/materials/custom/{mat_id}", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def delete_custom_material(mat_id: str) -> bool:
    """DELETE /materials/custom/{mat_id}. Returns True if deleted."""
    resp = requests.delete(f"{API_BASE_V1}/materials/custom/{mat_id}", timeout=15)
    resp.raise_for_status()
    return resp.json().get("deleted", True)


def download_pdf_report(results: dict, inputs: dict, save_path: str,
                         project: str = "", ref: str = "") -> str:
    """POST to /bucket-elevator/report and write the returned PDF to save_path."""
    resp = requests.post(
        f"{API_BASE_V1}/bucket-elevator/report",
        json={"results": results, "inputs": inputs, "project": project, "ref": ref},
        timeout=60,
    )
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    return save_path


def fetch_model_number(inputs: dict, results: dict) -> str:
    """POST to /model-number to get the canonical VM model number string.
    Falls back to a safe local derivation if the backend is unreachable."""
    try:
        resp = requests.post(
            f"{API_BASE_V1}/model-number",
            json={"inputs": inputs, "results": results},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("model_number", "VM-??-?-???/???")
    except Exception:
        # Minimal offline fallback using the same logic as the backend
        bkt = (results.get("bucket") or {})
        is_chain = results.get("is_chain") or (str(inputs.get("conveyor_type","")).lower() == "chain")
        drive = "C" if is_chain else "B"
        discharge = bkt.get("discharge_type", "centrifugal")
        abr = int((results.get("mat") or {}).get("abr_code") or 0)
        temp = float(inputs.get("material_temperature_c") or 20)
        w = int((results.get("belt_w") or inputs.get("belt_width_override_mm") or 305))
        d = int(inputs.get("D_mm") or 500)
        family = "MD" if (abr >= 5 or temp > 80) else ("KD" if discharge == "continuous" else "CD")
        suffix = "-".join(s for s in ["AR" if abr >= 5 else "", "HT" if temp > 80 else ""] if s)
        return f"VM-{family}-{drive}-{w}/{d}" + (f"-{suffix}" if suffix else "")