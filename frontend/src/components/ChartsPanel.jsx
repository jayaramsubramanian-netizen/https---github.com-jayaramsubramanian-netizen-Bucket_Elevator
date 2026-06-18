// ChartsPanel.jsx — Speed Sweep, Fill Analysis, Trajectory, Tension Model
// Pure display component — all data from results dict, no recomputation.
//
// v1.9.9 fixes:
//   1. results.tension_ratio does not exist in the backend — this caused a
//      hard crash on the Tension Model tab. T1/T2 exist and the derived
//      ratio is trivial arithmetic, but even that has been moved to a safe
//      expression with a null guard rather than a property access.
//   2. The slip-risk condition was recomputing Math.exp(inputs.mu * wrap *
//      PI/180) client-side. The backend already exposes results.euler_ratio
//      and results.slip_safe — read those instead.
//   3. results.theta_rel and results.cr were accessed without null guards,
//      which could crash if a result set was partially populated.

import { useState } from "react";
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

const C = {
  panel:   "#162032", border:  "#ffffff12", border2: "#ffffff1e",
  muted:   "#64748b", muted2:  "#94a3b8",   hi:      "#243247",
  blue:    "#3b82f6", series2: "#ef4444",   green:   "#10b981",
  amber:   "#f59e0b", teal:    "#14b8a6",   text:    "#f1f5f9",
  red:     "#ef4444",
};

const TS = {
  background: C.panel, border: `1px solid ${C.border2}`,
  borderRadius: "var(--r-md)", fontFamily: "JetBrains Mono", fontSize: 11,
};

const fmt = (v, dp = 3) => v != null ? Number(v).toFixed(dp) : "—";

export default function ChartsPanel({ results, inputs, activeTab }) {
  const [internalTab, setInternalTab] = useState("speed");
  const tab    = activeTab ?? internalTab;
  const setTab = activeTab ? () => {} : setInternalTab;
  if (!results) return null;

  const tabs = [
    { id: "speed",   label: "Speed Sweep" },
    { id: "fill",    label: "Fill Analysis" },
    { id: "traj",    label: "Discharge Trajectory" },
    { id: "tension", label: "Tension Model" },
  ];

  // Tension model — read directly from backend fields
  const T1            = results.T1 ?? null;
  const T2            = results.T2 ?? null;
  const T3            = results.T3 ?? null;
  const F_eff         = results.F_eff ?? null;
  // T1/T2 ratio: trivially derived from two backend fields, no physics
  const tensionRatio  = (T1 != null && T2 != null && T2 !== 0) ? T1 / T2 : null;
  // Slip check: backend computes euler_ratio (e^μθ) and slip_safe directly
  const eulerRatio    = results.euler_ratio ?? null;
  const slipSafe      = results.slip_safe ?? null;

  return (
    <div>
      {!activeTab && (
        <div className="sub-tabs">
          {tabs.map(t => (
            <button key={t.id} className={`sub-tab ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      )}

      <div className="chart-wrap" style={{ minHeight: 280 }}>

        {/* ── Speed Sweep ──────────────────────────────────────────────── */}
        {tab === "speed" && (
          <>
            <div className="chart-title">Capacity &amp; Power vs Belt Speed (RPM Sweep)</div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={results.speed_sweep}
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="rpm" stroke={C.muted}
                  tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "RPM", position: "insideBottom", offset: -2, fill: C.muted, fontSize: 10 }} />
                <YAxis yAxisId="left" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }} />
                <Tooltip contentStyle={TS} labelStyle={{ color: C.muted2 }} />
                <Legend wrapperStyle={{ fontSize: 11, color: C.muted }} />
                <Line yAxisId="left" type="monotone" dataKey="capacity"
                  name="Capacity (t/h)" stroke={C.blue} strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="power"
                  name="Power (kW)" stroke={C.series2} strokeWidth={2} dot={false} />
                <ReferenceLine yAxisId="left" y={inputs.Q_req} stroke={C.green}
                  strokeDasharray="5 3"
                  label={{ value: `Req ${inputs.Q_req}t/h`, fill: C.green, fontSize: 10 }} />
                <ReferenceLine x={inputs.n_rpm} yAxisId="left" stroke={C.amber}
                  strokeDasharray="5 3" />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}

        {/* ── Fill Analysis ─────────────────────────────────────────────── */}
        {tab === "fill" && (
          <>
            <div className="chart-title">Capacity vs Bucket Fill Factor</div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={results.fill_sweep}
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="fill" stroke={C.muted}
                  tick={{ fill: C.muted, fontSize: 10 }}
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

        {/* ── Discharge Trajectory ─────────────────────────────────────── */}
        {tab === "traj" && (
          <>
            <div className="chart-title">
              Discharge Trajectory (Projectile — relative to head pulley centre)
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={results.trajectory}
                margin={{ top: 5, right: 20, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                <XAxis dataKey="x" type="number" stroke={C.muted}
                  tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "Horizontal (mm)", position: "insideBottom", offset: -10, fill: C.muted, fontSize: 10 }} />
                <YAxis stroke={C.muted} tick={{ fill: C.muted, fontSize: 10 }}
                  label={{ value: "Vertical (mm)", angle: -90, position: "insideLeft", fill: C.muted, fontSize: 10 }} />
                <Tooltip contentStyle={TS} formatter={v => [v.toFixed(1) + "mm"]} />
                <Line type="monotone" dataKey="y" name="Y (mm)"
                  stroke={C.teal} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div style={{ padding: "8px 12px", fontSize: 10, color: C.muted, display: "flex", gap: 20 }}>
              <span>Release angle: <span style={{ color: C.text }}>
                {fmt(results.theta_rel, 1)}°</span> from vertical</span>
              <span>CR: <span style={{ color: results.cr > 1 ? C.green : C.amber }}>
                {fmt(results.cr, 3)}</span></span>
              <span>Head pulley: <span style={{ color: C.text }}>Ø{inputs.D_mm}mm</span></span>
            </div>
          </>
        )}

        {/* ── Tension Model ─────────────────────────────────────────────── */}
        {tab === "tension" && (
          <>
            <div className="chart-title">Belt Tension Model — CEMA 375 §4 Decomposition</div>
            <div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                // F_eff = T1 + T2 — the effective pull the motor must overcome
                { label: "Effective Tension  F_eff",
                  value: F_eff != null ? fmt(F_eff / 1000, 3) + " kN" : "—",
                  color: C.blue,
                  sub: "= T1 + T2  (total load at head shaft)" },
                // T1 = material lifting component (CEMA §4)
                { label: "Material Component  T1",
                  value: T1 != null ? fmt(T1 / 1000, 3) + " kN" : "—",
                  color: C.series2,
                  sub: "G × g × H / v  (lifting material)" },
                // T2 = belt+bucket self-weight component (CEMA §4)
                { label: "Self-Weight Component  T2",
                  value: T2 != null ? fmt(T2 / 1000, 3) + " kN" : "—",
                  color: C.teal,
                  sub: "(belt + bucket mass) × H × g" },
                // T3 = take-up / slack-side tension = F_eff × K_takeup
                { label: "Take-up Tension  T3  (slack side)",
                  value: T3 != null ? fmt(T3 / 1000, 3) + " kN" : "—",
                  color: C.amber,
                  sub: `F_eff × K = ${inputs.K_takeup}  (slack-side minimum)` },
                // True tight side = T3 + F_eff — what the belt actually sees
                { label: "Belt Tight Side  (T3 + F_eff)",
                  value: (T3 != null && F_eff != null) ? fmt((T3 + F_eff) / 1000, 3) + " kN" : "—",
                  color: C.text,
                  sub: "actual belt tension on carrying run" },
                // Euler ratio from backend
                { label: "Euler Limit  e^(μθ)",
                  value: eulerRatio != null ? eulerRatio.toFixed(3) : "—",
                  color: C.muted2,
                  sub: `μ=${inputs.mu}  θ=${inputs.wrap_deg}°` },
              ].map((item, i) => (
                <div key={i} style={{
                  background: C.hi, borderRadius: "var(--r-md)",
                  padding: "10px 12px", border: `1px solid ${C.border2}`,
                }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 2 }}>{item.label}</div>
                  <div style={{
                    fontFamily: "JetBrains Mono", fontSize: 16,
                    fontWeight: 700, color: item.color,
                  }}>{item.value}</div>
                  <div style={{ fontSize: 9, color: C.muted, marginTop: 3 }}>{item.sub}</div>
                </div>
              ))}
            </div>
            {slipSafe != null && (
              <div style={{ padding: "4px 16px 12px", fontSize: 10, color: C.muted }}>
                Slip check: (T3 + F_eff) / T3 = {(T3 != null && F_eff != null && T3 > 0)
                  ? ((T3 + F_eff) / T3).toFixed(3) : "—"} vs e^μθ = {eulerRatio != null ? eulerRatio.toFixed(3) : "—"}
                {slipSafe
                  ? <span style={{ color: C.green, marginLeft: 8 }}>✓ No slip  (T3 adequate)</span>
                  : <span style={{ color: C.red, marginLeft: 8 }}>⚠ SLIP RISK — increase T3</span>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}