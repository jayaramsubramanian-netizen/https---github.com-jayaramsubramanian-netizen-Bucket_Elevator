// MaterialLibraryPanel.jsx — Material Library tab
//
// Browse built-in + custom materials, copy any material into a new custom
// one, and edit/delete custom materials. Built-in materials (materials.py's
// MATERIALS list) are immutable by design -- no edit/delete on those rows,
// only "Copy & Customize". InputSidebar's MaterialSearchDropdown needs no
// changes for this: it already does pure selection (search/pick, no inline
// editing) and will pick up custom materials automatically once the backend
// exposes them through /materials/search (round 14's other change).

import { useState, useEffect, useMemo, useCallback } from "react";
import {
  fetchMaterials, listCustomMaterials, createCustomMaterial,
  updateCustomMaterial, deleteCustomMaterial,
} from "../api/client";

const C = {
  border: "var(--border)", border2: "#ffffff1e",
  panel: "var(--panel)", panel2: "var(--panel2)", surface: "var(--surface)",
  text: "var(--text)", text2: "var(--text2)", text3: "var(--text3)",
  muted: "var(--muted)", primary: "var(--primary)",
  success: "var(--success)", warning: "var(--warning)", danger: "var(--danger)",
};

const ABR_LABEL = ["–","Low","Low","Med","Med","High","High","V.Hi"];
const FLOW_LABEL = { 1:"Very free", 2:"Free", 3:"Average", 4:"Sluggish" };
const CATEGORIES = [
  "GRAIN","BIO","CHEM","CONST","FOOD","MIN","METAL","FERT",
  "CEM","COAL","GLASS","ENV","PHARM","PETRO","POLY","SALT",
];
const HAZARD_OPTIONS = [
  { code: "B1",  label: "Aerates / fluidises easily" },
  { code: "B4",  label: "Corrosive to steel" },
  { code: "B6",  label: "Other documented hazard (B6)" },
  { code: "B8",  label: "Hygroscopic (absorbs moisture)" },
  { code: "B10", label: "Explosive dust" },
  { code: "B11", label: "Flammable vapour" },
];

const BLANK_FORM = {
  id: "", name: "", category: "MIN", rho_loose: 1000, rho_vib: "",
  angle_repose: 35, angle_surcharge: "", angle_internal_friction: "",
  moisture_pct: 0, cohesion: 0, abr_code: 3, flowability: 2, size_code: "B",
  hazard_codes: [], Km: 1.0, Ceff_default: 1.15, Leq_default: 8,
  wall_friction_deg: 20, bucket_fill_factor: 0.75,
  pref_discharge_type: "centrifugal", pref_bucket_style: "AA",
  pref_cr_min: 1.2, pref_cr_max: 1.5, based_on: null,
};

export function slugify(name) {
  return name.toLowerCase().trim()
    .replace(/[^a-z0-9\s_]/g, "")
    .replace(/\s+/g, "_")
    .replace(/^[^a-z]+/, "")   // must start with a letter
    .slice(0, 40) || "custom_material";
}

// ── Small form field helpers ─────────────────────────────────────────────────
function Field({ label, children, hint }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 10.5, color: C.text2, marginBottom: 3, fontWeight: 600 }}>
        {label}
      </div>
      {children}
      {hint && <div style={{ fontSize: 9.5, color: C.muted, marginTop: 2 }}>{hint}</div>}
    </div>
  );
}
const inputStyle = {
  width: "100%", padding: "6px 8px", fontSize: 12,
  background: C.panel2, border: `1px solid ${C.border}`, borderRadius: 5,
  color: C.text, fontFamily: "inherit", boxSizing: "border-box",
};
function NumField({ value, onChange, step = "any", ...rest }) {
  return (
    <input type="number" step={step} value={value}
      onChange={e => onChange(e.target.value === "" ? "" : Number(e.target.value))}
      style={inputStyle} {...rest} />
  );
}
function TextField({ value, onChange, ...rest }) {
  return <input type="text" value={value ?? ""} onChange={e => onChange(e.target.value)} style={inputStyle} {...rest} />;
}
function SelectField({ value, onChange, options, ...rest }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={inputStyle} {...rest}>
      {options.map(o => (
        <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
      ))}
    </select>
  );
}

// ── Edit / Create / Copy form ────────────────────────────────────────────────
function MaterialForm({ initial, mode, onSave, onCancel, existingIds }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setForm(f => ({ ...f, [k]: v }));

  const idLocked = mode === "edit";
  const idError = !idLocked && form.id && existingIds.has(form.id)
    ? "This ID is already in use (built-in or custom)."
    : null;

  const handleSave = async () => {
    setError(null);
    if (!idLocked && (!form.id || idError)) {
      setError(idError || "Material ID is required.");
      return;
    }
    if (!form.name?.trim()) { setError("Material name is required."); return; }
    if (!form.rho_loose || form.rho_loose <= 0) { setError("Bulk density must be a positive number."); return; }
    if (Number(form.pref_cr_min) >= Number(form.pref_cr_max)) {
      setError("CR target minimum must be less than maximum."); return;
    }
    setSaving(true);
    try {
      const payload = { ...form };
      // Coerce blank-string optional numeric fields to null rather than "".
      for (const k of ["rho_vib", "angle_surcharge", "angle_internal_friction"]) {
        if (payload[k] === "") payload[k] = null;
      }
      const saved = mode === "edit"
        ? await updateCustomMaterial(form.id, payload)
        : await createCustomMaterial(payload);
      onSave(saved);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, height: "100%" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px", borderBottom: `1px solid ${C.border}`, flexShrink: 0,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
          {mode === "edit" ? `Edit: ${initial.name}`
            : mode === "copy" ? `Copy & Customize: ${initial.based_on || initial.name}`
            : "New Custom Material"}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-secondary" style={{ margin: 0 }} onClick={onCancel}>Cancel</button>
          <button className="btn-primary" style={{ margin: 0 }} onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {error && (
        <div className="warn-item w-fail" style={{ margin: "8px 14px" }}>{error}</div>
      )}

      <div style={{ overflowY: "auto", padding: "12px 14px", flex: 1 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>

          {/* Identity */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>Identity</div>
            <Field label="Material ID" hint={idLocked ? "Locked — IDs can't change after creation." : "Lowercase, numbers, underscores only. Auto-filled from name."}>
              <TextField value={form.id} onChange={set("id")} disabled={idLocked}
                placeholder="e.g. wheat_humid_batch7" />
            </Field>
            <Field label="Name">
              <TextField value={form.name} onChange={v => {
                set("name")(v);
                if (!idLocked && (!form.id || form.id === slugify(form.name))) set("id")(slugify(v));
              }} placeholder="e.g. Wheat (Humid, Batch 7)" />
            </Field>
            <Field label="Category">
              <SelectField value={form.category} onChange={set("category")}
                options={CATEGORIES.map(c => ({ value: c, label: c }))} />
            </Field>
            {form.based_on && (
              <Field label="Based on">
                <div style={{ fontSize: 11, color: C.muted, fontFamily: "JetBrains Mono,monospace" }}>{form.based_on}</div>
              </Field>
            )}
          </div>

          {/* Physical properties */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>Physical Properties</div>
            <Field label="Bulk density, loose (kg/m³)">
              <NumField value={form.rho_loose} onChange={set("rho_loose")} />
            </Field>
            <Field label="Bulk density, vibrated (kg/m³)" hint="Optional">
              <NumField value={form.rho_vib} onChange={set("rho_vib")} />
            </Field>
            <Field label="Angle of repose (°)">
              <NumField value={form.angle_repose} onChange={set("angle_repose")} />
            </Field>
            <Field label="Moisture (%)">
              <NumField value={form.moisture_pct} onChange={set("moisture_pct")} />
            </Field>
            <Field label="Cohesion (0-1)">
              <NumField value={form.cohesion} onChange={set("cohesion")} step="0.01" />
            </Field>
          </div>

          {/* Friction & flow */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>Friction &amp; Flow</div>
            <Field label="Abrasiveness class (1-7)" hint={ABR_LABEL[form.abr_code] ?? ""}>
              <SelectField value={form.abr_code} onChange={v => set("abr_code")(Number(v))}
                options={[1,2,3,4,5,6,7].map(n => ({ value: n, label: `${n} — ${ABR_LABEL[n]}` }))} />
            </Field>
            <Field label="Flowability class (1-4)" hint={FLOW_LABEL[form.flowability] ?? ""}>
              <SelectField value={form.flowability} onChange={v => set("flowability")(Number(v))}
                options={[1,2,3,4].map(n => ({ value: n, label: `${n} — ${FLOW_LABEL[n]}` }))} />
            </Field>
            <Field label="Wall friction angle (°)">
              <NumField value={form.wall_friction_deg} onChange={set("wall_friction_deg")} />
            </Field>
            <Field label="Size code">
              <TextField value={form.size_code} onChange={set("size_code")} placeholder="e.g. B" />
            </Field>
          </div>

          {/* CEMA defaults */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>CEMA Defaults</div>
            <Field label="Km (material factor)">
              <NumField value={form.Km} onChange={set("Km")} step="0.05" />
            </Field>
            <Field label="Ceff (efficiency factor)">
              <NumField value={form.Ceff_default} onChange={set("Ceff_default")} step="0.05" />
            </Field>
            <Field label="Leq default">
              <NumField value={form.Leq_default} onChange={set("Leq_default")} step="0.5" />
            </Field>
            <Field label="Bucket fill factor (0-1)">
              <NumField value={form.bucket_fill_factor} onChange={set("bucket_fill_factor")} step="0.05" />
            </Field>
          </div>

          {/* Discharge preference -- the fields that actually drive
              auto-bucket selection (round 7) and the optimizer (round 3+) */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>
              Discharge Preference
            </div>
            <Field label="Preferred discharge type" hint="Drives auto-bucket speed/style selection and the optimizer's CR objective.">
              <SelectField value={form.pref_discharge_type} onChange={set("pref_discharge_type")}
                options={[{ value: "continuous", label: "Continuous (HF/MF/SC)" },
                          { value: "centrifugal", label: "Centrifugal (AA/AC/C)" }]} />
            </Field>
            <Field label="Preferred bucket style">
              <TextField value={form.pref_bucket_style} onChange={set("pref_bucket_style")} placeholder="e.g. HF, AA, AC" />
            </Field>
            <div style={{ display: "flex", gap: 8 }}>
              <Field label="CR target min" hint="Continuous: 0.2-1.0. Centrifugal: 0.7-3.0.">
                <NumField value={form.pref_cr_min} onChange={set("pref_cr_min")} step="0.05" />
              </Field>
              <Field label="CR target max">
                <NumField value={form.pref_cr_max} onChange={set("pref_cr_max")} step="0.05" />
              </Field>
            </div>
          </div>

          {/* Hazards */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.primary, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".04em" }}>Hazards</div>
            {HAZARD_OPTIONS.map(h => {
              const checked = form.hazard_codes.includes(h.code);
              return (
                <label key={h.code} style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 6, fontSize: 11, color: C.text2, cursor: "pointer" }}>
                  <input type="checkbox" checked={checked} onChange={() => {
                    setForm(f => ({
                      ...f,
                      hazard_codes: checked
                        ? f.hazard_codes.filter(c => c !== h.code)
                        : [...f.hazard_codes, h.code],
                    }));
                  }} />
                  {h.label}
                </label>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Material row ──────────────────────────────────────────────────────────────
function MaterialRow({ mat, isCustom, onCopy, onEdit, onDelete }) {
  return (
    <tr>
      <td style={{ fontWeight: 600 }}>{mat.name}</td>
      <td className="mono" style={{ fontSize: 10 }}>{mat.id}</td>
      <td>{mat.category}</td>
      <td className="mono">{mat.rho_loose != null ? `${Math.round(mat.rho_loose)} kg/m³` : "—"}</td>
      <td>{ABR_LABEL[mat.abr_code] ?? "—"}</td>
      <td>{FLOW_LABEL[mat.flowability] ?? "—"}</td>
      <td>
        {mat.pref_discharge_type && (
          <span style={{
            fontSize: 9.5, padding: "1px 6px", borderRadius: 999, fontWeight: 700,
            background: mat.pref_discharge_type === "continuous" ? "rgba(20,184,166,.15)" : "rgba(244,163,0,.15)",
            color: mat.pref_discharge_type === "continuous" ? C.success : C.warning,
          }}>
            {mat.pref_bucket_style} · {mat.pref_discharge_type === "continuous" ? "cont." : "cent."}
          </span>
        )}
      </td>
      <td style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
        <button className="btn-secondary" style={{ margin: 0, padding: "3px 8px", fontSize: 10 }} onClick={() => onCopy(mat)}>
          Copy &amp; Customize
        </button>
        {isCustom && (
          <>
            <button className="btn-secondary" style={{ margin: 0, padding: "3px 8px", fontSize: 10 }} onClick={() => onEdit(mat)}>Edit</button>
            <button className="btn-secondary" style={{ margin: 0, padding: "3px 8px", fontSize: 10, color: C.danger }} onClick={() => onDelete(mat)}>Delete</button>
          </>
        )}
      </td>
    </tr>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────
export default function MaterialLibraryPanel() {
  const [builtins, setBuiltins] = useState([]);
  const [customs, setCustoms] = useState([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [showCustomOnly, setShowCustomOnly] = useState(false);
  const [editing, setEditing] = useState(null); // { mode: 'create'|'copy'|'edit', form }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [matsRes, customRes] = await Promise.all([fetchMaterials(), listCustomMaterials()]);
      setBuiltins(matsRes.materials ?? []);
      setCustoms(customRes.materials ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const existingIds = useMemo(
    () => new Set([...builtins.map(m => m.id), ...customs.map(m => m.id)]),
    [builtins, customs]
  );

  const allMaterials = useMemo(() => {
    const tagged = [
      ...builtins.map(m => ({ ...m, _isCustom: false })),
      ...customs.map(m => ({ ...m, _isCustom: true })),
    ];
    const q = query.toLowerCase();
    return tagged.filter(m => {
      if (showCustomOnly && !m._isCustom) return false;
      if (category && m.category !== category) return false;
      if (q && !m.name.toLowerCase().includes(q) && !m.id.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [builtins, customs, query, category, showCustomOnly]);

  const handleCopy = (mat) => {
    const { id: _drop, ...rest } = mat;
    setEditing({ mode: "copy", form: { ...BLANK_FORM, ...rest, id: "", name: `${mat.name} (Custom)`, based_on: mat.id } });
  };
  const handleEdit = (mat) => setEditing({ mode: "edit", form: { ...BLANK_FORM, ...mat } });
  const handleCreate = () => setEditing({ mode: "create", form: { ...BLANK_FORM } });
  const handleDelete = async (mat) => {
    if (!window.confirm(`Delete custom material "${mat.name}"? This cannot be undone. Any saved design still referencing it will fall back to safe defaults.`)) return;
    try {
      await deleteCustomMaterial(mat.id);
      await load();
    } catch (e) {
      setError(e.message);
    }
  };
  const handleSaved = async () => {
    setEditing(null);
    await load();
  };

  if (editing) {
    return (
      <MaterialForm
        initial={editing.form}
        mode={editing.mode === "create" ? "create" : editing.mode === "copy" ? "copy" : "edit"}
        existingIds={existingIds}
        onSave={handleSaved}
        onCancel={() => setEditing(null)}
      />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
        borderBottom: `1px solid ${C.border}`, flexShrink: 0,
      }}>
        <input
          value={query} onChange={e => setQuery(e.target.value)}
          placeholder="Search materials by name or ID…"
          style={{ ...inputStyle, flex: 1 }}
        />
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ ...inputStyle, width: 140 }}>
          <option value="">All categories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: C.text2, whiteSpace: "nowrap", cursor: "pointer" }}>
          <input type="checkbox" checked={showCustomOnly} onChange={e => setShowCustomOnly(e.target.checked)} />
          Custom only
        </label>
        <button className="btn-primary" style={{ margin: 0, whiteSpace: "nowrap" }} onClick={handleCreate}>
          + New Material
        </button>
      </div>

      {error && <div className="warn-item w-fail" style={{ margin: "8px 14px" }}>{error}</div>}

      <div style={{ overflowY: "auto", flex: 1 }}>
        {loading ? (
          <div style={{ padding: 20, textAlign: "center", color: C.muted, fontSize: 12 }}>Loading materials…</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th><th>ID</th><th>Category</th><th>Density</th>
                <th>Abrasion</th><th>Flow</th><th>Discharge Pref.</th><th></th>
              </tr>
            </thead>
            <tbody>
              {allMaterials.map(m => (
                <MaterialRow key={m.id} mat={m} isCustom={m._isCustom}
                  onCopy={handleCopy} onEdit={handleEdit} onDelete={handleDelete} />
              ))}
            </tbody>
          </table>
        )}
        {!loading && allMaterials.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: C.muted, fontSize: 12 }}>
            No materials match your search.
          </div>
        )}
      </div>

      <div style={{ padding: "6px 14px", borderTop: `1px solid ${C.border}`, fontSize: 10, color: C.muted, flexShrink: 0 }}>
        {builtins.length} built-in (read-only) · {customs.length} custom ·
        "Copy &amp; Customize" works on any row, including built-ins, to start from known-good values.
      </div>
    </div>
  );
}