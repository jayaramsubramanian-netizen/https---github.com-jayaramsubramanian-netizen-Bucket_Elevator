// TakeupCasingCard.jsx
// Displays take-up and casing structural results from structural.py v1.3.0:
//   takeup_gravity   → gravity_takeup() result
//   takeup_screw     → screw_takeup() result
//   casing_t_mm      → casing_plate_thickness() scalar
//   casing_stiffener → casing_stiffener_spacing() result
//   casing_panel     → casing_panel_deflection() result
//
// Both take-up types are always computed by solve_elevator().
// This card displays gravity take-up first (the common case for H > 15m)
// then the screw alternative, so the engineer can compare.

// ── Shared sub-components ──────────────────────────────────────────────────

function SectionHead({ label }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 700, letterSpacing: ".08em",
      textTransform: "uppercase", color: "var(--text3)",
      padding: "9px 12px 5px",
      borderTop: "1px solid var(--border)",
      background: "var(--panel2)",
    }}>{label}</div>
  );
}

function Row({ label, value, status, indent }) {
  const color =
    status === "ok"   ? "var(--success)" :
    status === "warn" ? "var(--warning)" :
    status === "fail" ? "var(--danger)"  :
                        "var(--text2)";
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "baseline",
      padding: "4px 12px 4px",
      paddingLeft: indent ? 24 : 12,
      borderBottom: "1px solid var(--border)",
      minHeight: 26,
    }}>
      <span style={{
        fontSize: 10.5, color: "var(--text3)", flex: "0 1 auto",
        paddingRight: 8, lineHeight: 1.4,
      }}>{label}</span>
      <span style={{
        fontSize: 10.5, fontFamily: "JetBrains Mono, monospace",
        color, textAlign: "right", flexShrink: 0,
      }}>{value ?? "—"}</span>
    </div>
  );
}

const f = (v, dp = 1, suffix = "") =>
  v != null && !Number.isNaN(Number(v))
    ? `${Number(v).toFixed(dp)}${suffix}`
    : "—";

const passIcon   = (ok) => ok  ? "✓ PASS" : "✗ FAIL";
const passStatus = (ok) => ok  ? "ok"     : "fail";
const okWarn     = (ok) => ok  ? "ok"     : "warn";

// ── Main component ────────────────────────────────────────────────────────

export default function TakeupCasingCard({ results }) {
  if (!results) return null;
  const {
    takeup_gravity, takeup_screw,
    casing_t_mm, casing_panel, casing_stiffener,
  } = results;

  if (!takeup_gravity && !casing_t_mm) return null;

  return (
    <div style={{
      background: "var(--panel)",
      borderRadius: "var(--r-md)",
      border: "1px solid var(--border)",
      overflow: "hidden",
      margin: "10px 12px",
    }}>

      {/* ── Gravity Take-Up ── */}
      {takeup_gravity && (
        <>
          <SectionHead label="Gravity Take-Up  ·  CEMA 375 §4" />
          <Row
            label="Counterweight — net"
            value={f(takeup_gravity.W_counterweight_kg_net, 0, " kg")}
          />
          <Row
            label="Counterweight — gross (+10%)"
            value={f(takeup_gravity.W_counterweight_kg_gross, 0, " kg")}
          />
          <Row
            label="Travel required"
            value={
              takeup_gravity.travel_m != null
                ? `${(takeup_gravity.travel_m * 1000).toFixed(0)} mm`
                : "—"
            }
          />
          <Row
            label="  Thermal component"
            value={
              takeup_gravity.travel_thermal_m != null
                ? `${(takeup_gravity.travel_thermal_m * 1000).toFixed(0)} mm`
                : "—"
            }
            indent
          />
          <Row
            label="  Belt elongation"
            value={
              takeup_gravity.travel_elongation_m != null
                ? `${(takeup_gravity.travel_elongation_m * 1000).toFixed(0)} mm`
                : "—"
            }
            indent
          />
          <Row label="  CEMA minimum" value="300 mm" indent />
        </>
      )}

      {/* ── Screw Take-Up (alternative) ── */}
      {takeup_screw && (
        <>
          <SectionHead label="Screw Take-Up  ·  Alternative" />
          <Row
            label="Screw load"
            value={
              takeup_screw.F_screw_N != null
                ? `${(takeup_screw.F_screw_N / 1000).toFixed(2)} kN`
                : "—"
            }
          />
          <Row label="Min. core dia."  value={f(takeup_screw.d_core_min_mm, 1, " mm")} />
          <Row label="Turns required"  value={f(takeup_screw.turns_required, 0, " turns")} />
          <Row
            label="Buckling SF"
            value={f(takeup_screw.SF_buckling, 2)}
            status={passStatus(takeup_screw.buckling_safe)}
          />
          <Row
            label="Buckling check"
            value={
              takeup_screw.buckling_safe
                ? "✓ PASS  (SF ≥ 3.0)"
                : "✗ FAIL — add guide or increase dia."
            }
            status={passStatus(takeup_screw.buckling_safe)}
          />
        </>
      )}

      {/* ── Casing Structural ── */}
      {(casing_t_mm || casing_stiffener || casing_panel) && (
        <>
          <SectionHead label="Casing Design  ·  CEMA 375 §7" />
          {casing_t_mm != null && (
            <Row label="Plate thickness" value={`${casing_t_mm} mm`} />
          )}
          {casing_stiffener && <>
            <Row
              label="Max stiffener pitch"
              value={f(casing_stiffener.max_spacing_mm, 0, " mm")}
            />
            <Row
              label="Recommended pitch  (×0.85)"
              value={f(casing_stiffener.recommended_mm, 0, " mm")}
            />
            <Row label="Wind pressure"     value={f(casing_stiffener.wind_pressure_Pa, 0, " Pa")} />
            <Row label="Deflection limit"  value={casing_stiffener.defl_limit ?? "L / 360"} />
          </>}
          {casing_panel && <>
            <Row
              label="Panel δ actual"
              value={f(casing_panel.delta_actual_mm, 2, " mm")}
              status={okWarn(casing_panel.status === "ok")}
            />
            <Row
              label="Panel δ allowed"
              value={f(casing_panel.delta_allow_mm, 2, " mm")}
            />
            <Row
              label="Panel σ_max"
              value={f(casing_panel.sigma_max_MPa, 1, " MPa")}
            />
            <Row
              label="Panel check"
              value={
                casing_panel.status === "ok"
                  ? "✓ PASS"
                  : "⚠ Reduce stiffener spacing"
              }
              status={okWarn(casing_panel.status === "ok")}
            />
          </>}
        </>
      )}
    </div>
  );
}