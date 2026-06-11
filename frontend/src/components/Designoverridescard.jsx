// DesignOverridesCard.jsx
// Gives the engineer direct control over every dimension the app auto-calculates:
//   • Take-up type (gravity / screw / auto)
//   • Screw take-up: core diameter + shank length
//   • Head shaft diameter
//   • Belt width
//   • Casing plate thickness
//
// All fields default to 0 (= auto).  Setting a value > 0 tells solve_elevator()
// to use that dimension and report pass/fail against the calculated minimum.
// The "calc" tooltip shows what the last solve produced so the engineer can
// see exactly what they're overriding.

import { useState } from "react";

// Standard commercial sizes shown as quick-select pills
const SCREW_SIZES = [20, 25, 32, 40, 50, 63, 80, 100];
const SHAFT_SIZES = [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100];
const BELT_WIDTHS = [300, 350, 400, 450, 500, 600, 650, 750, 800, 1000, 1200];
const CASING_T = [3, 4, 5, 6, 8, 10, 12];

function SizeLabel({ label, tip }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 3,
      }}
    >
      <span
        style={{
          fontSize: 9,
          color: "var(--text3)",
          letterSpacing: ".04em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      {tip && (
        <span
          style={{
            fontSize: 8,
            color: "var(--muted)",
            fontFamily: "JetBrains Mono,monospace",
          }}
        >
          {tip}
        </span>
      )}
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  placeholder,
  unit,
  min = 0,
  step = 1,
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <input
        type="number"
        value={value || ""}
        min={min}
        step={step}
        placeholder={placeholder || "0 = auto"}
        onChange={(e) =>
          onChange(e.target.value === "" ? 0 : parseFloat(e.target.value))
        }
        style={{
          flex: 1,
          padding: "4px 6px",
          fontSize: 11,
          borderRadius: 4,
          border: "1px solid var(--border)",
          background: value > 0 ? "rgba(74,158,255,.08)" : "var(--panel2)",
          color: value > 0 ? "var(--primary)" : "var(--text2)",
          fontFamily: "JetBrains Mono,monospace",
          outline: "none",
        }}
      />
      {unit && (
        <span style={{ fontSize: 9, color: "var(--text3)", minWidth: 24 }}>
          {unit}
        </span>
      )}
    </div>
  );
}

function Pills({ sizes, value, onSelect, unit = "mm" }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 4 }}>
      {sizes.map((s) => {
        const active = Math.abs(parseFloat(value) - s) < 0.5;
        return (
          <button
            key={s}
            onClick={() => onSelect(active ? 0 : s)}
            style={{
              padding: "2px 6px",
              fontSize: 8.5,
              borderRadius: 3,
              cursor: "pointer",
              border: `1px solid ${active ? "var(--primary)" : "var(--border)"}`,
              background: active ? "var(--primary-dim)" : "var(--panel2)",
              color: active ? "var(--primary)" : "var(--text3)",
              fontFamily: "JetBrains Mono,monospace",
              fontWeight: active ? 700 : 400,
            }}
          >
            {s}
            {unit}
          </button>
        );
      })}
    </div>
  );
}

export default function DesignOverridesCard({ inputs, setField, results }) {
  const [open, setOpen] = useState(false);

  // Pull calculated minimums from results to show as hints
  const ts = results?.takeup_screw || {};
  const tg = results?.takeup_gravity || {};
  const shft = results?.d_mm || null;
  const bw = results?.belt_w || null;
  const ct = results?.casing_panel?.t_calc_mm || null;

  const hasAnyOverride =
    inputs.takeup_type !== "gravity" ||
    inputs.takeup_screw_d_mm > 0 ||
    inputs.takeup_screw_len_m > 0 ||
    inputs.shaft_d_override_mm > 0 ||
    inputs.belt_width_override_mm > 0 ||
    inputs.casing_t_override_mm > 0;

  return (
    <div style={{ borderTop: "1px solid var(--border)" }}>
      {/* Header / toggle */}
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          cursor: "pointer",
          background: hasAnyOverride
            ? "rgba(74,158,255,.06)"
            : open
              ? "rgba(255,255,255,.02)"
              : "transparent",
        }}
        onMouseEnter={(e) =>
          !hasAnyOverride &&
          (e.currentTarget.style.background = "rgba(255,255,255,.03)")
        }
        onMouseLeave={(e) =>
          !hasAnyOverride &&
          !open &&
          (e.currentTarget.style.background = "transparent")
        }
      >
        <div>
          <span
            style={{ fontSize: 10, fontWeight: 700, color: "var(--text2)" }}
          >
            Design Overrides
          </span>
          {hasAnyOverride && (
            <span
              style={{
                marginLeft: 6,
                fontSize: 8,
                fontWeight: 700,
                padding: "1px 5px",
                borderRadius: 999,
                background: "var(--primary-dim)",
                color: "var(--primary)",
                border: "1px solid var(--primary-border)",
              }}
            >
              ACTIVE
            </span>
          )}
          <div style={{ fontSize: 8, color: "var(--text3)", marginTop: 1 }}>
            Specify any dimension — app checks against calculated minimum
          </div>
        </div>
        <span
          style={{
            fontSize: 9,
            color: "var(--text3)",
            transform: open ? "rotate(90deg)" : "rotate(0)",
            transition: "transform .15s",
          }}
        >
          ›
        </span>
      </div>

      {open && (
        <div
          style={{
            padding: "0 12px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {/* ── Take-up type ───────────────────────────────────────── */}
          <div>
            <SizeLabel label="Take-up type" />
            <div style={{ display: "flex", gap: 4 }}>
              {[
                ["gravity", "Gravity CW"],
                ["screw", "Screw"],
                ["auto", "Auto"],
              ].map(([v, lbl]) => {
                const active = inputs.takeup_type === v;
                return (
                  <button
                    key={v}
                    onClick={() => setField("takeup_type", v)}
                    style={{
                      flex: 1,
                      padding: "5px 4px",
                      fontSize: 9.5,
                      borderRadius: 4,
                      cursor: "pointer",
                      border: `1px solid ${active ? "var(--primary)" : "var(--border)"}`,
                      background: active
                        ? "var(--primary-dim)"
                        : "var(--panel2)",
                      color: active ? "var(--primary)" : "var(--text3)",
                      fontWeight: active ? 700 : 400,
                      fontFamily: "inherit",
                    }}
                  >
                    {lbl}
                  </button>
                );
              })}
            </div>
            <div style={{ fontSize: 8, color: "var(--text3)", marginTop: 3 }}>
              {inputs.takeup_type === "gravity"
                ? `Counterweight: ${tg.W_counterweight_kg_gross?.toFixed(0) ?? "—"} kg  ·  Travel: ${tg.travel_m?.toFixed(2) ?? "—"} m`
                : inputs.takeup_type === "screw"
                  ? `Screw load: ${(ts.F_screw_N / 1000)?.toFixed(1) ?? "—"} kN  ·  Buckling SF: ${ts.SF_buckling ?? "—"}`
                  : "Auto: gravity if H ≥ 15 m, screw otherwise"}
            </div>
          </div>

          {/* ── Screw take-up parameters (shown when screw or auto) ── */}
          {inputs.takeup_type !== "gravity" && (
            <div
              style={{
                padding: "8px 10px",
                borderRadius: 5,
                background: "var(--panel2)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  fontSize: 8.5,
                  fontWeight: 700,
                  color: "var(--text3)",
                  marginBottom: 6,
                  letterSpacing: ".04em",
                  textTransform: "uppercase",
                }}
              >
                Screw Take-up
              </div>

              <SizeLabel
                label="Core diameter"
                tip={
                  ts.d_core_min_mm
                    ? `calc min: ${ts.d_core_min_mm?.toFixed(0)} mm`
                    : ""
                }
              />
              <NumberInput
                value={inputs.takeup_screw_d_mm}
                onChange={(v) => setField("takeup_screw_d_mm", v)}
                unit="mm"
              />
              <Pills
                sizes={SCREW_SIZES}
                value={inputs.takeup_screw_d_mm}
                onSelect={(v) => setField("takeup_screw_d_mm", v)}
              />

              {/* Buckling SF indicator */}
              {ts.SF_buckling != null && (
                <div
                  style={{
                    marginTop: 5,
                    padding: "3px 7px",
                    borderRadius: 3,
                    background: ts.buckling_safe
                      ? "rgba(31,184,110,.10)"
                      : "rgba(224,82,82,.10)",
                    border: `1px solid ${ts.buckling_safe ? "var(--success-border)" : "var(--danger-border)"}`,
                    fontSize: 8.5,
                    color: ts.buckling_safe
                      ? "var(--success)"
                      : "var(--danger)",
                  }}
                >
                  Buckling SF = {ts.SF_buckling?.toFixed(2)}
                  {ts.buckling_safe
                    ? " ✓"
                    : " ✗  →  increase diameter or reduce length"}
                </div>
              )}

              <div style={{ marginTop: 8 }}>
                <SizeLabel
                  label="Shank length"
                  tip={
                    ts.travel_m
                      ? `travel req: ${ts.travel_m?.toFixed(2)} m`
                      : ""
                  }
                />
                <NumberInput
                  value={inputs.takeup_screw_len_m}
                  onChange={(v) => setField("takeup_screw_len_m", v)}
                  unit="m"
                  step={0.05}
                />
              </div>
            </div>
          )}

          {/* ── Head shaft ─────────────────────────────────────────── */}
          <div>
            <SizeLabel
              label="Head shaft diameter"
              tip={shft ? `calc min: ${Number(shft).toFixed(0)} mm` : ""}
            />
            <NumberInput
              value={inputs.shaft_d_override_mm}
              onChange={(v) => setField("shaft_d_override_mm", v)}
              unit="mm"
            />
            <Pills
              sizes={SHAFT_SIZES}
              value={inputs.shaft_d_override_mm}
              onSelect={(v) => setField("shaft_d_override_mm", v)}
            />
            {inputs.shaft_d_override_mm > 0 && shft && (
              <div
                style={{
                  marginTop: 4,
                  fontSize: 8.5,
                  color:
                    inputs.shaft_d_override_mm >= shft
                      ? "var(--success)"
                      : "var(--danger)",
                }}
              >
                {inputs.shaft_d_override_mm >= shft
                  ? `✓ ${inputs.shaft_d_override_mm} mm ≥ ${Number(shft).toFixed(0)} mm minimum`
                  : `✗ ${inputs.shaft_d_override_mm} mm < ${Number(shft).toFixed(0)} mm minimum — will FAIL shaft check`}
              </div>
            )}
          </div>

          {/* ── Belt width ─────────────────────────────────────────── */}
          <div>
            <SizeLabel
              label="Belt width"
              tip={bw ? `auto-selected: ${bw} mm` : ""}
            />
            <NumberInput
              value={inputs.belt_width_override_mm}
              onChange={(v) => setField("belt_width_override_mm", v)}
              unit="mm"
            />
            <Pills
              sizes={BELT_WIDTHS}
              value={inputs.belt_width_override_mm}
              onSelect={(v) => setField("belt_width_override_mm", v)}
            />
          </div>

          {/* ── Casing plate thickness ─────────────────────────────── */}
          <div>
            <SizeLabel
              label="Casing plate thickness"
              tip={ct ? `calc min: ${ct} mm` : ""}
            />
            <NumberInput
              value={inputs.casing_t_override_mm}
              onChange={(v) => setField("casing_t_override_mm", v)}
              unit="mm"
              step={0.5}
            />
            <Pills
              sizes={CASING_T}
              value={inputs.casing_t_override_mm}
              onSelect={(v) => setField("casing_t_override_mm", v)}
            />
            {inputs.casing_t_override_mm > 0 && ct && (
              <div
                style={{
                  marginTop: 4,
                  fontSize: 8.5,
                  color:
                    inputs.casing_t_override_mm >= ct
                      ? "var(--success)"
                      : "var(--warning)",
                }}
              >
                {inputs.casing_t_override_mm >= ct
                  ? `✓ ${inputs.casing_t_override_mm} mm ≥ ${ct} mm minimum`
                  : `⚠ ${inputs.casing_t_override_mm} mm < ${ct} mm — deflection check may fail`}
              </div>
            )}
          </div>

          {/* Reset link */}
          {hasAnyOverride && (
            <button
              onClick={() => {
                setField("takeup_type", "gravity");
                setField("takeup_screw_d_mm", 0);
                setField("takeup_screw_len_m", 0);
                setField("shaft_d_override_mm", 0);
                setField("belt_width_override_mm", 0);
                setField("casing_t_override_mm", 0);
              }}
              style={{
                padding: "4px 10px",
                fontSize: 9,
                cursor: "pointer",
                borderRadius: 4,
                border: "1px solid var(--border)",
                background: "transparent",
                color: "var(--text3)",
                alignSelf: "flex-start",
                fontFamily: "inherit",
              }}
            >
              Reset all overrides to auto
            </button>
          )}
        </div>
      )}
    </div>
  );
}
