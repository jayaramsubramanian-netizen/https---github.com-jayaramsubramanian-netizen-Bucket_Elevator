// EquipmentTree.jsx
// Equipment hierarchy tree for VECTRIX™ bucket elevator.
//
// Status dots are computed LIVE from results.checks every render.
// This fixes the bug where orange dots didn't turn green after the user
// corrected a warning — the old version cached status at mount time.
//
// Tree structure covers all subsystems now in the calculation pipeline:
//   PROCESS            → capacity, belt speed, centrifugal ratio
//   HEAD ASSEMBLY      → shaft, hub/key, bearings, lagging, end disc
//   DRIVE              → motor, power, gearbox ratio
//   BELT & BUCKETS     → belt class, bucket geometry, bolt fatigue
//   TAKE-UP            → gravity take-up, screw take-up
//   BOOT ASSEMBLY      → boot pulley, material intake
//   DISCHARGE CHUTE    → chute angle, flow regime, wear, dust
//   CASING & STRUCTURE → plate, stiffeners, panel deflection
//
// Each node maps to a set of check message keywords.  Status is:
//   green  → all matching checks are ok/info/pass
//   amber  → at least one warn, none fail
//   red    → at least one fail
//   grey   → no results loaded yet

import { useState } from "react";

// ── Keyword → tree-node mapping ─────────────────────────────────────────────
// Returns {status: 'ok'|'warn'|'fail'|'none', checks: [...]}
function nodeStatus(checks, keywords) {
  if (!checks?.length) return { status: "none", checks: [] };
  const kw = keywords.map(k => k.toLowerCase());
  const matched = checks.filter(c =>
    kw.some(k => (c.msg ?? "").toLowerCase().includes(k))
  );
  if (!matched.length) return { status: "none", checks: [] };
  if (matched.some(c => c.type === "fail")) return { status: "fail", checks: matched };
  if (matched.some(c => c.type === "warn")) return { status: "warn", checks: matched };
  return { status: "ok", checks: matched };
}

// ── Status dot ────────────────────────────────────────────────────────────────
function Dot({ status, size = 7 }) {
  const color =
    status === "ok"   ? "var(--success, #1fb86e)"  :
    status === "warn" ? "var(--warning, #d98e00)"  :
    status === "fail" ? "var(--danger,  #e05252)"  :
                        "var(--text3,   #5a7a9a)";
  return (
    <span style={{
      display: "inline-block",
      width: size, height: size,
      borderRadius: "50%",
      background: color,
      flexShrink: 0,
      boxShadow: status !== "none" ? `0 0 4px ${color}80` : "none",
      transition: "background .3s, box-shadow .3s",
    }} />
  );
}

// ── Tree leaf node ────────────────────────────────────────────────────────────
function Leaf({ label, sub, status, onClick, depth = 2 }) {
  return (
    <div
      onClick={onClick}
      title={label}
      style={{
        display: "flex", alignItems: "flex-start", gap: 7,
        padding: `4px 10px 4px ${10 + depth * 12}px`,
        cursor: onClick ? "pointer" : "default",
        borderRadius: 4,
        transition: "background .15s",
      }}
      onMouseEnter={e => e.currentTarget.style.background = "var(--panel, #0d1c2e)"}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
    >
      {/* indent line */}
      <span style={{
        position: "absolute", left: 10 + (depth - 1) * 12,
        width: 1, height: "100%",
        background: "var(--border, #1c3050)", opacity: 0.4,
      }} />
      <Dot status={status} size={6} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 11, color: "var(--text2, #b0c4d8)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{label}</div>
        {sub && (
          <div style={{
            fontSize: 9, color: "var(--text3, #5a7a9a)",
            marginTop: 1, lineHeight: 1.3,
          }}>{sub}</div>
        )}
      </div>
    </div>
  );
}

// ── Section header (collapsible) ──────────────────────────────────────────────
function Section({ id, label, status, children, defaultOpen = true, onNodeClick }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ position: "relative" }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 10px 6px 10px",
          cursor: "pointer",
          transition: "background .15s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,.03)"}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      >
        <Dot status={status} size={7} />
        <span style={{
          fontSize: 9, fontWeight: 700, letterSpacing: ".1em",
          textTransform: "uppercase", color: "var(--text3, #5a7a9a)",
          flex: 1,
        }}>{label}</span>
        <span style={{
          fontSize: 9, color: "var(--text3, #5a7a9a)",
          transform: open ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform .2s",
          lineHeight: 1,
        }}>›</span>
      </div>
      {open && (
        <div style={{ borderLeft: "1px solid var(--border, #1c3050)", marginLeft: 16 }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const f = (v, dp = 1, suffix = "") =>
  v != null && !Number.isNaN(Number(v)) ? `${Number(v).toFixed(dp)}${suffix}` : "—";

// Overall pass/warn/fail aggregation
function mergeStatus(...statuses) {
  if (statuses.includes("fail")) return "fail";
  if (statuses.includes("warn")) return "warn";
  if (statuses.every(s => s === "none")) return "none";
  return "ok";
}

// ── Main component ────────────────────────────────────────────────────────────
export default function EquipmentTree({ results, inputs, onNodeClick }) {
  const r  = results || {};
  const inp = inputs  || {};
  const checks = r.checks || [];

  // ── Live status per subsystem ─────────────────────────────────────────────
  const s_capacity  = nodeStatus(checks, ["capacity", "Capacity"]);
  const s_speed     = nodeStatus(checks, ["speed", "Speed"]);
  const s_cr        = nodeStatus(checks, ["CR=", "centrifugal", "scatter"]);
  const s_slip      = nodeStatus(checks, ["slip", "Slip", "euler", "Euler"]);
  const s_shaft     = nodeStatus(checks, ["shaft", "Shaft", "governed by"]);
  const s_key       = nodeStatus(checks, ["keyway", "Keyway", "key"]);
  const s_bearing   = nodeStatus(checks, ["bearing", "Bearing", "L10"]);
  const s_lagging   = nodeStatus(checks, ["lagging", "Lagging"]);
  const s_end_disc  = nodeStatus(checks, ["end disc", "End disc"]);
  const s_motor     = nodeStatus(checks, ["motor", "Motor", "kW", "Ceff"]);
  const s_belt      = nodeStatus(checks, ["belt", "Belt", "PLY", "headshaft"]);
  const s_bolt      = nodeStatus(checks, ["bolt", "Bolt", "fatigue", "Goodman"]);
  const s_takeup    = nodeStatus(checks, ["take-up", "Take-up", "takeup", "counterweight"]);
  const s_casing    = nodeStatus(checks, ["casing", "Casing", "panel", "stiffener"]);
  const s_chute     = nodeStatus(checks, ["chute", "Chute", "discharge", "plugging", "dust"]);
  const s_atex      = nodeStatus(checks, ["ATEX", "atex", "explosive", "dust control", "stainless"]);
  const s_abr       = nodeStatus(checks, ["abrasion", "AR400", "AR500", "liner"]);

  // Aggregate section statuses
  const st_process  = mergeStatus(s_capacity.status, s_speed.status, s_cr.status);
  const st_head     = mergeStatus(s_shaft.status, s_key.status, s_bearing.status, s_lagging.status, s_end_disc.status);
  const st_drive    = s_motor.status;
  const st_belt     = mergeStatus(s_belt.status, s_slip.status, s_bolt.status);
  const st_takeup   = s_takeup.status;
  const st_chute    = s_chute.status;
  const st_casing   = mergeStatus(s_casing.status, s_abr.status);
  const st_mech     = mergeStatus(st_head, st_drive, st_belt, st_takeup, st_casing);
  const overall     = mergeStatus(st_process, st_mech, st_chute);

  // ── Value shortcuts ────────────────────────────────────────────────────────
  const bkt    = r.bucket || {};
  const mat    = r.mat || r.material || {};
  const hub    = r.hub || {};
  const lag    = r.lagging || {};
  const tg     = r.takeup_gravity || {};
  const dc     = r.discharge_chute || {};
  const dcperf = dc.performance || {};
  const dcmnt  = dc.maintenance || {};

  const warnCount = checks.filter(c => c.type === "warn").length;
  const failCount = checks.filter(c => c.type === "fail").length;
  const okCount   = checks.filter(c => c.type === "ok").length;

  return (
    <div style={{
      height: "100%",
      overflowY: "auto",
      overflowX: "hidden",
      fontSize: 12,
      userSelect: "none",
    }}>
      {/* ── Equipment header ──────────────────────────────────────────────── */}
      <div style={{
        padding: "10px 12px 8px",
        borderBottom: "1px solid var(--border, #1c3050)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <span style={{ fontSize: 16, color: "var(--primary, #4a9eff)" }}>⛏</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text, #ddeaf6)" }}>
              Bucket Elevator
            </div>
            <div style={{ fontSize: 10, color: "var(--text3)", letterSpacing: ".04em" }}>
              VECTOMEC™ BE-001
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {failCount > 0 && (
            <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px",
              borderRadius: 999, background: "var(--danger-dim, #1a0808)",
              color: "var(--danger)", border: "1px solid var(--danger-border, #4a1515)" }}>
              {failCount} FAIL
            </span>
          )}
          {warnCount > 0 && (
            <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px",
              borderRadius: 999, background: "var(--warning-dim, #1a1205)",
              color: "var(--warning)", border: "1px solid var(--warning-border, #4a3005)" }}>
              {warnCount} WARN
            </span>
          )}
          {failCount === 0 && warnCount === 0 && okCount > 0 && (
            <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px",
              borderRadius: 999, background: "var(--success-dim, #081a10)",
              color: "var(--success)", border: "1px solid var(--success-border, #1a4a28)" }}>
              {okCount} OK
            </span>
          )}
        </div>
      </div>

      {/* ── PROCESS ───────────────────────────────────────────────────────── */}
      <Section id="process" label="Process" status={st_process}>
        <Leaf label="Material"
          sub={`${mat.name || inp.mat_id || "—"}  ρ=${f(r.rho, 0)} kg/m³`}
          status="none" depth={2} />
        <Leaf label="Capacity"
          sub={`${f(r.Q ?? r.Q_th, 1)} t/h  req ${inp.Q_req ?? "—"} t/h`}
          status={s_capacity.status} onClick={() => onNodeClick?.("process")} depth={2} />
        <Leaf label="Belt Speed"
          sub={`${f(r.v ?? r.v_ms, 2)} m/s`}
          status={s_speed.status} onClick={() => onNodeClick?.("process")} depth={2} />
        <Leaf label="Centrifugal Ratio"
          sub={`CR = ${f(r.cr ?? r.centrifugal_ratio, 3)}`}
          status={s_cr.status} onClick={() => onNodeClick?.("process")} depth={2} />
      </Section>

      {/* ── MECHANICAL DESIGN (group) ──────────────────────────────────────── */}
      <Section id="mechanical" label="Mechanical Design" status={st_mech} defaultOpen>

        {/* 2a Head & Tail Pulley */}
        <Section id="head" label="Head Assembly" status={st_head} depth={1} defaultOpen>
          <Leaf label="Head Pulley"
            sub={`Ø${inp.D_mm ?? "—"}mm  ${inp.n_rpm ?? "—"} rpm`}
            status="none" depth={3} />
          <Leaf label="Head Shaft"
            sub={`Ø${f(r.d_mm, 1)}mm  ${r.governed_by ?? "—"}`}
            status={s_shaft.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="Hub & Key"
            sub={hub.d_hub_mm
              ? `Hub Ø${f(hub.d_hub_mm, 1)}mm  key ${hub.b_key_mm}×${hub.h_key_mm}mm`
              : "—"}
            status={s_key.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="Bearings"
            sub={`L10 ${r.L10 != null ? Number(r.L10).toLocaleString() : "—"} h`}
            status={s_bearing.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="Lagging"
            sub={lag.lagging_type
              ? `${lag.lagging_type.replace(/_/g," ")}  μ=${f(lag.mu_operating,2)}`
              : "—"}
            status={s_lagging.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="End Disc"
            sub={r.end_disc?.t_governing_mm ? `min t=${f(r.end_disc.t_governing_mm, 1)}mm` : "—"}
            status={s_end_disc.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
        </Section>

        {/* 2b Belt Selection */}
        <Section id="belt_sel" label="Belt Selection" status={st_belt} depth={1}>
          <Leaf label="Belt"
            sub={`${r.belt_class ?? (r.belt_ply ? r.belt_ply + " PLY" : "—")}  ${r.belt_w ?? r.belt_width_mm ?? "—"}mm`}
            status={s_belt.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="Belt Slip"
            sub={r.euler_ratio != null
              ? `e^μθ=${f(r.euler_ratio,3)}  ${r.slip_safe ? "✓ Safe" : "✗ Risk"}`
              : "—"}
            status={s_slip.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
        </Section>

        {/* 2c Bucket Selection */}
        <Section id="bucket_sel" label="Bucket Selection" status="none" depth={1}>
          <Leaf label="Bucket Series"
            sub={bkt.id ? `${bkt.id}  ${bkt.W}×${bkt.H}mm  ${bkt.V}L` : "—"}
            status="none" depth={3} />
          <Leaf label="Bolt Fatigue"
            sub={r.bolt_fatigue?.goodman_ratio != null
              ? `Goodman ${f(r.bolt_fatigue.goodman_ratio, 3)}`
              : "—"}
            status={s_bolt.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
        </Section>

        {/* 2d Take-Up Selection */}
        <Section id="takeup_sel" label="Take-Up Selection" status={st_takeup} depth={1}>
          <Leaf label="Gravity Take-Up"
            sub={tg.W_counterweight_kg_gross
              ? `${f(tg.W_counterweight_kg_gross, 0)} kg  travel ${f((tg.travel_m ?? 0)*1000, 0)} mm`
              : "—"}
            status={s_takeup.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="Screw Alternative"
            sub={r.takeup_screw?.d_core_min_mm
              ? `d_core ${f(r.takeup_screw.d_core_min_mm, 1)}mm  SF ${f(r.takeup_screw.SF_buckling, 2)}`
              : "—"}
            status={r.takeup_screw?.buckling_safe === false ? "warn" : "none"} depth={3} />
        </Section>

        {/* 2e Discharge Section */}
        <Section id="discharge_sec" label="Discharge Section" status={st_chute} depth={1}>
          <Leaf label="Type"
            sub={r.is_continuous ? `HF Continuous  CR=${f(r.cr,3)}` : `Centrifugal  CR=${f(r.cr,3)}`}
            status="none" depth={3} />
          <Leaf label="Chute"
            sub={dcperf.chute_angle_deg
              ? `${f(dcperf.chute_angle_deg, 1)}°  ${dcperf.flow_regime?.replace(/_/g," ") ?? "—"}`
              : "—"}
            status={s_chute.status} onClick={() => onNodeClick?.("chute")} depth={3} />
          <Leaf label="Liner"
            sub={dcmnt.liner_material ? `${dcmnt.liner_material}  ${dcmnt.liner_thickness_mm ?? "—"}mm` : "—"}
            status="none" depth={3} />
        </Section>

        {/* 2f Feed Design (stub) */}
        <Section id="feed_sec" label="Feed Design" status="none" depth={1}>
          <Leaf label="Boot Pulley"
            sub={`Ø${inp.boot_pulley_same_as_head ? inp.D_mm : (inp.boot_pulley_D_mm ?? "—")}mm  Take-up point`}
            status="none" depth={3} />
          <Leaf label="Boot Volume"
            sub={r.boot_vol_min_m3 ? `${f(r.boot_vol_min_m3, 4)} m³ min` : "—"}
            status="none" depth={3} />
          <Leaf label="Feed Design"
            sub="Pending — next release"
            status="none" depth={3} />
        </Section>

        {/* 2g Casing Design */}
        <Section id="casing_sec" label="Casing Design" status={st_casing} depth={1}>
          <Leaf label="Casing Panel"
            sub={r.casing_panel
              ? `δ=${f(r.casing_panel.delta_actual_mm,1)}mm  t=${f(r.casing_panel.t_use_mm,0)}mm`
              : "—"}
            status={st_casing} onClick={() => onNodeClick?.("mechanical")} depth={3} />
          <Leaf label="Drive"
            sub={`${r.motor_kw ?? r.motor_kW ?? "—"} kW  SF ${inp.sf ?? "—"}`}
            status={s_motor.status} onClick={() => onNodeClick?.("mechanical")} depth={3} />
        </Section>

      </Section>

      {/* ── SERVICE CONDITIONS ─────────────────────────────────────────────── */}
      <Section id="service" label="Service Conditions" status={s_atex.status !== "none" ? s_atex.status : "none"}>
        <Leaf label="Environment"
          sub={`${inp.environment ?? "dry"}  μ=${inp.mu ?? "—"}`}
          status="none" depth={2} />
        {s_atex.status !== "none" && (
          <Leaf label="Hazard Flags" sub="ATEX / dust control"
            status={s_atex.status} onClick={() => onNodeClick?.("casing")} depth={2} />
        )}
        {s_abr.status !== "none" && (
          <Leaf label="Abrasion Rating"
            sub={`Class ${(r.mat || r.material)?.abr_code ?? "—"}/7`}
            status={s_abr.status} depth={2} />
        )}
      </Section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <div style={{
        padding: "8px 12px",
        fontSize: 10, color: "var(--text3)", letterSpacing: ".04em",
        borderTop: "1px solid var(--border)", marginTop: 4,
      }}>
        CEMA 375-2017  ·  ISO 281  ·  ASME B17.1
      </div>
    </div>
  );
}