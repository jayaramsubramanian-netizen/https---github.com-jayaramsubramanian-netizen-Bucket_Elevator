// MaintenanceCard.jsx — Reliability & Maintenance Schedule
// Displays schedule (periodic tasks) and replacements (life-based)
// from the reliability.py output.

import { useState } from "react";

const PRIORITY_STYLE = {
  CRITICAL: {
    color: "var(--danger)",
    bg: "rgba(224,82,82,.10)",
    label: "CRITICAL",
  },
  ROUTINE: { color: "var(--text3)", bg: "transparent", label: "ROUTINE" },
  ADVISORY: {
    color: "var(--primary)",
    bg: "rgba(74,158,255,.08)",
    label: "ADVISORY",
  },
};

const CAT_ICON = {
  LUBRICATION: "🛢",
  INSPECTION: "🔍",
  ADJUSTMENT: "🔧",
  CLEANING: "🧹",
};

function fmt(v, dp = 0) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: dp });
}

function KpiTile({ label, value, unit, color }) {
  return (
    <div
      style={{
        flex: 1,
        padding: "7px 8px",
        background: "var(--panel2)",
        borderRadius: 5,
        border: "1px solid var(--border)",
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: 7.5,
          color: "var(--text3)",
          letterSpacing: ".05em",
          textTransform: "uppercase",
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "JetBrains Mono,monospace",
          fontSize: 14,
          fontWeight: 700,
          color: color || "var(--primary)",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 8,
          color: "var(--muted)",
          fontFamily: "JetBrains Mono,monospace",
        }}
      >
        {unit}
      </div>
    </div>
  );
}

export default function MaintenanceCard({ results }) {
  const maint = results?.maintenance;
  const [tab, setTab] = useState("schedule");

  if (!maint) {
    return (
      <div style={{ padding: 12, fontSize: 10, color: "var(--text3)" }}>
        Maintenance schedule not available — run calculation first.
      </div>
    );
  }

  const { schedule, replacements, kpis, notes } = maint;

  // Sort schedule by interval
  const sorted = [...(schedule || [])].sort(
    (a, b) => a.interval_h - b.interval_h,
  );

  return (
    <div style={{ borderTop: "1px solid var(--border)" }}>
      {/* Header */}
      <div
        style={{
          padding: "10px 12px 6px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: ".08em",
            textTransform: "uppercase",
            color: "var(--text3)",
          }}
        >
          Reliability & Maintenance
        </span>
      </div>

      {/* KPI strip */}
      <div
        style={{
          display: "flex",
          gap: 5,
          padding: "8px 12px",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <KpiTile
          label="Bearing L10"
          value={fmt(kpis?.L10_hours)}
          unit="hours"
          color="var(--primary)"
        />
        <KpiTile
          label="Belt Life Est."
          value={fmt(kpis?.belt_life_h)}
          unit="hours"
          color="var(--warning)"
        />
        <KpiTile
          label="Grease Interval"
          value={fmt(kpis?.grease_interval_h)}
          unit="hours"
          color="var(--success)"
        />
        <KpiTile
          label="Min Repl. Interval"
          value={fmt(kpis?.mtbf_h)}
          unit="hours"
          color={kpis?.mtbf_h < 8000 ? "var(--danger)" : "var(--text2)"}
        />
      </div>

      {/* Tab strip */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border)",
          background: "var(--panel2)",
          padding: "0 12px",
        }}
      >
        {[
          { id: "schedule", label: `Schedule (${schedule?.length ?? 0})` },
          {
            id: "replacement",
            label: `Replacements (${replacements?.length ?? 0})`,
          },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: "6px 12px",
              fontSize: 10,
              fontWeight: tab === t.id ? 600 : 400,
              cursor: "pointer",
              border: "none",
              background: "transparent",
              color: tab === t.id ? "var(--primary)" : "var(--text3)",
              borderBottom: `2px solid ${tab === t.id ? "var(--primary)" : "transparent"}`,
              marginBottom: -1,
              fontFamily: "inherit",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Periodic maintenance schedule */}
      {tab === "schedule" && (
        <div>
          {sorted.map((item, i) => {
            const ps = PRIORITY_STYLE[item.priority] || PRIORITY_STYLE.ROUTINE;
            const icon = CAT_ICON[item.category] || "•";
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 10,
                  padding: "7px 12px",
                  borderBottom: "1px solid var(--border)",
                  background:
                    i % 2 === 0 ? "transparent" : "rgba(255,255,255,.015)",
                }}
              >
                {/* Interval badge */}
                <div
                  style={{
                    flexShrink: 0,
                    width: 52,
                    textAlign: "center",
                    padding: "4px 2px",
                    background: ps.bg,
                    border: `1px solid ${ps.color}30`,
                    borderRadius: 4,
                  }}
                >
                  <div
                    style={{
                      fontFamily: "JetBrains Mono,monospace",
                      fontSize: 11,
                      fontWeight: 700,
                      color: ps.color,
                    }}
                  >
                    {fmt(item.interval_h)}
                  </div>
                  <div style={{ fontSize: 7, color: "var(--text3)" }}>h</div>
                  <div style={{ fontSize: 7, color: "var(--text3)" }}>
                    ~{item.interval_wk}wk
                  </div>
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      marginBottom: 2,
                    }}
                  >
                    <span style={{ fontSize: 10 }}>{icon}</span>
                    <span
                      style={{
                        fontSize: 9.5,
                        color: "var(--text)",
                        fontWeight: 600,
                        flex: 1,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.task}
                    </span>
                    {item.priority === "CRITICAL" && (
                      <span
                        style={{
                          fontSize: 7,
                          fontWeight: 700,
                          padding: "1px 5px",
                          borderRadius: 999,
                          background: "var(--danger-dim)",
                          color: "var(--danger)",
                          border: "1px solid var(--danger-border)",
                          flexShrink: 0,
                        }}
                      >
                        CRITICAL
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 8.5, color: "var(--text3)" }}>
                    {item.component}
                  </div>
                  <div
                    style={{ fontSize: 8, color: "var(--muted)", marginTop: 1 }}
                  >
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
            const ps = PRIORITY_STYLE[item.priority] || PRIORITY_STYLE.ROUTINE;
            const yrs = item.estimated_life_yr;
            return (
              <div
                key={i}
                style={{
                  padding: "8px 12px",
                  borderBottom: "1px solid var(--border)",
                  background:
                    i % 2 === 0 ? "transparent" : "rgba(255,255,255,.015)",
                }}
              >
                {/* Component + life */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                    gap: 8,
                    marginBottom: 3,
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--text)",
                      flex: 1,
                    }}
                  >
                    {item.component}
                  </span>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div
                      style={{
                        fontFamily: "JetBrains Mono,monospace",
                        fontSize: 12,
                        fontWeight: 700,
                        color:
                          item.priority === "CRITICAL"
                            ? "var(--danger)"
                            : "var(--warning)",
                      }}
                    >
                      {fmt(item.estimated_life_h)}h
                    </div>
                    <div style={{ fontSize: 8, color: "var(--text3)" }}>
                      ≈ {yrs} yr
                    </div>
                  </div>
                </div>
                {/* Action */}
                <div
                  style={{
                    fontSize: 9,
                    color: "var(--primary)",
                    fontWeight: 600,
                    marginBottom: 2,
                  }}
                >
                  {item.action}
                </div>
                {/* Spec */}
                <div
                  style={{
                    fontSize: 8.5,
                    color: "var(--text3)",
                    marginBottom: 2,
                  }}
                >
                  {item.material_spec}
                </div>
                {/* Notes */}
                <div style={{ fontSize: 8, color: "var(--muted)" }}>
                  {item.notes}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Notes */}
      <div
        style={{
          padding: "6px 12px 10px",
          borderTop: "1px solid var(--border)",
        }}
      >
        {(notes || []).map((n, i) => (
          <div
            key={i}
            style={{
              fontSize: 8,
              color: "var(--text3)",
              marginBottom: 2,
              lineHeight: 1.4,
            }}
          >
            * {n}
          </div>
        ))}
      </div>
    </div>
  );
}
