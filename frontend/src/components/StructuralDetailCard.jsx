// StructuralDetailCard.jsx
// Pure display component — all values from results dict, no computation.
// Displays hub, key_check/weld_check, lagging, end_disc, bolt_fatigue blocks.
//
// v1.9.9: end_disc.t_specified_mm (+20% spec) now comes from the backend
// (structural.py pulley_end_disc()), eliminating Math.ceil(t * 1.20) here.
// Hub connection branches on results.shaft_hub_connection: keyed shafts show
// key_check; welded shafts show weld_check instead.

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

function Row({ label, value, status }) {
  const color =
    status === "ok"   ? "var(--success)"  :
    status === "warn" ? "var(--warning)"  :
    status === "fail" ? "var(--danger)"   :
                        "var(--text2)";
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "baseline",
      padding: "4px 12px",
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

const passIcon   = (ok) => ok ? "✓ PASS" : "✗ FAIL";
const passStatus = (ok) => ok ? "ok" : "fail";

export default function StructuralDetailCard({ results }) {
  if (!results) return null;
  const { hub, key_check, weld_check, lagging, end_disc, bolt_fatigue,
          shaft_hub_connection } = results;
  if (!hub && !lagging && !end_disc && !bolt_fatigue) return null;

  const isWelded = shaft_hub_connection === "welded";

  return (
    <div style={{
      background: "var(--panel)",
      borderRadius: "var(--r-md)",
      border: "1px solid var(--border)",
      overflow: "hidden",
      margin: "10px 12px",
    }}>

      {/* ── Hub ── */}
      {hub && (
        <>
          <SectionHead label={isWelded
            ? "Hub — Welded Connection  ·  AWS D1.1"
            : "Hub & Keyway  ·  ASME B17.1"} />
          <Row label="Hub OD"      value={f(hub.d_hub_mm, 1, " mm")} />
          <Row label="Hub length"  value={f(hub.L_hub_mm, 1, " mm")} />

          {/* Keyed: show key dimensions + key_check */}
          {!isWelded && (
            <>
              <Row label="Key  b × h" value={
                hub.b_key_mm != null
                  ? `${hub.b_key_mm} × ${hub.h_key_mm} mm`
                  : "—"
              } />
              {key_check && <>
                <Row
                  label="Shear stress"
                  value={`${f(key_check.tau_actual_MPa, 1)} / ${f(key_check.tau_allow_MPa, 0)} MPa`}
                  status={key_check.shear_pass ? "ok" : "fail"}
                />
                <Row
                  label="Bearing stress"
                  value={`${f(key_check.sigma_actual_MPa, 1)} / ${f(key_check.sigma_allow_MPa, 0)} MPa`}
                  status={key_check.bearing_pass ? "ok" : "fail"}
                />
                <Row
                  label="Keyway result"
                  value={passIcon(key_check.pass)}
                  status={passStatus(key_check.pass)}
                />
              </>}
            </>
          )}

          {/* Welded: show weld throat + weld_check */}
          {isWelded && weld_check && (
            <>
              <Row label="Weld throat" value={f(weld_check.t_throat_mm, 1, " mm")} />
              <Row label="Governed by" value={(weld_check.governed_by ?? "—").replace(/_/g, " ")} />
              <Row
                label="Weld shear stress"
                value={`${f(weld_check.tau_torsion_MPa, 1)} / ${f(weld_check.weld_allow_MPa, 0)} MPa`}
                status={weld_check.tau_torsion_MPa < weld_check.weld_allow_MPa ? "ok" : "fail"}
              />
              <Row label="Weld spec" value="E70xx, full 360° around shaft OD" />
            </>
          )}
        </>
      )}

      {/* ── Pulley Lagging ── */}
      {lagging && (
        <>
          <SectionHead label="Pulley Lagging  ·  CEMA 375 §4" />
          <Row label="Type"              value={lagging.lagging_type?.replace(/_/g, " ") ?? "—"} />
          <Row label="Thickness"         value={f(lagging.thickness_mm, 0, " mm")} />
          <Row label="μ dry / wet"       value={
            lagging.mu_dry != null
              ? `${f(lagging.mu_dry, 2)} / ${f(lagging.mu_wet, 2)}`
              : "—"
          } />
          <Row label="μ operating"       value={f(lagging.mu_operating, 2)} />
          <Row label="Euler limit e^(μθ)" value={f(lagging.euler_ratio_lagged, 3)} />
          <Row
            label="Belt ratio R/T3"
            value={f(lagging.belt_ratio_tight_slack, 3)}
            status={lagging.slip_safe ? "ok" : "fail"}
          />
          <Row
            label="Slip check"
            value={passIcon(lagging.slip_safe)}
            status={passStatus(lagging.slip_safe)}
          />
          {lagging.upgraded && (
            <Row label="Auto-upgraded" value="Ceramic — slip prevention" status="warn" />
          )}
        </>
      )}

      {/* ── Pulley End Disc ── */}
      {end_disc && (
        <>
          <SectionHead label="Pulley End Disc  ·  CEMA Pulley Standard" />
          <Row label="Min. thickness (calc.)"
            value={f(end_disc.t_governing_mm, 1, " mm")} />
          <Row
            label="Specify in drawings"
            value={end_disc.t_specified_mm != null
              ? `${end_disc.t_specified_mm} mm  (+20%)`
              : "—"}
          />
          <Row label="Governed by"          value={end_disc.governed_by ?? "—"} />
          <Row label="σ_membrane"           value={f(end_disc.sigma_membrane_MPa, 1, " MPa")} />
          <Row label="σ_bending"            value={f(end_disc.sigma_bending_MPa, 1, " MPa")} />
          <Row
            label="Force per disc"
            value={end_disc.F_per_disc_N != null
              ? `${(end_disc.F_per_disc_N / 1000).toFixed(2)} kN`
              : "—"}
          />
          <Row
            label="Arm (R_shell − R_hub)"
            value={end_disc.arm_m != null
              ? `${(end_disc.arm_m * 1000).toFixed(0)} mm`
              : "—"}
          />
        </>
      )}

      {/* ── Bucket Bolt Fatigue ── */}
      {bolt_fatigue && (
        <>
          <SectionHead label="Bucket Bolt Fatigue  ·  CEMA 375 §7" />
          <Row
            label="Bolts"
            value={bolt_fatigue.n_bolts != null
              ? `${bolt_fatigue.n_bolts}× M${bolt_fatigue.bolt_dia_mm}  grade ${bolt_fatigue.bolt_grade}`
              : "—"}
          />
          <Row
            label="Peak centrifugal load"
            value={bolt_fatigue.F_max_N != null
              ? `${bolt_fatigue.F_max_N.toFixed(0)} N`
              : "—"}
          />
          <Row label="σ_mean = σ_alt"  value={f(bolt_fatigue.sigma_mean_MPa, 2, " MPa")} />
          <Row label="Se  (Kf = 2.2)"  value={f(bolt_fatigue.S_e_MPa, 1, " MPa")} />
          <Row label="Sut"             value={f(bolt_fatigue.S_ut_MPa, 0, " MPa")} />
          <Row
            label="Goodman ratio"
            value={f(bolt_fatigue.goodman_ratio, 3)}
            status={
              bolt_fatigue.goodman_ratio > 1   ? "fail" :
              bolt_fatigue.goodman_ratio > 0.7 ? "warn" : "ok"
            }
          />
          <Row
            label="Fatigue life"
            value={
              bolt_fatigue.pass_infinite_life
                ? "∞  Infinite"
                : bolt_fatigue.life_years != null
                  ? `${bolt_fatigue.life_years.toFixed(1)} yr`
                  : "—"
            }
            status={passStatus(bolt_fatigue.pass_infinite_life)}
          />
        </>
      )}
    </div>
  );
}