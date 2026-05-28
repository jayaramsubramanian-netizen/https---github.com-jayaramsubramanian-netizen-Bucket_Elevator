// KpiGrid.jsx — 12-card KPI display
export default function KpiGrid({ results, inputs }) {
  if (!results) return null;
  const capOK = results.Q >= inputs.Q_req;
  const speedOK = results.v >= 0.5 && results.v <= 2.5;

  const kpis = [
    { label: "Capacity",        value: results.Q.toFixed(1),             unit: "t/h",   status: capOK ? "ok" : "fail",  sub: `req ${inputs.Q_req} t/h` },
    { label: "Belt Speed",      value: results.v.toFixed(2),             unit: "m/s",   status: speedOK ? "ok" : "warn", sub: `${inputs.n_rpm} RPM` },
    { label: "Total Power",     value: results.P_total.toFixed(2),       unit: "kW",    status: "info", sub: `lift ${results.P_lift.toFixed(2)} kW` },
    { label: "Motor Selected",  value: results.motor_kw,                 unit: "kW",    status: "info", sub: `SF ${inputs.sf}` },
    { label: "Tight-side T₁",  value: (results.T1 / 1000).toFixed(2),  unit: "kN",    status: results.T1 > 50000 ? "fail" : "ok", sub: `ratio ${results.tension_ratio.toFixed(2)}` },
    { label: "Shaft Dia.",      value: results.d_mm.toFixed(0),          unit: "mm",    status: "info", sub: `T = ${(results.T_Nm / 1000).toFixed(2)} kNm` },
    { label: "Belt Width",      value: results.belt_w,                   unit: "mm",    status: "info", sub: `bucket ${results.bucket.W}mm` },
    { label: "Centrifugal Ratio", value: results.cr.toFixed(3),          unit: "—",     status: results.cr < 0.8 || results.cr > 2.5 ? "warn" : "ok", sub: `θ_rel ${results.theta_rel.toFixed(1)}°` },
    { label: "Bearing L10",     value: results.L10 > 9999 ? `${(results.L10 / 1000).toFixed(0)}k` : results.L10.toFixed(0), unit: "h", status: results.L10 < 20000 ? "warn" : "ok", sub: `@ ${inputs.n_rpm} rpm` },
    { label: "Bucket Series",   value: results.bucket.id,                unit: "",      status: "info", sub: `${results.bucket.V}L, Km=${results.mat.Km}` },
    { label: "Material",        value: results.rho,                      unit: "kg/m³", status: "info", sub: results.mat.name },
    { label: "Fill Factor",     value: inputs.fill_pct,                  unit: "%",     status: "info", sub: `${(results.bucket.V * inputs.fill_pct / 100).toFixed(2)}L/bucket` },
  ];

  const cardClass = { ok: "ok", fail: "fail", warn: "warn", info: "" };

  return (
    <div className="results-grid">
      {kpis.map((k, i) => (
        <div key={i} className={`res-card ${cardClass[k.status] || ""}`}>
          <div className="res-label">{k.label}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <div className="res-value">{k.value}</div>
            {k.unit && <div className="res-unit">{k.unit}</div>}
          </div>
          <div className="res-sub">{k.sub}</div>
        </div>
      ))}
    </div>
  );
}
