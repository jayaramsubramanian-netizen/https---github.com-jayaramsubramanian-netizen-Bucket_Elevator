// BucketElevatorPage.jsx — v1.4.0
// Tab-driven 3-column workstation layout
//
// CHANGE FROM v1.3.0
// ─────────────────────────────────────────────────────────────────
// Added 5th nav pill: "Report"
//   Middle column → ReportView (Executive summary + Detailed calcs,
//                    both collapsible sections)
//   Right column  → DesignReview (persistent) + BOMCard
//
// BOMCard MOVED from Components tab → Report tab right column.
// Components tab right column ("ComponentHealth") unchanged.
// Components tab middle column no longer renders BOMCard —
// now: ComponentPanel, StructuralDetailCard, TakeupCasingCard,
//      ChuteFlowCard, MaintenanceCard (BOMCard removed).
//
// RootCausePanel and MaintenanceCard redesigned for readability +
// conflict detection (see those files for details).
// ─────────────────────────────────────────────────────────────────

import { useState, useEffect } from "react";
import { useElevatorCalc }          from "./hooks/useElevatorCalc";
import InputSidebar                 from "./components/InputSidebar";
import ElevatorSchematic            from "./components/ElevatorSchematic";
import KpiGrid                      from "./components/KpiGrid";
import ChartsPanel                  from "./components/ChartsPanel";
import OptimizerPanel               from "./components/OptimizerPanel";
import ComponentPanel               from "./components/ComponentPanel";
import ChecksPanel                  from "./components/ChecksPanel";
import SaveLoadModal                from "./components/SaveLoadModal";
import EquipmentTree                from "./components/EquipmentTree";
import DesignReview                 from "./components/DesignReview";
import DesignRecommendationsPanel   from "./components/DesignRecommendationsPanel";
import RootCausePanel               from "./components/RootCausePanel";
import StructuralDetailCard         from "./components/StructuralDetailCard";
import TakeupCasingCard             from "./components/TakeupCasingCard";
import ChuteFlowCard                from "./components/ChuteFlowCard";
import BOMCard                      from "./components/BOMCard";
import MaintenanceCard               from "./components/MaintenanceCard";
import ReportView                   from "./components/ReportView";

// ─── Nav tab definitions ────────────────────────────────────────────────────
const TABS = [
  { id: "design",     label: "Results"    },
  { id: "optimizer",  label: "Optimizer", badge: "AI" },
  { id: "components", label: "Components" },
  { id: "checks",     label: "Checks",    failBadge: true },
  { id: "report",     label: "Report"     },
];

// ─── Shared column header ────────────────────────────────────────────────────
function ColHeader({ label, sub, action }) {
  return (
    <div style={{
      height: 36, flexShrink: 0,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 12px",
      borderBottom: "1px solid var(--border)",
      background: "var(--panel)",
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
        <span style={{
          fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: "var(--text3)",
        }}>{label}</span>
        {sub && (
          <span style={{ fontSize: 8.5, color: "var(--muted)", letterSpacing: ".03em" }}>
            {sub}
          </span>
        )}
      </div>
      {action}
    </div>
  );
}

// ─── Right-col summary panels ────────────────────────────────────────────────

function ChecksSummary({ results }) {
  const checks = results?.checks || [];
  const pass = checks.filter(c => c.type === "ok").length;
  const warn = checks.filter(c => c.type === "warn").length;
  const fail = checks.filter(c => c.type === "fail").length;
  const info = checks.filter(c => c.type === "info" || !c.type).length;
  const total = checks.length;
  const pct = total ? Math.round((pass / total) * 100) : null;

  const Tile = ({ count, label, color, dim }) => (
    <div style={{
      flex: 1, textAlign: "center", padding: "8px 4px",
      background: dim, borderRadius: 5, border: `1px solid ${color}30`,
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1,
        fontFamily: "JetBrains Mono, monospace" }}>{count}</div>
      <div style={{ fontSize: 8, color: "var(--text3)", marginTop: 3,
        letterSpacing: ".06em", textTransform: "uppercase" }}>{label}</div>
    </div>
  );

  return (
    <div style={{ padding: "10px 10px 0" }}>
      <div style={{
        fontSize: 8.5, fontWeight: 700, letterSpacing: ".07em",
        textTransform: "uppercase", color: "var(--text3)", marginBottom: 7,
      }}>Check Summary</div>

      <div style={{ display: "flex", gap: 5, marginBottom: 10 }}>
        <Tile count={pass}  label="Pass" color="var(--success)" dim="rgba(16,185,129,.08)" />
        <Tile count={warn}  label="Warn" color="var(--warning)" dim="rgba(245,158,11,.08)" />
        <Tile count={fail}  label="Fail" color="var(--danger)"  dim="rgba(239,68,68,.08)" />
        <Tile count={info}  label="Info" color="var(--text3)"   dim="rgba(100,116,139,.08)" />
      </div>

      {pct !== null && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between",
            fontSize: 8.5, color: "var(--text3)", marginBottom: 4 }}>
            <span>CEMA 375 Compliance</span>
            <span style={{ color: pct >= 90 ? "var(--success)" : pct >= 70 ? "var(--warning)" : "var(--danger)",
              fontWeight: 700 }}>{pct}%</span>
          </div>
          <div style={{ height: 5, borderRadius: 3, background: "var(--border)" }}>
            <div style={{
              height: "100%", borderRadius: 3, width: `${pct}%`,
              background: pct >= 90 ? "var(--success)" : pct >= 70 ? "var(--warning)" : "var(--danger)",
              transition: "width .4s",
            }} />
          </div>
        </div>
      )}
    </div>
  );
}

function ComponentHealth({ results }) {
  const r = results || {};
  const items = [
    { label: "Shaft",        ok: r.key_check?.pass !== false && r.shaft_d_mm > 0 },
    { label: "Hub / Key",    ok: r.key_check?.pass !== false },
    { label: "Bearings",     ok: (r.L10 ?? 0) >= 17500 },
    { label: "Lagging",      ok: r.lagging?.slip_safe !== false },
    { label: "End Disc",     ok: r.end_disc != null },
    { label: "Bolt Fatigue", ok: r.bolt_fatigue?.pass_infinite_life !== false },
    { label: "Gravity T/U",  ok: r.takeup_gravity != null },
    { label: "Casing",       ok: r.casing_panel?.status !== "fail" },
    { label: "Chute",        ok: r.discharge_chute != null },
  ];

  return (
    <div style={{ padding: "10px 10px 0" }}>
      <div style={{
        fontSize: 8.5, fontWeight: 700, letterSpacing: ".07em",
        textTransform: "uppercase", color: "var(--text3)", marginBottom: 7,
      }}>Component Health</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {items.map(({ label, ok }) => (
          <div key={label} style={{
            display: "flex", alignItems: "center", gap: 7, padding: "4px 7px",
            background: "var(--panel2)", borderRadius: 4,
            border: `1px solid ${ok ? "rgba(16,185,129,.2)" : "rgba(100,116,139,.15)"}`,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
              background: !results ? "var(--text3)" : ok ? "var(--success)" : "var(--warning)",
              boxShadow: !results ? "none" : ok ? "0 0 4px var(--success)" : "none",
            }} />
            <span style={{ fontSize: 10, color: "var(--text2)", flex: 1 }}>{label}</span>
            <span style={{
              fontSize: 8, color: !results ? "var(--text3)" : ok ? "var(--success)" : "var(--warning)",
              fontWeight: 700,
            }}>{!results ? "—" : ok ? "OK" : "CHK"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function OptimizerSummary({ results }) {
  if (!results) return (
    <div style={{ padding: 12, fontSize: 10, color: "var(--text3)" }}>
      Run the optimizer to see best candidate summary.
    </div>
  );
  return (
    <div style={{ padding: "10px 10px 0" }}>
      <div style={{
        fontSize: 8.5, fontWeight: 700, letterSpacing: ".07em",
        textTransform: "uppercase", color: "var(--text3)", marginBottom: 7,
      }}>Current Design</div>
      {[
        ["Bucket",   results.bucket?.id ?? "—"],
        ["Speed",    `${Number(results.v ?? 0).toFixed(2)} m/s`],
        ["Power",    `${results.P_total ?? results.power_P_total ?? "—"} kW`],
        ["Motor",    `${results.motor_kw ?? results.motor_kW ?? "—"} kW`],
        ["Capacity", `${Number(results.Q ?? 0).toFixed(1)} t/h`],
        ["CR",       `${Number(results.cr ?? 0).toFixed(3)}`],
      ].map(([k, v]) => (
        <div key={k} style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "4px 0", borderBottom: "1px solid var(--border)", fontSize: 10,
        }}>
          <span style={{ color: "var(--text3)" }}>{k}</span>
          <span style={{ color: "var(--text)", fontFamily: "JetBrains Mono, monospace",
            fontWeight: 600 }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function BucketElevatorPage({ onResultsChange }) {
  const {
    inputs, results, loading, error,
    setField, applyOptimizer, saveCurrentDesign, loadDesign,
  } = useElevatorCalc();

  const [activeTab, setActiveTab]   = useState("design");
  const [showSaveLoad, setShowSaveLoad] = useState(false);
  const [showTree, setShowTree]     = useState(true);
  const [activeDisc, setActiveDisc] = useState(null);
  const [chartTab, setChartTab]     = useState("speed");

  useEffect(() => {
    if (onResultsChange) onResultsChange({ results, inputs });
  }, [results, inputs, onResultsChange]);

  const failCount = results?.checks?.filter(c => c.type === "fail").length ?? 0;
  const warnCount = results?.checks?.filter(c => c.type === "warn").length ?? 0;

  // Middle column title per tab
  const middleLabel = {
    design:     "Equipment Model",
    optimizer:  "Design Optimizer",
    components: "Component Design",
    checks:     "Engineering Checks",
    report:     "Engineering Report",
  }[activeTab];

  const middleSub = {
    design: results
      ? `Bucket ${results.bucket?.id} · ${results.bucket?.W}×${results.bucket?.H}mm · ${results.bucket?.V}L`
      : "Calculating…",
    optimizer:  "RPM × Series × Fill grid search",
    components: `${results ? "Structural + chute + maintenance detail" : "Run calculation first"}`,
    checks:     results ? `${results.checks?.length ?? 0} CEMA 375-2017 checks` : "—",
    report:     "Executive summary + full calculation record",
  }[activeTab];

  return (
    <>
      {/* ═══════════════════════════════════════════
          NAV BAR
          ═══════════════════════════════════════════ */}
      <div className="nav">

        {/* Brand */}
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

        {/* Tab pills */}
        <div style={{
          display: "flex", gap: 2,
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: "var(--r-pill)", padding: "3px", marginRight: 14,
        }}>
          {TABS.map(t => {
            const active = activeTab === t.id;
            const showFail = t.failBadge && failCount > 0;
            return (
              <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
                display: "flex", alignItems: "center", gap: 5,
                padding: "5px 11px", borderRadius: "var(--r-pill)",
                border: "none", cursor: "pointer",
                fontFamily: "var(--ff-ui)", fontSize: 11.5,
                fontWeight: active ? 600 : 400,
                background: active ? "var(--panel)" : "transparent",
                color:      active ? "var(--text)"  : "var(--text3)",
                boxShadow:  active
                  ? "0 1px 4px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.05)"
                  : "none",
                transition: "all var(--t-base)",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={e => { if (!active) e.currentTarget.style.color = "var(--text2)"; }}
              onMouseLeave={e => { if (!active) e.currentTarget.style.color = "var(--text3)"; }}
              >
                {t.label}
                {t.badge && !showFail && (
                  <span style={{ fontSize: 7.5, fontWeight: 700, padding: "1px 5px",
                    borderRadius: "var(--r-pill)", background: "var(--primary-dim)",
                    color: "var(--primary)", border: "1px solid var(--primary-ring)" }}>
                    {t.badge}
                  </span>
                )}
                {showFail && (
                  <span style={{ fontSize: 7.5, fontWeight: 700, padding: "1px 5px",
                    borderRadius: "var(--r-pill)", background: "var(--danger-dim)",
                    color: "var(--danger)", border: "1px solid var(--danger-border)",
                    minWidth: 16, textAlign: "center" }}>
                    {failCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Live KPI strip */}
        <div style={{ display: "flex", gap: 7, alignItems: "center", marginRight: 10 }}>
          {[
            { label: "Q",  value: results?.Q,       dp: 0, unit: "t/h",
              color: results?.Q == null ? "var(--muted)"
                : Number(results.Q) >= Number(inputs.Q_req) ? "var(--success)" : "var(--danger)" },
            { label: "P",  value: results?.P_total,  dp: 1, unit: "kW",
              color: results?.P_total == null ? "var(--muted)" : "var(--warning)" },
            { label: "v",  value: results?.v,        dp: 2, unit: "m/s",
              color: results?.v == null ? "var(--muted)" : "var(--primary)" },
          ].map(k => {
            const fmtd = k.value != null && !Number.isNaN(Number(k.value))
              ? Number(k.value).toFixed(k.dp)
              : loading ? "···" : "—";
            return (
              <div key={k.label} style={{
                display: "flex", flexDirection: "column", alignItems: "center",
                padding: "3px 7px", background: "var(--surface)",
                borderRadius: "var(--r-md)", border: "1px solid var(--border)",
                minWidth: 46, opacity: loading ? 0.6 : 1, transition: "opacity .2s",
              }}>
                <span style={{ fontSize: 8.5, color: "var(--muted)", fontWeight: 600,
                  letterSpacing: ".06em", textTransform: "uppercase" }}>{k.label}</span>
                <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 13,
                  fontWeight: 700, color: k.color, lineHeight: 1.2 }}>{fmtd}</span>
                <span style={{ fontSize: 8.5, color: "var(--muted)",
                  fontFamily: "JetBrains Mono,monospace" }}>{k.unit}</span>
              </div>
            );
          })}
        </div>

        <button className="btn-secondary"
          style={{ padding: "5px 11px", fontSize: 11, flexShrink: 0 }}
          onClick={() => setShowSaveLoad(true)}>
          💾 Save / Load
        </button>
      </div>

      {loading && <div className="loading-bar" />}
      {error && (
        <div className="warn-item w-fail" style={{ margin: "5px 10px", flexShrink: 0 }}>
          ⚠ API Error: {error}
        </div>
      )}

      {/* ═══════════════════════════════════════════
          3-COLUMN WORKSTATION BODY
          ═══════════════════════════════════════════ */}
      <div style={{
        display: "flex", flex: 1, overflow: "hidden", background: "var(--bg)",
      }}>

        {/* ── Equipment Tree (collapsible 190px) ───── */}
        {showTree && (
          <div style={{
            width: 190, flexShrink: 0,
            display: "flex", flexDirection: "column",
            borderRight: "1px solid var(--border)",
            background: "var(--panel2)", overflow: "hidden",
          }}>
            <ColHeader
              label="Equipment" sub="BE-001"
              action={
                <button onClick={() => setShowTree(false)} style={{
                  background: "none", border: "none", cursor: "pointer",
                  color: "var(--muted)", fontSize: 12, padding: "0 2px", lineHeight: 1,
                }} title="Collapse tree">✕</button>
              }
            />
            <div style={{ flex: 1, overflow: "hidden" }}>
              <EquipmentTree
                results={results} inputs={inputs}
                onNodeClick={disc => {
                  setActiveDisc(disc);
                  document.getElementById(`disc-${disc}`)
                    ?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              />
            </div>
          </div>
        )}

        {/* ── Parameters sidebar ─────────────────── */}
        <div style={{
          width: showTree ? 248 : 290,
          flexShrink: 0, display: "flex", flexDirection: "column",
          borderRight: "1px solid var(--border)",
          background: "var(--panel)", overflow: "hidden",
          transition: "width .2s ease",
        }}>
          <ColHeader
            label="Parameters" sub="CEMA 375 Inputs"
            action={!showTree && (
              <button onClick={() => setShowTree(true)} style={{
                display: "flex", alignItems: "center", gap: 4,
                background: "var(--primary-dim)", border: "1px solid var(--primary-ring)",
                borderRadius: "var(--r-sm)", cursor: "pointer",
                color: "var(--primary)", fontSize: 9, fontWeight: 600,
                padding: "2px 7px",
              }}>⛏ TREE</button>
            )}
          />
          <InputSidebar
            inputs={inputs} setField={setField}
            results={results} activeDisc={activeDisc}
          />
        </div>

        {/* ─────────────────────────────────────────────────────────────
            MIDDLE COLUMN — tab-driven main content
            ───────────────────────────────────────────────────────────── */}
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
          overflow: "hidden", borderRight: "1px solid var(--border)", minWidth: 0,
        }}>
          <ColHeader
            label={middleLabel} sub={middleSub}
            action={activeTab === "design" && results && (
              <div style={{ display: "flex", gap: 5 }}>
                {failCount > 0 && (
                  <span style={{ fontSize: 8.5, fontWeight: 700, padding: "2px 7px",
                    borderRadius: "var(--r-pill)", background: "var(--danger-dim)",
                    color: "var(--danger)", border: "1px solid var(--danger-border)" }}>
                    {failCount} FAIL
                  </span>
                )}
                {warnCount > 0 && (
                  <span style={{ fontSize: 8.5, fontWeight: 700, padding: "2px 7px",
                    borderRadius: "var(--r-pill)", background: "var(--warning-dim)",
                    color: "var(--warning)", border: "1px solid var(--warning-border)" }}>
                    {warnCount} WARN
                  </span>
                )}
              </div>
            )}
          />

          {/* ── RESULTS TAB — schematic + chart strip ─────────────────── */}
          {activeTab === "design" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{ flex: 1, overflow: "hidden", position: "relative" }}>
                <ElevatorSchematic inputs={inputs} results={results} />
              </div>
              <div style={{
                flexShrink: 0, height: 220,
                borderTop: "1px solid var(--border)", background: "var(--bg)",
                display: "flex", flexDirection: "column",
              }}>
                <div style={{
                  display: "flex", borderBottom: "1px solid var(--border)",
                  background: "var(--panel2)", padding: "0 10px", flexShrink: 0,
                }}>
                  {[
                    { id: "speed",   label: "Speed Sweep" },
                    { id: "fill",    label: "Fill Analysis" },
                    { id: "traj",    label: "Trajectory" },
                    { id: "tension", label: "Tension" },
                  ].map(t => (
                    <button key={t.id} onClick={() => setChartTab(t.id)} style={{
                      padding: "6px 12px", fontSize: 10.5,
                      fontWeight: chartTab === t.id ? 600 : 400,
                      cursor: "pointer", border: "none", background: "transparent",
                      color: chartTab === t.id ? "var(--primary)" : "var(--text3)",
                      borderBottom: `2px solid ${chartTab === t.id ? "var(--primary)" : "transparent"}`,
                      marginBottom: -1, transition: "all var(--t-base)",
                      fontFamily: "var(--ff-ui)",
                    }}
                    onMouseEnter={e => { if (chartTab !== t.id) e.currentTarget.style.color = "var(--text2)"; }}
                    onMouseLeave={e => { if (chartTab !== t.id) e.currentTarget.style.color = "var(--text3)"; }}
                    >{t.label}</button>
                  ))}
                </div>
                <div style={{ flex: 1, overflow: "hidden" }}>
                  <ChartsPanel results={results} inputs={inputs} activeTab={chartTab} />
                </div>
              </div>
            </div>
          )}

          {/* ── OPTIMIZER TAB ──────────────────────────────────────────── */}
          {activeTab === "optimizer" && (
            <div style={{ flex: 1, overflowY: "auto" }}>
              <OptimizerPanel inputs={inputs} onApply={applyOptimizer} />
            </div>
          )}

          {/* ── COMPONENTS TAB ─────────────────────────────────────────── */}
          {activeTab === "components" && (
            <div style={{ flex: 1, overflowY: "auto" }}>
              <ComponentPanel results={results} inputs={inputs} />
              {results && (
                <>
                  <div style={{
                    padding: "10px 12px 4px",
                    fontSize: 8.5, fontWeight: 700, letterSpacing: ".08em",
                    textTransform: "uppercase", color: "var(--text3)",
                    borderTop: "2px solid var(--border)", background: "var(--panel2)",
                  }}>
                    Structural Design Detail
                  </div>
                  <StructuralDetailCard results={results} />
                  <TakeupCasingCard results={results} />
                  <ChuteFlowCard results={results} />
                  {/* BOMCard moved to Report tab (v1.4.0) */}
                  <MaintenanceCard results={results} />
                </>
              )}
            </div>
          )}

          {/* ── CHECKS TAB ─────────────────────────────────────────────── */}
          {activeTab === "checks" && (
            <div style={{ flex: 1, overflowY: "auto" }}>
              <RootCausePanel results={results} setField={setField} />
              <DesignRecommendationsPanel
                recommendations={results?.design_recommendations}
              />
              <ChecksPanel results={results} inputs={inputs} />
            </div>
          )}

          {/* ── REPORT TAB (v1.4.0 / Task 9) ──────────────────────────────
              Executive summary + Detailed calculation record.
              Both sections collapsible via ReportView's own toggles. ── */}
          {activeTab === "report" && (
            <ReportView results={results} inputs={inputs} />
          )}
        </div>

        {/* ─────────────────────────────────────────────────────────────
            RIGHT COLUMN — 280px, DesignReview + context panel
            ───────────────────────────────────────────────────────────── */}
        <div style={{
          width: 280, flexShrink: 0,
          display: "flex", flexDirection: "column",
          overflow: "hidden", background: "var(--panel)",
        }}>
          <ColHeader
            label="Status"
            sub={results
              ? `${results.checks?.length ?? 0} checks · ${results.motor_kw ?? results.motor_kW ?? "—"}kW`
              : undefined}
          />

          {/* DesignReview — always visible */}
          <DesignReview results={results} />

          {/* Context panel — scrollable, changes with tab */}
          <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid var(--border)" }}>

            {activeTab === "design" && (
              <div style={{ padding: "0 0 8px" }}>
                <KpiGrid results={results} inputs={inputs} compact />
              </div>
            )}

            {activeTab === "optimizer" && (
              <OptimizerSummary results={results} />
            )}

            {activeTab === "components" && (
              <ComponentHealth results={results} />
            )}

            {activeTab === "checks" && (
              <ChecksSummary results={results} />
            )}

            {/* Report tab right column: preliminary BOM (v1.4.0) */}
            {activeTab === "report" && (
              <BOMCard results={results} />
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
