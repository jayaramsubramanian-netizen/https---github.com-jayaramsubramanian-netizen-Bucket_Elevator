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
    { id: "profile", label: "Tension Profile" },
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

        {/* ── Tension Profile ────────────────────────────────────────────── */}
        {tab === "profile" && (() => {
          const tp = results.tension_profile;

          // Chain elevators: tension profile not applicable
          if (results.is_chain) return (
            <div style={{ padding: 24, textAlign: "center", color: C.muted, fontSize: 11 }}>
              Tension profile is not computed for chain elevators.<br/>
              <span style={{ fontSize: 10 }}>Chain pull is a single lumped value — see Component tab.</span>
            </div>
          );

          // Belt elevator but no profile data
          if (!tp || !tp.stations?.length) return (
            <div style={{ padding: 24, textAlign: "center", color: C.muted, fontSize: 11 }}>
              Tension profile not available — recalculate to generate.
            </div>
          );

          const stations  = tp.stations;
          const loaded    = stations.filter(s => s.leg === "loaded");
          const empty     = stations.filter(s => s.leg === "empty");
          const T_max     = tp.T_max_N;
          const T_min     = tp.T_min_N;
          const T_rated   = tp.belt_rated_N;
          const margin    = tp.rating_margin;
          const marginOk  = margin != null && margin >= 1.0;
          const marginWarn= margin != null && margin >= 0.9 && margin < 1.0;

          // Chart geometry
          const W_draw = 420, H_draw = 220;
          const cl = 50, cb = 28, cr_edge = W_draw - 16, ct = H_draw - 22;
          const cw = cr_edge - cl, ch = ct - cb;

          const T_top = (T_rated != null ? Math.max(T_max, T_rated) : T_max) * 1.05;
          const T_bot = T_min * 0.90;
          const T_range = Math.max(T_top - T_bot, 1);

          const H_m = inputs.H_m || 25;

          const px = pos => cl + (pos / H_m) * cw;
          const py = T   => ct - ((T - T_bot) / T_range) * ch;

          // Grid lines
          const gridLines = [];
          const nGrid = 5;
          for (let i = 0; i <= nGrid; i++) {
            const T_grid = T_bot + (i / nGrid) * T_range;
            const y = py(T_grid);
            gridLines.push(
              <line key={`h${i}`} x1={cl} y1={y} x2={cr_edge} y2={y}
                stroke={C.border} strokeWidth={0.5} strokeDasharray="3,3" />,
              <text key={`hl${i}`} x={cl - 4} y={y + 3} fontSize={8}
                fill={C.muted} textAnchor="end">
                {(T_grid / 1000).toFixed(1)}
              </text>
            );
          }
          for (let i = 0; i <= 4; i++) {
            const pos = (i / 4) * H_m;
            const x = px(pos);
            gridLines.push(
              <line key={`v${i}`} x1={x} y1={cb} x2={x} y2={ct}
                stroke={C.border} strokeWidth={0.5} strokeDasharray="3,3" />,
              <text key={`vl${i}`} x={x} y={ct + 13} fontSize={8}
                fill={C.muted} textAnchor="middle">
                {pos.toFixed(0)}m
              </text>
            );
          }

          // Loaded leg line (ascending, left→right = boot→head)
          const loadedPath = loaded.map((s, i) =>
            `${i === 0 ? "M" : "L"} ${px(s.position_m)} ${py(s.tension_N)}`
          ).join(" ");

          // Empty leg — position_m is ALREADY height-above-boot (same physical
          // coordinate as the loaded leg, confirmed against backend station
          // data: height_frac runs 1.0→0.0 as position_m runs 25→0 for H_m=25).
          // No flip needed — plot directly against the same x-axis.
          const emptyPath = empty.map((s, i) =>
            `${i === 0 ? "M" : "L"} ${px(s.position_m)} ${py(s.tension_N)}`
          ).join(" ");

          // Belt rating line
          const ratedY = T_rated != null ? py(T_rated) : null;

          return (
            <>
              <div className="chart-title">
                Position-Resolved Belt Tension Profile — CEMA 375 §4.07
              </div>

              {/* SVG chart */}
              <svg width="100%" viewBox={`0 0 ${W_draw} ${H_draw}`}
                style={{ display: "block", background: C.panel }}>

                {/* Grid */}
                {gridLines}

                {/* Axes */}
                <line x1={cl} y1={cb} x2={cl} y2={ct} stroke={C.muted} strokeWidth={1} />
                <line x1={cl} y1={ct} x2={cr_edge} y2={ct} stroke={C.muted} strokeWidth={1} />

                {/* Axis labels */}
                <text x={cl - 30} y={cb + ch / 2} fontSize={8} fill={C.muted}
                  textAnchor="middle" transform={`rotate(-90, ${cl-30}, ${cb + ch/2})`}>
                  Tension (kN)
                </text>
                <text x={cl + cw / 2} y={H_draw - 4} fontSize={8} fill={C.muted}
                  textAnchor="middle">
                  Position from boot (m)
                </text>

                {/* Belt rating line */}
                {ratedY != null && ratedY >= cb && ratedY <= ct && (
                  <>
                    <line x1={cl} y1={ratedY} x2={cr_edge} y2={ratedY}
                      stroke={C.series2} strokeWidth={1.2} strokeDasharray="6,3" />
                    <text x={cr_edge - 2} y={ratedY - 3} fontSize={8}
                      fill={C.series2} textAnchor="end">
                      Rated {(T_rated/1000).toFixed(1)}kN
                    </text>
                  </>
                )}

                {/* Loaded leg — blue (ascending, carries material) */}
                <path d={loadedPath} fill="none" stroke={C.blue} strokeWidth={2.5} />

                {/* Empty leg — teal (descending, no material) */}
                <path d={emptyPath} fill="none" stroke={C.teal} strokeWidth={1.8}
                  strokeDasharray="6,3" />

                {/* Peak marker */}
                {loaded.length > 0 && (() => {
                  const peak = loaded[loaded.length - 1];
                  const px2 = px(peak.position_m);
                  const py2 = py(peak.tension_N);
                  return (
                    <>
                      <circle cx={px2} cy={py2} r={4} fill={C.blue} stroke={C.text} strokeWidth={1} />
                      <text x={px2 - 5} y={py2 - 8} fontSize={8} fill={C.blue} textAnchor="end">
                        {(peak.tension_N/1000).toFixed(2)}kN
                      </text>
                    </>
                  );
                })()}

                {/* Legend */}
                <line x1={cl+4} y1={14} x2={cl+22} y2={14} stroke={C.blue} strokeWidth={2.5} />
                <text x={cl+26} y={17} fontSize={8} fill={C.muted}>Loaded leg (carry)</text>
                <line x1={cl+110} y1={14} x2={cl+128} y2={14} stroke={C.teal}
                  strokeWidth={1.8} strokeDasharray="5,3" />
                <text x={cl+132} y={17} fontSize={8} fill={C.muted}>Empty leg (return)</text>
              </svg>

              {/* Summary strip */}
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(4,1fr)",
                gap: 6, padding: "10px 12px",
              }}>
                {[
                  { label: "Peak tension  (head)",
                    value: T_max != null ? (T_max/1000).toFixed(2)+" kN" : "—",
                    color: C.blue },
                  { label: "Min tension  (boot)",
                    value: T_min != null ? (T_min/1000).toFixed(2)+" kN" : "—",
                    color: C.teal },
                  { label: "Belt rated",
                    value: T_rated != null ? (T_rated/1000).toFixed(2)+" kN" : "—",
                    color: C.muted2 },
                  { label: "Rating margin",
                    value: margin != null ? margin.toFixed(3) : "—",
                    color: marginOk ? C.green : marginWarn ? C.amber : C.series2 },
                ].map((item, i) => (
                  <div key={i} style={{
                    background: C.hi, borderRadius: "var(--r-md)",
                    padding: "8px 10px", border: `1px solid ${C.border2}`,
                  }}>
                    <div style={{ fontSize: 9, color: C.muted, marginBottom: 2 }}>{item.label}</div>
                    <div style={{ fontFamily: "JetBrains Mono", fontSize: 14,
                      fontWeight: 700, color: item.color }}>{item.value}</div>
                  </div>
                ))}
              </div>
              <div style={{ padding: "2px 12px 10px", fontSize: 10, color: C.muted }}>
                {tp.T_max_location}  ·  {tp.note ?? ""}
                {margin != null && (margin < 1.0
                  ? <span style={{ color: C.series2, marginLeft: 8 }}>
                      ✗ Peak tension exceeds belt rating — upgrade belt or reduce load
                    </span>
                  : margin < 1.25
                    ? <span style={{ color: C.amber, marginLeft: 8 }}>
                        ⚠ Margin &lt;1.25 — verify with belt manufacturer
                      </span>
                    : <span style={{ color: C.green, marginLeft: 8 }}>
                        ✓ Adequate belt margin
                      </span>
                )}
              </div>
            </>
          );
        })()}
      </div>
    </div>
  );
}