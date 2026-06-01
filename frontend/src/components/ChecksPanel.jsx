// ChecksPanel.jsx — engineering checks, warnings, and design summary
// Field names match FastAPI /be/solve response (normalised by useElevatorCalc).
const C = {
  muted: "#5a7a9a", hi: "#132238", text: "#ddeaf6",
};

const fmt = (v, dp = 2, fb = "—") =>
  v == null || !isFinite(Number(v)) ? fb : Number(v).toFixed(dp);

export default function ChecksPanel({ results, inputs }) {
  if (!results || !inputs) return null;

  // ── FastAPI field aliases ─────────────────────────────────────
  const mat      = results.material;            // was: results.mat
  const bkt      = results.bucket;
  const rho      = mat?.rho ?? inputs.rho_kgm3 ?? inputs.custom_rho;

  // checks: FastAPI uses { status:'pass'|'warn'|'fail', code, msg }
  // normaliseResult() already converted old { type, msg } → { status, code, msg }
  const checks   = results.checks ?? [];

  const summary = [
    ["Material",          mat?.name              ?? "Custom"],
    ["Density",           `${rho ?? "—"} kg/m³`],
    ["Lift Height",       `${inputs.H_m} m`],
    ["Required Capacity", `${inputs.Q_req} t/h`],
    ["Achieved Capacity", `${fmt(results.Q_th, 1)} t/h`],
    ["Belt Speed",        `${fmt(results.v_ms, 3)} m/s`],
    ["Head Pulley Dia.",  `${inputs.D_mm} mm @ ${inputs.n_rpm} rpm`],
    ["Bucket Series",     `${bkt?.series ?? "—"} — ${bkt?.volume_L ?? "—"}L`],
    ["Belt Width",        `${results.belt_width_mm ?? "—"} mm`],
    ["Lift Power",        `${fmt(results.power_P_lift, 2)} kW`],
    ["Total Power",       `${fmt(results.power_P_total, 2)} kW`],
    ["Motor",             `${results.motor_kW ?? "—"} kW`],
    ["Tight-side Tension",`${fmt(results.T1 / 1000, 2)} kN`],
    ["Min Shaft Dia.",    `${fmt(results.shaft_d_mm, 1)} mm`],
    ["Centrifugal Ratio", fmt(results.centrifugal_ratio, 3)],
    ["Discharge Angle",   `${fmt(results.release_angle_deg, 1)}° from vertical`],
  ];

  // Icon + class helpers — handle both 'status' (FastAPI) and legacy 'type' (old HTML)
  const getStatus = (c) => c.status ?? (c.type === "ok" ? "pass" : c.type) ?? "info";
  const iconMap   = { pass: "✓", warn: "⚠", fail: "✗", info: "ℹ" };
  const classMap  = { pass: "w-ok", warn: "w-warn", fail: "w-fail", info: "w-info" };

  return (
    <>
      {/* Engineering Checks */}
      <div className="warn-panel">
        {checks.length === 0 && (
          <div className="warn-item w-info">
            <span>ℹ</span><span>No checks available — waiting for calculation.</span>
          </div>
        )}
        {checks.map((c, i) => {
          const st = getStatus(c);
          return (
            <div key={i} className={`warn-item ${classMap[st] ?? "w-info"}`}>
              <span>{iconMap[st] ?? "ℹ"}</span>
              <span>{c.msg}</span>
            </div>
          );
        })}
      </div>

      {/* Design Summary */}
      <div className="sec-hdr" style={{ marginTop: 8 }}>Design Summary</div>
      <div style={{
        padding: 16, display: "grid",
        gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: 11,
      }}>
        {summary.map(([k, v], i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between",
            padding: "5px 10px",
            background: i % 2 ? "transparent" : C.hi,
            borderRadius: 3,
          }}>
            <span style={{ color: C.muted }}>{k}</span>
            <span style={{ fontFamily: "JetBrains Mono", color: C.text }}>{v}</span>
          </div>
        ))}
      </div>
    </>
  );
}