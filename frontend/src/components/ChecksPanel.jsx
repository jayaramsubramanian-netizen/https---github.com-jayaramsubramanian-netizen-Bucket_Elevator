// ChecksPanel.jsx — engineering checks, warnings, and design summary
// Pure display component — all data from results dict, no recomputation.
// Field names match backend's solve_elevator() return shape.
const C = {
  muted: "var(--text3)", hi: "var(--surface)", text: "var(--text)",
};

const fmt = (v, dp = 2, fb = "—") =>
  v == null || !isFinite(Number(v)) ? fb : Number(v).toFixed(dp);

export default function ChecksPanel({ results, inputs }) {
  if (!results || !inputs) return null;

  const mat     = results.mat      ?? results.material ?? {};
  const bkt     = results.bucket   ?? {};
  const rho     = results.rho      ?? mat.rho_loose ?? mat.rho ?? inputs.custom_rho ?? "—";

  const Q       = results.Q        ?? results.Q_th        ?? null;
  const v       = results.v        ?? results.v_ms        ?? null;
  const belt_w  = results.belt_w   ?? results.belt_width_mm ?? "—";
  const P_lift  = results.P_lift   ?? results.power_P_lift  ?? null;
  const P_total = results.P_total  ?? results.power_P_total ?? null;
  const motor   = results.motor_kw ?? results.motor_kW      ?? "—";
  const d_mm    = results.d_mm     ?? results.shaft_d_mm    ?? null;
  const cr      = results.cr       ?? results.centrifugal_ratio ?? null;
  const theta   = results.theta_rel ?? results.release_angle_deg ?? null;
  const bktId   = bkt.id          ?? bkt.series    ?? "—";
  const bktV    = bkt.V           ?? bkt.volume_L  ?? "—";

  const checks  = results.checks ?? [];
  const getStatus = (c) => c.status ?? (c.type === "ok" ? "pass" : c.type) ?? "info";
  const iconMap   = { pass: "✓", ok: "✓", warn: "⚠", fail: "✗", info: "ℹ" };
  const classMap  = { pass: "w-ok", ok: "w-ok", warn: "w-warn", fail: "w-fail", info: "w-info" };

  const summary = [
    ["Material",           mat.name              ?? inputs.mat_id ?? "—"],
    ["Density",            `${rho} kg/m³`],
    ["Lift Height",        `${inputs.H_m} m`],
    ["Required Capacity",  `${inputs.Q_req} t/h`],
    ["Achieved Capacity",  `${fmt(Q, 1)} t/h`],
    ["Belt Speed",         `${fmt(v, 3)} m/s`],
    ["Head Pulley Dia.",   `${inputs.D_mm} mm @ ${inputs.n_rpm} rpm`],
    ["Bucket Series",      `${bktId} — ${bktV}L`],
    ["Belt Width",         `${belt_w} mm`],
    ["Lift Power",         `${fmt(P_lift, 2)} kW`],
    ["Total Power",        `${fmt(P_total, 2)} kW`],
    ["Motor",              `${motor} kW`],
    ["Material Component  T1",  `${fmt(results.T1 != null ? results.T1 / 1000 : null, 2)} kN`],
    ["Self-Weight Comp.  T2",   `${fmt(results.T2 != null ? results.T2 / 1000 : null, 2)} kN`],
    ["Take-up / Slack  T3",     `${fmt(results.T3 != null ? results.T3 / 1000 : null, 2)} kN`],
    ["Belt Tight Side (T3+Feff)", `${fmt((results.T3 != null && results.F_eff != null) ? (results.T3 + results.F_eff) / 1000 : null, 2)} kN`],
    ["Min Shaft Dia.",     `${fmt(d_mm, 1)} mm`],
    ["Shaft Material",     results.shaft_material_name ?? "—"],
    ["Shaft Section",      results.shaft_section ?? "—"],
    ["Hub Connection",     results.shaft_hub_connection ?? "—"],
    ["Centrifugal Ratio",  fmt(cr, 3)],
    ["Discharge Angle",    `${fmt(theta, 1)}° from vertical`],
    ["Belt Length",        results.belt_length_total_m != null ? `${results.belt_length_total_m} m` : "—"],
    ["Bucket Count",       results.n_buckets != null ? `${results.n_buckets} off` : "—"],
  ];

  return (
    <>
      {/* Engineering Checks */}
      <div className="warn-panel">
        {checks.length === 0 && (
          <div className="warn-item w-info">
            <span>ℹ</span><span>No checks available yet.</span>
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