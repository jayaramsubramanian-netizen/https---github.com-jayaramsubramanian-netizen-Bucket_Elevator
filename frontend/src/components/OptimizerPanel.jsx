// OptimizerPanel.jsx — multi-objective (NSGA-II) optimizer, Pareto front display
//
// ROUND 11 REWRITE — previously called the v1 brute-force grid-search
// endpoint (optimizeElevator), which scored candidates with a hardcoded
// CR threshold that actively contradicted the backend's own per-material
// CR preference (fix #9, this same file, an earlier round). That display
// bug was the SYMPTOM; the deeper problem Jay reported next (screenshot:
// wheat's top-ranked picks were all CR=1.369 centrifugal buckets, with HF
// -- wheat's own recommended style -- nowhere in the top 6) is in v1's
// OWN scoring/search itself, not just how this panel coloured one column.
// v2 (vectrix_optimizer_v2.py) was built specifically to fix this
// architecturally (material CR preference as a real search objective, not
// an afterthought) and was verified to solve it -- confirmed live,
// MF_12x8/HF_10x7 (wheat's actual preferred styles) rank at
// cr_deviation=0.000 in v2 for the identical scenario where v1's top 6
// were all wrong-discharge-type buckets. This rewrite switches the panel
// to v2 and changes the display from "ranked list by one weighted score"
// to "Pareto-efficient front across real objectives", which is what v2
// actually produces -- there is no single "best", so the UI shouldn't
// imply there is one.
import { useState, useCallback, useMemo } from "react";
import { optimizeElevatorV2 } from "../api/client";

const C = {
  hi: "#243247",
  border2: "#ffffff1e",
  muted: "#64748b",
  muted2: "#94a3b8",
  blue: "#3b82f6",
  green: "#10b981",
  amber: "#f59e0b",
  teal: "#14b8a6",
  red: "#ef4444",
  text: "#f1f5f9",
  accent: "#c8192e",
};

const SORT_OPTIONS = [
  { id: "cr_deviation", label: "CR Match (closest to material preference)" },
  { id: "motor_kw",     label: "Motor Power (lowest first)" },
  { id: "R_headshaft_N",label: "Structural Load (lowest first)" },
  { id: "L10_h",        label: "Bearing Life (longest first)" },
];

// Maps a v2 Pareto-front point into the field shape generate_report.py's
// build_variant_report() expects (rpm, bucket_id, fill, speed, capacity,
// power, motor_kw, T1_kN, cr, score, rank) -- written for v1 candidates,
// which had different field names and no D_mm/boot_pulley_D_mm/strands at
// all. `score`/`rank` have no real meaning for a Pareto front (there's no
// single objective to rank by) -- rank reflects the CURRENT on-screen sort
// order at export time, purely so the PDF's row numbering matches what was
// selected on screen; score is omitted.
function toVariantReportShape(p, rank) {
  return {
    rpm:       p.n_rpm,
    bucket_id: p.bucket_id,
    fill:      p.fill_pct,
    speed:     p.v_ms ?? 0,
    capacity:  p.Q_th ?? 0,
    power:     p.motor_kw,            // closest available analog
    motor_kw:  p.motor_kw,
    T1_kN:     Math.round((p.R_headshaft_N ?? 0) / 100) / 10,  // N -> kN
    cr:        p.cr ?? 0,
    rank,
    // Extra v2-specific fields included alongside -- harmless if the PDF
    // builder ignores unknown keys, useful if it's ever extended to show them.
    D_mm: p.D_mm, boot_pulley_D_mm: p.boot_pulley_D_mm,
    chain_n_strands: p.chain_n_strands, cr_deviation: p.cr_deviation,
    L10_h: p.L10_h,
  };
}

async function downloadVariantReport(candidates, inputs) {
  const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
  try {
    const res = await fetch(`${BASE}/bucket-elevator/report-variants`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidates, inputs }),
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "elevator_variants.pdf";
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Variant report failed: ${e.message}`);
  }
}

// cr_deviation is already the real, material-aware distance from the
// preferred CR range -- no need to recompute anything in the frontend
// (that recomputation was exactly fix #9's bug). Graduated colour band
// across cr_deviation's own scale (0 = exactly on target).
function crDevColor(dev) {
  if (dev >= 0.5) return C.red;
  if (dev >= 0.1) return C.amber;
  return C.teal;
}

export default function OptimizerPanel({ inputs, onApply }) {
  const [sortBy, setSortBy] = useState("cr_deviation");
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set()); // indices into sortedFront

  const runOptimizer = useCallback(async () => {
    setRunning(true);
    setError(null);
    setSelected(new Set());
    try {
      const data = await optimizeElevatorV2(inputs);
      setResults(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }, [inputs]);

  const sortedFront = useMemo(() => {
    const front = results?.pareto_front ?? [];
    const dir = sortBy === "L10_h" ? -1 : 1;   // longer life first, everything else ascending
    return [...front].sort((a, b) => dir * ((a[sortBy] ?? 0) - (b[sortBy] ?? 0)));
  }, [results, sortBy]);

  const toggleSelect = (i) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  const isChainRun = (inputs.conveyor_type ?? "belt") === "chain";
  const top = sortedFront[0];
  const pinned = sortedFront.filter((_, i) => selected.has(i));
  const pinnedNone = pinned.length === 0;
  const pref = results?.material_preference;

  return (
    <div
      style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}
    >
      <div style={{ fontSize: 11, color: C.muted }}>
        Multi-objective (NSGA-II) optimizer searches RPM × Bucket × Fill × Head
        &amp; Boot Pulley Diameter{isChainRun ? " × Chain Strands" : ""} space
        subject to Q ≥ <span style={{ color: C.text }}>{inputs.Q_req}</span>{" "}
        t/h, CEMA speed limits, and a 20,000h bearing-life floor. Returns a
        genuine Pareto-efficient front — every row below is a real trade-off,
        not a single "best" answer. Select one or more rows to apply or
        export as a comparison report.
      </div>

      <button
        className="btn-primary"
        style={{ margin: 0 }}
        onClick={runOptimizer}
        disabled={running}
      >
        {running ? "⟳  OPTIMIZING (≈20-30s)…" : "▶  RUN OPTIMIZER"}
      </button>

      {error && <div className="warn-item w-fail">{error}</div>}

      {results && (
        <>
          {/* Material preference strip -- this is the context that was
              completely invisible in v1's display, and is exactly what
              Jay's report showed missing: which discharge type/CR range
              this material actually wants, shown plainly rather than only
              implied by which rows happen to rank well. */}
          {pref && (
            <div
              style={{
                padding: "8px 12px", background: "rgba(74,158,255,.06)",
                border: "1px solid rgba(74,158,255,.2)", borderRadius: 5,
                fontSize: 11, color: C.muted2,
              }}
            >
              <span style={{ color: C.text }}>{inputs.mat_id ?? "Material"}</span>{" "}
              prefers <span style={{ color: C.blue, fontWeight: 700 }}>{pref.bucket_style}</span>{" "}
              ({pref.discharge_type}), target CR{" "}
              <span style={{ fontFamily: "JetBrains Mono", color: C.text }}>
                {pref.cr_target_range?.[0]}–{pref.cr_target_range?.[1]}
              </span>
              . This is a strong default, not a wall — a different style can
              still rank well if it wins decisively elsewhere.
            </div>
          )}

          {/* Summary strip */}
          <div
            style={{
              padding: "10px 12px",
              background: C.hi,
              borderRadius: "var(--r-md)",
              border: `1px solid ${C.border2}`,
              fontSize: 11,
            }}
          >
            <span style={{ color: C.muted }}>
              {results.n_pareto_points} Pareto-efficient design
              {results.n_pareto_points === 1 ? "" : "s"} found in{" "}
              {results.elapsed_s}s
              {top && (
                <>
                  {" "}· top by current sort:{" "}
                  <span style={{ color: C.green, fontFamily: "JetBrains Mono", fontWeight: 700 }}>
                    {top.n_rpm} rpm · {top.bucket_id} · {top.motor_kw} kW
                  </span>
                </>
              )}
            </span>
            <span style={{ color: C.muted, marginLeft: 8 }}>
              ({selected.size} selected)
            </span>
          </div>

          {/* Sort selector -- there's no single objective to rank by
              anymore, so this replaces v1's weighted "Objective Function"
              dropdown with an honest "sort the real trade-offs by..." control. */}
          <div className="inp-field">
            <div className="inp-label">Sort By</div>
            <select
              className="inp-sel"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="btn-secondary"
              style={{ margin: 0 }}
              disabled={selected.size !== 1}
              title={
                selected.size !== 1 ? "Select exactly one variant to apply" : ""
              }
              onClick={() => {
                const idx = [...selected][0];
                const c = sortedFront[idx];
                onApply({
                  rpm: c.n_rpm, bucket_id: c.bucket_id, fill: c.fill_pct,
                  D_mm: c.D_mm, boot_pulley_D_mm: c.boot_pulley_D_mm,
                  chain_n_strands: c.chain_n_strands ?? undefined,
                });
              }}
            >
              ✓ Apply Selected to Design
            </button>

            <button
              className="btn-secondary"
              style={{ margin: 0 }}
              disabled={pinnedNone}
              title={pinnedNone ? "Select at least one variant" : ""}
              onClick={() =>
                downloadVariantReport(
                  pinned.map((c, i) => toVariantReportShape(c, i + 1)),
                  inputs
                )
              }
            >
              ⬇ Export{" "}
              {pinned.length > 0
                ? `${pinned.length} Variant${pinned.length > 1 ? "s" : ""}`
                : "Variants"}{" "}
              as PDF
            </button>

            <button
              className="btn-secondary"
              style={{ margin: 0, fontSize: 10 }}
              onClick={() =>
                setSelected(new Set(sortedFront.map((_, i) => i)))
              }
            >
              Select All
            </button>
            <button
              className="btn-secondary"
              style={{ margin: 0, fontSize: 10 }}
              onClick={() => setSelected(new Set())}
            >
              Clear
            </button>
          </div>

          {selected.size > 0 && (
            <div style={{ fontSize: 10, color: C.teal }}>
              {selected.size} variant{selected.size > 1 ? "s" : ""} selected —{" "}
              {selected.size === 1
                ? "click Apply to use in design, or Export to generate PDF"
                : "Export will generate a side-by-side comparison report"}
            </div>
          )}

          {/* Results table */}
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 32 }}>⬜</th>
                  <th>#</th>
                  <th>RPM</th>
                  <th>Bucket</th>
                  <th>Fill %</th>
                  <th>D mm</th>
                  <th>Boot mm</th>
                  {isChainRun && <th>Strands</th>}
                  <th>Q t/h</th>
                  <th>Motor kW</th>
                  <th>Load kN</th>
                  <th>L10 h</th>
                  <th>CR</th>
                  <th>CR Dev</th>
                </tr>
              </thead>
              <tbody>
                {sortedFront.map((c, i) => {
                  const isPinned = selected.has(i);
                  const isTop = i === 0;
                  const crColor = crDevColor(c.cr_deviation ?? 0);
                  return (
                    <tr
                      key={i}
                      onClick={() => toggleSelect(i)}
                      style={{
                        cursor: "pointer",
                        background: isPinned
                          ? "rgba(59,130,246,.12)"
                          : isTop
                            ? "rgba(16,185,129,.06)"
                            : (c.feasible === false ? "rgba(239,68,68,.06)" : ""),
                        outline: isPinned ? `1px solid ${C.blue}40` : "none",
                      }}
                      title={c.feasible === false ? "Marked infeasible by the optimizer's own constraints" : ""}
                    >
                      <td style={{ textAlign: "center", fontSize: 14 }}>
                        {isPinned ? "☑" : "☐"}
                      </td>
                      <td
                        className="mono"
                        style={{ color: isTop ? C.green : C.muted }}
                      >
                        {isTop ? "★" : i + 1}
                      </td>
                      <td className="mono">{c.n_rpm}</td>
                      <td className="mono" style={{ color: C.blue }}>
                        {c.bucket_id}
                      </td>
                      <td className="mono">{c.fill_pct}%</td>
                      <td className="mono">{c.D_mm}</td>
                      <td className="mono">{c.boot_pulley_D_mm}</td>
                      {isChainRun && <td className="mono">{c.chain_n_strands ?? "—"}</td>}
                      <td className="mono" style={{ color: C.green }}>
                        {c.Q_th ?? "—"}
                      </td>
                      <td className="mono" style={{ color: C.amber }}>
                        {c.motor_kw}
                      </td>
                      <td className="mono">
                        {c.R_headshaft_N != null ? Math.round(c.R_headshaft_N / 1000) : "—"}
                      </td>
                      <td className="mono">
                        {c.L10_h != null ? Math.round(c.L10_h).toLocaleString() : "—"}
                      </td>
                      <td className="mono">{c.cr ?? "—"}</td>
                      <td className="mono" style={{ color: crColor }}>
                        {c.cr_deviation}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: 10, color: C.muted }}>
            Click any row to select / deselect. CR Dev = distance outside the
            material's preferred CR range (0 = exactly on target). Sorted by{" "}
            {SORT_OPTIONS.find((o) => o.id === sortBy)?.label.split(" (")[0]}.
          </div>
        </>
      )}
    </div>
  );
}