// RootCausePanel.jsx — Redesigned for readability + conflict detection
//
// CHANGES FROM ORIGINAL
// ──────────────────────
// 1. Font sizes increased: 7-9.5px → 10-13px throughout
// 2. More breathing room: padding/margins roughly doubled
// 3. CONFLICT DETECTION (new): before rendering findings, scan all
//    corrections across all findings. If two corrections target the
//    SAME input param with DIFFERENT target values, surface a single
//    "Conflicting Recommendations" banner at the top — listing both
//    asks and which findings they come from — instead of burying a
//    one-line c.conflict footnote under each correction.
// 4. Findings grouped by severity (fail first, then warn) with clearer
//    section dividers.
// 5. Driver bars redesigned: larger labels, bar moved below text for
//    cleaner scanning.

export default function RootCausePanel({ results, setField }) {
  const findings = results?.root_cause ?? [];

  if (!findings.length) {
    const failCount = (results?.checks ?? []).filter(c => c.type === "fail").length;
    const warnCount = (results?.checks ?? []).filter(c => c.type === "warn").length;
    if (!failCount && !warnCount) {
      return (
        <div style={{ padding: "24px 16px", textAlign: "center" }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>✅</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--success)" }}>
            All checks pass — no corrections required
          </div>
        </div>
      );
    }
    return (
      <div style={{ padding: "16px", fontSize: 11, color: "var(--text3)" }}>
        Root cause analysis loading…
      </div>
    );
  }

  // ── Conflict detection ──────────────────────────────────────────────────
  // Build a map: param → [{findingIdx, label, target, current, unit, source}]
  const paramMap = {};
  findings.forEach((f, fi) => {
    (f.corrections ?? []).forEach((c) => {
      if (!c.param) return;
      if (!paramMap[c.param]) paramMap[c.param] = [];
      paramMap[c.param].push({
        findingIdx: fi,
        findingLabel: f.failure_metric,
        label: c.label,
        target: c.target,
        current: c.current,
        unit: c.unit,
      });
    });
  });

  // A conflict exists if a param has 2+ entries with DIFFERENT targets
  const conflicts = Object.entries(paramMap)
    .map(([param, entries]) => {
      const uniqueTargets = [...new Set(entries.map(e => e.target))];
      return { param, entries, uniqueTargets };
    })
    .filter(c => c.uniqueTargets.length > 1);

  // Sort findings: fail before warn
  const sorted = [...findings].sort((a, b) =>
    a.severity === "fail" ? -1 : b.severity === "fail" ? 1 : 0
  );

  return (
    <div>
      {/* Header */}
      <div style={{
        padding: "12px 14px 8px",
        borderBottom: "1px solid var(--border)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".07em",
          textTransform: "uppercase", color: "var(--text3)" }}>
          Root Cause Analysis
        </span>
        <span style={{ fontSize: 10, color: "var(--text3)" }}>
          {findings.length} finding{findings.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* ── Conflict banner — surfaced ONCE, above findings ── */}
      {conflicts.length > 0 && (
        <div style={{
          margin: "10px 14px",
          padding: "12px 14px",
          borderRadius: "var(--r-md)",
          background: "rgba(245,158,11,.08)",
          border: "1px solid rgba(245,158,11,.3)",
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 8,
          }}>
            <span style={{ fontSize: 14 }}>⚠</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--warning)" }}>
              Conflicting Recommendations
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text2)", lineHeight: 1.6, marginBottom: 10 }}>
            The corrections below ask for different values for the same
            parameter. Applying one may worsen the other check — review
            both before changing this value.
          </div>
          {conflicts.map((c) => (
            <div key={c.param} style={{
              padding: "8px 10px", borderRadius: "var(--r-sm)",
              background: "var(--panel2)", marginBottom: 6,
              border: "1px solid var(--border)",
            }}>
              <div style={{
                fontSize: 11, fontWeight: 700, color: "var(--text)",
                fontFamily: "JetBrains Mono, monospace", marginBottom: 6,
              }}>{c.param}</div>
              {c.entries.map((e, i) => (
                <div key={i} style={{
                  display: "flex", justifyContent: "space-between",
                  alignItems: "baseline", fontSize: 10.5, padding: "3px 0",
                  borderTop: i > 0 ? "1px solid var(--border)" : "none",
                }}>
                  <span style={{ color: "var(--text3)", flex: 1 }}>
                    {e.findingLabel}
                  </span>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", color: "var(--text2)" }}>
                    {e.current}{e.unit ? ` ${e.unit}` : ""} → <span style={{ color: "var(--primary)", fontWeight: 700 }}>{e.target}{e.unit ? ` ${e.unit}` : ""}</span>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Finding cards */}
      {sorted.map((f, fi) => (
        <FindingCard key={fi} finding={f} setField={setField}
          conflictParams={conflicts.map(c => c.param)} />
      ))}
    </div>
  );
}

// ── Severity colours ──────────────────────────────────────────────────────────
const SEV = {
  fail: { color: "var(--danger)",  bg: "rgba(239,68,68,.06)",  border: "rgba(239,68,68,.2)",  icon: "✗" },
  warn: { color: "var(--warning)", bg: "rgba(245,158,11,.06)", border: "rgba(245,158,11,.2)", icon: "⚠" },
};

// ── Individual finding card ───────────────────────────────────────────────────
function FindingCard({ finding, setField, conflictParams }) {
  const sev = SEV[finding.severity] || SEV.warn;

  return (
    <div style={{
      margin: "10px 14px",
      borderRadius: "var(--r-md)",
      border: `1px solid ${sev.border}`,
      background: sev.bg,
      overflow: "hidden",
    }}>

      {/* ── Failure headline ─────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 10,
        padding: "12px 14px",
        borderBottom: "1px solid " + sev.border,
      }}>
        <span style={{ fontSize: 16, color: sev.color, flexShrink: 0,
          fontWeight: 700, lineHeight: 1.3 }}>
          {sev.icon}
        </span>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)",
            lineHeight: 1.4, marginBottom: 4 }}>
            {finding.failure_metric}
          </div>
          <div style={{ fontSize: 11, color: "var(--text3)", lineHeight: 1.6 }}>
            {finding.explanation}
          </div>
        </div>
      </div>

      {/* ── Driver bars ──────────────────────────────────────────────── */}
      {finding.drivers && finding.drivers.length > 0 && (
        <div style={{ padding: "10px 14px", borderBottom: "1px solid " + sev.border }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text3)",
            letterSpacing: ".08em", textTransform: "uppercase",
            marginBottom: 8 }}>Contributing Factors</div>
          {finding.drivers.map((d, di) => (
            <div key={di} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "baseline",
                justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: "var(--text)", fontWeight: 600 }}>
                  {d.label}
                  <span style={{ color: "var(--text3)", fontWeight: 400,
                    fontFamily: "JetBrains Mono, monospace", marginLeft: 6,
                    fontSize: 10.5 }}>
                    = {d.current}{d.unit ? ` ${d.unit}` : ""}
                  </span>
                </span>
                <span style={{
                  fontSize: 9, padding: "2px 7px", borderRadius: 999,
                  background: d.priority === 1
                    ? `${sev.color}22` : "rgba(100,116,139,.15)",
                  color: d.priority === 1 ? sev.color : "var(--text3)",
                  fontWeight: 700, letterSpacing: ".03em",
                }}>
                  {d.priority === 1 ? "PRIMARY" : `#${d.priority}`}
                </span>
              </div>
              {/* Impact bar */}
              <div style={{
                height: 4, borderRadius: 2,
                background: "var(--surface2)",
                marginBottom: 4,
              }}>
                <div style={{
                  height: "100%", borderRadius: 2,
                  width: `${100 - (d.priority - 1) * 30}%`,
                  background: d.priority === 1 ? sev.color : "var(--text3)",
                  transition: "width .3s",
                }} />
              </div>
              <div style={{ fontSize: 10.5, color: "var(--text3)", lineHeight: 1.5 }}>
                {d.impact}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Corrections ──────────────────────────────────────────────── */}
      {finding.corrections && finding.corrections.length > 0 && (
        <div style={{ padding: "10px 14px" }}>
          <div style={{ fontSize: 9, fontWeight: 700, color: "var(--text3)",
            letterSpacing: ".08em", textTransform: "uppercase",
            marginBottom: 8 }}>Suggested Corrections</div>
          {finding.corrections.map((c, ci) => (
            <CorrectionRow key={ci} correction={c} setField={setField}
              priority={c.priority}
              hasConflict={conflictParams.includes(c.param)} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Correction row with Apply button ─────────────────────────────────────────
function CorrectionRow({ correction: c, setField, priority, hasConflict }) {
  const canApply = !!setField && !!c.param && c.param !== "bearing" &&
                   c.target !== undefined && c.target !== null &&
                   typeof c.target !== "string";

  const changePct = c.change_pct;
  const pctColor  = changePct === 0 ? "var(--text3)"
                  : Math.abs(changePct) > 30 ? "var(--warning)"
                  : "var(--text3)";

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      padding: "10px 12px", marginBottom: 6,
      borderRadius: "var(--r-sm)",
      background: "var(--panel2)",
      border: `1px solid ${hasConflict ? "rgba(245,158,11,.35)" : "var(--border)"}`,
    }}>
      {/* Priority marker */}
      <div style={{
        width: 22, height: 22, borderRadius: 999, flexShrink: 0,
        background: priority === 1
          ? "var(--primary-dim)" : "rgba(100,116,139,.12)",
        border: `1px solid ${priority === 1 ? "var(--primary)" : "var(--border2)"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700,
        color: priority === 1 ? "var(--primary)" : "var(--text3)",
        marginTop: 1,
      }}>
        {priority}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center",
          justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>
            {c.label}
          </span>
          {canApply && (
            <button
              onClick={() => setField(c.param, c.target)}
              style={{
                padding: "4px 12px", fontSize: 10.5, fontWeight: 700,
                cursor: "pointer", borderRadius: "var(--r-sm)", flexShrink: 0,
                border: "1px solid var(--primary)",
                background: "var(--primary-dim)",
                color: "var(--primary)", fontFamily: "var(--ff-ui)",
              }}
              title={`Set ${c.param} = ${c.target}`}
            >
              Apply
            </button>
          )}
        </div>

        {/* Value change */}
        <div style={{ display: "flex", alignItems: "center", gap: 8,
          fontFamily: "JetBrains Mono, monospace", fontSize: 11,
          color: "var(--text2)", marginBottom: 4 }}>
          <span style={{ color: "var(--text3)" }}>{c.current}{c.unit ? ` ${c.unit}` : ""}</span>
          <span style={{ color: "var(--text3)" }}>→</span>
          <span style={{ fontWeight: 700, color: "var(--primary)" }}>
            {c.target}{c.unit ? ` ${c.unit}` : ""}
          </span>
          {changePct != null && changePct !== 0 && (
            <span style={{ fontSize: 10, color: pctColor }}>
              ({changePct > 0 ? "+" : ""}{changePct.toFixed(0)}%)
            </span>
          )}
        </div>

        {/* Note */}
        {c.note && (
          <div style={{ fontSize: 10.5, color: "var(--text3)", lineHeight: 1.5 }}>
            {c.note}
          </div>
        )}

        {/* Per-correction conflict reference — points to the banner above */}
        {hasConflict && (
          <div style={{
            marginTop: 6, fontSize: 10, lineHeight: 1.5,
            color: "var(--warning)",
            padding: "5px 8px", borderRadius: "var(--r-sm)",
            background: "rgba(245,158,11,.1)",
            border: "1px solid rgba(245,158,11,.25)",
            display: "flex", alignItems: "center", gap: 6,
          }}>
            <span>⚠</span> See "Conflicting Recommendations" above before applying
          </div>
        )}
      </div>
    </div>
  );
}