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