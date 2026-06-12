
// ReportView.jsx — Task 9: Executive + Detailed report view
//
// Used as the middle-column content for the "Report" tab (5th nav pill).
// Two stacked sections:
//   1. Executive — verdict banner, capacity decision, key pass/fail badges,
//      machine/drive/structural specification summary
//   2. Detailed  — every intermediate computed value, organized by
//      CEMA 375 calculation stage (input echo → capacity → power →
//      tensions → shaft → discharge → bearing → material)
//
// A small toggle lets the engineer collapse either section.
// BOMCard (preliminary bill of materials) lives in the right column
// alongside DesignReview when this tab is active — see BucketElevatorPage.jsx.

import { useState } from "react";

// ── Main export ────────────────────────────────────────────────────────────

export default function ReportView({ results, inputs }) {
  const [showExec, setShowExec] = useState(true);
  const [showDetail, setShowDetail] = useState(true);

  const SectionToggle = ({ label, open, onClick }) => (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "10px 14px", cursor: "pointer", userSelect: "none",
        background: "var(--panel2)", borderBottom: "1px solid var(--border)",
        position: "sticky", top: 0, zIndex: 1,
      }}
    >
      <span style={{
        fontSize: 9, color: "var(--faint)",
        transform: open ? "rotate(90deg)" : "none",
        transition: "transform .15s", display: "inline-block",
      }}>▶</span>
      <span style={{
        fontSize: 11, fontWeight: 700, letterSpacing: ".08em",
        textTransform: "uppercase", color: "var(--text2)",
      }}>{label}</span>
    </div>
  );

  return (
    <div style={{ flex: 1, overflowY: "auto" }}>
      <SectionToggle label="Executive Summary" open={showExec}
        onClick={() => setShowExec(!showExec)} />
      {showExec && <ExecutiveView results={results} inputs={inputs} />}

      <SectionToggle label="Detailed Calculations" open={showDetail}
        onClick={() => setShowDetail(!showDetail)} />
      {showDetail && <DetailedView results={results} inputs={inputs} />}
    </div>
  );
}
