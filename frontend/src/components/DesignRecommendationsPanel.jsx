// DesignRecommendationsPanel.jsx
// Renders the design_recommendations list produced by
// StructuralStressEngine.design_recommendations() in structural.py v1.3.0.
//
// Each item shape:  { check, status, problem, actions[] }
//   check:   string — "CAPACITY" | "SPEED" | "CR" | "SLIP" | "BEARING" | "HEADSHAFT"
//   status:  "fail" | "warn"
//   problem: short description of what is wrong and by how much
//   actions: ordered list of specific corrective actions with parameter values
//
// Empty-state:  green "Design passes all checks" — important positive signal.
//               An empty array is NOT the same as no data.

const STATUS = {
  fail: {
    icon:   "✗",
    label:  "FAIL",
    bg:     "var(--danger-dim,  #1a0808)",
    color:  "var(--danger,      #e05252)",
    border: "var(--danger-border, #4a1515)",
    hdr:    "var(--danger-dim2, #240d0d)",
  },
  warn: {
    icon:   "⚠",
    label:  "WARN",
    bg:     "var(--warning-dim,  #1a1205)",
    color:  "var(--warning,      #d98e00)",
    border: "var(--warning-border, #4a3005)",
    hdr:    "var(--warning-dim2, #241a07)",
  },
};

function RecommendationCard({ rec }) {
  const s = STATUS[rec.status] ?? STATUS.warn;
  return (
    <div style={{
      borderRadius: "var(--r-md, 6px)",
      border: `1px solid ${s.border}`,
      overflow: "hidden",
      background: s.bg,
    }}>
      {/* ── Header bar ── */}
      <div style={{
        padding: "7px 12px",
        background: s.hdr,
        borderBottom: `1px solid ${s.border}`,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ fontSize: 12, color: s.color, flexShrink: 0 }}>{s.icon}</span>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: ".10em",
          textTransform: "uppercase", color: s.color, flexShrink: 0,
        }}>{rec.check}</span>
        <span style={{
          fontSize: 10.5, color: "var(--text2)", lineHeight: 1.35, flex: 1,
        }}>{rec.problem}</span>
      </div>

      {/* ── Numbered actions ── */}
      <div style={{
        padding: "8px 12px 10px",
        display: "flex", flexDirection: "column", gap: 5,
      }}>
        {(rec.actions ?? []).map((action, j) => (
          <div key={j} style={{
            display: "flex", alignItems: "flex-start", gap: 8,
          }}>
            <span style={{
              fontSize: 9, fontWeight: 700, color: s.color,
              minWidth: 14, lineHeight: 1.6,
              fontFamily: "JetBrains Mono, monospace",
            }}>{j + 1}.</span>
            <span style={{
              fontSize: 11, color: "var(--text2)", lineHeight: 1.45,
            }}>{action}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DesignRecommendationsPanel({ recommendations }) {
  const recs = recommendations ?? [];

  // ── Empty state — positive signal ─────────────────────────────────────────
  if (recs.length === 0) {
    return (
      <div style={{
        margin: "10px 12px",
        padding: "11px 14px",
        borderRadius: "var(--r-md, 6px)",
        background: "var(--success-dim, #081a10)",
        border: "1px solid var(--success-border, #1a4a28)",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <span style={{ fontSize: 17, color: "var(--success, #1fb86e)", lineHeight: 1 }}>✓</span>
        <div>
          <div style={{
            fontSize: 12, fontWeight: 600,
            color: "var(--success, #1fb86e)", lineHeight: 1.3,
          }}>
            Design passes all checks
          </div>
          <div style={{
            fontSize: 10, color: "var(--muted)", marginTop: 3, lineHeight: 1.4,
          }}>
            No corrective actions required for this configuration.
          </div>
        </div>
      </div>
    );
  }

  // ── Active recommendations ─────────────────────────────────────────────────
  const failCount = recs.filter(r => r.status === "fail").length;
  const warnCount = recs.filter(r => r.status === "warn").length;

  return (
    <div>
      {/* Summary line */}
      <div style={{
        padding: "8px 12px 4px",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: "var(--text3)",
        }}>Design Recommendations</span>
        {failCount > 0 && (
          <span style={{
            fontSize: 8, fontWeight: 700, padding: "1px 6px",
            borderRadius: "var(--r-pill, 999px)",
            background: "var(--danger-dim)", color: "var(--danger)",
            border: "1px solid var(--danger-border)",
          }}>{failCount} FAIL</span>
        )}
        {warnCount > 0 && (
          <span style={{
            fontSize: 8, fontWeight: 700, padding: "1px 6px",
            borderRadius: "var(--r-pill, 999px)",
            background: "var(--warning-dim)", color: "var(--warning)",
            border: "1px solid var(--warning-border)",
          }}>{warnCount} WARN</span>
        )}
      </div>

      {/* Cards — fails first, then warns */}
      <div style={{ padding: "0 12px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
        {[...recs].sort((a, b) => (a.status === "fail" ? -1 : 1)).map((rec, i) => (
          <RecommendationCard key={i} rec={rec} />
        ))}
      </div>
    </div>
  );
}