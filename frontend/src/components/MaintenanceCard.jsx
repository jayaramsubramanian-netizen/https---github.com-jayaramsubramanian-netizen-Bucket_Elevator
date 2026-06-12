// MaintenanceCard.jsx — Redesigned for readability
//
// CHANGES FROM ORIGINAL
// ──────────────────────
// 1. KPI strip: 1×4 cramped row → 2×2 grid, larger text (14px → 16px values)
// 2. Schedule rows: increased padding, larger task name (9.5px → 12px),
//    secondary info given its own line with clearer hierarchy
// 3. Interval badge: 52px → 60px, larger numerals
// 4. Replacement cards: more breathing room, clearer life/action separation
// 5. All base font sizes raised from 7-9.5px range to 10-13px range

import { useState } from "react";

const PRIORITY_STYLE = {
  CRITICAL: { color: "var(--danger)",  bg: "rgba(239,68,68,.08)",  label: "CRITICAL" },
  ROUTINE:  { color: "var(--text3)",   bg: "transparent",          label: "ROUTINE"  },
  ADVISORY: { color: "var(--primary)", bg: "rgba(59,130,246,.06)", label: "ADVISORY" },
};

const CAT_ICON = {
  LUBRICATION: "🛢",
  INSPECTION:  "🔍",
  ADJUSTMENT:  "🔧",
  CLEANING:    "🧹",
};

function fmt(v, dp = 0) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: dp });
}

function KpiTile({ label, value, unit, color }) {
  return (
    <div style={{
      padding: "10px 10px",
      background: "var(--panel2)",
      borderRadius: "var(--r-md)",
      border: "1px solid var(--border)",
      textAlign: "center",
    }}>
      <div style={{
        fontSize: 9, color: "var(--text3)", letterSpacing: ".06em",
        textTransform: "uppercase", marginBottom: 4, fontWeight: 600,
      }}>{label}</div>
      <div style={{
        fontFamily: "JetBrains Mono, monospace", fontSize: 17, fontWeight: 700,
        color: color || "var(--primary)", lineHeight: 1.2,
      }}>{value}</div>
      <div style={{
        fontSize: 10, color: "var(--muted)",
        fontFamily: "JetBrains Mono, monospace",
      }}>{unit}</div>
    </div>
  );
}

export default function MaintenanceCard({ results }) {
  const maint = results?.maintenance;
  const [tab, setTab] = useState("schedule");

  if (!maint) {
    return (
      <div style={{ padding: 16, fontSize: 11, color: "var(--text3)" }}>
        Maintenance schedule not available — run calculation first.
      </div>
    );
  }

  const { schedule, replacements, kpis, notes } = maint;
  const sorted = [...(schedule || [])].sort((a, b) => a.interval_h - b.interval_h);

  return (
    <div style={{ borderTop: "1px solid var(--border)" }}>

      {/* Header */}
      <div style={{ padding: "12px 14px 8px", borderBottom: "1px solid var(--border)" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: "var(--text3)" }}>
          Reliability &amp; Maintenance
        </span>
      </div>

      {/* KPI grid — 2×2 instead of 1×4 */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
        padding: "12px 14px", borderBottom: "1px solid var(--border)",
      }}>
        <KpiTile label="Bearing L10"     value={fmt(kpis?.L10_hours)}        unit="hours" color="var(--primary)" />
        <KpiTile label="Belt Life Est."  value={fmt(kpis?.belt_life_h)}      unit="hours" color="var(--warning)" />
        <KpiTile label="Grease Interval" value={fmt(kpis?.grease_interval_h)} unit="hours" color="var(--success)" />
        <KpiTile label="Min Repl. Interval" value={fmt(kpis?.mtbf_h)} unit="hours"
          color={kpis?.mtbf_h < 8000 ? "var(--danger)" : "var(--text2)"} />
      </div>

      {/* Tab strip */}
      <div style={{
        display: "flex", borderBottom: "1px solid var(--border)",
        background: "var(--panel2)", padding: "0 14px",
      }}>
        {[
          { id: "schedule",    label: `Schedule (${schedule?.length ?? 0})` },
          { id: "replacement", label: `Replacements (${replacements?.length ?? 0})` },
        ].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "9px 14px", fontSize: 12, fontWeight: tab === t.id ? 600 : 400,
            cursor: "pointer", border: "none", background: "transparent",
            color: tab === t.id ? "var(--primary)" : "var(--text3)",
            borderBottom: `2px solid ${tab === t.id ? "var(--primary)" : "transparent"}`,
            marginBottom: -1, fontFamily: "var(--ff-ui)",
            transition: "color var(--t-base)",
          }}>{t.label}</button>
        ))}
      </div>

      {/* Periodic maintenance schedule */}
      {tab === "schedule" && (
        <div>
          {sorted.map((item, i) => {
            const ps   = PRIORITY_STYLE[item.priority] || PRIORITY_STYLE.ROUTINE;
            const icon = CAT_ICON[item.category] || "•";
            return (
              <div key={i} style={{
                display: "flex", gap: 12, padding: "12px 14px",
                borderBottom: "1px solid var(--border)",
                background: i % 2 === 0 ? "transparent" : "var(--panel2)",
              }}>
                {/* Interval badge — larger */}
                <div style={{
                  flexShrink: 0, width: 64, textAlign: "center",
                  padding: "8px 4px", background: ps.bg,
                  border: `1px solid ${ps.color}30`,
                  borderRadius: "var(--r-md)",
                }}>
                  <div style={{
                    fontFamily: "JetBrains Mono, monospace", fontSize: 15,
                    fontWeight: 700, color: ps.color, lineHeight: 1.1,
                  }}>{fmt(item.interval_h)}</div>
                  <div style={{ fontSize: 9, color: "var(--text3)" }}>hours</div>
                  <div style={{ fontSize: 9, color: "var(--text3)", marginTop: 2 }}>
                    ~{item.interval_wk}wk
                  </div>
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8,
                    marginBottom: 4 }}>
                    <span style={{ fontSize: 14 }}>{icon}</span>
                    <span style={{
                      fontSize: 12, color: "var(--text)", fontWeight: 700,
                      flex: 1, lineHeight: 1.4,
                    }}>{item.task}</span>
                    {item.priority === "CRITICAL" && (
                      <span style={{
                        fontSize: 9, fontWeight: 700, padding: "2px 7px",
                        borderRadius: 999, background: "var(--danger-dim)",
                        color: "var(--danger)", border: "1px solid var(--danger-border)",
                        flexShrink: 0,
                      }}>CRITICAL</span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text2)", marginBottom: 2 }}>
                    {item.component}
                  </div>
                  <div style={{ fontSize: 10.5, color: "var(--muted)", lineHeight: 1.5 }}>
                    {item.trigger}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Replacements */}
      {tab === "replacement" && (
        <div>
          {(replacements || []).map((item, i) => {
            const yrs = item.estimated_life_yr;
            return (
              <div key={i} style={{
                padding: "12px 14px",
                borderBottom: "1px solid var(--border)",
                background: i % 2 === 0 ? "transparent" : "var(--panel2)",
              }}>
                {/* Component + life */}
                <div style={{
                  display: "flex", alignItems: "flex-start",
                  justifyContent: "space-between", gap: 10, marginBottom: 6,
                }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text)", flex: 1 }}>
                    {item.component}
                  </span>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div style={{
                      fontFamily: "JetBrains Mono, monospace", fontSize: 15, fontWeight: 700,
                      color: item.priority === "CRITICAL" ? "var(--danger)" : "var(--warning)",
                    }}>{fmt(item.estimated_life_h)}h</div>
                    <div style={{ fontSize: 10, color: "var(--text3)" }}>≈ {yrs} yr</div>
                  </div>
                </div>
                {/* Action */}
                <div style={{ fontSize: 11.5, color: "var(--primary)", fontWeight: 600, marginBottom: 4 }}>
                  {item.action}
                </div>
                {/* Spec */}
                <div style={{ fontSize: 10.5, color: "var(--text3)", marginBottom: 4, lineHeight: 1.5 }}>
                  {item.material_spec}
                </div>
                {/* Notes */}
                <div style={{ fontSize: 10.5, color: "var(--muted)", lineHeight: 1.5 }}>
                  {item.notes}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Notes */}
      <div style={{ padding: "10px 14px 14px", borderTop: "1px solid var(--border)" }}>
        {(notes || []).map((n, i) => (
          <div key={i} style={{ fontSize: 10.5, color: "var(--text3)",
            marginBottom: 4, lineHeight: 1.6 }}>
            * {n}
          </div>
        ))}
      </div>
    </div>
  );
}