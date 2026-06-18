// EquipmentTree.jsx  v2.1.0
// Equipment hierarchy tree for VECTRIX™ bucket elevator.
//
// v2.1.0 fixes (all stale fields from v2.0 audit):
//   1. bkt.H → bkt.H ?? bkt.depth_mm  (new BUCKET_SERIES uses depth_mm)
//   2. r.boot_vol_min_m3 → r.feed_design?.V_surge_m3  (field never existed)
//   3. Feed Design section → real r.feed_design data, no more "Pending" stub
//   4. Belt Slip leaf → chain branch (shows chain SF / speed when is_chain)
//   5. Screw Take-Up → d_core_recommend_mm with d_core_min_mm fallback
//   6. s_slip keywords → added chain sf / chain speed / sprocket
//   7. Belt Selection → chain subsection (series, SF, sprocket) when is_chain
//   8. Feed Design section status → driven by r.feed_design.warnings

import { useState } from "react";

// ── Keyword → tree-node mapping ─────────────────────────────────────────────
function nodeStatus(checks, keywords) {
  if (!checks?.length) return { status: "none", checks: [] };
  const kw = keywords.map((k) => k.toLowerCase());
  const matched = checks.filter((c) =>
    kw.some((k) => (c.msg ?? "").toLowerCase().includes(k)),
  );
  if (!matched.length) return { status: "none", checks: [] };
  if (matched.some((c) => c.type === "fail"))
    return { status: "fail", checks: matched };
  if (matched.some((c) => c.type === "warn"))
    return { status: "warn", checks: matched };
  return { status: "ok", checks: matched };
}

// ── Status dot ────────────────────────────────────────────────────────────────
function Dot({ status, size = 7 }) {
  const color =
    status === "ok"
      ? "var(--success, #1fb86e)"
      : status === "warn"
        ? "var(--warning, #d98e00)"
        : status === "fail"
          ? "var(--danger,  #e05252)"
          : "var(--text3,   #5a7a9a)";
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        boxShadow: status !== "none" ? `0 0 4px ${color}80` : "none",
        transition: "background .3s, box-shadow .3s",
      }}
    />
  );
}

// ── Tree leaf node ────────────────────────────────────────────────────────────
function Leaf({ label, sub, status, onClick, depth = 2 }) {
  return (
    <div
      onClick={onClick}
      title={label}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 7,
        padding: `4px 10px 4px ${10 + depth * 12}px`,
        cursor: onClick ? "pointer" : "default",
        borderRadius: 4,
        transition: "background .15s",
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = "var(--panel, #0d1c2e)")
      }
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <span
        style={{
          position: "absolute",
          left: 10 + (depth - 1) * 12,
          width: 1,
          height: "100%",
          background: "var(--border, #1c3050)",
          opacity: 0.4,
        }}
      />
      <Dot status={status} size={6} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 11,
            color: "var(--text2, #b0c4d8)",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {label}
        </div>
        {sub && (
          <div
            style={{
              fontSize: 9,
              color: "var(--text3, #5a7a9a)",
              marginTop: 1,
              lineHeight: 1.3,
            }}
          >
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Section header (collapsible) ──────────────────────────────────────────────
function Section({ id, label, status, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ position: "relative" }}>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px 6px 10px",
          cursor: "pointer",
          transition: "background .15s",
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.background = "rgba(255,255,255,.03)")
        }
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        <Dot status={status} size={7} />
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: ".1em",
            textTransform: "uppercase",
            color: "var(--text3, #5a7a9a)",
            flex: 1,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: 9,
            color: "var(--text3, #5a7a9a)",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform .2s",
            lineHeight: 1,
          }}
        >
          ›
        </span>
      </div>
      {open && (
        <div
          style={{
            borderLeft: "1px solid var(--border, #1c3050)",
            marginLeft: 16,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const f = (v, dp = 1, suffix = "") =>
  v != null && !Number.isNaN(Number(v))
    ? `${Number(v).toFixed(dp)}${suffix}`
    : "—";

function mergeStatus(...statuses) {
  if (statuses.includes("fail")) return "fail";
  if (statuses.includes("warn")) return "warn";
  if (statuses.every((s) => s === "none")) return "none";
  return "ok";
}

// ── Main component ────────────────────────────────────────────────────────────
export default function EquipmentTree({ results, inputs, onNodeClick }) {
  const r = results || {};
  const inp = inputs || {};
  const checks = r.checks || [];

  // ── Live status per subsystem ─────────────────────────────────────────────
  const s_capacity = nodeStatus(checks, ["capacity", "Capacity"]);
  const s_speed = nodeStatus(checks, ["speed", "Speed"]);
  const s_cr = nodeStatus(checks, ["CR=", "centrifugal", "scatter"]);

  // FIX 6: added chain sf / chain speed / sprocket to slip keywords
  const s_slip = nodeStatus(checks, [
    "slip",
    "Slip",
    "euler",
    "Euler",
    "chain sf",
    "chain speed",
    "chain working",
    "sprocket",
  ]);

  const s_shaft = nodeStatus(checks, ["shaft", "Shaft", "governed by"]);
  const s_key = nodeStatus(checks, ["keyway", "Keyway", "key"]);
  const s_bearing = nodeStatus(checks, ["bearing", "Bearing", "L10"]);
  const s_lagging = nodeStatus(checks, ["lagging", "Lagging"]);
  const s_end_disc = nodeStatus(checks, ["end disc", "End disc"]);
  const s_motor = nodeStatus(checks, ["motor", "Motor", "kW", "Ceff"]);
  const s_belt = nodeStatus(checks, ["belt", "Belt", "PLY", "headshaft"]);
  const s_bolt = nodeStatus(checks, ["bolt", "Bolt", "fatigue", "Goodman"]);
  const s_takeup = nodeStatus(checks, [
    "take-up",
    "Take-up",
    "takeup",
    "counterweight",
  ]);
  const s_casing = nodeStatus(checks, [
    "casing",
    "Casing",
    "panel",
    "stiffener",
  ]);
  const s_chute = nodeStatus(checks, [
    "chute",
    "Chute",
    "discharge",
    "plugging",
    "dust",
  ]);
  const s_atex = nodeStatus(checks, [
    "ATEX",
    "atex",
    "explosive",
    "dust control",
    "stainless",
  ]);
  const s_abr = nodeStatus(checks, ["abrasion", "AR400", "AR500", "liner"]);

  // Aggregate section statuses
  const st_process = mergeStatus(
    s_capacity.status,
    s_speed.status,
    s_cr.status,
  );
  const st_head = mergeStatus(
    s_shaft.status,
    s_key.status,
    s_bearing.status,
    s_lagging.status,
    s_end_disc.status,
  );
  const st_drive = s_motor.status;
  const st_belt = mergeStatus(s_belt.status, s_slip.status, s_bolt.status);
  const st_takeup = s_takeup.status;
  const st_chute = s_chute.status;
  const st_casing = mergeStatus(s_casing.status, s_abr.status);
  const st_mech = mergeStatus(st_head, st_drive, st_belt, st_takeup, st_casing);

  // ── Value shortcuts ────────────────────────────────────────────────────────
  const bkt = r.bucket || {};
  const mat = r.mat || r.material || {};
  const hub = r.hub || {};
  const lag = r.lagging || {};
  const tg = r.takeup_gravity || {};
  const ts = r.takeup_screw || {};
  const dc = r.discharge_chute || {};
  const dcperf = dc.performance || {};
  const dcmnt = dc.maintenance || {};
  const fd = r.feed_design || null;
  const chain = r.chain_selected || {};
  const sprocket = r.sprocket || {};

  // FIX 1: depth field — new BUCKET_SERIES uses depth_mm; old used H
  const bkt_depth = bkt.depth_mm ?? bkt.H;
  // FIX 5: takeup screw core diameter field name changed
  const screw_d = ts.d_core_recommend_mm ?? ts.d_core_min_mm;

  // FIX 3 / FIX 8: feed design section status from real data
  const st_feed = fd ? (fd.warnings?.length ? "warn" : "ok") : "none";

  // Chain SF status
  const chain_sf_status =
    r.chain_SF_actual >= 6.0
      ? "ok"
      : r.chain_SF_actual >= 5.0
        ? "warn"
        : r.chain_SF_actual > 0
          ? "fail"
          : "none";

  const warnCount = checks.filter((c) => c.type === "warn").length;
  const failCount = checks.filter((c) => c.type === "fail").length;
  const okCount = checks.filter((c) => c.type === "ok").length;

  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
        overflowX: "hidden",
        fontSize: 12,
        userSelect: "none",
      }}
    >
      {/* ── Equipment header ─────────────────────────────────────────────── */}
      <div
        style={{
          padding: "10px 12px 8px",
          borderBottom: "1px solid var(--border, #1c3050)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 5,
          }}
        >
          <span style={{ fontSize: 16, color: "var(--primary, #4a9eff)" }}>
            ⛏
          </span>
          <div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: "var(--text, #ddeaf6)",
              }}
            >
              Bucket Elevator
            </div>
            <div
              style={{
                fontSize: 10,
                color: "var(--text3)",
                letterSpacing: ".04em",
              }}
            >
              VECTOMEC™ BE-001
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {failCount > 0 && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 999,
                background: "var(--danger-dim, #1a0808)",
                color: "var(--danger)",
                border: "1px solid var(--danger-border, #4a1515)",
              }}
            >
              {failCount} FAIL
            </span>
          )}
          {warnCount > 0 && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 999,
                background: "var(--warning-dim, #1a1205)",
                color: "var(--warning)",
                border: "1px solid var(--warning-border, #4a3005)",
              }}
            >
              {warnCount} WARN
            </span>
          )}
          {failCount === 0 && warnCount === 0 && okCount > 0 && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 999,
                background: "var(--success-dim, #081a10)",
                color: "var(--success)",
                border: "1px solid var(--success-border, #1a4a28)",
              }}
            >
              {okCount} OK
            </span>
          )}
        </div>
      </div>

      {/* ── PROCESS ──────────────────────────────────────────────────────── */}
      <Section id="process" label="Process" status={st_process}>
        <Leaf
          label="Material"
          sub={`${mat.name || inp.mat_id || "—"}  ρ=${f(r.rho, 0)} kg/m³`}
          status="none"
          depth={2}
        />
        <Leaf
          label="Capacity"
          sub={`${f(r.Q ?? r.Q_th, 1)} t/h  req ${inp.Q_req ?? "—"} t/h`}
          status={s_capacity.status}
          onClick={() => onNodeClick?.("process")}
          depth={2}
        />
        <Leaf
          label="Belt Speed"
          sub={`${f(r.v ?? r.v_ms, 2)} m/s`}
          status={s_speed.status}
          onClick={() => onNodeClick?.("process")}
          depth={2}
        />
        <Leaf
          label="Centrifugal Ratio"
          sub={`CR = ${f(r.cr ?? r.centrifugal_ratio, 3)}`}
          status={s_cr.status}
          onClick={() => onNodeClick?.("process")}
          depth={2}
        />
      </Section>

      {/* ── MECHANICAL DESIGN ────────────────────────────────────────────── */}
      <Section
        id="mechanical"
        label="Mechanical Design"
        status={st_mech}
        defaultOpen
      >
        {/* Head Assembly */}
        <Section id="head" label="Head Assembly" status={st_head} defaultOpen>
          <Leaf
            label="Head Pulley"
            sub={`Ø${inp.D_mm ?? "—"}mm  ${inp.n_rpm ?? "—"} rpm`}
            status="none"
            depth={3}
          />
          <Leaf
            label="Head Shaft"
            sub={`Ø${f(r.d_mm, 1)}mm  ${r.shaft_material ?? "A36"}  ${r.governed_by ?? "—"}`}
            status={s_shaft.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
          <Leaf
            label="Hub & Key"
            sub={
              hub.d_hub_mm
                ? `Hub Ø${f(hub.d_hub_mm, 1)}mm  key ${hub.b_key_mm}×${hub.h_key_mm}mm`
                : "—"
            }
            status={s_key.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
          <Leaf
            label="Bearings"
            sub={`L10 ${r.L10 != null ? Number(r.L10).toLocaleString() : "—"} h`}
            status={s_bearing.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
          <Leaf
            label="Lagging"
            sub={
              lag.lagging_type
                ? `${lag.lagging_type.replace(/_/g, " ")}  μ=${f(lag.mu_operating, 2)}`
                : "—"
            }
            status={s_lagging.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
          <Leaf
            label="End Disc"
            sub={
              r.end_disc?.t_governing_mm
                ? `min t=${f(r.end_disc.t_governing_mm, 1)}mm`
                : "—"
            }
            status={s_end_disc.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
        </Section>

        {/* Belt / Chain Selection */}
        <Section
          id="belt_sel"
          label={r.is_chain ? "Chain Selection" : "Belt Selection"}
          status={st_belt}
        >
          {r.is_chain ? (
            /* FIX 7: Chain elevator — show chain nodes instead of belt/slip */
            <>
              <Leaf
                label="Chain Series"
                sub={
                  chain.name
                    ? `${chain.name}  pitch ${f(chain.pitch_mm, 0)}mm  ${chain.n_strands ?? "—"} strand`
                    : "—"
                }
                status={chain_sf_status}
                onClick={() => onNodeClick?.("mechanical")}
                depth={3}
              />
              <Leaf
                label="Chain Working Load"
                sub={
                  r.chain_SF_actual != null
                    ? `SF=${f(r.chain_SF_actual, 2)}  Pull=${f((r.chain_pull_N ?? 0) / 1000, 1)}kN`
                    : "—"
                }
                status={chain_sf_status}
                onClick={() => onNodeClick?.("mechanical")}
                depth={3}
              />
              <Leaf
                label="Chain Speed"
                sub={`${f(r.v ?? r.v_ms, 2)} m/s  max ${f(chain.v_max_ms, 2)} m/s`}
                status={
                  r.chain_v_ok === false ? "fail" : r.chain_v_ok ? "ok" : "none"
                }
                onClick={() => onNodeClick?.("mechanical")}
                depth={3}
              />
              <Leaf
                label="Sprocket"
                sub={
                  sprocket.n_teeth
                    ? `${sprocket.n_teeth}T  PD=${f(sprocket.PD_mm, 0)}mm`
                    : "—"
                }
                status={
                  sprocket.smooth === false
                    ? "warn"
                    : sprocket.smooth
                      ? "ok"
                      : "none"
                }
                depth={3}
              />
            </>
          ) : (
            /* Belt elevator — show belt class and Euler slip */
            <>
              <Leaf
                label="Belt"
                sub={`${r.belt_class ?? (r.belt_ply ? r.belt_ply + " PLY" : "—")}  ${r.belt_w ?? r.belt_width_mm ?? "—"}mm`}
                status={s_belt.status}
                onClick={() => onNodeClick?.("mechanical")}
                depth={3}
              />
              {/* FIX 4: belt slip branch — only shown for belt mode */}
              <Leaf
                label="Belt Slip"
                sub={
                  r.euler_ratio != null
                    ? `e^μθ=${f(r.euler_ratio, 3)}  ${r.slip_safe ? "✓ Safe" : "✗ Risk"}`
                    : "—"
                }
                status={s_slip.status}
                onClick={() => onNodeClick?.("mechanical")}
                depth={3}
              />
            </>
          )}
        </Section>

        {/* Bucket Selection */}
        <Section
          id="bucket_sel"
          label="Bucket Selection"
          status={s_bolt.status !== "none" ? s_bolt.status : "none"}
        >
          {/* FIX 1: bkt.depth_mm ?? bkt.H */}
          <Leaf
            label="Bucket Series"
            sub={
              bkt.id
                ? `${bkt.id}  ${bkt.W ?? bkt.width_mm ?? "—"}×${bkt_depth ?? "—"}mm  ${bkt.V ?? bkt.volume_L ?? "—"}L`
                : "—"
            }
            status="none"
            depth={3}
          />
          <Leaf
            label="Bolt Fatigue"
            sub={
              r.bolt_fatigue?.goodman_ratio != null
                ? `Goodman ${f(r.bolt_fatigue.goodman_ratio, 3)}`
                : "—"
            }
            status={s_bolt.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
        </Section>

        {/* Take-Up */}
        <Section id="takeup_sel" label="Take-Up Selection" status={st_takeup}>
          <Leaf
            label="Gravity Take-Up"
            sub={
              tg.W_counterweight_kg_gross
                ? `${f(tg.W_counterweight_kg_gross, 0)} kg  travel ${f((tg.travel_m ?? 0) * 1000, 0)} mm`
                : "—"
            }
            status={s_takeup.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
          {/* FIX 5: d_core field name — use recommend, fall back to min */}
          <Leaf
            label="Screw Alternative"
            sub={
              screw_d
                ? `d_core ${f(screw_d, 1)}mm  SF ${f(ts.SF_buckling, 2)}`
                : "—"
            }
            status={ts.buckling_safe === false ? "warn" : "none"}
            depth={3}
          />
        </Section>

        {/* Discharge Section */}
        <Section id="discharge_sec" label="Discharge Section" status={st_chute}>
          <Leaf
            label="Type"
            sub={
              r.is_continuous
                ? `HF Continuous  CR=${f(r.cr, 3)}`
                : `Centrifugal  CR=${f(r.cr, 3)}`
            }
            status="none"
            depth={3}
          />
          <Leaf
            label="Chute"
            sub={
              dcperf.chute_angle_deg
                ? `${f(dcperf.chute_angle_deg, 1)}°  ${dcperf.flow_regime?.replace(/_/g, " ") ?? "—"}`
                : "—"
            }
            status={s_chute.status}
            onClick={() => onNodeClick?.("chute")}
            depth={3}
          />
          <Leaf
            label="Liner"
            sub={
              dcmnt.liner_material
                ? `${dcmnt.liner_material}  ${dcmnt.liner_thickness_mm ?? "—"}mm`
                : "—"
            }
            status="none"
            depth={3}
          />
        </Section>

        {/* FIX 3: Feed Design — real data, no more stub */}
        <Section id="feed_sec" label="Feed Design" status={st_feed}>
          <Leaf
            label="Boot Pulley"
            sub={`Ø${inp.boot_pulley_D_mm ?? inp.D_mm ?? "—"}mm  Take-up point`}
            status="none"
            depth={3}
          />
          {/* FIX 2: surge volume from r.feed_design, not nonexistent r.boot_vol_min_m3 */}
          <Leaf
            label="Boot Surge Volume"
            sub={
              fd
                ? `${fd.V_surge_litres ?? "—"}L  (${fd.t_surge_s ?? 3}s buffer)`
                : "—"
            }
            status="none"
            depth={3}
          />
          <Leaf
            label="Inlet Geometry"
            sub={
              fd
                ? `${fd.inlet_width_mm ?? "—"}×${fd.inlet_height_mm ?? "—"}mm  v=${f(fd.v_feed_mps, 2)}m/s`
                : "No data — run calculation"
            }
            status={fd ? "ok" : "none"}
            depth={3}
          />
          <Leaf
            label="Loading Method"
            sub={fd ? fd.loading_type : "—"}
            status={fd ? (fd.warnings?.length ? "warn" : "ok") : "none"}
            depth={3}
          />
          {/* Boot casing minimum height */}
          <Leaf
            label="Boot Casing Height"
            sub={
              fd
                ? `min ${fd.boot_casing_height_mm ?? "—"}mm below pulley CL`
                : "—"
            }
            status="none"
            depth={3}
          />
        </Section>

        {/* Casing Design */}
        <Section id="casing_sec" label="Casing Design" status={st_casing}>
          <Leaf
            label="Casing Panel"
            sub={
              r.casing_panel
                ? `δ=${f(r.casing_panel.delta_actual_mm, 1)}mm  t=${f(r.casing_panel.t_use_mm, 0)}mm`
                : "—"
            }
            status={st_casing}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
          <Leaf
            label="Drive"
            sub={`${r.motor_kw ?? r.motor_kW ?? "—"} kW  SF ${inp.sf ?? "—"}`}
            status={s_motor.status}
            onClick={() => onNodeClick?.("mechanical")}
            depth={3}
          />
        </Section>
      </Section>

      {/* ── SERVICE CONDITIONS ───────────────────────────────────────────── */}
      <Section
        id="service"
        label="Service Conditions"
        status={s_atex.status !== "none" ? s_atex.status : "none"}
      >
        <Leaf
          label="Environment"
          sub={`${inp.environment ?? "dry"}  μ=${inp.mu ?? "—"}`}
          status="none"
          depth={2}
        />
        {s_atex.status !== "none" && (
          <Leaf
            label="Hazard Flags"
            sub="ATEX / dust control"
            status={s_atex.status}
            onClick={() => onNodeClick?.("casing")}
            depth={2}
          />
        )}
        {s_abr.status !== "none" && (
          <Leaf
            label="Abrasion Rating"
            sub={`Class ${mat.abr_code ?? "—"}/7`}
            status={s_abr.status}
            depth={2}
          />
        )}
      </Section>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <div
        style={{
          padding: "8px 12px",
          fontSize: 10,
          color: "var(--text3)",
          letterSpacing: ".04em",
          borderTop: "1px solid var(--border)",
          marginTop: 4,
        }}
      >
        CEMA 375-2017 · ISO 281 · ASME B17.1
      </div>
    </div>
  );
}
