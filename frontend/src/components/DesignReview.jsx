// DesignReview.jsx — Task 7: Persistent Design Review Panel
//
// Replaces the inline checks summary strip in the right column.
// Always visible regardless of which right-column tab is active.
//
// Layout:
//   ┌─────────────────────────────────────────────┐
//   │ DESIGN REVIEW            [PASS 6] [WARN 2]  │
//   ├──────────────────────────────────────────────┤
//   │ ✓ Capacity OK: 130.9 t/h ≥ 100 t/h  §4     │
//   │ ✓ Speed 1.83 m/s within range 1.14–1.91 §6  │
//   │ ✓ CR=1.369 optimal centrifugal range   §3   │
//   │ ⚠ Bearing L10=459k h — acceptable     §4   │
//   │ ✓ Headshaft load 17.5 kN              §4   │
//   │ ℹ Shaft governed by stress: 59.1mm    §4   │
//   └──────────────────────────────────────────────┘
//
// Features:
//   - Always-visible — not hidden behind a tab
//   - Collapsible to a 1-line summary strip (saves space on small screens)
//   - Each check row has: icon, message, CEMA clause tag, expand detail
//   - Filter bar: ALL / FAIL / WARN / OK / INFO
//   - Design maturity indicator: Concept→Preliminary→Detailed→Released
//   - Overall PASS / FAIL verdict badge

import { useState } from "react";

// ── Check type config ─────────────────────────────────────────────────────────
const CHECK = {
  ok:   { icon: "✓", color: "var(--success)", bg: "rgba(16,185,129,.08)",  border: "rgba(16,185,129,.2)",  label: "PASS" },
  warn: { icon: "⚠", color: "var(--warning)", bg: "rgba(245,158,11,.08)",  border: "rgba(245,158,11,.2)",  label: "WARN" },
  fail: { icon: "✗", color: "var(--danger)",  bg: "rgba(239,68,68,.08)",   border: "rgba(239,68,68,.2)",   label: "FAIL" },
  info: { icon: "ℹ", color: "var(--info)",    bg: "rgba(56,189,248,.06)",  border: "rgba(56,189,248,.18)", label: "INFO" },
};

// ── Extract CEMA clause from message tail ─────────────────────────────────────
function extractClause(msg) {
  const m = msg.match(/\[([^\]]+)\]\s*$/);
  return m ? m[1] : null;
}
function stripClause(msg) {
  return msg.replace(/\s*\[[^\]]+\]\s*$/, "");
}

// ── Design maturity from check results ────────────────────────────────────────
function getMaturity(checks) {
  if (!checks || checks.length === 0) return 0;
  const fails  = checks.filter(c => c.type === "fail").length;
  const warns  = checks.filter(c => c.type === "warn").length;
  const okInfo = checks.filter(c => c.type === "ok" || c.type === "info").length;
  const total  = checks.length;
  if (fails > 0) return 1;                              // Concept — has failures
  if (warns > 2) return 2;                              // Preliminary — some warnings
  if (warns > 0) return 3;                              // Detailed — minor warnings
  if (okInfo === total) return 4;                       // Released — all pass
  return 2;
}

const MATURITY = [
  { level: 1, label: "Concept",      color: "var(--danger)"  },
  { level: 2, label: "Preliminary",  color: "var(--warning)" },
  { level: 3, label: "Detailed",     color: "var(--primary)" },
  { level: 4, label: "Released",     color: "var(--success)" },
];

// ── Single check row ──────────────────────────────────────────────────────────
function CheckRow({ check }) {
  const [expanded, setExpanded] = useState(false);
  const cfg     = CHECK[check.type] || CHECK.info;
  const clause  = extractClause(check.msg);
  const message = stripClause(check.msg);

  return (
    <div style={{
      borderRadius: "var(--r-sm)",
      border: `1px solid ${cfg.border}`,
      background: cfg.bg,
      overflow: "hidden",
      margin: "0 0 4px",
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex", alignItems: "flex-start", gap: 7,
          padding: "7px 10px",
          cursor: "pointer",
        }}
      >
        {/* Status icon */}
        <span style={{
          fontSize: 11, color: cfg.color,
          flexShrink: 0, paddingTop: 1, fontWeight: 700,
        }}>{cfg.icon}</span>

        {/* Message */}
        <span style={{
          fontSize: 11, color: "var(--text2)",
          lineHeight: 1.45, flex: 1,
        }}>{message}</span>

        {/* CEMA clause tag */}
        {clause && (
          <span style={{
            fontSize: 9, color: "var(--muted)",
            fontFamily: "JetBrains Mono, monospace",
            letterSpacing: ".03em", flexShrink: 0,
            paddingTop: 1,
          }}>{clause}</span>
        )}

        {/* Expand chevron */}
        <span style={{
          fontSize: 8, color: "var(--faint)", flexShrink: 0,
          paddingTop: 2,
          transform: expanded ? "rotate(180deg)" : "none",
          transition: "transform .15s",
          display: "inline-block",
        }}>▼</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{
          padding: "0 10px 8px 28px",
          fontSize: 10, color: "var(--text3)",
          lineHeight: 1.6, borderTop: `1px solid ${cfg.border}`,
          paddingTop: 6,
        }}>
          <div><span style={{ color: "var(--muted)" }}>Type:</span>{" "}
            <span style={{ color: cfg.color, fontWeight: 600,
              textTransform: "uppercase", fontSize: 9 }}>{check.type}</span>
          </div>
          {clause && (
            <div><span style={{ color: "var(--muted)" }}>Reference:</span>{" "}
              <span style={{ fontFamily: "JetBrains Mono, monospace" }}>{clause}</span>
            </div>
          )}
          <div style={{ marginTop: 4, color: "var(--text3)" }}>
            {message}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function DesignReview({ results }) {
  const [collapsed, setCollapsed] = useState(false);
  const [filter, setFilter]       = useState("all");

  const checks   = results?.checks ?? [];
  const failCount = checks.filter(c => c.type === "fail").length;
  const warnCount = checks.filter(c => c.type === "warn").length;
  const okCount   = checks.filter(c => c.type === "ok").length;
  const infoCount = checks.filter(c => c.type === "info").length;
  const passing   = failCount === 0;
  const maturity  = getMaturity(checks);
  const mat       = MATURITY.find(m => m.level === maturity) || MATURITY[0];

  const filtered = filter === "all"
    ? checks
    : checks.filter(c => c.type === filter);

  const FILTERS = [
    { id: "all",  label: "ALL",  count: checks.length },
    { id: "fail", label: "FAIL", count: failCount },
    { id: "warn", label: "WARN", count: warnCount },
    { id: "ok",   label: "PASS", count: okCount   },
    { id: "info", label: "INFO", count: infoCount  },
  ];

  return (
    <div style={{
      borderBottom: "1px solid var(--border)",
      background: "var(--panel2)",
      flexShrink: 0,
    }}>

      {/* ── Panel header ──────────────────────────────────── */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px",
          cursor: "pointer",
          userSelect: "none",
          borderBottom: collapsed ? "none" : "1px solid var(--border)",
        }}
        onClick={() => setCollapsed(!collapsed)}
      >
        {/* Title */}
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: "var(--text3)",
        }}>Design Review</span>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Overall verdict */}
        {results && (
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: ".05em",
            padding: "2px 8px", borderRadius: "var(--r-pill)",
            background: passing ? "rgba(16,185,129,.15)" : "rgba(239,68,68,.15)",
            color: passing ? "var(--success)" : "var(--danger)",
            border: `1px solid ${passing ? "rgba(16,185,129,.3)" : "rgba(239,68,68,.3)"}`,
          }}>
            {passing ? "✓ PASS" : `✗ ${failCount} FAIL`}
          </span>
        )}

        {/* Warn count */}
        {warnCount > 0 && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "2px 7px",
            borderRadius: "var(--r-pill)",
            background: "rgba(245,158,11,.12)", color: "var(--warning)",
            border: "1px solid rgba(245,158,11,.25)",
          }}>⚠ {warnCount}</span>
        )}

        {/* Collapse chevron */}
        <span style={{
          fontSize: 8, color: "var(--faint)",
          transform: collapsed ? "rotate(-90deg)" : "none",
          transition: "transform .15s", display: "inline-block",
        }}>▼</span>
      </div>

      {/* ── Expanded content ──────────────────────────────── */}
      {!collapsed && (
        <>
          {/* Design maturity bar */}
          {results && (
            <div style={{
              padding: "6px 12px 8px",
              borderBottom: "1px solid var(--border)",
            }}>
              <div style={{
                display: "flex", justifyContent: "space-between",
                alignItems: "center", marginBottom: 5,
              }}>
                <span style={{ fontSize: 9, color: "var(--muted)",
                  letterSpacing: ".06em", textTransform: "uppercase",
                  fontWeight: 600 }}>Design Maturity</span>
                <span style={{ fontSize: 10, fontWeight: 700,
                  color: mat.color }}>{mat.label}</span>
              </div>

              {/* Segmented maturity bar */}
              <div style={{ display: "flex", gap: 3 }}>
                {MATURITY.map((m) => (
                  <div key={m.level} style={{
                    flex: 1, height: 4, borderRadius: 2,
                    background: m.level <= maturity
                      ? mat.color
                      : "var(--surface2)",
                    transition: "background .3s",
                  }} />
                ))}
              </div>

              {/* Maturity labels */}
              <div style={{
                display: "flex", justifyContent: "space-between",
                marginTop: 3,
              }}>
                {MATURITY.map((m) => (
                  <span key={m.level} style={{
                    fontSize: 8,
                    color: m.level <= maturity ? mat.color : "var(--faint)",
                    fontWeight: m.level === maturity ? 700 : 400,
                    letterSpacing: ".03em",
                  }}>{m.label}</span>
                ))}
              </div>
            </div>
          )}

          {/* Filter pills */}
          {results && checks.length > 0 && (
            <div style={{
              display: "flex", gap: 4, padding: "6px 10px",
              borderBottom: "1px solid var(--border)",
              flexWrap: "wrap",
            }}>
              {FILTERS.filter(f => f.id === "all" || f.count > 0).map((f) => {
                const active = filter === f.id;
                const dotColor =
                  f.id === "fail" ? "var(--danger)"  :
                  f.id === "warn" ? "var(--warning)" :
                  f.id === "ok"   ? "var(--success)" :
                  f.id === "info" ? "var(--info)"    : "var(--text3)";
                return (
                  <button
                    key={f.id}
                    onClick={(e) => { e.stopPropagation(); setFilter(f.id); }}
                    style={{
                      display: "flex", alignItems: "center", gap: 4,
                      padding: "2px 8px", borderRadius: "var(--r-pill)",
                      border: `1px solid ${active ? dotColor : "var(--border2)"}`,
                      background: active ? `${dotColor}22` : "transparent",
                      color: active ? dotColor : "var(--muted)",
                      fontSize: 9, fontWeight: 600, cursor: "pointer",
                      letterSpacing: ".05em",
                      transition: "all var(--t-fast)",
                    }}
                  >
                    {f.label}
                    <span style={{
                      fontSize: 9, fontWeight: 700,
                      background: active ? `${dotColor}33` : "var(--surface)",
                      padding: "0 4px", borderRadius: 3,
                      color: active ? dotColor : "var(--muted)",
                    }}>{f.count}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Check list */}
          <div style={{
            padding: "8px 10px",
            maxHeight: 280,
            overflowY: "auto",
          }}>
            {!results ? (
              <div style={{ fontSize: 11, color: "var(--muted)",
                textAlign: "center", padding: "16px 0" }}>
                Calculating…
              </div>
            ) : filtered.length === 0 ? (
              <div style={{ fontSize: 11, color: "var(--muted)",
                textAlign: "center", padding: "12px 0" }}>
                No {filter !== "all" ? filter : ""} checks to show
              </div>
            ) : (
              filtered.map((c, i) => <CheckRow key={i} check={c} />)
            )}
          </div>
        </>
      )}
    </div>
  );
}
