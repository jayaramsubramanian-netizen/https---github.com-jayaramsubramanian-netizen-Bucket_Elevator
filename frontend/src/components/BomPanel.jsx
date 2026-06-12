// BomPanel.jsx — Task 10: Auto-generated Bill of Materials
//
// Generates a BOM from design results and inputs.
// Line items cover every physical component of the elevator:
//   Head assembly, Boot assembly, Belt, Buckets, Drive, Structure, Fasteners.
//
// Each line: Qty | Tag | Description | Key Spec | Unit | Mass(est.)
// Footer: total estimated steel mass, export to CSV button.

import { useState } from "react";

// ── Helpers ───────────────────────────────────────────────────────────────────

const f = (v, d = 1, sfx = "") =>
  v != null && !Number.isNaN(Number(v)) ? `${Number(v).toFixed(d)}${sfx}` : "—";

function kgToT(kg) {
  return kg >= 1000 ? `${(kg / 1000).toFixed(2)} t` : `${kg.toFixed(0)} kg`;
}

// ── BOM generation ─────────────────────────────────────────────────────────────

function buildBom(results, inputs) {
  if (!results || !results.bucket) return [];

  const H      = inputs.H_m ?? 25;
  const D_mm   = inputs.D_mm ?? 500;
  const D_boot = inputs.boot_pulley_D_mm ?? 300;
  const bw     = results.belt_w ?? 254;
  const bucket = results.bucket;
  const spacing_m = results.spacing ?? 0.2;
  const d_shaft   = results.d_mm ?? 60;
  const motor_kw  = results.motor_kw ?? 11;
  const P_total   = results.P_total ?? 0;

  // Bucket count: both runs (carry + return) × height / spacing
  const n_buckets = Math.ceil((H * 2) / spacing_m);
  // Bolts: 4 per bucket (2×M12 typical)
  const n_bolts   = n_buckets * 4;
  // Belt length: 2 × H + pulley circumference allowance
  const belt_len_m = Math.ceil(2 * H + Math.PI * D_mm / 1000 + Math.PI * D_boot / 1000 + 2);

  // Steel density for mass estimates (kg/m³)
  const RHO = 7850;

  // Head pulley mass estimate: hollow cylinder
  const d_head_m  = D_mm / 1000;
  const t_shell   = d_head_m / 100 + 0.006;  // CEMA pulley shell formula
  const L_pulley  = bw / 1000 + 0.10;        // belt + 100mm end clearance
  const m_head    = Math.PI * d_head_m * L_pulley * t_shell * RHO;

  // Boot pulley mass estimate
  const d_boot_m  = D_boot / 1000;
  const m_boot    = Math.PI * d_boot_m * L_pulley * (d_boot_m / 100 + 0.004) * RHO;

  // Shaft mass estimate: solid cylinder, 600mm span
  const r_shaft   = (d_shaft / 2) / 1000;
  const m_shaft   = Math.PI * r_shaft ** 2 * 0.6 * RHO;

  // Belt mass: ~1.5 kg/m²
  const m_belt    = belt_len_m * (bw / 1000) * 1.5;

  // Bucket mass: ~1.5 kg/L of struck capacity (steel bucket)
  const m_bucket  = bucket.V * 1.5;
  const m_buckets_total = n_buckets * m_bucket;

  // Casing: simplified — perimeter × H × t_casing × RHO
  const casing_w  = bw + 200;   // mm, outside width
  const t_casing  = bw <= 200 ? 0.003 : bw <= 450 ? 0.005 : 0.008;
  const perimeter = 2 * (casing_w / 1000 + 0.4);  // 400mm depth typical
  const m_casing  = perimeter * H * t_casing * RHO;

  // Gearbox ratio
  const gear_ratio = Math.round(1450 / inputs.n_rpm);

  return [
    // ── HEAD ASSEMBLY ──────────────────────────────────────────────────
    {
      group: "Head Assembly",
      items: [
        {
          qty: 1, tag: "HP-01", cat: "rotating",
          desc: "Head Pulley — crowned, lagged",
          spec: `Ø${D_mm}mm × ${bw + 100}mm  ·  ${f(t_shell * 1000, 0)}mm shell`,
          unit: "EA", mass_kg: m_head,
          note: "CEMA Pulley Standard; specify crown 1mm/300mm BW",
        },
        {
          qty: 1, tag: "HS-01", cat: "structural",
          desc: "Head Shaft — ASTM A36",
          spec: `Ø${f(d_shaft, 0)}mm governed by ${results.governed_by ?? "stress"}`,
          unit: "EA", mass_kg: m_shaft,
          note: "CEMA 375 §4 DE-Goodman + deflection",
        },
        {
          qty: 2, tag: "BRG-01", cat: "rotating",
          desc: "Pillow Block Bearing — heavy duty",
          spec: `C=355kN  ·  L10=${results.L10 > 9999
            ? (results.L10 / 1000).toFixed(0) + "k" : f(results.L10, 0)} h`,
          unit: "EA", mass_kg: 12,
          note: "ISO 281; verify bore to match shaft dia.",
        },
        {
          qty: 1, tag: "DIS-01", cat: "structural",
          desc: "Discharge Spout Assembly",
          spec: `${bw + 100}mm wide  ·  AR400 liner`,
          unit: "EA", mass_kg: 25,
          note: "CEMA 375 §5",
        },
      ],
    },

    // ── BOOT ASSEMBLY ──────────────────────────────────────────────────
    {
      group: "Boot Assembly",
      items: [
        {
          qty: 1, tag: "BP-01", cat: "rotating",
          desc: "Boot (Tail) Pulley",
          spec: `Ø${D_boot}mm × ${bw + 100}mm`,
          unit: "EA", mass_kg: m_boot,
          note: "Self-cleaning wing design recommended for abrasives",
        },
        {
          qty: 2, tag: "BRG-02", cat: "rotating",
          desc: "Boot Bearing — take-up type",
          spec: `Gravity take-up  ·  K=${inputs.K_takeup ?? 0.7}`,
          unit: "EA", mass_kg: 8,
          note: "Slide rail ≥ 300mm travel per CEMA 375",
        },
        {
          qty: 1, tag: "FIN-01", cat: "structural",
          desc: "Feed Inlet Hopper",
          spec: `${bw + 100}mm wide  ·  5mm plate`,
          unit: "EA", mass_kg: 18,
          note: "Inlet velocity ≤ 1.5 m/s — check ChuteFlow",
        },
      ],
    },

    // ── BELT & BUCKETS ─────────────────────────────────────────────────
    {
      group: "Belt & Buckets",
      items: [
        {
          qty: 1, tag: "BLT-01", cat: "wear",
          desc: `Elevator Belt — ${results.belt_ply ?? "est. 3"} ply`,
          spec: `${bw}mm wide × ${belt_len_m}m  ·  EP rubber  ·  ${f(results.F_eff != null ? results.F_eff / 1000 : null, 1)}kN F_eff`,
          unit: "M", mass_kg: m_belt,
          note: `Verify PIW rating ≥ ${f(results.F_eff != null ? results.F_eff / bw * 25.4 : null, 0)} PIW`,
        },
        {
          qty: n_buckets, tag: "BKT-01", cat: "wear",
          desc: `Bucket — CEMA Series ${bucket.id}`,
          spec: `${bucket.W}×${bucket.H}mm  ·  ${bucket.V}L  ·  P=${bucket.P}mm  ·  s=${f(spacing_m * 1000, 0)}mm`,
          unit: "EA", mass_kg: m_bucket,
          note: `Total mass both runs: ${kgToT(m_buckets_total)}`,
        },
        {
          qty: n_bolts, tag: "FAS-01", cat: "fastener",
          desc: "Bucket Bolt Set — M12 gr8.8 + nyloc nut",
          spec: "M12 × 35mm hex head · hot-dip galvanised",
          unit: "EA", mass_kg: 0.08,
          note: "CEMA 375 §7 fatigue check required for abrasive materials",
        },
      ],
    },

    // ── DRIVE ──────────────────────────────────────────────────────────
    {
      group: "Drive System",
      items: [
        {
          qty: 1, tag: "MTR-01", cat: "electrical",
          desc: `Electric Motor — ${motor_kw}kW`,
          spec: `${motor_kw}kW  ·  1450rpm  ·  4-pole  ·  IE3  ·  SF=${inputs.sf}`,
          unit: "EA", mass_kg: motor_kw * 8,
          note: `Design power: ${f(P_total * inputs.sf, 2)}kW; motor reserve ${f(
            motor_kw > 0 && P_total > 0
              ? ((motor_kw - P_total * inputs.sf) / (P_total * inputs.sf)) * 100
              : null, 1)}%`,
        },
        {
          qty: 1, tag: "GBX-01", cat: "mechanical",
          desc: "Helical Shaft-Mounted Gearbox",
          spec: `i≈${gear_ratio}:1  ·  T_out≥${f(results.T_Nm != null ? results.T_Nm / 1000 * inputs.sf : null, 2)}kNm  ·  ${inputs.n_rpm}rpm output`,
          unit: "EA", mass_kg: motor_kw * 12,
          note: "Verify thermal rating for continuous duty",
        },
        {
          qty: 1, tag: "BST-01", cat: "mechanical",
          desc: "Backstop / Holdback Device",
          spec: `Torque ≥ ${f(results.T_Nm != null ? results.T_Nm / 1000 * 1.5 : null, 2)}kNm`,
          unit: "EA", mass_kg: motor_kw * 2,
          note: "Required on all inclined elevators — CEMA 375",
        },
      ],
    },

    // ── CASING & STRUCTURE ─────────────────────────────────────────────
    {
      group: "Casing & Structure",
      items: [
        {
          qty: 1, tag: "CSG-01", cat: "structural",
          desc: "Elevator Casing — boot to head",
          spec: `${casing_w}mm wide  ·  ${t_casing * 1000}mm plate  ·  H=${H}m`,
          unit: "LOT", mass_kg: m_casing,
          note: "Includes inspection doors, venting, access platforms",
        },
        {
          qty: 1, tag: "LEG-01", cat: "structural",
          desc: "Structural Legs / Support Frame",
          spec: `H=${H}m  ·  self-supporting or braced per site`,
          unit: "LOT", mass_kg: m_casing * 0.4,
          note: "Site-specific civil loads not included",
        },
        {
          qty: 1, tag: "TUP-01", cat: "mechanical",
          desc: "Take-up Frame Assembly",
          spec: "Gravity type  ·  ≥300mm travel",
          unit: "EA", mass_kg: 40,
          note: "Include counterweight guides and rope/chain if req.",
        },
      ],
    },
  ];
}

// ── Category badge ────────────────────────────────────────────────────────────

const CAT_STYLE = {
  rotating:   { bg: "rgba(59,130,246,.1)",   color: "#3b82f6", border: "rgba(59,130,246,.25)"  },
  structural: { bg: "rgba(167,139,250,.1)",  color: "#a78bfa", border: "rgba(167,139,250,.25)" },
  wear:       { bg: "rgba(245,158,11,.1)",   color: "#f59e0b", border: "rgba(245,158,11,.25)"  },
  fastener:   { bg: "rgba(100,116,139,.1)",  color: "#94a3b8", border: "rgba(100,116,139,.25)" },
  electrical: { bg: "rgba(16,185,129,.1)",   color: "#10b981", border: "rgba(16,185,129,.25)"  },
  mechanical: { bg: "rgba(20,184,166,.1)",   color: "#14b8a6", border: "rgba(20,184,166,.25)"  },
};

function CatBadge({ cat }) {
  const s = CAT_STYLE[cat] || CAT_STYLE.structural;
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, letterSpacing: ".05em",
      textTransform: "uppercase", padding: "1px 5px",
      borderRadius: "var(--r-pill)",
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>{cat}</span>
  );
}

// ── CSV export ────────────────────────────────────────────────────────────────

function exportCSV(groups) {
  const rows = [["Qty","Tag","Category","Description","Spec","Unit","Mass(kg)","Note"]];
  for (const g of groups) {
    rows.push([g.group, "", "", "", "", "", "", ""]);
    for (const item of g.items) {
      rows.push([
        item.qty, item.tag, item.cat,
        item.desc, item.spec, item.unit,
        item.mass_kg.toFixed(1), item.note,
      ]);
    }
  }
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "VECTOMEC_BOM.csv"; a.click();
  URL.revokeObjectURL(url);
}

// ── Main component ────────────────────────────────────────────────────────────

export default function BomPanel({ results, inputs }) {
  const [expandedGroups, setExpandedGroups] = useState(
    ["Head Assembly","Boot Assembly","Belt & Buckets","Drive System","Casing & Structure"]
  );

  const bom = buildBom(results, inputs);
  if (!bom.length) return (
    <div style={{ padding: 20, color: "var(--muted)", fontSize: 12, textAlign: "center" }}>
      Calculating BOM…
    </div>
  );

  // Totals
  const totalItems = bom.reduce((s, g) => s + g.items.length, 0);
  const totalMass  = bom.reduce((s, g) =>
    s + g.items.reduce((gs, i) => gs + i.mass_kg * i.qty, 0), 0);

  const toggleGroup = (name) =>
    setExpandedGroups(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );

  return (
    <div style={{ display: "flex", flexDirection: "column", paddingBottom: 16 }}>

      {/* BOM header + export */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px", borderBottom: "1px solid var(--border)",
        background: "var(--panel2)", flexShrink: 0,
      }}>
        <div>
          <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text3)",
            letterSpacing: ".08em", textTransform: "uppercase" }}>
            Bill of Materials
          </span>
          <span style={{ fontSize: 9, color: "var(--muted)", marginLeft: 8 }}>
            {totalItems} line items · est. {kgToT(totalMass)} steel
          </span>
        </div>
        <button
          onClick={() => exportCSV(bom)}
          style={{
            display: "flex", alignItems: "center", gap: 5,
            padding: "4px 10px", borderRadius: "var(--r-md)",
            border: "1px solid var(--border2)", background: "transparent",
            color: "var(--text3)", fontSize: 10, fontWeight: 600,
            cursor: "pointer", transition: "all var(--t-fast)",
          }}
          onMouseEnter={e => { e.currentTarget.style.background = "var(--surface)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
        >
          ⬇ CSV
        </button>
      </div>

      {/* BOM groups */}
      {bom.map((group) => {
        const open = expandedGroups.includes(group.name ?? group.group);
        const gName = group.group;
        const groupMass = group.items.reduce((s, i) => s + i.mass_kg * i.qty, 0);

        return (
          <div key={gName}>
            {/* Group header */}
            <div
              onClick={() => toggleGroup(gName)}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "7px 12px",
                background: "var(--panel2)",
                borderBottom: "1px solid var(--border)",
                cursor: "pointer", userSelect: "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{
                  fontSize: 8, color: "var(--faint)",
                  transform: open ? "rotate(90deg)" : "none",
                  display: "inline-block", transition: "transform .15s",
                }}>▶</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text2)",
                  letterSpacing: ".02em" }}>{gName}</span>
                <span style={{ fontSize: 9, color: "var(--muted)" }}>
                  {group.items.length} items
                </span>
              </div>
              <span style={{ fontSize: 9, color: "var(--muted)",
                fontFamily: "JetBrains Mono, monospace" }}>
                {kgToT(groupMass)}
              </span>
            </div>

            {/* Item rows */}
            {open && group.items.map((item, i) => (
              <div key={i} style={{
                padding: "7px 12px 5px",
                borderBottom: "1px solid var(--border)",
                background: i % 2 === 0 ? "var(--panel)" : "transparent",
              }}>
                {/* Line 1: qty + tag + category + desc */}
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, color: "var(--primary)",
                    fontFamily: "JetBrains Mono, monospace", minWidth: 28,
                  }}>{item.qty}×</span>
                  <span style={{
                    fontSize: 9, color: "var(--muted)",
                    fontFamily: "JetBrains Mono, monospace", minWidth: 52,
                  }}>{item.tag}</span>
                  <CatBadge cat={item.cat} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text)",
                    flex: 1 }}>{item.desc}</span>
                </div>
                {/* Line 2: spec */}
                <div style={{
                  fontSize: 10, color: "var(--text3)",
                  fontFamily: "JetBrains Mono, monospace",
                  paddingLeft: 80, lineHeight: 1.5,
                }}>{item.spec}</div>
                {/* Line 3: mass + note */}
                <div style={{
                  display: "flex", justifyContent: "space-between",
                  paddingLeft: 80, marginTop: 2,
                }}>
                  <span style={{ fontSize: 9, color: "var(--muted)", flex: 1 }}>
                    {item.note}
                  </span>
                  <span style={{
                    fontSize: 9, color: "var(--muted)",
                    fontFamily: "JetBrains Mono, monospace",
                  }}>
                    {kgToT(item.mass_kg * item.qty)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {/* Footer totals */}
      <div style={{
        padding: "10px 12px",
        borderTop: "2px solid var(--border)",
        background: "var(--panel2)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span style={{ fontSize: 10, color: "var(--muted)" }}>
          Estimated structural steel mass (excludes electrical, instruments)
        </span>
        <span style={{
          fontSize: 12, fontWeight: 700, color: "var(--text)",
          fontFamily: "JetBrains Mono, monospace",
        }}>{kgToT(totalMass)}</span>
      </div>
    </div>
  );
}
