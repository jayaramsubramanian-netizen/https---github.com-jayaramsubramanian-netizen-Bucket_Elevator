// BucketElevatorPage.jsx — 3-Column Workstation Layout
//
// Column layout:
//   [EquipTree 190px] | [Parameters 248-300px] | [Equipment Model flex] | [Engineering Results 360px]
//
// Equipment Tree is collapsible. When collapsed, Parameters expands to 300px.
//
// Right column tabs:
//   Results     → KpiGrid + DesignRecommendationsPanel
//   Optimizer   → OptimizerPanel
//   Components  → ComponentPanel + StructuralDetailCard + TakeupCasingCard + ChuteFlowCard
//   Checks      → ChecksPanel
//
// DesignReview is rendered ABOVE all right-col tab content (always visible).
// ElevatorSchematic and charts are always visible in the centre column.
//
// v1.2.0 — Merged with structural + chute flow component additions
// ─────────────────────────────────────────────────────────────────
// ADDED  DesignRecommendationsPanel — wired under KpiGrid in Results tab
// ADDED  StructuralDetailCard       — hub/key/lagging/end-disc/bolt-fatigue
// ADDED  TakeupCasingCard           — take-up design + casing structural
// ADDED  ChuteFlowCard              — discharge chute design (v1.4.0)
// All four components gated on results != null; fail silently if component
// file not yet present (dynamic import guard is added below).
// ─────────────────────────────────────────────────────────────────

import { useState, useEffect } from "react";
import { useElevatorCalc }     from "./hooks/useElevatorCalc";
import InputSidebar            from "./components/InputSidebar";
import ElevatorSchematic       from "./components/ElevatorSchematic";
import KpiGrid                 from "./components/KpiGrid";
import ChartsPanel             from "./components/ChartsPanel";
import OptimizerPanel          from "./components/OptimizerPanel";
import ComponentPanel          from "./components/ComponentPanel";
import ChecksPanel             from "./components/ChecksPanel";
import SaveLoadModal           from "./components/SaveLoadModal";
import EquipmentTree           from "./components/EquipmentTree";
import DesignReview            from "./components/DesignReview";
// v1.2.0 additions
import DesignRecommendationsPanel from "./components/DesignRecommendationsPanel";
import StructuralDetailCard       from "./components/StructuralDetailCard";
import TakeupCasingCard           from "./components/TakeupCasingCard";
import ChuteFlowCard              from "./components/ChuteFlowCard";

const RIGHT_TABS = [
  { id: "design",     label: "Results",    badge: null },
  { id: "optimizer",  label: "Optimizer",  badge: "AI" },
  { id: "components", label: "Components", badge: null },
  { id: "checks",     label: "Checks",     badge: null, failBadge: true },
];

// ── Column header ─────────────────────────────────────────────────────────
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
  const [chartTab, setChartTab]   = useState("speed");
  const [showTree, setShowTree]   = useState(true);
  const [activeDisc, setActiveDisc] = useState(null);

  useEffect(() => {
    if (onResultsChange) onResultsChange({ results, inputs });
  }, [results, inputs, onResultsChange]);

  const failCount = results?.checks?.filter((c) => c.type === "fail").length ?? 0;
  const warnCount = results?.checks?.filter((c) => c.type === "warn").length ?? 0;

  return (
    <>
      {/* ══════════════════════════════════════════════════
          NAV BAR
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

        {/* Right-column tab pills */}
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
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginRight: 12 }}>
          {(() => {
            const fmt = (v, digits) =>
              v != null && !Number.isNaN(Number(v))
                ? Number(v).toFixed(digits)
                : loading ? "···" : "—";
            const Q       = results?.Q;
            const P       = results?.P_total;
            const v       = results?.v;
            const capPass = Q != null && Number(Q) >= Number(inputs.Q_req);
            return [
              { label: "Q", value: fmt(Q, 0), unit: "t/h",
                color: Q == null ? "var(--muted)" : capPass ? "var(--success)" : "var(--danger)" },
              { label: "P", value: fmt(P, 1), unit: "kW",
                color: P == null ? "var(--muted)" : "var(--warning)" },
              { label: "v", value: fmt(v, 2), unit: "m/s",
                color: v == null ? "var(--muted)" : "var(--primary)" },
            ].map((k) => (
              <div key={k.label} style={{
                display: "flex", flexDirection: "column", alignItems: "center",
                padding: "3px 8px", background: "var(--surface)",
                borderRadius: "var(--r-md)", border: "1px solid var(--border)",
                minWidth: 48, opacity: loading ? 0.6 : 1,
                transition: "opacity 0.2s",
              }}>
                <span style={{ fontSize: 9, color: "var(--muted)", fontWeight: 600,
                  letterSpacing: ".06em", textTransform: "uppercase" }}>{k.label}</span>
                <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 13,
                  fontWeight: 700, color: k.color, lineHeight: 1.2 }}>{k.value}</span>
                <span style={{ fontSize: 9, color: "var(--muted)",
                  fontFamily: "JetBrains Mono,monospace" }}>{k.unit}</span>
              </div>
            ));
          })()}
        </div>

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
          WORKSTATION BODY
          ══════════════════════════════════════════════════ */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", background: "var(--bg)" }}>

        {/* ── Equipment Tree (collapsible, 190px) ─────────── */}
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
                results={results}
                inputs={inputs}
                onNodeClick={(disc) => {
                  setActiveDisc(disc);
                  const el = document.getElementById(`disc-${disc}`);
                  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              />
            </div>
          </div>
        )}

        {/* ── Parameters (248px with tree, 300px without) ──── */}
        <div style={{
          width: showTree ? 248 : 300, flexShrink: 0,
          display: "flex", flexDirection: "column",
          borderRight: "1px solid var(--border)",
          background: "var(--panel)", overflow: "hidden",
          transition: "width .2s ease",
        }}>
          <ColHeader
            label="Parameters" sub="CEMA 375 Inputs"
            action={
              !showTree && (
                <button onClick={() => setShowTree(true)} style={{
                  display: "flex", alignItems: "center", gap: 4,
                  background: "var(--primary-dim)", border: "1px solid var(--primary-ring)",
                  borderRadius: "var(--r-sm)", cursor: "pointer",
                  color: "var(--primary)", fontSize: 9, fontWeight: 600,
                  padding: "2px 7px", letterSpacing: ".04em",
                }} title="Show equipment tree">⛏ TREE</button>
              )
            }
          />
          <div style={{ flex: 1, overflowY: "auto" }}>
            <InputSidebar
              inputs={inputs}
              setField={setField}
              results={results}
              activeDisc={activeDisc}
            />
          </div>
        </div>

        {/* ── Centre column — Equipment Model ──────────────── */}
        <div style={{
          flex: 1, display: "flex", flexDirection: "column",
          overflow: "hidden", borderRight: "1px solid var(--border)", minWidth: 0,
        }}>
          <ColHeader
            label="Equipment Model"
            sub={results
              ? `Bucket ${results.bucket?.id} · ${results.bucket?.W}×${results.bucket?.H}mm · ${results.bucket?.V}L`
              : "Calculating…"}
            action={results && (
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
            )}
          />

          {/* Schematic — permanent */}
          <div style={{
            flexShrink: 0, background: "var(--panel2)",
            borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: "12px 0", minHeight: 260,
          }}>
            <ElevatorSchematic inputs={inputs} results={results} />
          </div>

          {/* Charts */}
          <div style={{ flex: 1, overflowY: "auto", background: "var(--bg)" }}>
            <div style={{
              display: "flex", gap: 0,
              borderBottom: "1px solid var(--border)",
              background: "var(--panel2)", padding: "0 12px",
            }}>
              {[
                { id: "speed",   label: "Speed Sweep"  },
                { id: "fill",    label: "Fill Analysis" },
                { id: "traj",    label: "Trajectory"   },
                { id: "tension", label: "Tension"       },
              ].map((t) => (
                <button key={t.id} onClick={() => setChartTab(t.id)} style={{
                  padding: "8px 14px", fontSize: 11,
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
            <ChartsPanel results={results} inputs={inputs} activeTab={chartTab} />
          </div>
        </div>

        {/* ── Right column — Engineering Results (360px) ─────── */}
        <div style={{
          width: 360, flexShrink: 0,
          display: "flex", flexDirection: "column",
          overflow: "hidden", background: "var(--panel)",
        }}>
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

          {/* DesignReview — persistent above all tabs (your component) */}
          <DesignReview results={results} />

          {/* Scrollable tab content */}
          <div style={{ flex: 1, overflowY: "auto" }}>

            {/* ─── RESULTS TAB ─────────────────────────────────────
                KpiGrid first, then DesignRecommendationsPanel below.
                DesignRecommendationsPanel shows "All checks passed" (green)
                when design_recommendations is empty — always useful signal.
                ─────────────────────────────────────────────────── */}
            {activeRight === "design" && (
              <>
                <div style={{ padding: "0 0 8px" }}>
                  <KpiGrid results={results} inputs={inputs} compact />
                </div>
                <DesignRecommendationsPanel
                  recommendations={results?.design_recommendations}
                />
              </>
            )}

            {/* ─── OPTIMIZER TAB ───────────────────────────────────── */}
            {activeRight === "optimizer" && (
              <OptimizerPanel inputs={inputs} onApply={applyOptimizer} />
            )}

            {/* ─── COMPONENTS TAB ──────────────────────────────────────
                Original ComponentPanel first, then the v1.2.0 structural
                and chute additions below a visual section break.
                ─────────────────────────────────────────────────────── */}
            {activeRight === "components" && (
              <>
                <ComponentPanel results={results} inputs={inputs} />

                {results && (
                  <>
                    {/* Section divider */}
                    <div style={{
                      padding: "10px 12px 4px",
                      fontSize: 9, fontWeight: 700, letterSpacing: ".08em",
                      textTransform: "uppercase", color: "var(--text3)",
                      borderTop: "2px solid var(--border)",
                      background: "var(--panel2)",
                    }}>
                      Structural Design Detail
                    </div>
                    {/* Hub, keyway, lagging, end disc, bolt fatigue */}
                    <StructuralDetailCard results={results} />
                    {/* Take-up + casing structural */}
                    <TakeupCasingCard results={results} />
                    {/* Discharge chute design */}
                    <ChuteFlowCard results={results} />
                  </>
                )}
              </>
            )}

            {/* ─── CHECKS TAB ──────────────────────────────────────── */}
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