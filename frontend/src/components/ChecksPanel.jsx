// ChecksPanel.jsx — engineering checks, warnings, and design summary
const C = {
  muted: "#5a7a9a", hi: "#132238", text: "#ddeaf6",
};

export default function ChecksPanel({ results, inputs }) {
  if (!results) return null;

  const summary = [
    ["Material",          results.mat.name],
    ["Density",           `${results.rho} kg/m³`],
    ["Lift Height",       `${inputs.H_m} m`],
    ["Required Capacity", `${inputs.Q_req} t/h`],
    ["Achieved Capacity", `${results.Q.toFixed(1)} t/h`],
    ["Belt Speed",        `${results.v.toFixed(3)} m/s`],
    ["Head Pulley Dia.",  `${inputs.D_mm} mm @ ${inputs.n_rpm} rpm`],
    ["Bucket Series",     `${results.bucket.id} — ${results.bucket.V}L`],
    ["Belt Width",        `${results.belt_w} mm`],
    ["Lift Power",        `${results.P_lift.toFixed(2)} kW`],
    ["Total Power",       `${results.P_total.toFixed(2)} kW`],
    ["Motor",             `${results.motor_kw} kW`],
    ["Tight-side Tension",`${(results.T1 / 1000).toFixed(2)} kN`],
    ["Min Shaft Dia.",    `${results.d_mm.toFixed(1)} mm`],
    ["Centrifugal Ratio", results.cr.toFixed(3)],
    ["Discharge Angle",   `${results.theta_rel.toFixed(1)}° from vertical`],
  ];

  return (
    <>
      {/* Engineering Checks */}
      <div className="warn-panel">
        {results.checks.map((c, i) => (
          <div key={i} className={`warn-item ${c.type === "fail" ? "w-fail" : c.type === "warn" ? "w-warn" : c.type === "ok" ? "w-ok" : "w-info"}`}>
            <span>{c.type === "fail" ? "✗" : c.type === "warn" ? "⚠" : c.type === "ok" ? "✓" : "ℹ"}</span>
            <span>{c.msg}</span>
          </div>
        ))}
      </div>

      {/* Design Summary */}
      <div className="sec-hdr" style={{ marginTop: 8 }}>Design Summary</div>
      <div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: 11 }}>
        {summary.map(([k, v], i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", padding: "5px 10px",
            background: i % 2 ? "transparent" : C.hi, borderRadius: 3,
          }}>
            <span style={{ color: C.muted }}>{k}</span>
            <span style={{ fontFamily: "JetBrains Mono", color: C.text }}>{v}</span>
          </div>
        ))}
      </div>
    </>
  );
}
