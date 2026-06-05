// BucketElevatorPage.jsx — Task 4: 3-Column Workstation Layout
//
// BEFORE (Task 3):
//   [Sidebar 300px] | [main-content scrollable — schematic + KPIs + charts stacked]
//
// AFTER (Task 4):
//   [Parameters 280px] | [Equipment Model — fixed schematic] | [Engineering Results 360px]
//
// The machine schematic is now the permanent centre column.
// Left col: input accordion (discipline cards, always visible)
// Centre col: live SVG schematic + performance charts below
// Right col: KPI cards + engineering checks (scrollable)
//
// The top nav pill tabs now control what fills the RIGHT column:
//   Design     → KPI cards + checks summary
//   Optimizer  → optimizer panel
//   Components → component detail
//   Checks     → full checks panel
//
// The schematic ALWAYS stays visible in centre regardless of right-col tab.

import { useState, useEffect } from "react";
import { useElevatorCalc } from "./hooks/useElevatorCalc";
import InputSidebar      from "./components/InputSidebar";
import ElevatorSchematic from "./components/ElevatorSchematic";
import KpiGrid           from "./components/KpiGrid";
import ChartsPanel       from "./components/ChartsPanel";
import OptimizerPanel    from "./components/OptimizerPanel";
import ComponentPanel    from "./components/ComponentPanel";
import ChecksPanel       from "./components/ChecksPanel";
import SaveLoadModal     from "./components/SaveLoadModal";

const RIGHT_TABS = [
  { id: "design",     label: "Results",    badge: null },
  { id: "optimizer",  label: "Optimizer",  badge: "AI" },
  { id: "components", label: "Components", badge: null },
  { id: "checks",     label: "Checks",     badge: null, failBadge: true },
];

// ── Column header shared style ────────────────────────────────────────────
function ColHeader({ label, sub, action }) {
  return (
    <div style={{
      height: 38,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 14px",
      borderBottom: "1px solid var(--border)",
      background: "var(--panel)",
      flexShrink: 0,
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: "var(--text3)",
        }}>{label}</span>
        {sub && (
          <span style={{ fontSize: 9, color: "var(--muted)", letterSpacing: ".04em" }}>
            {sub}
          </span>
        )}
      </div>
      {action}
    </div>
  );
}

export default function BucketElevatorPage({ onResultsChange }) {
  const {
    inputs, results, loading, error,
    setField, applyOptimizer, saveCurrentDesign, loadDesign,
  } = useElevatorCalc();

  const [activeRight, setActiveRight] = useState("design");
  const [showSaveLoad, setShowSaveLoad] = useState(false);
  const [chartTab, setChartTab]       = useState("speed");

  useEffect(() => {
    if (onResultsChange) onResultsChange({ results, inputs });
  }, [results, inputs, onResultsChange]);

  const failCount  = results?.checks?.filter((c) => c.type === "fail").length  ?? 0;
  const warnCount  = results?.checks?.filter((c) => c.type === "warn").length  ?? 0;

  return (
    <>
      {/* ══════════════════════════════════════════════════
          MODULE NAV BAR (unchanged from Task 3)
          ══════════════════════════════════════════════════ */}
      <div className="nav">
        <div className="nav-brand">
          <div style={{
            width: 28, height: 28, borderRadius: "var(--r-sm)",
            background: "var(--primary-dim)", border: "1px solid var(--primary-ring)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 13, color: "var(--primary)",
          }}>⛏</div>
          <div>
            <div className="nav-title">Bucket Elevator</div>
            <div className="nav-sub">VECTOMEC™ · CEMA 375</div>
          </div>
        </div>

        {/* Right-column tabs — pill group */}
        <div style={{
          display: "flex", gap: 3,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--r-pill)",
          padding: "3px",
          marginRight: 16,
        }}>
          {RIGHT_TABS.map((t) => {
            const active   = activeRight === t.id;
            const showFail = t.failBadge && failCount > 0;
            return (
              <button key={t.id} onClick={() => setActiveRight(t.id)} style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "5px 12px", borderRadius: "var(--r-pill)",
                border: "none", cursor: "pointer",
                fontFamily: "var(--ff-ui)", fontSize: 12,
                fontWeight: active ? 600 : 400,
                transition: "all var(--t-base)",
                background: active ? "var(--panel)" : "transparent",
                color: active ? "var(--text)" : "var(--text3)",
                boxShadow: active
                  ? "0 1px 4px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.06)"
                  : "none",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.color = "var(--text2)"; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.color = "var(--text3)"; }}
              >
                {t.label}
                {t.badge && (
                  <span style={{
                    fontSize: 8, fontWeight: 700, letterSpacing: ".06em",
                    padding: "1px 5px", borderRadius: "var(--r-pill)",
                    background: "var(--primary-dim)", color: "var(--primary)",
                    border: "1px solid var(--primary-ring)",
                  }}>{t.badge}</span>
                )}
                {showFail && (
                  <span style={{
                    fontSize: 8, fontWeight: 700, padding: "1px 5px",
                    borderRadius: "var(--r-pill)",
                    background: "var(--danger-dim)", color: "var(--danger)",
                    border: "1px solid var(--danger-border)",
                    minWidth: 16, textAlign: "center",
                  }}>{failCount}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Live KPI strip */}
        {results && (
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginRight: 12 }}>
            {[
              { label:"Q", value: results.Q?.toFixed(0) ?? "—", unit:"t/h",
                color: (results.Q??0)>=inputs.Q_req ? "var(--success)" : "var(--danger)" },
              { label:"P", value: results.P_total?.toFixed(1) ?? "—", unit:"kW",
                color: "var(--warning)" },
              { label:"v", value: results.v?.toFixed(2) ?? "—", unit:"m/s",
                color: "var(--primary)" },
            ].map((k) => (
              <div key={k.label} style={{
                display: "flex", flexDirection: "column", alignItems: "center",
                padding: "3px 8px", background: "var(--surface)",
                borderRadius: "var(--r-md)", border: "1px solid var(--border)", minWidth: 48,
              }}>
                <span style={{ fontSize: 9, color: "var(--muted)", fontWeight: 600,
                  letterSpacing: ".06em", textTransform: "uppercase" }}>{k.label}</span>
                <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 13,
                  fontWeight: 700, color: k.color, lineHeight: 1.2 }}>{k.value}</span>
                <span style={{ fontSize: 9, color: "var(--muted)",
                  fontFamily: "JetBrains Mono,monospace" }}>{k.unit}</span>
              </div>
            ))}
          </div>
        )}

        <button className="btn-secondary"
          style={{ padding: "5px 12px", fontSize: 11, flexShrink: 0 }}
          onClick={() => setShowSaveLoad(true)}>
          💾 Save / Load
        </button>
      </div>

      {loading && <div className="loading-bar" />}
      {error && (
        <div className="warn-item w-fail" style={{ margin: "6px 12px", flexShrink: 0 }}>
          ⚠ API Error: {error}
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          3-COLUMN WORKSTATION BODY
          ══════════════════════════════════════════════════ */}
      <div style={{
        display: "flex",
        flex: 1,
        overflow: "hidden",
        background: "var(--bg)",
      }}>

        {/* ── LEFT COLUMN — Parameters (280px fixed) ──────── */}
        <div style={{
          width: 280,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid var(--border)",
          background: "var(--panel)",
          overflow: "hidden",
        }}>
          <ColHeader label="Parameters" sub="CEMA 375 Inputs" />
          <div style={{ flex: 1, overflowY: "auto" }}>
            <InputSidebar inputs={inputs} setField={setField} results={results} />
          </div>
        </div>

        {/* ── CENTRE COLUMN — Equipment Model (flexible) ───── */}
        <div style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          borderRight: "1px solid var(--border)",
          minWidth: 0,
        }}>
          <ColHeader
            label="Equipment Model"
            sub={results ? `Bucket ${results.bucket?.id} · ${results.bucket?.W}×${results.bucket?.H}mm · ${results.bucket?.V}L` : "Calculating…"}
            action={
              results && (
                <div style={{ display: "flex", gap: 6 }}>
                  {failCount > 0 && (
                    <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 7px",
                      borderRadius: "var(--r-pill)", background: "var(--danger-dim)",
                      color: "var(--danger)", border: "1px solid var(--danger-border)" }}>
                      {failCount} FAIL
                    </span>
                  )}
                  {warnCount > 0 && (
                    <span style={{ fontSize: 9, fontWeight: 600, padding: "2px 7px",
                      borderRadius: "var(--r-pill)", background: "var(--warning-dim)",
                      color: "var(--warning)", border: "1px solid var(--warning-border)" }}>
                      {warnCount} WARN
                    </span>
                  )}
                </div>
              )
            }
          />

          {/* Schematic — permanent, always visible */}
          <div style={{
            flexShrink: 0,
            background: "var(--panel2)",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "12px 0",
            minHeight: 260,
          }}>
            <ElevatorSchematic inputs={inputs} results={results} />
          </div>

          {/* Chart area — below schematic, scrollable */}
          <div style={{ flex: 1, overflowY: "auto", background: "var(--bg)" }}>

            {/* Chart sub-tabs */}
            <div style={{
              display: "flex", gap: 0,
              borderBottom: "1px solid var(--border)",
              background: "var(--panel2)",
              padding: "0 12px",
            }}>
              {[
                { id: "speed",   label: "Speed Sweep"  },
                { id: "fill",    label: "Fill Analysis" },
                { id: "traj",    label: "Trajectory"   },
                { id: "tension", label: "Tension"       },
              ].map((t) => (
                <button key={t.id} onClick={() => setChartTab(t.id)} style={{
                  padding: "8px 14px", fontSize: 11, fontWeight: chartTab===t.id ? 600 : 400,
                  cursor: "pointer", border: "none", background: "transparent",
                  color: chartTab===t.id ? "var(--primary)" : "var(--text3)",
                  borderBottom: `2px solid ${chartTab===t.id ? "var(--primary)" : "transparent"}`,
                  marginBottom: -1, transition: "all var(--t-base)",
                  fontFamily: "var(--ff-ui)",
                }}
                onMouseEnter={e => { if (chartTab!==t.id) e.currentTarget.style.color="var(--text2)"; }}
                onMouseLeave={e => { if (chartTab!==t.id) e.currentTarget.style.color="var(--text3)"; }}
                >{t.label}</button>
              ))}
            </div>

            <ChartsPanel results={results} inputs={inputs} activeTab={chartTab} />
          </div>
        </div>

        {/* ── RIGHT COLUMN — Engineering Results (360px fixed) */}
        <div style={{
          width: 360,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          background: "var(--panel)",
        }}>
          {/* Right column header with status summary */}
          <ColHeader
            label={
              activeRight === "design"     ? "Engineering Results" :
              activeRight === "optimizer"  ? "Design Optimizer"    :
              activeRight === "components" ? "Component Design"    :
                                            "Engineering Checks"
            }
            sub={
              activeRight === "design" && results
                ? `${results.checks?.length ?? 0} checks · ${results.motor_kw}kW motor`
                : undefined
            }
          />

          {/* Right column scrollable content */}
          <div style={{ flex: 1, overflowY: "auto" }}>

            {activeRight === "design" && (
              <>
                {/* Inline checks summary strip */}
                {results?.checks && (
                  <div style={{
                    padding: "8px 12px",
                    display: "flex", flexDirection: "column", gap: 4,
                    borderBottom: "1px solid var(--border)",
                    background: "var(--panel2)",
                  }}>
                    {results.checks.filter(c => c.type === "fail" || c.type === "warn").slice(0,3).map((c,i) => (
                      <div key={i} style={{
                        display: "flex", alignItems: "flex-start", gap: 7,
                        fontSize: 11, lineHeight: 1.4,
                        color: c.type === "fail" ? "var(--danger)" : "var(--warning)",
                      }}>
                        <span style={{ flexShrink: 0, fontSize: 10 }}>
                          {c.type === "fail" ? "✗" : "⚠"}
                        </span>
                        {c.msg}
                      </div>
                    ))}
                    {results.checks.filter(c => c.type === "fail" || c.type === "warn").length === 0 && (
                      <div style={{ fontSize: 11, color: "var(--success)", display: "flex", gap: 6 }}>
                        <span>✓</span> All checks passed
                      </div>
                    )}
                  </div>
                )}
                {/* KPI cards — compact grid in right column */}
                <div style={{ padding: "0 0 16px" }}>
                  <KpiGrid results={results} inputs={inputs} compact />
                </div>
              </>
            )}

            {activeRight === "optimizer" && (
              <OptimizerPanel inputs={inputs} onApply={applyOptimizer} />
            )}

            {activeRight === "components" && (
              <ComponentPanel results={results} inputs={inputs} />
            )}

            {activeRight === "checks" && (
              <ChecksPanel results={results} inputs={inputs} />
            )}
          </div>
        </div>

      </div>

      {showSaveLoad && (
        <SaveLoadModal
          onClose={() => setShowSaveLoad(false)}
          onSave={saveCurrentDesign}
          onLoad={loadDesign}
        />
      )}
    </>
  );
}
