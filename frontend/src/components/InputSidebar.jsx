// InputSidebar.jsx — CEMA 375 design parameter input cards
//
// Fix log vs previous version
// ─────────────────────────────────────────────────────────────────────────────
// FIX 1  Scroll: container was height-fixed with overflow:hidden.
//        Changed to flex column + overflow-y:auto so all cards are reachable
//        regardless of viewport height.
//
// FIX 2  Partial-open state: accordion used a shared activeCard string which
//        caused all cards to appear half-open on mount.
//        Each card now has individual useState(open) — fully independent.
//
// FIX 3  Height overflow: parent gave a fixed pixel height.  Accordion body
//        now uses max-height CSS transition (0 → auto proxy via large value)

import MaterialSearchDropdown from "./MaterialSearchDropdown";
import DesignOverridesCard from "./DesignOverridesCard";
//        so React never needs to know content height.
//
// FIX 4  New card: Service Conditions (environment, belt_type, wind_pressure_pa)
//        These were added to DEFAULT_INPUTS in v1.3.0 but had no UI inputs.
//
// Card default states: Mechanical Design open, all others closed.
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from "react";

// ─── Shared style tokens (inline to avoid CSS file dependency) ───────────────
const T = {
  border:   "var(--border,   #1c3050)",
  panel:    "var(--panel,    #0d1c2e)",
  panel2:   "var(--panel2,   #132238)",
  bg:       "var(--bg,       #07111e)",
  text:     "var(--text,     #ddeaf6)",
  text2:    "var(--text2,    #b0c4d8)",
  text3:    "var(--text3,    #5a7a9a)",
  primary:  "var(--primary,  #4a9eff)",
  success:  "var(--success,  #1fb86e)",
  warning:  "var(--warning,  #d98e00)",
  danger:   "var(--danger,   #e05252)",
  muted:    "var(--muted,    #5a7a9a)",
};

// ─── Accordion card wrapper ──────────────────────────────────────────────────
function Card({ id, title, cema, badge, badgeColor, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);

  const badgeBg =
    badgeColor === "green"  ? { bg: "rgba(31,184,110,.15)", col: T.success, bdr: "rgba(31,184,110,.3)" } :
    badgeColor === "orange" ? { bg: "rgba(217,142,0,.15)",  col: T.warning, bdr: "rgba(217,142,0,.3)"  } :
    badgeColor === "red"    ? { bg: "rgba(224,82,82,.15)",  col: T.danger,  bdr: "rgba(224,82,82,.3)"  } :
    badgeColor === "blue"   ? { bg: "rgba(74,158,255,.12)", col: T.primary, bdr: "rgba(74,158,255,.25)"} :
                              { bg: "rgba(90,122,154,.12)", col: T.text3,   bdr: "rgba(90,122,154,.25)" };

  return (
    <div style={{
      borderBottom: `1px solid ${T.border}`,
    }}>
      {/* ── Header ── */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center",
          gap: 8, padding: "9px 12px",
          background: open ? "rgba(255,255,255,.03)" : "transparent",
          border: "none", cursor: "pointer",
          transition: "background .15s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,.04)"}
        onMouseLeave={e => e.currentTarget.style.background = open ? "rgba(255,255,255,.03)" : "transparent"}
      >
        <span style={{
          fontSize: 8, fontWeight: 700, letterSpacing: ".08em",
          textTransform: "uppercase", color: T.text3,
          flex: 1, textAlign: "left",
        }}>
          {title}
          {cema && (
            <span style={{ marginLeft: 5, opacity: 0.6, fontWeight: 400, letterSpacing: ".04em" }}>
              {cema}
            </span>
          )}
        </span>
        {badge && (
          <span style={{
            fontSize: 8, fontWeight: 700, padding: "1px 7px",
            borderRadius: 999,
            background: badgeBg.bg, color: badgeBg.col, border: `1px solid ${badgeBg.bdr}`,
            flexShrink: 0,
          }}>{badge}</span>
        )}
        <span style={{
          fontSize: 10, color: T.text3, flexShrink: 0,
          transform: open ? "rotate(90deg)" : "rotate(0deg)",
          transition: "transform .2s", lineHeight: 1,
        }}>›</span>
      </button>

      {/* ── Body (CSS max-height transition) ── */}
      <div style={{
        maxHeight: open ? "600px" : "0",
        overflow: "hidden",
        transition: "max-height .25s ease",
      }}>
        <div style={{ padding: "6px 12px 12px" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

// ─── Field row (label + input) ────────────────────────────────────────────────
function Field({ label, name, type = "number", value, onChange, unit, min, max, step, options, note }) {
  const baseInput = {
    background: T.panel2,
    border: `1px solid ${T.border}`,
    borderRadius: 4, color: T.text,
    fontFamily: "JetBrains Mono, monospace",
    fontSize: 12, padding: "5px 8px",
    outline: "none", width: "100%",
    boxSizing: "border-box",
    transition: "border-color .15s",
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{
        display: "block", fontSize: 9, color: T.text3, marginBottom: 3,
        fontWeight: 600, letterSpacing: ".04em",
      }}>{label}</label>

      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        {type === "select" ? (
          <select
            value={value ?? ""}
            onChange={e => onChange(name, e.target.value)}
            style={{ ...baseInput, flex: 1, cursor: "pointer" }}
          >
            {options?.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        ) : type === "toggle" ? (
          <button
            onClick={() => onChange(name, !value)}
            style={{
              padding: "4px 10px", borderRadius: 4, cursor: "pointer",
              border: `1px solid ${value ? T.primary : T.border}`,
              background: value ? "rgba(74,158,255,.12)" : T.panel2,
              color: value ? T.primary : T.text3,
              fontSize: 10, fontWeight: 600,
            }}
          >
            {value ? "Auto" : "Manual"}
          </button>
        ) : (
          <input
            type={type}
            value={value ?? ""}
            min={min} max={max} step={step}
            onChange={e => onChange(name, type === "number" ? parseFloat(e.target.value) : e.target.value)}
            style={{ ...baseInput, flex: 1 }}
            onFocus={e => e.target.style.borderColor = T.primary}
            onBlur={e => e.target.style.borderColor = T.border}
          />
        )}
        {unit && (
          <span style={{ fontSize: 9, color: T.text3, flexShrink: 0, minWidth: 24 }}>{unit}</span>
        )}
      </div>
      {note && (
        <div style={{ fontSize: 9, color: T.text3, marginTop: 3, lineHeight: 1.4 }}>{note}</div>
      )}
    </div>
  );
}

// ─── Two-column field layout ─────────────────────────────────────────────────
function TwoCol({ children }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 10px" }}>
      {children}
    </div>
  );
}

// ─── Section label inside card ────────────────────────────────────────────────
function SubHead({ label }) {
  return (
    <div style={{
      fontSize: 8, fontWeight: 700, letterSpacing: ".08em",
      textTransform: "uppercase", color: T.text3,
      margin: "8px 0 5px",
      paddingBottom: 3,
      borderBottom: `1px solid ${T.border}`,
    }}>{label}</div>
  );
}

// ─── Status badge for cards ───────────────────────────────────────────────────
function cardBadge(results, keywords) {
  if (!results?.checks?.length) return { badge: null, color: null };
  const kw = keywords.map(k => k.toLowerCase());
  const matched = results.checks.filter(c =>
    kw.some(k => (c.msg ?? "").toLowerCase().includes(k))
  );
  if (!matched.length) return { badge: null, color: null };
  if (matched.some(c => c.type === "fail")) return { badge: "FAIL", color: "red" };
  if (matched.some(c => c.type === "warn")) return { badge: "WARN", color: "orange" };
  return { badge: "PASS", color: "green" };
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function InputSidebar({ inputs, setField, results, activeDisc }) {
  const inp = inputs || {};

  // Per-card badge status (live from results)
  const proc    = cardBadge(results, ["capacity", "speed", "centrifugal"]);
  const mech    = cardBadge(results, ["shaft", "bearing", "L10", "headshaft"]);
  const bkt     = cardBadge(results, ["bucket", "CR=", "scatter"]);
  const pwr     = cardBadge(results, ["motor", "power", "kW", "Ceff"]);
  const svc     = cardBadge(results, ["slip", "lagging", "panel"]);

  // Bucket series options (from BUCKET_SERIES — hardcoded here for UI, matches backend)
  const bucketOptions = [
    { value: "AA", label: "AA — Super Capacity 7.4L" },
    { value: "A",  label: "A — Extra Capacity 5.0L"  },
    { value: "B",  label: "B — Medium Capacity 3.3L" },
    { value: "C",  label: "C — Centrifugal 1.9L"     },
    { value: "D",  label: "D — Centrifugal Sm. 0.77L"},
    { value: "MF", label: "MF — Milk of Lime 4.0L"   },
    { value: "PF", label: "PF — Pellet/Feed 6.5L"    },
    { value: "HF", label: "HF — High Capacity 11.2L" },
  ];

  return (
    <div style={{
      height: "100%",
      overflowY: "auto",
      overflowX: "hidden",
      display: "flex",
      flexDirection: "column",
    }}>

      {/* ══════════════════════════════════════════════════════
          PROCESS DESIGN
          ══════════════════════════════════════════════════════ */}
      <div id="disc-process">
        <Card
          id="process" title="Process Design" cema="CEMA 375"
          badge={proc.badge} badgeColor={proc.color}
          defaultOpen={false}
        >
          <TwoCol>
            <Field label="Required Capacity" name="Q_req"
              value={inp.Q_req} onChange={setField}
              unit="t/h" min={1} max={5000} step={1} />
            <Field label="Lift Height" name="H_m"
              value={inp.H_m} onChange={setField}
              unit="m" min={1} max={200} step={0.5} />
          </TwoCol>
          <div style={{ marginBottom: 6 }}>
            <div style={{ fontSize: 9, color: "var(--text3)", letterSpacing: ".04em",
              textTransform: "uppercase", marginBottom: 3 }}>Material</div>
            <MaterialSearchDropdown
              matId={inp.mat_id}
              onChange={v => setField("mat_id", v)}
            />
            <div style={{ fontSize: 8, color: "var(--muted)", marginTop: 3 }}>
              Search 864 materials — or type a mat_id directly
            </div>
          </div>
          <Field label="Custom Bulk Density" name="custom_rho"
            value={inp.custom_rho} onChange={setField}
            unit="kg/m³" min={0} max={5000} step={10}
            note="Set 0 to use material database value" />
        </Card>
      </div>

      {/* ══════════════════════════════════════════════════════
          MECHANICAL DESIGN
          ══════════════════════════════════════════════════════ */}
      <div id="disc-mechanical">
        <Card
          id="mechanical" title="Mechanical Design" cema="CEMA 375  §3, §6"
          badge={mech.badge} badgeColor={mech.color}
          defaultOpen={true}
        >
          <TwoCol>
            <Field label="Head Pulley Dia." name="D_mm"
              value={inp.D_mm} onChange={setField}
              unit="mm" min={100} max={1500} step={25} />
            <Field label="Shaft Speed" name="n_rpm"
              value={inp.n_rpm} onChange={setField}
              unit="rpm" min={10} max={300} step={5} />
          </TwoCol>
          <TwoCol>
            <Field label="Fill Factor" name="fill_pct"
              value={inp.fill_pct} onChange={setField}
              unit="%" min={30} max={100} step={5} />
            <Field label="Spacing Gap" name="bucket_gap"
              value={inp.bucket_gap} onChange={setField}
              unit="mm" min={0} max={200} step={5} />
          </TwoCol>
          <TwoCol>
            <Field label="Friction  μ" name="mu"
              value={inp.mu} onChange={setField}
              min={0.1} max={0.6} step={0.01} />
            <Field label="Wrap Angle" name="wrap_deg"
              value={inp.wrap_deg} onChange={setField}
              unit="°" min={90} max={240} step={5} />
          </TwoCol>
        </Card>
      </div>

      {/* ══════════════════════════════════════════════════════
          BUCKET SELECTION
          ══════════════════════════════════════════════════════ */}
      <div id="disc-bucket">
        <Card
          id="bucket" title="Bucket Selection" cema="CEMA 375  §6"
          badge={bkt.badge} badgeColor={bkt.color}
          defaultOpen={false}
        >
          <SubHead label="Selection Mode" />
          <Field
            label="Auto-select bucket" name="auto_bucket"
            type="toggle" value={inp.auto_bucket} onChange={setField}
          />
          {!inp.auto_bucket && (
            <Field
              label="Bucket Series" name="bucket_id"
              type="select" value={inp.bucket_id} onChange={setField}
              options={bucketOptions}
            />
          )}
          {inp.auto_bucket && (
            <div style={{ fontSize: 9, color: T.text3, padding: "4px 0" }}>
              Bucket series selected automatically to meet Q_req at the specified belt speed.
            </div>
          )}
        </Card>
      </div>

      {/* ══════════════════════════════════════════════════════
          POWER TRANSMISSION
          ══════════════════════════════════════════════════════ */}
      <div id="disc-power">
        <Card
          id="power" title="Power Transmission" cema="CEMA 375"
          badge={pwr.badge} badgeColor={pwr.color}
          defaultOpen={false}
        >
          <TwoCol>
            <Field label="Service Factor" name="sf"
              value={inp.sf} onChange={setField}
              min={1.0} max={2.0} step={0.05} />
            <Field label="Take-Up Factor K" name="K_takeup"
              value={inp.K_takeup} onChange={setField}
              min={0.4} max={0.9} step={0.05}
              note="0.5 screw  0.7 gravity" />
          </TwoCol>
        </Card>
      </div>

      {/* ══════════════════════════════════════════════════════
          SERVICE CONDITIONS  (v1.3.0 — new card)
          Exposes environment, belt_type, wind_pressure_pa
          which were in DEFAULT_INPUTS but had no UI controls.
          ══════════════════════════════════════════════════════ */}
      <div id="disc-service">
        <Card
          id="service" title="Service Conditions" cema="v1.3.0"
          badge={svc.badge} badgeColor={svc.color}
          defaultOpen={false}
        >
          <Field
            label="Environment" name="environment"
            type="select" value={inp.environment ?? "dry"}
            onChange={setField}
            options={[
              { value: "dry",       label: "Dry — standard indoor" },
              { value: "humid",     label: "Humid — moisture > 15%" },
              { value: "wet",       label: "Wet — water spray / washdown" },
              { value: "submerged", label: "Submerged — boot below water" },
            ]}
            note="Drives pulley lagging type and friction coefficient selection"
          />
          <Field
            label="Belt Type" name="belt_type"
            type="select" value={inp.belt_type ?? "EP"}
            onChange={setField}
            options={[
              { value: "EP", label: "EP — Fabric ply (standard)" },
              { value: "ST", label: "ST — Steel cord (high tension)" },
            ]}
            note="ST belts route to herringbone lagging (diamond groove not recommended)"
          />
          <Field
            label="Design Wind Pressure" name="wind_pressure_pa"
            value={inp.wind_pressure_pa ?? 800}
            onChange={setField}
            unit="Pa" min={0} max={5000} step={100}
            note="Used for casing panel deflection check. Typical: 600–1200 Pa"
          />
        </Card>
      </div>

      {/* ══════════════════════════════════════════════════════
          CEMA 375 ADVANCED
          ══════════════════════════════════════════════════════ */}
      <div id="disc-advanced">
        <Card
          id="advanced" title="CEMA 375 Advanced" cema="LEQ Method"
          badge="Expert" badgeColor="blue"
          defaultOpen={false}
        >
          <div style={{
            fontSize: 9, color: T.text3, padding: "2px 0 8px",
            lineHeight: 1.5, borderBottom: `1px solid ${T.border}`, marginBottom: 8,
          }}>
            CEMA 375 §4 Length Equivalency power method parameters.
            Set to 0 to use material-specific database defaults.
          </div>
          <Field label="Boot Pulley Dia." name="boot_pulley_D_mm"
            value={inp.boot_pulley_D_mm} onChange={setField}
            unit="mm" min={100} max={1000} step={25}
            note="Tail pulley for LEQ digging loss calculation" />
          <TwoCol>
            <Field label="Leq Factor" name="Leq"
              value={inp.Leq} onChange={setField}
              min={0} max={20} step={0.5}
              note="0 = auto from material" />
            <Field label="Ceff Factor" name="Ceff"
              value={inp.Ceff} onChange={setField}
              min={0} max={2.0} step={0.01}
              note="0 = auto from material" />
          </TwoCol>
        </Card>
      </div>

      {/* Design Overrides — exposed for every auto-calculated dimension */}
      <DesignOverridesCard inputs={inp} setField={setField} results={results} />

      {/* Bottom padding so last card isn't flush with the container edge */}
      <div style={{ flexShrink: 0, height: 16 }} />
    </div>
  );
}