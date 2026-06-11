// MaterialSearchDropdown.jsx  v2 — UX rewrite
//
// Changes from v1
// ────────────────────────────────────────────────────────────────
// FIX 1  Premature close on category click:
//        v1 used onBlur + 150ms timeout on the search input.
//        Any click inside the dropdown (chips, results) caused the
//        input to blur → dropdown closed before results loaded.
//        Fix: document.addEventListener('mousedown', outsideClick)
//        — only a click OUTSIDE the container closes the panel.
//
// FIX 2  Categories wrapping into multiple rows:
//        16 category chips consumed most of the sidebar height.
//        Fix: single horizontally-scrollable row, flex-wrap:nowrap.
//        Scrollable with mouse-wheel or swipe on touch.
//
// FIX 3  "Defaults to first item" symptom:
//        Caused by FIX 1 — blur closed dropdown mid-search,
//        leaving the summary bar showing stale data. No longer
//        reproducible once the close logic is correct.
//
// REMOVED  Hover-footer strip — too cramped in sidebar; density
//          info is already inline in each result row.
// ────────────────────────────────────────────────────────────────

import { useState, useEffect, useRef, useCallback } from "react";

const API_BASE = "/api/v1";

// ── Display helpers ───────────────────────────────────────────────────────────
const ABR_LABEL = ["–","Low","Low","Med","Med","High","High","V.Hi"];
const ABR_COLOR = [
  "#5a7a9a","#1fb86e","#1fb86e","#d98e00",
  "#d98e00","#e05252","#e05252","#c8192e",
];
const FLOW_LABEL = { 1:"Very free", 2:"Free", 3:"Average", 4:"Sluggish" };
const CAT_FULL = {
  GRAIN:"Grain",    BIO:"Biomass",    CHEM:"Chemicals", CONST:"Construction",
  FOOD:"Food",      MIN:"Mining",     METAL:"Metals",   FERT:"Fertilisers",
  CEM:"Cement",     COAL:"Coal",      GLASS:"Glass",    ENV:"Environmental",
  PHARM:"Pharma",   PETRO:"Petroleum",POLY:"Polymers",  SALT:"Salt",
};

// Stable colour per category code
const CAT_PALETTE = [
  "#4a9eff","#1fb86e","#d98e00","#a78bfa","#2dd4bf",
  "#c8192e","#5a7a9a","#e05252","#1fb86e","#d98e00",
  "#4a9eff","#a78bfa","#2dd4bf","#e05252","#d98e00","#5a7a9a",
];
const _cc = {};
let _ci = 0;
const catColor = cat => (_cc[cat] = _cc[cat] ?? CAT_PALETTE[_ci++ % CAT_PALETTE.length]);

// ── Debounce ──────────────────────────────────────────────────────────────────
function useDebounce(v, ms = 220) {
  const [d, setD] = useState(v);
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t); }, [v, ms]);
  return d;
}

// ── API fetch ─────────────────────────────────────────────────────────────────
async function apiFetch(path) {
  try {
    const r = await fetch(path);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

// ── Result row ────────────────────────────────────────────────────────────────
function ResultRow({ mat, active, onSelect }) {
  const abr = mat.abr_code ?? 3;
  return (
    <div
      onMouseDown={e => { e.preventDefault(); onSelect(mat); }}
      style={{
        padding: "5px 10px",
        cursor: "pointer",
        background: active ? "rgba(74,158,255,.13)" : "transparent",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div style={{ display:"flex", alignItems:"center",
        justifyContent:"space-between", gap:6, marginBottom:1 }}>
        <span style={{ fontSize:10, fontWeight:600, color:"var(--text)",
          flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
          {mat.name}
        </span>
        {mat.category && (
          <span style={{
            fontSize:7, fontWeight:700, padding:"1px 4px", borderRadius:999,
            flexShrink:0,
            background: catColor(mat.category) + "20",
            color: catColor(mat.category),
            border: `1px solid ${catColor(mat.category)}40`,
          }}>{mat.category}</span>
        )}
      </div>
      <div style={{ display:"flex", gap:8, alignItems:"center" }}>
        <span style={{ fontSize:8, color:"var(--text3)",
          fontFamily:"JetBrains Mono,monospace" }}>
          {mat.rho_loose != null ? `${Number(mat.rho_loose).toFixed(0)} kg/m³` : "—"}
        </span>
        <span style={{ fontSize:8, fontWeight:600, color: ABR_COLOR[abr] || "#5a7a9a" }}>
          {ABR_LABEL[abr] || "Med"} abr
        </span>
        {mat.flowability && (
          <span style={{ fontSize:8, color:"var(--text3)" }}>
            {FLOW_LABEL[mat.flowability] || ""}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function MaterialSearchDropdown({ matId, onChange }) {
  const [query,      setQuery]      = useState("");
  const [open,       setOpen]       = useState(false);
  const [results,    setResults]    = useState([]);
  const [categories, setCategories] = useState([]);
  const [selCat,     setSelCat]     = useState("");
  const [loading,    setLoading]    = useState(false);
  const [activeIdx,  setActiveIdx]  = useState(0);
  const [currentMat, setCurrentMat] = useState(null);

  const containerRef = useRef(null);
  const inputRef     = useRef(null);
  const listRef      = useRef(null);
  const debouncedQ   = useDebounce(query);

  // ── FIX 1: close only when clicking OUTSIDE the component ────────────────
  useEffect(() => {
    function handleOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  // ── Load current material name on matId change ────────────────────────────
  useEffect(() => {
    if (!matId) return;
    apiFetch(`${API_BASE}/materials/${encodeURIComponent(matId)}`)
      .then(d => { if (d?.name) setCurrentMat(d); });
  }, [matId]);

  // ── Load categories once ──────────────────────────────────────────────────
  useEffect(() => {
    apiFetch(`${API_BASE}/materials/categories`)
      .then(d => { if (d?.categories) setCategories(d.categories); });
  }, []);

  // ── Search when query or category changes ─────────────────────────────────
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams({ limit: "40" });
    if (debouncedQ) params.set("q", debouncedQ);
    if (selCat)     params.set("category", selCat);
    apiFetch(`${API_BASE}/materials/search?${params}`)
      .then(d => {
        if (!cancelled) {
          setResults(Array.isArray(d) ? d : []);
          setActiveIdx(0);
          setLoading(false);
        }
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [debouncedQ, selCat, open]);

  // ── Select handler ────────────────────────────────────────────────────────
  const handleSelect = useCallback(mat => {
    setCurrentMat(mat);
    onChange(mat.mat_id || mat.name);
    setOpen(false);
    setQuery("");
    setSelCat("");
  }, [onChange]);

  // ── Keyboard nav ─────────────────────────────────────────────────────────
  const handleKeyDown = useCallback(e => {
    if (!open) {
      if (e.key === "Enter" || e.key === "ArrowDown") { setOpen(true); e.preventDefault(); }
      return;
    }
    if (e.key === "ArrowDown")  { setActiveIdx(i => Math.min(i + 1, results.length - 1)); e.preventDefault(); }
    else if (e.key === "ArrowUp") { setActiveIdx(i => Math.max(i - 1, 0)); e.preventDefault(); }
    else if (e.key === "Enter") { if (results[activeIdx]) handleSelect(results[activeIdx]); e.preventDefault(); }
    else if (e.key === "Escape") { setOpen(false); setQuery(""); }
  }, [open, results, activeIdx, handleSelect]);

  // Scroll active into view
  useEffect(() => {
    listRef.current?.children[activeIdx]?.scrollIntoView({ block: "nearest" });
  }, [activeIdx]);

  return (
    <div ref={containerRef} style={{ position:"relative" }}>

      {/* ── Search input ───────────────────────────────────────────────────── */}
      <div style={{
        display:"flex", alignItems:"center",
        border: `1px solid ${open ? "var(--primary)" : "var(--border)"}`,
        borderRadius:5,
        background: open ? "rgba(74,158,255,.04)" : "var(--panel2)",
        transition:"border-color .15s",
      }}>
        <span style={{ padding:"0 6px", fontSize:10,
          color: open ? "var(--primary)" : "var(--text3)" }}>🔍</span>
        <input
          ref={inputRef}
          value={query}
          placeholder={
            open ? "Type to search…"
                 : (currentMat?.name || matId || "Search materials…")
          }
          onChange={e => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          style={{
            flex:1, padding:"5px 2px", fontSize:10,
            border:"none", outline:"none",
            background:"transparent",
            color: query ? "var(--text)" : "var(--text3)",
            fontFamily:"inherit",
          }}
        />
        {loading
          ? <span style={{ padding:"0 7px", fontSize:9, color:"var(--text3)" }}>⟳</span>
          : <span
              onMouseDown={e => { e.preventDefault(); setOpen(o => !o); inputRef.current?.focus(); }}
              style={{ padding:"0 7px", cursor:"pointer", fontSize:9, color:"var(--text3)",
                transform: open ? "rotate(180deg)" : "none", transition:"transform .15s" }}>
              ▾
            </span>
        }
      </div>

      {/* ── Current material summary (shown when closed) ────────────────────── */}
      {!open && currentMat && (
        <div style={{ display:"flex", gap:6, alignItems:"center",
          padding:"2px 0", flexWrap:"wrap" }}>
          {currentMat.category && (
            <span style={{
              fontSize:7.5, padding:"1px 5px", borderRadius:999,
              background: catColor(currentMat.category) + "20",
              color: catColor(currentMat.category),
              border: `1px solid ${catColor(currentMat.category)}40`,
              fontWeight:700,
            }}>{currentMat.category}</span>
          )}
          <span style={{ fontSize:8, color:"var(--text3)",
            fontFamily:"JetBrains Mono,monospace" }}>
            {currentMat.rho_loose != null
              ? `${Number(currentMat.rho_loose).toFixed(0)} kg/m³` : ""}
          </span>
          {currentMat.abr_code != null && (
            <span style={{ fontSize:8, fontWeight:600,
              color: ABR_COLOR[currentMat.abr_code] || "var(--text3)" }}>
              {ABR_LABEL[currentMat.abr_code]} abr
            </span>
          )}
        </div>
      )}

      {/* ── Dropdown ──────────────────────────────────────────────────────── */}
      {open && (
        <div style={{
          position:"absolute",
          top:"calc(100% + 3px)",
          left:0, right:0,
          background:"var(--panel)",
          border:"1px solid var(--primary)",
          borderRadius:6,
          zIndex:999,
          boxShadow:"0 8px 24px rgba(0,0,0,.5)",
          display:"flex",
          flexDirection:"column",
          maxHeight:280,
        }}>

          {/* ── FIX 2: single scrollable category row ────────────────────── */}
          {categories.length > 0 && (
            <div style={{
              display:"flex",
              gap:4,
              padding:"5px 8px",
              borderBottom:"1px solid var(--border)",
              overflowX:"auto",
              flexWrap:"nowrap",           // ← no wrapping
              flexShrink:0,
              scrollbarWidth:"none",       // Firefox
              msOverflowStyle:"none",      // IE
            }}>
              {/* Hide webkit scrollbar */}
              <style>{`.mat-cat-strip::-webkit-scrollbar{display:none}`}</style>

              {/* All button */}
              <button
                onMouseDown={e => { e.preventDefault(); setSelCat(""); setOpen(true); }}
                style={{
                  padding:"2px 8px", fontSize:8.5, borderRadius:999,
                  cursor:"pointer", fontFamily:"inherit", whiteSpace:"nowrap", flexShrink:0,
                  border: `1px solid ${!selCat ? "var(--primary)" : "var(--border)"}`,
                  background: !selCat ? "var(--primary-dim)" : "var(--panel2)",
                  color: !selCat ? "var(--primary)" : "var(--text3)",
                  fontWeight: !selCat ? 700 : 400,
                }}>All</button>

              {categories.map(cat => {
                const active = selCat === cat;
                const cc = catColor(cat);
                return (
                  <button key={cat}
                    onMouseDown={e => {
                      e.preventDefault();
                      setSelCat(c => c === cat ? "" : cat);
                      setOpen(true);
                      inputRef.current?.focus();
                    }}
                    style={{
                      padding:"2px 8px", fontSize:8.5, borderRadius:999,
                      cursor:"pointer", fontFamily:"inherit", whiteSpace:"nowrap", flexShrink:0,
                      border: `1px solid ${active ? cc : "var(--border)"}`,
                      background: active ? cc + "20" : "var(--panel2)",
                      color: active ? cc : "var(--text3)",
                      fontWeight: active ? 700 : 400,
                    }}>
                    {CAT_FULL[cat] || cat}
                  </button>
                );
              })}
            </div>
          )}

          {/* ── Results list ─────────────────────────────────────────────── */}
          <div ref={listRef} style={{ overflowY:"auto", flex:1 }}>
            {!loading && results.length === 0 && (
              <div style={{ padding:"12px", fontSize:9,
                color:"var(--text3)", textAlign:"center" }}>
                {query || selCat
                  ? "No matches — try different search or category"
                  : "Type a material name to search"}
              </div>
            )}
            {loading && results.length === 0 && (
              <div style={{ padding:"12px", fontSize:9,
                color:"var(--text3)", textAlign:"center" }}>
                Searching…
              </div>
            )}
            {results.map((mat, i) => (
              <ResultRow
                key={mat.mat_id || mat.name}
                mat={mat}
                active={i === activeIdx}
                onSelect={handleSelect}
              />
            ))}
          </div>

          {/* ── Footer: count ────────────────────────────────────────────── */}
          {results.length > 0 && (
            <div style={{
              padding:"3px 10px",
              borderTop:"1px solid var(--border)",
              fontSize:7.5, color:"var(--text3)",
              flexShrink:0,
              display:"flex", justifyContent:"space-between",
            }}>
              <span>{results.length} result{results.length !== 1 ? "s" : ""}
                {selCat ? ` in ${CAT_FULL[selCat] || selCat}` : ""}
              </span>
              <span style={{ color:"var(--muted)" }}>
                ↑↓ Enter to select · Esc to close
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}