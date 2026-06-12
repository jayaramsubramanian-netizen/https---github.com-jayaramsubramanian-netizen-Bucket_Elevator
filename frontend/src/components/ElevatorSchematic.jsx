// ElevatorSchematic.jsx — Interactive equipment model
//
// Views: Elevation | Plan | Side Section | Trajectory Detail
//
// Controls:
//   Scroll wheel  → zoom in / out (min 0.25×, max 4×)
//   Click + drag  → pan
//   Reset button  → return to fitted view
//   View tabs     → switch between 4 views
//
// Improvements over previous version:
//   • No label overlap — info boxes are positioned in reserved corners,
//     never drawn over the pulley or casing geometry
//   • Trajectory arc drawn cleanly from results.trajectory data
//   • Belt speed / capacity KPIs in a floating pill, not overlapping SVG
//   • Pan/zoom state is reset when view changes
//   • 3 additional views: Plan (from above), Side Section, Trajectory Detail

import { useState, useRef, useCallback, useEffect } from "react";

const C = {
  bg:       "#07111e",
  casing:   "#1c3050",
  casFill:  "#0d1c2e",
  belt:     "#2dd4bf",
  bucket:   "#4a9eff",
  pulley:   "#4a9eff",
  hub:      "#07111e",
  motor:    "#1fb86e",
  dim:      "#2a4060",
  label:    "#5a7a9a",
  labelBr:  "#7a9ab8",
  traj:     "#c8192e",
  feed:     "#d98e00",
  text:     "#ddeaf6",
  text3:    "#5a7a9a",
  border:   "#1c3050",
  panel:    "#0d1c2e",
  success:  "#1fb86e",
  warning:  "#d98e00",
  danger:   "#e05252",
};

const VIEWS = [
  { id: "elevation", label: "Elevation" },
  { id: "plan",      label: "Plan" },
  { id: "side",      label: "Side Section" },
  { id: "trajectory",label: "Trajectory" },
];

function f(v, dp = 1, fallback = "—") {
  if (v == null || Number.isNaN(Number(v))) return fallback;
  return Number(v).toFixed(dp);
}

// ─── ELEVATION VIEW (main schematic) ─────────────────────────────────────────
function ElevationView({ inputs, results, W, H }) {
  const inp = inputs || {};
  const r   = results || {};
  const bkt = r.bucket || {};

  // Layout constants — increased top margin so HEAD SECTION text never clips
  const margin = { top: 52, bottom: 52, left: 48, right: 80 };
  const cx     = W * 0.38;

  // ── Pulley radii — proportional to actual input diameters ─────────────────
  const headD_mm  = Number(inp.D_mm  || 500);
  const bootD_mm  = Number(inp.boot_pulley_same_as_head
                      ? headD_mm
                      : (inp.boot_pulley_D_mm || 300));
  const _pScale   = Math.min(30, W * 0.065) / headD_mm;
  const rHead     = Math.max(12, Math.min(30, headD_mm * _pScale));
  const rBoot     = Math.max(8,  Math.min(26, bootD_mm * _pScale));
  const casW      = rHead + 14;
  const topY      = margin.top + rHead;
  const botY      = H - margin.bottom - rBoot;
  const elevH     = botY - topY;
  const bltX_L    = cx - rHead * 0.6;
  const bltX_R    = cx + rHead * 0.6;

  // Bucket spacing in px for dimension annotation
  const spacingMm = r.spacing != null ? Math.round(r.spacing * 1000) : null;
  const spacingPx = spacingMm != null ? (spacingMm / 1000) * (elevH / Math.max(inp.H_m || 25, 1)) : null;

  // Trajectory
  const traj    = r.trajectory || [];
  const trajPts = traj.slice(0, 25);
  const trajStr = (() => {
    if (!trajPts.length) return "";
    const tx0 = trajPts[0].x || 0;
    const ty0 = trajPts[0].y || 0;
    const scale = 0.13;
    return trajPts.map((p, i) => {
      const sx = cx + (p.x - tx0) * scale;
      const sy = topY - (p.y - ty0) * scale;
      return `${i === 0 ? "M" : "L"} ${sx.toFixed(1)} ${sy.toFixed(1)}`;
    }).join(" ");
  })();

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      {/* Arrowhead marker */}
      <defs>
        <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill={C.feed} />
        </marker>
        <marker id="dimArr" markerWidth="5" markerHeight="5" refX="2.5" refY="2.5" orient="auto">
          <path d="M0,0 L5,2.5 L0,5 Z" fill={C.dim} />
        </marker>
        <marker id="dimArrR" markerWidth="5" markerHeight="5" refX="2.5" refY="2.5" orient="auto-start-reverse">
          <path d="M0,0 L5,2.5 L0,5 Z" fill={C.dim} />
        </marker>
      </defs>

      {/* Background */}
      <rect width={W} height={H} fill={C.bg} />

      {/* ── Casing ──────────────────────────────────────────────────────── */}
      <rect x={cx - casW} y={topY} width={casW * 2} height={elevH}
        fill={C.casFill} stroke={C.casing} strokeWidth={1.5} />

      {/* ── Belt lines ──────────────────────────────────────────────────── */}
      <line x1={bltX_L} y1={topY} x2={bltX_L} y2={botY} stroke={C.belt} strokeWidth={2.5} />
      <line x1={bltX_R} y1={topY} x2={bltX_R} y2={botY} stroke={C.belt} strokeWidth={2.5} />

      {/* ── Buckets (ascending left side) ──────────────────────────────── */}
      {[0, 1, 2, 3, 4, 5, 6].map(i => {
        const by = botY - 20 - i * (elevH - 40) / 6;
        return (
          <g key={i}>
            <rect x={bltX_L - 16} y={by - 8} width={16} height={10}
              fill={C.bucket} fillOpacity={0.75} stroke={C.casing} strokeWidth={0.8} rx={1} />
          </g>
        );
      })}

      {/* ── Boot pulley ──────────────────────────────────────────────────── */}
      <circle cx={cx} cy={botY} r={rBoot} fill={C.pulley} fillOpacity={0.9}
        stroke={C.hub} strokeWidth={1.5} />
      <circle cx={cx} cy={botY} r={rBoot * 0.3} fill={C.hub} />

      {/* ── Head pulley ──────────────────────────────────────────────────── */}
      <circle cx={cx} cy={topY} r={rHead} fill={C.pulley} fillOpacity={0.9}
        stroke={C.hub} strokeWidth={1.5} />
      <circle cx={cx} cy={topY} r={rHead * 0.28} fill={C.hub} />

      {/* ── Motor symbol only (power shown in KPI panel, not here) ──────── */}
      <rect x={cx + casW + 16} y={topY - 10} width={36} height={20}
        fill={C.motor} fillOpacity={0.7} rx={3} stroke={"#0a7040"} strokeWidth={1} />
      <text x={cx + casW + 34} y={topY + 4} fontSize={8} fill="white"
        textAnchor="middle" fontWeight="700">M</text>
      <line x1={cx + rHead} y1={topY} x2={cx + casW + 16} y2={topY}
        stroke={C.dim} strokeWidth={1.5} strokeDasharray="4 2" />

      {/* ── Discharge trajectory ─────────────────────────────────────────── */}
      {trajStr && (
        <path d={trajStr} fill="none"
          stroke={C.traj} strokeWidth={1.5} strokeDasharray="5 3" opacity={0.9} />
      )}

      {/* ── Dimension: lift height (left of casing) ──────────────────────── */}
      <line x1={cx - casW - 22} y1={botY} x2={cx - casW - 22} y2={topY}
        stroke={C.dim} strokeWidth={0.8} />
      {[botY, topY].map((y, i) => (
        <line key={i} x1={cx - casW - 27} y1={y} x2={cx - casW - 17} y2={y}
          stroke={C.dim} strokeWidth={0.8} />
      ))}
      <text x={cx - casW - 30} y={(topY + botY) / 2} fontSize={9} fill={C.labelBr}
        textAnchor="middle" fontWeight="600"
        transform={`rotate(-90, ${cx - casW - 30}, ${(topY + botY) / 2})`}>
        H = {f(inp.H_m, 0)} m
      </text>

      {/* ── Dimension: bucket spacing (right of casing) ──────────────────── */}
      {spacingPx != null && spacingPx > 12 && (() => {
        const spX   = cx + casW + 62;
        const spY1  = botY - 28;
        const spY2  = spY1 - spacingPx;
        return (
          <g>
            {/* vertical dimension line */}
            <line x1={spX} y1={spY1} x2={spX} y2={spY2}
              stroke={C.dim} strokeWidth={0.8}
              markerEnd="url(#dimArr)" markerStart="url(#dimArrR)" />
            {/* tick marks */}
            <line x1={spX - 4} y1={spY1} x2={spX + 4} y2={spY1}
              stroke={C.dim} strokeWidth={0.8} />
            <line x1={spX - 4} y1={spY2} x2={spX + 4} y2={spY2}
              stroke={C.dim} strokeWidth={0.8} />
            {/* label */}
            <text x={spX + 6} y={(spY1 + spY2) / 2 + 3} fontSize={7.5}
              fill={C.text3} textAnchor="start">
              {spacingMm}mm
            </text>
            <text x={spX + 6} y={(spY1 + spY2) / 2 - 5} fontSize={6.5}
              fill={C.label} textAnchor="start">SPACING</text>
          </g>
        );
      })()}

      {/* ── Dimension: belt width ─────────────────────────────────────────── */}
      <line x1={bltX_L} y1={topY - rHead - 14} x2={bltX_R} y2={topY - rHead - 14}
        stroke={C.dim} strokeWidth={0.7} />
      <text x={cx} y={topY - rHead - 18} fontSize={7.5} fill={C.label}
        textAnchor="middle">
        BW = {r.belt_w ?? r.belt_width_mm ?? inp.D_mm ?? "—"} mm
      </text>

      {/* ── HEAD SECTION label — anchored to top margin, never clips ──────── */}
      <text x={cx} y={14} fontSize={8.5} fill={C.labelBr}
        textAnchor="middle" fontWeight="700" letterSpacing="0.06em">
        HEAD SECTION
      </text>
      <text x={cx} y={24} fontSize={7} fill={C.label} textAnchor="middle">
        BW = {r.belt_w ?? "—"} mm
      </text>

      {/* ── BOOT label ───────────────────────────────────────────────────── */}
      <text x={cx} y={botY + rBoot + 16} fontSize={8.5} fill={C.labelBr}
        textAnchor="middle" fontWeight="700" letterSpacing="0.06em">
        BOOT
      </text>

      {/* ── Feed arrow ───────────────────────────────────────────────────── */}
      <line x1={cx - casW - 30} y1={botY} x2={cx - casW - 4} y2={botY}
        stroke={C.feed} strokeWidth={2} markerEnd="url(#arr)" />
      <text x={cx - casW - 34} y={botY - 6} fontSize={7} fill={C.feed}
        textAnchor="end" fontWeight="700">FEED</text>

      {/* ── D label — head (right of pulley, below motor) ──────────────── */}
      <text x={cx + casW + 16} y={topY + 18} fontSize={7.5} fill={C.text3}
        textAnchor="start">
        D<tspan fontSize={6}>H</tspan> = {headD_mm} mm
      </text>

      {/* ── D label — boot (right of boot pulley) ─────────────────────── */}
      <text x={cx + rBoot + 6} y={botY + 4} fontSize={7.5} fill={C.text3}
        textAnchor="start">
        D<tspan fontSize={6}>B</tspan> = {bootD_mm} mm
        {bootD_mm !== headD_mm && (
          <tspan fontSize={6.5} fill={bootD_mm < headD_mm ? C.warning : C.success}>
            {" "}({bootD_mm < headD_mm ? "< DH" : "> DH"})
          </tspan>
        )}
      </text>

      {/* ── Bucket strip at bottom ─────────────────────────────────────── */}
      <text x={W / 2} y={H - 8} fontSize={7.5} fill={C.label} textAnchor="middle">
        BUCKET {bkt.id ?? "—"} · {bkt.W ?? "—"}×{bkt.H ?? "—"}mm · {bkt.V ?? "—"}L
      </text>
    </svg>
  );
}

// ─── PLAN VIEW (top-down) ──────────────────────────────────────────────────────
function PlanView({ inputs, results, W, H }) {
  const r = results || {};
  const inp = inputs || {};
  const BW = Number(r.belt_w ?? r.belt_width_mm ?? inp.D_mm ?? 300);
  const CW = BW + 40;
  const scale = Math.min((W - 80) / (CW + 40), (H - 60) / 160);
  const cw  = CW * scale;
  const bw  = BW * scale;
  const cx  = W / 2;
  const cy  = H / 2;

  const nBuckets = 5;
  const bktW = (Number(r.bucket?.W ?? 250)) * scale;
  const bktH = (Number(r.bucket?.P ?? 150)) * scale * 0.4;
  const spacing = (Number(r.spacing ?? 0.25) * 1000) * scale;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <rect width={W} height={H} fill={C.bg} />

      {/* Casing outline */}
      <rect x={cx - cw/2} y={cy - 30 * scale} width={cw} height={60 * scale}
        fill={C.casFill} stroke={C.casing} strokeWidth={1.5} rx={2} />

      {/* Belt edges */}
      <line x1={cx - bw/2} y1={cy - 40 * scale} x2={cx - bw/2} y2={cy + 40 * scale}
        stroke={C.belt} strokeWidth={1.5} />
      <line x1={cx + bw/2} y1={cy - 40 * scale} x2={cx + bw/2} y2={cy + 40 * scale}
        stroke={C.belt} strokeWidth={1.5} />

      {/* Buckets (row of 5 centred) */}
      {[-2,-1,0,1,2].map(i => (
        <rect key={i}
          x={cx - bktW / 2}
          y={cy - bktH / 2 + i * spacing * 0.5}
          width={bktW} height={bktH}
          fill={C.bucket} fillOpacity={0.7}
          stroke={C.casing} strokeWidth={0.8} rx={1} />
      ))}

      {/* Dimension: belt width */}
      <line x1={cx - bw/2} y1={cy + 60 * scale} x2={cx + bw/2} y2={cy + 60 * scale}
        stroke={C.dim} strokeWidth={0.8} />
      <text x={cx} y={cy + 60 * scale + 13} fontSize={9} fill={C.labelBr}
        textAnchor="middle">BW = {BW.toFixed(0)} mm</text>

      {/* Dimension: casing width */}
      <line x1={cx - cw/2} y1={cy - 55 * scale} x2={cx + cw/2} y2={cy - 55 * scale}
        stroke={C.dim} strokeWidth={0.8} />
      <text x={cx} y={cy - 55 * scale - 5} fontSize={9} fill={C.label}
        textAnchor="middle">Casing = {CW.toFixed(0)} mm</text>

      {/* Labels */}
      <text x={cx} y={30} fontSize={10} fill={C.text3}
        textAnchor="middle" fontWeight="600" letterSpacing=".06em">
        PLAN VIEW — TOP DOWN
      </text>

      {/* North arrow */}
      <text x={W - 20} y={20} fontSize={8} fill={C.label} textAnchor="middle">↑</text>
      <text x={W - 20} y={30} fontSize={7} fill={C.label} textAnchor="middle">UP</text>
    </svg>
  );
}

// ─── SIDE SECTION VIEW ────────────────────────────────────────────────────────
function SideView({ inputs, results, W, H }) {
  const r   = results || {};
  const inp = inputs  || {};
  const BW  = Number(r.belt_w ?? r.belt_width_mm ?? inp.D_mm ?? 300);
  const D   = Number(inp.D_mm ?? 500);
  const rPulley = D / 2;
  const scale  = Math.min((W - 80) / (BW * 1.5 + rPulley), (H - 80) / (D * 1.2));
  const cx     = W / 2;
  const cy     = H / 2;
  const rS     = rPulley * scale;
  const bwS    = BW * scale;
  const casDepth = (BW * 0.4 + 20) * scale;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <rect width={W} height={H} fill={C.bg} />

      {/* Casing cross section */}
      <rect x={cx - bwS / 2 - 12} y={cy - casDepth / 2}
        width={bwS + 24} height={casDepth}
        fill={C.casFill} stroke={C.casing} strokeWidth={1.5} rx={2} />

      {/* Pulley cross section (ellipse — side view of cylinder) */}
      <ellipse cx={cx} cy={cy} rx={rS} ry={rS * 0.2}
        fill={C.pulley} fillOpacity={0.7} stroke={C.hub} strokeWidth={1.5} />

      {/* Shaft line */}
      <line x1={cx - rS - 20} y1={cy} x2={cx + rS + 20} y2={cy}
        stroke={C.dim} strokeWidth={2} />

      {/* Belt width dimension */}
      <line x1={cx - bwS/2} y1={cy + casDepth/2 + 15}
        x2={cx + bwS/2} y2={cy + casDepth/2 + 15}
        stroke={C.dim} strokeWidth={0.8} />
      <text x={cx} y={cy + casDepth/2 + 28} fontSize={9} fill={C.labelBr}
        textAnchor="middle">BW = {BW.toFixed(0)} mm</text>

      {/* Pulley dia dimension */}
      <line x1={cx - rS} y1={cy - casDepth/2 - 15}
        x2={cx + rS} y2={cy - casDepth/2 - 15}
        stroke={C.dim} strokeWidth={0.8} />
      <text x={cx} y={cy - casDepth/2 - 20} fontSize={9} fill={C.label}
        textAnchor="middle">D = {D.toFixed(0)} mm</text>

      {/* Labels */}
      <text x={cx} y={28} fontSize={10} fill={C.text3}
        textAnchor="middle" fontWeight="600" letterSpacing=".06em">
        SIDE SECTION — HEAD PULLEY
      </text>
      <text x={cx + rS + 25} y={cy + 4} fontSize={8} fill={C.label}>
        SHAFT
      </text>
    </svg>
  );
}

// ─── TRAJECTORY DETAIL VIEW ───────────────────────────────────────────────────
function TrajectoryView({ inputs, results, W, H }) {
  const r   = results || {};
  const inp = inputs  || {};
  const traj = r.trajectory || [];
  const upper = r.trajectory_upper || [];
  const lower = r.trajectory_lower || [];
  const m   = r.trajectory_metrics || {};

  if (!traj.length) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
        <rect width={W} height={H} fill={C.bg} />
        <text x={W/2} y={H/2} fontSize={12} fill={C.text3} textAnchor="middle">
          No trajectory data — run calculation first
        </text>
      </svg>
    );
  }

  // Scale to fit
  const pad = { top: 50, bot: 40, left: 50, right: 20 };
  const pw  = W - pad.left - pad.right;
  const ph  = H - pad.top - pad.bot;

  const xs = traj.map(p => p.x);
  const ys = traj.map(p => p.y);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...[...ys, ...(lower.map(p=>p.y))]);
  const yMax = Math.max(...[...ys, ...(upper.map(p=>p.y))]);
  const xRange = Math.max(xMax - xMin, 1);
  const yRange = Math.max(yMax - yMin, 1);

  const tx = x => pad.left + (x - xMin) / xRange * pw;
  const ty = y => pad.top + (yMax - y) / yRange * ph;

  const toPath = pts => pts.map((p, i) =>
    `${i===0?"M":"L"} ${tx(p.x).toFixed(1)} ${ty(p.y).toFixed(1)}`
  ).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ display: "block" }}>
      <rect width={W} height={H} fill={C.bg} />

      {/* Grid */}
      {[0, 0.25, 0.5, 0.75, 1].map(t => {
        const gx = pad.left + t * pw;
        const gy = pad.top  + t * ph;
        return (
          <g key={t}>
            <line x1={gx} y1={pad.top} x2={gx} y2={pad.top + ph}
              stroke={C.casing} strokeWidth={0.5} opacity={0.5} />
            <line x1={pad.left} y1={gy} x2={pad.left + pw} y2={gy}
              stroke={C.casing} strokeWidth={0.5} opacity={0.5} />
          </g>
        );
      })}

      {/* Envelope (upper / lower) */}
      {upper.length > 0 && lower.length > 0 && (
        <>
          <path d={toPath(upper)} fill="none"
            stroke={C.traj} strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
          <path d={toPath(lower)} fill="none"
            stroke={C.traj} strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
        </>
      )}

      {/* Centre trajectory */}
      <path d={toPath(traj)} fill="none"
        stroke={C.traj} strokeWidth={2.5} />

      {/* Axes */}
      <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + ph}
        stroke={C.label} strokeWidth={1} />
      <line x1={pad.left} y1={pad.top + ph} x2={pad.left + pw} y2={pad.top + ph}
        stroke={C.label} strokeWidth={1} />

      {/* Axis labels */}
      <text x={W/2} y={H - 8} fontSize={8.5} fill={C.label} textAnchor="middle">
        x [mm]
      </text>
      <text x={12} y={H/2} fontSize={8.5} fill={C.label} textAnchor="middle"
        transform={`rotate(-90,12,${H/2})`}>y [mm]</text>

      {/* Title + metrics */}
      <text x={W/2} y={22} fontSize={10} fill={C.text3}
        textAnchor="middle" fontWeight="600" letterSpacing=".06em">
        DISCHARGE TRAJECTORY — HEAD PULLEY
      </text>
      <text x={W/2} y={37} fontSize={8} fill={C.label} textAnchor="middle">
        Throw {f(m.throw_distance_m, 3)} m  ·  Impact {f(m.impact_velocity_mps, 2)} m/s  ·  Flight {f(m.flight_time_s, 3)} s
      </text>

      {/* Spread legend */}
      {upper.length > 0 && (
        <g>
          <line x1={W - 90} y1={H - 25} x2={W - 70} y2={H - 25}
            stroke={C.traj} strokeWidth={1} strokeDasharray="3 3" opacity={0.5} />
          <text x={W - 66} y={H - 22} fontSize={7.5} fill={C.label}>Envelope</text>
          <line x1={W - 90} y1={H - 14} x2={W - 70} y2={H - 14}
            stroke={C.traj} strokeWidth={2} />
          <text x={W - 66} y={H - 11} fontSize={7.5} fill={C.label}>Centre</text>
        </g>
      )}
    </svg>
  );
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function ElevatorSchematic({ inputs, results }) {
  const r = results || {};
  const [view, setView] = useState("elevation");
  const [zoom, setZoom]   = useState(1);
  const [pan, setPan]     = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef({ startX: 0, startY: 0, panX: 0, panY: 0 });
  const containerRef = useRef(null);

  // Reset pan/zoom when view changes
  useEffect(() => { setZoom(1); setPan({ x: 0, y: 0 }); }, [view]);

  // Non-passive wheel handler
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 0.89;
      setZoom(z => Math.min(4, Math.max(0.25, z * factor)));
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

  const onMouseUp = useCallback(() => setDragging(false), []);

  // SVG logical size (fixed; CSS scale via transform)
  const SVG_W = 520;
  const SVG_H = 420;

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
            background: view === v.id ? "rgba(74,158,255,.15)" : "transparent",
            color: view === v.id ? C.pulley : C.text3,
            fontWeight: view === v.id ? 700 : 400,
            borderBottom: view === v.id ? `2px solid ${C.pulley}` : "2px solid transparent",
            transition: "all .15s",
            fontFamily: "inherit",
          }}>
            {v.label}
          </button>
        ))}

        <div style={{ flex: 1 }} />

        {/* Zoom indicator + reset */}
        <span style={{ fontSize: 9, color: C.text3, marginRight: 6 }}>
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
          title="Reset view"
          style={{
            padding: "2px 8px", fontSize: 9, borderRadius: 3,
            border: `1px solid ${C.border}`, cursor: "pointer",
            background: "transparent", color: C.text3,
          }}
        >
          ⊡ Reset
        </button>

        {/* Zoom in / out */}
        {["+", "−"].map((lbl, i) => (
          <button key={lbl}
            onClick={() => setZoom(z => Math.min(4, Math.max(0.25, z * (i === 0 ? 1.2 : 0.8))))}
            style={{
              width: 22, height: 22, padding: 0, fontSize: 14,
              borderRadius: 3, border: `1px solid ${C.border}`,
              cursor: "pointer", background: "transparent", color: C.text3,
              marginLeft: 3, lineHeight: 1,
            }}
          >{lbl}</button>
        ))}
      </div>

      {/* ── KPI floating pills (right, outside SVG pan area) ─────────────── */}
      <div style={{
        position: "absolute", top: 44, right: 10, zIndex: 10,
        display: "flex", flexDirection: "column", gap: 5,
        pointerEvents: "none",
      }}>
        {[
          { label: "BELT SPEED",
            value: `${Number(r.v ?? r.v_ms ?? 0).toFixed(2)}`,
            unit: "m/s", color: C.pulley },
          { label: "CAPACITY",
            value: `${Number(r.Q ?? r.Q_th ?? 0).toFixed(0)}`,
            unit: "t/h",
            color: (r.Q ?? 0) >= (inputs?.Q_req ?? 0) ? C.success : C.danger },
          { label: "MOTOR",
            value: `${r.motor_kw ?? r.motor_kW ?? "—"}`,
            unit: "kW", color: C.motor },
          { label: "DISCHARGE",
            value: `${r.theta_rel != null ? Number(r.theta_rel).toFixed(1) : "—"}`,
            unit: "° from vert", color: C.feed },
          { label: "CR",
            value: `${r.cr != null ? Number(r.cr).toFixed(3) : "—"}`,
            unit: r.is_continuous ? "HF mode" : "centrifugal",
            color: r.is_continuous
              ? (r.cr < 1.0 ? C.success : C.danger)
              : (r.cr >= 1.0 && r.cr <= 2.5 ? C.success : C.warning) },
        ].map(k => (
          <div key={k.label} style={{
            background: "rgba(7,17,30,.88)", backdropFilter: "blur(4px)",
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
      <div
        ref={containerRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
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
          />
        </div>
      </div>

      {/* ── Tip ──────────────────────────────────────────────────────────── */}
      <div style={{
        padding: "3px 10px", fontSize: 8, color: C.text3,
        borderTop: `1px solid ${C.border}`, flexShrink: 0,
        letterSpacing: ".03em",
      }}>
        Scroll to zoom  ·  Drag to pan  ·  Double-click reset
      </div>
    </div>
  );
}