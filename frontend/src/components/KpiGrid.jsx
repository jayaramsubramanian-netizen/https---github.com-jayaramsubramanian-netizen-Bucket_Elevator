// KpiGrid.jsx — 12-card KPI display
// Field names match FastAPI /be/solve response shape.
// Every value access is null-safe — no crash on partial results.

const fmt   = (v, dp = 2, fb = '—') =>
  (v == null || !isFinite(Number(v))) ? fb : Number(v).toFixed(dp)

const fmtDiv = (a, b, dp = 2) =>
  (a == null || !b) ? '—' : fmt(a / b, dp)

export default function KpiGrid({ results, inputs }) {
  // Guard: do not render until results AND required nested objects are present
  if (!results || !results.bucket || !inputs) return null

  const r   = results
  const inp = inputs

  // Convenience aliases that map FastAPI names → readable locals
  const Q            = r.Q_th
  const v            = r.v_ms
  const P_total      = r.power_P_total
  const P_lift       = r.power_P_lift
  const motor        = r.motor_kW
  const T1           = r.T1
  const T2           = r.T2
  const tension_ratio = r.tension_ratio
  const d_mm         = r.shaft_d_mm
  const T_Nm         = r.shaft_torque_Nm
  const belt_w       = r.belt_width_mm
  const belt_cls     = r.belt_class
  const cr           = r.centrifugal_ratio
  const theta_rel    = r.release_angle_deg
  const L10          = r.L10_hours
  // Bucket fields: FastAPI returns width_mm, volume_L, series, style
  const bkt          = r.bucket
  // Material: FastAPI returns r.material (may be null if no mat_id given)
  const mat          = r.material
  const matKm        = mat?.Km  ?? inp.Km
  const matName      = mat?.name ?? 'Custom'
  const rho          = mat?.rho ?? inp.rho_kgm3

  // Status helpers
  const capOK   = (Q   ?? 0) >= inp.Q_req
  const speedOK = (v   ?? 0) >= 0.5 && (v ?? 0) <= 2.5
  const crOK    = (cr  ?? 0) >= 1.0 && (cr ?? 0) <= 2.5
  const beltOK  = (T1  ?? 0) <= 50000
  const l10OK   = (L10 ?? 0) >= 20000

  // Fill sub-label: volume_L is the FastAPI field
  const fillVol = bkt?.volume_L != null
    ? (bkt.volume_L * inp.fill_pct / 100).toFixed(2)
    : '—'

  // L10 display — show "42k" for values > 9999
  const l10Display = L10 == null ? '—'
    : L10 > 9999 ? `${fmt(L10 / 1000, 0)}k`
    : fmt(L10, 0)

  const kpis = [
    {
      label:  'Capacity',
      value:  fmt(Q, 1),
      unit:   't/h',
      status: capOK ? 'ok' : 'fail',
      sub:    `req ${inp.Q_req} t/h`,
    },
    {
      label:  'Belt Speed',
      value:  fmt(v, 2),
      unit:   'm/s',
      status: speedOK ? 'ok' : 'warn',
      sub:    `${inp.n_rpm} RPM`,
    },
    {
      label:  'Total Power',
      value:  fmt(P_total, 2),
      unit:   'kW',
      status: 'info',
      sub:    `lift ${fmt(P_lift, 2)} kW`,
    },
    {
      label:  'Motor Selected',
      value:  motor ?? '—',
      unit:   'kW',
      status: 'info',
      sub:    `SF ${inp.sf}`,
    },
    {
      label:  'Tight-side T₁',
      value:  fmtDiv(T1, 1000),
      unit:   'kN',
      status: beltOK ? 'ok' : 'fail',
      sub:    `ratio ${fmt(tension_ratio, 2)} · ${belt_cls ?? ''}`,
    },
    {
      label:  'Shaft Dia.',
      value:  fmt(d_mm, 0),
      unit:   'mm',
      status: 'info',
      sub:    `T = ${fmtDiv(T_Nm, 1000, 2)} kNm`,
    },
    {
      label:  'Belt Width',
      value:  belt_w ?? '—',
      unit:   'mm',
      status: 'info',
      sub:    `bucket ${bkt?.width_mm ?? '—'} mm`,
    },
    {
      label:  'Centrifugal Ratio',
      value:  fmt(cr, 3),
      unit:   '—',
      status: crOK ? 'ok' : 'warn',
      sub:    `θ_rel ${fmt(theta_rel, 1)}°`,
    },
    {
      label:  'Bearing L10',
      value:  l10Display,
      unit:   'h',
      status: l10OK ? 'ok' : 'warn',
      sub:    `@ ${inp.n_rpm} rpm`,
    },
    {
      label:  'Bucket Series',
      value:  bkt?.series ?? '—',
      unit:   '',
      status: 'info',
      // volume_L is the FastAPI field; Km comes from material or input
      sub:    `${bkt?.volume_L ?? '—'}L · ${bkt?.style ?? ''} · Km=${fmt(matKm, 2)}`,
    },
    {
      label:  'Material',
      value:  rho ?? '—',
      unit:   'kg/m³',
      status: 'info',
      sub:    matName,
    },
    {
      label:  'Fill Factor',
      value:  inp.fill_pct,
      unit:   '%',
      status: 'info',
      sub:    `${fillVol} L/bucket`,
    },
  ]

  const cardClass = { ok: 'ok', fail: 'fail', warn: 'warn', info: '' }

  return (
    <div className="results-grid">
      {kpis.map((k, i) => (
        <div key={i} className={`res-card ${cardClass[k.status] || ''}`}>
          <div className="res-label">{k.label}</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
            <div className="res-value">{k.value}</div>
            {k.unit && <div className="res-unit">{k.unit}</div>}
          </div>
          <div className="res-sub">{k.sub}</div>
        </div>
      ))}
    </div>
  )
}