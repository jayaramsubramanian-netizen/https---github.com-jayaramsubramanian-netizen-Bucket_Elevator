// ChartsPanel.jsx — Speed Sweep, Fill Analysis, Trajectory, Tension Model
import { useState } from "react";
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

const C = {
  panel: "#0d1c2e", border: "#162438", border2: "#1c3050",
  muted: "#5a7a9a", muted2: "#7a9ab8", hi: "#132238",
  blue: "#4a9eff", accent: "#c8192e", green: "#1fb86e",
  amber: "#d98e00", teal: "#2dd4bf", text: "#ddeaf6", red: "#e05252",
};

const TS = { background: C.panel, border: `1px solid ${C.border2}`, borderRadius: 5, fontFamily: "JetBrains Mono", fontSize: 11 };

export default function ChartsPanel({ results, inputs }) {
  const [tab, setTab] = useState("speed");
  if (!results) return null;

  const tabs = [
    { id: "speed", label: "Speed Sweep" },
    { id: "fill", label: "Fill Analysis" },
    { id: "traj", label: "Discharge Trajectory" },
    { id: "tension", label: "Tension Model" },
  ];

  return (
    <div>
      <div className="sub-tabs">
        {tabs.map((t) => (
          <button key={t.id} className={`sub-tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="chart-wrap" style={{ minHeight: 280 }}>
        {tab === "speed" && (
          <>
            <div className="chart-title">Capacity &amp; Power vs Belt Speed (RPM Sweep)</div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={results.speed_sweep} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="rpm" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "RPM", position: "insideBottom", offset: -2, fill: C.muted, fontSize: 10 }} />
                <YAxis yAxisId="left" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }} />
                <Tooltip contentStyle={TS} labelStyle={{ color: C.muted2 }} />
                <Legend wrapperStyle={{ fontSize: 11, color: C.muted }} />
                <Line yAxisId="left" type="monotone" dataKey="capacity" name="Capacity (t/h)" stroke={C.blue} strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="power" name="Power (kW)" stroke={C.accent} strokeWidth={2} dot={false} />
                <ReferenceLine yAxisId="left" y={inputs.Q_req} stroke={C.green} strokeDasharray="5 3"
                  label={{ value: `Req ${inputs.Q_req}t/h`, fill: C.green, fontSize: 10 }} />
                <ReferenceLine x={inputs.n_rpm} yAxisId="left" stroke={C.amber} strokeDasharray="5 3" />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}

        {tab === "fill" && (
          <>
            <div className="chart-title">Capacity vs Bucket Fill Factor</div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={results.fill_sweep} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="fill" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "Fill %", position: "insideBottom", offset: -2, fill: C.muted, fontSize: 10 }} />
                <YAxis stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }} />
                <Tooltip contentStyle={TS} />
                <Area type="monotone" dataKey="capacity" name="Capacity (t/h)"
                  stroke={C.teal} fill="rgba(45,212,191,.15)" strokeWidth={2} />
                <ReferenceLine x={inputs.fill_pct} stroke={C.amber} strokeDasharray="5 3"
                  label={{ value: `${inputs.fill_pct}%`, fill: C.amber, fontSize: 10 }} />
                <ReferenceLine y={inputs.Q_req} stroke={C.green} strokeDasharray="5 3"
                  label={{ value: `${inputs.Q_req}t/h`, fill: C.green, fontSize: 10 }} />
              </AreaChart>
            </ResponsiveContainer>
          </>
        )}

        {tab === "traj" && (
          <>
            <div className="chart-title">Discharge Trajectory (Projectile — relative to head pulley centre)</div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={results.trajectory} margin={{ top: 5, right: 20, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="x" type="number" name="X (mm)" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "Horizontal (mm)", position: "insideBottom", offset: -10, fill: C.muted, fontSize: 10 }} />
                <YAxis stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "Vertical (mm)", angle: -90, position: "insideLeft", fill: C.muted, fontSize: 10 }} />
                <Tooltip contentStyle={TS} formatter={(v) => [v.toFixed(1) + "mm"]} />
                <Line type="monotone" dataKey="y" name="Y (mm)" stroke={C.teal} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div style={{ padding: "8px 12px", fontSize: 10, color: C.muted, display: "flex", gap: 20 }}>
              <span>Release angle: <span style={{ color: C.text }}>{results.theta_rel.toFixed(1)}°</span> from vertical</span>
              <span>Centrifugal ratio: <span style={{ color: results.cr > 1 ? C.green : C.amber }}>{results.cr.toFixed(3)}</span></span>
              <span>Head pulley: <span style={{ color: C.text }}>Ø{inputs.D_mm}mm</span></span>
            </div>
          </>
        )}

        {tab === "tension" && (
          <>
            <div className="chart-title">Belt Tension Model — Tight/Slack Side Analysis</div>
            <div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { label: "Effective Tension", value: (results.F_eff / 1000).toFixed(3) + " kN", color: C.blue },
                { label: "Tight Side (T₁)",  value: (results.T1 / 1000).toFixed(3) + " kN", color: C.accent },
                { label: "Slack Side (T₂)",  value: (results.T2 / 1000).toFixed(3) + " kN", color: C.teal },
                { label: "Tension Ratio T₁/T₂", value: results.tension_ratio.toFixed(3), color: C.amber },
                { label: "Wrap Angle",        value: inputs.wrap_deg + "°",              color: C.muted2 },
                { label: "Friction μ",        value: inputs.mu.toFixed(2),               color: C.muted2 },
              ].map((item, i) => (
                <div key={i} style={{ background: C.hi, borderRadius: 5, padding: "10px 12px", border: `1px solid ${C.border2}` }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>{item.label}</div>
                  <div style={{ fontFamily: "JetBrains Mono", fontSize: 16, fontWeight: 700, color: item.color }}>{item.value}</div>
                </div>
              ))}
            </div>
            {(() => {
              const emuTheta = Math.exp(inputs.mu * inputs.wrap_deg * Math.PI / 180);
              const slipRisk = results.tension_ratio > emuTheta;
              return (
                <div style={{ padding: "4px 16px 12px", fontSize: 10, color: C.muted }}>
                  Belt slip condition: T₁/T₂ = e^(μθ) = {emuTheta.toFixed(3)}
                  {slipRisk
                    ? <span style={{ color: C.red, marginLeft: 8 }}>⚠ SLIP RISK</span>
                    : <span style={{ color: C.green, marginLeft: 8 }}>✓ No slip</span>}
                </div>
              );
            })()}
          </>
        )}
      </div>
    </div>
  );
}
