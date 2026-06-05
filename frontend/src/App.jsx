// App.jsx — VECTRIX™ Design Platform shell
// Task 3: Premium pill-style module switcher
// Fixed: PDF button colors use new token system
// Fixed: badge uses --primary-dim not old red rgba
import { useState } from "react";
import BucketElevatorPage from "./BucketElevatorPage";
import "./tokens.css";

// ── SVG icons for each module (crisp at 16px) ─────────────────────────────
const ICONS = {
  bucket_elevator: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <rect x="9" y="2" width="6" height="5" rx="1"/>
      <line x1="12" y1="7" x2="12" y2="22"/>
      <line x1="8"  y1="22" x2="16" y2="22"/>
      <circle cx="12" cy="19" r="2"/>
      <line x1="5"  y1="10" x2="9"  y2="10"/>
      <line x1="15" y1="10" x2="19" y2="10"/>
    </svg>
  ),
  screw_conveyor: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M6 8 Q9 12 6 16"/>
      <path d="M10 8 Q13 12 10 16"/>
      <path d="M14 8 Q17 12 14 16"/>
      <circle cx="22" cy="12" r="2"/>
      <circle cx="2"  cy="12" r="2"/>
    </svg>
  ),
};

function ScrewConveyorPage() {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      flex: 1, flexDirection: "column", gap: 14,
      color: "var(--text3)", fontSize: 13, fontFamily: "var(--ff-ui)",
    }}>
      <div style={{ opacity: .4, color: "var(--primary)" }}>{ICONS.screw_conveyor}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text2)",
        letterSpacing: ".04em", textTransform: "uppercase" }}>
        Screw Conveyor Module
      </div>
      <div style={{ color: "var(--text3)", fontSize: 12 }}>
        Your existing screw conveyor design platform renders here.
      </div>
    </div>
  );
}

const MODULES = [
  {
    id:    "bucket_elevator",
    label: "Bucket Elevator",
    badge: "VECTOMEC™",
    desc:  "Centrifugal & continuous bucket design",
  },
  {
    id:    "screw_conveyor",
    label: "Screw Conveyor",
    badge: null,
    desc:  "Helical screw conveyor design",
  },
];

async function downloadReport(results, inputs) {
  if (!results) return;
  const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000") + "/api";
  try {
    const res = await fetch(`${BASE}/bucket-elevator/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results, inputs,
        project: inputs?.project ?? "", ref: inputs?.ref ?? "" }),
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "elevator_report.pdf"; a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Report generation failed: ${e.message}`);
  }
}

export default function App() {
  const [module, setModule]                   = useState("bucket_elevator");
  const [elevatorSnapshot, setElevatorSnapshot] = useState({ results: null, inputs: {} });

  return (
    <div className="app-shell">

      {/* ═══════════════════════════════════════════════════
          PLATFORM TOP BAR
          Left:  VECTRIX™ wordmark
          Centre: pill module tabs
          Right:  PDF button + version tag
          ═══════════════════════════════════════════════════ */}
      <div style={{
        height: 52,
        display: "flex",
        alignItems: "center",
        gap: 0,
        padding: "0 16px",
        background: "var(--overlay)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
        userSelect: "none",
        zIndex: 200,
      }}>

        {/* Wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 20 }}>
          <div style={{
            width: 30, height: 30, borderRadius: "var(--r-sm)",
            background: "var(--brand)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, flexShrink: 0,
            boxShadow: "0 2px 8px rgba(200,25,46,.35)",
          }}>⚙</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, letterSpacing: ".02em",
              color: "var(--text)", fontFamily: "var(--ff-ui)" }}>
              VECTRIX™
            </div>
            <div style={{ fontSize: 9, color: "var(--muted)", letterSpacing: ".1em",
              textTransform: "uppercase", fontWeight: 500 }}>
              Design Platform
            </div>
          </div>
        </div>

        {/* Pill module tabs — the Task 3 redesign */}
        <div style={{
          display: "flex",
          gap: 4,
          background: "var(--panel)",
          border: "1px solid var(--border2)",
          borderRadius: "var(--r-pill)",
          padding: "3px",
        }}>
          {MODULES.map((m) => {
            const active = module === m.id;
            return (
              <button
                key={m.id}
                onClick={() => setModule(m.id)}
                title={m.desc}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "6px 14px",
                  borderRadius: "var(--r-pill)",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "var(--ff-ui)",
                  fontSize: 12,
                  fontWeight: active ? 600 : 400,
                  letterSpacing: ".01em",
                  transition: "all var(--t-base)",
                  background: active
                    ? "var(--primary)"
                    : "transparent",
                  color: active ? "#fff" : "var(--text3)",
                  boxShadow: active
                    ? "0 1px 6px rgba(59,130,246,.4)"
                    : "none",
                }}
                onMouseEnter={e => {
                  if (!active) {
                    e.currentTarget.style.background = "var(--surface)";
                    e.currentTarget.style.color = "var(--text2)";
                  }
                }}
                onMouseLeave={e => {
                  if (!active) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--text3)";
                  }
                }}
              >
                {/* Module icon */}
                <span style={{ opacity: active ? 1 : 0.6, display: "flex" }}>
                  {ICONS[m.id]}
                </span>

                {m.label}

                {/* VECTOMEC™ badge — blue not red */}
                {m.badge && (
                  <span style={{
                    fontSize: 8, fontWeight: 700, letterSpacing: ".06em",
                    padding: "1px 6px", borderRadius: "var(--r-pill)",
                    background: active
                      ? "rgba(255,255,255,.2)"
                      : "var(--primary-dim)",
                    color: active ? "#fff" : "var(--primary)",
                    border: active
                      ? "1px solid rgba(255,255,255,.25)"
                      : "1px solid var(--primary-ring)",
                  }}>
                    {m.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* PDF Report button — only when results are available */}
        {module === "bucket_elevator" && elevatorSnapshot.results && (
          <button
            onClick={() => downloadReport(elevatorSnapshot.results, elevatorSnapshot.inputs)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "6px 14px",
              borderRadius: "var(--r-pill)",
              border: "1px solid var(--border2)",
              background: "var(--surface)",
              color: "var(--text2)",
              fontFamily: "var(--ff-ui)", fontSize: 11, fontWeight: 600,
              letterSpacing: ".03em", cursor: "pointer",
              transition: "all var(--t-base)",
              marginRight: 12,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = "var(--surface2)";
              e.currentTarget.style.borderColor = "var(--border3)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = "var(--surface)";
              e.currentTarget.style.borderColor = "var(--border2)";
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            PDF Report
          </button>
        )}

        {/* Platform version tag */}
        <div style={{
          fontSize: 9, color: "var(--faint)",
          fontFamily: "var(--ff-ui)", letterSpacing: ".08em",
          textTransform: "uppercase", fontWeight: 500,
        }}>
          AKSHAYVIPRA EL-MEC · v1.0
        </div>
      </div>

      {/* Active module */}
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        {module === "bucket_elevator" && (
          <BucketElevatorPage onResultsChange={setElevatorSnapshot} />
        )}
        {module === "screw_conveyor" && <ScrewConveyorPage />}
      </div>
    </div>
  );
}
