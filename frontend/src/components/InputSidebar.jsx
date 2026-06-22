// InputSidebar.jsx — v2.0  Popup-edit architecture
//
// Design principles
// ─────────────────────────────────────────────────────────────────────────────
// • Sidebar is a compact READ-ONLY summary panel — no inline forms.
// • Every section has an "Edit ✎" button that opens a dedicated popup modal.
// • Mechanical Design is a GROUP heading; its 7 sub-sections each open their
//   own popup editor.
// • Font sizes ~150% larger than the old sidebar (13–15 px).
// • Accordion collapse on each top-level section.
// • Popup modals: fixed full-screen overlay, dark semi-transparent backdrop,
//   max-height 80 vh with internal scroll, "Apply & Close" footer.
//
// Section map
// ─────────────────────────────────────────────────────────────────────────────
//  1  Process Design       (Q_req, H_m, fill_pct, material, custom overrides)
//  2  Mechanical Design    (GROUP — no direct edit)
//  2a   Head & Tail Pulley (D_mm, n_rpm, boot pulley, wrap_deg, bucket_gap)
//  2b   Belt Selection     (belt_width_override_mm, belt_type, belt_ply ro)
//  2c   Bucket Selection   (auto_bucket, bucket_id, bucket_gap)
//  2d   Take-Up Selection  (takeup_type, screw params, shaft override)
//  2e   Discharge Section  (casing_clearance info, chute angle ro)
//  2f   Feed Design        (STUB — future release)
//  2g   Casing Design      (casing_t_override_mm, wind_pressure_pa)
//  3  Service Conditions   (environment, mu, wrap_deg)
//  4  Power Transmission   (sf, K_takeup, Leq, Ceff)
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback, useEffect } from "react";
import MaterialSearchDropdown from "./MaterialSearchDropdown";

// API base URL — Vite uses import.meta.env (not process.env)
const API_BASE = (import.meta.env?.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

// Field defaults used by onChange NaN guards — mirrors useElevatorCalc DEFAULT_INPUTS
const DEFAULT_INPUTS = {
  Q_req: 100, H_m: 25, fill_pct: 75, n_rpm: 60, D_mm: 500,
  boot_pulley_D_mm: 300, wrap_deg: 180, mu: 0.35, sf: 1.25,
  K_takeup: 0.7, Leq: 0, Ceff: 0, bucket_gap: 25,
  wind_pressure_pa: 800, casing_t_override_mm: 0,
  shaft_material: "A36",
  shaft_section: "solid", shaft_bore_ratio: 0, shaft_hub_connection: "keyed",
  shaft_d_override_mm: 0, belt_width_override_mm: 0,
  pulley_shell_t_override_mm: 0,
  bucket_thickness_override_mm: 0,
  takeup_screw_d_mm: 0, takeup_screw_len_m: 0,
  custom_rho: 0, custom_aor: 0, custom_abr: 0, custom_flowability: 0,
  custom_moisture: -1, custom_cohesion: -1, motor_kw_override: 0,
  chain_sf: 6.0, chain_sprocket_teeth: 0, boot_inlet_height_override_mm: 0,
};

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  border:   "var(--border,   #1c3050)",
  panel:    "var(--panel,    #0d1c2e)",
  panel2:   "var(--panel2,   #132238)",
  panel3:   "var(--panel3,   #0a1828)",
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

// ─── Form primitives (larger, popup-quality) ─────────────────────────────────
function Label({ children, note }) {
  return (
    <div style={{ marginBottom: 5 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: T.text2,
        letterSpacing: ".03em" }}>{children}</div>
      {note && <div style={{ fontSize: 10, color: T.text3, marginTop: 1,
        lineHeight: 1.4 }}>{note}</div>}
    </div>
  );
}

function FormInput({ name, type = "number", value, onChange,
                     unit, min, max, step, options, note }) {
  const base = {
    background: T.panel2, border: `1px solid ${T.border}`,
    borderRadius: 5, color: T.text, fontFamily: "JetBrains Mono, monospace",
    fontSize: 14, padding: "7px 10px", outline: "none", width: "100%",
    boxSizing: "border-box", transition: "border-color .15s",
  };
  return (
    <div style={{ marginBottom: 12 }}>
      <Label note={note}>{name.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase())}</Label>
      <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
        {type === "select" ? (
          <select value={value ?? ""} onChange={e => onChange(e.target.value)}
            style={{ ...base, flex: 1, cursor: "pointer" }}>
            {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : type === "toggle" ? (
          <button onClick={() => onChange(!value)} style={{
            padding: "6px 16px", borderRadius: 5, cursor: "pointer",
            border: `1px solid ${value ? T.primary : T.border}`,
            background: value ? "rgba(74,158,255,.15)" : T.panel2,
            color: value ? T.primary : T.text3, fontSize: 13, fontWeight: 600,
            fontFamily: "inherit",
          }}>{value ? "✓ ON" : "OFF"}</button>
        ) : (
          <input type={type} value={value ?? ""} min={min} max={max} step={step}
            onChange={e => {
              const _v = e.target.value;
              onChange(type === "number"
                ? (_v === "" || isNaN(parseFloat(_v)) ? 0 : parseFloat(_v))
                : _v);
            }}
            style={{ ...base, flex: 1 }}
            onFocus={e => e.target.style.borderColor = T.primary}
            onBlur={e => e.target.style.borderColor = T.border} />
        )}
        {unit && <span style={{ fontSize: 11, color: T.text3,
          flexShrink: 0, minWidth: 28 }}>{unit}</span>}
      </div>
    </div>
  );
}

function F({ label, name, type="number", value, onChange, unit, min, max, step, options, note }) {
  const base = {
    background: T.panel2, border: `1px solid ${T.border}`,
    borderRadius: 5, color: T.text, fontFamily: "JetBrains Mono, monospace",
    fontSize: 14, padding: "7px 10px", outline: "none", width: "100%",
    boxSizing: "border-box", transition: "border-color .15s",
  };
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: T.text2,
        marginBottom: 4, letterSpacing: ".03em" }}>{label}</div>
      {note && <div style={{ fontSize: 10, color: T.text3,
        marginBottom: 4, lineHeight: 1.4 }}>{note}</div>}
      <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
        {type === "select" ? (
          <select value={value ?? ""} onChange={e => onChange(name, e.target.value)}
            style={{ ...base, flex: 1, cursor: "pointer" }}>
            {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : type === "toggle" ? (
          <button onClick={() => onChange(name, !value)} style={{
            padding: "6px 16px", borderRadius: 5, cursor: "pointer",
            border: `1px solid ${value ? T.primary : T.border}`,
            background: value ? "rgba(74,158,255,.15)" : T.panel2,
            color: value ? T.primary : T.text3, fontSize: 13, fontWeight: 600,
            fontFamily: "inherit",
          }}>{value ? "✓ ON" : "OFF"}</button>
        ) : (
          <input type={type} value={value ?? ""} min={min} max={max} step={step}
            onChange={e => {
              const _rv = e.target.value;
              const _pf = parseFloat(_rv);
              onChange(name, type === "number"
                ? (_rv === "" || isNaN(_pf) ? (typeof DEFAULT_INPUTS[name] === "number" ? DEFAULT_INPUTS[name] : 0) : _pf)
                : _rv);
            }}
            style={{ ...base, flex: 1 }}
            onFocus={e => e.target.style.borderColor = T.primary}
            onBlur={e => e.target.style.borderColor = T.border} />
        )}
        {unit && <span style={{ fontSize: 11, color: T.text3,
          flexShrink: 0, minWidth: 28 }}>{unit}</span>}
      </div>
    </div>
  );
}

function Row2({ children }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 14px" }}>
      {children}
    </div>
  );
}

function SectionHead({ label }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, letterSpacing: ".07em",
      textTransform: "uppercase", color: T.text3,
      borderBottom: `1px solid ${T.border}`,
      paddingBottom: 5, marginBottom: 10, marginTop: 4,
    }}>{label}</div>
  );
}

// ─── Popup Modal shell ────────────────────────────────────────────────────────
function Modal({ title, cema, onClose, children }) {
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9000,
      background: "rgba(0,0,0,.65)", backdropFilter: "blur(3px)",
      display: "flex", alignItems: "flex-start", justifyContent: "flex-start",
      padding: "8px 0 8px 8px",
    }} onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        background: T.panel, border: `1px solid ${T.border}`,
        borderRadius: 8, width: 400, maxHeight: "calc(100vh - 16px)",
        display: "flex", flexDirection: "column",
        boxShadow: "0 16px 48px rgba(0,0,0,.7)",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", padding: "12px 16px",
          borderBottom: `1px solid ${T.border}`, flexShrink: 0,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: T.text,
              letterSpacing: ".04em" }}>{title}</div>
            {cema && <div style={{ fontSize: 10, color: T.text3,
              marginTop: 1 }}>{cema}</div>}
          </div>
          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 5, border: `1px solid ${T.border}`,
            background: "transparent", color: T.text3, cursor: "pointer",
            fontSize: 16, lineHeight: 1, fontFamily: "inherit",
          }}>✕</button>
        </div>
        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px" }}>
          {children}
        </div>
        {/* Footer */}
        <div style={{
          padding: "10px 16px", borderTop: `1px solid ${T.border}`,
          flexShrink: 0, display: "flex", justifyContent: "flex-end",
        }}>
          <button onClick={onClose} style={{
            padding: "8px 22px", borderRadius: 5, cursor: "pointer",
            background: T.primary, border: "none", color: "white",
            fontSize: 13, fontWeight: 700, fontFamily: "inherit",
          }}>Apply & Close</button>
        </div>
      </div>
    </div>
  );
}

// ─── Summary badge helpers ────────────────────────────────────────────────────
function checkBadge(results, keywords) {
  if (!results?.checks?.length) return null;
  const kw = keywords.map(k => k.toLowerCase());
  const matched = results.checks.filter(c =>
    kw.some(k => (c.msg ?? "").toLowerCase().includes(k)));
  if (!matched.length) return null;
  if (matched.some(c => c.type === "fail")) return { label: "FAIL", color: T.danger };
  if (matched.some(c => c.type === "warn")) return { label: "WARN", color: T.warning };
  return { label: "PASS", color: T.success };
}

function StatusBadge({ badge }) {
  if (!badge) return null;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 999,
      background: badge.color + "18", color: badge.color,
      border: `1px solid ${badge.color}40`,
    }}>{badge.label}</span>
  );
}

// ─── Section row in sidebar ───────────────────────────────────────────────────
function SectionRow({ label, cema, summary, badge, onEdit, depth = 0 }) {
  return (
    <div style={{
      display: "flex", alignItems: "flex-start",
      padding: `8px 12px 8px ${12 + depth * 14}px`,
      borderBottom: `1px solid ${T.border}`,
      cursor: onEdit ? "pointer" : "default",
      transition: "background .12s",
    }}
      onMouseEnter={e => onEdit && (e.currentTarget.style.background = "rgba(255,255,255,.03)")}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      onClick={onEdit}
    >
      {depth > 0 && (
        <span style={{ color: T.border, marginRight: 6,
          fontSize: 10, flexShrink: 0, marginTop: 3 }}>└</span>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            fontSize: depth > 0 ? 12 : 13, fontWeight: depth > 0 ? 600 : 700,
            color: depth > 0 ? T.text2 : T.text, letterSpacing: ".03em",
            flex: 1,
          }}>{label}</span>
          {badge && <StatusBadge badge={badge} />}
          {cema && !depth && (
            <span style={{ fontSize: 9, color: T.text3,
              flexShrink: 0 }}>{cema}</span>
          )}
          {onEdit && (
            <span style={{ fontSize: 11, color: T.primary,
              flexShrink: 0, opacity: .7 }}>✎</span>
          )}
        </div>
        {summary && (
          <div style={{ fontSize: 11, color: T.text3, marginTop: 2,
            whiteSpace: "nowrap", overflow: "hidden",
            textOverflow: "ellipsis", lineHeight: 1.4 }}>
            {summary}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Accordion group ──────────────────────────────────────────────────────────
function AccordionGroup({ label, cema, badge, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button onClick={() => setOpen(o => !o)} style={{
        width: "100%", display: "flex", alignItems: "center",
        padding: "10px 12px", background: "rgba(255,255,255,.025)",
        border: "none", borderBottom: `1px solid ${T.border}`,
        cursor: "pointer", gap: 8, transition: "background .12s",
      }}
        onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,.04)"}
        onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,.025)"}
      >
        <span style={{ fontSize: 14, fontWeight: 700, color: T.text,
          flex: 1, textAlign: "left", letterSpacing: ".04em" }}>
          {label}
          {cema && <span style={{ fontSize: 10, color: T.text3,
            marginLeft: 8, fontWeight: 400 }}>{cema}</span>}
        </span>
        {badge && <StatusBadge badge={badge} />}
        <span style={{ fontSize: 12, color: T.text3,
          transform: open ? "rotate(90deg)" : "none",
          transition: "transform .2s", lineHeight: 1 }}>›</span>
      </button>
      {open && <div>{children}</div>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT PICKER — fetches DB catalogue rows with constraint filtering
// ═══════════════════════════════════════════════════════════════════════════════
//
// Usage:
//   <ComponentPicker
//     path="/components/bearings"          ← appended to /api/v1
//     params={{ bore_min: 60, role: "" }}  ← filter query params
//     valueField="name"                    ← which DB column = option value
//     formatLabel={r => `${r.name} bore=${r.bore}mm C=${r.C}kN`}
//     value={inp.bearing_name}
//     name="bearing_name"
//     onChange={setField}
//     autoLabel="SY 60 TF (auto)"          ← what solver selected
//     label="Head Shaft Bearing"
//     note="Filtered: bore ≥ shaft diameter"
//   />
//
// Auto-reset: selecting "" (first option) clears the override → solver picks.
// Re-fetches whenever params values change (JSONified for stable comparison).

function ComponentPicker({
  path,         // API path suffix, e.g. "/components/bearings"
  params = {},  // query filter params object
  valueField,   // which DB column is the unique key / option value
  formatLabel,  // (row) => string shown in dropdown
  value,        // current inp[name] (empty = auto)
  name,         // setField key
  onChange,     // setField(name, value)
  autoLabel,    // what the solver auto-selected (shown as hint)
  label,
  note,
}) {
  const [options, setOptions]  = useState([]);
  const [loading, setLoading]  = useState(false);
  const [fetchErr, setErr]     = useState(null);
  const paramsKey = JSON.stringify(params);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    const clean = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v != null && v !== "")
    );
    const qs  = new URLSearchParams(clean).toString();
    const url = `${API_BASE}/api/v1${path}?${qs}`;
    fetch(url)
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(data => {
        const list = Object.values(data).find(v => Array.isArray(v)) ?? [];
        setOptions(list);
        setLoading(false);
      })
      .catch(e => { setErr(String(e)); setLoading(false); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, path]);

  const base = {
    background: T.panel2, border: `1px solid ${T.border}`,
    borderRadius: 5, color: T.text, fontFamily: "JetBrains Mono,monospace",
    fontSize: 13, padding: "7px 10px", width: "100%", boxSizing: "border-box",
    cursor: "pointer",
  };

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: T.text2, marginBottom: 4 }}>
        {label}
      </div>
      {autoLabel && !value && (
        <div style={{ fontSize: 10, color: T.success, marginBottom: 4 }}>
          ✓ Auto: {autoLabel}
        </div>
      )}
      {value && (
        <div style={{ fontSize: 10, color: T.primary, marginBottom: 4 }}>
          ● Override active — clear to restore auto
        </div>
      )}
      {note && (
        <div style={{ fontSize: 10, color: T.text3, marginBottom: 4, lineHeight: 1.4 }}>
          {note}
        </div>
      )}
      {loading ? (
        <div style={{
          fontSize: 11, color: T.text3, padding: "8px 10px",
          background: T.panel2, borderRadius: 5, border: `1px solid ${T.border}`,
        }}>
          Loading catalogue…
        </div>
      ) : fetchErr ? (
        <div style={{ fontSize: 10, color: T.danger, padding: "6px 0" }}>
          ⚠ Could not load catalogue: {fetchErr}
        </div>
      ) : (
        <select
          value={value || ""}
          onChange={e => onChange(name, e.target.value)}
          style={base}
        >
          <option value="">— Auto (solver default) —</option>
          {options.map(opt => (
            <option key={opt[valueField]} value={opt[valueField]}>
              {formatLabel(opt)}
            </option>
          ))}
        </select>
      )}
      {options.length > 0 && (
        <div style={{ fontSize: 9, color: T.text3, marginTop: 3 }}>
          {options.length} options available
          {value ? (
            <button onClick={() => onChange(name, "")} style={{
              marginLeft: 10, fontSize: 9, color: T.warning, background: "none",
              border: "none", cursor: "pointer", padding: 0, fontFamily: "inherit",
            }}>
              ✕ clear override
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// EDIT MODAL CONTENTS — one per section
// ═══════════════════════════════════════════════════════════════════════════════

function ProcessEdit({ inp, setField, results }) {
  const r = results || {};
  const df = r.dynamic_fill ?? null;   // dynamic_fill_efficiency() output — has spacing_status
  return (
    <>
      <SectionHead label="Drive Type" />
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {[["belt", "🔵 Belt Drive"], ["chain", "⛓ Chain Drive"]].map(([v, label]) => (
          <button key={v} onClick={() => setField("conveyor_type", v)} style={{
            flex: 1, padding: "9px 4px", borderRadius: 5, cursor: "pointer",
            fontFamily: "inherit", fontSize: 13, fontWeight: 600,
            border: `1px solid ${(inp.conveyor_type ?? "belt") === v ? T.primary : T.border}`,
            background: (inp.conveyor_type ?? "belt") === v
              ? "rgba(74,158,255,.15)" : T.panel2,
            color: (inp.conveyor_type ?? "belt") === v ? T.primary : T.text3,
          }}>{label}</button>
        ))}
      </div>
      {(inp.conveyor_type ?? "belt") === "chain" && (
        <div style={{
          background: "rgba(74,158,255,.06)", border: "1px solid rgba(74,158,255,.2)",
          borderRadius: 5, padding: "8px 12px", marginBottom: 12, fontSize: 11,
          color: T.text3, lineHeight: 1.5,
        }}>
          ⛓ Chain mode: Euler slip check replaced by chain working load check.
          Belt ply calculation skipped. Configure chain series in Head &amp; Tail Pulley.
        </div>
      )}

      <SectionHead label="Process Requirements" />
      <Row2>
        <F label="Required Capacity" name="Q_req" value={inp.Q_req}
          onChange={setField} unit="t/h" min={1} max={5000} step={1} />
        <F label="Lift Height" name="H_m" value={inp.H_m}
          onChange={setField} unit="m" min={1} max={200} step={0.5} />
      </Row2>
      <F label="Bucket Fill Factor" name="fill_pct" value={inp.fill_pct}
        onChange={setField} unit="%" min={30} max={100} step={5}
        note="Grain 75–90% · Minerals 60–75% · Cohesive 40–65%" />
      {/* 3.8 — Dynamic fill efficiency advisory */}
      {df && (
        <div style={{
          background: "rgba(74,158,255,.06)", border: "1px solid rgba(74,158,255,.2)",
          borderRadius: 5, padding: "8px 12px", marginTop: -4, marginBottom: 12,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".05em",
            color: T.primary, marginBottom: 4 }}>
            ● DYNAMIC FILL ADVISORY (CEMA §6)
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 4 }}>
            {[
              ["Min",         `${r.min_fill_pct ?? "—"}%`],
              ["Recommended", `${df.recommended_fill_pct}%`],
              ["Your value",  `${inp.fill_pct}%`],
              ["Max",         `${r.max_fill_pct ?? "—"}%`],
              ["Spacing",     `${df.current_spacing_mm}mm`],
              ["Optimal",     `${df.optimal_spacing_mm}mm`],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700,
                  color: l === "Your value"
                    ? (inp.fill_pct >= (r.min_fill_pct ?? 0) && inp.fill_pct <= (r.max_fill_pct ?? 100) ? T.success : T.danger)
                    : l === "Recommended" ? T.primary : T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
          {/* Operating range bar */}
          {r.min_fill_pct != null && r.max_fill_pct != null && (() => {
            const mn = r.min_fill_pct, mx = r.max_fill_pct;
            const rec = df.recommended_fill_pct, uv = inp.fill_pct;
            const pct = v => Math.min(100, Math.max(0, (v - 30) / 70 * 100));
            const inRange = uv >= mn && uv <= mx;
            return (
              <div style={{ position: "relative", height: 8, borderRadius: 4,
                background: "var(--surface2)", margin: "6px 0", overflow: "visible" }}>
                <div style={{ position: "absolute", top: 0, bottom: 0,
                  left: `${pct(mn)}%`, width: `${pct(mx) - pct(mn)}%`,
                  background: "rgba(74,158,255,.22)", borderRadius: 4 }} />
                <div style={{ position: "absolute", top: -2, bottom: -2, width: 2,
                  left: `${pct(rec)}%`, background: T.primary, borderRadius: 1 }} />
                <div style={{ position: "absolute", top: -3, width: 14, height: 14,
                  borderRadius: "50%", transform: "translateX(-50%)",
                  left: `${pct(uv)}%`,
                  background: inRange ? T.success : T.danger,
                  border: "2px solid var(--bg)" }} />
              </div>
            );
          })()}
          <div style={{ fontSize: 10, color: T.text3, lineHeight: 1.4 }}>{df.note}</div>
          {df.spacing_status !== "optimal" && (
            <div style={{ fontSize: 10, color: T.warning, marginTop: 3 }}>
              ⚠ Spacing is {df.spacing_status.replace("_"," ")} — adjust Bucket Spacing Gap to approach {df.optimal_spacing_mm}mm
            </div>
          )}
        </div>
      )}

      <SectionHead label="Material" />
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: T.text2,
          marginBottom: 5 }}>Material Database Search</div>
        <MaterialSearchDropdown matId={inp.mat_id}
          onChange={v => setField("mat_id", v)} />
      </div>

      <SectionHead label="Custom / Override Properties" />
      <div style={{ fontSize: 11, color: T.text3, marginBottom: 10, lineHeight: 1.5 }}>
        Leave at 0 / –1 to use database values.
        Override individual properties for site-specific conditions.
      </div>
      <F label="Custom Display Name" name="custom_mat_name" type="text"
        value={inp.custom_mat_name || ""} onChange={setField}
        note="Optional — shown in reports when overrides are active" />
      <Row2>
        <F label="Bulk Density" name="custom_rho" value={inp.custom_rho}
          onChange={setField} unit="kg/m³" min={0} max={5000} step={10}
          note="0 = DB value" />
        <F label="Angle of Repose" name="custom_aor" value={inp.custom_aor ?? 0}
          onChange={setField} unit="°" min={0} max={90} step={1}
          note="0 = DB value" />
      </Row2>
      <Row2>
        <F label="Abrasiveness 1–7" name="custom_abr" value={inp.custom_abr ?? 0}
          onChange={setField} min={0} max={7} step={1}
          note="0=DB  1=Low  7=V.High" />
        <F label="Flowability 1–4" name="custom_flowability"
          value={inp.custom_flowability ?? 0} onChange={setField}
          min={0} max={4} step={1} note="0=DB  1=Free  4=Sluggish" />
      </Row2>
      <Row2>
        <F label="Moisture %" name="custom_moisture"
          value={inp.custom_moisture ?? -1} onChange={setField}
          unit="%" min={-1} max={100} step={1} note="–1 = DB value" />
        <F label="Cohesion kPa" name="custom_cohesion"
          value={inp.custom_cohesion ?? -1} onChange={setField}
          unit="kPa" min={-1} max={100} step={0.1} note="–1 = DB value" />
      </Row2>
    </>
  );
}

function PulleyEdit({ inp, setField, results }) {
  const r = results || {};
  const shaftD  = r.d_mm ?? 0;
  const boreMin = shaftD > 0 ? Math.floor(shaftD / 5) * 5 : 0;
  const boreMax = boreMin > 0 ? boreMin + 80 : 9999;
  const autoBrg = shaftD > 0
    ? `bore ≥ ${boreMin}mm  L10=${(r.L10 ?? 0).toLocaleString()}h`
    : null;

  return (
    <>
      <SectionHead label="Head Pulley" />
      <Row2>
        <F label="Head Pulley Dia." name="D_mm" value={inp.D_mm}
          onChange={setField} unit="mm" min={100} max={1500} step={25} />
        <F label="Shaft Speed" name="n_rpm" value={inp.n_rpm}
          onChange={setField} unit="rpm" min={10} max={300} step={5} />
      </Row2>
      {/* v1.9.0: wrap angle is DERIVED from pulley geometry, not a free input.
          The geometric wrap for a standard 2-pulley elevator is always ≈180°.
          A snub pulley adds ~30°, increasing belt-to-pulley contact.            */}
      <div style={{
        background: T.panel2, border: `1px solid ${T.border}`,
        borderRadius: 5, padding: "10px 12px", marginBottom: 12,
      }}>
        <div style={{ fontSize: 10, color: T.text3, marginBottom: 6,
          letterSpacing: ".04em", textTransform: "uppercase", fontWeight: 600 }}>
          Wrap Angle (derived)
        </div>
        <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 9, color: T.text3 }}>Geometric</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: T.text,
              fontFamily: "JetBrains Mono,monospace" }}>
              {r.wrap_geom_deg != null ? `${r.wrap_geom_deg}°` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: T.text3 }}>Effective</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: T.primary,
              fontFamily: "JetBrains Mono,monospace" }}>
              {r.wrap_effective_deg != null ? `${r.wrap_effective_deg}°` : "—"}
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: T.text3 }}>Formula</div>
            <div style={{ fontSize: 10, color: T.text3, lineHeight: 1.4 }}>
              180° + 2·arcsin((R_H−R_B)/C)
            </div>
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <F label="Snub pulley on return side (+30°)" name="snub_pulley"
            type="toggle" value={inp.snub_pulley ?? false} onChange={setField}
            note="Adds one snub pulley. Use when Euler check requires wrap > 180°." />
        </div>
        {(inp.snub_pulley ?? false) && (
          <div style={{ fontSize: 10, color: T.success, marginTop: 4 }}>
            Snub active — effective wrap ≈ {r.wrap_effective_deg != null ? `${r.wrap_effective_deg}°` : "210°"}
          </div>
        )}
      </div>
      {/* 3.9 — Wrap angle recommendation */}
      {(() => {
        const wr = results?.wrap_recommendation;
        if (!wr) return null;
        const effective_wrap = r.wrap_effective_deg ?? inp.wrap_deg ?? 180;
        const adequate = effective_wrap >= wr.required_deg;
        return (
          <div style={{
            background: adequate ? "rgba(31,184,110,.07)" : "rgba(217,142,0,.10)",
            border: `1px solid ${adequate ? "rgba(31,184,110,.25)" : "rgba(217,142,0,.35)"}`,
            borderRadius: 5, padding: "8px 12px", marginTop: -4, marginBottom: 12,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".05em",
              color: adequate ? T.success : T.warning, marginBottom: 4 }}>
              {adequate ? "✓ WRAP ANGLE ADEQUATE" : "⚠ WRAP ANGLE — SLIP RISK"}
            </div>
            <div style={{ display: "flex", gap: 16, marginBottom: 4 }}>
              {[
                ["Required", `${wr.required_deg}°`],
                ["Current",  r.wrap_effective_deg != null ? `${r.wrap_effective_deg}°` : `${inp.wrap_deg || 180}°`],
                ["Config",   wr.config],
              ].map(([l, v]) => (
                <div key={l}>
                  <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                  <div style={{ fontSize: 13, fontWeight: 700,
                    color: l === "Required" && !adequate ? T.warning : T.text,
                    fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
                </div>
              ))}
            </div>
            {!adequate && (
              <div style={{ fontSize: 10, color: T.warning, lineHeight: 1.4 }}>
                {wr.recommendation}
              </div>
            )}
          </div>
        );
      })()}

      <SectionHead label="Boot (Tail) Pulley" />
      <F label="Match head pulley diameter" name="boot_pulley_same_as_head"
        type="toggle" value={inp.boot_pulley_same_as_head ?? false}
        onChange={setField} />
      {!inp.boot_pulley_same_as_head && (() => {
        const headBootRatio = inp.D_mm / Math.max(inp.boot_pulley_D_mm, 1);
        const ratioOk = headBootRatio <= 2.0;
        return (
          <F label="Boot Pulley Diameter" name="boot_pulley_D_mm"
            value={inp.boot_pulley_D_mm} onChange={setField}
            unit="mm" min={100} max={1000} step={25}
            note={
              <span style={{ color: ratioOk ? undefined : T.warning }}>
                Head:Boot ratio = {headBootRatio.toFixed(2)}
                {" "}(CEMA §3.2 limit ≤ 2.00){!ratioOk ? " ⚠" : ""}
              </span>
            } />
        );
      })()}
      {inp.boot_pulley_same_as_head && (
        <div style={{ fontSize: 12, color: T.success, padding: "4px 0 8px" }}>
          Boot locked to head: {inp.D_mm} mm
        </div>
      )}

      <SectionHead label="Head Shaft Bearing" />
      {shaftD > 0 && (
        <div style={{
          background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 5,
          padding: "8px 12px", marginBottom: 10,
          display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11,
        }}>
          {[
            ["Calc shaft d",  `${shaftD.toFixed(1)} mm`],
            ["L10",           `${(r.L10 ?? 0).toLocaleString()} h`],
            ["Radial load",   r.R_headshaft != null ? `${(r.R_headshaft/1000).toFixed(1)} kN` : "—"],
          ].map(([l, v]) => (
            <div key={l}>
              <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
            </div>
          ))}
        </div>
      )}
      <ComponentPicker
        path="/components/bearings"
        params={{ bore_min: boreMin, bore_max: boreMax }}
        valueField="name"
        formatLabel={row =>
          `${row.name}  bore=${row.bore}mm  C=${row.C}kN  ${row.type ?? ""}  ${row.seal ?? ""}`
        }
        value={inp.bearing_name ?? ""}
        name="bearing_name"
        onChange={setField}
        autoLabel={autoBrg}
        label="Bearing Selection"
        note={`Showing bore ${boreMin}–${boreMax} mm. Select to override auto-pick.`}
      />

      <SectionHead label="Pulley Shell Thickness" />
      {results?.pulley_shell && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          marginBottom: 10, border: `1px solid ${T.border}`,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            {[
              ["CEMA min", `${results.pulley_shell.t_cema_mm} mm`],
              ["Pressure min", `${results.pulley_shell.t_pressure_mm} mm`],
              ["Governing", `${results.pulley_shell.t_governing_mm} mm`],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      <F label="Shell Thickness Override" name="pulley_shell_t_override_mm"
        value={inp.pulley_shell_t_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={50} step={1}
        note={results?.pulley_shell?.override_applied
          ? (results.pulley_shell.override_pass
              ? `✓ ${results.pulley_shell.t_use_mm}mm meets calculated minimum ${results.pulley_shell.t_calc_mm}mm`
              : `⚠ ${results.pulley_shell.t_use_mm}mm is BELOW calculated minimum ${results.pulley_shell.t_calc_mm}mm`)
          : "0 = auto from CEMA Pulley Standard minimum + belt-pressure check. Specify to verify a standard plate gauge."} />
    </>
  );
}

// ── Chain catalogue (mirrors backend CHAIN_SERIES) ───────────────────────────
const CHAIN_OPTIONS = [
  { id:"N102B", label:"N-102B  — 4\" std  WL=4,990kg  1 strand", pitch:101.6, strands:1 },
  { id:"S102B", label:"S-102B  — 4\" heavy WL=6,804kg  1 strand", pitch:101.6, strands:1 },
  { id:"S110",  label:"S-110   — 6\" heavy WL=12,474kg 1 strand", pitch:152.4, strands:1 },
  { id:"ER856", label:"ER-856  — 6\" MDC   WL=18,144kg 1 strand", pitch:152.4, strands:1 },
  { id:"ER857", label:"ER-857  — 6\" MDC   WL=22,680kg 1 strand", pitch:152.4, strands:1 },
  { id:"ER859", label:"ER-859  — 6\" SC    WL=31,750kg 2 strands", pitch:152.4, strands:2 },
  { id:"C6102", label:"6102-1/2 — 12\" SC   WL=27,215kg 2 strands", pitch:304.8, strands:2 },
  { id:"C9124", label:"9124    — 9\" SC    WL=38,100kg 2 strands", pitch:228.6, strands:2 },
];

function ChainEdit({ inp, setField, results }) {
  const r  = results || {};
  const cs = r.chain_selected ?? null;
  const sp = r.sprocket ?? null;

  const inputStyle = {
    background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 5,
    color: T.text, fontFamily: "JetBrains Mono,monospace", fontSize: 13,
    padding: "7px 10px", width: "100%", boxSizing: "border-box", cursor: "pointer",
  };

  return (
    <>
      <SectionHead label="Chain Selection" />
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: T.text2, marginBottom: 4 }}>
          Chain Series
        </div>
        <select value={inp.chain_series ?? ""} onChange={e => setField("chain_series", e.target.value)}
          style={inputStyle}>
          <option value="">Auto — select by pull force</option>
          {CHAIN_OPTIONS.map(c => (
            <option key={c.id} value={c.id}>{c.label}</option>
          ))}
        </select>
        {cs && (
          <div style={{ fontSize: 10, color: T.success, marginTop: 4 }}>
            ✓ Selected: {cs.name} — pull {r.chain_pull_N != null
              ? (r.chain_pull_N/1000).toFixed(1) : "—"}kN  SF={r.chain_SF_actual?.toFixed(2) ?? "—"}
          </div>
        )}
      </div>

      <Row2>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: T.text2, marginBottom: 4 }}>
            No. of Strands
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {[1, 2].map(n => (
              <button key={n} onClick={() => setField("chain_n_strands", n)} style={{
                flex: 1, padding: "7px 4px", borderRadius: 5, cursor: "pointer",
                fontFamily: "inherit", fontSize: 13, fontWeight: 600,
                border: `1px solid ${(inp.chain_n_strands ?? 1) === n ? T.primary : T.border}`,
                background: (inp.chain_n_strands ?? 1) === n
                  ? "rgba(74,158,255,.15)" : T.panel2,
                color: (inp.chain_n_strands ?? 1) === n ? T.primary : T.text3,
              }}>{n === 1 ? "1 — Single" : "2 — SC Double"}</button>
            ))}
          </div>
        </div>
        <F label="Chain SF" name="chain_sf"
          value={inp.chain_sf ?? 6.0} onChange={setField}
          min={3} max={12} step={0.5}
          note="CEMA default 6.0; 8.0 for shock/abrasive" />
      </Row2>

      <SectionHead label="Sprocket" />
      <F label="Sprocket Teeth Override" name="chain_sprocket_teeth"
        value={inp.chain_sprocket_teeth ?? 0} onChange={setField}
        min={0} max={32} step={1}
        note="0 = auto from D_mm. Recommend 10–20 teeth for smooth chain engagement." />
      {sp && (
        <div style={{
          background: T.panel2, border: `1px solid ${sp.smooth ? T.border : T.warning}`,
          borderRadius: 5, padding: "8px 12px", marginBottom: 10, fontSize: 11,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            {[
              ["PD",     `${sp.PD_mm} mm`],
              ["Teeth",  `${sp.n_teeth}`],
              ["Smooth", sp.smooth ? "✓ Yes" : "⚠ No"],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
          {!sp.smooth && (
            <div style={{ fontSize: 10, color: T.warning, marginTop: 4 }}>
              ⚠ {sp.note}
            </div>
          )}
        </div>
      )}

      <SectionHead label="Chain Speed Check" />
      {r.chain_v_ok != null && (
        <div style={{
          fontSize: 11, padding: "6px 10px", borderRadius: 5, marginBottom: 8,
          background: r.chain_v_ok ? "rgba(31,184,110,.08)" : "rgba(224,82,82,.10)",
          border: `1px solid ${r.chain_v_ok ? "rgba(31,184,110,.3)" : "rgba(224,82,82,.3)"}`,
          color: r.chain_v_ok ? T.success : T.danger,
        }}>
          {r.chain_v_ok
            ? `✓ Speed ${r.v?.toFixed(2) ?? "—"} m/s ≤ chain rated ${cs?.v_max_ms ?? "—"} m/s`
            : `⚠ Speed ${r.v?.toFixed(2) ?? "—"} m/s EXCEEDS chain rated ${cs?.v_max_ms ?? "—"} m/s`}
        </div>
      )}
    </>
  );
}

function BeltEdit({ inp, setField, results }) {
  const r  = results || {};
  const tp = r.tension_profile || {};
  // item 4: belt_ply is sized off F_eff (lumped effective tension at the
  // head), not T_max_N (actual peak tension, which includes the empty-leg
  // self-weight contribution). rating_margin flags when this matters —
  // surfacing both numbers here so the gap is visible rather than hidden.
  const marginBad = tp.rating_margin != null && tp.rating_margin < 1.0;
  return (
    <>
      <SectionHead label="Belt Configuration" />
      <div style={{
        background: T.panel2, border: `1px solid ${T.border}`,
        borderRadius: 5, padding: "10px 12px", marginBottom: 6, fontSize: 12,
      }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {[
            ["Auto Width", `${r.belt_w ?? "—"} mm`],
            ["Plies", `${r.belt_ply ?? "—"}`],
            ["Eff. Tension  (sizing basis)", `${r.F_eff != null ? (r.F_eff/1000).toFixed(1) : "—"} kN`],
          ].map(([l,v]) => (
            <div key={l}>
              <div style={{ fontSize: 10, color: T.text3 }}>{l}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
      {tp.T_max_N != null && (
        <div style={{
          background: marginBad ? "rgba(224,82,82,.08)" : T.panel2,
          border: `1px solid ${marginBad ? "var(--danger-border, #4a1515)" : T.border}`,
          borderRadius: 5, padding: "8px 12px", marginBottom: 12, fontSize: 11,
        }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: marginBad ? 6 : 0 }}>
            <div>
              <div style={{ fontSize: 9, color: T.text3 }}>Peak Tension  (actual max, full loop)</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{(tp.T_max_N/1000).toFixed(1)} kN</div>
            </div>
            <div>
              <div style={{ fontSize: 9, color: T.text3 }}>Belt Rated</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{tp.belt_rated_N != null ? (tp.belt_rated_N/1000).toFixed(1) : "—"} kN</div>
            </div>
            <div>
              <div style={{ fontSize: 9, color: T.text3 }}>Margin</div>
              <div style={{ fontSize: 13, fontWeight: 700,
                color: marginBad ? "var(--danger, #e05252)" : T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{tp.rating_margin ?? "—"}</div>
            </div>
          </div>
          {marginBad && (
            <div style={{ fontSize: 10, color: "var(--danger, #e05252)" }}>
              ⚠ Ply count above is sized for effective tension only — peak tension
              (including empty-leg self-weight) exceeds belt rating. Increase belt
              width or specify a higher ply count manually.
            </div>
          )}
        </div>
      )}
      <F label="Belt Width Override" name="belt_width_override_mm"
        value={inp.belt_width_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={1500} step={25}
        note="0 = auto-select from bucket width. Set > 0 to specify exact width." />
      <F label="Belt Type" name="belt_type" type="select"
        value={inp.belt_type ?? "EP"} onChange={setField}
        options={[
          { value: "EP", label: "EP — Fabric ply (standard)" },
          { value: "ST", label: "ST — Steel cord (high tension)" },
        ]}
        note="ST belts use herringbone lagging — not diamond groove" />
      <F label="Belt Cover Grade" name="belt_grade" type="select"
        value={inp.belt_grade ?? ""} onChange={setField}
        options={[
          { value: "",  label: "Auto — solver selects grade" },
          { value: "M", label: "M — Abrasion resistant (DIN 22102 Grade M)" },
          { value: "N", label: "N — General duty (DIN 22102 Grade N)" },
          { value: "W", label: "W — Oil and heat resistant" },
        ]}
        note="Grade M for abrasive materials (abr ≥ 4). Grade N for grain/light minerals." />
    </>
  );
}

// ── Bucket catalogue data (mirrors backend BUCKET_SERIES) ────────────────────
const BUCKET_CATALOG = {
  AA: {
    label: "AA — General Purpose Centrifugal",
    discharge: "centrifugal",
    desc: "Curved bottom, reinforced lip. Grain, aggregate, sand, coal, fertiliser.",
    sizes: [
      { id:"AA_6x4",  label:"AA 6×4  — 0.85 L  (W=152mm)", W:152, P:102, V:0.85 },
      { id:"AA_8x5",  label:"AA 8×5  — 1.98 L  (W=203mm)", W:203, P:127, V:1.98 },
      { id:"AA_10x6", label:"AA 10×6 — 3.40 L  (W=254mm)", W:254, P:152, V:3.40 },
      { id:"AA_12x7", label:"AA 12×7 — 5.38 L  (W=305mm)", W:305, P:178, V:5.38 },
      { id:"AA_14x8", label:"AA 14×8 — 9.06 L  (W=356mm)", W:356, P:203, V:9.06 },
      { id:"AA_16x8", label:"AA 16×8 — 10.21 L (W=406mm)", W:406, P:203, V:10.21},
      { id:"AA_18x8", label:"AA 18×8 — 11.33 L (W=457mm)", W:457, P:203, V:11.33},
      { id:"AA_18x10",label:"AA 18×10 — 17.84 L (W=457mm)",W:457, P:254, V:17.84},
    ],
  },
  AC: {
    label: "AC — Mill Duty (50° front, Added Capacity)",
    discharge: "centrifugal",
    desc: "Hooded back, 50° face angle. Cement, clinker, ore, shale, coal, asphalt.",
    sizes: [
      { id:"AC_12x8",  label:"AC 12×8×8  — 8.58 L  (W=305mm)", W:305, P:203, V:8.58 },
      { id:"AC_14x8",  label:"AC 14×8×8  — 10.08 L (W=356mm)", W:356, P:203, V:10.08},
      { id:"AC_16x8",  label:"AC 16×8×8  — 11.55 L (W=406mm)", W:406, P:203, V:11.55},
      { id:"AC_18x10", label:"AC 18×10×10 — 19.57 L (W=457mm)",W:457, P:254, V:19.57},
      { id:"AC_20x10", label:"AC 20×10×10 — 21.75 L (W=508mm)",W:508, P:254, V:21.75},
      { id:"AC_24x10", label:"AC 24×10×10 — 26.08 L (W=610mm)",W:610, P:254, V:26.08},
    ],
  },
  C: {
    label: "C — Wet / Sticky / Powdered (low profile)",
    discharge: "centrifugal",
    desc: "Open front, angled sides. Sugar, salt, wet grain, clay, flour, chemicals.",
    sizes: [
      { id:"C_6x4",  label:"C 6×4×4  — 0.74 L (W=152mm)", W:152, P:114, V:0.74 },
      { id:"C_8x4",  label:"C 8×4×4  — 0.99 L (W=203mm)", W:203, P:114, V:0.99 },
      { id:"C_10x5", label:"C 10×5×4 — 1.47 L (W=254mm)", W:254, P:127, V:1.47 },
      { id:"C_14x7", label:"C 14×7×5 — 3.91 L (W=356mm)", W:356, P:178, V:3.91 },
      { id:"C_16x7", label:"C 16×7×5 — 4.47 L (W=406mm)", W:406, P:178, V:4.47 },
    ],
  },
  MF: {
    label: "MF — Continuous Medium Front (30°)",
    discharge: "continuous",
    desc: "Gentle handling, CR < 1.0. Gypsum, cement, pellets, grain, salt, fertiliser.",
    sizes: [
      { id:"MF_10x7",  label:"MF 10×7×11  — 5.10 L  (W=254mm)", W:254, P:178, V:5.10 },
      { id:"MF_12x7",  label:"MF 12×7×11  — 6.17 L  (W=305mm)", W:305, P:178, V:6.17 },
      { id:"MF_12x8",  label:"MF 12×8×11  — 7.79 L  (W=305mm)", W:305, P:203, V:7.79 },
      { id:"MF_14x8",  label:"MF 14×8×11  — 9.20 L  (W=356mm)", W:356, P:203, V:9.20 },
      { id:"MF_16x8",  label:"MF 16×8×11  — 10.62 L (W=406mm)", W:406, P:203, V:10.62},
      { id:"MF_18x8",  label:"MF 18×8×11  — 11.89 L (W=457mm)", W:457, P:203, V:11.89},
      { id:"MF_24x10", label:"MF 24×10×11 — 24.07 L (W=610mm)", W:610, P:254, V:24.07},
    ],
  },
  HF: {
    label: "HF — Continuous High Front (45°)",
    discharge: "continuous",
    desc: "Higher front than MF, ~8% more capacity. Grain, gypsum, pellets, fragile materials.",
    sizes: [
      { id:"HF_10x7",  label:"HF 10×7×11 — 5.38 L  (W=254mm)", W:254, P:178, V:5.38 },
      { id:"HF_12x7",  label:"HF 12×7×11 — 6.80 L  (W=305mm)", W:305, P:178, V:6.80 },
      { id:"HF_14x7",  label:"HF 14×7×11 — 7.93 L  (W=356mm)", W:356, P:178, V:7.93 },
      { id:"HF_14x8",  label:"HF 14×8×11 — 9.91 L  (W=356mm)", W:356, P:203, V:9.91 },
      { id:"HF_16x8",  label:"HF 16×8×11 — 11.19 L (W=406mm)", W:406, P:203, V:11.19},
      { id:"HF_18x8",  label:"HF 18×8×11 — 12.83 L (W=457mm)", W:457, P:203, V:12.83},
    ],
  },
  SC: {
    label: "SC — Super Capacity (Double Chain only)",
    discharge: "continuous",
    desc: "Very slow, heavy abrasive duty. Cement, clinker, limestone, rock. DOUBLE CHAIN only.",
    sizes: [
      { id:"SC_12x8",  label:"SC 12×8×11 — 15.3 L  (W=305mm)", W:305, P:222, V:15.29},
      { id:"SC_14x8",  label:"SC 14×8×11 — 17.8 L  (W=356mm)", W:356, P:222, V:17.84},
      { id:"SC_16x8",  label:"SC 16×8×11 — 20.4 L  (W=406mm)", W:406, P:222, V:20.39},
      { id:"SC_18x8",  label:"SC 18×8×11 — 22.9 L  (W=457mm)", W:457, P:222, V:22.94},
      { id:"SC_20x8",  label:"SC 20×8×11 — 25.5 L  (W=508mm)", W:508, P:222, V:25.49},
      { id:"SC_20x12", label:"SC 20×12×17 — 54.9 L (W=508mm)", W:508, P:324, V:54.93},
      { id:"SC_24x12", label:"SC 24×12×17 — 66.0 L (W=610mm)", W:610, P:324, V:65.98},
      { id:"SC_30x12", label:"SC 30×12×17 — 82.4 L (W=762mm)", W:762, P:324, V:82.40},
    ],
  },
};

// Derive current style from bucket_id
function styleFromId(bucket_id) {
  for (const [style, data] of Object.entries(BUCKET_CATALOG)) {
    if (data.sizes.some(s => s.id === bucket_id)) return style;
  }
  // Legacy ID fallback
  if (!bucket_id) return "AA";
  const upper = bucket_id.toUpperCase();
  if (upper.startsWith("AA")) return "AA";
  if (upper.startsWith("AC")) return "AC";
  if (upper.startsWith("SC")) return "SC";
  if (upper.startsWith("MF")) return "MF";
  if (upper.startsWith("HF")) return "HF";
  if (upper.startsWith("C_") || upper === "C") return "C";
  return "AA";
}

function BucketEdit({ inp, setField, results }) {
  const [selectedStyle, setSelectedStyle] = useState(styleFromId(inp.bucket_id) || "AA");
  const styleData = BUCKET_CATALOG[selectedStyle] || BUCKET_CATALOG["AA"];

  // ── Belt width constraint ───────────────────────────────────────────────
  // Bucket width (W) must fit within belt with CEMA minimum 25mm clearance
  // each side → max bucket W = belt_width − 50mm.
  // Source: belt_width_override if set, else auto-selected width from results.
  const resolvedBeltW = inp.belt_width_override_mm > 0
    ? inp.belt_width_override_mm
    : (results?.belt_w ?? results?.belt_width_mm ?? null);
  const maxBucketW = resolvedBeltW ? resolvedBeltW - 50 : 9999;
  const filteredSizes = styleData.sizes.filter(s => s.W <= maxBucketW);
  const hiddenCount   = styleData.sizes.length - filteredSizes.length;
  const sizesToShow   = filteredSizes.length > 0 ? filteredSizes : styleData.sizes; // fallback

  // When style changes, auto-select the middle size within filtered list
  const handleStyleChange = (newStyle) => {
    setSelectedStyle(newStyle);
    const sizes = BUCKET_CATALOG[newStyle]?.sizes.filter(s => s.W <= maxBucketW) || [];
    const fallback = BUCKET_CATALOG[newStyle]?.sizes || [];
    const pool = sizes.length ? sizes : fallback;
    if (pool.length) {
      const mid = pool[Math.floor(pool.length / 2)];
      setField("bucket_id", mid.id);
      setField("auto_bucket", false);
    }
  };

  const currentSize = sizesToShow.find(s => s.id === inp.bucket_id)
    || sizesToShow[Math.floor(sizesToShow.length / 2)];

  const inputStyle = {
    background: "var(--panel2,#132238)", border: "1px solid var(--border,#1c3050)",
    borderRadius: 5, color: "var(--text,#ddeaf6)", fontFamily: "JetBrains Mono,monospace",
    fontSize: 14, padding: "7px 10px", width: "100%", boxSizing: "border-box",
    cursor: "pointer",
  };

  return (
    <>
      <SectionHead label="Auto-Select" />
      <F label="Auto-select smallest adequate series" name="auto_bucket"
        type="toggle" value={inp.auto_bucket} onChange={setField}
        note="Auto picks the smallest size that meets Q_req at current speed and fill" />

      {/* 3.7 — Bucket recommendation card */}
      {results?.bucket_recommendation && (() => {
        const rec = results.bucket_recommendation;
        const isCurrent = styleFromId(inp.bucket_id) === rec.recommended_style;
        return (
          <div style={{
            background: isCurrent ? "rgba(31,184,110,.08)" : "rgba(74,158,255,.07)",
            border: `1px solid ${isCurrent ? "rgba(31,184,110,.3)" : "rgba(74,158,255,.3)"}`,
            borderRadius: 5, padding: "10px 12px", marginBottom: 12,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".05em",
              color: isCurrent ? T.success : T.primary, marginBottom: 4 }}>
              {isCurrent ? "✓ CURRENT STYLE MATCHES RECOMMENDATION" : "● RECOMMENDATION FOR THIS MATERIAL"}
            </div>
            <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>
              {rec.recommended_style} style
              {rec.alternative_style !== rec.recommended_style && (
                <span style={{ fontSize: 10, color: T.text3, fontWeight: 400, marginLeft: 8 }}>
                  (alt: {rec.alternative_style})
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: T.text3, lineHeight: 1.5, marginBottom: rec.notes?.length ? 6 : 0 }}>
              {rec.reasoning}
            </div>
            {rec.notes?.map((n, i) => (
              <div key={i} style={{ fontSize: 10, color: T.warning, marginTop: 3 }}>⚠ {n}</div>
            ))}
          </div>
        );
      })()}

      <SectionHead label="Bucket Style" />
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text2,#b0c4d8)",
          marginBottom: 5 }}>Style</div>
        <select value={selectedStyle} onChange={e => handleStyleChange(e.target.value)}
          style={inputStyle}>
          {Object.entries(BUCKET_CATALOG).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <div style={{ fontSize: 10, color: "var(--text3,#5a7a9a)", marginTop: 5,
          lineHeight: 1.5 }}>
          {styleData.desc}
          {styleData.discharge === "continuous" && (
            <span style={{ color: "var(--primary,#4a9eff)", marginLeft: 6 }}>
              ● Continuous discharge — CR must be &lt; 1.0
            </span>
          )}
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text2,#b0c4d8)", flex: 1 }}>
            Size {!inp.auto_bucket && "(locked)"}
          </div>
          {resolvedBeltW && (
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 999,
              background: "rgba(74,158,255,.12)", color: "var(--primary,#4a9eff)",
              border: "1px solid rgba(74,158,255,.3)",
            }}>
              Belt {resolvedBeltW}mm → max W={maxBucketW}mm
            </span>
          )}
        </div>
        <select
          value={inp.bucket_id}
          disabled={inp.auto_bucket}
          onChange={e => { setField("bucket_id", e.target.value); setField("auto_bucket", false); }}
          style={{ ...inputStyle, opacity: inp.auto_bucket ? 0.5 : 1 }}>
          {sizesToShow.map(s => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
        {hiddenCount > 0 && (
          <div style={{ fontSize: 10, color: "var(--warning,#d98e00)", marginTop: 4 }}>
            ⚠ {hiddenCount} size{hiddenCount > 1 ? "s" : ""} hidden —
            wider than belt ({resolvedBeltW}mm − 50mm clearance).
            Increase belt width override to unlock them.
          </div>
        )}
        {inp.auto_bucket && (
          <div style={{ fontSize: 10, color: "var(--success,#1fb86e)", marginTop: 4 }}>
            Auto-select active — disable toggle above to pick a specific size
          </div>
        )}
      </div>

      {/* Size summary card */}
      {currentSize && !inp.auto_bucket && (
        <div style={{
          background: "var(--panel2,#132238)", border: "1px solid var(--border,#1c3050)",
          borderRadius: 5, padding: "10px 12px", marginBottom: 12, fontSize: 12,
        }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {[
              ["Width",     `${currentSize.W} mm`],
              ["Projection",`${currentSize.P} mm`],
              ["Volume",    `${currentSize.V} L`],
              ["Style",     selectedStyle],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 10, color: "var(--text3,#5a7a9a)" }}>{l}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text,#ddeaf6)",
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <SectionHead label="Spacing" />
      <F label="Bucket Spacing Gap" name="bucket_gap"
        value={inp.bucket_gap} onChange={setField}
        unit="mm" min={0} max={200} step={5}
        note="Gap added beyond bucket projection for spacing. CEMA default 25mm. Continuous elevators typically 0mm." />

      <SectionHead label="Plate Thickness" />
      {results?.bucket_thickness && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          marginBottom: 10, border: `1px solid ${T.border}`, fontSize: 12,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            {[
              ["Catalogue gauge", `${results.bucket_thickness.t_implied_mm} mm`],
              ["Specified", `${results.bucket_thickness.t_override_mm} mm`],
              ["Mass", `${results.bucket_thickness.mass_scaled_kg} kg`],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      <F label="Plate Thickness Override" name="bucket_thickness_override_mm"
        value={inp.bucket_thickness_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={20} step={0.5}
        note="0 = catalogue standard gauge for the selected series. Heavier gauge adds wear allowance and dead load; mass scales linearly from catalogue reference (not independently structurally validated)." />
    </>
  );
}

function TakeupEdit({ inp, setField, results }) {
  const ts  = results?.takeup_screw     || {};
  const tg  = results?.takeup_gravity   || {};
  const th  = results?.takeup_hydraulic || {};
  return (
    <>
      <SectionHead label="Take-Up Type" />
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {["gravity","screw","hydraulic","auto"].map(v => (
          <button key={v} onClick={() => setField("takeup_type", v)} style={{
            flex: 1, padding: "8px 4px", borderRadius: 5, cursor: "pointer",
            fontFamily: "inherit", fontSize: 12, fontWeight: 600,
            border: `1px solid ${inp.takeup_type===v ? T.primary : T.border}`,
            background: inp.takeup_type===v ? "rgba(74,158,255,.15)" : T.panel2,
            color: inp.takeup_type===v ? T.primary : T.text3,
          }}>{v.charAt(0).toUpperCase()+v.slice(1)}</button>
        ))}
      </div>

      {/* Gravity summary */}
      {tg.W_counterweight_kg_gross && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          marginBottom: 12, border: `1px solid ${T.border}`, fontSize: 12,
        }}>
          <div style={{ color: T.text3, marginBottom: 4, fontWeight: 600 }}>
            Gravity Take-Up (calculated)
          </div>
          <div style={{ display: "flex", gap: 16 }}>
            {[
              ["Counterweight", `${tg.W_counterweight_kg_gross?.toFixed(0) ?? "—"} kg`],
              ["Travel",        `${tg.travel_m != null ? (tg.travel_m*1000).toFixed(0) : "—"} mm`],
            ].map(([l,v]) => (
              <div key={l}>
                <div style={{ fontSize: 10, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <SectionHead label="Screw Take-Up Overrides" />
      <Row2>
        <F label="Screw Core Dia." name="takeup_screw_d_mm"
          value={inp.takeup_screw_d_mm ?? 0} onChange={setField}
          unit="mm" min={0} max={200} step={5}
          note="0 = auto-select" />
        <F label="Screw Span" name="takeup_screw_len_m"
          value={inp.takeup_screw_len_m ?? 0} onChange={setField}
          unit="m" min={0} max={5} step={0.1}
          note="0 = auto" />
      </Row2>
      {ts.d_core_recommend_mm > 0 && (
        <div style={{ fontSize: 11, color: T.success, marginTop: -6,
          marginBottom: 10 }}>
          ✓ Recommended: {ts.d_core_recommend_mm} mm core
          (SF_buckling = {ts.SF_buckling?.toFixed(2) ?? "—"})
        </div>
      )}

      {/* Hydraulic summary — v1.9.9. Not a CEMA-defined method; vendor cylinder
          mechanics (force from pressure, Euler buckling check on the rod). */}
      {th.F_cylinder_N != null && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          marginBottom: 12, border: `1px solid ${T.border}`, fontSize: 12,
        }}>
          <div style={{ color: T.text3, marginBottom: 4, fontWeight: 600 }}>
            Hydraulic Take-Up (calculated)
          </div>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {[
              ["Cylinder Force", `${(th.F_cylinder_N/1000).toFixed(1)} kN`],
              ["Bore",           `Ø${th.d_bore_use_mm ?? "—"} mm`],
              ["Stroke",         `${th.stroke_mm ?? "—"} mm`],
              ["SF Buckling",    th.SF_buckling != null ? th.SF_buckling.toFixed(2) : "—"],
            ].map(([l,v]) => (
              <div key={l}>
                <div style={{ fontSize: 10, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
          {th.buckling_safe === false && (
            <div style={{ fontSize: 10.5, color: T.danger, marginTop: 6 }}>
              ✗ {th.recommendation}
            </div>
          )}
        </div>
      )}

      <SectionHead label="Hydraulic Take-Up Overrides" />
      <Row2>
        <F label="Cylinder Bore" name="takeup_hydraulic_bore_mm"
          value={inp.takeup_hydraulic_bore_mm ?? 0} onChange={setField}
          unit="mm" min={0} max={300} step={5}
          note="0 = auto-select" />
        <F label="Operating Pressure" name="takeup_hydraulic_pressure_bar"
          value={inp.takeup_hydraulic_pressure_bar ?? 100} onChange={setField}
          unit="bar" min={10} max={350} step={10}
          note="Match power unit rating" />
      </Row2>
      {th.d_bore_recommend_mm > 0 && (
        <div style={{ fontSize: 11, color: th.buckling_safe ? T.success : T.danger,
          marginTop: -6, marginBottom: 10 }}>
          {th.buckling_safe ? "✓" : "✗"} Recommended: Ø{th.d_bore_recommend_mm} mm bore
          (SF_buckling = {th.SF_buckling?.toFixed(2) ?? "—"})
        </div>
      )}
      <div style={{ fontSize: 10, color: T.text3, marginTop: -4, marginBottom: 8 }}>
        Hydraulic take-up sizing follows standard cylinder mechanics
        (force ÷ pressure, Euler rod buckling) — not a CEMA-defined method.
        Verify against the actual power unit and cylinder vendor spec.
      </div>
    </>
  );
}

// ── Shaft design (material grade + diameter override) — v1.9.6 ──────────────
// Previously these controls were buried inside TakeupEdit with no visible
// tree label mentioning "shaft" — moved to its own tree row so the controls
// are actually discoverable.
function ShaftEdit({ inp, setField, results }) {
  return (
    <>
      <SectionHead label="Shaft Sizing" />
      {results?.d_mm != null && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          marginBottom: 12, border: `1px solid ${T.border}`, fontSize: 12,
        }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            {[
              ["Stress",     `${results.d_stress_mm} mm`],
              ["Deflection", `${results.d_deflect_mm} mm`],
              ["Governing",  `${results.d_mm} mm`],
              ["Governed by", results.governed_by ?? "—"],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <SectionHead label="Shaft Material" />
      <F label="Shaft Material Grade" name="shaft_material" type="select"
        value={inp.shaft_material ?? "A36"} onChange={setField}
        options={[
          { value: "A36",     label: "A36 Mild Steel (τ=42 MPa) — standard" },
          { value: "1045_HR", label: "1045 Hot-Rolled (τ=52 MPa) — higher capacity" },
          { value: "1045_CD", label: "1045 Cold-Drawn (τ=70 MPa) — precision machined" },
          { value: "4140_QT", label: "4140 Q&T Alloy (τ=110 MPa) — heavy/impact duty" },
        ]}
        note={results?.shaft_material_name
          ? `Selected: ${results.shaft_material_name} · τ_allow=${results.shaft_tau_allow_MPa}MPa. Higher grades reduce required shaft diameter for the same load.`
          : "Higher grades permit a smaller shaft diameter for the same load, at higher material cost."} />

      <SectionHead label="Shaft Section" />
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        {["solid", "hollow"].map(v => (
          <button key={v} onClick={() => setField("shaft_section", v)} style={{
            flex: 1, padding: "8px 4px", borderRadius: 5, cursor: "pointer",
            fontFamily: "inherit", fontSize: 12, fontWeight: 600,
            border: `1px solid ${inp.shaft_section===v ? T.primary : T.border}`,
            background: inp.shaft_section===v ? "rgba(74,158,255,.15)" : T.panel2,
            color: inp.shaft_section===v ? T.primary : T.text3,
          }}>{v.charAt(0).toUpperCase()+v.slice(1)}</button>
        ))}
      </div>
      {inp.shaft_section === "hollow" && (
        <F label="Bore Ratio (ID/OD)" name="shaft_bore_ratio"
          value={inp.shaft_bore_ratio ?? 0.5} onChange={setField}
          min={0.1} max={0.85} step={0.05}
          note={results?.shaft_bore_ratio
            ? `OD ${results.d_mm}mm · ID≈${results.shaft_d_inner_mm}mm · ~${results.shaft_mass_saving_pct}% mass reduction vs equivalent solid shaft. Typical practice 0.4–0.7; CEMA does not mandate a ratio.`
            : "Typical hollow shaft practice: 0.4–0.7. Higher ratio = larger required OD but greater net mass savings."} />
      )}

      <SectionHead label="Hub Connection" />
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        {["keyed", "welded"].map(v => (
          <button key={v} onClick={() => setField("shaft_hub_connection", v)} style={{
            flex: 1, padding: "8px 4px", borderRadius: 5, cursor: "pointer",
            fontFamily: "inherit", fontSize: 12, fontWeight: 600,
            border: `1px solid ${inp.shaft_hub_connection===v ? T.primary : T.border}`,
            background: inp.shaft_hub_connection===v ? "rgba(74,158,255,.15)" : T.panel2,
            color: inp.shaft_hub_connection===v ? T.primary : T.text3,
          }}>{v.charAt(0).toUpperCase()+v.slice(1)}</button>
        ))}
      </div>
      {inp.shaft_hub_connection === "welded" && results?.weld_check && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          marginBottom: 10, border: `1px solid ${T.border}`, fontSize: 12,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            {[
              ["Throat", `${results.weld_check.t_throat_mm} mm`],
              ["τ actual", `${results.weld_check.tau_torsion_MPa} MPa`],
              ["τ allow", `${results.weld_check.weld_allow_MPa} MPa`],
              ["Governed by", results.weld_check.governed_by?.replace("_"," ") ?? "—"],
            ].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10, color: T.text3, marginTop: 6 }}>
            E70xx fillet weld, allowable independent of shaft material grade (weld metal governs).
          </div>
        </div>
      )}
      {inp.shaft_hub_connection === "keyed" && (
        <div style={{ fontSize: 10, color: T.text3, marginBottom: 10 }}>
          Standard ASME B17.1 keyed connection. Field-serviceable — pulley can be removed without re-welding.
        </div>
      )}

      <SectionHead label="Shaft Diameter Override" />
      <F label="Head Shaft Dia. Override" name="shaft_d_override_mm"
        value={inp.shaft_d_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={500} step={5}
        note="0 = auto from stress/deflection check. Specify to force a standard bar size." />
    </>
  );
}

function DischargeEdit({ inp, setField, results }) {
  const r  = results || {};
  const cc = r.casing_clearance || {};
  const sc = r.stream_chute     || {};
  const isHF = r.is_continuous ?? false;
  return (
    <>
      <SectionHead label="Discharge Configuration" />
      <div style={{
        background: T.panel2, borderRadius: 5, padding: "10px 12px",
        marginBottom: 14, border: `1px solid ${T.border}`, fontSize: 12,
      }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {[
            ["Type",       isHF ? "Continuous (HF)" : "Centrifugal"],
            ["CR",         r.cr != null ? Number(r.cr).toFixed(3) : "—"],
            ["θ release",  r.theta_rel != null ? `${Number(r.theta_rel).toFixed(1)}°` : "—"],
            ["Stream",     cc.clears === false ? "⚠ Strikes casing" : "✓ Clears"],
            ["Chute",      sc.intercepted ? "✓ Captured" : "⚠ Missed"],
          ].map(([l,v]) => (
            <div key={l}>
              <div style={{ fontSize: 10, color: T.text3 }}>{l}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ fontSize: 12, color: T.text3, marginBottom: 14, lineHeight: 1.6 }}>
        Discharge geometry is calculated from pulley diameter and belt speed.
        To adjust: change D_mm or n_rpm in Head &amp; Tail Pulley.
        To switch to continuous discharge (HF), select HF bucket series in Bucket Selection.
      </div>
      <SectionHead label="Chute Liner Selection" />
      <div style={{ fontSize: 11, color: T.text3, marginBottom: 8, lineHeight: 1.5 }}>
        Liner material affects wall-friction angle (φ_w = arctan μ).
        Lower-friction liners reduce the minimum chute angle required for mass flow,
        resolving funnel-flow and plugging warnings without geometry changes.
      </div>
      {/* Liner options */}
      {[
        { id: "auto",         label: "Auto",                  mu: "—",    phi: "—",   note: "CEMA wear-index selection"             },
        { id: "mild_steel",   label: "Mild Steel (unlined)",  mu: "0.55", phi: "28.8°", note: "Class 1–2, v < 1.5 m/s"            },
        { id: "ar400",        label: "AR400 Wear Plate",      mu: "0.48", phi: "25.7°", note: "Abrasive Class 3+"                  },
        { id: "nat_rubber",   label: "Natural Rubber",        mu: "0.40", phi: "21.8°", note: "Cohesive/wet materials"             },
        { id: "uhmwpe",       label: "UHMW-PE Sheet",         mu: "0.20", phi: "11.3°", note: "Sticky/cohesive — lowest min angle" },
        { id: "ceramic_tile", label: "Ceramic Tile",          mu: "0.15", phi: "8.5°",  note: "Extreme abrasion"                  },
        { id: "ptfe",         label: "PTFE Sheet",            mu: "0.10", phi: "5.7°",  note: "Very sticky materials"             },
      ].map(({ id, label, mu, phi, note }) => {
        const active = (inp.chute_liner_id ?? "auto") === id;
        return (
          <div key={id}
            onClick={() => setField("chute_liner_id", id)}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "7px 10px", marginBottom: 4, borderRadius: 5, cursor: "pointer",
              border: `1px solid ${active ? T.primary : T.border}`,
              background: active ? "rgba(74,158,255,.08)" : "transparent",
              transition: "all .15s",
            }}>
            <div style={{
              width: 14, height: 14, borderRadius: "50%", flexShrink: 0,
              border: `2px solid ${active ? T.primary : T.border}`,
              background: active ? T.primary : "transparent",
            }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: active ? 700 : 400,
                color: active ? T.text : T.text2 }}>{label}</div>
              <div style={{ fontSize: 9, color: T.text3 }}>{note}</div>
            </div>
            <div style={{ fontSize: 9, fontFamily: "JetBrains Mono,monospace",
              color: T.muted, textAlign: "right" }}>
              <div>μ = {mu}</div>
              <div>φ = {phi}</div>
            </div>
          </div>
        );
      })}
      {/* Liner effect on chute */}
      {results?.discharge_chute?.maintenance && (
        <div style={{
          background: T.panel2, border: `1px solid ${T.border}`,
          borderRadius: 5, padding: "8px 12px", marginTop: 6, fontSize: 11,
        }}>
          <span style={{ color: T.text3 }}>Current liner: </span>
          <span style={{ color: T.text, fontWeight: 600 }}>
            {results.discharge_chute.maintenance.liner_material}
            {" "}{results.discharge_chute.maintenance.liner_thickness_mm}mm
          </span>
          <span style={{ color: T.text3, marginLeft: 12 }}>Min chute angle: </span>
          <span style={{ color: T.primary, fontWeight: 600 }}>
            {results.discharge_chute?.performance?.min_angle_deg?.toFixed(1) ?? "—"}°
          </span>
        </div>
      )}

      <SectionHead label="Chute Position" />
      {/* Chute position — v1.9.9. Previously the stream interception check
          could warn "review chute position" but the UI had no control for it. */}
      <F label="Chute inlet offset from wall" name="chute_x_offset_m"
        value={inp.chute_x_offset_m ?? 0} onChange={setField}
        unit="m" min={0} max={0.5} step={0.01}
        note="Move chute inlet inward from casing wall. 0 = auto (flush - 10mm). Increase if stream misses chute." />
      <F label="Chute opening height" name="chute_opening_height_m"
        value={inp.chute_opening_height_m ?? 0} onChange={setField}
        unit="m" min={0} max={1.0} step={0.05}
        note="Vertical height of chute inlet opening. 0 = auto (derived from head pulley diameter)." />
      {/* Live stream interception feedback */}
      {results?.stream_chute && (
        <div style={{
          background: results.stream_chute.intercepted
            ? "rgba(31,184,110,.08)" : "rgba(239,68,68,.08)",
          border: `1px solid ${results.stream_chute.intercepted
            ? T.successBorder ?? "rgba(31,184,110,.3)"
            : T.dangerBorder  ?? "rgba(239,68,68,.3)"}`,
          borderRadius: 5, padding: "8px 10px", marginTop: 4, fontSize: 10,
        }}>
          {results.stream_chute.intercepted
            ? <span style={{ color: "var(--success)" }}>
                ✓ Stream intercepted — impact angle {results.stream_chute.impact_angle_deg?.toFixed(1) ?? "—"}°
              </span>
            : <span style={{ color: "var(--danger)" }}>
                ✗ Stream misses chute — increase chute inlet offset or reduce belt speed
              </span>
          }
        </div>
      )}

      <SectionHead label="Casing Width Override" />
      <F label="Belt Width Override" name="belt_width_override_mm"
        value={inp.belt_width_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={1500} step={25}
        note="Wider belt = wider casing head section. 0 = auto." />
    </>
  );
}

function FeedEdit({ inp, setField, results }) {
  const r  = results || {};
  const fd = r.feed_design ?? null;
  const isC = r.is_continuous ?? false;

  const InfoGrid = ({ items }) => (
    <div style={{
      display: "flex", gap: 14, flexWrap: "wrap",
      background: T.panel2, border: `1px solid ${T.border}`,
      borderRadius: 5, padding: "10px 12px", marginBottom: 12,
    }}>
      {items.map(([l, v, hi]) => (
        <div key={l}>
          <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
          <div style={{
            fontSize: 13, fontWeight: 700,
            color: hi ? T.primary : T.text,
            fontFamily: "JetBrains Mono,monospace",
          }}>{v}</div>
        </div>
      ))}
    </div>
  );

  if (!fd) {
    return (
      <div style={{ textAlign: "center", padding: "32px 16px" }}>
        <div style={{ fontSize: 28, marginBottom: 12 }}>⚙</div>
        <div style={{ fontSize: 14, color: T.text, marginBottom: 8, fontWeight: 700 }}>
          Feed Design
        </div>
        <div style={{ fontSize: 12, color: T.text3, lineHeight: 1.6 }}>
          Run a calculation first — boot feed geometry is computed automatically
          from material, bucket, and belt parameters.
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={{
        background: isC ? "rgba(74,158,255,.08)" : "rgba(31,184,110,.07)",
        border: `1px solid ${isC ? "rgba(74,158,255,.3)" : "rgba(31,184,110,.25)"}`,
        borderRadius: 5, padding: "10px 12px", marginBottom: 14,
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
          color: isC ? T.primary : T.success, marginBottom: 5,
        }}>
          {isC ? "⛓ CONTINUOUS — LOADING LEG" : "⚙ CENTRIFUGAL — DIGGING / SCOOPING"}
        </div>
        <div style={{ fontSize: 11, color: T.text3, lineHeight: 1.5 }}>
          {fd.loading_note}
        </div>
      </div>

      <SectionHead label="Material Flow" />
      <InfoGrid items={[
        ["Volumetric flow", `${fd.Q_volumetric_m3h} m³/h`, false],
        ["Inlet velocity",  `${fd.v_feed_mps} m/s`,        false],
        ["Inlet area req.", `${(fd.A_inlet_m2 * 10000).toFixed(1)} cm²`, false],
      ]} />

      <SectionHead label="Boot Inlet Opening" />
      <InfoGrid items={[
        ["Width",  `${fd.inlet_width_mm} mm`,  false],
        ["Height", `${fd.inlet_height_mm} mm`, true],
        ["Area",   `${(fd.A_inlet_m2 * 1e6).toFixed(0)} mm²`, false],
      ]} />
      <F label="Inlet Height Override" name="boot_inlet_height_override_mm"
        value={inp.boot_inlet_height_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={2000} step={25}
        note={`0 = auto (${fd.inlet_height_mm}mm calculated). Set to preferred standard opening.`} />

      {isC ? (
        <>
          <SectionHead label="Loading Leg" />
          <InfoGrid items={[
            ["Leg height",  `${fd.loading_leg_height_mm} mm`, true],
            ["Leg width",   `${fd.loading_leg_width_mm} mm`,  false],
            ["Spout angle", `≥ ${fd.spout_angle_deg}°`,       false],
          ]} />
          <div style={{ fontSize: 10, color: T.text3, marginBottom: 12, lineHeight: 1.5 }}>
            Spout angle ≥ AoR + 10° prevents bridging. Leg height = 2× bucket depth.
          </div>
        </>
      ) : (
        <>
          <SectionHead label="Digging Zone" />
          <InfoGrid items={[
            ["Material depth", `${fd.material_depth_mm} mm (0.75×P)`, true],
            ["Dig arc",        `${fd.dig_zone_length_mm} mm`,         false],
            ["Dig volume",     `${fd.V_dig_litres} L`,                false],
          ]} />
          <div style={{ fontSize: 10, color: T.text3, marginBottom: 12, lineHeight: 1.5 }}>
            Maintain boot material at 0.75× projection for consistent scooping.
          </div>
        </>
      )}

      <SectionHead label="Boot Surge Volume" />
      <InfoGrid items={[
        ["Surge buffer", `${fd.V_surge_litres} L`, true],
        ["Flow rate",    `${fd.Q_volumetric_m3h} m³/h`, false],
        ["Buffer time",  `${fd.t_surge_s}s`, false],
      ]} />
      <div style={{ fontSize: 10, color: T.text3, marginBottom: 12, lineHeight: 1.5 }}>
        CEMA: 3s surge buffer absorbs upstream flow fluctuations.
      </div>

      <SectionHead label="Boot Casing" />
      <InfoGrid items={[
        ["Min height",   `${fd.boot_casing_height_mm} mm`, true],
        ["Pulley R",     `${fd.boot_pulley_radius_mm} mm`, false],
        ["Bucket proj.", `${fd.bucket_projection_mm} mm`,  false],
        ["Clearance",    `${fd.clearance_mm} mm`,          false],
      ]} />

      {fd.warnings?.length > 0 && fd.warnings.map((w, i) => (
        <div key={i} style={{
          background: "rgba(217,142,0,.08)", border: "1px solid rgba(217,142,0,.3)",
          borderRadius: 5, padding: "8px 12px", marginBottom: 8,
          fontSize: 11, color: T.warning, lineHeight: 1.5,
        }}>⚠ {w}</div>
      ))}
    </>
  );
}

function CasingEdit({ inp, setField, results }) {
  const r  = results || {};
  const cp = r.casing_panel || {};
  const cs = r.casing_stiffener || {};
  return (
    <>
      <SectionHead label="Casing Plate" />
      {cp.t_calc_mm && (
        <div style={{ fontSize: 12, color: T.text3, marginBottom: 10 }}>
          Calculated minimum: <span style={{ color: T.text,
            fontWeight: 700 }}>{cp.t_calc_mm} mm</span> ·
          Stiffener pitch: <span style={{ color: T.text,
            fontWeight: 700 }}>
            {cs.recommended_mm ?? "—"} mm
          </span>
        </div>
      )}
      <F label="Plate Thickness Override" name="casing_t_override_mm"
        value={inp.casing_t_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={50} step={1}
        note="0 = auto from Timoshenko plate check. Specify to use a standard plate size." />
      <SectionHead label="Structural Loading" />
      <F label="Design Wind Pressure" name="wind_pressure_pa"
        value={inp.wind_pressure_pa ?? 800} onChange={setField}
        unit="Pa" min={0} max={5000} step={100}
        note="Used for casing panel deflection check. Typical indoor: 600–800 Pa. Outdoor: 800–1200 Pa." />
      {cp.delta_actual_mm != null && (
        <div style={{
          background: T.panel2, borderRadius: 5, padding: "10px 12px",
          border: `1px solid ${cp.status === "fail" ? T.warning : T.border}`,
          fontSize: 12,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            {[
              ["Panel δ actual", `${cp.delta_actual_mm} mm`],
              ["L/360 limit",   `${cp.delta_allow_mm} mm`],
              ["Status",        cp.status === "fail" ? "⚠ Over limit" : "✓ OK"],
            ].map(([l,v]) => (
              <div key={l}>
                <div style={{ fontSize: 10, color: T.text3 }}>{l}</div>
                <div style={{ fontSize: 13, fontWeight: 600,
                  color: l === "Status"
                    ? (cp.status === "fail" ? T.warning : T.success) : T.text,
                  fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function ServiceEdit({ inp, setField }) {
  return (
    <>
      <F label="Environment" name="environment" type="select"
        value={inp.environment ?? "dry"} onChange={setField}
        options={[
          { value: "dry",       label: "Dry — standard indoor" },
          { value: "humid",     label: "Humid — moisture > 15%" },
          { value: "wet",       label: "Wet — water spray / washdown" },
          { value: "submerged", label: "Submerged — boot below water" },
        ]}
        note="Selects lagging type and adjusts friction coefficient" />
      <F label="Pulley Lagging Friction μ" name="mu"
        value={inp.mu} onChange={setField} min={0.1} max={0.6} step={0.01}
        note="Rubber dry: 0.35 · Rubber wet: 0.25 · Ceramic dry: 0.50 · Bare steel: 0.20" />
      <F label="Design Wind Pressure" name="wind_pressure_pa"
        value={inp.wind_pressure_pa ?? 800} onChange={setField}
        unit="Pa" min={0} max={5000} step={100}
        note="Structural load for casing panel check" />
    </>
  );
}

function PowerEdit({ inp, setField, results }) {
  const r        = results || {};
  const torqueNm = r.T_Nm ?? 0;
  const motorKw  = r.motor_kw ?? r.motor_kW ?? 0;
  const reqRatio = inp.n_rpm > 0 ? Math.round(1450 / Math.max(inp.n_rpm, 1)) : 0;

  return (
    <>
      <SectionHead label="Motor Sizing" />
      <F label="Service Factor" name="sf" value={inp.sf}
        onChange={setField} min={1.0} max={2.5} step={0.05}
        note="CEMA recommendation: 1.25 general · 1.50 heavy/abrasive · 2.0 shock loads" />
      <F label="Motor kW Override" name="motor_kw_override"
        value={inp.motor_kw_override ?? 0} onChange={setField}
        unit="kW" min={0} max={1000} step={1}
        note={`0 = auto. Calc: ${r.P_total?.toFixed(2) ?? "—"} kW → auto-selects ${motorKw} kW`} />

      <SectionHead label="Tension" />
      <F label="Take-Up Factor K" name="K_takeup" value={inp.K_takeup}
        onChange={setField} min={0.4} max={0.9} step={0.05}
        note="K = 0.5 screw take-up · K = 0.7 gravity take-up (CEMA §4)" />

      <SectionHead label="Gearbox Selection" />
      {torqueNm > 0 && (
        <div style={{
          background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 5,
          padding: "8px 12px", marginBottom: 10,
          display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11,
        }}>
          {[
            ["Required Tn", `${torqueNm.toFixed(0)} Nm`],
            ["Approx ratio", reqRatio > 0 ? `${reqRatio}:1` : "—"],
            ["Motor",        `${motorKw} kW`],
          ].map(([l, v]) => (
            <div key={l}>
              <div style={{ fontSize: 9, color: T.text3 }}>{l}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
            </div>
          ))}
        </div>
      )}
      <ComponentPicker
        path="/components/gearboxes"
        params={{
          torque_min: torqueNm > 0 ? Math.round(torqueNm) : 0,
          ratio_min:  reqRatio > 0 ? Math.max(1, reqRatio - 5) : 0,
          ratio_max:  reqRatio > 0 ? reqRatio + 10 : 9999,
        }}
        valueField="model"
        formatLabel={row =>
          `${row.model}  Tn=${row.Tn}Nm  i=${row.ratio_min}–${row.ratio_max}  η=${row.eta}%  ${row.type ?? ""}`
        }
        value={inp.gearbox_model ?? ""}
        name="gearbox_model"
        onChange={setField}
        autoLabel={torqueNm > 0 ? `Tn ≥ ${torqueNm.toFixed(0)} Nm, ratio ≈ ${reqRatio}:1` : null}
        label="Gearbox Selection"
        note="Filtered by required output torque and approximate ratio. Select to lock model."
      />

      <SectionHead label="Drive / Starter Selection" />
      <ComponentPicker
        path="/components/drives"
        params={{ pkw_min: motorKw > 0 ? motorKw : 0 }}
        valueField="model"
        formatLabel={row =>
          `${row.model}  ${row.type}  ${row.Pkw_max}kW  ${row.control ?? ""}  ${row.ip ?? ""}`
        }
        value={inp.drive_model ?? ""}
        name="drive_model"
        onChange={setField}
        autoLabel={motorKw > 0 ? `Pkw_max ≥ ${motorKw} kW` : null}
        label="Drive / Starter Selection"
        note="VFD, soft-starter, or DOL. Filtered by motor kW."
      />

      <SectionHead label="CEMA LEQ Power Method" />
      <div style={{ fontSize: 11, color: T.text3, marginBottom: 10, lineHeight: 1.5 }}>
        Leq and Ceff default to material database values. Set to 0 to use defaults.
        Boot pulley diameter is set in Head &amp; Tail Pulley.
      </div>
      <Row2>
        <F label="Leq Factor" name="Leq" value={inp.Leq}
          onChange={setField} min={0} max={20} step={0.5}
          note="0 = auto. CC: 6–8 · Continuous: 4–5 · Abrasive: 10–12" />
        <F label="Ceff Factor" name="Ceff" value={inp.Ceff}
          onChange={setField} min={0} max={2.0} step={0.01}
          note="0 = auto. Belt: 1.10–1.15 · Chain: 1.20–1.30" />
      </Row2>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
export default function InputSidebar({ inputs, setField, results, openSectionRef }) {
  const inp = inputs || {};
  const r   = results || {};
  const [editSection, setEditSection] = useState(null);

  const open  = useCallback(id => setEditSection(id), []);
  const close = useCallback(()  => setEditSection(null), []);

  // Expose open() to the parent (BucketElevatorPage) via ref so EquipmentTree
  // clicks can open a specific section panel directly, instead of routing
  // through one coarse "mechanical" identifier with no way to reach a
  // specific editor (shaft, belt, bucket, takeup, discharge, casing, etc).
  useEffect(() => {
    if (openSectionRef) {
      openSectionRef.current = open;
    }
    return () => {
      if (openSectionRef) openSectionRef.current = null;
    };
  }, [openSectionRef, open]);

  // ── Status badges ────────────────────────────────────────────────────────
  const badges = {
    process:   checkBadge(r, ["capacity","fill","material"]),
    pulleys:   checkBadge(r, ["shaft","bearing","L10","headshaft","boot"]),
    belt:      checkBadge(r, ["belt slip","euler","headshaft load"]),
    bucket:    checkBadge(r, ["bucket","cr=","scatter","back-legging"]),
    takeup:    checkBadge(r, ["take-up","screw","buckling","counterweight"]),
    shaft:     checkBadge(r, ["shaft material","shaft governed","critical speed","keyway","welded hub","hollow shaft"]),
    discharge: checkBadge(r, ["casing clearance","stream","chute"]),
    casing:    checkBadge(r, ["panel","casing panel","δ="]),
    service:   checkBadge(r, ["lagging","slip","atex","hygroscopic"]),
    power:     checkBadge(r, ["motor","power","ceff","kW"]),
  };

  // ── Section summaries (compact, one-line) ───────────────────────────────
  const matName = r.mat?.name ?? inp.mat_id ?? "—";
  const bootDia = inp.boot_pulley_same_as_head ? inp.D_mm : (inp.boot_pulley_D_mm ?? "—");
  const bkt     = r.bucket || {};
  const tg      = r.takeup_gravity || {};
  const ts      = r.takeup_screw   || {};
  const cp      = r.casing_panel   || {};

  const summaries = {
    process:   `${inp.Q_req}t/h · ${inp.H_m}m · ${matName} · Fill ${inp.fill_pct}%`,
    pulleys:   `D_H ${inp.D_mm}mm · D_B ${bootDia}mm · ${inp.n_rpm}rpm · Wrap ${r?.wrap_effective_deg ?? inp.wrap_deg ?? 180}°`,
    belt:      `${r.belt_w ?? "auto"}mm · ${inp.belt_type ?? "EP"} · ${r.belt_ply ?? "—"} ply`,
    bucket:    `${bkt.id ?? "auto"} series · ${bkt.V ?? "—"}L · Gap ${inp.bucket_gap}mm`,
    takeup:    `${inp.takeup_type ?? "gravity"} · ${tg.W_counterweight_kg_gross?.toFixed(0) ?? "—"}kg · ${ts.d_core_recommend_mm ? `Screw Ø${ts.d_core_recommend_mm}mm` : ""}`,
    shaft:     `${inp.shaft_material ?? "A36"} · Ø${r.d_mm ?? "—"}mm · ${inp.shaft_section === "hollow" ? "hollow" : "solid"} · ${inp.shaft_hub_connection ?? "keyed"}`,
    discharge: `${r.is_continuous ? "HF continuous" : "Centrifugal"} · CR=${r.cr?.toFixed(3) ?? "—"} · θ=${r.theta_rel?.toFixed(1) ?? "—"}°`,
    feed:      r.feed_design
      ? `${r.feed_design.loading_type} · Inlet ${r.feed_design.inlet_width_mm}×${r.feed_design.inlet_height_mm}mm · Surge ${r.feed_design.V_surge_litres}L`
      : "Run calculation to see boot feed geometry",
    casing:    `${cp.t_use_mm ?? inp.casing_t_override_mm ?? "auto"} mm plate · ${inp.wind_pressure_pa ?? 800} Pa wind`,
    service:   `${inp.environment ?? "dry"} · μ=${inp.mu}`,
    power:     `SF ${inp.sf} · K ${inp.K_takeup} · Leq ${inp.Leq || "auto"} · Ceff ${inp.Ceff || "auto"}`,
  };

  // ── Active modal content ─────────────────────────────────────────────────
  const modals = {
    process:   { title: "Process Design",      cema: "CEMA 375 §4",   C: <ProcessEdit   inp={inp} setField={setField} results={r} /> },
    pulleys:   { title: "Head & Tail Pulley",  cema: "CEMA 375 §3,6", C: <PulleyEdit    inp={inp} setField={setField} results={r} /> },
    belt:      { title: "Belt / Drive Selection", cema: "CEMA 375 §4",   C: <BeltEdit      inp={inp} setField={setField} results={r} /> },
    chain:     { title: "Chain Configuration",    cema: "CEMA 375 §4",   C: <ChainEdit     inp={inp} setField={setField} results={r} /> },
    bucket:    { title: "Bucket Selection",    cema: "CEMA 375 §6",   C: <BucketEdit    inp={inp} setField={setField} results={r} /> },
    takeup:    { title: "Take-Up Selection",   cema: "CEMA 375 §4",   C: <TakeupEdit    inp={inp} setField={setField} results={r} /> },
    shaft:     { title: "Shaft Design",        cema: "CEMA 375 §4",   C: <ShaftEdit     inp={inp} setField={setField} results={r} /> },
    discharge: { title: "Discharge Section",   cema: "CEMA 375 §5",   C: <DischargeEdit inp={inp} setField={setField} results={r} /> },
    feed:      { title: "Feed Design",         cema: "CEMA 375 §4",   C: <FeedEdit     inp={inp} setField={setField} results={r} /> },
    casing:    { title: "Casing Design",       cema: "CEMA 375 §7",   C: <CasingEdit    inp={inp} setField={setField} results={r} /> },
    service:   { title: "Service Conditions",  cema: "v1.3.0",         C: <ServiceEdit   inp={inp} setField={setField} /> },
    power:     { title: "Power Transmission",  cema: "CEMA 375 §4",   C: <PowerEdit     inp={inp} setField={setField} results={r} /> },
  };

  const activeModal = editSection ? modals[editSection] : null;

  return (
    <div style={{
      height: "100%", overflowY: "auto", overflowX: "hidden",
      display: "flex", flexDirection: "column",
    }}>

      {/* ── 1. Process Design ─────────────────────────────────────────────── */}
      <AccordionGroup label="Process Design" cema="CEMA 375"
        badge={badges.process} defaultOpen>
        <SectionRow label="Design Requirements" onEdit={() => open("process")}
          summary={summaries.process} depth={1} badge={badges.process} />
      </AccordionGroup>

      {/* ── 2. Mechanical Design (group) ────────────────────────────────── */}
      <AccordionGroup label="Mechanical Design" cema="CEMA 375"
        badge={[badges.pulleys,badges.belt,badges.bucket,badges.takeup,
                badges.discharge,badges.casing].find(b=>b?.label==="FAIL")
              ?? [badges.pulleys,badges.belt,badges.bucket,badges.takeup,
                  badges.discharge,badges.casing].find(b=>b?.label==="WARN")}
        defaultOpen>

        <SectionRow label="Head & Tail Pulley" depth={1}
          badge={badges.pulleys} summary={summaries.pulleys}
          onEdit={() => open("pulleys")} />
        {(inp.conveyor_type ?? "belt") === "belt" ? (
          <SectionRow label="Belt Selection" depth={1}
            badge={badges.belt} summary={summaries.belt}
            onEdit={() => open("belt")} />
        ) : (
          <SectionRow label="Chain Configuration ⛓" depth={1}
            badge={checkBadge(r, ["chain sf","chain speed","sprocket"])}
            summary={r.chain_selected
              ? `${r.chain_selected.name} · SF=${r.chain_SF_actual?.toFixed(2) ?? "—"} · ${inp.chain_n_strands ?? 1} strand`
              : "auto · configure below"}
            onEdit={() => open("chain")} />
        )}
        <SectionRow label="Bucket Selection" depth={1}
          badge={badges.bucket} summary={summaries.bucket}
          onEdit={() => open("bucket")} />
        <SectionRow label="Take-Up Selection" depth={1}
          badge={badges.takeup} summary={summaries.takeup}
          onEdit={() => open("takeup")} />
        <SectionRow label="Shaft Design" depth={1}
          badge={badges.shaft} summary={summaries.shaft}
          onEdit={() => open("shaft")} />
        <SectionRow label="Discharge Section" depth={1}
          badge={badges.discharge} summary={summaries.discharge}
          onEdit={() => open("discharge")} />
        <SectionRow label="Feed Design" depth={1}
          summary={summaries.feed}
          badge={r.feed_design
            ? (r.feed_design.warnings?.length ? { label: "WARN", color: T.warning } : { label: "OK", color: T.success })
            : { label: "PENDING", color: T.text3 }}
          onEdit={() => open("feed")} />
        <SectionRow label="Casing Design" depth={1}
          badge={badges.casing} summary={summaries.casing}
          onEdit={() => open("casing")} />
      </AccordionGroup>

      {/* ── 3. Service Conditions ─────────────────────────────────────────── */}
      <AccordionGroup label="Service Conditions" cema="v1.3.0"
        badge={badges.service} defaultOpen={false}>
        <SectionRow label="Environment & Friction" depth={1}
          badge={badges.service} summary={summaries.service}
          onEdit={() => open("service")} />
      </AccordionGroup>

      {/* ── 4. Power Transmission ─────────────────────────────────────────── */}
      <AccordionGroup label="Power Transmission" cema="CEMA 375 §4"
        badge={badges.power} defaultOpen={false}>
        <SectionRow label="Motor & Drive" depth={1}
          badge={badges.power} summary={summaries.power}
          onEdit={() => open("power")} />
      </AccordionGroup>

      {/* ── Standards footer ──────────────────────────────────────────────── */}
      <div style={{
        marginTop: "auto", padding: "8px 12px",
        borderTop: `1px solid ${T.border}`,
        fontSize: 10, color: T.text3, lineHeight: 1.6,
      }}>
        CEMA 375-2017 · ISO 281 · ASME B17.1
      </div>

      {/* ── Edit popup modal ──────────────────────────────────────────────── */}
      {activeModal && (
        <Modal title={activeModal.title} cema={activeModal.cema} onClose={close}>
          {activeModal.C}
        </Modal>
      )}
    </div>
  );
}