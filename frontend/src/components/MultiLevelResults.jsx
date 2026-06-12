// MultiLevelResults.jsx — Task 9: Executive / Engineering / Detailed tabs
import { useState } from "react";
import KpiGrid from "./KpiGrid";

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 700, letterSpacing: ".1em",
      textTransform: "uppercase", color: "var(--text3)",
      padding: "10px 12px 4px",
      borderBottom: "1px solid var(--border)",
    }}>{children}</div>
  );
}

function DataRow({ label, value, color, mono = true }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "baseline",
      padding: "5px 12px", borderBottom: "1px solid var(--border)", minHeight: 26,
    }}>
      <span style={{ fontSize: 11, color: "var(--text3)", paddingRight: 8 }}>{label}</span>
      <span style={{
        fontSize: 11, color: color || "var(--text2)",
        fontFamily: mono ? "JetBrains Mono, monospace" : "var(--ff-ui)",
        fontWeight: 500, textAlign: "right",
      }}>{value ?? "—"}</span>
    </div>
  );
}

function VerdictBadge({ ok, label }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: "var(--r-pill)",
      fontSize: 11, fontWeight: 700, letterSpacing: ".04em",
      background: ok ? "rgba(16,185,129,.12)" : "rgba(239,68,68,.12)",
      color: ok ? "var(--success)" : "var(--danger)",
      border: `1px solid ${ok ? "rgba(16,185,129,.3)" : "rgba(239,68,68,.3)"}`,
    }}>
      {ok ? "✓" : "✗"} {label}
    </span>
  );
}

// ── EXECUTIVE VIEW ─────────────────────────────────────────────────────────

function ExecutiveView({ results, inputs }) {
  if (!results) return (
    <div style={{ padding: 16, color: "var(--muted)", fontSize: 12 }}>Calculating…</div>
  );
  const fmt = (v, d = 1) =>
    v != null && !Number.isNaN(Number(v)) ? Number(v).toFixed(d) : "—";

  const capOK   = results.Q  != null && Number(results.Q)  >= Number(inputs.Q_req);
  const speedOK = results.v  != null && results.v >= (results.bucket?.v_min ?? 0.5)
                                     && results.v <= (results.bucket?.v_max ?? 3.0);
  const crOK    = results.cr != null && results.cr >= 1.0 && results.cr <= 1.8;
  const T_total = (results.T1 ?? 0) + (results.T2 ?? 0) + (results.T3 ?? 0);
  const l10OK   = results.L10 != null && results.L10 >= 40000;
  const failCount = results.checks?.filter(c => c.type === "fail").length ?? 0;
  const warnCount = results.checks?.filter(c => c.type === "warn").length ?? 0;
  const overallOK = failCount === 0;

  return (
    <div style={{ paddingBottom: 16 }}>
      {/* Verdict banner */}
      <div style={{
        margin: "10px 10px 6px", padding: "12px 14px",
        borderRadius: "var(--r-lg)",
        background: overallOK ? "rgba(16,185,129,.08)" : "rgba(239,68,68,.08)",
        border: `1px solid ${overallOK ? "rgba(16,185,129,.25)" : "rgba(239,68,68,.25)"}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <div style={{
            fontSize: 13, fontWeight: 700,
            color: overallOK ? "var(--success)" : "var(--danger)", marginBottom: 3,
          }}>
            {overallOK ? "Design Acceptable" : `Design has ${failCount} failure${failCount > 1 ? "s" : ""}`}
          </div>
          <div style={{ fontSize: 10, color: "var(--muted)" }}>
            {failCount === 0 && warnCount === 0
              ? "All engineering checks pass — ready for detailed review."
              : `${failCount} fail · ${warnCount} warn — see Engineering tab.`}
          </div>
        </div>
        <div style={{ fontSize: 28 }}>{overallOK ? "✓" : "✗"}</div>
      </div>

      {/* Key capacity decision */}
      <SectionLabel>Capacity Decision</SectionLabel>
      <DataRow label="Required"   value={`${inputs.Q_req} t/h`} />
      <DataRow label="Achieved"   value={`${fmt(results.Q, 1)} t/h`}
        color={capOK ? "var(--success)" : "var(--danger)"} />
      <DataRow label="Margin"
        value={results.Q != null
          ? `${(((results.Q - inputs.Q_req) / inputs.Q_req) * 100).toFixed(1)}%`
          : "—"}
        color={capOK ? "var(--success)" : "var(--danger)"} />

      {/* Verdicts */}
      <SectionLabel>Key Verdicts</SectionLabel>
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 7 }}>
        {[
          { label: "Capacity",              ok: capOK },
          { label: "Belt Speed",            ok: speedOK },
          { label: "Centrifugal Discharge", ok: crOK },
          { label: "Bearing Life",          ok: l10OK },
        ].map((v) => (
          <div key={v.label} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span style={{ fontSize: 11, color: "var(--text3)" }}>{v.label}</span>
            <VerdictBadge ok={v.ok} label={v.ok ? "PASS" : "WARN"} />
          </div>
        ))}
      </div>

      {/* Machine spec */}
      <SectionLabel>Machine Specification</SectionLabel>
      <DataRow label="Bucket Series"
        value={`${results.bucket?.id} — ${results.bucket?.V}L (${results.bucket?.W}×${results.bucket?.H}mm)`} />
      <DataRow label="Belt Speed"    value={`${fmt(results.v, 3)} m/s`} />
      <DataRow label="Head Pulley"   value={`Ø${inputs.D_mm}mm @ ${inputs.n_rpm} rpm`} />
      <DataRow label="Belt Width"    value={`${results.belt_w} mm`} />
      <DataRow label="Lift Height"   value={`${inputs.H_m} m`} />
      <DataRow label="Material"      value={results.mat?.name ?? "—"} mono={false} />
      <DataRow label="Bulk Density"  value={`${results.rho} kg/m³`} />

      {/* Drive */}
      <SectionLabel>Drive</SectionLabel>
      <DataRow label="Motor"         value={`${results.motor_kw} kW`} color="var(--primary)" />
      <DataRow label="Drive Power"   value={`${fmt(results.P_total, 2)} kW`} />
      <DataRow label="Service Factor" value={inputs.sf} />
      <DataRow label="Motor Reserve"
        value={results.motor_kw && results.P_total
          ? `${(((results.motor_kw - results.P_total * inputs.sf) / (results.P_total * inputs.sf)) * 100).toFixed(1)}%`
          : "—"} />

      {/* Structure */}
      <SectionLabel>Structure</SectionLabel>
      <DataRow label="Head Shaft"    value={`Ø${fmt(results.d_mm, 0)} mm`} />
      <DataRow label="Governed by"   value={results.governed_by ?? "stress"} mono={false} />
      <DataRow label="Headshaft Load" value={`${(T_total / 1000).toFixed(2)} kN`}
        color={T_total > 50000 ? "var(--warning)" : "var(--text2)"} />
      <DataRow label="Bearing L10"
        value={results.L10 > 9999
          ? `${(results.L10 / 1000).toFixed(0)}k h`
          : `${fmt(results.L10, 0)} h`}
        color={l10OK ? "var(--success)" : "var(--warning)"} />
    </div>
  );
}

// ── DETAILED VIEW ──────────────────────────────────────────────────────────

function DetailedView({ results, inputs }) {
  if (!results) return (
    <div style={{ padding: 16, color: "var(--muted)", fontSize: 12 }}>Calculating…</div>
  );
  const fmt = (v, d = 2) =>
    v != null && !Number.isNaN(Number(v)) ? Number(v).toFixed(d) : "—";
  const T_total = (results.T1 ?? 0) + (results.T2 ?? 0) + (results.T3 ?? 0);

  return (
    <div style={{ paddingBottom: 16 }}>
      <SectionLabel>Input Parameters</SectionLabel>
      <DataRow label="Q required"         value={`${inputs.Q_req} t/h`} />
      <DataRow label="H lift"             value={`${inputs.H_m} m`} />
      <DataRow label="D head pulley"      value={`${inputs.D_mm} mm`} />
      <DataRow label="D boot pulley"      value={`${inputs.boot_pulley_D_mm ?? 300} mm`} />
      <DataRow label="n head shaft"       value={`${inputs.n_rpm} rpm`} />
      <DataRow label="Fill factor"        value={`${inputs.fill_pct} %`} />
      <DataRow label="Bucket gap"         value={`${inputs.bucket_gap} mm`} />
      <DataRow label="μ friction"         value={fmt(inputs.mu, 2)} />
      <DataRow label="Wrap angle"         value={`${inputs.wrap_deg} °`} />
      <DataRow label="K takeup"           value={fmt(inputs.K_takeup, 2)} />
      <DataRow label="Leq (0=auto)"       value={`${inputs.Leq}`} />
      <DataRow label="Ceff (0=auto)"      value={`${inputs.Ceff}`} />
      <DataRow label="Service factor"     value={fmt(inputs.sf, 2)} />

      <SectionLabel>Capacity  [CEMA 375 §4]</SectionLabel>
      <DataRow label="Belt speed v"       value={`${fmt(results.v, 4)} m/s`} />
      <DataRow label="Bucket spacing s"   value={`${fmt(results.spacing != null ? results.spacing * 1000 : null, 1)} mm`} />
      <DataRow label="Bucket volume Vb"   value={`${results.bucket?.V} L`} />
      <DataRow label="Fill η"             value={`${(inputs.fill_pct / 100).toFixed(2)}`} />
      <DataRow label="Bulk density ρ"     value={`${results.rho} kg/m³`} />
      <DataRow label="Capacity Q"         value={`${fmt(results.Q, 2)} t/h`}
        color="var(--primary)" />

      <SectionLabel>Power  [CEMA 375 §4 LEQ]</SectionLabel>
      <DataRow label="Leq used"           value={results.Leq} />
      <DataRow label="Ceff used"          value={results.Ceff} />
      <DataRow label="P_lift"             value={`${fmt(results.P_lift, 3)} kW`} />
      <DataRow label="P_digging"          value={`${fmt(results.P_digging, 3)} kW`} />
      <DataRow label="P_drive_loss"       value={`${fmt(results.P_drive_loss, 3)} kW`} />
      <DataRow label="P_total"            value={`${fmt(results.P_total, 3)} kW`}
        color="var(--warning)" />
      <DataRow label="Motor selected"     value={`${results.motor_kw} kW`}
        color="var(--primary)" />

      <SectionLabel>Belt Tensions  [CEMA 375 §4.07–4.09]</SectionLabel>
      <DataRow label="T1 (material)"      value={`${fmt(results.T1 != null ? results.T1/1000 : null, 3)} kN`} />
      <DataRow label="T2 (belt+bucket)"   value={`${fmt(results.T2 != null ? results.T2/1000 : null, 3)} kN`} />
      <DataRow label="T3 (slack side)"    value={`${fmt(results.T3 != null ? results.T3/1000 : null, 3)} kN`} />
      <DataRow label="F_eff"              value={`${fmt(results.F_eff != null ? results.F_eff/1000 : null, 3)} kN`} />
      <DataRow label="R headshaft"        value={`${(T_total/1000).toFixed(3)} kN`} />

      <SectionLabel>Shaft Design  [CEMA 375 §4 / ASME DE-Goodman]</SectionLabel>
      <DataRow label="Torque T"           value={`${fmt(results.T_Nm != null ? results.T_Nm/1000 : null, 3)} kNm`} />
      <DataRow label="d stress (ASME)"    value={`${fmt(results.d_stress_mm, 1)} mm`} />
      <DataRow label="d deflect (0.0015)" value={`${fmt(results.d_deflect_mm, 1)} mm`} />
      <DataRow label="d governing"        value={`${fmt(results.d_mm, 1)} mm`}
        color="var(--primary)" />
      <DataRow label="Governed by"        value={results.governed_by ?? "—"} mono={false} />

      <SectionLabel>Discharge Physics  [CEMA 375 §3]</SectionLabel>
      <DataRow label="Centrifugal ratio CR" value={fmt(results.cr, 4)} />
      <DataRow label="Release angle θ"    value={`${fmt(results.theta_rel, 2)} °`} />
      <DataRow label="Belt ply (est.)"    value={results.belt_ply} />

      <SectionLabel>Bearing  [ISO 281]</SectionLabel>
      <DataRow label="Radial load P"      value={`${fmt(results.R_headshaft != null ? results.R_headshaft/1000 : null, 2)} kN`} />
      <DataRow label="C basic (90mm ⌀)"  value="355 kN" />
      <DataRow label="L10"
        value={results.L10 > 9999
          ? `${(results.L10/1000).toFixed(1)}k h`
          : `${fmt(results.L10, 0)} h`}
        color={results.L10 >= 40000 ? "var(--success)" : "var(--warning)"} />

      <SectionLabel>Material  [ANSI/CEMA 550-2020]</SectionLabel>
      <DataRow label="CEMA code"          value={results.mat?.cema_code ?? "—"} />
      <DataRow label="Name"               value={results.mat?.name ?? "—"} mono={false} />
      <DataRow label="ρ loose"            value={`${results.mat?.rho_loose} kg/m³`} />
      <DataRow label="ρ vibrated"         value={`${results.mat?.rho_vib} kg/m³`} />
      <DataRow label="Angle of repose"    value={`${results.mat?.angle_repose} °`} />
      <DataRow label="Abrasive code"      value={`${results.mat?.abr_code} / 7`} />
      <DataRow label="Flowability"        value={`${results.mat?.flowability} / 4`} />
      <DataRow label="Km factor"          value={results.mat?.Km} />
      {results.mat?.hazard_codes?.length > 0 && (
        <DataRow label="Hazard codes"
          value={results.mat.hazard_codes.join(", ")}
          color="var(--warning)" />
      )}
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────

const LEVELS = [
  { id: "executive",   label: "Executive",   desc: "Decision summary" },
  { id: "engineering", label: "Engineering", desc: "KPI cards + formulas" },
  { id: "detailed",    label: "Detailed",    desc: "All computed values" },
];

export default function MultiLevelResults({ results, inputs }) {
  const [level, setLevel] = useState("engineering");

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {/* Level sub-tabs */}
      <div style={{
        display: "flex", borderBottom: "1px solid var(--border)",
        background: "var(--panel2)", padding: "0 10px", flexShrink: 0,
      }}>
        {LEVELS.map((l) => {
          const active = level === l.id;
          return (
            <button key={l.id} onClick={() => setLevel(l.id)} title={l.desc} style={{
              padding: "7px 11px", fontSize: 11,
              fontWeight: active ? 600 : 400,
              cursor: "pointer", border: "none", background: "transparent",
              color: active ? "var(--primary)" : "var(--text3)",
              borderBottom: `2px solid ${active ? "var(--primary)" : "transparent"}`,
              marginBottom: -1, transition: "all var(--t-base)",
              fontFamily: "var(--ff-ui)", whiteSpace: "nowrap",
            }}
            onMouseEnter={e => { if (!active) e.currentTarget.style.color = "var(--text2)"; }}
            onMouseLeave={e => { if (!active) e.currentTarget.style.color = "var(--text3)"; }}
            >{l.label}</button>
          );
        })}
      </div>

      {level === "executive"   && <ExecutiveView   results={results} inputs={inputs} />}
      {level === "engineering" && <KpiGrid          results={results} inputs={inputs} compact />}
      {level === "detailed"    && <DetailedView     results={results} inputs={inputs} />}
    </div>
  );
}
