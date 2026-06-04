// ElevatorSchematic.jsx — live SVG cross-section diagram
// Fixed: null guard moved to before ALL results access (was after some inline uses)
// Fixed: C.blue and C.red added to color object (were missing after Task 1 patch)

const C = {
  bg:      "#0f172a",   panel:   "#162032",   panel2:  "#1e293b",
  hi:      "#243247",   border:  "#ffffff12",  border2: "#ffffff1e",
  text:    "#f1f5f9",   muted:   "#64748b",   muted2:  "#94a3b8",
  faint:   "#3d536b",
  primary: "#3b82f6",   brand:   "#c8192e",   green:   "#10b981",
  amber:   "#f59e0b",   teal:    "#14b8a6",   danger:  "#ef4444",
  // explicit aliases used in bucket fill rendering
  blue:    "#3b82f6",   red:     "#ef4444",
};

export default function ElevatorSchematic({ inputs, results }) {
  // Guard: results AND results.bucket must exist before any access
  if (!results || !results.bucket || !results.trajectory) return null;

  const W = 420, H = 480;
  const cx = W / 2;
  const bootY = 420, headY = 60;
  const casingW = 80, casingHalf = casingW / 2;
  const pulleyR = 28;
  const beltL = cx - 18, beltR = cx + 18;

  const nBuckets = 6;
  const bucketH = Math.max(12, Math.min(22, results.bucket.H / 10));
  const bucketW = Math.max(16, Math.min(32, results.bucket.W / 9));

  const buckets = Array.from({ length: nBuckets }, (_, i) => {
    const frac = i / (nBuckets - 1);
    const by = bootY - 60 + (headY + 60 - (bootY - 60)) * frac;
    return { x: beltR - 2, y: by };
  });

  // Discharge trajectory scaled to schematic
  const trajScale = 0.12;
  const trajOriginX = cx + pulleyR;
  const trajOriginY = headY;
  const trajPts = (results.trajectory || []).map((p) => ({
    x: trajOriginX + p.x * trajScale,
    y: trajOriginY - p.y * trajScale,
  }));
  const trajPath = trajPts.map((p, i) =>
    `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`
  ).join(" ");

  const speedOK = results.v >= 0.5 && results.v <= 2.5;
  const capOK   = results.Q >= inputs.Q_req;
  // Safe numeric values with fallbacks
  const theta   = results.theta_rel != null ? Number(results.theta_rel).toFixed(0) : "—";
  const speed   = results.v       != null ? Number(results.v).toFixed(2)       : "—";
  const cap     = results.Q       != null ? Number(results.Q).toFixed(0)        : "—";
  const spacing = results.spacing != null ? (results.spacing * 1000).toFixed(0) : "—";

  return (
    <svg width={W} height={H} style={{ display: "block", margin: "0 auto" }}>
      <rect width={W} height={H} fill={C.panel2} />

      {/* Grid lines */}
      {[100, 200, 300, 400].map((y) => (
        <line key={y} x1={0} y1={y} x2={W} y2={y}
          stroke={C.border} strokeWidth={0.5} strokeDasharray="4,6" />
      ))}

      {/* Height label */}
      <text x={20} y={(headY + bootY) / 2} fill={C.muted} fontSize={9}
        fontFamily="JetBrains Mono" textAnchor="middle"
        transform={`rotate(-90,20,${(headY + bootY) / 2})`}>
        H = {inputs.H_m} m
      </text>
      <line x1={28} y1={headY} x2={28} y2={bootY} stroke={C.faint} strokeWidth={1} strokeDasharray="3,4" />
      <line x1={24} y1={headY} x2={32} y2={headY} stroke={C.faint} strokeWidth={1} />
      <line x1={24} y1={bootY} x2={32} y2={bootY} stroke={C.faint} strokeWidth={1} />

      {/* Casing outer */}
      <rect x={cx - casingHalf - 6} y={headY + pulleyR}
        width={casingW + 12} height={bootY - headY - pulleyR * 2}
        fill="none" stroke={C.border2} strokeWidth={2} rx={2} />

      {/* Casing inner */}
      <rect x={cx - casingHalf} y={headY + pulleyR + 8}
        width={casingW} height={bootY - headY - pulleyR * 2 - 16}
        fill="rgba(22,32,50,.7)" stroke={C.border} strokeWidth={1} rx={1} />

      {/* Belt return side */}
      <line x1={beltL} y1={headY + pulleyR} x2={beltL} y2={bootY - pulleyR}
        stroke={C.muted} strokeWidth={4} strokeLinecap="round" opacity={0.4} />

      {/* Belt carry side — green=ok, amber=speed warning */}
      <line x1={beltR} y1={headY + pulleyR} x2={beltR} y2={bootY - pulleyR}
        stroke={speedOK ? C.green : C.amber} strokeWidth={4} strokeLinecap="round" opacity={0.85} />

      {/* Head pulley */}
      <circle cx={cx} cy={headY} r={pulleyR} fill={C.hi} stroke={C.border2} strokeWidth={2} />
      <circle cx={cx} cy={headY} r={pulleyR * 0.55} fill="none" stroke={C.faint} strokeWidth={1} />
      <circle cx={cx} cy={headY} r={4} fill={C.brand} />
      <text x={cx + pulleyR + 8} y={headY - 10} fill={C.muted2}
        fontSize={9} fontFamily="Inter, sans-serif" fontWeight={700}>HEAD</text>
      <text x={cx + pulleyR + 8} y={headY + 2}
        fill={C.muted} fontSize={8} fontFamily="JetBrains Mono">Ø{inputs.D_mm}mm</text>
      <text x={cx + pulleyR + 8} y={headY + 13}
        fill={C.muted} fontSize={8} fontFamily="JetBrains Mono">{inputs.n_rpm}RPM</text>

      {/* Boot pulley */}
      <circle cx={cx} cy={bootY} r={pulleyR * 0.8} fill={C.hi} stroke={C.border} strokeWidth={2} />
      <circle cx={cx} cy={bootY} r={3} fill={C.muted} />
      <text x={cx + pulleyR + 4} y={bootY + 4}
        fill={C.muted} fontSize={9} fontFamily="Inter, sans-serif" fontWeight={700}>BOOT</text>

      {/* Take-up */}
      <rect x={cx - pulleyR * 0.8 - 4} y={bootY + 24}
        width={(pulleyR * 0.8 + 4) * 2} height={8}
        fill="none" stroke={C.faint} strokeWidth={1} strokeDasharray="3,3" />
      <text x={cx} y={bootY + 40} fill={C.faint}
        fontSize={8} fontFamily="Inter, sans-serif" textAnchor="middle">TAKE-UP</text>

      {/* Discharge spout */}
      <path d={`M ${cx + pulleyR} ${headY - 10} L ${cx + pulleyR + 40} ${headY - 25}
        L ${cx + pulleyR + 50} ${headY - 10} L ${cx + pulleyR + 10} ${headY}`}
        fill="rgba(245,158,11,.1)" stroke={C.amber} strokeWidth={1.5} opacity={0.8} />
      <text x={cx + pulleyR + 52} y={headY - 18}
        fill={C.amber} fontSize={9} fontFamily="Inter, sans-serif" fontWeight={700}>DISCHARGE</text>

      {/* Feed inlet */}
      <path d={`M ${cx - casingHalf - 6} ${bootY - 10}
        L ${cx - casingHalf - 30} ${bootY + 15}
        L ${cx - casingHalf - 30} ${bootY + 30}
        L ${cx - casingHalf + 10} ${bootY + 30}
        L ${cx - casingHalf + 10} ${bootY + 10}`}
        fill="rgba(16,185,129,.08)" stroke={C.green} strokeWidth={1.5} opacity={0.8} />
      <text x={cx - casingHalf - 34} y={bootY + 44}
        fill={C.green} fontSize={9} fontFamily="Inter, sans-serif" fontWeight={700}>FEED INLET</text>

      {/* Buckets — blue=capacity ok, red=fail */}
      {buckets.map((b, i) => (
        <g key={i} transform={`translate(${b.x},${b.y})`}>
          <rect x={0} y={-bucketH / 2} width={bucketW} height={bucketH}
            fill={capOK ? "rgba(59,130,246,.2)" : "rgba(239,68,68,.2)"}
            stroke={capOK ? C.blue : C.red} strokeWidth={1} rx={2} />
          <rect x={2} y={0} width={bucketW - 4} height={bucketH / 2 - 2}
            fill={capOK ? "rgba(59,130,246,.4)" : "rgba(239,68,68,.4)"} rx={1} />
        </g>
      ))}

      {/* Discharge trajectory */}
      {trajPts.length > 2 && (
        <path d={trajPath} fill="none"
          stroke={C.teal} strokeWidth={1.5} strokeDasharray="4,3" opacity={0.7} />
      )}

      {/* Trajectory angle label — uses safe 'theta' string */}
      <text x={trajOriginX + 5} y={headY - 35}
        fill={C.teal} fontSize={9} fontFamily="JetBrains Mono" opacity={0.8}>
        θ={theta}°
      </text>

      {/* Speed indicator */}
      <rect x={W - 80} y={10} width={70} height={38} fill={C.hi} stroke={C.border2} rx={4} />
      <text x={W - 45} y={24} fill={C.muted} fontSize={8}
        fontFamily="Inter, sans-serif" fontWeight={700} textAnchor="middle">BELT SPEED</text>
      <text x={W - 45} y={40}
        fill={speedOK ? C.green : C.amber} fontSize={14}
        fontFamily="JetBrains Mono" fontWeight={700} textAnchor="middle">
        {speed}
      </text>
      <text x={W - 10} y={40} fill={C.muted} fontSize={8} fontFamily="JetBrains Mono">m/s</text>

      {/* Capacity indicator */}
      <rect x={W - 80} y={54} width={70} height={38}
        fill={C.hi} stroke={capOK ? C.border2 : "rgba(239,68,68,.4)"} rx={4} />
      <text x={W - 45} y={68} fill={C.muted} fontSize={8}
        fontFamily="Inter, sans-serif" fontWeight={700} textAnchor="middle">CAPACITY</text>
      <text x={W - 45} y={84}
        fill={capOK ? C.green : C.red} fontSize={14}
        fontFamily="JetBrains Mono" fontWeight={700} textAnchor="middle">
        {cap}
      </text>
      <text x={W - 12} y={84} fill={C.muted} fontSize={7} fontFamily="JetBrains Mono">t/h</text>

      {/* Bucket footer label */}
      <text x={cx} y={H - 10} fill={C.muted}
        fontSize={9} fontFamily="Inter, sans-serif" fontWeight={600} textAnchor="middle">
        BUCKET {results.bucket.id} — {results.bucket.W}×{results.bucket.H}mm
        — {results.bucket.V}L — SPACING {spacing}mm
      </text>
    </svg>
  );
}
