// useElevatorCalc.js — manages input state, debounced API calls, save/load
// Your original architecture preserved exactly.
// Added: normaliseResult() maps any API response shape to the field contract
// that KpiGrid, ComponentPanel, and all display components expect.
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

  // Detect which shape we received. FastAPI has Q_th; backend has Q.
  const isOldShape = raw.Q_th === undefined && raw.Q !== undefined;

  // ── Performance ──────────────────────────────────────────────
  const Q_th = raw.Q_th ?? raw.Q;
  const v_ms = raw.v_ms ?? raw.v;
  const spacing_m = raw.spacing_m ?? raw.spacing;
  const centrifugal_ratio = raw.centrifugal_ratio ?? raw.cr;
  const release_angle_deg = raw.release_angle_deg ?? raw.theta_rel;

  // ── Power ─────────────────────────────────────────────────────
  // Backend: P_lift, P_digging, P_drive_loss, P_total
  const power_P_lift = raw.power_P_lift ?? raw.P_lift;
  const power_P_frict = raw.power_P_frict ?? raw.P_drive_loss ?? raw.P_frict;
  const power_P_dig = raw.power_P_dig ?? raw.P_digging ?? 0;
  const power_P_total = raw.power_P_total ?? raw.P_total;

  // ── Tension ───────────────────────────────────────────────────
  // T1, T2, T3, F_eff, R_headshaft — same keys in backend ✓
  const tension_ratio =
    raw.tension_ratio ??
    raw.tensionRatio ??
    (raw.T1 && raw.T2 ? raw.T1 / raw.T2 : null);
  const slip_limit =
    raw.slip_limit ??
    (raw.mu != null && raw.wrap_deg != null
      ? Math.exp((raw.mu * raw.wrap_deg * Math.PI) / 180)
      : null);

  // ── Shaft ─────────────────────────────────────────────────────
  // Backend: T_Nm, d_mm
  const shaft_torque_Nm = raw.shaft_torque_Nm ?? raw.T_Nm;
  const shaft_d_mm = raw.shaft_d_mm ?? raw.d_mm;

  // ── Belt ──────────────────────────────────────────────────────
  // Backend: belt_w (int mm), belt_ply
  const belt_width_mm = raw.belt_width_mm ?? raw.belt_w ?? raw.beltW;
  const belt_class =
    raw.belt_class ?? (raw.belt_ply ? `${raw.belt_ply} PLY` : null);

  // ── Motor ─────────────────────────────────────────────────────
  // Backend: motor_kw (lowercase)
  const motor_kW = raw.motor_kW ?? raw.motor_kw ?? raw.motorKW;

  // ── Bearing ───────────────────────────────────────────────────
  // Backend: L10
  const L10_hours = raw.L10_hours ?? raw.L10;

  // ── Bucket sub-object ─────────────────────────────────────────
  // Backend keys: id, W, H, P, V, type, name
  // Normalised:   series, style, width_mm, depth_mm, projection_mm, volume_L
  let bucket = raw.bucket ?? null;
  if (bucket) {
    bucket = {
      ...bucket,
      // Normalised names (used by display components)
      series: bucket.series ?? bucket.id,
      style: bucket.style ?? bucket.type ?? bucket.proj ?? "centrifugal",
      width_mm: bucket.width_mm ?? bucket.W,
      depth_mm: bucket.depth_mm ?? bucket.H,
      projection_mm: bucket.projection_mm ?? bucket.P,
      volume_L: bucket.volume_L ?? bucket.V,
      // Keep originals so generate_report.py can read both naming conventions
      id: bucket.id ?? bucket.series,
      W: bucket.W ?? bucket.width_mm,
      H: bucket.H ?? bucket.depth_mm,
      P: bucket.P ?? bucket.projection_mm,
      V: bucket.V ?? bucket.volume_L,
    };
  }

  // ── Material sub-object ───────────────────────────────────────
  // Backend: results.mat   Normalised: results.material
  const material = raw.material ?? raw.mat ?? null;

  // ── Checks ────────────────────────────────────────────────────
  // Backend uses { type:'ok'|'warn'|'fail'|'info', msg }
  // Normalise to { status:'pass'|'warn'|'fail'|'info', code, msg }
  const checks = (raw.checks ?? []).map((c) => ({
    status: c.status ?? (c.type === "ok" ? "pass" : c.type) ?? "info",
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
    material, // normalised name
    bucket, // both old + new keys present

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
    // Backend returns speed_sweep / fill_sweep (snake_case).
    // Keep all four names so ChartsPanel finds them regardless of shape.
    speed_sweep: raw.speed_sweep ?? raw.speedSweep ?? [],
    fill_sweep: raw.fill_sweep ?? raw.fillSweep ?? [],
    speedSweep: raw.speed_sweep ?? raw.speedSweep ?? [],
    fillSweep: raw.fill_sweep ?? raw.fillSweep ?? [],

    // ── Backend alias pass-throughs ─────────────────────────────
    // generate_report.py reads these original field names directly,
    // so they must survive the normaliser unchanged.
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

    // ── Validation ──────────────────────────────────────────────
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
      setResults(normaliseResult(raw)); // ← only change from your original
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
    // Normalise on load too — handles designs saved in old field-name format
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
