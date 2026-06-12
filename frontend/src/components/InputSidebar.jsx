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

import { useState, useCallback } from "react";
import MaterialSearchDropdown from "./MaterialSearchDropdown";

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
            onChange={e => onChange(type === "number" ? parseFloat(e.target.value) : e.target.value)}
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
            onChange={e => onChange(name, type === "number"
              ? parseFloat(e.target.value) : e.target.value)}
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
// EDIT MODAL CONTENTS — one per section
// ═══════════════════════════════════════════════════════════════════════════════

function ProcessEdit({ inp, setField }) {
  return (
    <>
      <Row2>
        <F label="Required Capacity" name="Q_req" value={inp.Q_req}
          onChange={setField} unit="t/h" min={1} max={5000} step={1} />
        <F label="Lift Height" name="H_m" value={inp.H_m}
          onChange={setField} unit="m" min={1} max={200} step={0.5} />
      </Row2>
      <F label="Bucket Fill Factor" name="fill_pct" value={inp.fill_pct}
        onChange={setField} unit="%" min={30} max={100} step={5}
        note="Grain 75–90% · Minerals 60–75% · Cohesive 40–65%" />

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

function PulleyEdit({ inp, setField }) {
  return (
    <>
      <SectionHead label="Head Pulley" />
      <Row2>
        <F label="Head Pulley Dia." name="D_mm" value={inp.D_mm}
          onChange={setField} unit="mm" min={100} max={1500} step={25} />
        <F label="Shaft Speed" name="n_rpm" value={inp.n_rpm}
          onChange={setField} unit="rpm" min={10} max={300} step={5} />
      </Row2>
      <F label="Wrap Angle" name="wrap_deg" value={inp.wrap_deg}
        onChange={setField} unit="°" min={90} max={240} step={5}
        note="Standard 180°. Add snub pulley to increase." />

      <SectionHead label="Boot (Tail) Pulley" />
      <F label="Match head pulley diameter" name="boot_pulley_same_as_head"
        type="toggle" value={inp.boot_pulley_same_as_head ?? false}
        onChange={setField} />
      {!inp.boot_pulley_same_as_head && (
        <F label="Boot Pulley Diameter" name="boot_pulley_D_mm"
          value={inp.boot_pulley_D_mm} onChange={setField}
          unit="mm" min={100} max={1000} step={25}
          note={`Head = ${inp.D_mm} mm · Ratio = ${(inp.boot_pulley_D_mm / Math.max(inp.D_mm,1)).toFixed(2)}`} />
      )}
      {inp.boot_pulley_same_as_head && (
        <div style={{ fontSize: 12, color: T.success, padding: "4px 0 8px" }}>
          Boot locked to head: {inp.D_mm} mm
        </div>
      )}
    </>
  );
}

function BeltEdit({ inp, setField, results }) {
  const r = results || {};
  return (
    <>
      <SectionHead label="Belt Configuration" />
      <div style={{
        background: T.panel2, border: `1px solid ${T.border}`,
        borderRadius: 5, padding: "10px 12px", marginBottom: 12, fontSize: 12,
      }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {[
            ["Auto Width", `${r.belt_w ?? "—"} mm`],
            ["Plies", `${r.belt_ply ?? "—"}`],
            ["Eff. Tension", `${r.F_eff != null ? (r.F_eff/1000).toFixed(1) : "—"} kN`],
          ].map(([l,v]) => (
            <div key={l}>
              <div style={{ fontSize: 10, color: T.text3 }}>{l}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text,
                fontFamily: "JetBrains Mono,monospace" }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
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
    </>
  );
}

function BucketEdit({ inp, setField }) {
  const bucketOptions = [
    { value: "AA", label: "AA — Super Capacity  7.4L" },
    { value: "A",  label: "A  — Extra Capacity  5.0L" },
    { value: "B",  label: "B  — Medium Capacity 3.3L" },
    { value: "C",  label: "C  — Centrifugal     1.9L" },
    { value: "D",  label: "D  — Centrifugal Sm. 0.77L" },
    { value: "MF", label: "MF — Milk of Lime    4.0L" },
    { value: "PF", label: "PF — Pellet/Feed     6.5L" },
    { value: "HF", label: "HF — High Capacity   11.2L (continuous)" },
  ];
  return (
    <>
      <SectionHead label="Bucket Selection" />
      <F label="Auto-select bucket series" name="auto_bucket" type="toggle"
        value={inp.auto_bucket} onChange={setField}
        note="Auto picks the smallest series that meets Q_req at current speed" />
      {!inp.auto_bucket && (
        <F label="Bucket Series" name="bucket_id" type="select"
          value={inp.bucket_id} onChange={setField} options={bucketOptions} />
      )}
      <F label="Bucket Spacing Gap" name="bucket_gap"
        value={inp.bucket_gap} onChange={setField}
        unit="mm" min={0} max={200} step={5}
        note="Gap between bucket back and next bucket lip. CEMA default 25mm." />
    </>
  );
}

function TakeupEdit({ inp, setField, results }) {
  const ts  = results?.takeup_screw  || {};
  const tg  = results?.takeup_gravity || {};
  return (
    <>
      <SectionHead label="Take-Up Type" />
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {["gravity","screw","auto"].map(v => (
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
      <SectionHead label="Casing Width Override" />
      <F label="Belt Width Override" name="belt_width_override_mm"
        value={inp.belt_width_override_mm ?? 0} onChange={setField}
        unit="mm" min={0} max={1500} step={25}
        note="Wider belt = wider casing head section. 0 = auto." />
    </>
  );
}

function FeedEdit() {
  return (
    <div style={{
      textAlign: "center", padding: "32px 16px",
    }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>🚧</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: T.text,
        marginBottom: 8 }}>Feed Design Module</div>
      <div style={{ fontSize: 12, color: T.text3, lineHeight: 1.6 }}>
        Boot inlet geometry, scooping angle, feeder sizing, and
        boot surge volume calculations are planned for the next release.
      </div>
    </div>
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

function PowerEdit({ inp, setField }) {
  return (
    <>
      <SectionHead label="Motor Sizing" />
      <F label="Service Factor" name="sf"
        value={inp.sf} onChange={setField} min={1.0} max={2.5} step={0.05}
        note="CEMA recommendation: 1.25 general · 1.50 heavy/abrasive · 2.0 shock loads" />
      <SectionHead label="Tension" />
      <F label="Take-Up Factor K" name="K_takeup"
        value={inp.K_takeup} onChange={setField} min={0.4} max={0.9} step={0.05}
        note="K = 0.5 screw take-up · K = 0.7 gravity take-up (CEMA §4)" />
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
export default function InputSidebar({ inputs, setField, results }) {
  const inp = inputs || {};
  const r   = results || {};
  const [editSection, setEditSection] = useState(null);

  const open  = useCallback(id => setEditSection(id), []);
  const close = useCallback(()  => setEditSection(null), []);

  // ── Status badges ────────────────────────────────────────────────────────
  const badges = {
    process:   checkBadge(r, ["capacity","fill","material"]),
    pulleys:   checkBadge(r, ["shaft","bearing","L10","headshaft","boot"]),
    belt:      checkBadge(r, ["belt slip","euler","headshaft load"]),
    bucket:    checkBadge(r, ["bucket","cr=","scatter","back-legging"]),
    takeup:    checkBadge(r, ["take-up","screw","buckling","counterweight"]),
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
    pulleys:   `D_H ${inp.D_mm}mm · D_B ${bootDia}mm · ${inp.n_rpm}rpm · Wrap ${inp.wrap_deg}°`,
    belt:      `${r.belt_w ?? "auto"}mm · ${inp.belt_type ?? "EP"} · ${r.belt_ply ?? "—"} ply`,
    bucket:    `${bkt.id ?? "auto"} series · ${bkt.V ?? "—"}L · Gap ${inp.bucket_gap}mm`,
    takeup:    `${inp.takeup_type ?? "gravity"} · ${tg.W_counterweight_kg_gross?.toFixed(0) ?? "—"}kg · ${ts.d_core_recommend_mm ? `Screw Ø${ts.d_core_recommend_mm}mm` : ""}`,
    discharge: `${r.is_continuous ? "HF continuous" : "Centrifugal"} · CR=${r.cr?.toFixed(3) ?? "—"} · θ=${r.theta_rel?.toFixed(1) ?? "—"}°`,
    feed:      "Boot inlet geometry — pending",
    casing:    `${cp.t_use_mm ?? inp.casing_t_override_mm ?? "auto"} mm plate · ${inp.wind_pressure_pa ?? 800} Pa wind`,
    service:   `${inp.environment ?? "dry"} · μ=${inp.mu}`,
    power:     `SF ${inp.sf} · K ${inp.K_takeup} · Leq ${inp.Leq || "auto"} · Ceff ${inp.Ceff || "auto"}`,
  };

  // ── Active modal content ─────────────────────────────────────────────────
  const modals = {
    process:   { title: "Process Design",      cema: "CEMA 375 §4",   C: <ProcessEdit   inp={inp} setField={setField} /> },
    pulleys:   { title: "Head & Tail Pulley",  cema: "CEMA 375 §3,6", C: <PulleyEdit    inp={inp} setField={setField} /> },
    belt:      { title: "Belt Selection",      cema: "CEMA 375 §4",   C: <BeltEdit      inp={inp} setField={setField} results={r} /> },
    bucket:    { title: "Bucket Selection",    cema: "CEMA 375 §6",   C: <BucketEdit    inp={inp} setField={setField} /> },
    takeup:    { title: "Take-Up Selection",   cema: "CEMA 375 §4",   C: <TakeupEdit    inp={inp} setField={setField} results={r} /> },
    discharge: { title: "Discharge Section",   cema: "CEMA 375 §5",   C: <DischargeEdit inp={inp} setField={setField} results={r} /> },
    feed:      { title: "Feed Design",         cema: "Pending",        C: <FeedEdit /> },
    casing:    { title: "Casing Design",       cema: "CEMA 375 §7",   C: <CasingEdit    inp={inp} setField={setField} results={r} /> },
    service:   { title: "Service Conditions",  cema: "v1.3.0",         C: <ServiceEdit   inp={inp} setField={setField} /> },
    power:     { title: "Power Transmission",  cema: "CEMA 375 §4",   C: <PowerEdit     inp={inp} setField={setField} /> },
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
        <SectionRow label="Belt Selection" depth={1}
          badge={badges.belt} summary={summaries.belt}
          onEdit={() => open("belt")} />
        <SectionRow label="Bucket Selection" depth={1}
          badge={badges.bucket} summary={summaries.bucket}
          onEdit={() => open("bucket")} />
        <SectionRow label="Take-Up Selection" depth={1}
          badge={badges.takeup} summary={summaries.takeup}
          onEdit={() => open("takeup")} />
        <SectionRow label="Discharge Section" depth={1}
          badge={badges.discharge} summary={summaries.discharge}
          onEdit={() => open("discharge")} />
        <SectionRow label="Feed Design" depth={1}
          summary={summaries.feed}
          badge={{ label: "PENDING", color: T.text3 }}
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