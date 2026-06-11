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
  environment: "dry", // "dry" | "humid" | "wet" | "submerged"  (lagging selection)
  belt_type: "EP", // "EP" | "ST"  (lagging selection)
  wind_pressure_pa: 800, // [Pa]  (casing panel check — typical industrial site)

  // ── v1.5.0 Design Overrides ─────────────────────────────────────
  // All 0 = auto-calculate from first principles. Set > 0 to specify.
  takeup_type: "gravity", // "gravity" | "screw" | "auto"
  takeup_screw_d_mm: 0, // Screw core diameter override [mm]
  takeup_screw_len_m: 0, // Screw shank length for buckling [m]
  shaft_d_override_mm: 0, // Head shaft diameter override [mm]
  belt_width_override_mm: 0, // Belt width override [mm]
  casing_t_override_mm: 0, // Casing plate thickness override [mm]
};

// ─────────────────────────────────────────────────────────────────
// NORMALISER
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
  const power_P_lift = raw.power_P_lift ?? raw.P_lift;
  const power_P_frict = raw.power_P_frict ?? raw.P_drive_loss ?? raw.P_frict;
  const power_P_dig = raw.power_P_dig ?? raw.P_digging ?? 0;
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
  const shaft_d_mm = raw.shaft_d_mm ?? raw.d_mm;

  // ── Belt ──────────────────────────────────────────────────────
  const belt_width_mm = raw.belt_width_mm ?? raw.belt_w ?? raw.beltW;
  const belt_class =
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
      series: bucket.series ?? bucket.id,
      style: bucket.style ?? bucket.type ?? "centrifugal",
      width_mm: bucket.width_mm ?? bucket.W,
      depth_mm: bucket.depth_mm ?? bucket.H,
      projection_mm: bucket.projection_mm ?? bucket.P,
      volume_L: bucket.volume_L ?? bucket.V,
      id: bucket.id ?? bucket.series,
      W: bucket.W ?? bucket.width_mm,
      H: bucket.H ?? bucket.depth_mm,
      P: bucket.P ?? bucket.projection_mm,
      V: bucket.V ?? bucket.volume_L,
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
    type: c.type ?? (c.status === "pass" ? "ok" : c.status) ?? "info",
    code: c.code ?? "GEN",
    msg: c.msg,
  }));

  const has_fail = checks.some((c) => c.status === "fail");
  const has_warn = checks.some((c) => c.status === "warn");
  const status =
    raw.status ?? (has_fail ? "fail" : has_warn ? "warning" : "pass");

  return {
    // ── Meta ────────────────────────────────────────────────────
    inputs: raw.inputs ?? null,
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
    F_eff: raw.F_eff ?? null,
    R_headshaft: raw.R_headshaft ?? null,
    tension_ratio,
    slip_limit,

    // ── Shaft + motor ───────────────────────────────────────────
    shaft_torque_Nm,
    shaft_d_mm,
    d_stress_mm: raw.d_stress_mm ?? null,
    d_deflect_mm: raw.d_deflect_mm ?? null,
    governed_by: raw.governed_by ?? null,
    motor_kW,

    // ── Belt ────────────────────────────────────────────────────
    belt_width_mm,
    belt_class,
    belt_ply: raw.belt_ply ?? null,

    // ── Bearing ─────────────────────────────────────────────────
    L10_hours,

    // ── Component design ────────────────────────────────────────
    inlet_chute: raw.inlet_chute ?? null,
    casing_t_mm: raw.casing_t_mm ?? null,
    boot_vol_min_m3: raw.boot_vol_min_m3 ?? null,
    thermal_exp_mm: raw.thermal_exp_mm ?? null,

    // ── Chart sweep data ────────────────────────────────────────
    speed_sweep: raw.speed_sweep ?? raw.speedSweep ?? [],
    fill_sweep: raw.fill_sweep ?? raw.fillSweep ?? [],
    speedSweep: raw.speed_sweep ?? raw.speedSweep ?? [],
    fillSweep: raw.fill_sweep ?? raw.fillSweep ?? [],

    // ── Backend alias pass-throughs ─────────────────────────────
    // generate_report.py and KpiGrid read these original field names
    // directly — they must survive the normaliser unchanged.
    //
    // FIX 1: Q and v were renamed to Q_th and v_ms but never written
    // back under the original names. Nav bar, ElevatorSchematic, and
    // KpiGrid all read results.Q / results.v → were always undefined.
    Q: Q_th, // ← FIX 1: nav bar, KpiGrid, ElevatorSchematic
    v: v_ms, // ← FIX 1: nav bar, KpiGrid, ElevatorSchematic

    rho: raw.rho ?? null,
    mat: raw.mat ?? null,
    Leq: raw.Leq ?? null,
    Ceff: raw.Ceff ?? null,
    P_total: raw.P_total ?? null,
    P_lift: raw.P_lift ?? null,
    P_digging: raw.P_digging ?? null,
    P_drive_loss: raw.P_drive_loss ?? null,
    T_Nm: raw.T_Nm ?? null,
    d_mm: raw.d_mm ?? null,
    motor_kw: raw.motor_kw ?? null,
    belt_w: raw.belt_w ?? null,
    L10: raw.L10 ?? null,
    spacing: raw.spacing ?? null,
    cr: raw.cr ?? null,
    theta_rel: raw.theta_rel ?? null,

    // FIX 3: New backend fields from v1.2.x — pass through for
    // ComponentPanel, generate_report.py, and future KpiGrid cards.

    // Task 3 — Power decomposition
    P_shaft: raw.P_shaft ?? null,
    H_equiv: raw.H_equiv ?? null,
    H_total: raw.H_total ?? null,

    // Task 1 — Euler-Eytelwein slip check
    T3_ktakeup: raw.T3_ktakeup ?? null,
    T3_euler_min: raw.T3_euler_min ?? null,
    euler_ratio: raw.euler_ratio ?? null,
    slip_safe: raw.slip_safe ?? null,
    euler_check: raw.euler_check ?? null,

    // v1.2.0 — Shaft geometry and material behaviour
    shaft_span_mm: raw.shaft_span_mm ?? null,
    shaft_A_mm: raw.shaft_A_mm ?? null,
    shaft_B_mm: raw.shaft_B_mm ?? null,
    bucket_mass_kg: raw.bucket_mass_kg ?? null,
    stream_spread: raw.stream_spread ?? null,
    mat_behavior: raw.mat_behavior ?? null,
    recommended_fill_pct: raw.recommended_fill_pct ?? null,

    // v1.3.0 — Structural detail blocks
    hub: raw.hub ?? null,
    key_check: raw.key_check ?? null,
    lagging: raw.lagging ?? null,
    end_disc: raw.end_disc ?? null,
    bolt_fatigue: raw.bolt_fatigue ?? null,
    takeup_gravity: raw.takeup_gravity ?? null,
    takeup_screw: raw.takeup_screw ?? null,
    casing_panel: raw.casing_panel ?? null,
    casing_stiffener: raw.casing_stiffener ?? null,
    design_recommendations: raw.design_recommendations ?? [],

    // v1.4.0 — Discharge chute (ChuteFlowEngine integration)
    // Shape: { performance, maintenance, telemetry, recommendations, geometry, hood_spoon }
    discharge_chute: raw.discharge_chute ?? null,

    // ── Validation ──────────────────────────────────────────────
    // Casing clearance + stream interception — v1.4.0
    casing_clearance: raw.casing_clearance ?? null,
    stream_chute: raw.stream_chute ?? null,

    // BOM + maintenance schedule — Tier 2
    bom: raw.bom ?? null,
    maintenance: raw.maintenance ?? null,

    checks,
    status,
  };
}

// ─────────────────────────────────────────────────────────────────
// HOOK — your original structure, one line changed
// ─────────────────────────────────────────────────────────────────
export function useElevatorCalc() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [designId] = useState(() => uuidv4());
  const debounceRef = useRef(null);

  const runCalc = useCallback(async (inp) => {
    setLoading(true);
    setError(null);
    try {
      const raw = await calculateElevator(inp);
      setResults(normaliseResult(raw)); // ← only change from original hook
    } catch (e) {
      setError(e.message);
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
      n_rpm: rpm,
      bucket_id,
      auto_bucket: false,
      fill_pct: fill,
    }));
  }, []);

  const saveCurrentDesign = useCallback(
    async (name, project, notes) => {
      if (!results) return;
      await saveDesign({
        id: designId,
        module: "bucket_elevator",
        name,
        project: project || null,
        inputs_json: JSON.stringify(inputs),
        results_json: JSON.stringify(results),
        notes: notes || null,
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
