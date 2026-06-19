// ComponentPanel.jsx — Belt/Chain, Buckets, Shaft & Bearings, Drive
// Pure display component — all values from results dict, no recomputation.
//
// v1.9.9 fixes:
//   1. tensionRatio — was computed as T1/T2 because results.tension_ratio
//      doesn't exist. T1/T2 is trivial display arithmetic from two known
//      backend fields; kept as-is. But emuTheta was re-computing
//      Math.exp(mu * wrap_deg * PI / 180) — replaced with results.euler_ratio.
//      slipRisk now reads results.slip_safe directly.
//   2. "55 MPa (mild steel)" — hardcoded allowable shear stress that became
//      wrong the moment shaft_material was added. Now reads
//      results.shaft_tau_allow_MPa (grade-specific, from backend).
//   3. beltPlyCalc = Math.ceil(T1 / 12000) — hardcoded 12000 N/ply threshold
//      used as fallback when belt_ply was missing. Backend always provides
//      results.belt_ply directly; the estimate is removed.
//   4. chainPitch from hardcoded tension thresholds (20000/50000N) — replaced
//      with results.chain_selected.pitch_mm for chain elevators.
//   5. fillVol/matMass — these were derived from bktV * fill_pct / 100 and
//      fillVol * rho / 1000. Backend exposes results.bucket_mass_kg (total
//      bucket mass at the specified fill) — used instead for bucket mass display.
//      Active volume per bucket is retained as a simple display calculation
//      (bktV * fill_pct / 100) since it's display arithmetic, not engineering.

import { useState } from "react";

const C = {
  muted: "#64748b",
  muted2: "#94a3b8",
  hi: "#243247",
  border2: "#ffffff1e",
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  teal: "#14b8a6",
  red: "#ef4444",
  text: "#f1f5f9",
};

const TABS = [
  { id: "belt",    label: "Belt / Chain" },
  { id: "bucket",  label: "Buckets" },
  { id: "shaft",   label: "Shaft & Bearings" },
  { id: "gearbox", label: "Drive" },
];

const fmt = (v, dp = 2, fb = "—") =>
  v == null || !isFinite(Number(v)) ? fb : Number(v).toFixed(dp);

const fmtDiv = (a, b, dp = 2) => (a == null || !b ? "—" : fmt(a / b, dp));

function Row({ label, value, color }) {
  return (
    <tr>
      <td style={{ color: C.muted }}>{label}</td>
      <td className="mono" style={{ color: color || C.text }}>{value}</td>
    </tr>
  );
}

export default function ComponentPanel({ results, inputs }) {
  const [tab, setTab] = useState("belt");

  if (!results || !results.bucket || !inputs) return null;

  const bkt   = results.bucket;
  const bktW  = bkt.W  ?? bkt.width_mm      ?? "—";
  const bktH  = bkt.H  ?? bkt.depth_mm      ?? "—";
  const bktP  = bkt.P  ?? bkt.projection_mm ?? "—";
  const bktV  = bkt.V  ?? bkt.volume_L      ?? null;
  const bktId = bkt.id ?? bkt.series        ?? "—";
  const bktName = bkt.name ?? bkt.style     ?? "—";

  const mat = results.mat ?? results.material ?? {};
  const rho = results.rho ?? mat.rho_loose ?? mat.rho ?? inputs.custom_rho ?? 1000;

  const T1    = results.T1 ?? 0;
  const T2    = results.T2 ?? 0;
  const T3    = results.T3 ?? 0;
  const F_eff = results.F_eff ?? 0;

  // T1/T2 is display arithmetic from two backend fields — acceptable
  const tensionRatio = T2 ? T1 / T2 : null;

  // FIX 1: euler_ratio and slip_safe come from backend — no recomputation
  const eulerRatio = results.euler_ratio ?? null;
  const slipSafe   = results.slip_safe   ?? null;

  const beltW   = results.belt_w ?? results.belt_width_mm ?? "—";
  // FIX 3: belt_ply always provided by backend — removed beltPlyCalc fallback
  const beltPly = results.belt_ply ?? null;

  const T_Nm    = results.T_Nm ?? results.shaft_torque_Nm ?? null;
  const d_mm    = results.d_mm ?? results.shaft_d_mm      ?? null;
  const v_ms    = results.v   ?? results.v_ms             ?? null;
  const L10     = results.L10 ?? results.L10_hours        ?? null;
  const P_total = results.P_total ?? results.power_P_total ?? null;
  const motor_kw = results.motor_kw ?? results.motor_kW   ?? "—";
  const spacing  = results.spacing  ?? results.spacing_m  ?? null;

  // FIX 2: allowable shear from backend (grade-specific) — was "55 MPa (mild steel)"
  const tauAllow = results.shaft_tau_allow_MPa;

  // FIX 4: chain pitch from backend chain_selected — was hardcoded tension thresholds
  const chainPitchMm = results.chain_selected?.pitch_mm ?? null;

  // FIX 5: bucket mass per bucket from backend — was matMass = fillVol * rho / 1000
  // Active volume display (bktV * fill_pct / 100) is retained as pure display arithmetic
  const fillVol   = bktV != null ? (bktV * inputs.fill_pct) / 100 : null;
  const bktMassKg = results.bucket_mass_kg ?? null;

  const abrCode  = mat.abr_code ?? 0;
  const abrLabel = abrCode >= 6 ? "Highly abrasive" : abrCode >= 4 ? "Abrasive"
                 : abrCode >= 2 ? "Mildly abrasive" : "Non-abrasive";
  const abrColor = abrCode >= 6 ? C.red : abrCode >= 4 ? C.amber : C.green;

  return (
    <div>
      <div className="sub-tabs">
        {TABS.map(t => (
          <button key={t.id} className={`sub-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>

        {/* ── BELT / CHAIN ── */}
        {tab === "belt" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Belt Design — CEMA Standards
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Belt Width"         value={beltW !== "—" ? `${beltW} mm` : "—"} />
                <Row label="Effective Tension  F_eff"
                  value={`${fmtDiv(F_eff, 1000)} kN`} />
                <Row label="Material Component  T1"
                  value={`${fmtDiv(T1, 1000)} kN`}
                  color={T1 > 50000 ? C.red : C.text} />
                <Row label="Self-Weight Component  T2"
                  value={`${fmtDiv(T2, 1000)} kN`} />
                <Row label="Take-up / Slack Side  T3"
                  value={`${fmtDiv(T3, 1000)} kN`} />
                <Row label="Belt Tight Side  (T3 + F_eff)"
                  value={T3 != null && F_eff != null
                    ? `${fmtDiv(T3 + F_eff, 1000)} kN`
                    : "—"}
                  color={C.blue} />
                <Row label="Slip Limit e^(μθ)"  value={eulerRatio != null ? fmt(eulerRatio, 3) : "—"} />
                <Row label="Belt Ply Rating"
                  value={beltPly != null ? `${beltPly} PLY` : "—"}
                  color={C.blue} />
                {chainPitchMm != null && (
                  <Row label="Chain Pitch" value={`${chainPitchMm} mm`} />
                )}
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10 }}>
              ℹ Slip check: (T3 + F_eff) / T3 must be ≤ e^(μθ) = {eulerRatio != null ? fmt(eulerRatio, 3) : "—"} (μ={inputs.mu}, θ={inputs.wrap_deg}°).
              {slipSafe === false
                ? <span style={{ color: C.red, marginLeft: 6 }}>⚠ SLIP RISK</span>
                : slipSafe === true
                  ? <span style={{ color: C.green, marginLeft: 6 }}>✓ No slip</span>
                  : null}
            </div>
          </>
        )}

        {/* ── BUCKETS ── */}
        {tab === "bucket" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Bucket Analysis — Series {bktId}
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Series"          value={`${bktId} — ${bktName}`} color={C.blue} />
                <Row label="Width × Height"  value={`${bktW} × ${bktH} mm`} />
                <Row label="Projection (P)"  value={`${bktP} mm`} />
                <Row label="Volume (struck)" value={`${bktV ?? "—"} L`} />
                <Row label="Fill Factor"     value={`${inputs.fill_pct}%`} />
                <Row label="Active Volume"
                  value={fillVol != null ? `${fillVol.toFixed(3)} L` : "—"} />
                <Row label="Mass per Bucket"
                  value={bktMassKg != null
                    ? `${bktMassKg.toFixed(2)} kg`
                    : "—"} />
                <Row label="Spacing"
                  value={spacing != null ? `${(spacing * 1000).toFixed(0)} mm` : "—"} />
                <Row label="Buckets per metre"
                  value={spacing ? (1 / spacing).toFixed(2) : "—"} />
                <Row label="Abrasiveness"
                  value={`${abrCode}/7 — ${abrLabel}`} color={abrColor} />
              </tbody>
            </table>
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>
                Bucket Fill Visualisation
              </div>
              <div className="perf-bar-bg">
                <div className="perf-bar-fill" style={{
                  width: `${inputs.fill_pct}%`,
                  background: `linear-gradient(90deg,${C.blue},${C.teal})`,
                }} />
              </div>
              <div style={{
                fontSize: 9, color: C.muted, marginTop: 3,
                display: "flex", justifyContent: "space-between",
              }}>
                <span>0%</span>
                <span style={{ color: C.text }}>{inputs.fill_pct}% fill</span>
                <span>100%</span>
              </div>
            </div>
          </>
        )}

        {/* ── SHAFT & BEARINGS ── */}
        {tab === "shaft" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Shaft &amp; Bearing Design
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Shaft Torque"
                  value={`${fmtDiv(T_Nm, 1000, 3)} kNm`} />
                <Row label="Min Shaft Dia."
                  value={`${fmt(d_mm, 1)} mm`} color={C.blue} />
                <Row label="Governed by"
                  value={results.governed_by ?? "stress"} />
                <Row label="Material Grade"
                  value={results.shaft_material_name ?? "—"} />
                {/* FIX 2: was hardcoded "55 MPa (mild steel)" — now reads
                    results.shaft_tau_allow_MPa (grade-specific from backend) */}
                <Row label="Allowable Shear"
                  value={tauAllow != null ? `${tauAllow} MPa` : "—"} />
                <Row label="Section"
                  value={results.shaft_section ?? "—"} />
                <Row label="Hub Connection"
                  value={results.shaft_hub_connection ?? "—"} />
                <Row label="Head Pulley Dia."  value={`${inputs.D_mm} mm`} />
                <Row label="Belt Speed"        value={`${fmt(v_ms, 3)} m/s`} />
                <Row label="Head Shaft RPM"    value={`${inputs.n_rpm} rpm`} />
                <Row label="Bearing L10 Life"
                  value={`${fmt(L10, 0)} h`}
                  color={(L10 ?? 0) < 20000 ? C.amber : C.green} />
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10, marginTop: 6 }}>
              ℹ Shaft sizing uses combined torsion + bending (ASME DE-Goodman).
              Full detailed design should verify keyway stress concentration factors.
            </div>
          </>
        )}

        {/* ── DRIVE / GEARBOX ── */}
        {tab === "gearbox" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Drive System Design
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Required Power"   value={`${fmt(P_total, 2)} kW`} />
                <Row label="Service Factor"   value={inputs.sf} />
                <Row label="Design Power"
                  value={`${fmt((P_total ?? 0) * (inputs.sf ?? 1.25), 2)} kW`} />
                <Row label="Selected Motor"   value={`${motor_kw} kW`} color={C.green} />
                <Row label="Head Shaft Speed" value={`${inputs.n_rpm} rpm`} />
                <Row label="Head Shaft Torque" value={`${fmtDiv(T_Nm, 1000, 3)} kNm`} />
                <Row label="Typical Motor Speed"
                  value={results.motor_nominal_rpm != null
                    ? `${results.motor_nominal_rpm} rpm (4P IEC)`
                    : "1450 rpm (4P)"} />
                <Row label="Required Ratio"
                  value={results.gearbox_ratio != null
                    ? `${results.gearbox_ratio} : 1`
                    : `${(1450 / (inputs.n_rpm || 1)).toFixed(1)} : 1`} />
              </tbody>
            </table>
            <div className="warn-item w-ok" style={{ marginTop: 6, fontSize: 10 }}>
              ✓ Select gearbox rated ≥{" "}
              {fmtDiv(T_Nm ? T_Nm * (inputs.sf ?? 1.25) : null, 1000, 2)} kNm
              output torque at {inputs.n_rpm} rpm output
            </div>
          </>
        )}
      </div>
    </div>
  );
}