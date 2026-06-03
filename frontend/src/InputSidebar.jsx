// InputSidebar.jsx — all user inputs for the bucket elevator
import { useState } from "react";

const MATERIALS = [
  { id: "wheat", name: "Wheat" },
  { id: "corn", name: "Corn (Maize)" },
  { id: "soybeans", name: "Soybeans" },
  { id: "rice", name: "Rice (rough)" },
  { id: "sugar", name: "Sugar (granulated)" },
  { id: "salt", name: "Salt (fine)" },
  { id: "cement", name: "Cement (dry)" },
  { id: "limestone", name: "Limestone (crushed)" },
  { id: "coal", name: "Coal (bituminous)" },
  { id: "ironore", name: "Iron Ore (fines)" },
  { id: "sand", name: "Sand (dry)" },
  { id: "clinker", name: "Clinker" },
  { id: "flyash", name: "Fly Ash" },
  { id: "phosphate", name: "Phosphate Rock" },
  { id: "woodchips", name: "Wood Chips" },
  { id: "custom", name: "Custom Material" },
];

const BUCKET_SERIES = [
  { id: "AA", label: "AA — 7.4L Super Capacity" },
  { id: "A",  label: "A  — 5.0L Extra Capacity" },
  { id: "B",  label: "B  — 3.3L Medium Capacity" },
  { id: "C",  label: "C  — 1.9L Centrifugal" },
  { id: "D",  label: "D  — 0.77L Centrifugal Sm." },
  { id: "MF", label: "MF — 4.0L Milk of Lime" },
  { id: "PF", label: "PF — 6.5L Pellet/Feed" },
  { id: "HF", label: "HF — 11.2L High Capacity" },
];

function Section({ id, title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="inp-section">
      <div className="inp-hdr" onClick={() => setOpen(!open)}>
        <span className="hdr-dot" />
        {title}
        <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--faint)" }}>
          {open ? "▲" : "▼"}
        </span>
      </div>
      {open && <div className="inp-body">{children}</div>}
    </div>
  );
}

function Field({ label, k, unit, min, max, step = 1, inputs, setField }) {
  return (
    <div className="inp-field">
      <div className="inp-label">{label}</div>
      <div className="inp-wrap">
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={inputs[k]}
          onChange={(e) => setField(k, parseFloat(e.target.value) || 0)}
        />
        {unit && <span className="inp-unit">{unit}</span>}
      </div>
    </div>
  );
}

export default function InputSidebar({ inputs, setField, results }) {
  const mat = MATERIALS.find((m) => m.id === inputs.mat_id) || MATERIALS[0];

  return (
    <div className="sidebar">
      <div
        style={{
          padding: "8px 12px 4px",
          fontSize: 9,
          color: "var(--faint)",
          letterSpacing: ".1em",
          textTransform: "uppercase",
          fontFamily: "var(--ff-ui)",
          fontWeight: 700,
        }}
      >
        System Inputs
      </div>

      {/* A — Process */}
      <Section id="process" title="A — Process Requirements">
        <Field label="Required Capacity" k="Q_req" unit="t/h" min={1} max={5000} inputs={inputs} setField={setField} />
        <Field label="Lift Height" k="H_m" unit="m" min={1} max={200} inputs={inputs} setField={setField} />
        <div className="inp-field">
          <div className="inp-label">Material</div>
          <select
            className="inp-sel"
            value={inputs.mat_id}
            onChange={(e) => setField("mat_id", e.target.value)}
          >
            {MATERIALS.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
        {inputs.mat_id === "custom" && (
          <Field label="Custom Density" k="custom_rho" unit="kg/m³" min={100} max={5000} inputs={inputs} setField={setField} />
        )}
        {results && (
          <div style={{ fontSize: 10, color: "var(--muted)", padding: "4px 0" }}>
            ρ = {results.rho} kg/m³ · Km = {results.mat?.Km}
          </div>
        )}
      </Section>

      {/* B — Mechanical */}
      <Section id="mech" title="B — Mechanical Parameters">
        <Field label="Head Pulley Dia." k="D_mm" unit="mm" min={100} max={1500} step={25} inputs={inputs} setField={setField} />
        <Field label="Head Shaft Speed" k="n_rpm" unit="rpm" min={10} max={300} inputs={inputs} setField={setField} />
        <Field label="Bucket Fill Factor" k="fill_pct" unit="%" min={30} max={100} inputs={inputs} setField={setField} />
        <Field label="Bucket Spacing Gap" k="bucket_gap" unit="mm" min={0} max={200} inputs={inputs} setField={setField} />
      </Section>

      {/* C — Bucket */}
      <Section id="bucket" title="C — Bucket Selection">
        <div className="inp-field">
          <div className="inp-label">Selection Mode</div>
          <select
            className="inp-sel"
            value={inputs.auto_bucket ? "auto" : "manual"}
            onChange={(e) => setField("auto_bucket", e.target.value === "auto")}
          >
            <option value="auto">Auto Select</option>
            <option value="manual">Manual Select</option>
          </select>
        </div>
        {!inputs.auto_bucket && (
          <div className="inp-field">
            <div className="inp-label">Bucket Series</div>
            <select
              className="inp-sel"
              value={inputs.bucket_id}
              onChange={(e) => setField("bucket_id", e.target.value)}
            >
              {BUCKET_SERIES.map((b) => (
                <option key={b.id} value={b.id}>{b.label}</option>
              ))}
            </select>
          </div>
        )}
        {results?.bucket && (
          <div style={{ padding: "6px 0", fontSize: 10, color: "var(--muted2)", fontFamily: "var(--ff-mono)" }}>
            Selected:{" "}
            <span style={{ color: "var(--blue)" }}>{results.bucket.id}</span>{" "}
            · {results.bucket.W}×{results.bucket.H}mm · {results.bucket.V}L
          </div>
        )}
      </Section>

      {/* D — Belt & Drive */}
      <Section id="belt" title="D — Belt & Drive">
        <div className="inp-row">
          <Field label="Friction μ" k="mu" unit="" min={0.1} max={0.6} step={0.01} inputs={inputs} setField={setField} />
          <Field label="Wrap Angle" k="wrap_deg" unit="°" min={90} max={240} inputs={inputs} setField={setField} />
        </div>
        <Field label="Service Factor" k="sf" unit="" min={1.0} max={2.0} step={0.05} inputs={inputs} setField={setField} />
      </Section>

      <div style={{ padding: 8, marginTop: "auto" }}>
        <div
          style={{
            fontSize: 9,
            color: "var(--faint)",
            textAlign: "center",
            fontFamily: "var(--ff-ui)",
            letterSpacing: ".06em",
          }}
        >
          VECTRIX™ · AKSHAYVIPRA EL-MEC
          <br />
          VECTOMEC™ Bucket Elevator v1.0
        </div>
      </div>
    </div>
  );
}
