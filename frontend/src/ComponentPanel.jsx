// ComponentPanel.jsx — Belt/Chain, Buckets, Shaft & Bearings, Drive
// Field names match your backend's solve_elevator() return shape.
// All computed variables are inside the guard — never run on undefined data.
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
  { id: "belt", label: "Belt / Chain" },
  { id: "bucket", label: "Buckets" },
  { id: "shaft", label: "Shaft & Bearings" },
  { id: "gearbox", label: "Drive" },
];

const fmt = (v, dp = 2, fb = "—") =>
  v == null || !isFinite(Number(v)) ? fb : Number(v).toFixed(dp);

const fmtDiv = (a, b, dp = 2) => (a == null || !b ? "—" : fmt(a / b, dp));

function Row({ label, value, color }) {
  return (
    <tr>
      <td style={{ color: C.muted }}>{label}</td>
      <td className="mono" style={{ color: color || C.text }}>
        {value}
      </td>
    </tr>
  );
}

export default function ComponentPanel({ results, inputs }) {
  const [tab, setTab] = useState("belt");

  // Guard — wait until results and bucket sub-object are populated
  if (!results || !results.bucket || !inputs) return null;

  // ── Field resolution — backend names first, normalised names as fallback ──
  const bkt = results.bucket;

  // Bucket dims: backend uses W/H/P/V/id, normaliser also adds width_mm etc.
  const bktW = bkt.W ?? bkt.width_mm ?? "—";
  const bktH = bkt.H ?? bkt.depth_mm ?? "—";
  const bktP = bkt.P ?? bkt.projection_mm ?? "—";
  const bktV = bkt.V ?? bkt.volume_L ?? null;
  const bktId = bkt.id ?? bkt.series ?? "—";
  const bktName = bkt.name ?? bkt.style ?? "—";

  // Material: backend returns results.mat, normaliser keeps both mat + material
  const mat = results.mat ?? results.material ?? {};
  const rho =
    results.rho ?? mat.rho_loose ?? mat.rho ?? inputs.custom_rho ?? 1000;

  // Tensions: same keys in backend ✓
  const T1 = results.T1 ?? 0;
  const T2 = results.T2 ?? 0;
  const F_eff = results.F_eff ?? 0;
  const tensionRatio = results.tension_ratio ?? (T2 ? T1 / T2 : null);

  // Belt: backend uses belt_w, normaliser adds belt_width_mm
  const beltW = results.belt_w ?? results.belt_width_mm ?? "—";
  const beltPly = results.belt_ply ?? null;

  // Shaft: backend uses T_Nm / d_mm, normaliser adds shaft_torque_Nm / shaft_d_mm
  const T_Nm = results.T_Nm ?? results.shaft_torque_Nm ?? null;
  const d_mm = results.d_mm ?? results.shaft_d_mm ?? null;

  // Speed: backend uses v, normaliser adds v_ms
  const v_ms = results.v ?? results.v_ms ?? null;

  // Bearing: backend uses L10, normaliser adds L10_hours
  const L10 = results.L10 ?? results.L10_hours ?? null;

  // Power: backend uses P_total, normaliser adds power_P_total
  const P_total = results.P_total ?? results.power_P_total ?? null;

  // Motor: backend uses motor_kw (lowercase)
  const motor_kw = results.motor_kw ?? results.motor_kW ?? "—";

  // Spacing: backend uses spacing, normaliser adds spacing_m
  const spacing = results.spacing ?? results.spacing_m ?? null;

  // ── Derived values (safe — only after guard) ──────────────────
  const fillVol = bktV != null ? (bktV * inputs.fill_pct) / 100 : null;
  const matMass = fillVol != null ? (fillVol * rho) / 1000 : null;
  const emuTheta = Math.exp(
    ((inputs.mu ?? 0.35) * (inputs.wrap_deg ?? 180) * Math.PI) / 180,
  );
  const beltPlyCalc = T1 ? Math.ceil(T1 / 12000) : null;
  const chainPitch = T1 < 20000 ? 63.5 : T1 < 50000 ? 101.6 : 152.4;
  const slipRisk = tensionRatio != null && tensionRatio > emuTheta;

  // Abrasiveness: backend abr_code is 1–7 numeric
  const abrCode = mat.abr_code ?? 0;
  const abrLabel =
    abrCode >= 6
      ? "Highly abrasive"
      : abrCode >= 4
        ? "Abrasive"
        : abrCode >= 2
          ? "Mildly abrasive"
          : "Non-abrasive";
  const abrColor = abrCode >= 6 ? C.red : abrCode >= 4 ? C.amber : C.green;

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

      <div
        style={{
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {/* ── BELT / CHAIN ── */}
        {tab === "belt" && (
          <>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>
              Belt Design — CEMA Standards
            </div>
            <table className="data-table">
              <tbody>
                <Row
                  label="Belt Width"
                  value={beltW !== "—" ? `${beltW} mm` : "—"}
                />
                <Row
                  label="Effective Tension"
                  value={`${fmtDiv(F_eff, 1000)} kN`}
                />
                <Row
                  label="Tight Side T₁"
                  value={`${fmtDiv(T1, 1000)} kN`}
                  color={T1 > 50000 ? C.red : C.text}
                />
                <Row label="Slack Side T₂" value={`${fmtDiv(T2, 1000)} kN`} />
                <Row label="Tension Ratio" value={fmt(tensionRatio, 3)} />
                <Row label="Slip Limit e^(μθ)" value={fmt(emuTheta, 3)} />
                <Row
                  label="Recommended Ply Rating"
                  value={
                    beltPly
                      ? `${beltPly} PLY`
                      : beltPlyCalc
                        ? `${beltPlyCalc} PLY (est.)`
                        : "—"
                  }
                  color={C.blue}
                />
                <Row
                  label="Chain Pitch (if chain)"
                  value={`${chainPitch} mm`}
                />
              </tbody>
            </table>
            <div className="warn-item w-info" style={{ fontSize: 10 }}>
              ℹ Belt tension ratio should be ≤ {fmt(emuTheta, 3)} to prevent
              slip (μ={inputs.mu}, θ={inputs.wrap_deg}°).
              {slipRisk ? (
                <span style={{ color: C.red, marginLeft: 6 }}>⚠ SLIP RISK</span>
              ) : (
                <span style={{ color: C.green, marginLeft: 6 }}>✓ No slip</span>
              )}
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
                <Row
                  label="Series"
                  value={`${bktId} — ${bktName}`}
                  color={C.blue}
                />
                <Row label="Width × Height" value={`${bktW} × ${bktH} mm`} />
                <Row label="Projection (P)" value={`${bktP} mm`} />
                <Row label="Volume (struck)" value={`${bktV ?? "—"} L`} />
                <Row label="Fill Factor" value={`${inputs.fill_pct}%`} />
                <Row
                  label="Active Volume"
                  value={fillVol != null ? `${fillVol.toFixed(3)} L` : "—"}
                />
                <Row
                  label="Mass per Bucket"
                  value={
                    matMass != null
                      ? `${(matMass * 1000).toFixed(1)} g (${mat.name ?? "Custom"})`
                      : "—"
                  }
                />
                <Row
                  label="Spacing"
                  value={
                    spacing != null ? `${(spacing * 1000).toFixed(0)} mm` : "—"
                  }
                />
                <Row
                  label="Buckets per metre"
                  value={spacing ? (1 / spacing).toFixed(2) : "—"}
                />
                <Row
                  label="Abrasiveness"
                  value={`${abrCode}/7 — ${abrLabel}`}
                  color={abrColor}
                />
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
              <div
                style={{
                  fontSize: 9,
                  color: C.muted,
                  marginTop: 3,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
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
                <Row
                  label="Shaft Torque"
                  value={`${fmtDiv(T_Nm, 1000, 3)} kNm`}
                />
                <Row
                  label="Min Shaft Dia (torsion)"
                  value={`${fmt(d_mm, 1)} mm`}
                  color={C.blue}
                />
                <Row
                  label="Governed by"
                  value={results.governed_by ?? "torsion"}
                />
                <Row
                  label="Allowable Shear Stress"
                  value="55 MPa (mild steel)"
                />
                <Row label="Head Pulley Dia" value={`${inputs.D_mm} mm`} />
                <Row label="Belt Speed" value={`${fmt(v_ms, 3)} m/s`} />
                <Row label="Head Shaft RPM" value={`${inputs.n_rpm} rpm`} />
                <Row
                  label="Bearing L10 Life"
                  value={`${fmt(L10, 0)} h`}
                  color={(L10 ?? 0) < 20000 ? C.amber : C.green}
                />
              </tbody>
            </table>
            <div
              className="warn-item w-info"
              style={{ fontSize: 10, marginTop: 6 }}
            >
              ℹ Shaft sizing uses pure torsion. Add 15–20% for keyway stress
              concentration and combined bending loads in detailed design.
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
                <Row label="Required Power" value={`${fmt(P_total, 2)} kW`} />
                <Row label="Service Factor" value={inputs.sf} />
                <Row
                  label="Design Power"
                  value={`${fmt((P_total ?? 0) * (inputs.sf ?? 1.25), 2)} kW`}
                />
                <Row
                  label="Selected Motor"
                  value={`${motor_kw} kW`}
                  color={C.green}
                />
                <Row label="Head Shaft Speed" value={`${inputs.n_rpm} rpm`} />
                <Row
                  label="Head Shaft Torque"
                  value={`${fmtDiv(T_Nm, 1000, 3)} kNm`}
                />
                <Row label="Typical Motor Speed" value="1450 rpm (4P)" />
                <Row
                  label="Required Ratio"
                  value={`${(1450 / (inputs.n_rpm || 1)).toFixed(1)} : 1`}
                />
              </tbody>
            </table>
            <div
              className="warn-item w-ok"
              style={{ marginTop: 6, fontSize: 10 }}
            >
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
