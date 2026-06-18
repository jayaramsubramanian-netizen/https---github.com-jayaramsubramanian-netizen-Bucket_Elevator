// BomPanel.jsx
// Pure display component — renders the BOM already computed by the backend's
// generate_bom() via solve_elevator(). No mass estimates, no geometry, no
// physics are recomputed here.
//
// Backend exposes the full BOM as results.bom:
//   {
//     items:   [{ pos, tag, category, description, qty, unit, spec,
//                 mass_ea_kg, mass_tot_kg, notes }],
//     summary: { total_items, total_mass_kg, by_category },
//     notes:   [string],
//     version: "1.9.9",
//   }

import { useState } from "react";

const f = (v, d = 1, fb = "—") =>
  v != null && !Number.isNaN(Number(v)) ? Number(v).toFixed(d) : fb;

function kgToT(kg) {
  if (kg == null) return "—";
  return kg >= 1000 ? `${(kg / 1000).toFixed(2)} t` : `${Number(kg).toFixed(0)} kg`;
}

// ── Category badge ─────────────────────────────────────────────────────────────
const CAT_STYLE = {
  SHAFT:     { bg: "rgba(167,139,250,.1)", color: "#a78bfa", border: "rgba(167,139,250,.25)" },
  PULLEY:    { bg: "rgba(59,130,246,.1)",  color: "#3b82f6", border: "rgba(59,130,246,.25)"  },
  BELT:      { bg: "rgba(245,158,11,.1)",  color: "#f59e0b", border: "rgba(245,158,11,.25)"  },
  DRIVE:     { bg: "rgba(16,185,129,.1)",  color: "#10b981", border: "rgba(16,185,129,.25)"  },
  "TAKE-UP": { bg: "rgba(20,184,166,.1)",  color: "#14b8a6", border: "rgba(20,184,166,.25)"  },
  CASING:    { bg: "rgba(100,116,139,.1)", color: "#94a3b8", border: "rgba(100,116,139,.25)" },
  BEARINGS:  { bg: "rgba(59,130,246,.1)",  color: "#60a5fa", border: "rgba(59,130,246,.25)"  },
  FASTENERS: { bg: "rgba(100,116,139,.1)", color: "#94a3b8", border: "rgba(100,116,139,.25)" },
  CHUTE:     { bg: "rgba(239,68,68,.1)",   color: "#ef4444", border: "rgba(239,68,68,.25)"   },
};

function CatBadge({ cat }) {
  const s = CAT_STYLE[cat] || CAT_STYLE.CASING;
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, letterSpacing: ".05em",
      textTransform: "uppercase", padding: "1px 5px",
      borderRadius: "var(--r-pill)",
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>{cat}</span>
  );
}

// ── CSV export ─────────────────────────────────────────────────────────────────
function exportCSV(items) {
  const rows = [["Pos","Tag","Category","Description","Qty","Unit","Spec","Mass ea (kg)","Mass tot (kg)","Notes"]];
  for (const item of items) {
    rows.push([
      item.pos, item.tag, item.category, item.description,
      item.qty, item.unit, item.spec,
      f(item.mass_ea_kg, 1), f(item.mass_tot_kg, 1),
      item.notes,
    ]);
  }
  const csv = rows.map(r => r.map(c => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "VECTOMEC_BOM.csv"; a.click();
  URL.revokeObjectURL(url);
}

// ── Group items by category for collapsible display ───────────────────────────
function groupItems(items) {
  const order = ["SHAFT","PULLEY","BELT","DRIVE","TAKE-UP","CASING","FASTENERS","BEARINGS","CHUTE"];
  const map = {};
  for (const item of items) {
    if (!map[item.category]) map[item.category] = [];
    map[item.category].push(item);
  }
  // Sort groups by defined order, then alphabetically for any unexpected categories
  return Object.entries(map).sort(([a], [b]) => {
    const ia = order.indexOf(a), ib = order.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function BomPanel({ results }) {
  const bom = results?.bom;

  const [expandedGroups, setExpandedGroups] = useState(
    ["SHAFT","PULLEY","BELT","DRIVE","TAKE-UP","CASING","FASTENERS","BEARINGS","CHUTE"]
  );

  if (!bom?.items?.length) return (
    <div style={{ padding: 20, color: "var(--muted)", fontSize: 12, textAlign: "center" }}>
      {results ? "BOM not available — ensure backend v1.9.9+" : "Calculating…"}
    </div>
  );

  const groups = groupItems(bom.items);
  const toggleGroup = (name) =>
    setExpandedGroups(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );

  return (
    <div style={{ display: "flex", flexDirection: "column", paddingBottom: 16 }}>

      {/* Header */}
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
            {bom.summary.total_items} line items · est. {kgToT(bom.summary.total_mass_kg)} steel
          </span>
          <span style={{ fontSize: 8, color: "var(--faint)", marginLeft: 6 }}>
            v{bom.version}
          </span>
        </div>
        <button
          onClick={() => exportCSV(bom.items)}
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

      {/* Groups */}
      {groups.map(([cat, items]) => {
        const open = expandedGroups.includes(cat);
        const groupMass = bom.summary.by_category[cat]?.mass_kg ?? 0;

        return (
          <div key={cat}>
            {/* Group header */}
            <div
              onClick={() => toggleGroup(cat)}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "7px 12px", background: "var(--panel2)",
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
                <CatBadge cat={cat} />
                <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text2)",
                  letterSpacing: ".02em" }}>{cat}</span>
                <span style={{ fontSize: 9, color: "var(--muted)" }}>
                  {items.length} items
                </span>
              </div>
              <span style={{ fontSize: 9, color: "var(--muted)",
                fontFamily: "JetBrains Mono, monospace" }}>
                {kgToT(groupMass)}
              </span>
            </div>

            {/* Item rows */}
            {open && items.map((item, i) => (
              <div key={item.pos} style={{
                padding: "7px 12px 5px",
                borderBottom: "1px solid var(--border)",
                background: i % 2 === 0 ? "var(--panel)" : "transparent",
              }}>
                {/* Line 1: qty × tag + desc */}
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, color: "var(--primary)",
                    fontFamily: "JetBrains Mono, monospace", minWidth: 28,
                  }}>{item.qty}×</span>
                  <span style={{
                    fontSize: 9, color: "var(--muted)",
                    fontFamily: "JetBrains Mono, monospace", minWidth: 52,
                  }}>{item.tag}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text)", flex: 1 }}>
                    {item.description}
                  </span>
                  <span style={{ fontSize: 9, color: "var(--muted)" }}>{item.unit}</span>
                </div>
                {/* Line 2: spec */}
                <div style={{
                  fontSize: 10, color: "var(--text3)",
                  fontFamily: "JetBrains Mono, monospace",
                  paddingLeft: 80, lineHeight: 1.5,
                }}>{item.spec}</div>
                {/* Line 3: notes + mass */}
                <div style={{
                  display: "flex", justifyContent: "space-between",
                  paddingLeft: 80, marginTop: 2,
                }}>
                  <span style={{ fontSize: 9, color: "var(--muted)", flex: 1 }}>
                    {item.notes}
                  </span>
                  <span style={{
                    fontSize: 9, color: "var(--muted)",
                    fontFamily: "JetBrains Mono, monospace",
                  }}>
                    {kgToT(item.mass_tot_kg)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {/* BOM notes */}
      {bom.notes?.length > 0 && (
        <div style={{ padding: "10px 12px", borderTop: "1px solid var(--border)" }}>
          {bom.notes.map((note, i) => (
            <div key={i} style={{ fontSize: 9, color: "var(--muted)", lineHeight: 1.6 }}>
              · {note}
            </div>
          ))}
        </div>
      )}

      {/* Footer total */}
      <div style={{
        padding: "10px 12px", borderTop: "2px solid var(--border)",
        background: "var(--panel2)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span style={{ fontSize: 10, color: "var(--muted)" }}>
          Estimated total mass (±25% preliminary)
        </span>
        <span style={{
          fontSize: 12, fontWeight: 700, color: "var(--text)",
          fontFamily: "JetBrains Mono, monospace",
        }}>{kgToT(bom.summary.total_mass_kg)}</span>
      </div>
    </div>
  );
}