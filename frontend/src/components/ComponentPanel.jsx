// ComponentPanel.jsx — Belt/Chain, Buckets, Shaft & Bearings, Drive
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
  if (!results) return null;

  const beltPlyRating = Math.ceil(results.T1 / 12000);
  const chainPitch = results.T1 < 20000 ? 63.5 : results.T1 < 50000 ? 101.6 : 152.4;
  const fillVol = results.bucket.V * inputs.fill_pct / 100;
  const matMass = fillVol * results.rho / 1000;
  const emuTheta = Math.exp(inputs.mu * inputs.wrap_deg * Math.PI / 180);

  return (
    <div>
      <div className="sub-tabs">
        {TABS.map((t) => (
          <button key={t.id} className={`sub-tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        {tab === "belt" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>Belt Design — CEMA Standards</div>
            <table className="data-table">
              <tbody>
                <Row label="Belt Width"            value={`${results.belt_w} mm`} />
                <Row label="Effective Tension"     value={`${(results.F_eff / 1000).toFixed(2)} kN`} />
                <Row label="Tight Side T₁"         value={`${(results.T1 / 1000).toFixed(2)} kN`} color={results.T1 > 50000 ? C.red : C.text} />
                <Row label="Slack Side T₂"         value={`${(results.T2 / 1000).toFixed(2)} kN`} />
                <Row label="Tension Ratio"         value={results.tension_ratio.toFixed(3)} />
                <Row label="Recommended Ply Rating" value={`${beltPlyRating} PLY (est.)`} color={C.blue} />
                <Row label="Chain Pitch (if chain)" value={`${chainPitch} mm`} />
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10 }}>
              ℹ Belt tension ratio should be ≤ e^(μθ) = {emuTheta.toFixed(3)} to prevent slip (μ={inputs.mu}, θ={inputs.wrap_deg}°)
            </div>
          </>
        )}

        {tab === "bucket" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>Bucket Analysis — Series {results.bucket.id}</div>
            <table className="data-table">
              <tbody>
                <Row label="Series"            value={`${results.bucket.id} — ${results.bucket.name}`} color={C.blue} />
                <Row label="Width × Height"    value={`${results.bucket.W} × ${results.bucket.H} mm`} />
                <Row label="Projection (P)"    value={`${results.bucket.P} mm`} />
                <Row label="Volume (struck)"   value={`${results.bucket.V} L`} />
                <Row label="Fill Factor"       value={`${inputs.fill_pct}%`} />
                <Row label="Active Volume"     value={`${fillVol.toFixed(3)} L`} />
                <Row label="Mass per Bucket"   value={`${(matMass * 1000).toFixed(1)} g (${results.mat.name})`} />
                <Row label="Spacing"           value={`${(results.spacing * 1000).toFixed(0)} mm`} />
                <Row label="Buckets per metre" value={(1 / results.spacing).toFixed(2)} />
                <Row label="Abrasiveness"
                  value={`${results.mat.abr} — ${results.mat.abr === "A" ? "Non-abrasive" : results.mat.abr === "B" ? "Mildly abrasive" : results.mat.abr === "C" ? "Abrasive" : "Highly abrasive"}`}
                  color={results.mat.abr === "D" ? C.red : results.mat.abr === "C" ? C.amber : C.green} />
              </tbody>
            </table>
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>Bucket Fill Visualisation</div>
              <div className="perf-bar-bg">
                <div className="perf-bar-fill" style={{ width: `${inputs.fill_pct}%`, background: `linear-gradient(90deg,${C.blue},${C.teal})` }} />
              </div>
              <div style={{ fontSize: 9, color: C.muted, marginTop: 3, display: "flex", justifyContent: "space-between" }}>
                <span>0%</span>
                <span style={{ color: C.text }}>{inputs.fill_pct}% fill</span>
                <span>100%</span>
              </div>
            </div>
          </>
        )}

        {tab === "shaft" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>Shaft &amp; Bearing Design</div>
            <table className="data-table">
              <tbody>
                <Row label="Shaft Torque"             value={`${(results.T_Nm / 1000).toFixed(3)} kNm`} />
                <Row label="Min Shaft Dia (torsion)"  value={`${results.d_mm.toFixed(1)} mm`} color={C.blue} />
                <Row label="Allowable Shear Stress"   value="55 MPa (mild steel)" />
                <Row label="Head Pulley Dia"          value={`${inputs.D_mm} mm`} />
                <Row label="Belt Speed"               value={`${results.v.toFixed(3)} m/s`} />
                <Row label="Head Shaft RPM"           value={`${inputs.n_rpm} rpm`} />
                <Row label="Bearing L10 Life"         value={`${results.L10.toFixed(0)} h`} color={results.L10 < 20000 ? C.amber : C.green} />
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10, marginTop: 6 }}>
              ℹ Shaft sizing uses pure torsion. Add 15–20% for keyway stress concentration and combined bending loads in detailed design.
            </div>
          </>
        )}

        {tab === "gearbox" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>Drive System Design</div>
            <table className="data-table">
              <tbody>
                <Row label="Required Power"    value={`${results.P_total.toFixed(2)} kW`} />
                <Row label="Service Factor"    value={inputs.sf} />
                <Row label="Design Power"      value={`${(results.P_total * inputs.sf).toFixed(2)} kW`} />
                <Row label="Selected Motor"    value={`${results.motor_kw} kW`} color={C.green} />
                <Row label="Head Shaft Speed"  value={`${inputs.n_rpm} rpm`} />
                <Row label="Head Shaft Torque" value={`${(results.T_Nm / 1000).toFixed(3)} kNm`} />
                <Row label="Typical Motor Speed"  value="1450 rpm (4P)" />
                <Row label="Required Ratio"    value={`${(1450 / inputs.n_rpm).toFixed(1)} : 1`} />
              </tbody>
            </table>
            <div className="warn-item w-ok" style={{ marginTop: 6, fontSize: 10 }}>
              ✓ Select gearbox rated ≥ {(results.T_Nm / 1000 * inputs.sf).toFixed(2)} kNm output torque at {inputs.n_rpm} rpm output
            </div>
          </>
        )}
      </div>
    </div>
  );
}
