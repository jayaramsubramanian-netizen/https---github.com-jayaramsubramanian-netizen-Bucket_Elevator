// ElevatorSchematic.jsx — Tasks 11 + 12: Full Engineering Drawing
//
// CHANGES FROM PREVIOUS VERSION
// ──────────────────────────────
// Task 11:
//   • Animated belt: CSS @keyframes on strokeDashoffset — belt moves up
//     on the carrying side, down on the return side
//   • Hover callouts: onMouseEnter/Leave on head pulley, boot pulley,
//     motor, belt, buckets → floating engineering detail box
//   • Lagging ring on head pulley (outer stroke = lagging)
//   • Discharge chute plate drawn at head section
//   • Drive train: motor body + coupling disc + gearbox block
//   • Engineering drawing grid background (light construction lines)
//   • Title block (bottom-right corner) with doc ref, scale, date
//
// Task 12:
//   • Plan view completely redrawn as head-section cross-section:
//     pulley cylinder (side view of a circle = ellipse), shaft,
//     bearing housings, lagging, belt, buckets in plan, casing plates,
//     all with dimension lines and witness lines
//
// Bug fixes:
//   • C palette updated to new design system colors
//   • r.v_ms → r.v, r.Q_th → r.Q in KPI pills
//   • position:relative on root div so KPI pills absolute-position correctly
//   • Double-click on canvas → reset zoom/pan (was in tip, not implemented)

import { useState, useRef, useCallback, useEffect } from "react";

// ── Updated color palette — new design system ─────────────────────────────
const C = {
  bg:       "#0f172a",
  casing:   "#243247",
  casFill:  "#162032",
  belt:     "#14b8a6",
  beltRtn:  "#0f766e",
  bucket:   "#3b82f6",
  pulley:   "#3b82f6",
  lagging:  "#f59e0b",
  hub:      "#0f172a",
  motor:    "#10b981",
  gearbox:  "#059669",
  coupling: "#6b7280",
  dim:      "#3d536b",
  dimTxt:   "#64748b",
  label:    "#475569",
  labelBr:  "#94a3b8",
  traj:     "#ef4444",
  feed:     "#f59e0b",
  chute:    "#f59e0b",
  text:     "#f1f5f9",
  text3:    "#64748b",
  border:   "#243247",
  panel:    "#162032",
  success:  "#10b981",
  warning:  "#f59e0b",
  danger:   "#ef4444",
  primary:  "#3b82f6",
  grid:     "rgba(59,130,246,.04)",
};

const VIEWS = [
  { id: "elevation",  label: "Elevation"    },
  { id: "plan",       label: "Head Section" },
  { id: "side",       label: "Side Section" },
  { id: "trajectory", label: "Trajectory"   },
];

function f(v, dp = 1, fallback = "—") {
  if (v == null || Number.isNaN(Number(v))) return fallback;
  return Number(v).toFixed(dp);
}

// ── Shared SVG defs (injected once per view) ─────────────────────────────
function Defs() {
  return (
    <defs>
      <marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill={C.feed} />
      </marker>
      <marker id="dimArr" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
        <path d="M0,0 L5,2.5 L0,5 Z" fill={C.dim} />
      </marker>
      <marker id="dimArrR" markerWidth="5" markerHeight="5" refX="1" refY="2.5" orient="auto-start-reverse">
        <path d="M0,0 L5,2.5 L0,5 Z" fill={C.dim} />
      </marker>
      {/* Belt animation — carrying side moves upward */}
      <style>{`
        @keyframes beltUp   { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -40; } }
        @keyframes beltDown { from { stroke-dashoffset: 0; } to { stroke-dashoffset:  40; } }
        .belt-carry  { animation: beltUp   1.2s linear infinite; }
        .belt-return { animation: beltDown 1.2s linear infinite; }
        @keyframes bucketFloat {
          0%   { transform: translateY(0px);   }
          50%  { transform: translateY(-3px);  }
          100% { transform: translateY(0px);   }
        }
      `}</style>
    </defs>
  );
}

// ── Engineering drawing grid background ─────────────────────────────────
function DrawingGrid({ W, H }) {
  const lines = [];
  const step = 20;
  for (let x = 0; x <= W; x += step)
    lines.push(<line key={`gx${x}`} x1={x} y1={0} x2={x} y2={H} stroke={C.grid} strokeWidth={0.5} />);
  for (let y = 0; y <= H; y += step)
    lines.push(<line key={`gy${y}`} x1={0} y1={y} x2={W} y2={y} stroke={C.grid} strokeWidth={0.5} />);
  return <g>{lines}</g>;
}

// ── Title block (bottom right) ──────────────────────────────────────────
function TitleBlock({ W, H, view, inputs, results }) {
  const r   = results || {};
  const inp = inputs  || {};
  const bw  = 200;
  const bh  = 52;
  const bx  = W - bw - 4;
  const by  = H - bh - 4;

  return (
    <g>
      <rect x={bx} y={by} width={bw} height={bh}
        fill={C.panel} stroke={C.dim} strokeWidth={0.8} />
      {/* Dividers */}
      <line x1={bx} y1={by + 16} x2={bx + bw} y2={by + 16} stroke={C.dim} strokeWidth={0.5} />
      <line x1={bx} y1={by + 32} x2={bx + bw} y2={by + 32} stroke={C.dim} strokeWidth={0.5} />
      <line x1={bx + 100} y1={by + 16} x2={bx + 100} y2={by + bh} stroke={C.dim} strokeWidth={0.5} />
      {/* Title */}
      <text x={bx + bw/2} y={by + 11} fontSize={8} fill={C.labelBr}
        fontWeight="700" textAnchor="middle" letterSpacing=".06em">
        VECTOMEC™ BUCKET ELEVATOR
      </text>
      {/* Fields */}
      <text x={bx + 4} y={by + 25} fontSize={7} fill={C.text3}>
        BUCKET: {r.bucket?.id ?? "—"}  {r.bucket?.W ?? "—"}×{r.bucket?.H ?? "—"}mm
      </text>
      <text x={bx + 104} y={by + 25} fontSize={7} fill={C.text3}>
        H = {inp.H_m ?? "—"} m
      </text>
      <text x={bx + 4} y={by + 40} fontSize={7} fill={C.text3}>
        {view.toUpperCase()} VIEW
      </text>
      <text x={bx + 104} y={by + 40} fontSize={7} fill={C.text3}>
        D = {inp.D_mm ?? "—"} mm
      </text>
      <text x={bx + 4} y={by + 50} fontSize={6} fill={C.label}>
        AKSHAYVIPRA EL-MEC  ·  VECTRIX™
      </text>
    </g>
  );
}

// ── Hover callout box ────────────────────────────────────────────────────
function Callout({ x, y, title, lines, W }) {
  const boxW  = 150;
  const lineH = 13;
  const boxH  = 18 + lines.length * lineH;
  // Clamp so callout stays inside SVG
  const bx = Math.min(x + 8, W - boxW - 4);
  const by = y - boxH / 2;

  return (
    <g style={{ pointerEvents: "none" }}>
      <rect x={bx} y={by} width={boxW} height={boxH}
        fill={C.panel} stroke={C.primary} strokeWidth={1}
        rx={4} opacity={0.96} />
      <text x={bx + 8} y={by + 12} fontSize={9} fontWeight="700"
        fill={C.primary} letterSpacing=".04em">{title}</text>
      {lines.map((line, i) => (
        <text key={i} x={bx + 8} y={by + 12 + (i + 1) * lineH}
          fontSize={8.5} fill={C.labelBr}
          fontFamily="JetBrains Mono, monospace">
          {line}
        </text>
      ))}
    </g>
  );
}

// ─── ELEVATION VIEW ──────────────────────────────────────────────────────────
function ElevationView({ inputs, results, W, H, hovered, setHovered }) {
  const inp = inputs || {};
  const r   = results || {};
  const bkt = r.bucket || {};

  const margin = { top: 54, bottom: 58, left: 52, right: 90 };
  const cx = W * 0.40;

  const headD_mm = Number(inp.D_mm || 500);
  const bootD_mm = Number(inp.boot_pulley_D_mm || 300);
  const _pScale  = Math.min(32, W * 0.065) / headD_mm;
  const rHead    = Math.max(14, Math.min(32, headD_mm * _pScale));
  const rBoot    = Math.max(10, Math.min(26, bootD_mm * _pScale));
  const casW     = rHead + 16;
  const topY     = margin.top + rHead;
  const botY     = H - margin.bottom - rBoot;
  const elevH    = botY - topY;
  const bltX_L   = cx - rHead * 0.62;
  const bltX_R   = cx + rHead * 0.62;

  const spacingMm = r.spacing != null ? Math.round(r.spacing * 1000) : null;
  const spacingPx = spacingMm != null
    ? (spacingMm / 1000) * (elevH / Math.max(inp.H_m || 25, 1))
    : null;

  // Discharge trajectory
  const traj = r.trajectory || [];
  const trajStr = (() => {
    const pts = traj.slice(0, 30);
    if (!pts.length) return "";
    const tx0 = pts[0].x || 0, ty0 = pts[0].y || 0;
    const scale = 0.12;
    return pts.map((p, i) => {
      const sx = cx + (p.x - tx0) * scale;
      const sy = topY - (p.y - ty0) * scale;
      return `${i === 0 ? "M" : "L"} ${sx.toFixed(1)} ${sy.toFixed(1)}`;
    }).join(" ");
  })();

  // Bucket positions (7 on carrying side, 3 on return)
  const nCarry  = 7;
  const buckets = Array.from({ length: nCarry }, (_, i) => ({
    x: bltX_L - 18,
    y: botY - 30 - i * (elevH - 50) / (nCarry - 1),
  }));

  // Callout data per hovered element
  const callouts = {
    head: {
      title: "HEAD PULLEY",
      lines: [
        `D = ${headD_mm} mm`,
        `n = ${inp.n_rpm ?? "—"} rpm`,
        `v = ${f(r.v, 3)} m/s`,
        `Lagged — rubber`,
      ],
    },
    boot: {
      title: "BOOT PULLEY",
      lines: [
        `D = ${bootD_mm} mm`,
        `K_takeup = ${inp.K_takeup ?? 0.7}`,
        `T3 = ${f(r.T3 != null ? r.T3/1000 : null, 2)} kN`,
        `Gravity take-up`,
      ],
    },
    motor: {
      title: "DRIVE",
      lines: [
        `Motor: ${r.motor_kw ?? "—"} kW`,
        `P_total: ${f(r.P_total, 2)} kW`,
        `T = ${f(r.T_Nm != null ? r.T_Nm/1000 : null, 2)} kNm`,
        `SF = ${inp.sf ?? "—"}`,
      ],
    },
    belt: {
      title: "BELT",
      lines: [
        `BW = ${r.belt_w ?? "—"} mm`,
        `Ply: ${r.belt_ply ?? "—"}`,
        `F_eff = ${f(r.F_eff != null ? r.F_eff/1000 : null, 2)} kN`,
        `T1 = ${f(r.T1 != null ? r.T1/1000 : null, 2)} kN`,
      ],
    },
    bucket: {
      title: `BUCKET ${bkt.id ?? "—"}`,
      lines: [
        `${bkt.W ?? "—"}×${bkt.H ?? "—"}mm`,
        `V = ${bkt.V ?? "—"} L`,
        `Spacing = ${spacingMm ?? "—"} mm`,
        `Fill: ${inp.fill_pct ?? "—"}%`,
      ],
    },
  };
  const co = hovered && callouts[hovered];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <Defs />
      <rect width={W} height={H} fill={C.bg} />
      <DrawingGrid W={W} H={H} />

      {/* ── Casing ─────────────────────────────────────────────────── */}
      <rect x={cx - casW} y={topY} width={casW * 2} height={elevH}
        fill={C.casFill} stroke={C.casing} strokeWidth={2} />
      {/* Casing centre-line */}
      <line x1={cx} y1={topY - 10} x2={cx} y2={botY + 10}
        stroke={C.dim} strokeWidth={0.7} strokeDasharray="6 3" />

      {/* ── Animated belt — carry side (left, going up) ─────────────── */}
      <line
        className="belt-carry"
        x1={bltX_L} y1={topY} x2={bltX_L} y2={botY}
        stroke={C.belt} strokeWidth={3}
        strokeDasharray="12 4"
      />
      {/* ── Animated belt — return side (right, going down) ────────── */}
      <line
        className="belt-return"
        x1={bltX_R} y1={topY} x2={bltX_R} y2={botY}
        stroke={C.beltRtn} strokeWidth={2}
        strokeDasharray="10 5"
        opacity={0.6}
      />

      {/* ── Invisible hover zone for belt ───────────────────────────── */}
      <rect
        x={cx - casW} y={topY} width={casW * 2} height={elevH}
        fill="transparent"
        onMouseEnter={() => setHovered("belt")}
        onMouseLeave={() => setHovered(null)}
        style={{ cursor: "crosshair" }}
      />

      {/* ── Buckets (carry side, animated upward) ───────────────────── */}
      {buckets.map((b, i) => (
        <g key={i}
          onMouseEnter={() => setHovered("bucket")}
          onMouseLeave={() => setHovered(null)}
          style={{ cursor: "help" }}
        >
          {/* Bucket body */}
          <rect x={b.x - 14} y={b.y - 7} width={14} height={10}
            fill={C.bucket} fillOpacity={0.8}
            stroke={C.casing} strokeWidth={0.8} rx={1} />
          {/* Bucket lip */}
          <line x1={b.x - 14} y1={b.y - 7} x2={b.x} y2={b.y - 7}
            stroke={C.belt} strokeWidth={1.2} />
        </g>
      ))}

      {/* ── Boot pulley ──────────────────────────────────────────────── */}
      <g onMouseEnter={() => setHovered("boot")}
         onMouseLeave={() => setHovered(null)}
         style={{ cursor: "help" }}>
        <circle cx={cx} cy={botY} r={rBoot}
          fill={C.pulley} fillOpacity={0.85}
          stroke={C.hub} strokeWidth={2} />
        <circle cx={cx} cy={botY} r={rBoot * 0.3} fill={C.hub} />
        {/* Shaft stub */}
        <line x1={cx - rBoot - 16} y1={botY} x2={cx - rBoot} y2={botY}
          stroke={C.dim} strokeWidth={3} strokeLinecap="round" />
        <line x1={cx + rBoot} y1={botY} x2={cx + rBoot + 16} y2={botY}
          stroke={C.dim} strokeWidth={3} strokeLinecap="round" />
      </g>
      {/* Take-up weight indicator */}
      <rect x={cx - 8} y={botY + rBoot + 4} width={16} height={18}
        fill={C.casing} stroke={C.dim} strokeWidth={1} rx={2} />
      <text x={cx} y={botY + rBoot + 15} fontSize={6.5} fill={C.text3}
        textAnchor="middle" fontWeight="700">T/U</text>
      <line x1={cx} y1={botY + rBoot + 2} x2={cx} y2={botY + rBoot + 4}
        stroke={C.dim} strokeWidth={1} />

      {/* ── Head pulley ──────────────────────────────────────────────── */}
      <g onMouseEnter={() => setHovered("head")}
         onMouseLeave={() => setHovered(null)}
         style={{ cursor: "help" }}>
        {/* Lagging ring */}
        <circle cx={cx} cy={topY} r={rHead + 3}
          fill="none" stroke={C.lagging} strokeWidth={3} opacity={0.6} />
        {/* Pulley body */}
        <circle cx={cx} cy={topY} r={rHead}
          fill={C.pulley} fillOpacity={0.85}
          stroke={C.hub} strokeWidth={2} />
        {/* Face hatching */}
        {[-1, 0, 1].map(k => (
          <line key={k}
            x1={cx + k * rHead * 0.4} y1={topY - rHead * 0.85}
            x2={cx + k * rHead * 0.4} y2={topY + rHead * 0.85}
            stroke={C.hub} strokeWidth={1} opacity={0.5} />
        ))}
        <circle cx={cx} cy={topY} r={rHead * 0.28} fill={C.hub} />
        {/* Shaft stubs */}
        <line x1={cx - rHead - 20} y1={topY} x2={cx - rHead} y2={topY}
          stroke={C.dim} strokeWidth={4} strokeLinecap="round" />
        <line x1={cx + rHead} y1={topY} x2={cx + rHead + 20} y2={topY}
          stroke={C.dim} strokeWidth={4} strokeLinecap="round" />
      </g>

      {/* ── Discharge chute ──────────────────────────────────────────── */}
      <path d={`M ${cx + rHead} ${topY - 6}
                L ${cx + rHead + 38} ${topY - 22}
                L ${cx + rHead + 50} ${topY - 8}
                L ${cx + rHead + 12} ${topY + 4} Z`}
        fill="rgba(245,158,11,.08)" stroke={C.chute} strokeWidth={1.5} />
      <text x={cx + rHead + 54} y={topY - 16} fontSize={7.5}
        fill={C.chute} fontWeight="700">DISCHARGE</text>
      <text x={cx + rHead + 54} y={topY - 6} fontSize={7}
        fill={C.label}>CHUTE</text>

      {/* ── Drive train: coupling + gearbox + motor ───────────────────── */}
      <g onMouseEnter={() => setHovered("motor")}
         onMouseLeave={() => setHovered(null)}
         style={{ cursor: "help" }}>
        {/* Drive shaft from pulley */}
        <line x1={cx + rHead + 20} y1={topY} x2={cx + casW + 10} y2={topY}
          stroke={C.dim} strokeWidth={1.5} strokeDasharray="4 2" />
        {/* Coupling disc */}
        <ellipse cx={cx + casW + 18} cy={topY} rx={6} ry={9}
          fill={C.coupling} stroke={C.hub} strokeWidth={1} />
        {/* Gearbox */}
        <rect x={cx + casW + 24} y={topY - 13} width={24} height={26}
          fill={C.gearbox} fillOpacity={0.7}
          stroke="#047857" strokeWidth={1} rx={2} />
        <text x={cx + casW + 36} y={topY + 3} fontSize={7}
          fill="white" textAnchor="middle" fontWeight="700">GB</text>
        {/* Motor */}
        <rect x={cx + casW + 48} y={topY - 11} width={30} height={22}
          fill={C.motor} fillOpacity={0.75}
          stroke="#065f46" strokeWidth={1} rx={2} />
        <text x={cx + casW + 63} y={topY + 3} fontSize={8}
          fill="white" textAnchor="middle" fontWeight="700">M</text>
        {/* Motor rating */}
        <text x={cx + casW + 63} y={topY + 18} fontSize={7}
          fill={C.text3} textAnchor="middle">
          {r.motor_kw ?? "—"}kW
        </text>
      </g>

      {/* ── Feed inlet arrow ──────────────────────────────────────────── */}
      <line x1={cx - casW - 32} y1={botY}
        x2={cx - casW - 4} y2={botY}
        stroke={C.feed} strokeWidth={2} markerEnd="url(#arr)" />
      <text x={cx - casW - 36} y={botY - 5} fontSize={7.5}
        fill={C.feed} textAnchor="end" fontWeight="700">FEED</text>

      {/* ── Dimension: H (lift height, left of casing) ───────────────── */}
      {(() => {
        const dx = cx - casW - 26;
        return (
          <g>
            {/* witness lines */}
            <line x1={cx - casW} y1={botY} x2={dx - 4} y2={botY}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx - casW} y1={topY} x2={dx - 4} y2={topY}
              stroke={C.dim} strokeWidth={0.6} />
            {/* dimension line */}
            <line x1={dx} y1={botY} x2={dx} y2={topY}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={dx - 4} y={(topY + botY) / 2}
              fontSize={9} fill={C.labelBr} fontWeight="600"
              textAnchor="middle"
              transform={`rotate(-90, ${dx - 4}, ${(topY + botY) / 2})`}>
              H = {f(inp.H_m, 0)} m
            </text>
          </g>
        );
      })()}

      {/* ── Dimension: bucket spacing (right of casing) ──────────────── */}
      {spacingPx != null && spacingPx > 14 && (() => {
        const spX  = cx + casW + 68;
        const spY1 = botY - 30;
        const spY2 = spY1 - spacingPx;
        return (
          <g>
            <line x1={cx + casW} y1={spY1} x2={spX + 4} y2={spY1}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx + casW} y1={spY2} x2={spX + 4} y2={spY2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={spX} y1={spY1} x2={spX} y2={spY2}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={spX + 6} y={(spY1 + spY2) / 2 + 3} fontSize={7.5}
              fill={C.text3} textAnchor="start">{spacingMm}mm</text>
            <text x={spX + 6} y={(spY1 + spY2) / 2 - 5} fontSize={6.5}
              fill={C.label} textAnchor="start">SPACING</text>
          </g>
        );
      })()}

      {/* ── Dimension: belt width ─────────────────────────────────────── */}
      {(() => {
        const dy = topY - rHead - 18;
        return (
          <g>
            <line x1={bltX_L} y1={topY - rHead - 4} x2={bltX_L} y2={dy + 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={bltX_R} y1={topY - rHead - 4} x2={bltX_R} y2={dy + 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={bltX_L} y1={dy} x2={bltX_R} y2={dy}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={cx} y={dy - 4} fontSize={7.5} fill={C.label}
              textAnchor="middle">
              BW = {r.belt_w ?? "—"} mm
            </text>
          </g>
        );
      })()}

      {/* ── Head / Boot labels ───────────────────────────────────────── */}
      <text x={cx} y={12} fontSize={9} fill={C.labelBr}
        textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        HEAD SECTION
      </text>
      <text x={cx} y={23} fontSize={7.5} fill={C.label} textAnchor="middle">
        Ø{headD_mm}mm · {inp.n_rpm ?? "—"}rpm · Lagged
      </text>
      <text x={cx} y={botY + rBoot + 30} fontSize={9} fill={C.labelBr}
        textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        BOOT / TAKE-UP
      </text>
      <text x={cx} y={botY + rBoot + 40} fontSize={7.5} fill={C.label}
        textAnchor="middle">
        Ø{bootD_mm}mm · Gravity T/U
      </text>

      {/* ── Head pulley diameter label ───────────────────────────────── */}
      <text x={cx + casW + 26} y={topY - 18} fontSize={7.5} fill={C.text3}>
        DH = {headD_mm} mm
      </text>
      <text x={cx + rBoot + 6} y={botY + 4} fontSize={7.5} fill={C.text3}>
        DB = {bootD_mm} mm
      </text>

      {/* ── Bucket strip label ───────────────────────────────────────── */}
      <text x={W / 2} y={H - 62} fontSize={7.5} fill={C.label} textAnchor="middle">
        BUCKET {bkt.id ?? "—"} · {bkt.W ?? "—"}×{bkt.H ?? "—"}mm · {bkt.V ?? "—"}L
        · SPACING {spacingMm ?? "—"}mm
      </text>

      {/* ── Hover callout ────────────────────────────────────────────── */}
      {co && (
        <Callout
          x={cx + casW + 10} y={H / 2}
          title={co.title} lines={co.lines} W={W} />
      )}

      <TitleBlock W={W} H={H} view="elevation" inputs={inputs} results={results} />
    </svg>
  );
}

// ─── HEAD SECTION PLAN VIEW (Task 12 upgrade) ────────────────────────────────
function PlanView({ inputs, results, W, H, hovered, setHovered }) {
  const r   = results || {};
  const inp = inputs  || {};

  const BW     = Number(r.belt_w ?? inp.D_mm ?? 300);
  const D      = Number(inp.D_mm ?? 500);
  const dShaft = Number(r.d_mm ?? 60);
  const CW     = BW + 120;   // casing outer width
  const CD     = D * 0.5;    // casing depth (side-to-side)

  // Scale to fit SVG
  const scale  = Math.min((W - 120) / CW, (H - 100) / (D + 80));
  const cw     = CW * scale;
  const cd     = CD * scale;
  const dPul   = D   * scale;
  const dSh    = dShaft * scale;
  const bw     = BW * scale;
  const cx     = W / 2;
  const cy     = H / 2;

  // Pulley as ellipse in plan (cylinder viewed from above)
  const pulleyRx = dPul / 2;
  const pulleyRy = Math.max(8, dPul * 0.12);

  // Lagging thickness in plan
  const laggingT = 6 * scale;

  // Bucket dimensions in plan
  const bktW  = Number(r.bucket?.W ?? 250) * scale;
  const bktH  = Number(r.bucket?.P ?? 150) * scale * 0.35;
  const nBkts = 5;
  const bktSpacingPx = Number(r.spacing ?? 0.20) * 1000 * scale;

  // Bearing housing
  const bhW = 26 * scale, bhH = 24 * scale;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <Defs />
      <rect width={W} height={H} fill={C.bg} />
      <DrawingGrid W={W} H={H} />

      {/* Title */}
      <text x={W/2} y={18} fontSize={10} fill={C.text3}
        textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        HEAD SECTION — PLAN VIEW
      </text>
      <text x={W/2} y={30} fontSize={7.5} fill={C.label} textAnchor="middle">
        Cross-section at head pulley centre-line
      </text>

      {/* ── Casing outer ─────────────────────────────────────────────── */}
      <g onMouseEnter={() => setHovered("casing")}
         onMouseLeave={() => setHovered(null)}
         style={{ cursor: "help" }}>
        <rect x={cx - cw/2} y={cy - cd/2 - 10}
          width={cw} height={cd + 20}
          fill={C.casFill} stroke={C.casing} strokeWidth={2} rx={2} />
        {/* Casing plate thickness hatching */}
        <rect x={cx - cw/2} y={cy - cd/2 - 10}
          width={8 * scale} height={cd + 20}
          fill="none" stroke={C.casing} strokeWidth={0.5}
          strokeDasharray="3 2" />
        <rect x={cx + cw/2 - 8 * scale} y={cy - cd/2 - 10}
          width={8 * scale} height={cd + 20}
          fill="none" stroke={C.casing} strokeWidth={0.5}
          strokeDasharray="3 2" />
      </g>

      {/* ── Belt edges ───────────────────────────────────────────────── */}
      <line x1={cx - bw/2} y1={cy - cd/2 - 12}
        x2={cx - bw/2} y2={cy + cd/2 + 12}
        stroke={C.belt} strokeWidth={2} />
      <line x1={cx + bw/2} y1={cy - cd/2 - 12}
        x2={cx + bw/2} y2={cy + cd/2 + 12}
        stroke={C.belt} strokeWidth={2} />

      {/* ── Pulley (ellipse = cylinder from above) ───────────────────── */}
      <g onMouseEnter={() => setHovered("head")}
         onMouseLeave={() => setHovered(null)}
         style={{ cursor: "help" }}>
        {/* Lagging (outer ellipse) */}
        <ellipse cx={cx} cy={cy} rx={pulleyRx + laggingT} ry={pulleyRy + laggingT * 0.3}
          fill="none" stroke={C.lagging} strokeWidth={3} opacity={0.7} />
        {/* Pulley shell */}
        <ellipse cx={cx} cy={cy} rx={pulleyRx} ry={pulleyRy}
          fill={C.pulley} fillOpacity={0.8}
          stroke={C.hub} strokeWidth={2} />
        {/* Face lines (weld seam hints) */}
        <line x1={cx - pulleyRx * 0.7} y1={cy} x2={cx + pulleyRx * 0.7} y2={cy}
          stroke={C.hub} strokeWidth={0.8} opacity={0.6} />
        {/* Shaft (circle in plan) */}
        <circle cx={cx} cy={cy} r={dSh / 2}
          fill={C.hub} stroke={C.dim} strokeWidth={1.5} />
        {/* Shaft centre mark */}
        <line x1={cx - 6} y1={cy} x2={cx + 6} y2={cy}
          stroke={C.dimTxt} strokeWidth={0.8} />
        <line x1={cx} y1={cy - 6} x2={cx} y2={cy + 6}
          stroke={C.dimTxt} strokeWidth={0.8} />
      </g>

      {/* ── Shaft stubs extending past casing ────────────────────────── */}
      <rect x={cx - cw/2 - bhW - 10} y={cy - dSh/2}
        width={10} height={dSh}
        fill={C.dim} />
      <rect x={cx + cw/2 + bhW} y={cy - dSh/2}
        width={10} height={dSh}
        fill={C.dim} />

      {/* ── Bearing housings (left + right) ──────────────────────────── */}
      {[-1, 1].map(side => {
        const bx = side < 0
          ? cx - cw/2 - bhW - 10
          : cx + cw/2 + 10;
        return (
          <g key={side}
            onMouseEnter={() => setHovered("bearings")}
            onMouseLeave={() => setHovered(null)}
            style={{ cursor: "help" }}>
            <rect x={bx} y={cy - bhH/2} width={bhW} height={bhH}
              fill={C.gearbox} fillOpacity={0.5}
              stroke={C.motor} strokeWidth={1.2} rx={2} />
            {/* Pillow block bolt holes */}
            {[-1, 1].map(d => (
              <circle key={d}
                cx={bx + bhW/2} cy={cy + d * bhH * 0.35} r={2}
                fill={C.hub} stroke={C.dim} strokeWidth={0.8} />
            ))}
            <text x={bx + bhW/2} y={side < 0 ? cy - bhH/2 - 4 : cy + bhH/2 + 10}
              fontSize={6.5} fill={C.labelBr} textAnchor="middle"
              fontWeight="700">BRG</text>
          </g>
        );
      })}

      {/* ── Buckets in plan (row across belt width) ──────────────────── */}
      {Array.from({ length: nBkts }, (_, i) => {
        const offset = (i - (nBkts - 1) / 2) * bktSpacingPx;
        return (
          <rect key={i}
            x={cx - bktW / 2}
            y={cy - bktH / 2 + offset}
            width={bktW} height={bktH}
            fill={C.bucket} fillOpacity={0.65}
            stroke={C.casing} strokeWidth={0.8} rx={1} />
        );
      })}

      {/* ── Dimension: belt width ─────────────────────────────────────── */}
      {(() => {
        const dy = cy + cd/2 + 30;
        return (
          <g>
            <line x1={cx - bw/2} y1={cy + cd/2 + 14} x2={cx - bw/2} y2={dy + 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx + bw/2} y1={cy + cd/2 + 14} x2={cx + bw/2} y2={dy + 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx - bw/2} y1={dy} x2={cx + bw/2} y2={dy}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={cx} y={dy + 11} fontSize={9} fill={C.labelBr}
              textAnchor="middle">BW = {BW.toFixed(0)} mm</text>
          </g>
        );
      })()}

      {/* ── Dimension: casing width ───────────────────────────────────── */}
      {(() => {
        const dy = cy - cd/2 - 28;
        return (
          <g>
            <line x1={cx - cw/2} y1={cy - cd/2 - 12} x2={cx - cw/2} y2={dy - 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx + cw/2} y1={cy - cd/2 - 12} x2={cx + cw/2} y2={dy - 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx - cw/2} y1={dy} x2={cx + cw/2} y2={dy}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={cx} y={dy - 5} fontSize={9} fill={C.label}
              textAnchor="middle">Casing = {CW.toFixed(0)} mm</text>
          </g>
        );
      })()}

      {/* ── Dimension: pulley diameter ───────────────────────────────── */}
      {(() => {
        const dx = cx + cw/2 + bhW + 26;
        return (
          <g>
            <line x1={cx + cw/2 + bhW + 20} y1={cy - pulleyRy}
              x2={cx + cw/2 + bhW + 20} y2={cy + pulleyRy}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={dx + 2} y={cy + 3} fontSize={8} fill={C.label}>
              D = {D.toFixed(0)} mm
            </text>
          </g>
        );
      })()}

      {/* ── Dimension: shaft diameter ─────────────────────────────────── */}
      {dSh > 8 && (() => {
        const dx = cx - cw/2 - bhW - 26;
        return (
          <g>
            <line x1={dx} y1={cy - dSh/2} x2={dx} y2={cy + dSh/2}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={dx - 4} y={cy - dSh/2 - 4} fontSize={7.5} fill={C.label}
              textAnchor="middle">
              d = {f(dShaft, 0)} mm
            </text>
          </g>
        );
      })()}

      {/* ── Callout ──────────────────────────────────────────────────── */}
      {hovered === "head" && (
        <Callout x={cx + pulleyRx + 20} y={cy - 30}
          title="HEAD PULLEY"
          lines={[
            `D = ${D.toFixed(0)} mm`,
            `Lagged — ${r.lagging?.lagging_type?.replace(/_/g, " ") ?? "rubber"}`,
            `Shaft d = ${f(dShaft, 0)} mm`,
            `n = ${inp.n_rpm ?? "—"} rpm`,
          ]}
          W={W} />
      )}
      {hovered === "bearings" && (
        <Callout x={cx} y={cy + bhH/2 + 30}
          title="PILLOW BLOCK BEARINGS"
          lines={[
            `L10 = ${r.L10 > 9999 ? (r.L10/1000).toFixed(0)+"k" : f(r.L10, 0)} h`,
            `Load: ${f(r.R_headshaft != null ? r.R_headshaft/1000 : null, 2)} kN`,
            "ISO 281 · C = 355 kN",
            "2× per shaft",
          ]}
          W={W} />
      )}
      {hovered === "casing" && (
        <Callout x={cx} y={cy}
          title="CASING"
          lines={[
            `Width: ${CW.toFixed(0)} mm`,
            `BW + 2×60mm`,
            "Mild steel plate",
            `H = ${inp.H_m ?? "—"} m total`,
          ]}
          W={W} />
      )}

      <TitleBlock W={W} H={H} view="plan" inputs={inputs} results={results} />
    </svg>
  );
}

// ─── SIDE SECTION VIEW ────────────────────────────────────────────────────────
function SideView({ inputs, results, W, H }) {
  const r   = results || {};
  const inp = inputs  || {};
  const BW  = Number(r.belt_w ?? inp.D_mm ?? 300);
  const D   = Number(inp.D_mm ?? 500);
  const scale = Math.min((W - 100) / (BW * 1.6 + D * 0.5), (H - 100) / (D * 1.3));
  const cx    = W / 2;
  const cy    = H / 2;
  const rS    = (D / 2) * scale;
  const bwS   = BW * scale;
  const casD  = (BW * 0.38 + 24) * scale;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <Defs />
      <rect width={W} height={H} fill={C.bg} />
      <DrawingGrid W={W} H={H} />

      {/* Casing cross section */}
      <rect x={cx - bwS / 2 - 14} y={cy - casD / 2}
        width={bwS + 28} height={casD}
        fill={C.casFill} stroke={C.casing} strokeWidth={2} rx={2} />

      {/* Lagging ring (side view — just thicker outer stroke) */}
      <ellipse cx={cx} cy={cy} rx={rS + 5} ry={rS * 0.22 + 2}
        fill="none" stroke={C.lagging} strokeWidth={4} opacity={0.5} />

      {/* Pulley cross section */}
      <ellipse cx={cx} cy={cy} rx={rS} ry={rS * 0.22}
        fill={C.pulley} fillOpacity={0.75}
        stroke={C.hub} strokeWidth={2} />

      {/* Shaft */}
      <line x1={cx - rS - 22} y1={cy} x2={cx + rS + 22} y2={cy}
        stroke={C.dim} strokeWidth={3} strokeLinecap="round" />

      {/* Belt sides (vertical lines at belt edges) */}
      <line x1={cx - bwS/2} y1={cy - casD/2 - 8} x2={cx - bwS/2} y2={cy + casD/2 + 8}
        stroke={C.belt} strokeWidth={2} />
      <line x1={cx + bwS/2} y1={cy - casD/2 - 8} x2={cx + bwS/2} y2={cy + casD/2 + 8}
        stroke={C.belt} strokeWidth={2} />

      {/* Dimension: belt width */}
      {(() => {
        const dy = cy + casD/2 + 22;
        return (
          <g>
            <line x1={cx - bwS/2} y1={cy + casD/2 + 10} x2={cx - bwS/2} y2={dy + 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx + bwS/2} y1={cy + casD/2 + 10} x2={cx + bwS/2} y2={dy + 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx - bwS/2} y1={dy} x2={cx + bwS/2} y2={dy}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={cx} y={dy + 12} fontSize={9} fill={C.labelBr} textAnchor="middle">
              BW = {BW.toFixed(0)} mm
            </text>
          </g>
        );
      })()}

      {/* Dimension: pulley D */}
      {(() => {
        const dy = cy - casD/2 - 22;
        return (
          <g>
            <line x1={cx - rS} y1={cy - casD/2 - 10} x2={cx - rS} y2={dy - 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx + rS} y1={cy - casD/2 - 10} x2={cx + rS} y2={dy - 2}
              stroke={C.dim} strokeWidth={0.6} />
            <line x1={cx - rS} y1={dy} x2={cx + rS} y2={dy}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            <text x={cx} y={dy - 5} fontSize={9} fill={C.label} textAnchor="middle">
              D = {D.toFixed(0)} mm
            </text>
          </g>
        );
      })()}

      {/* Labels */}
      <text x={cx} y={24} fontSize={10} fill={C.text3}
        textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        SIDE SECTION — HEAD PULLEY
      </text>
      <text x={cx} y={36} fontSize={7.5} fill={C.label} textAnchor="middle">
        Looking from drive side  ·  Lagging shown in amber
      </text>
      <text x={cx + rS + 28} y={cy + 3} fontSize={8} fill={C.labelBr}>SHAFT Ø{f(r.d_mm, 0)}mm</text>

      <TitleBlock W={W} H={H} view="side" inputs={inputs} results={results} />
    </svg>
  );
}

// ─── TRAJECTORY DETAIL VIEW ───────────────────────────────────────────────────
function TrajectoryView({ inputs, results, W, H }) {
  const r    = results || {};
  const traj  = r.trajectory || [];
  const upper = r.trajectory_upper || [];
  const lower = r.trajectory_lower || [];
  const m     = r.trajectory_metrics || {};

  if (!traj.length) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
        <Defs />
        <rect width={W} height={H} fill={C.bg} />
        <DrawingGrid W={W} H={H} />
        <text x={W/2} y={H/2} fontSize={12} fill={C.text3} textAnchor="middle">
          No trajectory data — run calculation first
        </text>
      </svg>
    );
  }

  const pad  = { top: 56, bot: 44, left: 54, right: 24 };
  const pw   = W - pad.left - pad.right;
  const ph   = H - pad.top  - pad.bot;

  const allX = [...traj.map(p => p.x), ...upper.map(p => p.x), ...lower.map(p => p.x)];
  const allY = [...traj.map(p => p.y), ...upper.map(p => p.y), ...lower.map(p => p.y)];
  const xMin = Math.min(...allX), xMax = Math.max(...allX);
  const yMin = Math.min(...allY), yMax = Math.max(...allY);
  const xRange = Math.max(xMax - xMin, 0.01);
  const yRange = Math.max(yMax - yMin, 0.01);

  const tx = x => pad.left + (x - xMin) / xRange * pw;
  const ty = y => pad.top  + (yMax - y) / yRange * ph;

  const toPath = pts => pts.map((p, i) =>
    `${i===0?"M":"L"} ${tx(p.x).toFixed(1)} ${ty(p.y).toFixed(1)}`
  ).join(" ");

  // Grid ticks
  const nTick = 5;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <Defs />
      <rect width={W} height={H} fill={C.bg} />
      <DrawingGrid W={W} H={H} />

      {/* Plot area border */}
      <rect x={pad.left} y={pad.top} width={pw} height={ph}
        fill="none" stroke={C.dim} strokeWidth={0.8} />

      {/* Grid lines */}
      {Array.from({ length: nTick + 1 }, (_, i) => i / nTick).map(t => {
        const gx = pad.left + t * pw;
        const gy = pad.top  + t * ph;
        const xv = (xMin + t * xRange) * 1000;
        const yv = (yMax - t * yRange) * 1000;
        return (
          <g key={t}>
            <line x1={gx} y1={pad.top} x2={gx} y2={pad.top + ph}
              stroke={C.casing} strokeWidth={0.6} />
            <line x1={pad.left} y1={gy} x2={pad.left + pw} y2={gy}
              stroke={C.casing} strokeWidth={0.6} />
            <text x={gx} y={pad.top + ph + 12} fontSize={7.5} fill={C.label}
              textAnchor="middle">{xv.toFixed(0)}</text>
            <text x={pad.left - 4} y={gy + 3} fontSize={7.5} fill={C.label}
              textAnchor="end">{yv.toFixed(0)}</text>
          </g>
        );
      })}

      {/* Envelope */}
      {upper.length > 0 && (
        <>
          <path d={toPath(upper)} fill="none"
            stroke={C.danger} strokeWidth={1} strokeDasharray="4 3" opacity={0.45} />
          <path d={toPath(lower)} fill="none"
            stroke={C.danger} strokeWidth={1} strokeDasharray="4 3" opacity={0.45} />
          {/* Shaded envelope fill */}
          <path
            d={toPath(upper) + " " + toPath([...lower].reverse()).replace("M", "L")}
            fill={C.danger} fillOpacity={0.06} />
        </>
      )}

      {/* Centre trajectory */}
      <path d={toPath(traj)} fill="none"
        stroke={C.danger} strokeWidth={2.5} />

      {/* Release point dot */}
      {traj[0] && (
        <circle cx={tx(traj[0].x)} cy={ty(traj[0].y)} r={4}
          fill={C.danger} />
      )}

      {/* Axis labels */}
      <text x={W/2} y={H - 6} fontSize={9} fill={C.labelBr} textAnchor="middle">
        x [mm] — horizontal distance from pulley centre
      </text>
      <text x={10} y={H/2} fontSize={9} fill={C.labelBr} textAnchor="middle"
        transform={`rotate(-90,10,${H/2})`}>y [mm]</text>

      {/* Title */}
      <text x={W/2} y={22} fontSize={10} fill={C.text3}
        textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        DISCHARGE TRAJECTORY
      </text>
      <text x={W/2} y={35} fontSize={8} fill={C.label} textAnchor="middle">
        Throw {f(m.throw_distance_m, 3)} m  ·  Impact {f(m.impact_velocity_mps, 2)} m/s
        ·  CR = {f(results?.cr, 3)}
        ·  θ = {f(results?.theta_rel, 1)}° from vertical
      </text>

      {/* Legend */}
      <g>
        <circle cx={W - 85} cy={H - 32} r={4} fill={C.danger} />
        <text x={W - 78} y={H - 29} fontSize={7.5} fill={C.label}>Centre traj.</text>
        <line x1={W - 88} y1={H - 20} x2={W - 72} y2={H - 20}
          stroke={C.danger} strokeWidth={1} strokeDasharray="3 2" opacity={0.5} />
        <text x={W - 68} y={H - 17} fontSize={7.5} fill={C.label}>Envelope</text>
      </g>

      <TitleBlock W={W} H={H} view="trajectory" inputs={inputs} results={results} />
    </svg>
  );
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function ElevatorSchematic({ inputs, results }) {
  const r = results || {};
  const [view, setView]       = useState("elevation");
  const [zoom, setZoom]       = useState(1);
  const [pan, setPan]         = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [hovered, setHovered]   = useState(null);
  const dragRef      = useRef({ startX: 0, startY: 0, panX: 0, panY: 0 });
  const containerRef = useRef(null);

  useEffect(() => { setZoom(1); setPan({ x: 0, y: 0 }); setHovered(null); }, [view]);

  // Non-passive wheel zoom
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e) => {
      e.preventDefault();
      const f = e.deltaY < 0 ? 1.12 : 0.89;
      setZoom(z => Math.min(4, Math.max(0.25, z * f)));
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, []);

  const onMouseDown = useCallback((e) => {
    setDragging(true);
    dragRef.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
  }, [pan]);
  const onMouseMove = useCallback((e) => {
    if (!dragging) return;
    setPan({
      x: dragRef.current.panX + (e.clientX - dragRef.current.startX),
      y: dragRef.current.panY + (e.clientY - dragRef.current.startY),
    });
  }, [dragging]);
  const onMouseUp   = useCallback(() => setDragging(false), []);
  const resetView   = useCallback(() => { setZoom(1); setPan({ x: 0, y: 0 }); }, []);

  const SVG_W = 560, SVG_H = 440;

  const ViewComponent =
    view === "plan"       ? PlanView       :
    view === "side"       ? SideView       :
    view === "trajectory" ? TrajectoryView :
    ElevationView;

  return (
    <div style={{
      width: "100%", height: "100%",
      display: "flex", flexDirection: "column",
      background: C.bg, overflow: "hidden",
      userSelect: "none",
      position: "relative",   // ← fixes KPI pills absolute positioning
    }}>

      {/* ── View tabs + controls ─────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center",
        padding: "0 10px", height: 34, flexShrink: 0,
        borderBottom: `1px solid ${C.border}`,
        background: C.panel, gap: 2,
      }}>
        {VIEWS.map(v => (
          <button key={v.id} onClick={() => setView(v.id)} style={{
            padding: "3px 10px", fontSize: 10, borderRadius: 4,
            border: "none", cursor: "pointer",
            background: view === v.id ? "rgba(59,130,246,.12)" : "transparent",
            color: view === v.id ? C.primary : C.text3,
            fontWeight: view === v.id ? 700 : 400,
            borderBottom: view === v.id ? `2px solid ${C.primary}` : "2px solid transparent",
            transition: "all .15s", fontFamily: "inherit",
          }}>
            {v.label}
          </button>
        ))}

        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 9, color: C.text3, marginRight: 6 }}>
          {Math.round(zoom * 100)}%
        </span>
        <button onClick={resetView} title="Reset view" style={{
          padding: "2px 8px", fontSize: 9, borderRadius: 3,
          border: `1px solid ${C.border}`, cursor: "pointer",
          background: "transparent", color: C.text3,
        }}>⊡ Reset</button>
        {["+", "−"].map((lbl, i) => (
          <button key={lbl}
            onClick={() => setZoom(z => Math.min(4, Math.max(0.25, z * (i===0 ? 1.2 : 0.8))))}
            style={{
              width: 22, height: 22, padding: 0, fontSize: 14,
              borderRadius: 3, border: `1px solid ${C.border}`,
              cursor: "pointer", background: "transparent", color: C.text3,
              marginLeft: 3, lineHeight: 1,
            }}>{lbl}</button>
        ))}
      </div>

      {/* ── KPI floating pills — fixed field names (r.v, r.Q) ────────────── */}
      <div style={{
        position: "absolute", top: 42, right: 8, zIndex: 10,
        display: "flex", flexDirection: "column", gap: 5,
        pointerEvents: "none",
      }}>
        {[
          { label: "BELT SPEED",
            value: f(r.v, 2), unit: "m/s",
            color: r.v != null ? C.primary : C.text3 },
          { label: "CAPACITY",
            value: r.Q != null ? Number(r.Q).toFixed(0) : "—",
            unit: "t/h",
            color: r.Q != null
              ? (r.Q >= (inputs?.Q_req ?? 0) ? C.success : C.danger)
              : C.text3 },
          { label: "MOTOR",
            value: r.motor_kw ?? "—", unit: "kW",
            color: C.motor },
          { label: "DISCHARGE θ",
            value: f(r.theta_rel, 1), unit: "° from vert",
            color: C.feed },
          { label: "CR",
            value: f(r.cr, 3),
            unit: r.cr >= 1.0 && r.cr <= 1.8 ? "optimal" : "check",
            color: r.cr >= 1.0 && r.cr <= 1.8 ? C.success : C.warning },
        ].map(k => (
          <div key={k.label} style={{
            background: "rgba(15,23,42,.90)", backdropFilter: "blur(4px)",
            border: `1px solid ${C.border}`, borderRadius: 5,
            padding: "4px 10px", textAlign: "right",
          }}>
            <div style={{ fontSize: 7.5, color: C.text3, letterSpacing: ".06em" }}>
              {k.label}
            </div>
            <div style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 16,
              fontWeight: 700, color: k.color, lineHeight: 1.2 }}>
              {k.value}
            </div>
            <div style={{ fontSize: 7.5, color: C.text3,
              fontFamily: "JetBrains Mono,monospace" }}>
              {k.unit}
            </div>
          </div>
        ))}
      </div>

      {/* ── Pan / zoom canvas ────────────────────────────────────────────── */}
      <div ref={containerRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onDoubleClick={resetView}
        style={{
          flex: 1, overflow: "hidden", position: "relative",
          cursor: dragging ? "grabbing" : "grab",
        }}
      >
        <div style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: "50% 50%",
          transition: dragging ? "none" : "transform .05s",
          willChange: "transform",
          display: "flex", alignItems: "center", justifyContent: "center",
          width: "100%", height: "100%",
        }}>
          <ViewComponent
            inputs={inputs} results={results}
            W={SVG_W} H={SVG_H}
            hovered={hovered} setHovered={setHovered}
          />
        </div>
      </div>

      {/* ── Status tip ──────────────────────────────────────────────────── */}
      <div style={{
        padding: "3px 10px", fontSize: 8, color: C.text3,
        borderTop: `1px solid ${C.border}`, flexShrink: 0,
        letterSpacing: ".03em",
        display: "flex", justifyContent: "space-between",
      }}>
        <span>Scroll to zoom  ·  Drag to pan  ·  Double-click to reset</span>
        <span style={{ color: hovered ? C.primary : C.text3 }}>
          {hovered ? `Hover: ${hovered.toUpperCase()} — click for detail` : "Hover components for callouts"}
        </span>
      </div>
    </div>
  );
}
