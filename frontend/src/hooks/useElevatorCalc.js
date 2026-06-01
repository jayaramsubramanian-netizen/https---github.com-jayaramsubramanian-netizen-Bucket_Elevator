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
//   A) FastAPI /be/solve  → already correct, pass-through
//   B) Old HTML solve()   → renames fields to FastAPI convention
//
// Safe to call on already-normalised data (idempotent).
// ─────────────────────────────────────────────────────────────────
function normaliseResult(raw) {
  if (!raw) return null;

  // Detect which shape we received. FastAPI has Q_th; old HTML has Q.
  const isOldShape = raw.Q_th === undefined && raw.Q !== undefined;

  // ── Performance ──────────────────────────────────────────────
  const Q_th              = raw.Q_th    ?? raw.Q;
  const v_ms              = raw.v_ms    ?? raw.v;
  const spacing_m         = raw.spacing_m ?? raw.spacing;
  const centrifugal_ratio = raw.centrifugal_ratio ?? raw.cr;
  const release_angle_deg = raw.release_angle_deg ?? raw.theta_rel;

  // ── Power ─────────────────────────────────────────────────────
  const power_P_lift  = raw.power_P_lift  ?? raw.P_lift;
  const power_P_frict = raw.power_P_frict ?? raw.P_frict;
  const power_P_dig   = raw.power_P_dig   ?? 0;
  const power_P_total = raw.power_P_total ?? raw.P_total;

  // ── Tension ───────────────────────────────────────────────────
  // T1, T2, F_eff are the same in both shapes ✓
  const tension_ratio = raw.tension_ratio ?? raw.tensionRatio;
  const slip_limit    = raw.slip_limit
    ?? (raw.mu != null && raw.wrap_deg != null
        ? Math.exp(raw.mu * raw.wrap_deg * Math.PI / 180)
        : null);

  // ── Shaft ─────────────────────────────────────────────────────
  const shaft_torque_Nm = raw.shaft_torque_Nm ?? raw.T_Nm;
  const shaft_d_mm      = raw.shaft_d_mm      ?? raw.d_mm;

  // ── Belt ──────────────────────────────────────────────────────
  const belt_width_mm = raw.belt_width_mm ?? raw.beltW;
  const belt_class    = raw.belt_class    ?? null;

  // ── Motor ─────────────────────────────────────────────────────
  const motor_kW = raw.motor_kW ?? raw.motorKW ?? raw.motor_kw;

  // ── Bearing ───────────────────────────────────────────────────
  const L10_hours = raw.L10_hours ?? raw.L10;

  // ── Bucket sub-object ─────────────────────────────────────────
  // FastAPI: { series, style, width_mm, depth_mm, projection_mm, volume_L }
  // Old HTML: { id, name, W, H, P, V, proj }
  let bucket = raw.bucket ?? null;
  if (bucket && isOldShape) {
    bucket = {
      ...bucket,
      series:        bucket.series        ?? bucket.id,
      style:         bucket.style         ?? bucket.proj ?? "centrifugal",
      width_mm:      bucket.width_mm      ?? bucket.W,
      depth_mm:      bucket.depth_mm      ?? bucket.H,
      projection_mm: bucket.projection_mm ?? bucket.P,
      volume_L:      bucket.volume_L      ?? bucket.V,
    };
  }

  // ── Material sub-object ───────────────────────────────────────
  // FastAPI: results.material   Old HTML: results.mat
  const material = raw.material ?? raw.mat ?? null;

  // ── Checks ───────────────────────────────────────────────────
  // Old HTML checks used { type:'ok'|'warn'|'fail', msg } without code.
  // FastAPI uses { status:'pass'|'warn'|'fail', code, msg }.
  const checks = (raw.checks ?? []).map((c) => ({
    status: c.status ?? (c.type === "ok" ? "pass" : c.type) ?? "info",
    code:   c.code   ?? "GEN",
    msg:    c.msg,
  }));

  const has_fail = checks.some((c) => c.status === "fail");
  const has_warn = checks.some((c) => c.status === "warn");
  const status   = raw.status
    ?? (has_fail ? "fail" : has_warn ? "warning" : "pass");

  return {
    // Meta
    inputs:   raw.inputs  ?? null,
    material,
    bucket,
    // Performance
    Q_th, v_ms, spacing_m, centrifugal_ratio, release_angle_deg,
    trajectory: raw.trajectory ?? [],
    // Power
    power_P_lift, power_P_frict, power_P_dig, power_P_total,
    // Tension
    T1: raw.T1, T2: raw.T2, F_eff: raw.F_eff,
    tension_ratio, slip_limit,
    // Shaft + motor
    shaft_torque_Nm, shaft_d_mm, motor_kW,
    // Belt
    belt_width_mm, belt_class,
    // Bearing
    L10_hours,
    // Component design (FastAPI only — null if old shape)
    inlet_chute:     raw.inlet_chute     ?? null,
    casing_t_mm:     raw.casing_t_mm     ?? null,
    boot_vol_min_m3: raw.boot_vol_min_m3 ?? null,
    thermal_exp_mm:  raw.thermal_exp_mm  ?? null,
    // Chart sweep data (old HTML only — empty if FastAPI)
    speedSweep: raw.speedSweep ?? [],
    fillSweep:  raw.fillSweep  ?? [],
    // Validation
    checks, status,
  };
}

// ─────────────────────────────────────────────────────────────────
// HOOK — your original structure, one line changed
// ─────────────────────────────────────────────────────────────────
export function useElevatorCalc() {
  const [inputs,  setInputs]  = useState(DEFAULT_INPUTS);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [designId]            = useState(() => uuidv4());
  const debounceRef           = useRef(null);

  const runCalc = useCallback(async (inp) => {
    setLoading(true);
    setError(null);
    try {
      const raw = await calculateElevator(inp);
      setResults(normaliseResult(raw));          // ← only change from your original
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
        id:           designId,
        module:       "bucket_elevator",
        name,
        project:      project || null,
        inputs_json:  JSON.stringify(inputs),
        results_json: JSON.stringify(results),
        notes:        notes || null,
      });
    },
    [designId, inputs, results]
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