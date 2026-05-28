// OptimizerPanel.jsx — grid-search optimizer via FastAPI
import { useState, useCallback } from "react";
import { optimizeElevator } from "../api/client";

const C = {
  hi: "#132238", border2: "#1c3050", muted: "#5a7a9a", muted2: "#7a9ab8",
  blue: "#4a9eff", green: "#1fb86e", amber: "#d98e00", teal: "#2dd4bf",
  red: "#e05252", text: "#ddeaf6",
};

export default function OptimizerPanel({ inputs, onApply }) {
  const [objective, setObjective] = useState("power");
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const runOptimizer = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      const data = await optimizeElevator(inputs, objective);
      setResults(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }, [inputs, objective]);

  const best = results?.candidates?.[0];

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 11, color: C.muted }}>
        Multi-objective optimizer searches RPM × Bucket × Fill space subject to Q ≥{" "}
        <span style={{ color: C.text }}>{inputs.Q_req}</span> t/h and speed limits [0.5–3.0 m/s].
      </div>

      <div className="inp-field">
        <div className="inp-label">Objective Function</div>
        <select className="inp-sel" value={objective} onChange={(e) => setObjective(e.target.value)}>
          <option value="power">Minimize Power</option>
          <option value="tension">Minimize Belt Tension</option>
          <option value="motor">Minimize Motor Size</option>
          <option value="balanced">Balanced (Power + Tension + Discharge)</option>
        </select>
      </div>

      <button className="btn-primary" style={{ margin: 0 }} onClick={runOptimizer} disabled={running}>
        {running ? "⟳  OPTIMIZING…" : "▶  RUN OPTIMIZER"}
      </button>

      {error && (
        <div className="warn-item w-fail">{error}</div>
      )}

      {results && best && (
        <>
          <div style={{ padding: "10px 12px", background: C.hi, borderRadius: 5, border: `1px solid ${C.border2}`, fontSize: 11 }}>
            <span style={{ color: C.muted }}>Best solution: </span>
            <span style={{ color: C.green, fontFamily: "JetBrains Mono", fontWeight: 700 }}>
              {best.rpm} RPM · Bucket {best.bucket_id} · Fill {best.fill}%
            </span>
            <span style={{ color: C.muted, marginLeft: 8 }}>({results.count} feasible candidates)</span>
          </div>

          <button
            className="btn-secondary"
            style={{ margin: 0 }}
            onClick={() => onApply({ rpm: best.rpm, bucket_id: best.bucket_id, fill: best.fill })}
          >
            ✓ Apply Best Solution to Inputs
          </button>

          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th><th>RPM</th><th>Bucket</th><th>Fill %</th>
                  <th>Q t/h</th><th>P kW</th><th>T₁ kN</th><th>CR</th><th>Motor kW</th>
                </tr>
              </thead>
              <tbody>
                {results.candidates.map((r, i) => (
                  <tr key={i} style={{ background: i === 0 ? "rgba(31,184,110,.06)" : "" }}>
                    <td className="mono" style={{ color: i === 0 ? C.green : C.muted }}>
                      {i === 0 ? "★" : i + 1}
                    </td>
                    <td className="mono">{r.rpm}</td>
                    <td className="mono" style={{ color: C.blue }}>{r.bucket_id}</td>
                    <td className="mono">{r.fill}%</td>
                    <td className="mono" style={{ color: C.green }}>{r.capacity}</td>
                    <td className="mono" style={{ color: C.amber }}>{r.power}</td>
                    <td className="mono">{r.T1_kN}</td>
                    <td className="mono" style={{ color: r.cr < 0.8 || r.cr > 2.5 ? C.red : C.teal }}>{r.cr}</td>
                    <td className="mono">{r.motor_kw}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
