// RootCausePanel.jsx
// Displays root cause findings for every failed/warned engineering check.
// For each finding:
//   • Failure metric — what failed and by how much
//   • Driver bars   — which inputs drive the failure (ranked)
//   • Corrections   — specific parameter changes with Apply button
//
// Corrections with an `param` that matches an input field call setField()
// directly so the engineer can apply the fix with one click and see the
// result update immediately.

export default function RootCausePanel({ results, setField }) {
  const findings = results?.root_cause ?? [];

  if (!findings.length) {
    const failCount = (results?.checks ?? []).filter(c => c.type === "fail").length;
    const warnCount = (results?.checks ?? []).filter(c => c.type === "warn").length;
    if (!failCount && !warnCount) {
      return (
        <div style={{ padding:"16px 12px", textAlign:"center" }}>
          <div style={{ fontSize:20, marginBottom:6 }}>✅</div>
          <div style={{ fontSize:10, fontWeight:700, color:"var(--success)" }}>
            All checks pass — no corrections required
          </div>
        </div>
      );
    }
    return (
      <div style={{ padding:"12px", fontSize:9, color:"var(--text3)" }}>
        Root cause analysis loading…
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{
        padding:"8px 12px 6px",
        borderBottom:"1px solid var(--border)",
        display:"flex", alignItems:"center", justifyContent:"space-between",
      }}>
        <span style={{ fontSize:9, fontWeight:700, letterSpacing:".07em",
          textTransform:"uppercase", color:"var(--text3)" }}>
          Root Cause Analysis
        </span>
        <span style={{ fontSize:8, color:"var(--text3)" }}>
          {findings.length} finding{findings.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Finding cards */}
      {findings.map((f, fi) => (
        <FindingCard key={fi} finding={f} setField={setField} />
      ))}
    </div>
  );
}

// ── Severity colours ──────────────────────────────────────────────────────────
const SEV = {
  fail: { color:"var(--danger)",  bg:"rgba(224,82,82,.08)",  border:"rgba(224,82,82,.25)",  icon:"✗" },
  warn: { color:"var(--warning)", bg:"rgba(217,142,0,.08)",  border:"rgba(217,142,0,.25)",  icon:"▲" },
};

// ── Individual finding card ───────────────────────────────────────────────────
function FindingCard({ finding, setField }) {
  const sev = SEV[finding.severity] || SEV.warn;

  return (
    <div style={{
      borderBottom:"1px solid var(--border)",
      padding:"10px 12px",
      background: sev.bg,
    }}>

      {/* ── Failure headline ─────────────────────────────────────────── */}
      <div style={{ display:"flex", alignItems:"flex-start", gap:6, marginBottom:6 }}>
        <span style={{ fontSize:11, color:sev.color, flexShrink:0,
          fontWeight:700, lineHeight:1.3 }}>
          {sev.icon}
        </span>
        <div>
          <div style={{ fontSize:9.5, fontWeight:700, color:"var(--text)",
            lineHeight:1.3, marginBottom:2 }}>
            {finding.failure_metric}
          </div>
          <div style={{ fontSize:8.5, color:"var(--text3)", lineHeight:1.4 }}>
            {finding.explanation}
          </div>
        </div>
      </div>

      {/* ── Driver bars ──────────────────────────────────────────────── */}
      {finding.drivers && finding.drivers.length > 0 && (
        <div style={{ marginBottom:8 }}>
          <div style={{ fontSize:7.5, fontWeight:700, color:"var(--text3)",
            letterSpacing:".06em", textTransform:"uppercase",
            marginBottom:4 }}>Drivers</div>
          {finding.drivers.map((d, di) => (
            <div key={di} style={{ marginBottom:3 }}>
              <div style={{ display:"flex", alignItems:"center",
                justifyContent:"space-between", marginBottom:1 }}>
                <span style={{ fontSize:8.5, color:"var(--text2)", fontWeight:600 }}>
                  {d.label}
                  <span style={{ color:"var(--text3)", fontWeight:400,
                    fontFamily:"JetBrains Mono,monospace", marginLeft:4 }}>
                    = {d.current}{d.unit ? ` ${d.unit}` : ""}
                  </span>
                </span>
                <span style={{
                  fontSize:7, padding:"1px 5px", borderRadius:999,
                  background: d.priority === 1
                    ? `${sev.color}20` : "rgba(90,122,154,.12)",
                  color: d.priority === 1 ? sev.color : "var(--text3)",
                  fontWeight:700,
                }}>
                  {d.priority === 1 ? "PRIMARY" : `#${d.priority}`}
                </span>
              </div>
              {/* Impact bar — visual weight by priority */}
              <div style={{
                height:2, borderRadius:1,
                background:"var(--border)",
                marginBottom:1,
              }}>
                <div style={{
                  height:"100%", borderRadius:1,
                  width: `${100 - (d.priority - 1) * 30}%`,
                  background: d.priority === 1 ? sev.color : "var(--text3)",
                  transition:"width .3s",
                }} />
              </div>
              <div style={{ fontSize:7.5, color:"var(--text3)", lineHeight:1.3 }}>
                {d.impact}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Corrections ──────────────────────────────────────────────── */}
      {finding.corrections && finding.corrections.length > 0 && (
        <div>
          <div style={{ fontSize:7.5, fontWeight:700, color:"var(--text3)",
            letterSpacing:".06em", textTransform:"uppercase",
            marginBottom:4 }}>Corrections</div>
          {finding.corrections.map((c, ci) => (
            <CorrectionRow key={ci} correction={c} setField={setField}
              priority={c.priority} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Correction row with Apply button ─────────────────────────────────────────
function CorrectionRow({ correction: c, setField, priority }) {
  const canApply = !!setField && !!c.param && c.param !== "bearing" &&
                   c.target !== undefined && c.target !== null &&
                   typeof c.target !== "string";

  const changePct = c.change_pct;
  const pctColor  = changePct === 0 ? "var(--text3)"
                  : Math.abs(changePct) > 30 ? "var(--warning)"
                  : "var(--text3)";

  return (
    <div style={{
      display:"flex", alignItems:"flex-start", gap:8,
      padding:"5px 8px", marginBottom:3,
      borderRadius:4,
      background:"var(--panel2)",
      border:"1px solid var(--border)",
    }}>
      {/* Priority marker */}
      <div style={{
        width:16, height:16, borderRadius:999, flexShrink:0,
        background: priority === 1
          ? "rgba(74,158,255,.15)" : "rgba(90,122,154,.10)",
        border: `1px solid ${priority === 1 ? "var(--primary)" : "var(--border)"}`,
        display:"flex", alignItems:"center", justifyContent:"center",
        fontSize:8, fontWeight:700,
        color: priority === 1 ? "var(--primary)" : "var(--text3)",
        marginTop:1,
      }}>
        {priority}
      </div>

      {/* Content */}
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:"flex", alignItems:"center",
          justifyContent:"space-between", gap:4, marginBottom:2 }}>
          <span style={{ fontSize:9.5, fontWeight:700, color:"var(--text)" }}>
            {c.label}
          </span>
          {canApply && (
            <button
              onClick={() => setField(c.param, c.target)}
              style={{
                padding:"2px 8px", fontSize:8.5, fontWeight:700,
                cursor:"pointer", borderRadius:3, flexShrink:0,
                border:"1px solid var(--primary)",
                background:"var(--primary-dim)",
                color:"var(--primary)", fontFamily:"inherit",
              }}
              title={`Set ${c.param} = ${c.target}`}
            >
              Apply
            </button>
          )}
        </div>

        {/* Value change summary */}
        <div style={{ display:"flex", alignItems:"center", gap:6,
          fontFamily:"JetBrains Mono,monospace", fontSize:9,
          color:"var(--text2)", marginBottom:2 }}>
          <span style={{ color:"var(--text3)" }}>{c.current}{c.unit ? ` ${c.unit}` : ""}</span>
          <span style={{ color:"var(--text3)" }}>→</span>
          <span style={{ fontWeight:700, color:"var(--primary)" }}>
            {c.target}{c.unit ? ` ${c.unit}` : ""}
          </span>
          {changePct != null && changePct !== 0 && (
            <span style={{ fontSize:8, color:pctColor }}>
              ({changePct > 0 ? "+" : ""}{changePct.toFixed(0)}%)
            </span>
          )}
        </div>

        {/* Note */}
        {c.note && (
          <div style={{ fontSize:8, color:"var(--text3)", lineHeight:1.4 }}>
            {c.note}
          </div>
        )}
      </div>
    </div>
  );
}