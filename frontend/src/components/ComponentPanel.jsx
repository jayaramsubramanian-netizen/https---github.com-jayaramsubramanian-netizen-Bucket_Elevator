// ComponentPanel.jsx — Belt/Chain, Buckets, Shaft & Bearings, Drive
// Field names match FastAPI /be/solve response shape.
// All computed variables are INSIDE the guard — never run on undefined data.
import { useState } from "react";

const C = {
  muted: "#5a7a9a", muted2: "#7a9ab8", hi: "#132238", border2: "#1c3050",
  blue: "#4a9eff", green: "#1fb86e", amber: "#d98e00", teal: "#2dd4bf",
  red: "#e05252", text: "#ddeaf6",
};

const TABS = [
  { id: "belt",    label: "Belt / Chain" },
  { id: "bucket",  label: "Buckets" },
  { id: "shaft",   label: "Shaft & Bearings" },
  { id: "gearbox", label: "Drive" },
];

// Safe formatter — returns fallback string instead of throwing on undefined/NaN
const fmt = (v, dp = 2, fb = "—") =>
  (v == null || !isFinite(Number(v))) ? fb : Number(v).toFixed(dp);

const fmtDiv = (a, b, dp = 2) =>
  (a == null || !b) ? "—" : fmt(a / b, dp);

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

  // ── Guard: wait until results AND bucket sub-object are fully populated ──
  if (!results || !results.bucket || !inputs) return null;

  // ── FastAPI field aliases ─────────────────────────────────────────────────
  // Belt / tension
  const T1            = results.T1;                 // N  (same name ✓)
  const T2            = results.T2;                 // N  (same name ✓)
  const F_eff         = results.F_eff;              // N  (same name ✓)
  const tensionRatio  = results.tension_ratio;      // (same name ✓)
  const slipLimit     = results.slip_limit;         // e^(μθ) — FastAPI computes this
  const beltW         = results.belt_width_mm;      // was: results.belt_w
  const beltClass     = results.belt_class;         // e.g. "EP400"

  // Bucket  — FastAPI: width_mm, depth_mm, projection_mm, volume_L, series, style
  const bkt           = results.bucket;
  const bktSeries     = bkt.series;                 // was: bkt.id
  const bktW          = bkt.width_mm;               // was: bkt.W
  const bktH          = bkt.depth_mm;               // was: bkt.H
  const bktP          = bkt.projection_mm;          // was: bkt.P
  const bktV          = bkt.volume_L;               // was: bkt.V
  const spacingM      = results.spacing_m;          // was: results.spacing

  // Material — FastAPI: results.material (may be null if no mat_id)
  const mat           = results.material;
  const matName       = mat?.name  ?? "Custom";
  const matAbr        = mat?.abr   ?? "B";          // A/B/C/D from materials_elevator view
  const rho           = mat?.rho   ?? inputs.rho_kgm3;  // kg/m³

  // Shaft / drive
  const T_Nm          = results.shaft_torque_Nm;    // was: results.T_Nm
  const d_mm          = results.shaft_d_mm;         // was: results.d_mm
  const L10           = results.L10_hours;          // was: results.L10
  const P_total       = results.power_P_total;      // was: results.P_total
  const motor_kW      = results.motor_kW;           // was: results.motor_kw
  const v_ms          = results.v_ms;               // was: results.v

  // ── Derived values (safe — only run after guard) ──────────────────────────

  // Belt ply: T1 per mm of belt width against ~400 N/mm EP standard
  // More accurate than the old T1/12000 heuristic
  const beltPlyRating = (T1 != null && beltW)
    ? Math.ceil(T1 / (beltW * 400 / 4))   // SF≈4 against EP400 baseline
    : "—";

  // Chain pitch selection from T1 (N)
  const chainPitch = T1 == null ? "—"
    : T1 < 20000 ? "63.5"
    : T1 < 50000 ? "101.6"
    : "152.4";

  // Bucket fill volume and mass
  const fillVol = (bktV != null) ? bktV * inputs.fill_pct / 100 : null;
  const matMass = (fillVol != null && rho) ? fillVol * rho / 1000 : null;  // kg

  // Slip limit — prefer the value FastAPI computed (exact μ and θ used in solve)
  // Fall back to recalculating from inputs if not present
  const emuTheta = slipLimit
    ?? Math.exp(inputs.mu * inputs.wrap_deg * Math.PI / 180);

  // Abrasiveness label for display
  const abrLabel = {
    A: "Non-abrasive",
    B: "Mildly abrasive",
    C: "Abrasive",
    D: "Highly abrasive",
  }[matAbr] ?? "—";

  const abrColor = matAbr === "D" ? C.red
                 : matAbr === "C" ? C.amber
                 : C.green;

  // Gearbox output torque requirement
  const gbxTorqueMin = (T_Nm != null && inputs.sf)
    ? fmt(T_Nm / 1000 * inputs.sf, 2)
    : "—";

  return (
    <div>
      <div className="sub-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`sub-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>

        {/* ── BELT / CHAIN ─────────────────────────────────────────── */}
        {tab === "belt" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Belt Design — CEMA Standards · Class {beltClass ?? "—"}
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Belt Width"
                     value={beltW != null ? `${beltW} mm` : "—"} />
                <Row label="Effective Tension"
                     value={`${fmtDiv(F_eff, 1000)} kN`} />
                <Row label="Tight Side T₁"
                     value={`${fmtDiv(T1, 1000)} kN`}
                     color={(T1 ?? 0) > 50000 ? C.red : C.text} />
                <Row label="Slack Side T₂"
                     value={`${fmtDiv(T2, 1000)} kN`} />
                <Row label="Tension Ratio"
                     value={fmt(tensionRatio, 3)} />
                <Row label="Slip Limit e^(μθ)"
                     value={fmt(emuTheta, 3)} />
                <Row label="Belt Class (by T₁/width)"
                     value={beltClass ?? "—"}
                     color={C.blue} />
                <Row label="Belt Ply Estimate"
                     value={typeof beltPlyRating === "number"
                       ? `${beltPlyRating} PLY (est.)` : beltPlyRating}
                     color={C.blue} />
                <Row label="Chain Pitch (if chain)"
                     value={`${chainPitch} mm`} />
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10 }}>
              ℹ Belt tension ratio should be ≤ {fmt(emuTheta, 3)} to prevent
              slip (μ={inputs.mu}, θ={inputs.wrap_deg}°).
              {(tensionRatio ?? 0) > emuTheta
                ? <span style={{ color: C.red, marginLeft: 6 }}>⚠ SLIP RISK</span>
                : <span style={{ color: C.green, marginLeft: 6 }}>✓ No slip</span>}
            </div>
          </>
        )}

        {/* ── BUCKETS ──────────────────────────────────────────────── */}
        {tab === "bucket" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Bucket Analysis — Series {bktSeries ?? "—"}
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Series"
                     value={`${bktSeries ?? "—"} — ${bkt.style ?? ""}`}
                     color={C.blue} />
                <Row label="Width × Depth"
                     value={`${bktW ?? "—"} × ${bktH ?? "—"} mm`} />
                <Row label="Projection (P)"
                     value={`${bktP ?? "—"} mm`} />
                <Row label="Volume (struck)"
                     value={`${bktV ?? "—"} L`} />
                <Row label="Fill Factor"
                     value={`${inputs.fill_pct}%`} />
                <Row label="Active Volume"
                     value={fillVol != null ? `${fillVol.toFixed(3)} L` : "—"} />
                <Row label="Mass per Bucket"
                     value={matMass != null
                       ? `${(matMass * 1000).toFixed(1)} g (${matName})`
                       : "—"} />
                <Row label="Spacing"
                     value={spacingM != null
                       ? `${(spacingM * 1000).toFixed(0)} mm` : "—"} />
                <Row label="Buckets per metre"
                     value={spacingM ? (1 / spacingM).toFixed(2) : "—"} />
                <Row label="Abrasiveness"
                     value={`${matAbr} — ${abrLabel}`}
                     color={abrColor} />
              </tbody>
            </table>
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>
                Bucket Fill Visualisation
              </div>
              <div className="perf-bar-bg">
                <div
                  className="perf-bar-fill"
                  style={{
                    width: `${inputs.fill_pct}%`,
                    background: `linear-gradient(90deg,${C.blue},${C.teal})`,
                  }}
                />
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

        {/* ── SHAFT & BEARINGS ─────────────────────────────────────── */}
        {tab === "shaft" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Shaft &amp; Bearing Design
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Shaft Torque"
                     value={`${fmtDiv(T_Nm, 1000, 3)} kNm`} />
                <Row label="Min Shaft Dia (torsion)"
                     value={`${fmt(d_mm, 1)} mm`}
                     color={C.blue} />
                <Row label="Allowable Shear Stress"
                     value="55 MPa (mild steel)" />
                <Row label="Head Pulley Dia"
                     value={`${inputs.D_mm} mm`} />
                <Row label="Belt Speed"
                     value={`${fmt(v_ms, 3)} m/s`} />
                <Row label="Head Shaft RPM"
                     value={`${inputs.n_rpm} rpm`} />
                <Row label="Bearing L10 Life"
                     value={`${fmt(L10, 0)} h`}
                     color={(L10 ?? 0) < 20000 ? C.amber : C.green} />
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10, marginTop: 6 }}>
              ℹ Shaft sizing uses pure torsion. Add 15–20% for keyway stress
              concentration and combined bending loads in detailed design.
            </div>
          </>
        )}

        {/* ── DRIVE / GEARBOX ──────────────────────────────────────── */}
        {tab === "gearbox" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Drive System Design
            </div>
            <table className="data-table">
              <tbody>
                <Row label="Required Power"
                     value={`${fmt(P_total, 2)} kW`} />
                <Row label="Service Factor"
                     value={inputs.sf} />
                <Row label="Design Power"
                     value={`${fmt((P_total ?? 0) * inputs.sf, 2)} kW`} />
                <Row label="Selected Motor"
                     value={`${motor_kW ?? "—"} kW`}
                     color={C.green} />
                <Row label="Head Shaft Speed"
                     value={`${inputs.n_rpm} rpm`} />
                <Row label="Head Shaft Torque"
                     value={`${fmtDiv(T_Nm, 1000, 3)} kNm`} />
                <Row label="Typical Motor Speed"
                     value="1450 rpm (4P)" />
                <Row label="Required Ratio"
                     value={`${(1450 / inputs.n_rpm).toFixed(1)} : 1`} />
              </tbody>
            </table>
            <div className="warn-item w-ok" style={{ marginTop: 6, fontSize: 10 }}>
              ✓ Select gearbox rated ≥ {gbxTorqueMin} kNm output torque
              at {inputs.n_rpm} rpm output
            </div>
          </>
        )}

      </div>
    </div>
  );
}