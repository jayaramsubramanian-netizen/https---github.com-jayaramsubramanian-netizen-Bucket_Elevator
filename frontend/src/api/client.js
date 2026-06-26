// VECTRIX™ — API Client
// All calls to FastAPI backend

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function req(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Reference Data ──────────────────────────────────────────────
export const fetchMaterials = () => req("GET", "/api/materials");
export const fetchBucketSeries = () => req("GET", "/api/bucket-series");
export const fetchMotorSizes = () => req("GET", "/api/motor-sizes");

// ─── Calculations ────────────────────────────────────────────────
export const calculateElevator = (inputs) =>
  req("POST", "/api/bucket-elevator/calculate", inputs);

export const optimizeElevator = (base_input, objective) =>
  req("POST", "/api/bucket-elevator/optimize", { base_input, objective });

// v2 — NSGA-II multi-objective optimizer (round 3+). Returns a genuine
// Pareto front (pareto_front[], material_preference, elapsed_s) instead of
// a single weighted-score ranked list. objective is accepted by the
// request schema for compat but unused server-side -- there is no single
// objective in a Pareto front by design.
export const optimizeElevatorV2 = (base_input) =>
  req("POST", "/api/bucket-elevator/optimize/v2", { base_input, objective: "balanced" });

// ─── Designs ─────────────────────────────────────────────────────
export const saveDesign = (record) => req("POST", "/api/designs/save", record);
export const listDesigns = (module, project) => {
  const params = new URLSearchParams();
  if (module) params.set("module", module);
  if (project) params.set("project", project);
  return req("GET", `/api/designs?${params}`);
};
export const getDesign = (id) => req("GET", `/api/designs/${id}`);
export const deleteDesign = (id) => req("DELETE", `/api/designs/${id}`);

// ─── Projects ────────────────────────────────────────────────────
export const listProjects = () => req("GET", "/api/projects");

// ─── Material Library (custom materials) ────────────────────────
// Uses /api/v1 directly (not the /api compat shim) -- matches the
// convention MaterialSearchDropdown.jsx already uses for materials
// search/lookup. Built-in materials have no PUT/DELETE here on purpose;
// they're immutable, only custom_materials rows are editable.
export const listCustomMaterials  = () => req("GET", "/api/v1/materials/custom");
export const getCustomMaterial    = (id) => req("GET", `/api/v1/materials/custom/${encodeURIComponent(id)}`);
export const createCustomMaterial = (data) => req("POST", "/api/v1/materials/custom", data);
export const updateCustomMaterial = (id, data) =>
  req("PUT", `/api/v1/materials/custom/${encodeURIComponent(id)}`, data);
export const deleteCustomMaterial = (id) =>
  req("DELETE", `/api/v1/materials/custom/${encodeURIComponent(id)}`);