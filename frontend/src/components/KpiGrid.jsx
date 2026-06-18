// KpiGrid.jsx — Engineering KPI cards
// Pure display component — all values and status from results dict.
//
// v1.9.9: removed all frontend physics computation. Previously this file
// recomputed capMargin, motorMargin, T_total, crOK, speedOK, l10OK,
// and embedded physics in formula strings (g=9.81, C=355kN, belt clearance
// = W+50, etc). All of these now come from pre-computed backend fields:
//   results.cap_ok, results.cap_margin_pct, results.motor_margin_pct,
//   results.T_total, results.cr_ok, results.speed_ok, results.l10_ok,
//   results.status, results.fail_count, results.warn_count
// Formula strings now display backend values rather than recomputing them.

import { useState } from "react";

const C = {
  surface:  "#243247", surface2: "#2d3f57", hi:     "#1e293b",
  border:   "#ffffff12", border2: "#ffffff1e",
  text:     "#f1f5f9",  text2:   "#cbd5e1",  text3:  "#94a3b8",
  muted:    "#64748b",
  primary:  "#3b82f6",  green:   "#10b981",
  amber:    "#f59e0b",  danger:  "#ef4444",
  teal:     "#14b8a6",  purple:  "#a78bfa",
};

const STATUS = {
  ok:   { bg: "rgba(16,185,129,.1)",  border: "rgba(16,185,129,.3)",  text: "#10b981", label: "PASS"  },
  warn: { bg: "rgba(245,158,11,.1)",  border: "rgba(245,158,11,.3)",  text: "#f59e0b", label: "WARN"  },
  fail: { bg: "rgba(239,68,68,.1)",   border: "rgba(239,68,68,.3)",   text: "#ef4444", label: "FAIL"  },
  info: { bg: "rgba(59,130,246,.08)", border: "rgba(59,130,246,.2)",  text: "#3b82f6", label: "INFO"  },
};

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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Tag disc={disc} />
        <Pill status={status} />
      </div>
      <div style={{ fontSize: 11, fontWeight: 600, color: C.text3,
        letterSpacing: ".04em", textTransform: "uppercase" }}>
        {label}
      </div>
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
      {formula && (
        <div>
          <button
            onClick={() => setOpen(!open)}
            style={{
              display: "flex", alignItems: "center", gap: 5,
              background: "none", border: "none", cursor: "pointer",
              fontSize: 10, color: C.muted, fontWeight: 500,
              letterSpacing: ".03em", padding: 0, transition: "color .15s",
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
              color: C.text2, lineHeight: 1.7, whiteSpace: "pre-wrap",
            }}>
              {formula}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const fmt = (v, digits = 2) =>
  v != null && !Number.isNaN(Number(v)) ? Number(v).toFixed(digits) : "—";

export default function KpiGrid({ results, inputs, compact }) {
  if (!results || !results.bucket) return null;

  const r   = results;
  const bkt = r.bucket;
  const mat = r.mat ?? {};

  // All status flags and margins come from the backend (v1.9.9 summary fields)
  const capOk       = r.cap_ok   ?? false;
  const speedOk     = r.speed_ok ?? false;
  const crOk        = r.cr_ok    ?? false;
  const l10Ok       = r.l10_ok   ?? false;
  const capMargin   = r.cap_margin_pct   ?? null;
  const motorMargin = r.motor_margin_pct ?? null;
  // T_total pre-computed by backend; R_headshaft is the same value
  const T_total_kN  = r.T_total != null ? r.T_total / 1000 : null;
  const T_warn      = r.T_total != null && r.T_total > 50000;
  const T_fail      = r.T_total != null && r.T_total > 80000;

  const kpis = [
    {
      label: "Design Capacity",
      value: fmt(r.Q, 1),
      unit: "t/h",
      disc: "process",
      status: capOk ? "ok" : "fail",
      target: `${inputs.Q_req} t/h required`,
      margin: capMargin,
      formula:
`Q = (v / s) · Vb · η · ρ · 3.6
v  = ${fmt(r.v, 3)} m/s   (belt speed)
s  = ${fmt(r.spacing, 4)} m    (bucket spacing)
Vb = ${bkt?.V} L = ${bkt?.V != null ? (bkt.V/1000).toFixed(4) : "—"} m³
η  = ${fmt(inputs.fill_pct / 100, 2)}   (fill factor ${inputs.fill_pct}%)
ρ  = ${r.rho} kg/m³
→  Q = ${fmt(r.Q, 2)} t/h  [CEMA 375 §4]`,
    },
    {
      label: "Belt Speed",
      value: fmt(r.v, 3),
      unit: "m/s",
      disc: "mechanical",
      status: speedOk ? "ok" : "warn",
      target: `${bkt?.v_min}–${bkt?.v_max} m/s (${bkt?.id})`,
      margin: null,
      formula:
`v = π · D · n / 60
D  = ${inputs.D_mm} mm
n  = ${inputs.n_rpm} rpm
→  v = ${fmt(r.v, 4)} m/s  [CEMA 375 §3]`,
    },
    {
      label: "Total Drive Power",
      value: fmt(r.P_total, 2),
      unit: "kW",
      disc: "power",
      status: "info",
      target: `Lift ${fmt(r.P_lift, 2)} + Dig ${fmt(r.P_digging, 2)} kW`,
      margin: null,
      formula:
`P = (P_lift + P_digging) × Ceff
P_lift    = ${fmt(r.P_lift, 3)} kW
P_digging = ${fmt(r.P_digging, 3)} kW  (Leq=${r.Leq})
Ceff      = ${r.Ceff}
→  P_total = ${fmt(r.P_total, 3)} kW  [CEMA 375 §4 LEQ]`,
    },
    {
      label: "Motor Selected",
      value: r.motor_kw ?? "—",
      unit: "kW",
      disc: "power",
      status: "ok",
      target: `SF ${inputs.sf} · design ${fmt(r.P_total != null ? r.P_total * inputs.sf : null, 2)} kW`,
      margin: motorMargin,
      formula:
`Motor = next std size ≥ P_total × SF
P_total  = ${fmt(r.P_total, 3)} kW
SF       = ${inputs.sf}
Design   = ${fmt(r.P_total != null ? r.P_total * inputs.sf : null, 3)} kW
Selected : ${r.motor_kw} kW  [IEC/NEMA std sizes]`,
    },
    {
      label: "Headshaft Load",
      value: T_total_kN != null ? T_total_kN.toFixed(2) : "—",
      unit: "kN",
      disc: "structural",
      status: T_fail ? "fail" : T_warn ? "warn" : "ok",
      target: "T1+T2+T3  ≤ 80 kN",
      margin: null,
      formula:
`R = T1 + T2 + T3
T1 = ${fmt(r.T1 != null ? r.T1/1000 : null, 2)} kN  (material weight)
T2 = ${fmt(r.T2 != null ? r.T2/1000 : null, 2)} kN  (belt+bucket self-weight)
T3 = ${fmt(r.T3 != null ? r.T3/1000 : null, 2)} kN  (slack side, K=${inputs.K_takeup})
→  R = ${T_total_kN != null ? T_total_kN.toFixed(2) : "—"} kN  [CEMA 375 §4.07–4.09]`,
    },
    {
      label: "Head Shaft Dia.",
      value: fmt(r.d_mm, 0),
      unit: "mm",
      disc: "structural",
      status: "info",
      target: `Governed by ${r.governed_by ?? "stress"}`,
      margin: null,
      formula:
`Stress check (ASME DE-Goodman):
  d_stress   = ${fmt(r.d_stress_mm, 1)} mm
Deflection check (CEMA 0.0015 in/in):
  d_deflect  = ${fmt(r.d_deflect_mm, 1)} mm
Governing    = ${fmt(r.d_mm, 1)} mm
T_shaft      = ${fmt(r.T_Nm != null ? r.T_Nm/1000 : null, 3)} kNm  [CEMA 375 §4]`,
    },
    {
      label: "Belt Width",
      value: r.belt_w ?? "—",
      unit: "mm",
      disc: "mechanical",
      status: "info",
      target: `Bucket ${bkt?.W}mm + clearance`,
      margin: null,
      formula:
`Belt width = next std ≥ bucket_W + clearance
Bucket W  = ${bkt?.W} mm
Selected  = ${r.belt_w} mm  [CEMA std widths]`,
    },
    {
      label: "Centrifugal Ratio",
      value: fmt(r.cr, 3),
      unit: "—",
      disc: "discharge",
      status: crOk ? "ok" : "warn",
      target: "Optimal: 1.0 – 1.8",
      margin: null,
      formula:
`CR = v² / (r · g)
v  = ${fmt(r.v, 4)} m/s
r  = head pulley radius
g  = gravitational acceleration
→  CR = ${fmt(r.cr, 4)}
Release angle θ = ${fmt(r.theta_rel, 1)}° from vertical  [CEMA 375 §3]`,
    },
    {
      label: "Bearing L10 Life",
      value: r.L10 > 9999 ? `${(r.L10/1000).toFixed(0)}k` : fmt(r.L10, 0),
      unit: "h",
      disc: "mechanical",
      status: l10Ok ? "ok" : r.L10 >= 20000 ? "warn" : "fail",
      target: "≥ 40,000 h continuous",
      margin: null,
      formula:
`L10 = (C / P)³ × 10⁶ / (60 × n)
C   = rated dynamic capacity (from bearing selection)
P   = ${fmt(r.R_headshaft, 0)} N  (radial load)
n   = ${inputs.n_rpm} rpm
→  L10 = ${fmt(r.L10, 0)} h  [ISO 281]`,
    },
    {
      label: "Bucket Series",
      value: bkt?.id ?? "—",
      unit: "",
      disc: "process",
      status: "info",
      target: `${bkt?.V}L  ·  ${bkt?.W}×${bkt?.H}mm`,
      margin: null,
      formula:
`Active volume = V × η
V   = ${bkt?.V} L  (struck capacity)
η   = ${fmt(inputs.fill_pct/100, 2)}  (fill factor)
Spacing  = ${fmt(r.spacing != null ? r.spacing * 1000 : null, 0)} mm  [CEMA 375 §4]`,
    },
    {
      label: "Material",
      value: r.rho ?? "—",
      unit: "kg/m³",
      disc: "process",
      status: "info",
      target: mat.name ?? "",
      margin: null,
      formula:
`CEMA 550 code : ${mat.cema_code ?? "—"}
ρ_loose      = ${mat.rho_loose} kg/m³
ρ_vibrated   = ${mat.rho_vib} kg/m³
Abrasive     = ${mat.abr_code}/7
Flowability  = ${mat.flowability}/4
Km factor    = ${mat.Km}  [ANSI/CEMA 550-2020]`,
    },
    {
      label: "Fill Factor",
      value: `${inputs.fill_pct}`,
      unit: "%",
      disc: "process",
      status: inputs.fill_pct >= 80 ? "warn" : "ok",
      target: `CEMA advisory ≤ 80%`,
      margin: null,
      formula:
`η = fill_pct / 100 = ${fmt(inputs.fill_pct/100, 2)}
CEMA 375 §4: fill > 80% increases spillage risk at boot`,
    },
  ];

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: compact
        ? "1fr"
        : "repeat(auto-fill, minmax(220px, 1fr))",
      gap: compact ? 6 : 10,
      padding: compact ? "10px 10px" : 16,
    }}>
      {kpis.map((k, i) => <KpiCard key={i} {...k} />)}
    </div>
  );
}