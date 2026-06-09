// InputSidebar.jsx — Task 5: Discipline Accordion Cards
//
// CHANGES FROM TASK 3 VERSION
// ────────────────────────────
// Layout:  flat border-bottom list  →  accordion cards per discipline
// Sections renamed to engineering disciplines:
//   A — Process Requirements   → PROCESS DESIGN
//   B — Mechanical Parameters  → MECHANICAL DESIGN
//   C — Bucket Selection       → BUCKET SELECTION   (unchanged)
//   D — Belt & Drive           → POWER TRANSMISSION
//   NEW: CEMA 375 Advanced (boot pulley, Leq, Ceff, K_takeup)
//
// Each section card:
//   - Colour-coded discipline dot matching KPI card tags
//   - Section status badge (CEMA clause + check count)
//   - Inline result feedback below relevant fields
//   - Collapsible with smooth indicator
//   - 12px border-radius, 8px vertical gap between cards
//   - Background contrast instead of border-bottom separators
//
// New fields exposed (were hidden, using Pydantic defaults only):
//   boot_pulley_D_mm  — required for CEMA 375 §4 LEQ power method
//   Leq               — length equivalency factor
//   Ceff              — drive efficiency factor
//   K_takeup          — take-up tension factor

import { useState } from "react";

// ── Discipline colour palette — matches KPI card tags ────────────────────────
const DISC_COLORS = {
  process:    { dot: "#3b82f6", bg: "rgba(59,130,246,.08)",  border: "rgba(59,130,246,.2)"  },
  mechanical: { dot: "#10b981", bg: "rgba(16,185,129,.08)",  border: "rgba(16,185,129,.2)"  },
  bucket:     { dot: "#f59e0b", bg: "rgba(245,158,11,.08)",  border: "rgba(245,158,11,.2)"  },
  power:      { dot: "#a78bfa", bg: "rgba(167,139,250,.08)", border: "rgba(167,139,250,.2)" },
  advanced:   { dot: "#14b8a6", bg: "rgba(20,184,166,.08)",  border: "rgba(20,184,166,.2)"  },
};

const MATERIALS = [
  { id: "wheat",     name: "Wheat",              group: "Grain" },
  { id: "corn",      name: "Corn (Maize)",        group: "Grain" },
  { id: "soybeans",  name: "Soybeans",            group: "Grain" },
  { id: "rice",      name: "Rice (rough)",        group: "Grain" },
  { id: "sugar",     name: "Sugar (granulated)",  group: "Mineral" },
  { id: "salt",      name: "Salt (fine)",         group: "Mineral" },
  { id: "cement",    name: "Cement (dry)",        group: "Industrial" },
  { id: "limestone", name: "Limestone (crushed)", group: "Industrial" },
  { id: "coal",      name: "Coal (bituminous)",   group: "Industrial" },
  { id: "ironore",   name: "Iron Ore (fines)",    group: "Industrial" },
  { id: "sand",      name: "Sand (dry)",          group: "Industrial" },
  { id: "clinker",   name: "Clinker",             group: "Industrial" },
  { id: "flyash",    name: "Fly Ash",             group: "Industrial" },
  { id: "phosphate", name: "Phosphate Rock",      group: "Industrial" },
  { id: "woodchips", name: "Wood Chips",          group: "Biomass" },
  { id: "custom",    name: "Custom Material",     group: "Custom" },
];

const BUCKET_SERIES = [
  { id: "AA", label: "AA — Super Capacity",  vol: "7.4L", dim: "305×203mm" },
  { id: "A",  label: "A  — Extra Capacity",  vol: "5.0L", dim: "254×178mm" },
  { id: "B",  label: "B  — Medium Capacity", vol: "3.3L", dim: "203×152mm" },
  { id: "C",  label: "C  — Centrifugal",     vol: "1.9L", dim: "152×127mm" },
  { id: "D",  label: "D  — Centrifugal Sm.", vol: "0.77L",dim: "102×89mm"  },
  { id: "MF", label: "MF — Milk of Lime",    vol: "4.0L", dim: "254×152mm" },
  { id: "PF", label: "PF — Pellet/Feed",     vol: "6.5L", dim: "305×203mm" },
  { id: "HF", label: "HF — High Capacity",   vol: "11.2L",dim: "356×254mm" },
];

// ── Shared field components ───────────────────────────────────────────────────

function Field({ label, k, unit, min, max, step = 1, inputs, setField, hint }) {
  return (
    <div className="inp-field">
      <div className="inp-label">{label}</div>
      <div className="inp-wrap">
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={inputs[k] ?? ""}
          onChange={(e) => setField(k, parseFloat(e.target.value) || 0)}
        />
        {unit && <span className="inp-unit">{unit}</span>}
      </div>
      {hint && (
        <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2,
          lineHeight: 1.4 }}>{hint}</div>
      )}
    </div>
  );
}

function ResultFeedback({ children }) {
  return (
    <div style={{
      fontSize: 10, color: "var(--text3)",
      background: "var(--panel2)",
      border: "1px solid var(--border)",
      borderRadius: "var(--r-sm)",
      padding: "5px 8px",
      fontFamily: "JetBrains Mono, monospace",
      lineHeight: 1.6,
    }}>
      {children}
    </div>
  );
}

// ── Discipline Section Card ───────────────────────────────────────────────────

function DisciplineCard({
  disc, title, cema, badge, badgeType = "info",
  defaultOpen = true, children,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const dc = DISC_COLORS[disc] || DISC_COLORS.process;

  const badgeColors = {
    ok:   { bg: "rgba(16,185,129,.15)", color: "#10b981", border: "rgba(16,185,129,.3)"  },
    warn: { bg: "rgba(245,158,11,.15)", color: "#f59e0b", border: "rgba(245,158,11,.3)"  },
    fail: { bg: "rgba(239,68,68,.15)",  color: "#ef4444", border: "rgba(239,68,68,.3)"   },
    info: { bg: "rgba(59,130,246,.12)", color: "#3b82f6", border: "rgba(59,130,246,.25)" },
  };
  const bc = badgeColors[badgeType] || badgeColors.info;

  return (
    <div style={{
      margin: "6px 8px",
      borderRadius: "var(--r-lg)",
      border: `1px solid ${open ? dc.border : "var(--border)"}`,
      background: open ? dc.bg : "var(--surface)",
      overflow: "hidden",
      transition: "border-color .2s, background .2s",
    }}>
      {/* Card header */}
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "9px 12px",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        {/* Discipline colour dot */}
        <div style={{
          width: 6, height: 6, borderRadius: "50%",
          background: dc.dot, flexShrink: 0,
          boxShadow: `0 0 5px ${dc.dot}88`,
        }} />

        {/* Title */}
        <span style={{
          fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
          textTransform: "uppercase", color: "var(--text2)",
          flex: 1,
        }}>{title}</span>

        {/* CEMA clause tag */}
        {cema && (
          <span style={{
            fontSize: 9, color: "var(--muted)", letterSpacing: ".04em",
            fontFamily: "JetBrains Mono, monospace",
          }}>{cema}</span>
        )}

        {/* Status badge */}
        {badge && (
          <span style={{
            fontSize: 9, fontWeight: 600, letterSpacing: ".04em",
            padding: "1px 6px", borderRadius: "var(--r-pill)",
            background: bc.bg, color: bc.color, border: `1px solid ${bc.border}`,
          }}>{badge}</span>
        )}

        {/* Chevron */}
        <span style={{
          fontSize: 9, color: "var(--faint)",
          transform: open ? "rotate(180deg)" : "none",
          transition: "transform .2s",
          display: "inline-block",
        }}>▼</span>
      </div>

      {/* Card body */}
      {open && (
        <div style={{
          padding: "8px 10px 12px",
          display: "flex", flexDirection: "column", gap: 8,
          borderTop: `1px solid ${dc.border}`,
          background: "var(--panel)",
        }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function InputSidebar({ inputs, setField, results }) {

  // Derive status badges from results
  const capOK    = results?.Q != null && results.Q >= inputs.Q_req;
  const speedOK  = results?.v != null
    && results.v >= (results.bucket?.v_min ?? 0.5)
    && results.v <= (results.bucket?.v_max ?? 3.0);
  const crOK     = results?.cr != null && results.cr >= 1.0 && results.cr <= 1.8;
  const T_total  = (results?.T1 ?? 0) + (results?.T2 ?? 0) + (results?.T3 ?? 0);

  const procBadge  = !results ? null : capOK  ? "✓ PASS" : "✗ FAIL";
  const mechBadge  = !results ? null : speedOK ? "✓ PASS" : "⚠ WARN";
  const powerBadge = !results ? null : "INFO";

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      height: "100%", overflowY: "auto",
      paddingBottom: 12,
    }}>

      {/* ── PROCESS DESIGN ─────────────────────────────────── */}
      <DisciplineCard
        disc="process" title="Process Design"
        cema="CEMA 375 §4"
        badge={procBadge}
        badgeType={!results ? "info" : capOK ? "ok" : "fail"}
        defaultOpen={true}
      >
        <Field label="Required Capacity" k="Q_req" unit="t/h"
          min={1} max={5000} inputs={inputs} setField={setField} />
        <Field label="Lift Height" k="H_m" unit="m"
          min={1} max={200} inputs={inputs} setField={setField} />

        <div className="inp-field">
          <div className="inp-label">Bulk Material</div>
          <select className="inp-sel" value={inputs.mat_id}
            onChange={(e) => setField("mat_id", e.target.value)}>
            {MATERIALS.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        {inputs.mat_id === "custom" && (
          <Field label="Custom Density" k="custom_rho" unit="kg/m³"
            min={100} max={5000} inputs={inputs} setField={setField} />
        )}

        {results && (
          <ResultFeedback>
            <span style={{ color: "var(--muted)" }}>ρ</span>{" "}
            <span style={{ color: "var(--text)" }}>{results.rho} kg/m³</span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>Km</span>{" "}
            <span style={{ color: "var(--text)" }}>{results.mat?.Km}</span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>Flow</span>{" "}
            <span style={{ color: "var(--primary)" }}>
              {results.mat?.flowability === 1 ? "Very Free"
               : results.mat?.flowability === 2 ? "Free"
               : results.mat?.flowability === 3 ? "Average" : "Poor"}
            </span>
            {results.mat?.hazard_codes?.length > 0 && (
              <span style={{ color: "var(--danger)", marginLeft: 6 }}>
                ⚠ {results.mat.hazard_codes.join(" ")}
              </span>
            )}
          </ResultFeedback>
        )}

        {results && (
          <ResultFeedback>
            <span style={{ color: "var(--muted)" }}>Q achieved</span>{" "}
            <span style={{ color: capOK ? "var(--success)" : "var(--danger)", fontWeight: 700 }}>
              {Number(results.Q).toFixed(1)} t/h
            </span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>req</span>{" "}
            <span style={{ color: "var(--text)" }}>{inputs.Q_req} t/h</span>
            {results.Q != null && (
              <span style={{
                color: capOK ? "var(--success)" : "var(--danger)",
                marginLeft: 6,
              }}>
                {capOK ? "+" : ""}{(((results.Q - inputs.Q_req) / inputs.Q_req) * 100).toFixed(1)}%
              </span>
            )}
          </ResultFeedback>
        )}
      </DisciplineCard>

      {/* ── MECHANICAL DESIGN ──────────────────────────────── */}
      <DisciplineCard
        disc="mechanical" title="Mechanical Design"
        cema="CEMA 375 §3,6"
        badge={mechBadge}
        badgeType={!results ? "info" : speedOK ? "ok" : "warn"}
        defaultOpen={true}
      >
        <div className="inp-row">
          <Field label="Head Pulley Dia." k="D_mm" unit="mm"
            min={100} max={1500} step={25} inputs={inputs} setField={setField} />
          <Field label="Shaft Speed" k="n_rpm" unit="rpm"
            min={10} max={300} inputs={inputs} setField={setField} />
        </div>
        <div className="inp-row">
          <Field label="Fill Factor" k="fill_pct" unit="%"
            min={30} max={100} inputs={inputs} setField={setField} />
          <Field label="Spacing Gap" k="bucket_gap" unit="mm"
            min={0} max={200} inputs={inputs} setField={setField} />
        </div>

        {results && (
          <ResultFeedback>
            <span style={{ color: "var(--muted)" }}>v</span>{" "}
            <span style={{ color: speedOK ? "var(--success)" : "var(--danger)", fontWeight: 700 }}>
              {Number(results.v).toFixed(3)} m/s
            </span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>CR</span>{" "}
            <span style={{ color: crOK ? "var(--success)" : "var(--warning)" }}>
              {Number(results.cr).toFixed(3)}
            </span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>θ</span>{" "}
            <span style={{ color: "var(--primary)" }}>{Number(results.theta_rel).toFixed(1)}°</span>
          </ResultFeedback>
        )}
        {results && (
          <ResultFeedback>
            <span style={{ color: "var(--muted)" }}>spacing</span>{" "}
            <span style={{ color: "var(--text)" }}>{(results.spacing * 1000).toFixed(0)} mm</span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>belt</span>{" "}
            <span style={{ color: "var(--text)" }}>{results.belt_w} mm wide</span>
          </ResultFeedback>
        )}
      </DisciplineCard>

      {/* ── BUCKET SELECTION ───────────────────────────────── */}
      <DisciplineCard
        disc="bucket" title="Bucket Selection"
        cema="CEMA 375 §6"
        badge={results?.bucket ? results.bucket.id : null}
        badgeType="info"
        defaultOpen={true}
      >
        <div className="inp-field">
          <div className="inp-label">Selection Mode</div>
          <select className="inp-sel"
            value={inputs.auto_bucket ? "auto" : "manual"}
            onChange={(e) => setField("auto_bucket", e.target.value === "auto")}>
            <option value="auto">Auto Select (recommended)</option>
            <option value="manual">Manual Select</option>
          </select>
        </div>

        {!inputs.auto_bucket && (
          <div className="inp-field">
            <div className="inp-label">Bucket Series</div>
            <select className="inp-sel" value={inputs.bucket_id}
              onChange={(e) => setField("bucket_id", e.target.value)}>
              {BUCKET_SERIES.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.label} · {b.vol}
                </option>
              ))}
            </select>
          </div>
        )}

        {results?.bucket && (
          <ResultFeedback>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>
                <span style={{ color: "var(--muted)" }}>Series</span>{" "}
                <span style={{ color: "var(--warning)", fontWeight: 700 }}>
                  {results.bucket.id}
                </span>
              </span>
              <span>
                <span style={{ color: "var(--muted)" }}>V</span>{" "}
                <span style={{ color: "var(--text)" }}>{results.bucket.V}L</span>
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
              <span>
                <span style={{ color: "var(--muted)" }}>Size</span>{" "}
                <span style={{ color: "var(--text)" }}>
                  {results.bucket.W}×{results.bucket.H}mm
                </span>
              </span>
              <span>
                <span style={{ color: "var(--muted)" }}>P</span>{" "}
                <span style={{ color: "var(--text)" }}>{results.bucket.P}mm</span>
              </span>
            </div>
            <div style={{ marginTop: 4 }}>
              <span style={{ color: "var(--muted)" }}>Speed range</span>{" "}
              <span style={{ color: "var(--text2)" }}>
                {results.bucket.v_min}–{results.bucket.v_max} m/s
              </span>
            </div>
          </ResultFeedback>
        )}
      </DisciplineCard>

      {/* ── POWER TRANSMISSION ─────────────────────────────── */}
      <DisciplineCard
        disc="power" title="Power Transmission"
        cema="CEMA 375 §4"
        badge={results ? `${results.motor_kw}kW` : null}
        badgeType="info"
        defaultOpen={false}
      >
        <div className="inp-row">
          <Field label="Friction μ" k="mu" unit=""
            min={0.1} max={0.6} step={0.01} inputs={inputs} setField={setField} />
          <Field label="Wrap Angle" k="wrap_deg" unit="°"
            min={90} max={240} inputs={inputs} setField={setField} />
        </div>
        <div className="inp-row">
          <Field label="Service Factor" k="sf" unit=""
            min={1.0} max={2.0} step={0.05} inputs={inputs} setField={setField} />
          <Field label="Take-up K" k="K_takeup" unit=""
            min={0.4} max={0.9} step={0.05} inputs={inputs} setField={setField}
            hint="0.5 screw · 0.7 gravity" />
        </div>

        {results && (
          <ResultFeedback>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>
                <span style={{ color: "var(--muted)" }}>P_total</span>{" "}
                <span style={{ color: "var(--warning)", fontWeight: 700 }}>
                  {Number(results.P_total).toFixed(2)} kW
                </span>
              </span>
              <span>
                <span style={{ color: "var(--muted)" }}>motor</span>{" "}
                <span style={{ color: "var(--text)" }}>{results.motor_kw} kW</span>
              </span>
            </div>
            <div style={{ marginTop: 2 }}>
              <span style={{ color: "var(--muted)" }}>T1+T2+T3</span>{" "}
              <span style={{ color: T_total > 50000 ? "var(--warning)" : "var(--text)" }}>
                {(T_total / 1000).toFixed(2)} kN
              </span>
            </div>
          </ResultFeedback>
        )}
      </DisciplineCard>

      {/* ── CEMA 375 ADVANCED ──────────────────────────────── */}
      <DisciplineCard
        disc="advanced" title="CEMA 375 Advanced"
        cema="LEQ Method"
        badge="§4 Expert"
        badgeType="info"
        defaultOpen={false}
      >
        <div style={{ fontSize: 10, color: "var(--muted)", lineHeight: 1.5,
          padding: "2px 0 6px" }}>
          CEMA 375 §4 Length Equivalency power method parameters.
          Leave at 0 to use material-specific defaults.
        </div>

        <Field label="Boot Pulley Dia." k="boot_pulley_D_mm" unit="mm"
          min={100} max={1000} step={25} inputs={inputs} setField={setField}
          hint="Tail pulley for LEQ digging loss calc" />

        <div className="inp-row">
          <Field label="Leq Factor" k="Leq" unit=""
            min={0} max={20} step={0.5} inputs={inputs} setField={setField}
            hint="5–12 · 0=auto" />
          <Field label="Ceff Factor" k="Ceff" unit=""
            min={0} max={2.0} step={0.05} inputs={inputs} setField={setField}
            hint="1.10–1.30 · 0=auto" />
        </div>

        {results && (
          <ResultFeedback>
            <span style={{ color: "var(--muted)" }}>Leq used</span>{" "}
            <span style={{ color: "var(--teal)" }}>{results.Leq}</span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>Ceff</span>{" "}
            <span style={{ color: "var(--teal)" }}>{results.Ceff}</span>
            {"  "}
            <span style={{ color: "var(--muted)" }}>P_dig</span>{" "}
            <span style={{ color: "var(--text)" }}>
              {results.P_digging != null ? Number(results.P_digging).toFixed(3) : "—"} kW
            </span>
          </ResultFeedback>
        )}
      </DisciplineCard>

      {/* Footer */}
      <div style={{ padding: "10px 12px 4px", marginTop: "auto" }}>
        <div style={{ fontSize: 9, color: "var(--faint)", textAlign: "center",
          letterSpacing: ".05em" }}>
          VECTRIX™ · AKSHAYVIPRA EL-MEC
          <br />
          VECTOMEC™ Bucket Elevator · CEMA 375-2017
        </div>
      </div>
    </div>
  );
}
