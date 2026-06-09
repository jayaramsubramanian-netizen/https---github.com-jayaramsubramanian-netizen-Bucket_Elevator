// ChuteFlowCard.jsx
// Displays the discharge_chute block produced by ChuteFlowEngine.design_summary()
// integrated in calculations.py v1.4.0.
//
// Block shape:
//   discharge_chute: {
//     performance:     { chute_angle_deg, min_angle_deg, angle_adequate, governed_by,
//                        flow_regime, mass_flow_angle_deg, capacity_check }
//     maintenance:     { wear_index, wear_rating, liner_material, liner_grade,
//                        liner_thickness_mm, plugging_risk, plugging_index,
//                        dust_risk, dust_index }
//     telemetry:       { recommended_sensors[] }
//     recommendations: [ string, ... ]
//     geometry:        { back_plate_angle_deg, spout_width_mm, throw_distance_m,
//                        throat_velocity_mps, plugging_risk, land_x_m, land_y_m }
//     hood_spoon:      { hood_radius_m, hood_angle_deg, spoon_radius_m,
//                        spoon_angle_deg, capture_efficiency }
//   }

function SectionHead({ label }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 700, letterSpacing: ".08em",
      textTransform: "uppercase", color: "var(--text3)",
      padding: "9px 12px 5px",
      borderTop: "1px solid var(--border)",
      background: "var(--panel2)",
    }}>{label}</div>
  );
}

function Row({ label, value, status }) {
  const color =
    status === "ok"   ? "var(--success)"  :
    status === "warn" ? "var(--warning)"  :
    status === "fail" ? "var(--danger)"   :
                        "var(--text2)";
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "baseline",
      padding: "4px 12px", borderBottom: "1px solid var(--border)", minHeight: 26,
    }}>
      <span style={{ fontSize: 10.5, color: "var(--text3)", paddingRight: 8, lineHeight: 1.4 }}>
        {label}
      </span>
      <span style={{
        fontSize: 10.5, fontFamily: "JetBrains Mono, monospace",
        color, textAlign: "right", flexShrink: 0,
      }}>{value ?? "—"}</span>
    </div>
  );
}

const f = (v, dp = 1, suffix = "") =>
  v != null && !Number.isNaN(Number(v))
    ? `${Number(v).toFixed(dp)}${suffix}`
    : "—";

// Colour-coded regime badge
function RegimeBadge({ regime }) {
  const map = {
    MASS_FLOW:    { label: "Mass Flow",    color: "var(--success)", bg: "var(--success-dim,#081a10)", border: "var(--success-border,#1a4a28)" },
    FUNNEL_FLOW:  { label: "Funnel Flow",  color: "var(--warning)", bg: "var(--warning-dim,#1a1205)", border: "var(--warning-border,#4a3005)" },
    PLUGGING_RISK:{ label: "Plugging Risk",color: "var(--danger)",  bg: "var(--danger-dim,#1a0808)",  border: "var(--danger-border,#4a1515)"  },
  };
  const s = map[regime] ?? map.MASS_FLOW;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: "2px 8px",
      borderRadius: "var(--r-pill, 999px)",
      color: s.color, background: s.bg, border: `1px solid ${s.border}`,
    }}>{s.label}</span>
  );
}

// Risk level badge (LOW / MODERATE / HIGH / SEVERE)
function RiskBadge({ level }) {
  const map = {
    LOW:      { color: "var(--success)", bg: "var(--success-dim,#081a10)", border: "var(--success-border,#1a4a28)" },
    MODERATE: { color: "var(--warning)", bg: "var(--warning-dim,#1a1205)", border: "var(--warning-border,#4a3005)" },
    HIGH:     { color: "var(--danger)",  bg: "var(--danger-dim,#1a0808)",  border: "var(--danger-border,#4a1515)"  },
    SEVERE:   { color: "var(--danger)",  bg: "var(--danger-dim,#1a0808)",  border: "var(--danger-border,#4a1515)"  },
  };
  const s = map[level?.toUpperCase?.()] ?? map.LOW;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: "2px 8px",
      borderRadius: "var(--r-pill, 999px)",
      color: s.color, background: s.bg, border: `1px solid ${s.border}`,
    }}>{level ?? "—"}</span>
  );
}

export default function ChuteFlowCard({ results }) {
  if (!results?.discharge_chute) return null;

  const dc   = results.discharge_chute;
  const perf = dc.performance  ?? {};
  const mnt  = dc.maintenance  ?? {};
  const geom = dc.geometry     ?? {};
  const hs   = dc.hood_spoon   ?? {};
  const tele = dc.telemetry    ?? {};
  const recs = dc.recommendations ?? [];

  const regime       = perf.flow_regime ?? "—";
  const angleOk      = perf.angle_adequate ?? true;
  const pluggingRisk = mnt.plugging_risk ?? "LOW";
  const dustRisk     = mnt.dust_risk ?? "LOW";
  const sensors      = tele.recommended_sensors ?? [];

  return (
    <div style={{
      background: "var(--panel)",
      borderRadius: "var(--r-md)",
      border: "1px solid var(--border)",
      overflow: "hidden",
      margin: "10px 12px",
    }}>

      {/* ── Discharge Geometry ── */}
      <SectionHead label="Discharge Chute Geometry  ·  CEMA 375 §5" />
      <Row
        label="Back-plate angle"
        value={f(perf.chute_angle_deg, 1, " deg")}
        status={angleOk ? "ok" : "fail"}
      />
      <Row label="Min angle  (wall friction)" value={f(perf.min_angle_deg, 1, " deg")} />
      <Row label="Governed by"   value={perf.governed_by ?? "—"} />
      <Row label="Spout width"   value={f(geom.spout_width_mm, 0, " mm")} />
      <Row label="Throw distance" value={f(geom.throw_distance_m, 3, " m")} />
      <Row
        label="Throat velocity"
        value={f(geom.throat_velocity_mps, 2, " m/s")}
        status={geom.plugging_risk === "HIGH" ? "warn" : "ok"}
      />

      {/* ── Flow Regime ── */}
      <SectionHead label="Flow Regime" />
      <div style={{
        padding: "8px 12px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid var(--border)",
      }}>
        <span style={{ fontSize: 10.5, color: "var(--text3)" }}>Flow regime</span>
        <RegimeBadge regime={regime} />
      </div>
      <Row label="Mass-flow threshold" value={f(perf.mass_flow_angle_deg, 1, " deg")} />
      <Row label="Angle adequate"
        value={angleOk ? "✓ YES" : "✗ NO — increase angle"}
        status={angleOk ? "ok" : "fail"}
      />

      {/* ── Hood & Spoon Geometry ── */}
      <SectionHead label="Hood & Spoon  (preliminary)" />
      <Row label="Hood radius"       value={f(hs.hood_radius_m, 3, " m")} />
      <Row label="Hood angle"        value={f(hs.hood_angle_deg, 1, " deg")} />
      <Row label="Spoon radius"      value={f(hs.spoon_radius_m, 3, " m")} />
      <Row label="Spoon angle"       value={f(hs.spoon_angle_deg, 1, " deg")} />
      <Row label="Capture efficiency" value={hs.capture_efficiency != null
        ? `${(hs.capture_efficiency * 100).toFixed(0)}%` : "—"} />

      {/* ── Wear & Liner ── */}
      <SectionHead label="Wear & Liner Selection" />
      <Row label="Wear index"     value={`${f(mnt.wear_index, 1)}  (${mnt.wear_rating ?? "—"})`} />
      <Row label="Liner material" value={mnt.liner_material ?? "—"} />
      <Row label="Liner grade"    value={mnt.liner_grade ?? "—"} />
      <Row label="Liner thickness" value={f(mnt.liner_thickness_mm, 0, " mm")} />

      {/* ── Risk Assessment ── */}
      <SectionHead label="Risk Assessment" />
      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)",
        display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 10.5, color: "var(--text3)" }}>Plugging risk</span>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 10, color: "var(--text3)", fontFamily: "JetBrains Mono, monospace" }}>
            idx {f(mnt.plugging_index, 2)}
          </span>
          <RiskBadge level={pluggingRisk} />
        </div>
      </div>
      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)",
        display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 10.5, color: "var(--text3)" }}>Dust risk</span>
        <RiskBadge level={dustRisk} />
      </div>

      {/* ── Telemetry Sensors (if any) ── */}
      {sensors.length > 0 && (
        <>
          <SectionHead label="Recommended Sensors" />
          <div style={{ padding: "8px 12px", display: "flex", flexWrap: "wrap", gap: 4 }}>
            {sensors.map((s, i) => (
              <span key={i} style={{
                fontSize: 9, padding: "2px 8px",
                borderRadius: "var(--r-pill, 999px)",
                background: "var(--primary-dim, #0d1e3a)",
                color: "var(--primary, #4a9eff)",
                border: "1px solid var(--primary-ring, #1a3060)",
                fontFamily: "JetBrains Mono, monospace",
              }}>{s.replace(/_/g, " ")}</span>
            ))}
          </div>
        </>
      )}

      {/* ── Recommendations (if any) ── */}
      {recs.length > 0 && (
        <>
          <SectionHead label="Chute Recommendations" />
          <div style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 5 }}>
            {recs.map((rec, i) => {
              const isCrit  = rec.startsWith("CRITICAL");
              const isWarn  = rec.startsWith("Plugging") || rec.startsWith("Chute") || rec.startsWith("Steepen");
              const color   = isCrit ? "var(--danger)" : isWarn ? "var(--warning)" : "var(--text2)";
              const icon    = isCrit ? "✗" : isWarn ? "⚠" : "→";
              return (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <span style={{ fontSize: 11, color, flexShrink: 0, lineHeight: 1.5 }}>{icon}</span>
                  <span style={{ fontSize: 11, color: "var(--text2)", lineHeight: 1.45 }}>{rec}</span>
                </div>
              );
            })}
          </div>
        </>
      )}

      {recs.length === 0 && (
        <div style={{
          padding: "10px 12px", display: "flex", gap: 10, alignItems: "center",
          borderTop: "1px solid var(--border)",
        }}>
          <span style={{ fontSize: 14, color: "var(--success)" }}>✓</span>
          <span style={{ fontSize: 11, color: "var(--success)" }}>
            No chute design issues — configuration is adequate for this material.
          </span>
        </div>
      )}
    </div>
  );
}