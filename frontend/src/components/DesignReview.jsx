// DesignReview.jsx  v2.0.0
// Persistent design review panel for VECTRIX™ bucket elevator.
//
// v2.0.0 changes from v1.0:
//   • Manual stage advancement — Concept → Preliminary → Detailed → Released
//   • Advancement gated: 0 FAILs required to advance; warns on WARNs
//   • Stage auto-regresses to Concept when FAILs appear
//   • Stage is persisted in component state (parent can lift up if needed)
//   • "Advance Design" button shows requirement and gate status
//   • Stage is annotated with timestamp when manually advanced

import { useState, useEffect } from "react";

const CHECK = {
  ok:   { icon: "✓", color: "var(--success)", bg: "rgba(16,185,129,.08)",  border: "rgba(16,185,129,.2)",  label: "PASS" },
  warn: { icon: "⚠", color: "var(--warning)", bg: "rgba(245,158,11,.08)",  border: "rgba(245,158,11,.2)",  label: "WARN" },
  fail: { icon: "✗", color: "var(--danger)",  bg: "rgba(239,68,68,.08)",   border: "rgba(239,68,68,.2)",   label: "FAIL" },
  info: { icon: "ℹ", color: "var(--info)",    bg: "rgba(56,189,248,.06)",  border: "rgba(56,189,248,.18)", label: "INFO" },
};

function extractClause(msg) {
  const m = msg.match(/\[([^\]]+)\]\s*$/);
  return m ? m[1] : null;
}
function stripClause(msg) {
  return msg.replace(/\s*\[[^\]]+\]\s*$/, "");
}

// ── Stage definitions ─────────────────────────────────────────────────────────
const STAGES = [
  {
    level: 1, label: "Concept", color: "var(--danger)",
    desc: "Has FAILs — not suitable for procurement",
    gate: "Resolve all FAILs to advance",
    autoLabel: "Auto — FAILs present",
  },
  {
    level: 2, label: "Preliminary", color: "var(--warning)",
    desc: "No FAILs — suitable for budgetary purposes",
    gate: "Resolve all WARNs to advance",
    autoLabel: "Auto — WARNs present",
  },
  {
    level: 3, label: "Detailed", color: "var(--primary)",
    desc: "No FAILs or WARNs — suitable for detailed engineering",
    gate: "All checks PASS — advance to Released to freeze design",
    autoLabel: "Auto — all checks clean",
  },
  {
    level: 4, label: "Released", color: "var(--success)",
    desc: "Design frozen — suitable for fabrication and procurement",
    gate: "Design released",
    autoLabel: "Manual advance",
  },
];

function computeAutoStage(checks) {
  if (!checks?.length) return 1;
  if (checks.some(c => c.type === "fail")) return 1;
  if (checks.some(c => c.type === "warn")) return 2;
  return 3;    // all pass/info — can be advanced to Released manually
}

function CheckRow({ check }) {
  const [expanded, setExpanded] = useState(false);
  const cfg     = CHECK[check.type] || CHECK.info;
  const clause  = extractClause(check.msg);
  const message = stripClause(check.msg);

  return (
    <div style={{
      borderRadius: "var(--r-sm, 4px)",
      border: `1px solid ${cfg.border}`,
      background: cfg.bg,
      overflow: "hidden",
      margin: "0 0 4px",
    }}>
      <div onClick={() => setExpanded(!expanded)} style={{
        display: "flex", alignItems: "flex-start", gap: 7,
        padding: "7px 10px", cursor: "pointer",
      }}>
        <span style={{ fontSize: 11, color: cfg.color,
          flexShrink: 0, paddingTop: 1, fontWeight: 700 }}>{cfg.icon}</span>
        <span style={{ fontSize: 11, color: "var(--text2)", lineHeight: 1.45, flex: 1 }}>
          {message}
        </span>
        {clause && (
          <span style={{ fontSize: 9, color: "var(--muted)",
            fontFamily: "JetBrains Mono, monospace", letterSpacing: ".03em",
            flexShrink: 0, paddingTop: 1 }}>{clause}</span>
        )}
        <span style={{ fontSize: 8, color: "var(--faint)", flexShrink: 0,
          paddingTop: 2, transform: expanded ? "rotate(180deg)" : "none",
          transition: "transform .15s", display: "inline-block" }}>▼</span>
      </div>
      {expanded && (
        <div style={{ padding: "0 10px 8px 28px", fontSize: 10,
          color: "var(--text3)", lineHeight: 1.6,
          borderTop: `1px solid ${cfg.border}`, paddingTop: 6 }}>
          <div><span style={{ color: "var(--muted)" }}>Type:</span>{" "}
            <span style={{ color: cfg.color, fontWeight: 600,
              textTransform: "uppercase", fontSize: 9 }}>{check.type}</span>
          </div>
          {clause && (
            <div><span style={{ color: "var(--muted)" }}>Reference:</span>{" "}
              <span style={{ fontFamily: "JetBrains Mono, monospace" }}>{clause}</span>
            </div>
          )}
          <div style={{ marginTop: 4, color: "var(--text3)" }}>{message}</div>
        </div>
      )}
    </div>
  );
}

export default function DesignReview({ results, onStageChange }) {
  const [collapsed,       setCollapsed]       = useState(false);
  const [filter,          setFilter]          = useState("all");
  const [manualStage,     setManualStage]     = useState(null);   // null = auto
  const [advancedAt,      setAdvancedAt]      = useState(null);   // ISO timestamp

  const checks    = results?.checks ?? [];
  const failCount = checks.filter(c => c.type === "fail").length;
  const warnCount = checks.filter(c => c.type === "warn").length;
  const okCount   = checks.filter(c => c.type === "ok").length;
  const infoCount = checks.filter(c => c.type === "info").length;
  const passing   = failCount === 0;

  // Compute auto stage; manual stage only sticks if no regressions
  const autoStage = computeAutoStage(checks);

  // Auto-regress if FAILs appear after manual advance
  const effectiveStage = (() => {
    if (manualStage === null) return autoStage;
    if (failCount > 0) return 1;                        // always regress on FAIL
    if (warnCount > 0 && manualStage > 2) return 2;    // regress past Preliminary on WARN
    return Math.max(manualStage, autoStage);            // never regress below auto
  })();

  // Notify parent if provided
  useEffect(() => {
    onStageChange?.(effectiveStage);
  }, [effectiveStage, onStageChange]);

  const stage = STAGES.find(s => s.level === effectiveStage) || STAGES[0];

  // Can we advance?
  const nextLevel   = effectiveStage + 1;
  const canAdvance  = nextLevel <= 4 && failCount === 0 && (nextLevel < 4 ? warnCount === 0 : true);
  const nextStage   = STAGES.find(s => s.level === nextLevel);

  function handleAdvance() {
    if (!canAdvance) return;
    setManualStage(nextLevel);
    setAdvancedAt(new Date().toISOString().slice(0, 16).replace("T", " "));
  }

  const filtered = filter === "all"
    ? checks
    : checks.filter(c => c.type === filter);

  const FILTERS = [
    { id: "all",  label: "ALL",  count: checks.length },
    { id: "fail", label: "FAIL", count: failCount },
    { id: "warn", label: "WARN", count: warnCount },
    { id: "ok",   label: "PASS", count: okCount },
    { id: "info", label: "INFO", count: infoCount },
  ];

  return (
    <div style={{ borderBottom: "1px solid var(--border)", background: "var(--panel2)", flexShrink: 0 }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div onClick={() => setCollapsed(!collapsed)} style={{
        display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
        cursor: "pointer", userSelect: "none",
        borderBottom: collapsed ? "none" : "1px solid var(--border)",
      }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: "var(--text3)" }}>Design Review</span>
        <div style={{ flex: 1 }} />
        {results && (
          <span style={{
            fontSize: 9, fontWeight: 700, letterSpacing: ".05em",
            padding: "2px 8px", borderRadius: "var(--r-pill, 999px)",
            background: passing ? "rgba(16,185,129,.15)" : "rgba(239,68,68,.15)",
            color: passing ? "var(--success)" : "var(--danger)",
            border: `1px solid ${passing ? "rgba(16,185,129,.3)" : "rgba(239,68,68,.3)"}`,
          }}>
            {passing ? "✓ PASS" : `✗ ${failCount} FAIL`}
          </span>
        )}
        {warnCount > 0 && (
          <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px",
            borderRadius: "var(--r-pill, 999px)",
            background: "rgba(245,158,11,.12)", color: "var(--warning)",
            border: "1px solid rgba(245,158,11,.25)" }}>⚠ {warnCount}</span>
        )}
        <span style={{ fontSize: 8, color: "var(--faint)",
          transform: collapsed ? "rotate(-90deg)" : "none",
          transition: "transform .15s", display: "inline-block" }}>▼</span>
      </div>

      {!collapsed && (
        <>
          {/* ── Design Maturity ────────────────────────────────────────────── */}
          {results && (
            <div style={{ padding: "8px 12px 0", borderBottom: "1px solid var(--border)" }}>

              {/* Stage header */}
              <div style={{ display: "flex", justifyContent: "space-between",
                alignItems: "center", marginBottom: 5 }}>
                <span style={{ fontSize: 9, color: "var(--muted)", letterSpacing: ".06em",
                  textTransform: "uppercase", fontWeight: 600 }}>Design Maturity</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: stage.color }}>
                  {stage.label}
                </span>
              </div>

              {/* Segmented bar */}
              <div style={{ display: "flex", gap: 3, marginBottom: 3 }}>
                {STAGES.map(s => (
                  <div key={s.level} style={{
                    flex: 1, height: 4, borderRadius: 2,
                    background: s.level <= effectiveStage ? stage.color : "var(--surface2)",
                    transition: "background .3s",
                  }} />
                ))}
              </div>

              {/* Stage labels */}
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                {STAGES.map(s => (
                  <span key={s.level} style={{
                    fontSize: 8,
                    color: s.level <= effectiveStage ? stage.color : "var(--faint)",
                    fontWeight: s.level === effectiveStage ? 700 : 400,
                    letterSpacing: ".03em",
                  }}>{s.label}</span>
                ))}
              </div>

              {/* Stage description */}
              <div style={{ fontSize: 10, color: "var(--text3)", lineHeight: 1.4,
                marginBottom: 6 }}>{stage.desc}</div>

              {/* Advance button */}
              {effectiveStage < 4 && (
                <div style={{ marginBottom: 8 }}>
                  {canAdvance ? (
                    <button onClick={handleAdvance} style={{
                      width: "100%", padding: "6px 12px", borderRadius: 4,
                      border: `1px solid ${nextStage?.color ?? "var(--primary)"}`,
                      background: `${nextStage?.color ?? "var(--primary)"}22`,
                      color: nextStage?.color ?? "var(--primary)",
                      fontSize: 10, fontWeight: 700, cursor: "pointer",
                      letterSpacing: ".04em", transition: "all .15s",
                    }}>
                      Advance to {nextStage?.label} →
                    </button>
                  ) : (
                    <div style={{ fontSize: 10, color: "var(--muted)", lineHeight: 1.4,
                      padding: "5px 8px", borderRadius: 4,
                      background: "rgba(0,0,0,.1)", border: "1px solid var(--border2)" }}>
                      🔒 {failCount > 0
                        ? `Resolve ${failCount} FAIL${failCount > 1 ? "s" : ""} to advance`
                        : warnCount > 0 && effectiveStage >= 2
                        ? `Resolve ${warnCount} WARN${warnCount > 1 ? "s" : ""} to advance to Detailed`
                        : stage.gate}
                    </div>
                  )}
                  {advancedAt && effectiveStage === 4 && (
                    <div style={{ fontSize: 9, color: "var(--muted)", marginTop: 3 }}>
                      Released {advancedAt}
                    </div>
                  )}
                </div>
              )}

              {effectiveStage === 4 && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 10, color: "var(--success)", fontWeight: 700,
                    padding: "5px 8px", borderRadius: 4,
                    background: "rgba(31,184,110,.1)", border: "1px solid rgba(31,184,110,.25)" }}>
                    ✓ Design Released{advancedAt ? ` — ${advancedAt}` : ""}
                  </div>
                  <button onClick={() => { setManualStage(null); setAdvancedAt(null); }}
                    style={{ marginTop: 4, fontSize: 9, color: "var(--muted)",
                      background: "none", border: "none", cursor: "pointer",
                      textDecoration: "underline" }}>
                    Revoke release
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Filter pills ────────────────────────────────────────────────── */}
          {results && checks.length > 0 && (
            <div style={{ display: "flex", gap: 4, padding: "6px 10px",
              borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
              {FILTERS.filter(f => f.id === "all" || f.count > 0).map(f => {
                const active = filter === f.id;
                const dc = f.id === "fail" ? "var(--danger)" : f.id === "warn" ? "var(--warning)"
                  : f.id === "ok" ? "var(--success)" : f.id === "info" ? "var(--info)" : "var(--text3)";
                return (
                  <button key={f.id}
                    onClick={e => { e.stopPropagation(); setFilter(f.id); }}
                    style={{ display: "flex", alignItems: "center", gap: 4,
                      padding: "2px 8px", borderRadius: "var(--r-pill, 999px)",
                      border: `1px solid ${active ? dc : "var(--border2)"}`,
                      background: active ? `${dc}22` : "transparent",
                      color: active ? dc : "var(--muted)",
                      fontSize: 9, fontWeight: 600, cursor: "pointer",
                      letterSpacing: ".05em", transition: "all var(--t-fast, .15s)" }}>
                    {f.label}
                    <span style={{ fontSize: 9, fontWeight: 700,
                      background: active ? `${dc}33` : "var(--surface)",
                      padding: "0 4px", borderRadius: 3,
                      color: active ? dc : "var(--muted)" }}>{f.count}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* ── Check list ───────────────────────────────────────────────────── */}
          <div style={{ padding: "8px 10px", maxHeight: 260, overflowY: "auto" }}>
            {!results ? (
              <div style={{ fontSize: 11, color: "var(--muted)",
                textAlign: "center", padding: "16px 0" }}>Calculating…</div>
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