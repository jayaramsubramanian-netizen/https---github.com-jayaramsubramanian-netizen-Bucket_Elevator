// BucketElevatorPage.jsx — full page assembling all panels
import { useState } from "react";
import { useElevatorCalc } from "../hooks/useElevatorCalc";
import InputSidebar from "../components/InputSidebar";
import ElevatorSchematic from "../components/ElevatorSchematic";
import KpiGrid from "../components/KpiGrid";
import ChartsPanel from "../components/ChartsPanel";
import OptimizerPanel from "../components/OptimizerPanel";
import ComponentPanel from "../components/ComponentPanel";
import ChecksPanel from "../components/ChecksPanel";
import SaveLoadModal from "../components/SaveLoadModal";

const NAV_TABS = [
  { id: "design",     label: "Design",      badge: null },
  { id: "optimizer",  label: "Optimizer",   badge: "AI" },
  { id: "components", label: "Components",  badge: null },
  { id: "checks",     label: "Eng. Checks", badge: null },
];

export default function BucketElevatorPage() {
  const { inputs, results, loading, error, setField, applyOptimizer, saveCurrentDesign, loadDesign } =
    useElevatorCalc();
  const [activeNav, setActiveNav]     = useState("design");
  const [showSaveLoad, setShowSaveLoad] = useState(false);

  // Derive fail-count badge for Checks tab
  const failCount = results?.checks?.filter((c) => c.status === "fail").length ?? 0;

  return (
    <>
      {/* ── Top Navigation ──────────────────────────────── */}
      <div className="nav">
        <div className="nav-brand">
          <div className="nav-logo">⚙</div>
          <div>
            <div className="nav-title">VECTRIX™</div>
            <div className="nav-sub">Bucket Elevator</div>
          </div>
        </div>

        <div className="nav-tabs">
          {NAV_TABS.map((t) => (
            <button
              key={t.id}
              className={`nav-tab ${activeNav === t.id ? "active" : ""}`}
              onClick={() => setActiveNav(t.id)}
            >
              {t.label}
              {t.badge && <span className="nav-badge">{t.badge}</span>}
              {t.id === "checks" && failCount > 0 && (
                <span className="nav-badge" style={{ background: "var(--accent)" }}>
                  {failCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Quick KPIs — uses normalised FastAPI field names */}
        {results && (
          <div style={{ display: "flex", gap: 16, alignItems: "center", fontSize: 11, fontFamily: "JetBrains Mono" }}>
            <span style={{ color: "var(--muted)" }}>
              Q:{" "}
              <span style={{ color: (results.Q_th ?? 0) >= inputs.Q_req ? "var(--green)" : "var(--red)", fontWeight: 700 }}>
                {(results.Q_th ?? 0).toFixed(0)}
              </span>{" "}
              t/h
            </span>
            <span style={{ color: "var(--muted)" }}>
              P:{" "}
              <span style={{ color: "var(--amber)", fontWeight: 700 }}>
                {(results.power_P_total ?? 0).toFixed(1)}
              </span>{" "}
              kW
            </span>
            <span style={{ color: "var(--muted)" }}>
              v:{" "}
              <span style={{ color: "var(--blue)", fontWeight: 700 }}>
                {(results.v_ms ?? 0).toFixed(2)}
              </span>{" "}
              m/s
            </span>
          </div>
        )}

        <button
          className="btn-secondary"
          style={{ marginLeft: 12, padding: "5px 12px", fontSize: 11 }}
          onClick={() => setShowSaveLoad(true)}
        >
          💾 Save / Load
        </button>
      </div>

      {/* ── Loading bar ─────────────────────────────────── */}
      {loading && <div className="loading-bar" />}

      {/* ── Body ────────────────────────────────────────── */}
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

      {/* ── Save/Load Modal ─────────────────────────────── */}
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