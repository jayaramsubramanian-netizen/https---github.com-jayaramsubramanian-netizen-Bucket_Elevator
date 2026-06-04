// OptimizerPanel.jsx — multi-select optimizer with variant reporting
import { useState, useCallback } from "react";
import { optimizeElevator } from "../api/client";

const C = {
  hi: "#243247",
  border2: "#ffffff1e",
  muted: "#64748b",
  muted2: "#94a3b8",
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  teal: "#14b8a6",
  red: "#ef4444",
  text: "#f1f5f9",
  accent: "#c8192e",
};

async function downloadVariantReport(candidates, inputs) {
  const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
  try {
    const res = await fetch(`${BASE}/bucket-elevator/report-variants`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidates, inputs }),
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "elevator_variants.pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Variant report failed: ${e.message}`);
  }
}

export default function OptimizerPanel({ inputs, onApply }) {
  const [objective, setObjective] = useState("power");
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set()); // indices of pinned variants

  const runOptimizer = useCallback(async () => {
    setRunning(true);
    setError(null);
    setSelected(new Set());
    try {
      const data = await optimizeElevator(inputs, objective);
      setResults(data);
      // Auto-pin rank 1
      setSelected(new Set([0]));
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }, [inputs, objective]);

  const toggleSelect = (i) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  const best = results?.candidates?.[0];
  const pinned = results?.candidates?.filter((_, i) => selected.has(i)) ?? [];
  const pinnedNone = pinned.length === 0;

  return (
    <div
      style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}
    >
      <div style={{ fontSize: 11, color: C.muted }}>
        Multi-objective optimizer searches RPM × Bucket × Fill space subject to
        Q ≥ <span style={{ color: C.text }}>{inputs.Q_req}</span> t/h and CEMA
        speed limits. Select one or more variants to apply or export as a
        comparison report.
      </div>

      {/* Objective selector */}
      <div className="inp-field">
        <div className="inp-label">Objective Function</div>
        <select
          className="inp-sel"
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
        >
          <option value="power">Minimize Power</option>
          <option value="tension">Minimize Belt Tension</option>
          <option value="motor">Minimize Motor Size</option>
          <option value="balanced">
            Balanced (Power + Tension + Discharge)
          </option>
        </select>
      </div>

      <button
        className="btn-primary"
        style={{ margin: 0 }}
        onClick={runOptimizer}
        disabled={running}
      >
        {running ? "⟳  OPTIMIZING…" : "▶  RUN OPTIMIZER"}
      </button>

      {error && <div className="warn-item w-fail">{error}</div>}

      {results && best && (
        <>
          {/* Summary strip */}
          <div
            style={{
              padding: "10px 12px",
              background: C.hi,
              borderRadius: "var(--r-md)",
              border: `1px solid ${C.border2}`,
              fontSize: 11,
            }}
          >
            <span style={{ color: C.muted }}>Best: </span>
            <span
              style={{
                color: C.green,
                fontFamily: "JetBrains Mono",
                fontWeight: 700,
              }}
            >
              {best.rpm} RPM · Bucket {best.bucket_id} · Fill {best.fill}% ·{" "}
              {best.power} kW · CR={best.cr}
            </span>
            <span style={{ color: C.muted, marginLeft: 8 }}>
              ({results.count} feasible, {selected.size} selected)
            </span>
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="btn-secondary"
              style={{ margin: 0 }}
              disabled={selected.size !== 1}
              title={
                selected.size !== 1 ? "Select exactly one variant to apply" : ""
              }
              onClick={() => {
                const idx = [...selected][0];
                const c = results.candidates[idx];
                onApply({ rpm: c.rpm, bucket_id: c.bucket_id, fill: c.fill });
              }}
            >
              ✓ Apply Selected to Design
            </button>

            <button
              className="btn-secondary"
              style={{ margin: 0 }}
              disabled={pinnedNone}
              title={pinnedNone ? "Select at least one variant" : ""}
              onClick={() => downloadVariantReport(pinned, inputs)}
            >
              ⬇ Export{" "}
              {pinned.length > 0
                ? `${pinned.length} Variant${pinned.length > 1 ? "s" : ""}`
                : "Variants"}{" "}
              as PDF
            </button>

            <button
              className="btn-secondary"
              style={{ margin: 0, fontSize: 10 }}
              onClick={() =>
                setSelected(new Set(results.candidates.map((_, i) => i)))
              }
            >
              Select All
            </button>
            <button
              className="btn-secondary"
              style={{ margin: 0, fontSize: 10 }}
              onClick={() => setSelected(new Set())}
            >
              Clear
            </button>
          </div>

          {selected.size > 0 && (
            <div style={{ fontSize: 10, color: C.teal }}>
              {selected.size} variant{selected.size > 1 ? "s" : ""} selected —{" "}
              {selected.size === 1
                ? "click Apply to use in design, or Export to generate PDF"
                : "Export will generate a side-by-side comparison report"}
            </div>
          )}

          {/* Results table */}
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 32 }}>⬜</th>
                  <th>Rank</th>
                  <th>RPM</th>
                  <th>Bucket</th>
                  <th>Fill %</th>
                  <th>Q t/h</th>
                  <th>P kW</th>
                  <th>T kN</th>
                  <th>CR</th>
                  <th>Motor</th>
                </tr>
              </thead>
              <tbody>
                {results.candidates.map((c, i) => {
                  const isPinned = selected.has(i);
                  const isBest = i === 0;
                  const crBad = c.cr < 1.0 || c.cr > 2.5;
                  return (
                    <tr
                      key={i}
                      onClick={() => toggleSelect(i)}
                      style={{
                        cursor: "pointer",
                        background: isPinned
                          ? "rgba(59,130,246,.12)"
                          : isBest
                            ? "rgba(16,185,129,.06)"
                            : "",
                        outline: isPinned ? `1px solid ${C.blue}40` : "none",
                      }}
                    >
                      {/* Checkbox column */}
                      <td style={{ textAlign: "center", fontSize: 14 }}>
                        {isPinned ? "☑" : "☐"}
                      </td>
                      <td
                        className="mono"
                        style={{ color: isBest ? C.green : C.muted }}
                      >
                        {isBest ? "★" : i + 1}
                      </td>
                      <td className="mono">{c.rpm}</td>
                      <td className="mono" style={{ color: C.blue }}>
                        {c.bucket_id}
                      </td>
                      <td className="mono">{c.fill}%</td>
                      <td className="mono" style={{ color: C.green }}>
                        {c.capacity}
                      </td>
                      <td className="mono" style={{ color: C.amber }}>
                        {c.power}
                      </td>
                      <td className="mono">{c.T1_kN}</td>
                      <td
                        className="mono"
                        style={{ color: crBad ? C.red : C.teal }}
                      >
                        {c.cr}
                      </td>
                      <td className="mono">{c.motor_kw}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: 10, color: C.muted }}>
            Click any row to select / deselect. Selected variants are
            highlighted in blue.
          </div>
        </>
      )}
    </div>
  );
}
