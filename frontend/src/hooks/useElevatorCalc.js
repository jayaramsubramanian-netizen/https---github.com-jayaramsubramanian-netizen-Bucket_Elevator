// useElevatorCalc.js — manages input state, debounced API calls, save/load
// Your original architecture preserved exactly.
// Added: normaliseResult() maps any API response shape to the field contract
// that KpiGrid, ComponentPanel, and all display components expect.
//
// v1.1.0 — Three fixes
// ─────────────────────────────────────────────────────────────────
// FIX 1  Q and v missing from return object.
//        normaliseResult() renamed raw.Q → Q_th and raw.v → v_ms
//        but never wrote Q or v back. Nav bar, ElevatorSchematic,
//        and KpiGrid all read results.Q / results.v → always undefined
//        → always "—". P_total worked because it was in pass-throughs.
//        Fix: add  Q: Q_th  and  v: v_ms  to the return.
//
// FIX 2  Checks lost the `type` field after normalisation.
//        The check map returned {status, code, msg} — dropping `type`.
//        BucketElevatorPage reads c.type for fail/warn counts and for
//        the colour of the inline check strip. After normalisation
//        c.type === undefined so failCount was always 0 and the
//        danger/warning colours never appeared.
//        Fix: keep `type` in the normalised check object.
//
// FIX 3  New backend fields (Task 1 Euler, Task 3 power decomposition,
//        v1.2.x shaft geometry) were not in pass-throughs, so
//        ComponentPanel and generate_report.py couldn't read them.
//        Fix: add them to the pass-throughs section.
// ─────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback, useRef } from "react";
import { calculateElevator, saveDesign, getDesign } from "../api/client";
import { v4 as uuidv4 } from "uuid";

export const DEFAULT_INPUTS = {
  Q_req: 100,
  H_m: 25,
  mat_id: "wheat",
  custom_rho: 0,

  // ── v1.6.0 Custom material property overrides ──────────────────────────
  custom_mat_name:    "",   // display label (reports only)
  custom_aor:         0,    // angle of repose [°]   — 0 = use DB
  custom_abr:         0,    // abrasiveness code 1-7 — 0 = use DB
  custom_flowability: 0,    // flowability class 1-4 — 0 = use DB
  custom_moisture:   -1,    // moisture content [%]  — -1 = use DB
  custom_cohesion:   -1,    // cohesion index [kPa]  — -1 = use DB

  // ── v1.6.0 Boot pulley ──────────────────────────────────────────────────
  boot_pulley_same_as_head: false,
  D_mm: 500,
  n_rpm: 60,
  fill_pct: 75,
  bucket_gap: 25,
  auto_bucket: true,
  bucket_id: "B",
  mu: 0.35,
  wrap_deg: 180,
  sf: 1.25,
  // v1.3.0 — structural module inputs
  environment:      "dry",   // "dry" | "humid" | "wet" | "submerged"  (lagging selection)
  belt_type:        "EP",    // "EP" | "ST"  (lagging selection)
  wind_pressure_pa: 800,     // [Pa]  (casing panel check — typical industrial site)

  // ── v1.5.0 Design Overrides ─────────────────────────────────────
  // All 0 = auto-calculate from first principles. Set > 0 to specify.
  takeup_type:            "gravity",  // "gravity" | "screw" | "auto"
  takeup_screw_d_mm:      0,          // Screw core diameter override [mm]
  takeup_screw_len_m:     0,          // Screw shank length for buckling [m]
  shaft_d_override_mm:    0,          // Head shaft diameter override [mm]
  belt_width_override_mm: 0,          // Belt width override [mm]
  casing_t_override_mm:   0,          // Casing plate thickness override [mm]

  // ── v1.7.0 Component selector overrides ──────────────────────────
  // All empty / 0 = auto.  Set to lock a specific catalogue component.
  belt_grade:              "",        // "M" | "N" | "W" — belt cover grade
  motor_kw_override:       0,         // kW — lock to specific standard motor size
  gearbox_model:           "",        // model ID from gearboxes DB table
  bearing_name:            "",        // name from bearings DB table
  drive_model:             "",        // model ID from drives DB table
  discharge_type_override: "",        // "centrifugal" | "continuous" | "" (auto)

  // ── v1.8.0 Chain elevator ─────────────────────────────────────────────────
  conveyor_type:        "belt",       // "belt" | "chain"
  chain_series:         "",           // "" = auto; "S102B" | "S110" | "ER856" | "ER857" | "ER859"
  chain_n_strands:      1,            // 1 = single; 2 = SC double-chain
  chain_sprocket_teeth: 0,            // 0 = auto-compute from D_mm
  chain_sf:             6.0,          // safety factor (CEMA 375 default 6.0)

  // ── v1.8.0 Feed Design (2f) ────────────────────────────────────────────────
  boot_outlet_height_mm: 0,           // 0 = auto-calculate from bucket/belt geometry
};

// ─── Input sanitiser ──────────────────────────────────────────────────────────
// Called inside runCalc before every API request.
// Prevents two classes of 422 errors:
//   1. NaN values  — produced when a numeric field is cleared (parseFloat("") = NaN)
//   2. Out-of-range values — produced when the user types beyond model bounds
//      (HTML max/min prevent spinner overflow but not direct keyboard entry)
//
// BOUNDS must match the ge/le constraints in models.py BucketElevatorInput.
// When a value is out of range it is silently clamped rather than rejected,
// so the UI stays responsive and only shows an error for real solver failures.

const _BOUNDS = {
  Q_req:                  [1,     5000],
  H_m:                    [1,      200],
  fill_pct:               [30,     100],
  n_rpm:                  [10,     300],
  D_mm:                   [100,   1500],
  boot_pulley_D_mm:       [100,   1000],
  wrap_deg:               [90,     240],
  mu:                     [0.10,  0.60],
  sf:                     [1.0,   2.5],
  K_takeup:               [0.4,   0.9],
  Leq:                    [0,      20],
  Ceff:                   [0,     2.0],
  bucket_gap:             [0,     600],
  wind_pressure_pa:       [0,    5000],
  casing_t_override_mm:   [0,      50],
  shaft_d_override_mm:    [0,     500],
  belt_width_override_mm: [0,    1500],
  takeup_screw_d_mm:      [0,     200],
  takeup_screw_len_m:     [0,       5],
  custom_rho:             [0,    5000],
  custom_aor:             [0,      90],
  custom_abr:             [0,       7],
  custom_flowability:     [0,       4],
  custom_moisture:        [-1,    100],
  custom_cohesion:        [-1,    100],
  motor_kw_override:      [0,    1000],
  chain_sf:               [3.0,  12.0],
  chain_n_strands:        [1,       2],
  chain_sprocket_teeth:   [0,      32],
  boot_outlet_height_mm:  [0,    2000],
};

function sanitizeInputs(inp) {
  return Object.fromEntries(
    Object.entries(inp).map(([k, v]) => {
      // 1. Replace NaN / Infinity with the DEFAULT_INPUTS value (or 0)
      if (typeof v === "number" && !Number.isFinite(v)) {
        const def = DEFAULT_INPUTS[k];
        return [k, typeof def === "number" ? def : 0];
      }
      // 2. Clamp numeric fields to model bounds
      if (_BOUNDS[k] !== undefined && typeof v === "number") {
        const [lo, hi] = _BOUNDS[k];
        return [k, Math.min(hi, Math.max(lo, v))];
      }
      return [k, v];
    })
  );
}
//
// Maps any API response to the canonical field contract used by
// KpiGrid, ComponentPanel, WarningsPanel, and ChartsPanel.
//
// Handles two possible source shapes:
//   A) Your backend's solve_elevator() — uses Q, v, P_total, T_Nm,
//      d_mm, motor_kw, L10, cr, theta_rel, speed_sweep, fill_sweep,
//      mat (dict), bucket (dict with W/H/P/V/id keys)
//   B) FastAPI normalised shape — Q_th, v_ms, power_P_total, etc.
//
// Safe to call on already-normalised data (idempotent).
// ─────────────────────────────────────────────────────────────────
function normaliseResult(raw) {
  if (!raw) return null;

  // ── Performance ──────────────────────────────────────────────
  const Q_th = raw.Q_th ?? raw.Q;
  const v_ms = raw.v_ms ?? raw.v;
  const spacing_m = raw.spacing_m ?? raw.spacing;
  const centrifugal_ratio = raw.centrifugal_ratio ?? raw.cr;
  const release_angle_deg = raw.release_angle_deg ?? raw.theta_rel;

  // ── Power ─────────────────────────────────────────────────────
  const power_P_lift  = raw.power_P_lift  ?? raw.P_lift;
  const power_P_frict = raw.power_P_frict ?? raw.P_drive_loss ?? raw.P_frict;
  const power_P_dig   = raw.power_P_dig   ?? raw.P_digging ?? 0;
  const power_P_total = raw.power_P_total ?? raw.P_total;

  // ── Tension ───────────────────────────────────────────────────
  const tension_ratio =
    raw.tension_ratio ??
    raw.tensionRatio ??
    (raw.T1 && raw.T2 ? raw.T1 / raw.T2 : null);

  // FIX 3: prefer euler_ratio from Task 1 backend; fall back to computed value
  const slip_limit =
    raw.slip_limit ??
    raw.euler_ratio ??
    (raw.mu != null && raw.wrap_deg != null
      ? Math.exp((raw.mu * raw.wrap_deg * Math.PI) / 180)
      : null);

  // ── Shaft ─────────────────────────────────────────────────────
  const shaft_torque_Nm = raw.shaft_torque_Nm ?? raw.T_Nm;
  const shaft_d_mm      = raw.shaft_d_mm      ?? raw.d_mm;

  // ── Belt ──────────────────────────────────────────────────────
  const belt_width_mm = raw.belt_width_mm ?? raw.belt_w ?? raw.beltW;
  const belt_class    =
    raw.belt_class ?? (raw.belt_ply ? `${raw.belt_ply} PLY` : null);

  // ── Motor ─────────────────────────────────────────────────────
  const motor_kW = raw.motor_kW ?? raw.motor_kw ?? raw.motorKW;

  // ── Bearing ───────────────────────────────────────────────────
  const L10_hours = raw.L10_hours ?? raw.L10;

  // ── Bucket sub-object ─────────────────────────────────────────
  let bucket = raw.bucket ?? null;
  if (bucket) {
    bucket = {
      ...bucket,
      series:         bucket.series         ?? bucket.id,
      style:          bucket.style          ?? bucket.type ?? "centrifugal",
      width_mm:       bucket.width_mm       ?? bucket.W,
      depth_mm:       bucket.depth_mm       ?? bucket.H,
      projection_mm:  bucket.projection_mm  ?? bucket.P,
      volume_L:       bucket.volume_L       ?? bucket.V,
      id:             bucket.id             ?? bucket.series,
      W:              bucket.W              ?? bucket.width_mm,
      H:              bucket.H              ?? bucket.depth_mm,
      P:              bucket.P              ?? bucket.projection_mm,
      V:              bucket.V              ?? bucket.volume_L,
    };
  }

  // ── Material sub-object ───────────────────────────────────────
  const material = raw.material ?? raw.mat ?? null;

  // ── Checks ────────────────────────────────────────────────────
  // FIX 2: keep `type` in the normalised check object.
  // BucketElevatorPage reads c.type for fail/warn counts and for the
  // inline strip colour. Removing it caused failCount === 0 always.
  const checks = (raw.checks ?? []).map((c) => ({
    status: c.status ?? (c.type === "ok" ? "pass" : c.type) ?? "info",
    type:   c.type   ?? (c.status === "pass" ? "ok" : c.status) ?? "info",
    code:   c.code   ?? "GEN",
    msg:    c.msg,
  }));

  const has_fail = checks.some((c) => c.status === "fail");
  const has_warn = checks.some((c) => c.status === "warn");
  const status =
    raw.status ?? (has_fail ? "fail" : has_warn ? "warning" : "pass");

  return {
    // ── Meta ────────────────────────────────────────────────────
    inputs:   raw.inputs ?? null,
    material,
    bucket,

    // ── Performance ─────────────────────────────────────────────
    Q_th,
    v_ms,
    spacing_m,
    centrifugal_ratio,
    release_angle_deg,
    trajectory: raw.trajectory ?? [],

    // ── Power ───────────────────────────────────────────────────
    power_P_lift,
    power_P_frict,
    power_P_dig,
    power_P_total,

    // ── Tension ─────────────────────────────────────────────────
    T1: raw.T1 ?? null,
    T2: raw.T2 ?? null,
    T3: raw.T3 ?? null,
    F_eff:       raw.F_eff       ?? null,
    R_headshaft: raw.R_headshaft ?? null,
    tension_ratio,
    slip_limit,

    // ── Shaft + motor ───────────────────────────────────────────
    shaft_torque_Nm,
    shaft_d_mm,
    d_stress_mm:  raw.d_stress_mm  ?? null,
    d_deflect_mm: raw.d_deflect_mm ?? null,
    governed_by:  raw.governed_by  ?? null,
    motor_kW,

    // ── Belt ────────────────────────────────────────────────────
    belt_width_mm,
    belt_class,
    belt_ply: raw.belt_ply ?? null,

    // ── Bearing ─────────────────────────────────────────────────
    L10_hours,

    // ── Component design ────────────────────────────────────────
    inlet_chute:    raw.inlet_chute    ?? null,
    casing_t_mm:    raw.casing_t_mm    ?? null,
    boot_vol_min_m3: raw.boot_vol_min_m3 ?? null,
    thermal_exp_mm: raw.thermal_exp_mm ?? null,

    // ── Chart sweep data ────────────────────────────────────────
    speed_sweep: raw.speed_sweep ?? raw.speedSweep ?? [],
    fill_sweep:  raw.fill_sweep  ?? raw.fillSweep  ?? [],
    speedSweep:  raw.speed_sweep ?? raw.speedSweep ?? [],
    fillSweep:   raw.fill_sweep  ?? raw.fillSweep  ?? [],

    // ── Backend alias pass-throughs ─────────────────────────────
    // generate_report.py and KpiGrid read these original field names
    // directly — they must survive the normaliser unchanged.
    //
    // FIX 1: Q and v were renamed to Q_th and v_ms but never written
    // back under the original names. Nav bar, ElevatorSchematic, and
    // KpiGrid all read results.Q / results.v → were always undefined.
    Q: Q_th,   // ← FIX 1: nav bar, KpiGrid, ElevatorSchematic
    v: v_ms,   // ← FIX 1: nav bar, KpiGrid, ElevatorSchematic

    rho:          raw.rho         ?? null,
    mat:          raw.mat         ?? null,
    Leq:          raw.Leq         ?? null,
    Ceff:         raw.Ceff        ?? null,
    P_total:      raw.P_total     ?? null,
    P_lift:       raw.P_lift      ?? null,
    P_digging:    raw.P_digging   ?? null,
    P_drive_loss: raw.P_drive_loss ?? null,
    T_Nm:         raw.T_Nm        ?? null,
    d_mm:         raw.d_mm        ?? null,
    motor_kw:     raw.motor_kw    ?? null,
    belt_w:       raw.belt_w      ?? null,
    L10:          raw.L10         ?? null,
    spacing:      raw.spacing     ?? null,
    cr:           raw.cr          ?? null,
    theta_rel:    raw.theta_rel   ?? null,

    // FIX 3: New backend fields from v1.2.x — pass through for
    // ComponentPanel, generate_report.py, and future KpiGrid cards.

    // Task 3 — Power decomposition
    P_shaft:   raw.P_shaft  ?? null,
    H_equiv:   raw.H_equiv  ?? null,
    H_total:   raw.H_total  ?? null,

    // Task 1 — Euler-Eytelwein slip check
    T3_ktakeup:   raw.T3_ktakeup   ?? null,
    T3_euler_min: raw.T3_euler_min ?? null,
    euler_ratio:  raw.euler_ratio  ?? null,
    slip_safe:    raw.slip_safe    ?? null,
    euler_check:  raw.euler_check  ?? null,

    // v1.2.0 — Shaft geometry and material behaviour
    shaft_span_mm:        raw.shaft_span_mm        ?? null,
    shaft_A_mm:           raw.shaft_A_mm           ?? null,
    shaft_B_mm:           raw.shaft_B_mm           ?? null,
    bucket_mass_kg:       raw.bucket_mass_kg       ?? null,
    stream_spread:        raw.stream_spread        ?? null,
    mat_behavior:         raw.mat_behavior         ?? null,
    recommended_fill_pct: raw.recommended_fill_pct ?? null,

    // v1.3.0 — Structural detail blocks
    hub:       raw.hub       ?? null,
    key_check: raw.key_check ?? null,
    lagging:   raw.lagging   ?? null,
    end_disc:  raw.end_disc  ?? null,
    bolt_fatigue:   raw.bolt_fatigue   ?? null,
    takeup_gravity: raw.takeup_gravity ?? null,
    takeup_screw:   raw.takeup_screw   ?? null,
    casing_panel:     raw.casing_panel     ?? null,
    casing_stiffener: raw.casing_stiffener ?? null,
    design_recommendations: raw.design_recommendations ?? [],

    // v1.4.0 — Discharge chute (ChuteFlowEngine integration)
    // Shape: { performance, maintenance, telemetry, recommendations, geometry, hood_spoon }
    discharge_chute: raw.discharge_chute ?? null,

    // ── Validation ──────────────────────────────────────────────
    // Casing clearance + stream interception — v1.4.0
    casing_clearance: raw.casing_clearance ?? null,
    stream_chute:     raw.stream_chute     ?? null,

    // BOM + maintenance schedule — Tier 2
    boot_pulley:     raw.boot_pulley     ?? null,
    bom:         raw.bom         ?? null,
    maintenance: raw.maintenance ?? null,
    root_cause:     raw.root_cause     ?? [],
    discharge_type:  raw.discharge_type  ?? "centrifugal",
    is_continuous:   raw.is_continuous   ?? false,

    // v1.7.0 — Selected component details (populated by solver when DB lookup succeeds)
    selected_motor:    raw.selected_motor    ?? null,
    selected_gearbox:  raw.selected_gearbox  ?? null,
    selected_bearing:  raw.selected_bearing  ?? null,
    selected_drive:    raw.selected_drive    ?? null,
    belt_grade:        raw.belt_grade        ?? "",
    motor_kw_override: raw.motor_kw_override ?? 0,

    // v1.7.0 — Bucket geometry fields (for discharge physics and report)
    bucket_style:         raw.bucket_style         ?? null,
    bucket_front_angle:   raw.bucket_front_angle   ?? null,
    bucket_depth_mm:      raw.bucket_depth_mm      ?? null,
    bucket_discharge_type: raw.bucket_discharge_type ?? null,
    bucket_recommended_materials: raw.bucket_recommended_materials ?? null,

    // v1.8.0 — Advisory engines (3.7 / 3.8 / 3.9)
    bucket_recommendation: raw.bucket_recommendation ?? null,
    dynamic_fill:          raw.dynamic_fill          ?? null,
    wrap_recommendation:   raw.wrap_recommendation   ?? null,

    // v1.8.0 — Feed Design (2f)
    feed_design:     raw.feed_design     ?? null,

    // v1.8.0 — Chain elevator outputs
    is_chain:        raw.is_chain        ?? false,
    chain_selected:  raw.chain_selected  ?? null,
    chain_pull_N:    raw.chain_pull_N    ?? null,
    chain_SF_actual: raw.chain_SF_actual ?? null,
    chain_v_ok:      raw.chain_v_ok      ?? null,
    sprocket:        raw.sprocket        ?? null,

    // v1.9.0 — Wrap angle geometry (derived from pulley diameters).
    // FIX: backend computed these but they were never added to this
    // whitelist, so the PulleyEdit wrap card always showed "—".
    wrap_geom_deg:      raw.wrap_geom_deg      ?? null,
    wrap_effective_deg: raw.wrap_effective_deg ?? null,

    // v1.9.0 — Fill advisory range (min/max operating band)
    min_fill_pct: raw.min_fill_pct ?? null,
    max_fill_pct: raw.max_fill_pct ?? null,

    // v1.9.0 — Pulley shell thickness + head shaft critical speed
    pulley_shell:   raw.pulley_shell   ?? null,
    critical_speed: raw.critical_speed ?? null,

    // v1.9.1 — Backlegging risk classification
    backlegging_risk: raw.backlegging_risk ?? null,

    // v1.9.2 — Position-resolved belt tension profile (boot/loaded leg/head/empty leg)
    tension_profile: raw.tension_profile ?? null,

    // v1.9.3 — Material pickup / digging efficiency (centrifugal buckets only)
    pickup_efficiency: raw.pickup_efficiency ?? null,

    // v1.9.4 — Dynamic startup analysis + shock load advisory
    startup_dynamic: raw.startup_dynamic ?? null,
    shock_check:     raw.shock_check     ?? null,

    checks,
    status,
  };
}

// ─────────────────────────────────────────────────────────────────
// HOOK — your original structure, one line changed
// ─────────────────────────────────────────────────────────────────
export function useElevatorCalc() {
  const [inputs,   setInputs]  = useState(DEFAULT_INPUTS);
  const [results,  setResults] = useState(null);
  const [loading,  setLoading] = useState(false);
  const [error,    setError]   = useState(null);
  const [designId]             = useState(() => uuidv4());
  const debounceRef            = useRef(null);

  const runCalc = useCallback(async (inp) => {
    setLoading(true);
    setError(null);
    try {
      const safe = sanitizeInputs(inp);   // clamp NaN + out-of-range before sending
      const raw  = await calculateElevator(safe);
      setResults(normaliseResult(raw));
    } catch (e) {
      // FastAPI 422 validation errors return structured JSON objects.
      // Extract a human-readable message regardless of error shape.
      let msg = "Unknown error";
      if (typeof e?.message === "string" && e.message) {
        // Try to parse if it looks like JSON
        try {
          const parsed = JSON.parse(e.message);
          if (Array.isArray(parsed?.detail)) {
            // Pydantic validation error: [{loc, msg, type}, ...]
            msg = parsed.detail
              .map(d => `${d.loc?.slice(1).join(".") ?? "field"}: ${d.msg}`)
              .join(" · ");
          } else if (parsed?.detail) {
            msg = typeof parsed.detail === "string"
              ? parsed.detail
              : JSON.stringify(parsed.detail);
          } else {
            msg = e.message;
          }
        } catch {
          msg = e.message;
        }
      } else if (typeof e?.message === "object" && e.message !== null) {
        // Already-parsed object on e.message
        const d = e.message;
        if (Array.isArray(d?.detail)) {
          msg = d.detail
            .map(d => `${d.loc?.slice(1).join(".") ?? "field"}: ${d.msg}`)
            .join(" · ");
        } else {
          msg = JSON.stringify(e.message);
        }
      } else if (typeof e === "string") {
        msg = e;
      } else {
        msg = JSON.stringify(e);
      }
      setError(msg);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runCalc(inputs), 300);
    return () => clearTimeout(debounceRef.current);
  }, [inputs, runCalc]);

  const setField = useCallback((key, value) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  }, []);

  const applyOptimizer = useCallback(({ rpm, bucket_id, fill }) => {
    setInputs((prev) => ({
      ...prev,
      n_rpm:       rpm,
      bucket_id,
      auto_bucket: false,
      fill_pct:    fill,
    }));
  }, []);

  const saveCurrentDesign = useCallback(
    async (name, project, notes) => {
      if (!results) return;
      await saveDesign({
        id:           designId,
        module:       "bucket_elevator",
        name,
        project:      project || null,
        inputs_json:  JSON.stringify(inputs),
        results_json: JSON.stringify(results),
        notes:        notes || null,
      });
    },
    [designId, inputs, results],
  );

  const loadDesign = useCallback(async (id) => {
    const record = await getDesign(id);
    setInputs(JSON.parse(record.inputs_json));
    setResults(normaliseResult(JSON.parse(record.results_json)));
  }, []);

  return {
    inputs,
    results,
    loading,
    error,
    setField,
    applyOptimizer,
    saveCurrentDesign,
    loadDesign,
    forceCalc: () => runCalc(inputs),
  };
}