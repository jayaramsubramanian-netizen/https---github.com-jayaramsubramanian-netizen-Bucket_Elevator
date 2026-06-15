// ElevatorSchematic.jsx — Tasks 11 + 12 (v2) — All issues fixed
//
// FIXES FROM SCREENSHOT REVIEW
// ─────────────────────────────
// 1. BELT DIRECTION: carry side now animates upward correctly.
//    SVG path direction is top→bottom, so positive dashoffset moves dashes UP.
//    beltUp: 0 → +40 (carry, left, going up — correct clockwise rotation)
//    beltDown: 0 → -40 (return, right, going down)
//
// 2. BUCKETS MOVE WITH BELT: buckets are now inside an SVG <g> wrapped
//    in a CSS animation group. They scroll continuously with the belt.
//    A clip-path restricts the animated group to the casing area so
//    buckets don't appear outside the casing.
//
// 3. RETURN SIDE BUCKETS: inverted/faded buckets now appear on the
//    right (return) belt — empty, descending.
//
// 4. DISCHARGE CROWDING: chute label moved far right, motor labels
//    moved below motor box, DH label repositioned. 
//
// 5. PLAN VIEW FIXED: pulley shown as RECTANGLE (correct plan projection
//    of a cylinder), not ellipse. Ellipse = perspective/isometric, NOT plan.
//    Buckets shown as rectangles across belt width.
//
// 6. SIDE VIEW RENAMED & REBUILT: 'Side Section' → 'Side Elevation'
//    showing the COMPLETE elevator from 90° — casing depth, leg frame,
//    inspection doors, belt wrap around head pulley. 
//    The old "side view" was actually a front elevation of head pulley
//    which is already covered by the Elevation view.
//
// 7. NEW: 'Bucket Detail' 5th view — engineering drawing of the selected
//    CEMA bucket series showing front elevation + side profile with
//    all key dimensions, bolt positions, volume calculation.

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

// CEMA bucket series catalog dimensions
const BUCKET_CATALOG = {
  AA: { W:305, H:203, P:190, V:7.4,  backR:160, lipH:18, boltSpacW:220, boltSpacH:140 },
  A:  { W:254, H:178, P:165, V:5.0,  backR:140, lipH:15, boltSpacW:180, boltSpacH:120 },
  B:  { W:203, H:152, P:140, V:3.3,  backR:115, lipH:13, boltSpacW:145, boltSpacH:100 },
  C:  { W:152, H:127, P:115, V:1.9,  backR: 95, lipH:11, boltSpacW:108, boltSpacH: 85 },
  D:  { W:102, H: 89, P: 89, V:0.77, backR: 70, lipH: 9, boltSpacW: 72, boltSpacH: 60 },
  MF: { W:254, H:152, P:152, V:4.0,  backR:120, lipH:14, boltSpacW:180, boltSpacH:105 },
  PF: { W:305, H:203, P:178, V:6.5,  backR:160, lipH:16, boltSpacW:220, boltSpacH:140 },
  HF: { W:356, H:254, P:229, V:11.2, backR:200, lipH:22, boltSpacW:260, boltSpacH:175 },
};

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
      {/* Clip path for casing area — keeps animated buckets inside */}
      {clipId && (
        <clipPath id={clipId}>
          <rect x={clipX} y={clipY} width={clipW} height={clipH} />
        </clipPath>
      )}
      <style>{`
        /* FIXED: positive dashoffset → dashes move in REVERSE of path direction */
        /* Path is drawn top→bottom, so +ve offset moves dashes UP (carry side) */
        @keyframes beltUp   { from{stroke-dashoffset:40}  to{stroke-dashoffset:0}  }
        @keyframes beltDown { from{stroke-dashoffset:-40} to{stroke-dashoffset:0}  }
        /* Bucket scroll — translates downward by 1 spacing then loops */
        @keyframes bucketsUp {
          from { transform: translateY(0px);   }
          to   { transform: translateY(-52px); }
        }
        @keyframes bucketsDown {
          from { transform: translateY(0px);  }
          to   { transform: translateY(52px); }
        }
        .belt-carry  { animation: beltUp   1.4s linear infinite; stroke-dasharray:14 6; }
        .belt-return { animation: beltDown 1.4s linear infinite; stroke-dasharray:10 8; }
        .buckets-carry  { animation: bucketsUp   1.4s linear infinite; }
        .buckets-return { animation: bucketsDown 1.4s linear infinite; }
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
        BUCKET: {bkt.id??'—'}×{bkt.W??'—'} {bkt.W??'—'}×{bkt.H??'—'}mm · H = {inp.H_m??'—'} m
      </text>
      <text x={bx+4} y={by+41} fontSize={7} fill={C.text3}>{view.toUpperCase()} VIEW</text>
      <text x={bx+104} y={by+41} fontSize={7} fill={C.text3}>D = {inp.D_mm??'—'} mm</text>
      <text x={bx+4} y={by+52} fontSize={6} fill={C.label}>AKSHAYVIPRA EL-MEC · VECTRIX™</text>
    </g>
  );
}

// Dimension helper: horizontal or vertical with witness lines
function Dim({ x1,y1, x2,y2, label, offset=16, fontSize=8.5, side="positive" }) {
  const isVert = Math.abs(x1-x2)<2;
  const isHorz = Math.abs(y1-y2)<2;
  const sgn = side==="positive"?1:-1;
  if (isVert) {
    // vertical dim — offset to the left/right
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

// ─── ELEVATION VIEW (fixed belt direction + animated buckets) ─────────────────
function ElevationView({ inputs, results, W, H, hovered, setHovered }) {
  const inp=inputs||{}, r=results||{}, bkt=r.bucket||{};
  const margin={top:56,bottom:68,left:52,right:110};
  const cx=W*0.38;
  const headD=Number(inp.D_mm||500), bootD=Number(inp.boot_pulley_D_mm||300);
  const pScale=Math.min(32,W*0.065)/headD;
  const rH=Math.max(14,Math.min(32,headD*pScale));
  const rB=Math.max(10,Math.min(26,bootD*pScale));
  const casW=rH+18;
  const topY=margin.top+rH, botY=H-margin.bottom-rB, elevH=botY-topY;
  const bltL=cx-rH*0.60, bltR=cx+rH*0.60;
  const spacePx=r.spacing ? (r.spacing*(elevH/Math.max(inp.H_m||25,1))) : 52;

  // Bucket geometry (in px, relative to belt line)
  const bktH_px=Math.max(8,Math.min(18, Number(bkt.H||152)/10));
  const bktW_px=Math.max(10,Math.min(20, Number(bkt.W||203)/12));

  // Build an array of buckets that spans MORE than the casing height
  // so the animation loop is seamless
  const nBkts=Math.ceil(elevH/spacePx)+4;
  const carryBuckets=Array.from({length:nBkts},(_,i)=>botY-10-i*spacePx);
  const returnBuckets=Array.from({length:Math.ceil(nBkts/2)},(_,i)=>topY+20+i*spacePx*1.3);

  // Trajectory
  const traj=r.trajectory||[];
  const trajStr=traj.slice(0,30).map((p,i)=>{
    const sx=cx+(p.x-(traj[0]?.x||0))*0.11;
    const sy=topY-(p.y-(traj[0]?.y||0))*0.11;
    return `${i===0?"M":"L"} ${sx.toFixed(1)} ${sy.toFixed(1)}`;
  }).join(" ");

  const callouts={
    head:{title:"HEAD PULLEY",lines:[`D = ${headD} mm`,`n = ${inp.n_rpm??'—'} rpm`,`v = ${f(r.v,3)} m/s`,`Lagged — rubber`]},
    boot:{title:"BOOT PULLEY",lines:[`D = ${bootD} mm`,`K_takeup = ${inp.K_takeup??0.7}`,`T3 = ${f(r.T3!=null?r.T3/1000:null,2)} kN`,`Gravity take-up`]},
    motor:{title:"DRIVE",lines:[`Motor: ${r.motor_kw??'—'} kW`,`P_total: ${f(r.P_total,2)} kW`,`T = ${f(r.T_Nm!=null?r.T_Nm/1000:null,2)} kNm`,`SF = ${inp.sf??'—'}`]},
    bucket:{title:`BUCKET ${bkt.id??'—'}`,lines:[`${bkt.W??'—'}×${bkt.H??'—'}mm P=${bkt.P??'—'}mm`,`V = ${bkt.V??'—'} L`,`Spacing = ${r.spacing?Math.round(r.spacing*1000):'—'} mm`,`Fill: ${inp.fill_pct??'—'}%`]},
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
      {/* Casing centre-line */}
      <line x1={cx} y1={topY-12} x2={cx} y2={botY+12}
        stroke={C.dim} strokeWidth={0.7} strokeDasharray="6 3"/>

      {/* ── Animated belt lines ──
          Path direction: y1(top)→y2(bottom) = top-to-bottom
          Positive dashoffset on beltUp = dashes appear to move UP ── */}
      {/* Carry side (left) — going UP — clockwise */}
      <line className="belt-carry"
        x1={bltL} y1={topY} x2={bltL} y2={botY}
        stroke={C.belt} strokeWidth={3.5}/>
      {/* Return side (right) — going DOWN */}
      <line className="belt-return"
        x1={bltR} y1={topY} x2={bltR} y2={botY}
        stroke={C.beltRtn} strokeWidth={2.5} opacity={0.65}/>

      {/* ── ANIMATED CARRY BUCKETS (clipped to casing) ── */}
      <g clipPath="url(#casingClip)">
        {/* Carry side buckets — move UP with belt */}
        <g className="buckets-carry">
          {carryBuckets.map((by_,i)=>(
            <g key={i}
              onMouseEnter={()=>setHovered("bucket")}
              onMouseLeave={()=>setHovered(null)}
              style={{cursor:"help"}}
            >
              {/* Bucket body — projects LEFT from carry belt */}
              <path d={`
                M ${bltL} ${by_-bktH_px*0.5}
                L ${bltL-bktW_px} ${by_-bktH_px*0.5}
                Q ${bltL-bktW_px-4} ${by_} ${bltL-bktW_px} ${by_+bktH_px*0.5}
                L ${bltL} ${by_+bktH_px*0.5} Z`}
                fill={C.bucket} fillOpacity={0.82}
                stroke={C.casing} strokeWidth={0.8}/>
              {/* Fill indicator (partial fill) */}
              <rect x={bltL-bktW_px+1} y={by_}
                width={bktW_px-4} height={bktH_px*0.35}
                fill={C.belt} fillOpacity={0.3} rx={1}/>
            </g>
          ))}
        </g>

        {/* Return side buckets — inverted, going DOWN, empty */}
        <g className="buckets-return">
          {returnBuckets.map((by_,i)=>(
            <g key={i}>
              {/* Inverted bucket on return side — open end faces DOWN */}
              <path d={`
                M ${bltR} ${by_+bktH_px*0.5}
                L ${bltR+bktW_px} ${by_+bktH_px*0.5}
                Q ${bltR+bktW_px+4} ${by_} ${bltR+bktW_px} ${by_-bktH_px*0.5}
                L ${bltR} ${by_-bktH_px*0.5} Z`}
                fill={C.bucket} fillOpacity={0.25}
                stroke={C.casing} strokeWidth={0.7}/>
            </g>
          ))}
        </g>
      </g>

      {/* ── Boot pulley ── */}
      <g onMouseEnter={()=>setHovered("boot")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <circle cx={cx} cy={botY} r={rB} fill={C.pulley} fillOpacity={0.85} stroke={C.hub} strokeWidth={2}/>
        <circle cx={cx} cy={botY} r={rB*0.3} fill={C.hub}/>
        <line x1={cx-rB-18} y1={botY} x2={cx-rB} y2={botY} stroke={C.dim} strokeWidth={3} strokeLinecap="round"/>
        <line x1={cx+rB} y1={botY} x2={cx+rB+18} y2={botY} stroke={C.dim} strokeWidth={3} strokeLinecap="round"/>
      </g>
      {/* Take-up weight */}
      <rect x={cx-10} y={botY+rB+4} width={20} height={20}
        fill={C.casing} stroke={C.dim} strokeWidth={1} rx={2}/>
      <text x={cx} y={botY+rB+16} fontSize={6.5} fill={C.text3} textAnchor="middle" fontWeight="700">T/U</text>
      <line x1={cx} y1={botY+rB+2} x2={cx} y2={botY+rB+4} stroke={C.dim} strokeWidth={1}/>

      {/* ── Head pulley ── */}
      <g onMouseEnter={()=>setHovered("head")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        <circle cx={cx} cy={topY} r={rH+3} fill="none" stroke={C.lagging} strokeWidth={4} opacity={0.55}/>
        <circle cx={cx} cy={topY} r={rH} fill={C.pulley} fillOpacity={0.85} stroke={C.hub} strokeWidth={2}/>
        {[-1,0,1].map(k=>(
          <line key={k} x1={cx+k*rH*0.38} y1={topY-rH*0.82} x2={cx+k*rH*0.38} y2={topY+rH*0.82}
            stroke={C.hub} strokeWidth={0.9} opacity={0.4}/>
        ))}
        <circle cx={cx} cy={topY} r={rH*0.28} fill={C.hub}/>
        <line x1={cx-rH-20} y1={topY} x2={cx-rH} y2={topY} stroke={C.dim} strokeWidth={4} strokeLinecap="round"/>
        <line x1={cx+rH} y1={topY} x2={cx+rH+20} y2={topY} stroke={C.dim} strokeWidth={4} strokeLinecap="round"/>
      </g>

      {/* ── Discharge chute — MOVED RIGHT to avoid crowding ── */}
      <path d={`M ${cx+rH+2} ${topY-8}
                L ${cx+rH+44} ${topY-26}
                L ${cx+rH+58} ${topY-10}
                L ${cx+rH+16} ${topY+6} Z`}
        fill="rgba(245,158,11,.07)" stroke={C.chute} strokeWidth={1.5}/>
      {/* Discharge label far right — no overlap */}
      <text x={cx+rH+64} y={topY-22} fontSize={7.5} fill={C.chute} fontWeight="700">DISCHARGE</text>
      <text x={cx+rH+64} y={topY-12} fontSize={7} fill={C.label}>CHUTE</text>

      {/* ── Drive train — moved down and spaced out ── */}
      <g onMouseEnter={()=>setHovered("motor")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        {/* Drive shaft */}
        <line x1={cx+rH+20} y1={topY} x2={cx+casW+8} y2={topY}
          stroke={C.dim} strokeWidth={1.5} strokeDasharray="4 2"/>
        {/* Coupling disc */}
        <ellipse cx={cx+casW+16} cy={topY} rx={5} ry={8}
          fill={C.coupling} stroke={C.hub} strokeWidth={1}/>
        {/* Gearbox */}
        <rect x={cx+casW+21} y={topY-12} width={22} height={24}
          fill={C.gearbox} fillOpacity={0.75} stroke="#047857" strokeWidth={1} rx={2}/>
        <text x={cx+casW+32} y={topY+4} fontSize={7} fill="white" textAnchor="middle" fontWeight="700">GB</text>
        {/* Motor */}
        <rect x={cx+casW+43} y={topY-10} width={28} height={20}
          fill={C.motor} fillOpacity={0.8} stroke="#065f46" strokeWidth={1} rx={2}/>
        <text x={cx+casW+57} y={topY+3} fontSize={8} fill="white" textAnchor="middle" fontWeight="700">M</text>
        {/* Motor label BELOW the boxes — no overlap */}
        <text x={cx+casW+40} y={topY+22} fontSize={7} fill={C.text3}>
          {r.motor_kw??'—'} kW
        </text>
        <text x={cx+casW+40} y={topY+31} fontSize={7} fill={C.label}>
          DH = {headD} mm
        </text>
      </g>

      {/* ── Feed inlet ── */}
      <line x1={cx-casW-34} y1={botY} x2={cx-casW-4} y2={botY}
        stroke={C.feed} strokeWidth={2} markerEnd="url(#arr)"/>
      <text x={cx-casW-38} y={botY-5} fontSize={7.5} fill={C.feed} textAnchor="end" fontWeight="700">FEED</text>

      {/* ── Dimension lines ── */}
      <Dim x1={cx-casW-4} y1={botY} x2={cx-casW-4} y2={topY}
        label={`H = ${f(inp.H_m,0)} m`} offset={24} side="negative"/>

      {/* Belt width */}
      <Dim x1={bltL} y1={topY-rH-6} x2={bltR} y2={topY-rH-6}
        label={`BW = ${r.belt_w??'—'} mm`} offset={16} side="positive"/>

      {/* Bucket spacing */}
      {spacePx>14 && (
        <Dim x1={cx+casW+8} y1={botY-10} x2={cx+casW+8} y2={botY-10-spacePx}
          label={`${r.spacing?Math.round(r.spacing*1000):'—'}mm`} offset={20} side="positive"/>
      )}

      {/* Head / Boot labels */}
      <text x={cx} y={10} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700" letterSpacing=".06em">HEAD SECTION</text>
      <text x={cx} y={21} fontSize={7} fill={C.label} textAnchor="middle">Ø{headD}mm · {inp.n_rpm??'—'}rpm · Lagged</text>

      <text x={cx} y={botY+rB+36} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700" letterSpacing=".06em">BOOT / TAKE-UP</text>
      <text x={cx} y={botY+rB+46} fontSize={7} fill={C.label} textAnchor="middle">Ø{headD}mm · Gravity</text>

      {/* DB label — boot, right side only */}
      <text x={cx+rB+6} y={botY+4} fontSize={7.5} fill={C.text3}>DB = {headD} mm</text>

      {/* Bucket footer */}
      <text x={W/2} y={H-6} fontSize={7.5} fill={C.label} textAnchor="middle">
        BUCKET {bkt.id??'—'} · {bkt.W??'—'}×{bkt.H??'—'}mm · {bkt.V??'—'}L · SPACING {r.spacing?Math.round(r.spacing*1000):'—'}mm
      </text>

      {/* Callout */}
      {co && <Callout x={cx+casW+10} y={H/2} title={co.title} lines={co.lines} W={W} H={H}/>}
      <TitleBlock W={W} H={H} view="elevation" inputs={inputs} results={results}/>
    </svg>
  );
}

// ─── HEAD SECTION PLAN VIEW (corrected — cylinder = rectangle from above) ────
function PlanView({ inputs, results, W, H, hovered, setHovered }) {
  const r=results||{}, inp=inputs||{};
  const BW=Number(r.belt_w??inp.D_mm??300);
  const D=Number(inp.D_mm??500);
  const dShaft=Number(r.d_mm??60);
  // Casing width = BW + 120mm clearance each side
  const CW=BW+120;
  // Pulley face length = BW + 50mm end clearance each side  
  const PL=BW+50;
  // Casing depth (front to back) = 400mm typical
  const CD=400;

  const scale=Math.min((W-120)/CW, (H-120)/(CD+60));
  const cw=CW*scale, cd=CD*scale, pl=PL*scale, bw=BW*scale;
  const cx=W/2, cy=H/2+10;

  // Shaft diameter in plan
  const dSh=dShaft*scale;
  const bh=26*scale, bhW=22*scale; // bearing housing

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

      {/* ── Casing outer walls (plan view = rectangles) ── */}
      <g onMouseEnter={()=>setHovered("casing")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        {/* Full casing outline */}
        <rect x={cx-cw/2} y={cy-cd/2} width={cw} height={cd}
          fill={C.casFill} stroke={C.casing} strokeWidth={2} rx={2}/>
        {/* Casing plate thickness (8mm each side — shown as inner line) */}
        <rect x={cx-cw/2+8*scale} y={cy-cd/2+8*scale}
          width={cw-16*scale} height={cd-16*scale}
          fill="none" stroke={C.casing} strokeWidth={0.5} strokeDasharray="3 2"/>
      </g>

      {/* ── Pulley in plan = RECTANGLE (shell of a cylinder from above) ── */}
      <g onMouseEnter={()=>setHovered("head")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
        {/* Lagging (slightly wider rectangle) */}
        <rect x={cx-pl/2-5*scale} y={cy-D*scale/2-6*scale}
          width={pl+10*scale} height={D*scale+12*scale}
          fill="none" stroke={C.lagging} strokeWidth={3.5} opacity={0.6} rx={2}/>
        {/* Pulley shell */}
        <rect x={cx-pl/2} y={cy-D*scale/2}
          width={pl} height={D*scale}
          fill={C.pulley} fillOpacity={0.75} stroke={C.hub} strokeWidth={1.5} rx={2}/>
        {/* Shell weld seams (vertical lines across face) */}
        {[-0.3,0,0.3].map(k=>(
          <line key={k} x1={cx+k*pl*0.35} y1={cy-D*scale/2}
            x2={cx+k*pl*0.35} y2={cy+D*scale/2}
            stroke={C.hub} strokeWidth={0.8} opacity={0.4}/>
        ))}
        {/* Shaft (rectangle in plan = shaft diameter × shaft length) */}
        <rect x={cx-cw/2-bhW-10} y={cy-dSh/2}
          width={cw+2*(bhW+10)} height={dSh}
          fill={C.dim} rx={1} opacity={0.7}/>
        {/* Shaft centre-line */}
        <line x1={cx-cw/2-bhW-20} y1={cy} x2={cx+cw/2+bhW+20} y2={cy}
          stroke={C.dimTxt} strokeWidth={0.8} strokeDasharray="6 3"/>
      </g>

      {/* ── Belt edges (two lines through casing) ── */}
      <line x1={cx-bw/2} y1={cy-cd/2-10} x2={cx-bw/2} y2={cy+cd/2+10}
        stroke={C.belt} strokeWidth={2}/>
      <line x1={cx+bw/2} y1={cy-cd/2-10} x2={cx+bw/2} y2={cy+cd/2+10}
        stroke={C.belt} strokeWidth={2}/>

      {/* ── Bearing housings (left and right) ── */}
      {[-1,1].map(side=>{
        const bx=side<0 ? cx-cw/2-bhW-10 : cx+cw/2+10;
        return (
          <g key={side} onMouseEnter={()=>setHovered("bearings")} onMouseLeave={()=>setHovered(null)} style={{cursor:"help"}}>
            <rect x={bx} y={cy-bh/2} width={bhW} height={bh}
              fill={C.gearbox} fillOpacity={0.5} stroke={C.motor} strokeWidth={1.2} rx={2}/>
            {[-1,1].map(d=>(
              <circle key={d} cx={bx+bhW/2} cy={cy+d*bh*0.34} r={2}
                fill={C.hub} stroke={C.dim} strokeWidth={0.8}/>
            ))}
            <text x={bx+bhW/2} y={side<0?cy-bh/2-5:cy+bh/2+11} fontSize={6.5}
              fill={C.labelBr} textAnchor="middle" fontWeight="700">BRG</text>
          </g>
        );
      })}

      {/* ── Buckets (rectangles in plan — flat projection of bucket face) ── */}
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

      {/* ── Dimension lines ── */}
      <Dim x1={cx-bw/2} y1={cy+cd/2+14} x2={cx+bw/2} y2={cy+cd/2+14}
        label={`BW = ${BW.toFixed(0)} mm`} offset={18}/>
      <Dim x1={cx-cw/2} y1={cy-cd/2-22} x2={cx+cw/2} y2={cy-cd/2-22}
        label={`Casing = ${CW.toFixed(0)} mm`} offset={16}/>
      <Dim x1={cx-pl/2} y1={cy-cd/2-42} x2={cx+pl/2} y2={cy-cd/2-42}
        label={`Pulley face = ${PL.toFixed(0)} mm`} offset={16}/>
      {/* Shaft dia — vertical on far left */}
      <Dim x1={cx-cw/2-bhW-10} y1={cy-dSh/2} x2={cx-cw/2-bhW-10} y2={cy+dSh/2}
        label={`d = ${f(dShaft,0)} mm`} offset={20} side="negative"/>
      {/* Pulley dia — vertical on far right */}
      <Dim x1={cx+cw/2+bhW+22} y1={cy-D*scale/2} x2={cx+cw/2+bhW+22} y2={cy+D*scale/2}
        label={`D = ${D.toFixed(0)} mm`} offset={22}/>

      {/* Callouts */}
      {hovered==="head" && (
        <Callout x={cx+pl/2+10} y={cy-40}
          title="HEAD PULLEY" W={W} H={H}
          lines={[`D = ${D.toFixed(0)} mm`,`Pulley face = ${PL.toFixed(0)} mm`,`Lagged — amber ring`,`Shaft Ø${f(dShaft,0)} mm`]}/>
      )}
      {hovered==="bearings" && (
        <Callout x={cx} y={cy+bh/2+40}
          title="BEARINGS (×2)" W={W} H={H}
          lines={[`L10 = ${r.L10>9999?(r.L10/1000).toFixed(0)+"k":f(r.L10,0)} h`,`Load: ${f(r.R_headshaft!=null?r.R_headshaft/1000:null,2)} kN`,"ISO 281 · C = 355 kN"]}/>
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

// ─── SIDE ELEVATION (complete elevator from 90°) ─────────────────────────────
function SideView({ inputs, results, W, H }) {
  const r=results||{}, inp=inputs||{};
  const CD=400; // casing depth mm (front-to-back)
  const H_m=Number(inp.H_m||25);
  const D=Number(inp.D_mm||500);
  const bootD=Number(inp.boot_pulley_D_mm||300);

  const scale=Math.min((W-80)/( CD+160),(H-80)/(H_m*40+D*0.6));
  const casDepth=CD*scale;
  const elevH_px=H_m*40*scale;
  const rH_px=(D/2)*scale, rB_px=(bootD/2)*scale;
  const cx=W/2, topY=40+rH_px, botY=topY+elevH_px;

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

      {/* ── Casing side elevation (narrow rectangle = depth × height) ── */}
      <rect x={cx-casDepth/2} y={topY} width={casDepth} height={elevH_px}
        fill={C.casFill} stroke={C.casing} strokeWidth={2} rx={2}/>

      {/* ── Leg structure ── */}
      {[-1,1].map(side=>(
        <g key={side}>
          {/* Vertical leg */}
          <rect x={cx+side*(casDepth/2+4)} y={topY+elevH_px*0.15}
            width={10*scale} height={elevH_px*0.85}
            fill={C.leg} stroke={C.dim} strokeWidth={0.8}/>
          {/* Diagonal brace */}
          <line x1={cx+side*(casDepth/2+4+(side>0?10*scale:0))} y1={topY+elevH_px*0.15}
            x2={cx+side*(casDepth/2+8+30*scale)} y2={topY+elevH_px*0.6}
            stroke={C.leg} strokeWidth={1.5} opacity={0.7}/>
        </g>
      ))}

      {/* ── Head pulley side (shows as rectangle = face length × depth) ── */}
      <rect x={cx-casDepth/2-10} y={topY-rH_px/3}
        width={casDepth+20} height={rH_px/1.5}
        fill={C.pulley} fillOpacity={0.6} stroke={C.hub} strokeWidth={1.5} rx={2}/>
      {/* Lagging */}
      <rect x={cx-casDepth/2-14} y={topY-rH_px/3-4}
        width={casDepth+28} height={rH_px/1.5+8}
        fill="none" stroke={C.lagging} strokeWidth={3} opacity={0.5} rx={3}/>

      {/* ── Boot pulley side ── */}
      <rect x={cx-casDepth/2-8} y={botY-rB_px/4}
        width={casDepth+16} height={rB_px/2}
        fill={C.pulley} fillOpacity={0.5} stroke={C.hub} strokeWidth={1} rx={2}/>

      {/* ── Inspection doors ── */}
      {[0.25, 0.55, 0.78].map((frac,i)=>(
        <rect key={i} x={cx-casDepth/4} y={topY+elevH_px*frac}
          width={casDepth/2} height={elevH_px*0.08}
          fill="none" stroke={C.dimTxt} strokeWidth={0.8} strokeDasharray="3 2" rx={1}/>
      ))}

      {/* ── Drive platform (at head level) ── */}
      <rect x={cx+casDepth/2+10} y={topY-20}
        width={50*scale} height={10*scale}
        fill={C.leg} stroke={C.dim} strokeWidth={0.8} opacity={0.7}/>
      <text x={cx+casDepth/2+15+25*scale} y={topY-12} fontSize={7}
        fill={C.label}>DRIVE</text>

      {/* ── Belt (shown as lines on inside of casing) ── */}
      <line x1={cx-casDepth/4} y1={topY} x2={cx-casDepth/4} y2={botY}
        stroke={C.belt} strokeWidth={2} opacity={0.6}/>
      <line x1={cx+casDepth/4} y1={topY} x2={cx+casDepth/4} y2={botY}
        stroke={C.beltRtn} strokeWidth={1.5} opacity={0.4}/>

      {/* ── Dimension lines ── */}
      <Dim x1={cx-casDepth/2-28} y1={topY} x2={cx-casDepth/2-28} y2={botY}
        label={`H = ${f(H_m,0)} m`} offset={24} side="negative"/>
      <Dim x1={cx-casDepth/2} y1={topY-rH_px/3-24} x2={cx+casDepth/2} y2={topY-rH_px/3-24}
        label={`Casing depth = ${CD.toFixed(0)} mm`} offset={18}/>

      {/* Labels */}
      <text x={cx} y={topY-rH_px/3-42} fontSize={8.5} fill={C.labelBr}
        textAnchor="middle" fontWeight="700">HEAD</text>
      <text x={cx} y={botY+rB_px/2+24} fontSize={8.5} fill={C.labelBr}
        textAnchor="middle" fontWeight="700">BOOT / T/U</text>
      <text x={cx+casDepth/2+16} y={topY+elevH_px*0.32} fontSize={7.5}
        fill={C.label}>INSPECTION</text>
      <text x={cx+casDepth/2+16} y={topY+elevH_px*0.32+10} fontSize={7.5}
        fill={C.label}>DOORS</text>

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

  const pad={top:58,bot:46,left:56,right:26};
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
      {[0,.25,.5,.75,1].map(t=>{
        const gx=pad.left+t*pw, gy=pad.top+t*ph;
        const xv=(xMin+t*xR)*1000, yv=(yMax-t*yR)*1000;
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
      <text x={12} y={H/2} fontSize={9} fill={C.labelBr} textAnchor="middle" transform={`rotate(-90,12,${H/2})`}>y [mm]</text>
      <TitleBlock W={W} H={H} view="trajectory" inputs={inputs} results={results}/>
    </svg>
  );
}

// ─── BUCKET DETAIL VIEW (new — Task 11 extra viewport) ───────────────────────
function BucketDetailView({ inputs, results, W, H }) {
  const r=results||{}, bkt=r.bucket||{};
  const seriesId=bkt.id||"B";
  const cat=BUCKET_CATALOG[seriesId]||BUCKET_CATALOG.B;

  // Use catalog values over API values where available
  const bW=cat.W, bH=cat.H, bP=cat.P, bV=cat.V;
  const scale=Math.min((W-120)/(bW+bP+80),(H-120)/(bH+60));
  const bWs=bW*scale, bHs=bH*scale, bPs=bP*scale;
  const backR=cat.backR*scale;

  // Left panel: front elevation; Right panel: side profile
  const fCx=W*0.30, sCx=W*0.72;
  const midY=H*0.48;

  // Front elevation — bucket face view (W × H rectangle with curved back)
  const fX=fCx-bWs/2, fY=midY-bHs/2;
  // Back plate curve path
  const backPath=`
    M ${fX} ${fY+bHs}
    L ${fX} ${fY}
    Q ${fX-backR*0.4} ${midY} ${fX} ${fY+bHs} Z`;

  // Bucket fill level (75% full)
  const fillPct=Number(inputs?.fill_pct||75)/100;
  const fillY=fY+bHs*(1-fillPct*0.7);

  // Side profile — projection P, height H
  const sX=sCx-bPs/2, sY=midY-bHs/2;
  // Side profile path: back plate (left) → bottom → lip (right, shorter)
  const sidePath=`
    M ${sX} ${sY+bHs}
    Q ${sX-8} ${sY+bHs*0.5} ${sX} ${sY}
    L ${sX+bPs} ${sY+bHs*0.15}
    L ${sX+bPs} ${sY+bHs*0.85}
    L ${sX} ${sY+bHs} Z`;

  // Bolt positions
  const boltSW=cat.boltSpacW*scale, boltSH=cat.boltSpacH*scale;
  const bolts=[
    {x:fCx-boltSW/2, y:midY-boltSH/2},
    {x:fCx+boltSW/2, y:midY-boltSH/2},
    {x:fCx-boltSW/2, y:midY+boltSH/2},
    {x:fCx+boltSW/2, y:midY+boltSH/2},
  ];

  // Material volume calc
  const V_actual=(bV*(Number(inputs?.fill_pct||75)/100)).toFixed(3);
  const mass_bucket=(bV*1.5).toFixed(1);
  const n_buckets=r.spacing?Math.ceil((2*Number(inputs?.H_m||25))/r.spacing):0;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{display:"block"}}>
      <Defs/>
      <rect width={W} height={H} fill={C.bg}/>
      <Grid W={W} H={H}/>

      <text x={W/2} y={18} fontSize={10} fill={C.text3} textAnchor="middle" fontWeight="700" letterSpacing=".06em">
        BUCKET SERIES {seriesId} — CEMA STANDARD
      </text>
      <text x={W/2} y={30} fontSize={7.5} fill={C.label} textAnchor="middle">
        Front Elevation (left)  ·  Side Profile (right)
      </text>

      {/* ─── FRONT ELEVATION ─── */}
      {/* Back plate fill */}
      <rect x={fX} y={fY} width={bWs} height={bHs}
        fill={C.casFill} stroke={C.bucket} strokeWidth={1.5}/>
      {/* Back curve highlight */}
      <path d={`M ${fX} ${fY} Q ${fX-backR*0.35} ${midY} ${fX} ${fY+bHs}`}
        fill="none" stroke={C.lagging} strokeWidth={2} opacity={0.7}/>
      {/* Material fill (at set fill%) */}
      <rect x={fX+1} y={fillY} width={bWs-2} height={fY+bHs-fillY-1}
        fill={C.belt} fillOpacity={0.2} rx={1}/>
      {/* Fill level line */}
      <line x1={fX+1} y1={fillY} x2={fX+bWs-1} y2={fillY}
        stroke={C.belt} strokeWidth={1} strokeDasharray="3 2" opacity={0.7}/>
      {/* Mounting bolts */}
      {bolts.map((b,i)=>(
        <g key={i}>
          <circle cx={b.x} cy={b.y} r={3.5} fill={C.dim} stroke={C.dimTxt} strokeWidth={1}/>
          <line x1={b.x-3} y1={b.y} x2={b.x+3} y2={b.y} stroke={C.dimTxt} strokeWidth={0.6}/>
          <line x1={b.x} y1={b.y-3} x2={b.x} y2={b.y+3} stroke={C.dimTxt} strokeWidth={0.6}/>
        </g>
      ))}
      {/* Centre line */}
      <line x1={fCx} y1={fY-8} x2={fCx} y2={fY+bHs+8}
        stroke={C.dim} strokeWidth={0.7} strokeDasharray="5 3"/>

      <text x={fCx} y={fY-14} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700">
        FRONT ELEVATION
      </text>

      {/* W dimension */}
      <Dim x1={fX} y1={fY+bHs+14} x2={fX+bWs} y2={fY+bHs+14}
        label={`W = ${bW} mm`} offset={16}/>
      {/* H dimension */}
      <Dim x1={fX-20} y1={fY} x2={fX-20} y2={fY+bHs}
        label={`H = ${bH} mm`} offset={22} side="negative"/>
      {/* Bolt spacing W */}
      <Dim x1={fCx-boltSW/2} y1={fY-26} x2={fCx+boltSW/2} y2={fY-26}
        label={`${cat.boltSpacW} mm`} offset={14}/>

      {/* ─── SIDE PROFILE ─── */}
      <path d={sidePath} fill={C.casFill} stroke={C.bucket} strokeWidth={1.5}/>
      {/* Back plate curve side */}
      <path d={`M ${sX} ${sY} Q ${sX-10} ${sY+bHs*0.5} ${sX} ${sY+bHs}`}
        fill="none" stroke={C.lagging} strokeWidth={2} opacity={0.7}/>
      {/* Lip indicator */}
      <line x1={sX+bPs} y1={sY+bHs*0.15} x2={sX+bPs} y2={sY+bHs*0.85}
        stroke={C.primary} strokeWidth={2.5} opacity={0.8}/>
      {/* Mounting holes (side view) */}
      {[0.3,0.65].map((f_,i)=>(
        <ellipse key={i} cx={sX+8} cy={sY+bHs*f_} rx={3} ry={2}
          fill={C.dim} stroke={C.dimTxt} strokeWidth={0.8}/>
      ))}

      <text x={sCx} y={sY-14} fontSize={9} fill={C.labelBr} textAnchor="middle" fontWeight="700">
        SIDE PROFILE
      </text>

      {/* P dimension */}
      <Dim x1={sX} y1={sY+bHs+14} x2={sX+bPs} y2={sY+bHs+14}
        label={`P = ${bP} mm`} offset={16}/>
      {/* H dimension (side) */}
      <Dim x1={sX+bPs+20} y1={sY} x2={sX+bPs+20} y2={sY+bHs}
        label={`H = ${bH} mm`} offset={22}/>

      {/* Lip label */}
      <text x={sX+bPs+6} y={sY+bHs*0.5} fontSize={7.5} fill={C.primary} fontWeight="700">LIP</text>

      {/* ─── Specification table ─── */}
      {[
        [`Series ${seriesId}`,  `CEMA Standard`],
        [`W × H × P`,           `${bW} × ${bH} × ${bP} mm`],
        [`Struck capacity`,     `${bV} L`],
        [`Active volume`,       `${V_actual} L (${inputs?.fill_pct??75}% fill)`],
        [`Bucket mass (est.)`,  `${mass_bucket} kg`],
        [`Total buckets`,       n_buckets ? `${n_buckets} EA` : "—"],
        [`Bolt pattern`,        `${cat.boltSpacW} × ${cat.boltSpacH} mm`],
        [`Mounting`,            `4× M12 gr8.8`],
      ].map(([k,v],i)=>(
        <g key={i}>
          <rect x={14} y={H-130+i*14} width={180} height={14}
            fill={i%2===0?"rgba(59,130,246,.05)":"transparent"}/>
          <text x={18} y={H-120+i*14} fontSize={8} fill={C.text3}>{k}</text>
          <text x={130} y={H-120+i*14} fontSize={8} fill={C.labelBr}
            fontFamily="JetBrains Mono,monospace" fontWeight="600">{v}</text>
        </g>
      ))}
      <rect x={12} y={H-133} width={184} height={116}
        fill="none" stroke={C.dim} strokeWidth={0.8} rx={3}/>
      <text x={104} y={H-140} fontSize={8.5} fill={C.text3} textAnchor="middle"
        fontWeight="700" letterSpacing=".05em">BUCKET SPECIFICATION</text>

      {/* Fill level label */}
      <text x={fX+bWs+4} y={fillY} fontSize={7} fill={C.belt}>
        {inputs?.fill_pct??75}%
      </text>

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

  return (
    <div style={{
      width:"100%",height:"100%",
      display:"flex",flexDirection:"column",
      background:C.bg,overflow:"hidden",
      userSelect:"none",position:"relative",
    }}>
      {/* Tab bar */}
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

      {/* KPI pills — fixed field names */}
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

      {/* Pan/zoom canvas */}
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
            inputs={inputs} results={results}
            W={SVG_W} H={SVG_H}
            hovered={hovered} setHovered={setHovered}
          />
        </div>
      </div>

      {/* Status bar */}
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
