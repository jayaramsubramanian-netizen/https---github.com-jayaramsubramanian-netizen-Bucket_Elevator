// BucketElevatorPage.jsx — Task 3 updated nav bar
// Fixed: Quick KPI field names corrected to match API response
//   results.Q_th → results.Q
//   results.power_P_total → results.P_total
//   results.v_ms → results.v
// Fixed: fail badge uses --danger token not var(--accent)
// Fixed: import paths corrected for src/ location
// Added: discipline view tabs styled as pills matching new system

import { useState, useEffect } from "react";
import { useElevatorCalc } from "./hooks/useElevatorCalc";
import InputSidebar    from "./components/InputSidebar";
import ElevatorSchematic from "./components/ElevatorSchematic";
import KpiGrid         from "./components/KpiGrid";
import ChartsPanel     from "./components/ChartsPanel";
import OptimizerPanel  from "./components/OptimizerPanel";
import ComponentPanel  from "./components/ComponentPanel";
import ChecksPanel     from "./components/ChecksPanel";
import SaveLoadModal   from "./components/SaveLoadModal";

const NAV_TABS = [
  { id: "design",     label: "Design",       icon: "◈", badge: null },
  { id: "optimizer",  label: "Optimizer",    icon: "⌬", badge: "AI" },
  { id: "components", label: "Components",   icon: "◻", badge: null },
  { id: "checks",     label: "Eng. Checks",  icon: "✓", badge: null, failBadge: true },
];

export default function BucketElevatorPage({ onResultsChange }) {
  const {
    inputs, results, loading, error,
    setField, applyOptimizer, saveCurrentDesign, loadDesign,
  } = useElevatorCalc();

  const [activeNav,    setActiveNav]    = useState("design");
  const [showSaveLoad, setShowSaveLoad] = useState(false);

  // Lift results + inputs up to App so the PDF button can access them
  useEffect(() => {
    if (onResultsChange) onResultsChange({ results, inputs });
  }, [results, inputs, onResultsChange]);

  // Count fail-level checks for the badge
  const failCount = results?.checks?.filter((c) => c.type === "fail").length ?? 0;

  return (
    <>
      {/* ══════════════════════════════════════════════════
          MODULE NAV BAR
          Left:  module title + sub
          Centre: discipline tabs (pill row)
          Right:  live KPI strip + save button
          ══════════════════════════════════════════════════ */}
      <div className="nav">

        {/* Module identity */}
        <div className="nav-brand">
          <div style={{
            width: 28, height: 28,
            borderRadius: "var(--r-sm)",
            background: "var(--primary-dim)",
            border: "1px solid var(--primary-ring)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 13, color: "var(--primary)",
          }}>⛏</div>
          <div>
            <div className="nav-title">Bucket Elevator</div>
            <div className="nav-sub">VECTOMEC™ · CEMA 375</div>
          </div>
        </div>

        {/* Discipline tabs — pill group matching platform switcher */}
        <div style={{
          display: "flex", gap: 3,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--r-pill)",
          padding: "3px",
          marginRight: 16,
        }}>
          {NAV_TABS.map((t) => {
            const active = activeNav === t.id;
            const showFail = t.failBadge && failCount > 0;
            return (
              <button
                key={t.id}
                onClick={() => setActiveNav(t.id)}
                style={{
                  display: "flex", alignItems: "center", gap: 5,
                  padding: "5px 12px",
                  borderRadius: "var(--r-pill)",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "var(--ff-ui)",
                  fontSize: 12,
                  fontWeight: active ? 600 : 400,
                  transition: "all var(--t-base)",
                  background: active ? "var(--panel)" : "transparent",
                  color: active ? "var(--text)" : "var(--text3)",
                  boxShadow: active
                    ? "0 1px 4px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.06)"
                    : "none",
                  whiteSpace: "nowrap",
                }}
                onMouseEnter={e => {
                  if (!active) e.currentTarget.style.color = "var(--text2)";
                }}
                onMouseLeave={e => {
                  if (!active) e.currentTarget.style.color = "var(--text3)";
                }}
              >
                {t.label}

                {/* AI badge */}
                {t.badge && (
                  <span style={{
                    fontSize: 8, fontWeight: 700, letterSpacing: ".06em",
                    padding: "1px 5px", borderRadius: "var(--r-pill)",
                    background: "var(--primary-dim)",
                    color: "var(--primary)",
                    border: "1px solid var(--primary-ring)",
                  }}>
                    {t.badge}
                  </span>
                )}

                {/* Fail count badge — danger color */}
                {showFail && (
                  <span style={{
                    fontSize: 8, fontWeight: 700,
                    padding: "1px 5px", borderRadius: "var(--r-pill)",
                    background: "var(--danger-dim)",
                    color: "var(--danger)",
                    border: "1px solid var(--danger-border)",
                    minWidth: 16, textAlign: "center",
                  }}>
                    {failCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Live KPI strip — corrected field names */}
        {results && (
          <div style={{
            display: "flex", gap: 12, alignItems: "center",
            marginRight: 12,
          }}>
            {[
              {
                label: "Q",
                value: results.Q?.toFixed(0) ?? "—",
                unit: "t/h",
                ok: (results.Q ?? 0) >= inputs.Q_req,
                color: (results.Q ?? 0) >= inputs.Q_req
                  ? "var(--success)" : "var(--danger)",
              },
              {
                label: "P",
                value: results.P_total?.toFixed(1) ?? "—",
                unit: "kW",
                color: "var(--warning)",
              },
              {
                label: "v",
                value: results.v?.toFixed(2) ?? "—",
                unit: "m/s",
                color: "var(--primary)",
              },
            ].map((k) => (
              <div key={k.label} style={{
                display: "flex", flexDirection: "column", alignItems: "center",
                padding: "3px 10px",
                background: "var(--surface)",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--border)",
                minWidth: 52,
              }}>
                <span style={{
                  fontSize: 9, color: "var(--muted)",
                  fontWeight: 600, letterSpacing: ".06em",
                  textTransform: "uppercase",
                }}>{k.label}</span>
                <span style={{
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 13, fontWeight: 700,
                  color: k.color, lineHeight: 1.2,
                }}>{k.value}</span>
                <span style={{
                  fontSize: 9, color: "var(--muted)",
                  fontFamily: "JetBrains Mono, monospace",
                }}>{k.unit}</span>
              </div>
            ))}
          </div>
        )}

        {/* Save / Load */}
        <button
          className="btn-secondary"
          style={{ padding: "5px 12px", fontSize: 11, flexShrink: 0 }}
          onClick={() => setShowSaveLoad(true)}
        >
          💾 Save / Load
        </button>
      </div>

      {/* Loading bar */}
      {loading && <div className="loading-bar" />}

      {/* Body */}
      <div className="app-body">
        <InputSidebar inputs={inputs} setField={setField} results={results} />

        <div className="main-content">
          {error && (
            <div className="warn-item w-fail" style={{ margin: 12 }}>
              ⚠ API Error: {error}
            </div>
          )}

          {activeNav === "design" && (
            <>
              <div className="sec-hdr">Elevator Schematic</div>
              <div className="canvas-wrap">
                <ElevatorSchematic inputs={inputs} results={results} />
              </div>
              <div className="sec-hdr">Key Performance Indicators</div>
              <KpiGrid results={results} inputs={inputs} />
              <div className="sec-hdr">Performance Analysis</div>
              <ChartsPanel results={results} inputs={inputs} />
            </>
          )}

          {activeNav === "optimizer" && (
            <>
              <div className="sec-hdr">Multi-Parameter Optimizer</div>
              <OptimizerPanel inputs={inputs} onApply={applyOptimizer} />
            </>
          )}

          {activeNav === "components" && (
            <>
              <div className="sec-hdr">Component-Level Design</div>
              <ComponentPanel results={results} inputs={inputs} />
            </>
          )}

          {activeNav === "checks" && (
            <>
              <div className="sec-hdr">Engineering Checks &amp; Warnings</div>
              <ChecksPanel results={results} inputs={inputs} />
            </>
          )}
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
