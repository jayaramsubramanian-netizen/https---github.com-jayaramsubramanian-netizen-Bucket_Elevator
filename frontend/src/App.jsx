// App.jsx — VECTRIX™ Design Platform shell
// Hosts Bucket Elevator + Screw Conveyor (and future modules)
import { useState } from "react";
import BucketElevatorPage from "./pages/BucketElevatorPage";
import "./tokens.css";

// Placeholder page for screw conveyor (already in your platform)
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

export default function App() {
  const [module, setModule] = useState("bucket_elevator");

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
        <div style={{ marginLeft: "auto", padding: "8px 0", fontSize: 9,
          color: "var(--faint)", fontFamily: "var(--ff-ui)", letterSpacing: ".08em", textTransform: "uppercase" }}>
          AKSHAYVIPRA EL-MEC · VECTRIX™ Platform
        </div>
      </div>

      {/* Active module */}
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        {module === "bucket_elevator" && <BucketElevatorPage />}
        {module === "screw_conveyor"  && <ScrewConveyorPage />}
      </div>
    </div>
  );
}
