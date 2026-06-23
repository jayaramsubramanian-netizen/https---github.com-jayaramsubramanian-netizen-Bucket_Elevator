// SaveLoadModal.jsx — save current design or load a past one
import { useState, useEffect } from "react";
import { listDesigns, deleteDesign } from "../api/client";
import { v4 as uuidv4 } from "uuid";

const C = { muted: "var(--text3)", green: "var(--success)", red: "var(--danger)", amber: "var(--warning)", blue: "var(--primary)" };

export default function SaveLoadModal({ onClose, onSave, onLoad }) {
  const [tab, setTab] = useState("save");
  const [name, setName] = useState("Bucket Elevator Design 1");
  const [project, setProject] = useState("");
  const [notes, setNotes] = useState("");
  const [designs, setDesigns] = useState([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    if (tab === "load") {
      listDesigns("bucket_elevator").then((d) => setDesigns(d.designs || []));
    }
  }, [tab]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(name, project, notes);
      setMsg({ type: "ok", text: "Design saved successfully." });
    } catch (e) {
      setMsg({ type: "fail", text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    await deleteDesign(id);
    setDesigns((prev) => prev.filter((d) => d.id !== id));
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-title">💾 Designs — Save / Load</div>

        <div className="sub-tabs" style={{ margin: "0 -0px 16px", borderRadius: "var(--r-md)", overflow: "hidden" }}>
          {["save", "load"].map((t) => (
            <button key={t} className={`sub-tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}
              style={{ flex: 1, textTransform: "uppercase" }}>
              {t === "save" ? "Save Current" : "Load Design"}
            </button>
          ))}
        </div>

        {tab === "save" && (
          <>
            <input className="modal-input" placeholder="Design name…" value={name} onChange={(e) => setName(e.target.value)} />
            <input className="modal-input" placeholder="Project (optional)…" value={project} onChange={(e) => setProject(e.target.value)} />
            <textarea className="modal-input" placeholder="Notes (optional)…" value={notes}
              onChange={(e) => setNotes(e.target.value)} rows={3} style={{ resize: "vertical" }} />
            {msg && (
              <div className={`warn-item ${msg.type === "ok" ? "w-ok" : "w-fail"}`} style={{ marginBottom: 8 }}>
                {msg.text}
              </div>
            )}
            <div className="modal-actions">
              <button className="btn-secondary" onClick={onClose}>Cancel</button>
              <button className="btn-primary" onClick={handleSave} disabled={saving || !name.trim()}>
                {saving ? "Saving…" : "💾 Save"}
              </button>
            </div>
          </>
        )}

        {tab === "load" && (
          <>
            {designs.length === 0 ? (
              <div style={{ color: C.muted, fontSize: 12, textAlign: "center", padding: "20px 0" }}>
                No saved designs yet.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 300, overflowY: "auto" }}>
                {designs.map((d) => (
                  <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px",
                    background: "var(--hi)", borderRadius: "var(--r-md)", border: "1px solid var(--border2)" }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{d.name}</div>
                      {d.project && <div style={{ fontSize: 10, color: C.muted }}>{d.project}</div>}
                      <div style={{ fontSize: 9, color: "var(--faint)", fontFamily: "JetBrains Mono" }}>
                        {new Date(d.updated_at).toLocaleString()}
                      </div>
                    </div>
                    <button className="btn-secondary" style={{ padding: "4px 10px", fontSize: 10 }}
                      onClick={() => { onLoad(d.id); onClose(); }}>
                      Load
                    </button>
                    <button style={{ background: "none", border: "none", color: C.red, cursor: "pointer", fontSize: 14 }}
                      onClick={() => handleDelete(d.id)} title="Delete">✕</button>
                  </div>
                ))}
              </div>
            )}
            <div className="modal-actions" style={{ marginTop: 12 }}>
              <button className="btn-secondary" onClick={onClose}>Close</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}