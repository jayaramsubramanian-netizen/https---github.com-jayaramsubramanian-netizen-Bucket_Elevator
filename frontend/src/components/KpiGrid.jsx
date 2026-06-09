// KpiGrid.jsx — Task 2: Engineering KPI cards
// Replaces the old label/value/unit stack with:
//   - Metric name + discipline tag
//   - Large value + unit
//   - Required/target value with margin %
//   - Status pill (PASS / WARN / FAIL)
//   - Expandable formula trace (chevron)

import { useState } from "react";

const C = {
  surface:  "#243247",  surface2: "#2d3f57",  hi:      "#1e293b",
  border:   "#ffffff12", border2: "#ffffff1e",
  text:     "#f1f5f9",  text2:   "#cbd5e1",   text3:   "#94a3b8",
  muted:    "#64748b",
  primary:  "#3b82f6",  green:   "#10b981",
  amber:    "#f59e0b",  danger:  "#ef4444",
  teal:     "#14b8a6",  purple:  "#a78bfa",
};

// Status → colors
const STATUS = {
  ok:   { bg: "rgba(16,185,129,.1)",  border: "rgba(16,185,129,.3)",  text: "#10b981", label: "PASS"  },
  warn: { bg: "rgba(245,158,11,.1)",  border: "rgba(245,158,11,.3)",  text: "#f59e0b", label: "WARN"  },
  fail: { bg: "rgba(239,68,68,.1)",   border: "rgba(239,68,68,.3)",   text: "#ef4444", label: "FAIL"  },
  info: { bg: "rgba(59,130,246,.08)", border: "rgba(59,130,246,.2)",  text: "#3b82f6", label: "INFO"  },
};

// Discipline colors for the top tag
const DISC = {
  process:    { bg: "rgba(59,130,246,.15)",  color: "#3b82f6" },
  mechanical: { bg: "rgba(16,185,129,.15)",  color: "#10b981" },
  power:      { bg: "rgba(245,158,11,.15)",  color: "#f59e0b" },
  structural: { bg: "rgba(167,139,250,.15)", color: "#a78bfa" },
  discharge:  { bg: "rgba(20,184,166,.15)",  color: "#14b8a6" },
};

function Pill({ status }) {
  const s = STATUS[status] || STATUS.info;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 999,
      fontSize: 9, fontWeight: 700, letterSpacing: ".06em",
      background: s.bg, border: `1px solid ${s.border}`, color: s.text,
    }}>
      {status === "ok" ? "✓" : status === "fail" ? "✗" : status === "warn" ? "⚠" : "·"}
      {" "}{s.label}
    </span>
  );
}

function Tag({ disc }) {
  const d = DISC[disc] || DISC.process;
  return (
    <span style={{
      fontSize: 9, fontWeight: 600, letterSpacing: ".05em", textTransform: "uppercase",
      padding: "1px 7px", borderRadius: 999,
      background: d.bg, color: d.color,
    }}>{disc}</span>
  );
}

function KpiCard({ label, value, unit, status, target, margin, formula, disc }) {
  const [open, setOpen] = useState(false);
  const s = STATUS[status] || STATUS.info;
  const hasFormula = !!formula;

  return (
    <div style={{
      background: C.surface,
      border: `1px solid ${open ? s.border : C.border}`,
      borderRadius: 12,
      padding: "16px 18px",
      display: "flex", flexDirection: "column", gap: 10,
      transition: "border-color .15s, box-shadow .15s",
      boxShadow: open ? `0 0 0 3px ${s.bg}` : "none",
    }}>

      {/* Top row: discipline tag + status pill */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Tag disc={disc} />
        <Pill status={status} />
      </div>

      {/* Label */}
      <div style={{ fontSize: 11, fontWeight: 600, color: C.text3,
        letterSpacing: ".04em", textTransform: "uppercase" }}>
        {label}
      </div>

      {/* Value + unit — large mono */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span style={{
          fontFamily: "JetBrains Mono, monospace",
          fontSize: 26, fontWeight: 700,
          color: s.text, lineHeight: 1, letterSpacing: "-.02em",
        }}>{value}</span>
        {unit && (
          <span style={{ fontFamily: "JetBrains Mono, monospace",
            fontSize: 13, color: C.text3, fontWeight: 400 }}>{unit}</span>
        )}
      </div>

      {/* Target + margin row */}
      {(target || margin != null) && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "6px 10px", borderRadius: 6,
          background: "rgba(255,255,255,.04)", border: `1px solid ${C.border}`,
        }}>
          {target && (
            <span style={{ fontSize: 11, color: C.text3 }}>
              Target: <span style={{ color: C.text2, fontFamily: "JetBrains Mono, monospace",
                fontSize: 11, fontWeight: 500 }}>{target}</span>
            </span>
          )}
          {margin != null && (
            <span style={{
              fontSize: 11, fontWeight: 600,
              color: margin >= 0 ? C.green : C.danger,
              fontFamily: "JetBrains Mono, monospace",
            }}>
              {margin >= 0 ? "+" : ""}{margin}%
            </span>
          )}
        </div>
      )}

      {/* Formula trace — expandable */}
      {hasFormula && (
        <div>
          <button
            onClick={() => setOpen(!open)}
            style={{
              display: "flex", alignItems: "center", gap: 5,
              background: "none", border: "none", cursor: "pointer",
              fontSize: 10, color: C.muted, fontWeight: 500,
              letterSpacing: ".03em", padding: 0,
              transition: "color .15s",
            }}
            onMouseEnter={e => e.currentTarget.style.color = C.text3}
            onMouseLeave={e => e.currentTarget.style.color = C.muted}
          >
            <span style={{ transform: open ? "rotate(90deg)" : "none",
              display: "inline-block", transition: "transform .15s" }}>▶</span>
            {open ? "HIDE FORMULA" : "SHOW FORMULA"}
          </button>
          {open && (
            <div style={{
              marginTop: 8, padding: "10px 12px", borderRadius: 6,
              background: C.hi, border: `1px solid ${C.border2}`,
              fontFamily: "JetBrains Mono, monospace", fontSize: 11,
              color: C.text2, lineHeight: 1.7,
              whiteSpace: "pre-wrap",
            }}>
              {formula}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function KpiGrid({ results, inputs, compact }) {
  if (!results || !results.bucket) return null;

  // Safe formatter: handles null, undefined, and 0 correctly.
  // Optional chaining (?.) returns undefined for 0 (falsy), causing ?? to show "—".
  // This explicit check fixes that.
  const fmt = (v, digits = 2) =>
    v != null && !Number.isNaN(Number(v)) ? Number(v).toFixed(digits) : "—";

  const capOK    = results.Q != null && Number(results.Q) >= Number(inputs.Q_req);
  const capMargin = capOK != null && results.Q != null
    ? (((Number(results.Q) - Number(inputs.Q_req)) / Number(inputs.Q_req)) * 100).toFixed(1)
    : "0.0";
  const speedOK  = results.v != null
    && Number(results.v) >= (results.bucket.v_min ?? 0.5)
    && Number(results.v) <= (results.bucket.v_max ?? 3.0);
  const T_total  = (results.T1 ?? 0) + (results.T2 ?? 0) + (results.T3 ?? 0);
  const motorMargin = results.motor_kw != null && results.P_total != null && results.P_total > 0
    ? (((Number(results.motor_kw) - Number(results.P_total)) / Number(results.P_total)) * 100).toFixed(1)
    : "0.0";
  const crOK     = results.cr != null && results.cr >= 1.0 && results.cr <= 1.8;
  const l10OK    = results.L10 != null && results.L10 >= 40000;

  const kpis = [
    {
      label: "Design Capacity",
      value: fmt(results.Q, 1) ?? "—",
      unit: "t/h",
      disc: "process",
      status: capOK ? "ok" : "fail",
      target: `${inputs.Q_req} t/h required`,
      margin: capMargin != null ? parseFloat(capMargin) : null,
      formula:
`Q = (v / s) · Vb · η · ρ · 3.6
v = ${fmt(results.v, 3)} m/s  (belt speed)
s = ${fmt(results.spacing, 4)} m  (bucket spacing)
Vb = ${results.bucket?.V} L = ${(results.bucket?.V/1000).toFixed(4)} m³
η = ${(inputs.fill_pct/100).toFixed(2)}  (fill factor ${inputs.fill_pct}%)
ρ = ${results.rho} kg/m³
→ Q = ${fmt(results.Q, 2)} t/h  [CEMA 375 §4]`,
    },
    {
      label: "Belt Speed",
      value: fmt(results.v, 3) ?? "—",
      unit: "m/s",
      disc: "mechanical",
      status: speedOK ? "ok" : "warn",
      target: `${results.bucket?.v_min}–${results.bucket?.v_max} m/s (${results.bucket?.id})`,
      margin: null,
      formula:
`v = π · D · n / 60
D = ${inputs.D_mm} mm = ${(inputs.D_mm/1000).toFixed(3)} m
n = ${inputs.n_rpm} rpm
→ v = π × ${(inputs.D_mm/1000).toFixed(3)} × ${inputs.n_rpm} / 60
→ v = ${fmt(results.v, 4)} m/s  [CEMA 375 §3]`,
    },
    {
      label: "Total Drive Power",
      value: fmt(results.P_total, 2) ?? "—",
      unit: "kW",
      disc: "power",
      status: "info",
      target: `Lift ${fmt(results.P_lift, 2)} + Dig ${fmt(results.P_digging, 2)} kW`,
      margin: null,
      formula:
`P = (P_lift + P_digging) × Ceff
P_lift    = G × g × H / 1000
         = ${(results.Q/3.6).toFixed(3)} × 9.81 × ${inputs.H_m} / 1000
         = ${fmt(results.P_lift, 3)} kW
P_digging = G × g × (d × Leq) / 1000
         = ${fmt(results.P_digging, 3)} kW  (Leq=${results.Leq})
Ceff      = ${results.Ceff}
→ P_total = ${fmt(results.P_total, 3)} kW  [CEMA 375 §4 LEQ]`,
    },
    {
      label: "Motor Selected",
      value: results.motor_kw ?? "—",
      unit: "kW",
      disc: "power",
      status: "ok",
      target: `SF ${inputs.sf} · design ${(results.P_total * inputs.sf).toFixed(2)} kW`,
      margin: motorMargin != null ? parseFloat(motorMargin) : null,
      formula:
`Motor = next std size ≥ P_total × SF
P_total = ${fmt(results.P_total, 3)} kW
SF      = ${inputs.sf}
Design  = ${(results.P_total * inputs.sf).toFixed(3)} kW
Selected: ${results.motor_kw} kW  [IEC/NEMA std sizes]`,
    },
    {
      label: "Headshaft Load",
      value: (T_total / 1000).toFixed(2),
      unit: "kN",
      disc: "structural",
      status: T_total > 80000 ? "fail" : T_total > 50000 ? "warn" : "ok",
      target: `T1+T2+T3  ≤ 80 kN`,
      margin: null,
      formula:
`R = T1 + T2 + T3
T1 = ${(results.T1/1000).toFixed(2)} kN  (material weight in carrying run)
T2 = ${(results.T2/1000).toFixed(2)} kN  (belt + bucket self-weight)
T3 = ${(results.T3/1000).toFixed(2)} kN  (slack side, K=${inputs.K_takeup})
→ R = ${(T_total/1000).toFixed(2)} kN  [CEMA 375 §4.07–4.09]`,
    },
    {
      label: "Head Shaft Dia.",
      value: fmt(results.d_mm, 0) ?? "—",
      unit: "mm",
      disc: "structural",
      status: "info",
      target: `Governed by ${results.governed_by ?? "stress"}`,
      margin: null,
      formula:
`Stress check (ASME DE-Goodman):
  d_stress   = ${fmt(results.d_stress_mm, 1)} mm
Deflection check (CEMA 0.0015 in/in):
  d_deflect  = ${fmt(results.d_deflect_mm, 1)} mm
Governing    = ${fmt(results.d_mm, 1)} mm
T_shaft      = ${(results.T_Nm/1000).toFixed(3)} kNm  [CEMA 375 §4]`,
    },
    {
      label: "Belt Width",
      value: results.belt_w ?? "—",
      unit: "mm",
      disc: "mechanical",
      status: "info",
      target: `Bucket ${results.bucket?.W}mm + 50mm clearance`,
      margin: null,
      formula:
`Belt width = next std ≥ bucket_W + 50mm
Bucket W  = ${results.bucket?.W} mm
Min width = ${results.bucket?.W + 50} mm
Selected  = ${results.belt_w} mm  [CEMA std widths]`,
    },
    {
      label: "Centrifugal Ratio",
      value: fmt(results.cr, 3) ?? "—",
      unit: "—",
      disc: "discharge",
      status: crOK ? "ok" : results.cr < 1.0 ? "warn" : "warn",
      target: "Optimal: 1.0 – 1.8",
      margin: null,
      formula:
`CR = v² / (r · g)
v  = ${fmt(results.v, 4)} m/s
r  = ${(inputs.D_mm/2000).toFixed(4)} m  (head pulley radius)
g  = 9.81 m/s²
→ CR = ${fmt(results.v, 4)}² / (${(inputs.D_mm/2000).toFixed(4)} × 9.81)
→ CR = ${fmt(results.cr, 4)}
Release angle θ = ${fmt(results.theta_rel, 1)}° from vertical  [CEMA 375 §3]`,
    },
    {
      label: "Bearing L10 Life",
      value: results.L10 > 9999
        ? `${(results.L10 / 1000).toFixed(0)}k`
        : fmt(results.L10, 0) ?? "—",
      unit: "h",
      disc: "mechanical",
      status: results.L10 < 20000 ? "fail" : results.L10 < 40000 ? "warn" : "ok",
      target: "≥ 40,000 h continuous",
      margin: null,
      formula:
`L10 = (C / P)³ × 10⁶ / (60 × n)
C   = 355,000 N  (basic dynamic rating)
P   = ${fmt(results.R_headshaft, 0)} N  (radial load)
n   = ${inputs.n_rpm} rpm
→ L10 = ${fmt(results.L10, 0)} h  [ISO 281]`,
    },
    {
      label: "Bucket Series",
      value: results.bucket?.id ?? "—",
      unit: "",
      disc: "process",
      status: "info",
      target: `${results.bucket?.V}L  ·  ${results.bucket?.W}×${results.bucket?.H}mm`,
      margin: null,
      formula:
`Active volume = V × η
V   = ${results.bucket?.V} L  (struck capacity)
η   = ${(inputs.fill_pct/100).toFixed(2)}  (fill factor)
→ Active = ${(results.bucket?.V * inputs.fill_pct / 100).toFixed(3)} L / bucket
Mass/bucket = ${(results.bucket?.V * inputs.fill_pct / 100 * results.rho / 1000).toFixed(3)} kg
Spacing  = ${(results.spacing * 1000).toFixed(0)} mm  [CEMA 375 §4]`,
    },
    {
      label: "Material",
      value: results.rho ?? "—",
      unit: "kg/m³",
      disc: "process",
      status: "info",
      target: results.mat?.name ?? "",
      margin: null,
      formula:
`CEMA 550 code: ${results.mat?.cema_code ?? "—"}
ρ_loose  = ${results.mat?.rho_loose} kg/m³
ρ_vib    = ${results.mat?.rho_vib} kg/m³
Abrasive = ${results.mat?.abr_code}/7
Flowability = ${results.mat?.flowability}/4
Km factor   = ${results.mat?.Km}  [ANSI/CEMA 550-2020]`,
    },
    {
      label: "Fill Factor",
      value: `${inputs.fill_pct}`,
      unit: "%",
      disc: "process",
      status: inputs.fill_pct >= 80 ? "warn" : "ok",
      target: `${(results.bucket?.V * inputs.fill_pct / 100).toFixed(3)} L / bucket`,
      margin: null,
      formula:
`η = fill_pct / 100 = ${(inputs.fill_pct/100).toFixed(2)}
Active vol = ${results.bucket?.V} × ${(inputs.fill_pct/100).toFixed(2)}
          = ${(results.bucket?.V * inputs.fill_pct / 100).toFixed(3)} L
CEMA 375 §4: fill > 80% increases spillage risk at boot`,
    },
  ];

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: compact
        ? "1fr"  // single column in right panel (360px)
        : "repeat(auto-fill, minmax(220px, 1fr))",
      gap: compact ? 6 : 10,
      padding: compact ? "10px 10px" : 16,
    }}>
      {kpis.map((k, i) => <KpiCard key={i} {...k} />)}
    </div>
  );
}
