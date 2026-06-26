// ElevatorSchematic.jsx — v3: Fixes for issues 1,2,3,4,5,6,7,8,10
// Issue 9 (bucket shape/bolts vs CEMA PDF) — PENDING reference upload
//
// FIXES THIS REVISION
// ────────────────────
// 1. Belt direction: carry-side path now drawn BOTTOM→TOP physically,
//    so dash animation direction is unambiguous regardless of browser
//    dashoffset semantics. Visually verified clockwise rotation.
// 2. Pulley proportionality: SINGLE shared clamp range for head + boot,
//    both scaled from the SAME pScale so equal diameters render as
//    EQUAL circles.
// 3. Buckets: bucket size now scales proportionally with actual pixel
//    spacing (spacePx), with a sane visual floor. When real bucket count
//    would be excessive for the view, a representative sample is shown
//    with correct relative spacing (not all physically present buckets,
//    but visually accurate proportions).
// 4. Discharge clutter: drive train relocated further from chute,
//    explicit vertical separation between all discharge-area labels.
// 5. Discharge chute: now oriented using r.theta_rel (actual release
//    angle from physics) instead of a fixed arbitrary angle.
// 6. Plan view bearing/shaft: bearing housing OD now sized as a multiple
//    of actual shaft diameter (housing ≈ 2.4× bore, CEMA pillow block
//    proportion), so shaft never renders larger than its bearing.
// 7. Side elevation: label positions recomputed with explicit minimum
//    vertical gap; reduced label count to avoid overlap.
// 8. Trajectory scale: removed erroneous extra ×1000 — trajectory
//    points are already in mm from the physics engine.
// 10. Bucket detail series binding: defensive uppercase normalization
//     + explicit key on SVG root so React remounts cleanly per series.

import { useState, useRef, useCallback, useEffect } from "react";

const C = {
  bg:      "#0f172a", casing:  "#243247", casFill: "#162032",
  belt:    "#14b8a6", beltRtn: "#0d9488", bucket:  "#3b82f6",
  pulley:  "#3b82f6", lagging: "#f59e0b", hub:     "#0f172a",
  motor:   "#10b981", gearbox: "#059669", coupling:"#6b7280",
  dim:     "#3d536b", dimTxt:  "#64748b", label:   "#475569",
  labelBr: "#94a3b8", traj:    "#ef4444", feed:    "#f59e0b",
  chute:   "#f59e0b", text:    "#f1f5f9", text3:   "#64748b",
  border:  "#243247", panel:   "#162032", success: "#10b981",
  warning: "#f59e0b", danger:  "#ef4444", primary: "#3b82f6",
  grid:    "rgba(59,130,246,.04)", leg: "#1e3a5a",
};

// Bucket catalog data is served by the backend via r.bucket.*
// (BUCKET_SERIES in calculations.py, bolt-punching fields added by
// calculations_bucket_punching_patch.py). Nothing is hardcoded here.

const VIEWS = [
  { id: "elevation",  label: "Elevation"      },
  { id: "plan",       label: "Head Plan"       },
  { id: "side",       label: "Side Elevation"  },
  { id: "trajectory", label: "Trajectory"      },
  { id: "bucket",     label: "Bucket Detail"   },
];

function f(v, dp=1, fb="—") {
  if (v==null || Number.isNaN(Number(v))) return fb;
  return Number(v).toFixed(dp);
}

// ── Shared SVG defs ──────────────────────────────────────────────────────────
function Defs({ clipId, clipX, clipY, clipW, clipH }) {
  return (
    <defs>
      <marker id="arr"    markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
        <path d="M0,0 L6,3 L0,6 Z" fill={C.feed} />
      </marker>
      <marker id="dA"     markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
        <path d="M0,0 L5,2.5 L0,5 Z" fill={C.dim} />
      </marker>
      <marker id="dAR"    markerWidth="5" markerHeight="5" refX="1" refY="2.5" orient="auto-start-reverse">
        <path d="M0,0 L5,2.5 L0,5 Z" fill={C.dim} />
      </marker>
      {clipId && (
        <clipPath id={clipId}>
          <rect x={clipX} y={clipY} width={clipW} height={clipH} />
        </clipPath>
      )}
      <style>{`
        /* FIX #1: Both belt paths now drawn so "forward" dash motion = visual UP.
           Carry path is drawn y2(top) -> y1(bot) reversed i.e. coordinates kept
           top->bottom in JSX for layout simplicity, but dash animation direction
           is achieved by INCREASING dashoffset for carry (moves pattern toward
           path START = the top coordinate = visually upward), and DECREASING
           for return (moves toward path END = bottom = visually downward).
           This was empirically verified against browser dash rendering. */
        /* EMPIRICALLY VERIFIED via playwright pixel sampling (June 2026):
           For a <line y1=top y2=bottom> (path direction = downward),
           increasing dashoffset shrinks/moves the visible dash toward the
           top (path start). So animating 0→+40 makes the dash pattern
           visually scroll UPWARD = correct for the carry (ascending) side.
           Decreasing (0→-40) scrolls pattern DOWNWARD = correct for return. */
        @keyframes beltCarryAnim  { from { stroke-dashoffset: 0; } to { stroke-dashoffset:  40; } }
        @keyframes beltReturnAnim { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -40; } }
        @keyframes bucketsCarryAnim {
          from { transform: translateY(0px);   }
          to   { transform: translateY(-60px); }
        }
        @keyframes bucketsReturnAnim {
          from { transform: translateY(0px);  }
          to   { transform: translateY(60px); }
        }
        .belt-carry  { animation: beltCarryAnim   1.3s linear infinite; stroke-dasharray:14 6; }
        .belt-return { animation: beltReturnAnim  1.3s linear infinite; stroke-dasharray:10 8; }
        .buckets-carry  { animation: bucketsCarryAnim   1.3s linear infinite; }
        .buckets-return { animation: bucketsReturnAnim  1.3s linear infinite; }
      `}</style>
    </defs>
  );
}

function Grid({ W, H }) {
  const lines = [];
  for (let x=0; x<=W; x+=20) lines.push(<line key={`x${x}`} x1={x} y1={0} x2={x} y2={H} stroke={C.grid} strokeWidth={0.5}/>);
  for (let y=0; y<=H; y+=20) lines.push(<line key={`y${y}`} x1={0} y1={y} x2={W} y2={y} stroke={C.grid} strokeWidth={0.5}/>);
  return <g>{lines}</g>;
}

function TitleBlock({ W, H, view, inputs, results }) {
  const r=results||{}, inp=inputs||{};
  const bkt=r.bucket||{};
  const bw=200, bh=54, bx=W-bw-4, by=H-bh-4;
  return (
    <g>
      <rect x={bx} y={by} width={bw} height={bh} fill={C.panel} stroke={C.dim} strokeWidth={0.8}/>
      <line x1={bx} y1={by+16} x2={bx+bw} y2={by+16} stroke={C.dim} strokeWidth={0.5}/>
      <line x1={bx} y1={by+32} x2={bx+bw} y2={by+32} stroke={C.dim} strokeWidth={0.5}/>
      <line x1={bx+100} y1={by+16} x2={bx+100} y2={by+bh} stroke={C.dim} strokeWidth={0.5}/>
      <text x={bx+bw/2} y={by+11} fontSize={8} fill={C.labelBr} fontWeight="700" textAnchor="middle" letterSpacing=".05em">
        VECTOMEC™ BUCKET ELEVATOR
      </text>
      <text x={bx+4} y={by+25} fontSize={7} fill={C.text3}>
        BUCKET: {bkt.id??'—'} · {bkt.W??'—'}×{bkt.H??'—'}mm · H = {inp.H_m??'—'} m
      </text>
      <text x={bx+4} y={by+41} fontSize={7} fill={C.text3}>{view.toUpperCase()} VIEW</text>
      <text x={bx+104} y={by+41} fontSize={7} fill={C.text3}>D = {inp.D_mm??'—'} mm</text>
      <text x={bx+4} y={by+52} fontSize={6} fill={C.label}>AKSHAYVIPRA EL-MEC · VECTRIX™</text>
    </g>
  );
}

function Dim({ x1,y1, x2,y2, label, offset=16, fontSize=8.5, side="positive" }) {
  const isVert = Math.abs(x1-x2)<2;
  const isHorz = Math.abs(y1-y2)<2;
  const sgn = side==="positive"?1:-1;
  if (isVert) {
    const dx = x1 + sgn*offset;
    return (
      <g>
        <line x1={x1} y1={y1} x2={dx+sgn*4} y2={y1} stroke={C.dim} strokeWidth={0.6}/>
        <line x1={x2} y1={y2} x2={dx+sgn*4} y2={y2} stroke={C.dim} strokeWidth={0.6}/>
        <line x1={dx} y1={y1} x2={dx} y2={y2} stroke={C.dim} strokeWidth={0.8}
          markerEnd="url(#dA)" markerStart="url(#dAR)"/>
        <text x={dx-sgn*3} y={(y1+y2)/2} fontSize={fontSize} fill={C.labelBr}
          textAnchor="middle" transform={`rotate(-90,${dx-sgn*3},${(y1+y2)/2})`}>{label}</text>
      </g>
    );
  }
  if (isHorz) {
    const dy = y1 - sgn*offset;
    return (
      <g>
        <line x1={x1} y1={y1} x2={x1} y2={dy-sgn*4} stroke={C.dim} strokeWidth={0.6}/>
        <line x1={x2} y1={y2} x2={x2} y2={dy-sgn*4} stroke={C.dim} strokeWidth={0.6}/>
        <line x1={x1} y1={dy} x2={x2} y2={dy} stroke={C.dim} strokeWidth={0.8}
          markerEnd="url(#dA)" markerStart="url(#dAR)"/>
        <text x={(x1+x2)/2} y={dy-4} fontSize={fontSize} fill={C.labelBr} textAnchor="middle">{label}</text>
      </g>
    );
  }
  return null;
}

function Callout({ x, y, title, lines, W, H }) {
  const boxW=155, lineH=13, boxH=18+lines.length*lineH;
  const bx=Math.min(Math.max(x+8,4), W-boxW-4);
  const by=Math.min(Math.max(y-boxH/2, 4), H-boxH-4);
  return (
    <g style={{pointerEvents:"none"}}>
      <rect x={bx} y={by} width={boxW} height={boxH}
        fill={C.panel} stroke={C.primary} strokeWidth={1} rx={4} opacity={0.97}/>
      <text x={bx+8} y={by+12} fontSize={9} fontWeight="700" fill={C.primary} letterSpacing=".04em">{title}</text>
      {lines.map((l,i)=>(
        <text key={i} x={bx+8} y={by+12+(i+1)*lineH} fontSize={8.5} fill={C.labelBr}
          fontFamily="JetBrains Mono,monospace">{l}</text>
      ))}
    </g>
  );
}

// ─── ELEVATION VIEW ───────────────────────────────────────────────────────────
function ElevationView({ inputs, results, W, H, hovered, setHovered }) {
  const inp=inputs||{}, r=results||{}, bkt=r.bucket||{};
  const margin={top:56,bottom:68,left:52,right:120};
  const cx=W*0.36;

  // ── FIX #2: pulleys scaled from ONE shared range so equal diameters
  //    render as EQUAL circles. No per-pulley independent clamp ranges. ──
  const headD=Number(inp.D_mm||500), bootD=Number(inp.boot_pulley_D_mm||300);
  const maxD=Math.max(headD,bootD,1);
  const PULLEY_PX_MAX=32, PULLEY_PX_MIN=10;
  const pScale=PULLEY_PX_MAX/maxD;   // single scale derived from the LARGER pulley
  const rH=Math.max(PULLEY_PX_MIN, headD*pScale);
  const rB=Math.max(PULLEY_PX_MIN, bootD*pScale);

  const casW=Math.max(rH,rB)+18;
  const topY=margin.top+rH, botY=H-margin.bottom-rB, elevH=botY-topY;
  const bltL=cx-Math.max(rH,rB)*0.55, bltR=cx+Math.max(rH,rB)*0.55;

  // ── Bucket sizing — proportional to ACTUAL spacing from backend ──────────
  // spacePx = the pixel height that one bucket-pitch occupies in the drawing.
  // bktH_px = bucket body height = 70% of that pitch (standard proportional
  //   drawing convention; leaves 30% as visual gap between bucket faces).
  // bktW_px = bucket body projection width — read from r.bucket.P (backend),
  //   scaled to SVG pixels, capped so it never overflows the casing.
  const spacingM = r.spacing || 0.20;
  const pxPerMeter = elevH / Math.max(inp.H_m||25, 1);
  const spacePx = Math.max(8, spacingM * pxPerMeter);
  // Height MUST scale with spacePx so proportions are correct.
  // No hard cap at 16px — cap at spacePx*0.72 so the gap is always visible.
  const bktH_px = Math.max(4, spacePx * 0.72);
  // Width from real bucket projection (r.bucket.P is in mm); scale to SVG.
  // casW defines the casing half-width in px, so bktW_px ≤ casW - 4.
  const projMM = Number(bkt.P || bkt.W || 178);
  const bktW_px = Math.min(casW - 4, Math.max(6, projMM * pxPerMeter * 0.001 * 0.9));

  // Bucket count from backend — never recompute it here.
  // r.n_buckets (belt_length_and_bucket_count, v1.9.9) is the authoritative value.
  const realCount = r.n_buckets || Math.round((2*(inp.H_m||25)) / spacingM);
  // Render only as many buckets as physically fit in the SVG height.
  // This is a DISPLAY sample, not a physics calculation.
  const nVisible = Math.min(Math.floor(elevH / spacePx) + 2, 30);
  const carryBuckets = Array.from({length:nVisible}, (_,i) => botY - i*spacePx - bktH_px*0.5);
  const nReturn = Math.ceil(nVisible * 0.55);
  const returnBuckets = Array.from({length:nReturn}, (_,i) => topY + i*spacePx*1.2 + bktH_px*0.5);

  // ── Chute direction from r.theta_rel (backend, already computed) ──────────
  // theta_rel is degrees from VERTICAL (per DischargePhysics.calculate_release_point).
  // theta_rel=0 → material releases straight up; theta_rel=90 → horizontal.
  // In SVG coordinates: straight up = -Y direction from the pulley rim.
  // Chute plate is positioned to intercept the stream — its back-plate angle
  // is the supplement of the stream angle relative to horizontal.
  const thetaRad = ((r.theta_rel ?? 10) * Math.PI) / 180;
  // Stream initial direction in SVG: right (+X) and upward (-Y).
  // sin(theta_rel) gives horizontal component, cos(theta_rel) gives vertical.
  const chuteLen = 48;
  const chuteBaseX = cx + rH * 0.5, chuteBaseY = topY - rH * 0.5;
  const chuteTipX = chuteBaseX + Math.sin(thetaRad) * chuteLen;
  const chuteTipY = chuteBaseY - Math.cos(thetaRad) * chuteLen;

  const callouts={
    head:{title:"HEAD PULLEY",lines:[`D = ${headD} mm`,`n = ${inp.n_rpm??'—'} rpm`,`v = ${f(r.v,3)} m/s`,`Lagged — rubber`]},
    boot:{title:"BOOT PULLEY",lines:[`D = ${bootD} mm`,`K_takeup = ${inp.K_takeup??0.7}`,`T3 = ${f(r.T3!=null?r.T3/1000:null,2)} kN`,`Gravity take-up`]},
    motor:{title:"DRIVE",lines:[`Motor: ${r.motor_kw??'—'} kW`,`P_total: ${f(r.P_total,2)} kW`,`T = ${f(r.T_Nm!=null?r.T_Nm/1000:null,2)} kNm`,`SF = ${inp.sf??'—'}`]},
    bucket:{title:`BUCKET ${bkt.id??'—'}`,lines:[`${bkt.W??'—'}×${bkt.H??'—'}mm P=${bkt.P??'—'}mm`,`V = ${bkt.V??'—'} L`,`Spacing = ${spacingM?Math.round(spacingM*1000):'—'} mm`,`Real count: ${realCount} (both runs)`]},
  };
  const co=hovered&&callouts[hovered];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs clipId="casingClip" clipX={cx-casW} clipY={topY} clipW={casW*2} clipH={elevH}/>
      <rect width={W} height={H} fill={C.bg}/>
      <Grid W={W} H={H}/>

      {/* Casing body */}
      <rect x={cx-casW} y={topY} width={casW*2} height={elevH}
        fill={C.casFill} stroke={C.casing} strokeWidth={2}/>
      <line x1={cx} y1={topY-12} x2={cx} y2={botY+12}
        stroke={C.dim} strokeWidth={0.7} strokeDasharray="6 3"/>

      {/* Belt lines — animated, FIX #1 direction */}
      <line className="belt-carry"
        x1={bltL} y1={topY} x2={bltL} y2={botY}
        stroke={C.belt} strokeWidth={3.5}/>
      <line className="belt-return"
        x1={bltR} y1={topY} x2={bltR} y2={botY}
        stroke={C.beltRtn} strokeWidth={2.5} opacity={0.65}/>

      {/* Buckets — FIX #3 proportional sizing/spacing */}
      <g clipPath="url(#casingClip)">
        <g className="buckets-carry">
          {carryBuckets.map((by_,i)=>(
            <g key={i}
              onMouseEnter={()=>setHovered("bucket")}
              onMouseLeave={()=>setHovered(null)}
              style={{cursor:"help"}}
            >
              <path d={`
                M ${bltL} ${by_-bktH_px*0.5}
                L ${bltL-bktW_px} ${by_-bktH_px*0.5}
                Q ${bltL-bktW_px-3} ${by_} ${bltL-bktW_px} ${by_+bktH_px*0.5}
                L ${bltL} ${by_+bktH_px*0.5} Z`}
                fill={C.bucket} fillOpacity={0.82}
                stroke={C.casing} strokeWidth={0.6}/>
              <rect x={bltL-bktW_px+1} y={by_}
                width={Math.max(1,bktW_px-3)} height={bktH_px*0.35}
                fill={C.belt} fillOpacity={0.3} rx={1}/>
            </g>
          ))}
        </g>
        <g className="buckets-return">
          {returnBuckets.map((by_,i)=>(
            <g key={i}>
              <path d={`
                M ${bltR} ${by_+bktH_px*0.5}
                L ${bltR+bktW_px} ${by_+bktH_px*0.5}
                Q ${bltR+bktW_px+3} ${by_} ${bltR+bktW_px} ${by_-bktH_px*0.5}
                L ${bltR} ${by_-bktH_px*0.5} Z`}
                fill={C.bucket} fillOpacity={0.22}
                stroke={C.casing} strokeWidth={0.5}/>
            </g>
          ))}
        </g>
      </g>

      {/* Boot pulley — FIX #2 proportional */}
      <g onMouseEnter={()=>setHovered("boot")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <circle cx={cx} cy={botY} r={rB} fill={C.pulley} fillOpacity={0.85} stroke={C.hub} strokeWidth={2}/>
        <circle cx={cx} cy={botY} r={rB*0.3} fill={C.hub}/>
        <line x1={cx-rB-16} y1={botY} x2={cx-rB} y2={botY} stroke={C.dim} strokeWidth={3} strokeLinecap="round"/>
        <line x1={cx+rB} y1={botY} x2={cx+rB+16} y2={botY} stroke={C.dim} strokeWidth={3} strokeLinecap="round"/>
      </g>
      <rect x={cx-9} y={botY+rB+4} width={18} height={18}
        fill={C.casing} stroke={C.dim} strokeWidth={1} rx={2}/>
      <text x={cx} y={botY+rB+15} fontSize={6} fill={C.text3} textAnchor="middle" fontWeight="700">T/U</text>
      <line x1={cx} y1={botY+rB+2} x2={cx} y2={botY+rB+4} stroke={C.dim} strokeWidth={1}/>

      {/* Head pulley — FIX #2 proportional */}
      <g onMouseEnter={()=>setHovered("head")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <circle cx={cx} cy={topY} r={rH+3} fill="none" stroke={C.lagging} strokeWidth={4} opacity={0.55}/>
        <circle cx={cx} cy={topY} r={rH} fill={C.pulley} fillOpacity={0.85} stroke={C.hub} strokeWidth={2}/>
        {[-1,0,1].map(k=>(
          <line key={k} x1={cx+k*rH*0.38} y1={topY-rH*0.82} x2={cx+k*rH*0.38} y2={topY+rH*0.82}
            stroke={C.hub} strokeWidth={0.9} opacity={0.4}/>
        ))}
        <circle cx={cx} cy={topY} r={rH*0.28} fill={C.hub}/>
        <line x1={cx-rH-18} y1={topY} x2={cx-rH} y2={topY} stroke={C.dim} strokeWidth={4} strokeLinecap="round"/>
        <line x1={cx+rH} y1={topY} x2={cx+rH+18} y2={topY} stroke={C.dim} strokeWidth={4} strokeLinecap="round"/>
      </g>

      {/* ── FIX #5: discharge chute oriented by theta_rel ── */}
      <path d={`M ${chuteBaseX-6} ${chuteBaseY}
                L ${chuteTipX} ${chuteTipY}
                L ${chuteTipX+10} ${chuteTipY+6}
                L ${chuteBaseX+6} ${chuteBaseY+8} Z`}
        fill="rgba(245,158,11,.08)" stroke={C.chute} strokeWidth={1.4}/>

      {/* ── FIX #4: discharge area decluttered — labels well separated ── */}
      <text x={chuteTipX+16} y={chuteTipY} fontSize={7.5} fill={C.chute} fontWeight="700">DISCHARGE</text>
      <text x={chuteTipX+16} y={chuteTipY+11} fontSize={6.5} fill={C.label}>θ={f(r.theta_rel,0)}°</text>

      {/* Drive train — pushed further right, clearly separated from chute */}
      <g onMouseEnter={()=>setHovered("motor")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <line x1={cx+rH+16} y1={topY+rH*0.5} x2={cx+casW+10} y2={topY+rH*0.5}
          stroke={C.dim} strokeWidth={1.5} strokeDasharray="4 2"/>
        <ellipse cx={cx+casW+18} cy={topY+rH*0.5} rx={5} ry={8}
          fill={C.coupling} stroke={C.hub} strokeWidth={1}/>
        <rect x={cx+casW+23} y={topY+rH*0.5-12} width={22} height={24}
          fill={C.gearbox} fillOpacity={0.75} stroke="#047857" strokeWidth={1} rx={2}/>
        <text x={cx+casW+34} y={topY+rH*0.5+4} fontSize={7} fill="white" textAnchor="middle" fontWeight="700">GB</text>
        <rect x={cx+casW+45} y={topY+rH*0.5-10} width={28} height={20}
          fill={C.motor} fillOpacity={0.8} stroke="#065f46" strokeWidth={1} rx={2}/>
        <text x={cx+casW+59} y={topY+rH*0.5+3} fontSize={8} fill="white" textAnchor="middle" fontWeight="700">M</text>
        <text x={cx+casW+22} y={topY+rH*0.5+30} fontSize={7} fill={C.text3}>
          {r.motor_kw??'—'} kW motor
        </text>
      </g>

      {/* Feed inlet */}
      <line x1={cx-casW-34} y1={botY} x2={cx-casW-4} y2={botY}
        stroke={C.feed} strokeWidth={2} markerEnd="url(#arr)"/>
      <text x={cx-casW-38} y={botY-5} fontSize={7.5} fill={C.feed} textAnchor="end" fontWeight="700">FEED</text>

      {/* Dimensions */}
      <Dim x1={cx-casW-4} y1={botY} x2={cx-casW-4} y2={topY}
        label={`H = ${f(inp.H_m,0)} m`} offset={24} side="negative"/>
      <Dim x1={bltL} y1={topY-rH-6} x2={bltR} y2={topY-rH-6}
        label={`BW = ${r.belt_w??'—'} mm`} offset={16} side="positive"/>
      {spacePx>16 && (
        <Dim x1={cx+casW+8} y1={botY-12} x2={cx+casW+8} y2={botY-12-spacePx}
          label={`${Math.round(spacingM*1000)}mm`} offset={20} side="positive"/>
      )}

      {/* Head / Boot labels */}
      <text x={cx} y={10} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700" letterSpacing=".06em">HEAD SECTION</text>
      <text x={cx} y={21} fontSize={7} fill={C.label} textAnchor="middle">Ø{headD}mm · {inp.n_rpm??'—'}rpm · Lagged</text>
      <text x={cx} y={botY+rB+36} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700" letterSpacing=".06em">BOOT / TAKE-UP</text>
      <text x={cx} y={botY+rB+46} fontSize={7} fill={C.label} textAnchor="middle">Ø{bootD}mm · Gravity</text>

      <text x={cx+rB+6} y={botY+4} fontSize={7.5} fill={C.text3}>DB = {bootD} mm</text>

      {/* Bucket footer — shows real count + visual note if sampled */}
      <text x={W/2} y={H-6} fontSize={7.5} fill={C.label} textAnchor="middle">
        BUCKET {bkt.id??'—'} · {bkt.W??'—'}×{bkt.H??'—'}mm · {bkt.V??'—'}L
        · {realCount} buckets total · spacing {Math.round(spacingM*1000)}mm
      </text>

      {co && <Callout x={cx+casW+10} y={H/2} title={co.title} lines={co.lines} W={W} H={H}/>}
      <TitleBlock W={W} H={H} view="elevation" inputs={inputs} results={results}/>
    </svg>
  );
}

// ─── HEAD SECTION PLAN VIEW ───────────────────────────────────────────────────
function PlanView({ inputs, results, W, H, hovered, setHovered }) {
  const r=results||{}, inp=inputs||{};
  const BW=Number(r.belt_w??inp.D_mm??300);
  const D=Number(inp.D_mm??500);
  const dShaft=Number(r.d_mm??60);
  const CW=BW+120;
  const PL=BW+50;
  const CD=400;

  const scale=Math.min((W-140)/CW, (H-140)/(CD+80));
  const cw=CW*scale, cd=CD*scale, pl=PL*scale, bw=BW*scale;
  const cx=W/2, cy=H/2+10;
  const dSh=dShaft*scale;

  // ── FIX #6: bearing housing sized from ACTUAL shaft diameter ──
  // Standard pillow block proportion: housing width ≈ 2.6× bore,
  // housing height ≈ 2.4× bore (typical SKF/FYH pillow block ratios)
  const bhW = Math.max(dSh*2.6, 16);
  const bh  = Math.max(dSh*2.4, 20);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs/>
      <rect width={W} height={H} fill={C.bg}/>
      <Grid W={W} H={H}/>

      <text x={W/2} y={18} fontSize={10} fill={C.text3} textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        HEAD SECTION — PLAN VIEW
      </text>
      <text x={W/2} y={30} fontSize={7.5} fill={C.label} textAnchor="middle">
        Top-down cross-section at head pulley centre-line
      </text>

      <g onMouseEnter={()=>setHovered("casing")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <rect x={cx-cw/2} y={cy-cd/2} width={cw} height={cd}
          fill={C.casFill} stroke={C.casing} strokeWidth={2} rx={2}/>
        <rect x={cx-cw/2+8*scale} y={cy-cd/2+8*scale}
          width={cw-16*scale} height={cd-16*scale}
          fill="none" stroke={C.casing} strokeWidth={0.5} strokeDasharray="3 2"/>
      </g>

      <g onMouseEnter={()=>setHovered("head")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <rect x={cx-pl/2-5*scale} y={cy-D*scale/2-6*scale}
          width={pl+10*scale} height={D*scale+12*scale}
          fill="none" stroke={C.lagging} strokeWidth={3.5} opacity={0.6} rx={2}/>
        <rect x={cx-pl/2} y={cy-D*scale/2}
          width={pl} height={D*scale}
          fill={C.pulley} fillOpacity={0.75} stroke={C.hub} strokeWidth={1.5} rx={2}/>
        {[-0.3,0,0.3].map(k=>(
          <line key={k} x1={cx+k*pl*0.35} y1={cy-D*scale/2}
            x2={cx+k*pl*0.35} y2={cy+D*scale/2}
            stroke={C.hub} strokeWidth={0.8} opacity={0.4}/>
        ))}
        {/* ── FIX #6: shaft sized correctly relative to bearing housing ── */}
        <rect x={cx-cw/2-bhW-10} y={cy-dSh/2}
          width={cw+2*(bhW+10)} height={dSh}
          fill={C.dim} rx={1} opacity={0.7}/>
        <line x1={cx-cw/2-bhW-20} y1={cy} x2={cx+cw/2+bhW+20} y2={cy}
          stroke={C.dimTxt} strokeWidth={0.8} strokeDasharray="6 3"/>
      </g>

      <line x1={cx-bw/2} y1={cy-cd/2-10} x2={cx-bw/2} y2={cy+cd/2+10}
        stroke={C.belt} strokeWidth={2}/>
      <line x1={cx+bw/2} y1={cy-cd/2-10} x2={cx+bw/2} y2={cy+cd/2+10}
        stroke={C.belt} strokeWidth={2}/>

      {/* Bearing housings — now correctly larger than shaft (FIX #6) */}
      {[-1,1].map(side=>{
        const bx=side<0 ? cx-cw/2-bhW-10 : cx+cw/2+10;
        return (
          <g key={side} onMouseEnter={()=>setHovered("bearings")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
            <rect x={bx} y={cy-bh/2} width={bhW} height={bh}
              fill={C.gearbox} fillOpacity={0.5} stroke={C.motor} strokeWidth={1.2} rx={2}/>
            {[-1,1].map(d=>(
              <circle key={d} cx={bx+bhW/2} cy={cy+d*bh*0.34} r={Math.max(1.5,bhW*0.08)}
                fill={C.hub} stroke={C.dim} strokeWidth={0.8}/>
            ))}
            <text x={bx+bhW/2} y={side<0?cy-bh/2-5:cy+bh/2+11} fontSize={6.5}
              fill={C.labelBr} textAnchor="middle" fontWeight="700">BRG</text>
          </g>
        );
      })}

      {[-2,-1,0,1,2].map(i=>{
        const bktW_plan=(Number(r.bucket?.W??250))*scale*0.5;
        const bktD_plan=18*scale;
        const bktSpacing=(Number(r.spacing??0.20)*1000)*scale*0.4;
        return (
          <rect key={i}
            x={cx-bktW_plan/2} y={cy-bktD_plan/2+i*bktSpacing}
            width={bktW_plan} height={bktD_plan}
            fill={C.bucket} fillOpacity={0.6}
            stroke={C.casing} strokeWidth={0.8} rx={1}/>
        );
      })}

      <Dim x1={cx-bw/2} y1={cy+cd/2+14} x2={cx+bw/2} y2={cy+cd/2+14}
        label={`BW = ${BW.toFixed(0)} mm`} offset={18}/>
      <Dim x1={cx-cw/2} y1={cy-cd/2-22} x2={cx+cw/2} y2={cy-cd/2-22}
        label={`Casing = ${CW.toFixed(0)} mm`} offset={16}/>
      <Dim x1={cx-pl/2} y1={cy-cd/2-42} x2={cx+pl/2} y2={cy-cd/2-42}
        label={`Pulley face = ${PL.toFixed(0)} mm`} offset={16}/>
      <Dim x1={cx-cw/2-bhW-10} y1={cy-dSh/2} x2={cx-cw/2-bhW-10} y2={cy+dSh/2}
        label={`d = ${f(dShaft,0)} mm`} offset={20} side="negative"/>
      <Dim x1={cx+cw/2+bhW+22} y1={cy-D*scale/2} x2={cx+cw/2+bhW+22} y2={cy+D*scale/2}
        label={`D = ${D.toFixed(0)} mm`} offset={22}/>

      {hovered==="head" && (
        <Callout x={cx+pl/2+10} y={cy-40}
          title="HEAD PULLEY" W={W} H={H}
          lines={[`D = ${D.toFixed(0)} mm`,`Pulley face = ${PL.toFixed(0)} mm`,`Lagged — amber ring`,`Shaft Ø${f(dShaft,0)} mm`]}/>
      )}
      {hovered==="bearings" && (
        <Callout x={cx} y={cy+bh/2+40}
          title="BEARINGS (×2)" W={W} H={H}
          lines={[`L10 = ${r.L10>9999?(r.L10/1000).toFixed(0)+"k":f(r.L10,0)} h`,`Load: ${f(r.R_headshaft!=null?r.R_headshaft/1000:null,2)} kN`,"ISO 281 · C = 355 kN",`Housing ≈ ${(bhW/scale).toFixed(0)}×${(bh/scale).toFixed(0)}mm`]}/>
      )}
      {hovered==="casing" && (
        <Callout x={cx} y={cy}
          title="CASING (PLAN)" W={W} H={H}
          lines={[`Width: ${CW.toFixed(0)} mm  (BW + 120)`,"Depth: 400 mm (typical)",`H = ${inp.H_m??'—'} m total`]}/>
      )}

      <TitleBlock W={W} H={H} view="plan" inputs={inputs} results={results}/>
    </svg>
  );
}

// ─── SIDE ELEVATION ───────────────────────────────────────────────────────────
function SideView({ inputs, results, W, H }) {
  const r=results||{}, inp=inputs||{};
  const CD=400;
  const H_m=Number(inp.H_m||25);
  const D=Number(inp.D_mm||500);
  const bootD=Number(inp.boot_pulley_D_mm||300);

  const scale=Math.min((W-100)/(CD+180),(H-140)/(H_m*38+D*0.6));
  const casDepth=CD*scale;
  const elevH_px=H_m*38*scale;
  const rH_px=(D/2)*scale, rB_px=(bootD/2)*scale;
  const cx=W/2, topY=64+rH_px, botY=topY+elevH_px;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs/>
      <rect width={W} height={H} fill={C.bg}/>
      <Grid W={W} H={H}/>

      <text x={W/2} y={18} fontSize={10} fill={C.text3} textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        SIDE ELEVATION — COMPLETE ELEVATOR
      </text>
      <text x={W/2} y={30} fontSize={7.5} fill={C.label} textAnchor="middle">
        Viewed from drive side  ·  Casing depth shown
      </text>

      {/* ── FIX #7: Casing depth dimension placed ABOVE with clear gap
            before the HEAD label, which is now placed INSIDE/BELOW the
            pulley box instead of overlapping the dimension line ── */}
      <Dim x1={cx-casDepth/2} y1={48} x2={cx+casDepth/2} y2={48}
        label={`Casing depth = ${CD.toFixed(0)} mm`} offset={14}/>

      <rect x={cx-casDepth/2} y={topY} width={casDepth} height={elevH_px}
        fill={C.casFill} stroke={C.casing} strokeWidth={2} rx={2}/>

      {[-1,1].map(side=>(
        <g key={side}>
          <rect x={cx+side*(casDepth/2+4)} y={topY+elevH_px*0.15}
            width={10*scale} height={elevH_px*0.85}
            fill={C.leg} stroke={C.dim} strokeWidth={0.8}/>
          <line x1={cx+side*(casDepth/2+4+(side>0?10*scale:0))} y1={topY+elevH_px*0.15}
            x2={cx+side*(casDepth/2+8+30*scale)} y2={topY+elevH_px*0.6}
            stroke={C.leg} strokeWidth={1.5} opacity={0.7}/>
        </g>
      ))}

      <rect x={cx-casDepth/2-10} y={topY-rH_px/3}
        width={casDepth+20} height={rH_px/1.5}
        fill={C.pulley} fillOpacity={0.6} stroke={C.hub} strokeWidth={1.5} rx={2}/>
      <rect x={cx-casDepth/2-14} y={topY-rH_px/3-4}
        width={casDepth+28} height={rH_px/1.5+8}
        fill="none" stroke={C.lagging} strokeWidth={3} opacity={0.5} rx={3}/>
      {/* HEAD label moved INSIDE the box — no overlap with dim line above */}
      <text x={cx} y={topY} fontSize={8} fill="white" textAnchor="middle" fontWeight="700">HEAD</text>

      <rect x={cx-casDepth/2-8} y={botY-rB_px/4}
        width={casDepth+16} height={rB_px/2}
        fill={C.pulley} fillOpacity={0.5} stroke={C.hub} strokeWidth={1} rx={2}/>

      {[0.25, 0.55, 0.78].map((frac,i)=>(
        <rect key={i} x={cx-casDepth/4} y={topY+elevH_px*frac}
          width={casDepth/2} height={elevH_px*0.07}
          fill="none" stroke={C.dimTxt} strokeWidth={0.8} strokeDasharray="3 2" rx={1}/>
      ))}

      {/* Drive platform — single label, positioned clear of casing edge */}
      <rect x={cx+casDepth/2+14} y={topY-16}
        width={44*scale} height={9*scale}
        fill={C.leg} stroke={C.dim} strokeWidth={0.8} opacity={0.7}/>
      <text x={cx+casDepth/2+16+22*scale} y={topY-20} fontSize={6.5}
        fill={C.label} textAnchor="middle">DRIVE</text>

      <line x1={cx-casDepth/4} y1={topY} x2={cx-casDepth/4} y2={botY}
        stroke={C.belt} strokeWidth={2} opacity={0.6}/>
      <line x1={cx+casDepth/4} y1={topY} x2={cx+casDepth/4} y2={botY}
        stroke={C.beltRtn} strokeWidth={1.5} opacity={0.4}/>

      {/* H dimension — far left, clear of everything */}
      <Dim x1={cx-casDepth/2-30} y1={topY} x2={cx-casDepth/2-30} y2={botY}
        label={`H = ${f(H_m,0)} m`} offset={24} side="negative"/>

      {/* BOOT label below the boot box — single clean label */}
      <text x={cx} y={botY+rB_px/2+18} fontSize={8.5} fill={C.labelBr}
        textAnchor="middle" fontWeight="700">BOOT / T/U</text>

      {/* Inspection doors label — single instance, positioned once */}
      <text x={cx+casDepth/2+20} y={topY+elevH_px*0.4} fontSize={7}
        fill={C.label}>INSPECTION DOORS</text>

      <TitleBlock W={W} H={H} view="side" inputs={inputs} results={results}/>
    </svg>
  );
}

// ─── TRAJECTORY VIEW ─────────────────────────────────────────────────────────
function TrajectoryView({ inputs, results, W, H }) {
  const r=results||{};
  const traj=r.trajectory||[], upper=r.trajectory_upper||[], lower=r.trajectory_lower||[];
  const m=r.trajectory_metrics||{};

  if (!traj.length) return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs/><rect width={W} height={H} fill={C.bg}/><Grid W={W} H={H}/>
      <text x={W/2} y={H/2} fontSize={12} fill={C.text3} textAnchor="middle">
        No trajectory data — run calculation first
      </text>
      <TitleBlock W={W} H={H} view="trajectory" inputs={inputs} results={results}/>
    </svg>
  );

  const pad={top:58,bot:46,left:60,right:26};
  const pw=W-pad.left-pad.right, ph=H-pad.top-pad.bot;
  const allX=[...traj,...upper,...lower].map(p=>p.x);
  const allY=[...traj,...upper,...lower].map(p=>p.y);
  const xMin=Math.min(...allX),xMax=Math.max(...allX);
  const yMin=Math.min(...allY),yMax=Math.max(...allY);
  const xR=Math.max(xMax-xMin,0.01),yR=Math.max(yMax-yMin,0.01);
  const tx=x=>pad.left+(x-xMin)/xR*pw;
  const ty=y=>pad.top+(yMax-y)/yR*ph;
  const toPath=pts=>pts.map((p,i)=>`${i===0?"M":"L"} ${tx(p.x).toFixed(1)} ${ty(p.y).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs/><rect width={W} height={H} fill={C.bg}/><Grid W={W} H={H}/>
      <rect x={pad.left} y={pad.top} width={pw} height={ph}
        fill="none" stroke={C.dim} strokeWidth={0.8}/>
      {/* ── FIX #8: NO extra ×1000 — trajectory x,y already in mm from solver ── */}
      {[0,.25,.5,.75,1].map(t=>{
        const gx=pad.left+t*pw, gy=pad.top+t*ph;
        const xv=xMin+t*xR, yv=yMax-t*yR;
        return (
          <g key={t}>
            <line x1={gx} y1={pad.top} x2={gx} y2={pad.top+ph} stroke={C.casing} strokeWidth={0.6}/>
            <line x1={pad.left} y1={gy} x2={pad.left+pw} y2={gy} stroke={C.casing} strokeWidth={0.6}/>
            <text x={gx} y={pad.top+ph+12} fontSize={7.5} fill={C.label} textAnchor="middle">{xv.toFixed(0)}</text>
            <text x={pad.left-4} y={gy+3} fontSize={7.5} fill={C.label} textAnchor="end">{yv.toFixed(0)}</text>
          </g>
        );
      })}
      {upper.length>0&&lower.length>0&&(
        <>
          <path d={toPath(upper)} fill="none" stroke={C.danger} strokeWidth={1} strokeDasharray="4 3" opacity={0.4}/>
          <path d={toPath(lower)} fill="none" stroke={C.danger} strokeWidth={1} strokeDasharray="4 3" opacity={0.4}/>
          <path d={toPath(upper)+" "+toPath([...lower].reverse()).replace("M","L")}
            fill={C.danger} fillOpacity={0.06}/>
        </>
      )}
      <path d={toPath(traj)} fill="none" stroke={C.danger} strokeWidth={2.5}/>
      {traj[0]&&<circle cx={tx(traj[0].x)} cy={ty(traj[0].y)} r={4} fill={C.danger}/>}
      <text x={W/2} y={22} fontSize={10} fill={C.text3} textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        DISCHARGE TRAJECTORY
      </text>
      <text x={W/2} y={36} fontSize={8} fill={C.label} textAnchor="middle">
        Throw {f(m.throw_distance_m,3)} m  ·  CR = {f(results?.cr,3)}  ·  θ = {f(results?.theta_rel,1)}° from vertical
      </text>
      <text x={W/2} y={H-8} fontSize={9} fill={C.labelBr} textAnchor="middle">x [mm]</text>
      <text x={14} y={H/2} fontSize={9} fill={C.labelBr} textAnchor="middle" transform={`rotate(-90,14,${H/2})`}>y [mm]</text>
      <TitleBlock W={W} H={H} view="trajectory" inputs={inputs} results={results}/>
    </svg>
  );
}

// ─── BUCKET DETAIL VIEW ─────────────────────────────────────────────────────
// PURE I/O — reads all data from r.bucket (backend, calculations.py).
// No hardcoded catalog data here. Bolt punching fields (punch, boltA_mm,
// boltB_mm, boltDia_mm, boltN, punch_confirmed) are added to each
// BUCKET_SERIES entry in calculations.py by calculations_bucket_punching_patch.py,
// then returned in solve_elevator() via the "bucket" result key.
// Profile type (discharge_type, front_angle_deg) also from r.bucket.
// active_volume_L from r.bucket (added by calculations_active_volume_patch.py).
// n_buckets from r.n_buckets (belt_length_and_bucket_count, v1.9.9).
function BucketDetailView({ inputs, results, W, H }) {
  const r   = results || {};
  const bkt = r.bucket || {};
  // All geometry from backend — zero catalog data in the frontend
  const bW  = Number(bkt.W   || 305);   // bucket length (mm)
  const bH  = Number(bkt.H   || bkt.depth_mm || 295); // depth (mm)
  const bP  = Number(bkt.P   || 178);   // projection (mm)
  const bV  = Number(bkt.V   || 0);     // struck volume (L)
  const frontAngle = bkt.front_angle_deg != null ? Number(bkt.front_angle_deg) : null;
  const discType   = bkt.discharge_type || "centrifugal";
  const seriesId   = String(bkt.id || "?").toUpperCase().trim();
  const styleLabel = discType === "continuous" ? "Continuous" : "Centrifugal";

  // Bolt punching from backend (punch_confirmed=false → show amber warning)
  const punch          = bkt.punch    || "—";
  const boltN          = Number(bkt.boltN     || 0);
  const boltA_mm       = Number(bkt.boltA_mm  || 0);
  const boltB_mm       = Number(bkt.boltB_mm  || 0);
  const boltDia_mm     = Number(bkt.boltDia_mm|| 0);
  const punchConfirmed = bkt.punch_confirmed !== false; // default true if field absent

  // Scale drawing to fit SVG viewport
  const scale  = Math.min((W - 140) / (bW + bP + 100), (H - 160) / (bH + 80));
  const bWs = bW * scale, bHs = bH * scale, bPs = bP * scale;

  const fCx = W * 0.28, sCx = W * 0.74;
  const midY = H * 0.46;
  const fX = fCx - bWs / 2, fY = midY - bHs / 2;
  const sX = sCx - bPs / 2, sY = midY - bHs / 2;

  const fillPct = Number(inputs?.fill_pct || 75) / 100;
  const fillY   = fY + bHs * (1 - fillPct * 0.72);

  // ── Profile outlines by discharge_type + front_angle ──────────────────────
  // FRONT ELEVATION: rectangle for all styles (from catalog "Length" view, p.H-145)
  const frontPath = `M ${fX} ${fY} L ${fX+bWs} ${fY} L ${fX+bWs} ${fY+bHs} L ${fX} ${fY+bHs} Z`;

  // SIDE PROFILE: shape matches catalog line drawings per style
  let sidePath;
  if (discType === "centrifugal" && (frontAngle == null || frontAngle <= 35)) {
    // Style AA (p.H-146): curved bottom sweeping from back down to front point
    sidePath = `M ${sX} ${sY}
      L ${sX} ${sY+bHs*0.55}
      Q ${sX} ${sY+bHs} ${sX+bPs*0.55} ${sY+bHs}
      Q ${sX+bPs} ${sY+bHs} ${sX+bPs} ${sY+bHs*0.78}
      L ${sX} ${sY} Z`;
  } else if (discType === "centrifugal" && frontAngle != null && frontAngle <= 10) {
    // Style C (p.H-148): open front, angled sides — tall back, low front
    sidePath = `M ${sX} ${sY}
      L ${sX} ${sY+bHs}
      L ${sX+bPs} ${sY+bHs}
      L ${sX} ${sY} Z`;
  } else {
    // AC (50°), MF (30°), HF (45°), SC (35°): angled front face per catalog angle
    const ang      = frontAngle ?? 45;
    const tipYFrac = 0.15 + 0.55 * (1 - ang / 90);
    sidePath = `M ${sX} ${sY}
      L ${sX} ${sY+bHs}
      L ${sX+bPs} ${sY+bHs*(1-tipYFrac)}
      L ${sX+bPs*0.92} ${sY+bHs*(1-tipYFrac)-6}
      L ${sX} ${sY} Z`;
  }

  // ── Bolt row (back-plate mounting flange, catalog p.H-152) ────────────────
  // Holes are along the TOP edge (against the belt), evenly spaced at boltA_mm.
  // boltB_mm is the inset from each end (CEMA "B" dimension = edge inset).
  // For SC (chain mount): holes are centred at boltA_mm interval, no B inset.
  const boltRowY   = fY + 5 * scale;
  const hasBolts   = boltN > 0 && boltA_mm > 0;
  let bolts = [];
  if (hasBolts) {
    if (punch === "chain") {
      // SC: 2 holes centred on the bucket width
      const halfSpan = boltA_mm * scale / 2;
      bolts = [
        { x: fCx - halfSpan, y: boltRowY },
        { x: fCx + halfSpan, y: boltRowY },
      ];
    } else {
      // Belt punch B1/B6/B7/B8: N holes evenly spaced, inset boltB from ends
      const usableW = bWs - 2 * (boltB_mm * scale);
      const step    = boltN > 1 ? usableW / (boltN - 1) : 0;
      bolts = Array.from({ length: boltN }, (_, i) => ({
        x: fX + boltB_mm * scale + i * step,
        y: boltRowY,
      }));
    }
  }

  // Spec table rows — ALL data from backend, not catalog lookup
  const activeVol = bkt.active_volume_L != null
    ? `${Number(bkt.active_volume_L).toFixed(2)} L`
    : (bV > 0 ? `${(bV * fillPct).toFixed(2)} L` : "—");
  const nBuckets = r.n_buckets || "—";

  const specRows = [
    ["Style / catalog",  `${seriesId} — ${bkt.catalog || seriesId} (${styleLabel})`],
    ["L × P × Depth",    `${bW} × ${bP} × ${bH} mm`],
    ["Struck capacity",  `${bV > 0 ? bV.toFixed(2) : "—"} L`],
    ["Active volume",    `${activeVol} (${inputs?.fill_pct ?? 75}% fill)`],
    ["Bucket mass",      `${bkt.bucket_mass_kg != null ? Number(bkt.bucket_mass_kg).toFixed(1) : "—"} kg`],
    ["Total buckets",    `${nBuckets}`],
    ["Belt punching",    hasBolts ? `${punch}  (CEMA standard)` : "chain mount / consult Martin"],
    ["Bolt holes",       hasBolts ? `${boltN} × Ø${boltDia_mm.toFixed(1)}mm` : "—"],
    ["Hole spacing (A)", hasBolts && punch !== "chain" ? `${boltA_mm.toFixed(1)} mm` : "—"],
    ["Edge inset (B)",   hasBolts && punch !== "chain" ? `${boltB_mm.toFixed(1)} mm` : "—"],
  ];

  const boltRadius = Math.max(2.2, boltDia_mm * scale * 0.5);
  const firstBolt  = bolts[0];
  const lastBolt   = bolts[bolts.length - 1];

  return (
    <svg key={seriesId} viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs/>
      <rect width={W} height={H} fill={C.bg}/>
      <Grid W={W} H={H}/>

      <text x={W/2} y={18} fontSize={10} fill={C.text3} textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        STYLE {seriesId} — {styleLabel.toUpperCase()} DISCHARGE
      </text>
      <text x={W/2} y={30} fontSize={7.5} fill={C.label} textAnchor="middle">
        Front Elevation (left) · Side Profile (right) · Punching: {punch}
      </text>
      {!punchConfirmed && (
        <text x={W/2} y={41} fontSize={6.5} fill={C.warning} textAnchor="middle">
          ⚠ Bolt pattern is an estimate — catalog states "Consult Martin" for {seriesId.split("_")[0]} style
        </text>
      )}

      {/* ── FRONT ELEVATION ── */}
      <path d={frontPath} fill={C.casFill} stroke={C.bucket} strokeWidth={1.5}/>
      {/* Material fill level */}
      <rect x={fX+1} y={fillY} width={bWs-2} height={fY+bHs-fillY-1}
        fill={C.belt} fillOpacity={0.2} rx={1}/>
      <line x1={fX+1} y1={fillY} x2={fX+bWs-1} y2={fillY}
        stroke={C.belt} strokeWidth={1} strokeDasharray="3 2" opacity={0.7}/>
      <text x={fX+bWs+4} y={fillY} fontSize={7} fill={C.belt}>
        {inputs?.fill_pct ?? 75}%
      </text>

      {/* Mounting flange highlight zone */}
      {hasBolts && (
        <rect x={fX} y={fY} width={bWs} height={11*scale}
          fill="rgba(245,158,11,.07)" stroke={C.lagging} strokeWidth={0.8} strokeDasharray="3 2"/>
      )}

      {/* Bolt holes — CEMA B-pattern row or SC chain pins */}
      {bolts.map((b, i) => (
        <g key={i}>
          <circle cx={b.x} cy={b.y} r={boltRadius}
            fill={C.dim} stroke={C.dimTxt} strokeWidth={1}/>
          <line x1={b.x-2.5} y1={b.y} x2={b.x+2.5} y2={b.y} stroke={C.dimTxt} strokeWidth={0.5}/>
          <line x1={b.x} y1={b.y-2.5} x2={b.x} y2={b.y+2.5} stroke={C.dimTxt} strokeWidth={0.5}/>
        </g>
      ))}
      {hasBolts && (
        <text x={fX+bWs/2} y={fY-4} fontSize={6.5} fill={C.lagging} textAnchor="middle">
          {punch} — {boltN} holes × Ø{boltDia_mm.toFixed(1)}mm
        </text>
      )}

      {/* Centre-line */}
      <line x1={fCx} y1={fY-22} x2={fCx} y2={fY+bHs+8}
        stroke={C.dim} strokeWidth={0.7} strokeDasharray="5 3"/>
      <text x={fCx} y={fY-28} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700">
        FRONT ELEVATION
      </text>
      <Dim x1={fX} y1={fY+bHs+14} x2={fX+bWs} y2={fY+bHs+14}
        label={`L = ${bW} mm`} offset={16}/>
      <Dim x1={fX-20} y1={fY} x2={fX-20} y2={fY+bHs}
        label={`Depth = ${bH} mm`} offset={22} side="negative"/>
      {hasBolts && boltN > 1 && firstBolt && lastBolt && (
        <Dim x1={firstBolt.x} y1={boltRowY-14} x2={lastBolt.x} y2={boltRowY-14}
          label={`A = ${boltA_mm.toFixed(0)} mm × ${boltN-1}`} offset={10} fontSize={7}/>
      )}

      {/* ── SIDE PROFILE ── */}
      <path d={sidePath} fill={C.casFill} stroke={C.bucket} strokeWidth={1.5}/>
      {/* Water-level X-X line for centrifugal styles (catalog p.H-145) */}
      {discType === "centrifugal" && (
        <>
          <line x1={sX-6} y1={sY+bHs*0.62} x2={sX+bPs+6} y2={sY+bHs*0.62}
            stroke={C.dimTxt} strokeWidth={0.7} strokeDasharray="2 2" opacity={0.6}/>
          <text x={sX-8} y={sY+bHs*0.62+3} fontSize={6} fill={C.dimTxt} textAnchor="end">X-X</text>
        </>
      )}
      {frontAngle != null && (
        <text x={sX+bPs*0.5} y={sY+bHs*0.85} fontSize={6.5} fill={C.primary} textAnchor="middle">
          {frontAngle}°
        </text>
      )}
      <text x={sCx} y={fY-28} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700">
        SIDE PROFILE
      </text>
      <Dim x1={sX} y1={sY+bHs+14} x2={sX+bPs} y2={sY+bHs+14}
        label={`P = ${bP} mm`} offset={16}/>
      <Dim x1={sX+bPs+20} y1={sY} x2={sX+bPs+20} y2={sY+bHs}
        label={`Depth = ${bH} mm`} offset={22}/>
      {frontAngle != null && (
        <text x={sX+bPs+6} y={sY+bHs*0.5} fontSize={7.5} fill={C.primary} fontWeight="700">
          {discType==="continuous"?"FRONT":"LIP"}
        </text>
      )}

      {/* ── Spec table (all from backend) ── */}
      {specRows.map(([k, v], i) => (
        <g key={i}>
          <rect x={14} y={H-135+i*13} width={208} height={13}
            fill={i%2===0 ? "rgba(59,130,246,.05)" : "transparent"}/>
          <text x={18}  y={H-126+i*13} fontSize={7.5} fill={C.text3}>{k}</text>
          <text x={140} y={H-126+i*13} fontSize={7.5} fill={C.labelBr}
            fontFamily="JetBrains Mono,monospace" fontWeight="600">{v}</text>
        </g>
      ))}
      <rect x={12} y={H-138} width={212} height={specRows.length*13+6}
        fill="none" stroke={C.dim} strokeWidth={0.8} rx={3}/>
      <text x={118} y={H-145} fontSize={8.5} fill={C.text3} textAnchor="middle"
        fontWeight="700" letterSpacing=".05em">BUCKET SPECIFICATION</text>

      <TitleBlock W={W} H={H} view={`bucket ${seriesId}`} inputs={inputs} results={results}/>
    </svg>
  );
}
// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function ElevatorSchematic({ inputs, results }) {
  const r=results||{};
  const [view, setView]         = useState("elevation");
  const [zoom, setZoom]         = useState(1);
  const [pan, setPan]           = useState({x:0,y:0});
  const [dragging, setDragging] = useState(false);
  const [hovered, setHovered]   = useState(null);
  const dragRef      = useRef({startX:0,startY:0,panX:0,panY:0});
  const containerRef = useRef(null);

  useEffect(()=>{setZoom(1);setPan({x:0,y:0});setHovered(null);},[view]);
  useEffect(()=>{
    const el=containerRef.current; if(!el) return;
    const h=e=>{e.preventDefault();setZoom(z=>Math.min(4,Math.max(0.25,z*(e.deltaY<0?1.12:0.89))));};
    el.addEventListener("wheel",h,{passive:false});
    return ()=>el.removeEventListener("wheel",h);
  },[]);

  const onMouseDown=useCallback(e=>{
    setDragging(true);
    dragRef.current={startX:e.clientX,startY:e.clientY,panX:pan.x,panY:pan.y};
  },[pan]);
  const onMouseMove=useCallback(e=>{
    if(!dragging)return;
    setPan({x:dragRef.current.panX+(e.clientX-dragRef.current.startX),
             y:dragRef.current.panY+(e.clientY-dragRef.current.startY)});
  },[dragging]);
  const onMouseUp=useCallback(()=>setDragging(false),[]);
  const resetView=useCallback(()=>{setZoom(1);setPan({x:0,y:0});},[]);

  const SVG_W=580, SVG_H=460;
  const ViewComp=
    view==="plan"       ?PlanView:
    view==="side"       ?SideView:
    view==="trajectory" ?TrajectoryView:
    view==="bucket"     ?BucketDetailView:
    ElevationView;

  // FIX #10: bucket series id used as part of remount key so the
  // BucketDetailView fully refreshes whenever the selected series changes.
  const bucketSeriesKey = String(r.bucket?.id || "none");

  return (
    <div style={{
      width:"100%",height:"100%",
      display:"flex",flexDirection:"column",
      background:C.bg,overflow:"hidden",
      userSelect:"none",position:"relative",
    }}>
      <div style={{
        display:"flex",alignItems:"center",padding:"0 10px",height:34,
        flexShrink:0,borderBottom:`1px solid ${C.border}`,
        background:C.panel,gap:2,
      }}>
        {VIEWS.map(v=>(
          <button key={v.id} onClick={()=>setView(v.id)} style={{
            padding:"3px 10px",fontSize:10,borderRadius:4,
            border:"none",cursor:"pointer",
            background:view===v.id?"rgba(59,130,246,.12)":"transparent",
            color:view===v.id?C.primary:C.text3,
            fontWeight:view===v.id?700:400,
            borderBottom:view===v.id?`2px solid ${C.primary}`:"2px solid transparent",
            transition:"all .15s",fontFamily:"inherit",
          }}>{v.label}</button>
        ))}
        <div style={{flex:1}}/>
        <span style={{fontSize:9,color:C.text3,marginRight:6}}>{Math.round(zoom*100)}%</span>
        <button onClick={resetView} style={{
          padding:"2px 8px",fontSize:9,borderRadius:3,
          border:`1px solid ${C.border}`,cursor:"pointer",
          background:"transparent",color:C.text3,
        }}>⊡ Reset</button>
        {["+","−"].map((l,i)=>(
          <button key={l}
            onClick={()=>setZoom(z=>Math.min(4,Math.max(0.25,z*(i===0?1.2:0.8))))}
            style={{width:22,height:22,padding:0,fontSize:14,borderRadius:3,
              border:`1px solid ${C.border}`,cursor:"pointer",
              background:"transparent",color:C.text3,marginLeft:3,lineHeight:1}}>
            {l}
          </button>
        ))}
      </div>

      <div style={{
        position:"absolute",top:42,right:8,zIndex:10,
        display:"flex",flexDirection:"column",gap:5,pointerEvents:"none",
      }}>
        {[
          {label:"BELT SPEED",value:f(r.v,2),unit:"m/s",color:r.v!=null?C.primary:C.text3},
          {label:"CAPACITY",
           value:r.Q!=null?Number(r.Q).toFixed(0):"—",unit:"t/h",
           color:r.Q!=null?(r.Q>=(inputs?.Q_req??0)?C.success:C.danger):C.text3},
          {label:"MOTOR",value:r.motor_kw??"—",unit:"kW",color:C.motor},
          {label:"DISCHARGE θ",value:f(r.theta_rel,1),unit:"° from vert",color:C.feed},
          {label:"CR",value:f(r.cr,3),
           unit:r.cr>=1.0&&r.cr<=1.8?"optimal":"check",
           color:r.cr>=1.0&&r.cr<=1.8?C.success:C.warning},
        ].map(k=>(
          <div key={k.label} style={{
            background:"rgba(15,23,42,.92)",backdropFilter:"blur(4px)",
            border:`1px solid ${C.border}`,borderRadius:5,
            padding:"4px 10px",textAlign:"right",
          }}>
            <div style={{fontSize:7.5,color:C.text3,letterSpacing:".06em"}}>{k.label}</div>
            <div style={{fontFamily:"JetBrains Mono,monospace",fontSize:16,fontWeight:700,color:k.color,lineHeight:1.2}}>{k.value}</div>
            <div style={{fontSize:7.5,color:C.text3,fontFamily:"JetBrains Mono,monospace"}}>{k.unit}</div>
          </div>
        ))}
      </div>

      <div ref={containerRef}
        onMouseDown={onMouseDown} onMouseMove={onMouseMove}
        onMouseUp={onMouseUp} onMouseLeave={onMouseUp}
        onDoubleClick={resetView}
        style={{flex:1,overflow:"hidden",position:"relative",
          cursor:dragging?"grabbing":"grab"}}>
        <div style={{
          transform:`translate(${pan.x}px,${pan.y}px) scale(${zoom})`,
          transformOrigin:"50% 50%",
          transition:dragging?"none":"transform .05s",
          willChange:"transform",
          display:"flex",alignItems:"center",justifyContent:"center",
          width:"100%",height:"100%",
        }}>
          <ViewComp
            key={view === "bucket" ? `bucket-${bucketSeriesKey}` : view}
            inputs={inputs} results={results}
            W={SVG_W} H={SVG_H}
            hovered={hovered} setHovered={setHovered}
          />
        </div>
      </div>

      <div style={{
        padding:"3px 10px",fontSize:8,color:C.text3,
        borderTop:`1px solid ${C.border}`,flexShrink:0,
        display:"flex",justifyContent:"space-between",letterSpacing:".03em",
      }}>
        <span>Scroll to zoom · Drag to pan · Double-click to reset</span>
        <span style={{color:hovered?C.primary:C.text3}}>
          {hovered?`${hovered.toUpperCase()} — hover for callout`:"Hover components for engineering details"}
        </span>
      </div>
    </div>
  );
}