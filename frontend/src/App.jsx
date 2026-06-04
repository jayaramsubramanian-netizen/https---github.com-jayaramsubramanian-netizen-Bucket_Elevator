// App.jsx — VECTRIX™ Design Platform shell
import { useState, useEffect } from "react";
import BucketElevatorPage from "./BucketElevatorPage";   // ← same folder as App.jsx
import "./tokens.css";

function ScrewConveyorPage() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
      flex: 1, flexDirection: "column", gap: 12, color: "var(--muted)", fontSize: 13 }}>
      <div style={{ fontSize: 32 }}>🔩</div>
      <div style={{ fontFamily: "var(--ff-ui)", fontSize: 14, letterSpacing: ".08em",
        textTransform: "uppercase" }}>Screw Conveyor Module</div>
      <div>Your existing screw conveyor design platform renders here.</div>
    </div>
  );
}

const MODULES = [
  { id: "bucket_elevator", label: "Bucket Elevator", icon: "⛏", badge: "VECTOMEC™" },
  { id: "screw_conveyor",  label: "Screw Conveyor",  icon: "🔩", badge: null },
];

async function downloadReport(results, inputs) {
  if (!results) return;
  const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";
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
  const [module, setModule] = useState("bucket_elevator");
  const [elevatorSnapshot, setElevatorSnapshot] = useState({ results: null, inputs: {} });

  return (
    <div className="app-shell">
      {/* Module switcher bar */}
      <div className="module-switcher">
        {MODULES.map((m) => (
          <button key={m.id} className={`module-tab ${module === m.id ? "active" : ""}`}
            onClick={() => setModule(m.id)}>
            {m.icon} {m.label}
            {m.badge && (
              <span style={{ marginLeft: 6, fontSize: 8, color: "var(--primary)",
                background: "rgba(200,25,46,.15)", border: "1px solid rgba(200,25,46,.3)",
                padding: "1px 5px", borderRadius: 3, fontFamily: "var(--ff-ui)", fontWeight: 700 }}>
                {m.badge}
              </span>
            )}
          </button>
        ))}

        {/* PDF download button — only when elevator is active and has results */}
        {module === "bucket_elevator" && elevatorSnapshot.results && (
          <button
            onClick={() => downloadReport(elevatorSnapshot.results, elevatorSnapshot.inputs)}
            style={{ marginLeft: 8, padding: "4px 12px",
              background: "rgba(200,25,46,.15)", border: "1px solid rgba(200,25,46,.4)",
              borderRadius: 4, color: "var(--primary, #c8192e)",
              fontFamily: "var(--ff-ui)", fontSize: 11, fontWeight: 700,
              letterSpacing: ".04em", cursor: "pointer", textTransform: "uppercase" }}>
            ⬇ PDF Report
          </button>
        )}

        <div style={{ marginLeft: "auto", padding: "8px 0", fontSize: 9,
          color: "var(--faint)", fontFamily: "var(--ff-ui)", letterSpacing: ".08em",
          textTransform: "uppercase" }}>
          AKSHAYVIPRA EL-MEC · VECTRIX™ Platform
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