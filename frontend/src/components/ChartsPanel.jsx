// ChartsPanel.jsx — Speed Sweep, Fill Analysis, Trajectory, Tension Model
// Field names match your backend's solve_elevator() return shape exactly.
import { useState } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

const C = {
  panel: "#162032",
  border: "#ffffff12",
  border2: "#ffffff1e",
  muted: "#64748b",
  muted2: "#94a3b8",
  hi: "#243247",
  blue: "#3b82f6",
  series2: "#ef4444",
  green: "#10b981",
  amber: "#f59e0b",
  teal: "#14b8a6",
  text: "#f1f5f9",
  red: "#ef4444",
};

const TS = {
  background: C.panel,
  border: `1px solid ${C.border2}`,
  borderRadius: "var(--r-md)",
  fontFamily: "JetBrains Mono",
  fontSize: 11,
};

// Safe formatter
const fmt = (v, dp = 2) =>
  v == null || !isFinite(Number(v)) ? "—" : Number(v).toFixed(dp);

export default function ChartsPanel({ results, inputs }) {
  const [tab, setTab] = useState("speed");
  if (!results || !inputs) return null;

  // ── Resolve field names — backend uses snake_case, normaliser may rename ──
  // speed_sweep / speedSweep, fill_sweep / fillSweep
  const speedSweep = results.speed_sweep ?? results.speedSweep ?? [];
  const fillSweep = results.fill_sweep ?? results.fillSweep ?? [];
  const trajectory = results.trajectory ?? [];

  // Centrifugal ratio + release angle — backend: cr / theta_rel
  //   normaliser maps → centrifugal_ratio / release_angle_deg (may or may not be present)
  const cr = results.centrifugal_ratio ?? results.cr ?? 0;
  const thetaRel = results.release_angle_deg ?? results.theta_rel ?? 0;

  // Tension fields — same in both shapes
  const T1 = results.T1 ?? 0;
  const T2 = results.T2 ?? 0;
  const F_eff = results.F_eff ?? 0;
  const tensionRatio = results.tension_ratio ?? results.tensionRatio ?? 0;

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
          <button
            key={t.id}
            className={`sub-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="chart-wrap" style={{ minHeight: 280 }}>
        {/* ── Speed Sweep ── */}
        {tab === "speed" && (
          <>
            <div className="chart-title">
              Capacity &amp; Power vs Belt Speed (RPM Sweep)
            </div>
            {speedSweep.length === 0 ? (
              <div style={{ padding: 24, color: C.muted, fontSize: 12 }}>
                No speed sweep data — backend did not return speed_sweep array.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart
                  data={speedSweep}
                  margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="rpm"
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                    label={{
                      value: "RPM",
                      position: "insideBottom",
                      offset: -2,
                      fill: C.muted,
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                  />
                  <Tooltip contentStyle={TS} labelStyle={{ color: C.muted2 }} />
                  <Legend wrapperStyle={{ fontSize: 11, color: C.muted }} />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="capacity"
                    name="Capacity (t/h)"
                    stroke={C.blue}
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="power"
                    name="Power (kW)"
                    stroke={C.series2}
                    strokeWidth={2}
                    dot={false}
                  />
                  <ReferenceLine
                    yAxisId="left"
                    y={inputs.Q_req}
                    stroke={C.green}
                    strokeDasharray="5 3"
                    label={{
                      value: `Req ${inputs.Q_req}t/h`,
                      fill: C.green,
                      fontSize: 10,
                    }}
                  />
                  <ReferenceLine
                    x={inputs.n_rpm}
                    yAxisId="left"
                    stroke={C.amber}
                    strokeDasharray="5 3"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </>
        )}

        {/* ── Fill Analysis ── */}
        {tab === "fill" && (
          <>
            <div className="chart-title">Capacity vs Bucket Fill Factor</div>
            {fillSweep.length === 0 ? (
              <div style={{ padding: 24, color: C.muted, fontSize: 12 }}>
                No fill sweep data — backend did not return fill_sweep array.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart
                  data={fillSweep}
                  margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="fill"
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                    label={{
                      value: "Fill %",
                      position: "insideBottom",
                      offset: -2,
                      fill: C.muted,
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                  />
                  <Tooltip contentStyle={TS} />
                  <Area
                    type="monotone"
                    dataKey="capacity"
                    name="Capacity (t/h)"
                    stroke={C.teal}
                    fill="rgba(45,212,191,.15)"
                    strokeWidth={2}
                  />
                  <ReferenceLine
                    x={inputs.fill_pct}
                    stroke={C.amber}
                    strokeDasharray="5 3"
                    label={{
                      value: `${inputs.fill_pct}%`,
                      fill: C.amber,
                      fontSize: 10,
                    }}
                  />
                  <ReferenceLine
                    y={inputs.Q_req}
                    stroke={C.green}
                    strokeDasharray="5 3"
                    label={{
                      value: `${inputs.Q_req}t/h`,
                      fill: C.green,
                      fontSize: 10,
                    }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </>
        )}

        {/* ── Discharge Trajectory ── */}
        {tab === "traj" && (
          <>
            <div className="chart-title">
              Discharge Trajectory (relative to head pulley centre)
            </div>
            {trajectory.length === 0 ? (
              <div style={{ padding: 24, color: C.muted, fontSize: 12 }}>
                No trajectory data available.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart
                  data={trajectory}
                  margin={{ top: 5, right: 20, left: 20, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                  <XAxis
                    dataKey="x"
                    type="number"
                    name="X (mm)"
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                    label={{
                      value: "Horizontal (mm)",
                      position: "insideBottom",
                      offset: -10,
                      fill: C.muted,
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    stroke={C.muted}
                    tick={{ fill: C.muted, fontSize: 10 }}
                    label={{
                      value: "Vertical (mm)",
                      angle: -90,
                      position: "insideLeft",
                      fill: C.muted,
                      fontSize: 10,
                    }}
                  />
                  <Tooltip
                    contentStyle={TS}
                    formatter={(v) => [fmt(v, 1) + " mm"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="y"
                    name="Y (mm)"
                    stroke={C.teal}
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
            <div
              style={{
                padding: "8px 12px",
                fontSize: 10,
                color: C.muted,
                display: "flex",
                gap: 20,
              }}
            >
              <span>
                Release angle:{" "}
                <span style={{ color: C.text }}>{fmt(thetaRel, 1)}°</span> from
                vertical
              </span>
              <span>
                Centrifugal ratio:{" "}
                <span style={{ color: cr > 1 ? C.green : C.amber }}>
                  {fmt(cr, 3)}
                </span>
              </span>
              <span>
                Head pulley:{" "}
                <span style={{ color: C.text }}>Ø{inputs.D_mm}mm</span>
              </span>
            </div>
          </>
        )}

        {/* ── Tension Model ── */}
        {tab === "tension" && (
          <>
            <div className="chart-title">
              Belt Tension Model — Tight/Slack Side Analysis
            </div>
            <div
              style={{
                padding: 16,
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 12,
              }}
            >
              {[
                {
                  label: "Effective Tension",
                  value: fmt(F_eff / 1000, 3) + " kN",
                  color: C.blue,
                },
                {
                  label: "Tight Side (T₁)",
                  value: fmt(T1 / 1000, 3) + " kN",
                  color: C.series2,
                },
                {
                  label: "Slack Side (T₂)",
                  value: fmt(T2 / 1000, 3) + " kN",
                  color: C.teal,
                },
                {
                  label: "Tension Ratio T₁/T₂",
                  value: fmt(tensionRatio, 3),
                  color: C.amber,
                },
                {
                  label: "Wrap Angle",
                  value: inputs.wrap_deg + "°",
                  color: C.muted2,
                },
                {
                  label: "Friction μ",
                  value: fmt(inputs.mu, 2),
                  color: C.muted2,
                },
              ].map((item, i) => (
                <div
                  key={i}
                  style={{
                    background: C.hi,
                    borderRadius: "var(--r-md)",
                    padding: "10px 12px",
                    border: `1px solid ${C.border2}`,
                  }}
                >
                  <div
                    style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}
                  >
                    {item.label}
                  </div>
                  <div
                    style={{
                      fontFamily: "JetBrains Mono",
                      fontSize: 16,
                      fontWeight: 700,
                      color: item.color,
                    }}
                  >
                    {item.value}
                  </div>
                </div>
              ))}
            </div>
            {(() => {
              const emuTheta = Math.exp(
                ((inputs.mu ?? 0.35) * (inputs.wrap_deg ?? 180) * Math.PI) /
                  180,
              );
              const slipRisk = tensionRatio > emuTheta;
              return (
                <div
                  style={{
                    padding: "4px 16px 12px",
                    fontSize: 10,
                    color: C.muted,
                  }}
                >
                  Belt slip condition: T₁/T₂ = e^(μθ) = {fmt(emuTheta, 3)}
                  {slipRisk ? (
                    <span style={{ color: C.red, marginLeft: 8 }}>
                      ⚠ SLIP RISK
                    </span>
                  ) : (
                    <span style={{ color: C.green, marginLeft: 8 }}>
                      ✓ No slip
                    </span>
                  )}
                </div>
              );
            })()}
          </>
        )}
      </div>
    </div>
  );
}
