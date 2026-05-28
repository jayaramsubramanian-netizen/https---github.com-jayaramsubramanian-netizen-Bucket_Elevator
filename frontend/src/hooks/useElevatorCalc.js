// useElevatorCalc.js — manages input state, debounced API calls, save/load
import { useState, useEffect, useCallback, useRef } from "react";
import { calculateElevator, saveDesign, getDesign } from "../api/client";
import { v4 as uuidv4 } from "uuid";

export const DEFAULT_INPUTS = {
  Q_req: 100,
  H_m: 25,
  mat_id: "wheat",
  custom_rho: 0,
  D_mm: 500,
  n_rpm: 60,
  fill_pct: 75,
  bucket_gap: 25,
  auto_bucket: true,
  bucket_id: "B",
  mu: 0.35,
  wrap_deg: 180,
  sf: 1.25,
};

export function useElevatorCalc() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [designId] = useState(() => uuidv4());
  const debounceRef = useRef(null);

  const runCalc = useCallback(async (inp) => {
    setLoading(true);
    setError(null);
    try {
      const res = await calculateElevator(inp);
      setResults(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounce: recalculate 300ms after last input change
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runCalc(inputs), 300);
    return () => clearTimeout(debounceRef.current);
  }, [inputs, runCalc]);

  const setField = useCallback((key, value) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  }, []);

  const applyOptimizer = useCallback(({ rpm, bucket_id, fill }) => {
    setInputs((prev) => ({
      ...prev,
      n_rpm: rpm,
      bucket_id,
      auto_bucket: false,
      fill_pct: fill,
    }));
  }, []);

  const saveCurrentDesign = useCallback(
    async (name, project, notes) => {
      if (!results) return;
      await saveDesign({
        id: designId,
        module: "bucket_elevator",
        name,
        project: project || null,
        inputs_json: JSON.stringify(inputs),
        results_json: JSON.stringify(results),
        notes: notes || null,
      });
    },
    [designId, inputs, results]
  );

  const loadDesign = useCallback(async (id) => {
    const record = await getDesign(id);
    setInputs(JSON.parse(record.inputs_json));
    setResults(JSON.parse(record.results_json));
  }, []);

  return {
    inputs,
    results,
    loading,
    error,
    setField,
    applyOptimizer,
    saveCurrentDesign,
    loadDesign,
    forceCalc: () => runCalc(inputs),
  };
}
