"""
backend/sensitivity_engine.py -- Engine 3: one design, many operating conditions.
═══════════════════════════════════════════════════════════════════════════
Real equipment operates over an ENVELOPE, not a design point. This engine sweeps
the independent variables around a nominal design and reports how the outputs --
and the verdicts -- respond.

ARCHITECTURE: it owns NO physics. Every evaluation goes through the real
solve_elevator(), exactly as vectrix_optimizer_v2.py does. That is the whole
design: one canonical solver, many callers (GUI / Optimizer / Sensitivity /
Reliability / Digital Twin). If a sweep disagrees with the design page, the bug
is in the solver, not in two copies of the maths.

FEASIBILITY: solve_elevator() is ~1.2 ms/call (findings log #21, and the
optimizer runs 20,000 evaluations in ~29 s). So:
    20-step 1-D sweep      ~0.02 s
    50x50 grid            ~3 s
    10,000-run Monte Carlo ~12 s
All levels are viable single-threaded.

INDEPENDENT VARIABLES ONLY. Bucket fill, power, torque, tension and trajectory
are DERIVED -- sweeping them would be meaningless (you cannot "set" power). The
VARIABLES registry below contains only things a plant can actually change or
that genuinely vary.

NON-SMOOTH BY DESIGN. The solver snaps to catalogue sizes (motor kW, shaft mm,
bearing class), so response curves have plateaus and steps. That is a FEATURE:
the steps show the engineer exactly where a component selection changes. Nothing
here smooths or interpolates them.

LIMITS COME FROM engineering_limits, NEVER FROM THIS FILE. A margin needs a
limit, and a limit needs provenance. This module reads limits by limit_key and
carries their source through to the output so the UI can show
"Source: CEMA 375" or "Source: VECTOMEC judgement". There are deliberately NO
threshold literals below.
"""
from __future__ import annotations

import math
import statistics
import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:                                    # package or flat layout, same as calculations.py
    from .calculations import solve_elevator
    from .models import BucketElevatorInput
except ImportError:                     # pragma: no cover
    from calculations import solve_elevator          # type: ignore
    from models import BucketElevatorInput           # type: ignore


# ── Independent variables ────────────────────────────────────────────────────
# Each entry says how to APPLY a value to the input payload. Derived quantities
# are deliberately absent.
#
#   key -> (label, unit, payload_field, typical_rel_range)
VARIABLES: Dict[str, Dict[str, Any]] = {
    "Q_req":            dict(label="Feed rate",           unit="tph",   field="Q_req",                    rel=(0.70, 1.30)),
    "belt_speed":       dict(label="Belt speed",          unit="m/s",   field="belt_speed_override_ms",   rel=(0.80, 1.20)),
    "bucket_gap":       dict(label="Bucket spacing gap",  unit="mm",    field="bucket_gap",               rel=(0.60, 1.60)),
    "D_mm":             dict(label="Head pulley dia.",    unit="mm",    field="D_mm",                     rel=(0.80, 1.25)),
    "fill_pct":         dict(label="Fill efficiency",     unit="%",     field="fill_pct",                 rel=(0.75, 1.15)),
    "material_temperature_c": dict(label="Material temp.", unit="degC", field="material_temperature_c",   rel=(0.50, 2.00)),
    "H_m":              dict(label="Lift height",         unit="m",     field="H_m",                      rel=(0.90, 1.10)),
}

# Outputs pulled from each solve. (key in result, label, unit).
# Nested paths use dotted notation.
METRICS: Dict[str, Dict[str, str]] = {
    "Q":                dict(label="Capacity",            unit="tph"),
    "P_total":          dict(label="Power",               unit="kW"),
    "T_total":          dict(label="Belt/chain tension",  unit="N"),
    "motor_kw":         dict(label="Motor size",          unit="kW"),
    "cr":               dict(label="Centrifugal ratio",   unit="-"),
    "v":                dict(label="Belt speed",          unit="m/s"),
    "L10":              dict(label="Bearing L10",         unit="h"),
    "d_shaft_mm":       dict(label="Head shaft dia.",     unit="mm"),
}


class SolveFailure(Exception):
    """A single evaluation failed. Carries the reason so a sweep can CLASSIFY
    failures rather than silently dropping cells."""

    def __init__(self, reason: str, kind: str = "unknown"):
        super().__init__(reason)
        self.kind = kind


def _dig(d: Any, path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def solve_once(payload: Dict[str, Any]) -> Dict[str, Any]:
    """One evaluation through the REAL solver.

    Exceptions are classified, not swallowed. Until the solver raises structured
    errors (GeometryInvalidError / ConstraintViolationError -- roadmap item 2),
    the message is inspected to separate a genuine infeasible geometry from an
    unexpected crash. That distinction matters: a sweep should report "12% of
    this region is geometrically infeasible", not silently lose 12% of its cells.
    """
    try:
        inp = BucketElevatorInput(**payload)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return solve_elevator(inp)
    except ValueError as e:
        msg = str(e).lower()
        kind = "geometry_invalid" if ("domain error" in msg or "math" in msg) else "invalid_input"
        raise SolveFailure(str(e), kind) from e
    except Exception as e:                       # backstop -- never kill a sweep
        raise SolveFailure(f"{type(e).__name__}: {e}", "crash") from e


def extract(result: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the tracked metrics plus the verdict summary from one solution."""
    out: Dict[str, Any] = {k: result.get(k) for k in METRICS}
    checks = result.get("checks") or []
    out["_n_fail"] = sum(1 for c in checks if c.get("type") == "fail")
    out["_n_warn"] = sum(1 for c in checks if c.get("type") == "warn")
    out["_feasible"] = out["_n_fail"] == 0
    return out


# ── Level 1: single-variable sweep ───────────────────────────────────────────
def sweep_1d(base_payload: Dict[str, Any], var: str,
             values: Optional[Sequence[float]] = None,
             steps: int = 21) -> Dict[str, Any]:
    """Hold everything constant, vary ONE independent variable.

    Returns every solved point plus the failure classification. Steps and
    plateaus in the response are preserved exactly -- they are catalogue
    selections, not noise.
    """
    if var not in VARIABLES:
        raise KeyError(f"'{var}' is not an independent variable. "
                       f"Known: {sorted(VARIABLES)}")
    spec = VARIABLES[var]
    field = spec["field"]
    nominal = base_payload.get(field)
    if nominal is None:
        raise ValueError(f"base payload has no value for '{field}' to sweep around")

    if values is None:
        lo, hi = spec["rel"]
        values = [float(nominal) * (lo + (hi - lo) * i / (steps - 1))
                  for i in range(steps)]

    points, failures = [], []
    for val in values:
        payload = dict(base_payload)
        payload[field] = val
        try:
            res = solve_once(payload)
        except SolveFailure as f:
            failures.append({"value": val, "kind": f.kind, "reason": str(f)})
            points.append({"value": val, "ok": False, "kind": f.kind})
            continue
        row = extract(res)
        row["value"] = val
        row["ok"] = True
        points.append(row)

    return {
        "variable": var, "label": spec["label"], "unit": spec["unit"],
        "nominal": nominal, "points": points,
        "n_solved": sum(1 for p in points if p["ok"]),
        "n_failed": len(failures), "failures": failures,
    }


def sensitivity_coefficients(base_payload: Dict[str, Any],
                             variables: Optional[Iterable[str]] = None,
                             delta: float = 0.10) -> Dict[str, Any]:
    """Normalised sensitivity coefficients.

        S = (dO/O) / (dI/I)

    NOTE ON THE FORMULA: this is OUTPUT-over-INPUT. The spec text had it
    inverted (input-over-output) while its own interpretation table described
    output-over-input ("0.5 -> a 10% input change gives ~5% output change",
    "1.0 -> linear"). Output-over-input is the standard definition and the one
    that matches the intended reading; the inverted form would have reported
    2.0 for that same 0.5 response and reversed every ranking.

    Central difference (+/- delta) so the estimate is not biased by which side
    of a catalogue step the nominal sits on. Because the solver is non-smooth, a
    coefficient can still land on a step edge -- `stepped` flags when the two
    sides disagree in sign or differ by more than 3x, meaning the local
    gradient is dominated by a discrete selection change rather than by physics.
    """
    variables = list(variables or VARIABLES.keys())
    base = solve_once(base_payload)
    base_m = extract(base)

    table: Dict[str, Dict[str, Any]] = {}
    for var in variables:
        spec = VARIABLES[var]
        field = spec["field"]
        nom = base_payload.get(field)
        if nom in (None, 0):
            continue
        row: Dict[str, Any] = {}
        try:
            up = extract(solve_once({**base_payload, field: float(nom) * (1 + delta)}))
            dn = extract(solve_once({**base_payload, field: float(nom) * (1 - delta)}))
        except SolveFailure as f:
            table[var] = {"_error": f.kind}
            continue

        for m in METRICS:
            o0, ou, od = base_m.get(m), up.get(m), dn.get(m)
            if not all(isinstance(x, (int, float)) for x in (o0, ou, od)) or not o0:
                continue
            s_up = ((ou - o0) / o0) / delta
            s_dn = ((o0 - od) / o0) / delta
            s = (s_up + s_dn) / 2.0
            stepped = (s_up * s_dn < 0) or (
                max(abs(s_up), abs(s_dn)) > 3.0 * max(min(abs(s_up), abs(s_dn)), 1e-9))
            row[m] = {"S": round(s, 3), "stepped": bool(stepped)}
        table[var] = row

    return {"delta": delta, "base": base_m, "coefficients": table,
            "note": "S = (dO/O)/(dI/I); |S|>1 amplifies, <1 damps, <0 inverts. "
                    "stepped=True means a catalogue step dominates the local slope."}


def tornado(base_payload: Dict[str, Any], metric: str = "P_total",
            variables: Optional[Iterable[str]] = None,
            delta: float = 0.10) -> List[Dict[str, Any]]:
    """Tornado chart data: which inputs move `metric` most, ranked."""
    sc = sensitivity_coefficients(base_payload, variables, delta)
    rows = []
    for var, mm in sc["coefficients"].items():
        if "_error" in mm or metric not in mm:
            continue
        rows.append({"variable": var, "label": VARIABLES[var]["label"],
                     "S": mm[metric]["S"], "abs_S": abs(mm[metric]["S"]),
                     "stepped": mm[metric]["stepped"]})
    rows.sort(key=lambda r: r["abs_S"], reverse=True)
    return rows


# ── Level 2: 2-variable grid ─────────────────────────────────────────────────
def grid_2d(base_payload: Dict[str, Any], var_x: str, var_y: str,
            steps_x: int = 15, steps_y: int = 15,
            metric: str = "P_total") -> Dict[str, Any]:
    """Solve a grid, producing heat-map data plus a feasibility mask."""
    sx, sy = VARIABLES[var_x], VARIABLES[var_y]
    nx, ny = base_payload.get(sx["field"]), base_payload.get(sy["field"])
    xs = [nx * (sx["rel"][0] + (sx["rel"][1] - sx["rel"][0]) * i / (steps_x - 1))
          for i in range(steps_x)]
    ys = [ny * (sy["rel"][0] + (sy["rel"][1] - sy["rel"][0]) * j / (steps_y - 1))
          for j in range(steps_y)]

    z, feasible, n_fail = [], [], 0
    for yv in ys:
        zrow, frow = [], []
        for xv in xs:
            payload = {**base_payload, sx["field"]: xv, sy["field"]: yv}
            try:
                m = extract(solve_once(payload))
                zrow.append(m.get(metric))
                frow.append(bool(m["_feasible"]))
            except SolveFailure:
                zrow.append(None); frow.append(False); n_fail += 1
        z.append(zrow); feasible.append(frow)

    return {"x": xs, "y": ys, "z": z, "feasible": feasible,
            "x_label": sx["label"], "y_label": sy["label"],
            "metric": metric, "n_unsolvable": n_fail}


# ── Level 3: worst case ──────────────────────────────────────────────────────
def worst_case(base_payload: Dict[str, Any],
               ranges: Dict[str, tuple], metric: str = "P_total",
               sample: int = 0) -> Dict[str, Any]:
    """Min / nominal / max / worst / best over the input box.

    IMPORTANT: corner enumeration is NOT guaranteed to find the true extreme.
    The solver is non-monotonic (catalogue snapping, regime changes), so the
    worst case can sit INSIDE the box, not at a corner. Pass sample>0 to add a
    quasi-random interior sample -- at ~1.2 ms/solve this is cheap insurance and
    the result reports which strategy actually found the extreme.
    """
    import itertools, random
    keys = list(ranges)
    fields = [VARIABLES[k]["field"] for k in keys]

    evaluated = []
    for combo in itertools.product(*[ranges[k] for k in keys]):
        payload = {**base_payload, **dict(zip(fields, combo))}
        try:
            m = extract(solve_once(payload))
            evaluated.append(({k: v for k, v in zip(keys, combo)}, m, "corner"))
        except SolveFailure:
            pass

    if sample > 0:
        rng = random.Random(12345)          # deterministic: a report must reproduce
        for _ in range(sample):
            combo = [rng.uniform(min(ranges[k]), max(ranges[k])) for k in keys]
            payload = {**base_payload, **dict(zip(fields, combo))}
            try:
                m = extract(solve_once(payload))
                evaluated.append(({k: v for k, v in zip(keys, combo)}, m, "interior"))
            except SolveFailure:
                pass

    vals = [(e[1].get(metric), e) for e in evaluated
            if isinstance(e[1].get(metric), (int, float))]
    if not vals:
        return {"error": "no feasible evaluation in the given ranges"}
    lo = min(vals, key=lambda t: t[0]); hi = max(vals, key=lambda t: t[0])
    nominal = extract(solve_once(base_payload))
    return {
        "metric": metric,
        "nominal": nominal.get(metric),
        "best":  {"value": lo[0], "inputs": lo[1][0], "found_at": lo[1][2]},
        "worst": {"value": hi[0], "inputs": hi[1][0], "found_at": hi[1][2]},
        "n_evaluated": len(evaluated),
        "corner_dominated": hi[1][2] == "corner" and lo[1][2] == "corner",
    }


# ── Level 4: Monte Carlo (Engine 4 seed) ─────────────────────────────────────
def monte_carlo(base_payload: Dict[str, Any],
                distributions: Dict[str, Dict[str, float]],
                n: int = 2000, seed_value: int = 42) -> Dict[str, Any]:
    """Inputs as DISTRIBUTIONS, outputs as PROBABILITIES.

    distributions: {var: {"dist": "normal", "mean": .., "sd": ..}}
                   {var: {"dist": "uniform", "lo": .., "hi": ..}}
    Deterministic seed so a report can be reproduced exactly.
    """
    import random
    rng = random.Random(seed_value)
    fields = {k: VARIABLES[k]["field"] for k in distributions}

    # THREE OUTCOMES, never conflated -- they mean different things and demand
    # different responses:
    #   feasible        the design works at that operating point
    #   infeasible      the design is VALID but VIOLATES a check (motor overload)
    #                   -> an engineering result: reduce load, resize, accept risk
    #   solver_failure  the solver could NOT evaluate it (geometry impossible)
    #                   -> NOT a probability of failure; a gap in the analysis
    # Lumping "motor overloaded" with "geometry impossible" would misreport an
    # un-analysed region as a reliability figure.
    samples: List[Dict[str, Any]] = []
    n_infeasible = n_unsolvable = 0
    failure_kinds: Dict[str, int] = {}
    for _ in range(n):
        draw = {}
        for k, d in distributions.items():
            if d.get("dist") == "uniform":
                draw[fields[k]] = rng.uniform(d["lo"], d["hi"])
            else:
                draw[fields[k]] = rng.gauss(d["mean"], d["sd"])
        try:
            m = extract(solve_once({**base_payload, **draw}))
        except SolveFailure as f:
            n_unsolvable += 1
            failure_kinds[f.kind] = failure_kinds.get(f.kind, 0) + 1
            continue
        if not m["_feasible"]:
            n_infeasible += 1
        samples.append(m)

    def stats(metric):
        xs = [s[metric] for s in samples if isinstance(s.get(metric), (int, float))]
        if not xs:
            return None
        xs_sorted = sorted(xs)
        def pct(p):
            i = min(len(xs_sorted) - 1, max(0, int(round(p / 100 * (len(xs_sorted) - 1)))))
            return xs_sorted[i]
        return {"mean": round(statistics.fmean(xs), 3),
                "sd": round(statistics.pstdev(xs), 3) if len(xs) > 1 else 0.0,
                "min": xs_sorted[0], "max": xs_sorted[-1],
                "p05": pct(5), "p50": pct(50), "p95": pct(95)}

    n_ok = len(samples)
    n_feasible = n_ok - n_infeasible

    # Convergence: split the sample in half and compare the mean of the primary
    # metric. If the halves disagree by more than 2%, n is too small for the
    # reported probabilities to be trusted.
    converged, conv_note = None, None
    # Build a genuinely float-typed list. The previous comprehension called
    # .get() twice -- once in the filter, once in the value -- so the isinstance
    # guard narrowed the filter expression while the value stayed Any | None.
    # That is a real type hole, not a linter quirk: a None slipping through
    # would raise inside fmean() mid-analysis.
    prim: List[float] = []
    for _s in samples:
        _p = _s.get("P_total")
        if isinstance(_p, (int, float)):
            prim.append(float(_p))
    if len(prim) >= 100:
        h = len(prim) // 2
        m1, m2 = statistics.fmean(prim[:h]), statistics.fmean(prim[h:])
        drift = abs(m2 - m1) / abs(m1) if m1 else 0.0
        converged = drift < 0.02
        conv_note = f"half-sample means differ by {drift*100:.2f}%"

    return {
        "n_requested": n,
        "n_evaluated": n_ok,
        "n_feasible": n_feasible,          # valid design, all checks pass
        "n_infeasible": n_infeasible,      # valid design, a check FAILS
        "n_solver_failure": n_unsolvable,  # could not be evaluated at all
        "solver_failure_kinds": failure_kinds,
        "converged": converged,
        "convergence_note": conv_note,
        # denominator is EVALUATED runs -- unsolvable points are excluded, not
        # counted as successes, and are reported separately above
        "p_infeasible": round(n_infeasible / n_ok, 4) if n_ok else None,
        "coverage": round(n_ok / n, 4) if n else None,
        "metrics": {m: stats(m) for m in METRICS},
        "note": "p_infeasible = P(at least one FAIL check | the point was "
                "evaluable). n_solver_failure is a GAP IN THE ANALYSIS, not a "
                "failure probability -- if coverage is well below 1.0, the "
                "sampled envelope extends outside what the solver can model.",
    }


class EngineeringLimitManager:
    """ONE SQL read, then thousands of solver calls against an in-memory dict.

    Why this exists: a Monte Carlo run calls the solver 10,000 times. If each
    margin evaluation re-queried SQLite, the analysis would spend more time in
    the database than in the physics. Limits change on the timescale of an
    engineering review, not a solve, so they are loaded once and cached.

    Every engine (Sensitivity, Optimizer, GUI, Reports, API) reads through here
    -- so there is exactly one place limits enter the system, and one place to
    invalidate when an engineering change lands.
    """

    _cache: Dict[str, Dict[str, Any]] = {}
    # (db_path, equipment) -- the cache key. Annotated as a tuple because that
    # is what it holds; it was declared Optional[str] while being assigned a
    # 2-tuple, so every cache-hit comparison was type-unsound.
    _loaded_from: Optional[Tuple[str, str]] = None

    @classmethod
    def load(cls, db_path: str, equipment: str = "bucket_elevator",
             force: bool = False) -> Dict[str, Dict[str, Any]]:
        if cls._cache and cls._loaded_from == (db_path, equipment) and not force:
            return cls._cache
        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT * FROM engineering_limits WHERE is_active=1 "
                "AND equipment IN (?,'any')", (equipment,)).fetchall()
        finally:
            con.close()
        cls._cache = {r["limit_key"]: dict(r) for r in rows}
        cls._loaded_from = (db_path, equipment)
        return cls._cache

    @classmethod
    def get(cls, limit_key: str) -> Optional[Dict[str, Any]]:
        return cls._cache.get(limit_key)

    @classmethod
    def all(cls) -> List[Dict[str, Any]]:
        return list(cls._cache.values())

    @classmethod
    def invalidate(cls) -> None:
        """Call after an engineering change / SQL migration."""
        cls._cache = {}
        cls._loaded_from = None

    @classmethod
    def resolve_derived(cls, limit_key: str, **bounds) -> Dict[str, Any]:
        """Supply a DERIVED limit's bounds from the component the solver chose.

        e.g. resolve_derived("headshaft_radial_load", fail_max=bearing_C_dyn_N)
        Returns a COPY -- the cache is never mutated by a single solve.
        """
        lim = dict(cls._cache.get(limit_key) or {})
        lim.update({k: v for k, v in bounds.items() if v is not None})
        return lim


def evaluate_limit(value: Any, lim: Dict[str, Any]) -> Dict[str, Any]:
    """THE generic limit evaluator. One function, every comparison type.

    `lim["direction"]` carries the comparison semantics, so neither this module
    nor the UI needs a special case per parameter:

        min      lower bound binds   -- L10 >= 40,000 h
        max      upper bound binds   -- motor load <= 90%
        range    two-sided band      -- CR 1.0 - 1.8
        boolean  condition must be False -- backlegging present = fail

    Returns status (ok|warn|fail|None), the binding bound, and margin toward
    that bound as a percentage, so every row is comparable on one chart.

    None value -> status None (NEUTRAL). A limit that could not be evaluated is
    not a pass; the caller renders it grey, never green.
    """
    direction = lim.get("direction")
    wmin, wmax = lim.get("warning_min"), lim.get("warning_max")
    fmin, fmax = lim.get("fail_min"), lim.get("fail_max")

    if direction == "target":
        # A target is an IDEAL, not a limit. Deviation is REPORTED, never failed
        # on -- 95.8% against a 96% target is not an error. If the parameter also
        # has allowable bounds, model those as a SEPARATE 'range' limit.
        tgt = lim.get("target_min")
        if value is None or tgt is None:
            return {"value": None, "status": None, "bound": None,
                    "margin_abs": None, "margin_pct": None}
        v = float(value)
        dev = v - float(tgt)
        return {"value": round(v, 3), "status": "ok", "bound": float(tgt),
                "margin_abs": round(dev, 3),
                "margin_pct": round(dev / abs(tgt) * 100.0, 1) if tgt else None,
                "is_deviation": True}

    if direction == "boolean":
        if value is None:
            return {"value": None, "status": None, "bound": None,
                    "margin_abs": None, "margin_pct": None}
        # POLARITY MATTERS: "hub fits = True" PASSES, "backlegging = True" FAILS.
        # boolean_expect states which value is the passing one. Without it, half
        # of all boolean limits would report exactly the inverted verdict --
        # which is what this dashboard did until the hub-fits row read "fail"
        # on a hub that fits.
        expect = lim.get("boolean_expect")
        expect = True if expect is None else bool(expect)
        actual = bool(value)
        return {"value": actual, "status": "ok" if actual == expect else "fail",
                "bound": expect, "margin_abs": None, "margin_pct": None}

    if not isinstance(value, (int, float)):
        return {"value": None, "status": None, "bound": None,
                "margin_abs": None, "margin_pct": None}
    v = float(value)

    def _pct(val, bnd):
        # `is not None`, NOT truthiness: 0.0 is a legitimate bound
        # (motor_power_margin's warning_min IS 0%). `if bnd:` silently dropped
        # that row's margin entirely -- caught by testing, not review.
        if bnd is None:
            return None
        if bnd == 0:
            return val                      # margin above a zero bound IS the value
        return (val - bnd) / abs(bnd) * 100.0

    # BOTH margins are emitted, because neither alone is right for every case:
    #   margin_abs -- in the parameter's own units. Correct for motor load
    #                 (90% - 75% = 15 percentage points) and for range limits
    #                 (distance to the NEAREST boundary).
    #   margin_pct -- relative to the bound. Correct for bearing life
    #                 (120,000 vs 50,000 h = +140%), where an absolute
    #                 70,000 h means little without its scale.
    # The UI picks whichever suits the parameter instead of the backend guessing.
    status, bound, margin_abs, margin_pct = "ok", None, None, None

    if direction == "min":
        bound = wmin if wmin is not None else fmin
        if fmin is not None and v < fmin:
            status = "fail"
        elif wmin is not None and v < wmin:
            status = "warn"
        if bound is not None:
            margin_abs = v - bound
        margin_pct = _pct(v, bound)

    elif direction == "max":
        bound = wmax if wmax is not None else fmax
        if fmax is not None and v > fmax:
            status = "fail"
        elif wmax is not None and v > wmax:
            status = "warn"
        if bound is not None:
            margin_abs = bound - v                  # headroom below the ceiling
        m = _pct(v, bound)
        margin_pct = None if m is None else -m

    elif direction == "range":
        if (fmin is not None and v < fmin) or (fmax is not None and v > fmax):
            status = "fail"
        elif (wmin is not None and v < wmin) or (wmax is not None and v > wmax):
            status = "warn"
        # DISTANCE TO THE NEAREST BOUNDARY -- for a band, "how much room is
        # left before I leave the acceptable zone" is the intuitive reading;
        # a percentage of the span is not.
        if wmin is not None and wmax is not None:
            margin_abs = min(v - wmin, wmax - v)
            span = abs(wmax - wmin) or 1.0
            margin_pct = margin_abs / span * 100.0
            bound = (wmin, wmax)

    return {"value": round(v, 3), "status": status, "bound": bound,
            "margin_abs": round(margin_abs, 3) if margin_abs is not None else None,
            "margin_pct": round(margin_pct, 1) if margin_pct is not None else None}


# ── DERIVED limit resolution ─────────────────────────────────────────────────
# A derived limit's bound is NOT a stored constant -- it comes from the
# component the solver actually selected. This registry says, for each derived
# limit, where in the result to find the ACTUAL value and its ALLOWABLE.
#
# This is the mechanism that stops a stale static number (the old 50/80 kN
# headshaft limit) from silently overriding a correctly computed component
# rating. If a pair is absent from the result, the limit renders NEUTRAL --
# never a green PASS derived from an assumed bound.
#
#   limit_key -> (actual_path, allow_path)
DERIVED_SOURCES: Dict[str, tuple] = {
    "key_shear_stress":      ("key_check.tau_actual_MPa",   "key_check.tau_allow_MPa"),
    "key_bearing_stress":    ("key_check.sigma_actual_MPa", "key_check.sigma_allow_MPa"),
    "weld_stress":           ("weld_check.tau_torsion_MPa", "weld_check.weld_allow_MPa"),
    "pulley_hub_fits_shell": ("end_disc.hub_fits_in_shell", None),
    # headshaft_radial_load: the allowable is the SELECTED bearing's rating.
    # Left unmapped until the solver exposes that rating in its result -- an
    # honest gap is better than an invented denominator.
}


def resolve_derived_limits(result: Dict[str, Any],
                           limits: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fill each derived limit's bounds from the solved design.

    Returns COPIES -- the shared limit cache is never mutated by one solve.
    A derived limit whose pair is missing keeps NULL bounds and will render
    neutral, which is the correct display for "not yet wired".
    """
    out = []
    for lim in limits:
        if lim.get("limit_class") != "derived":
            out.append(lim)
            continue
        spec = DERIVED_SOURCES.get(lim["limit_key"])
        lim = dict(lim)
        if not spec:
            out.append(lim)
            continue
        actual_path, allow_path = spec
        lim["_actual_value"] = _dig(result, actual_path)
        if allow_path:
            allow = _dig(result, allow_path)
            if allow is not None:
                # the ALLOWABLE from the selected component becomes the bound
                if lim.get("direction") == "max":
                    lim["fail_max"] = float(allow)
                elif lim.get("direction") == "min":
                    lim["fail_min"] = float(allow)
        out.append(lim)
    return out


# ── Level 5: design margin dashboard ─────────────────────────────────────────
def design_margins(result: Dict[str, Any],
                   limits: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Margin of each computed value against its SOURCED limit.

    `limits` are rows from the engineering_limits table -- this function holds
    NO thresholds of its own. Each margin therefore carries its provenance, so
    the UI can show "Source: CEMA 375 Sec 3" or "Source: VECTOMEC judgement"
    next to the number. A margin against an unsourced constant is an opinion
    with a decimal point.

    Margin is expressed toward the nearest binding bound, as a percentage of
    that bound, so all rows are comparable on one bar chart.
    """
    # result field that each limit_key measures
    FIELD_FOR = {
        "centrifugal_ratio":     "cr",
        "bearing_l10_life":      "L10",
        "chain_safety_factor":   "chain_SF_actual",
        "motor_power_margin":    None,      # computed below
        "startup_torque_margin": None,
        "headshaft_radial_load": "T_total",
        "chute_loading":         None,
        "mtbf_minimum":          None,
    }
    limits = resolve_derived_limits(result, limits)
    rows: List[Dict[str, Any]] = []
    for lim in limits:
        key = lim["limit_key"]
        field = FIELD_FOR.get(key)
        if "_actual_value" in lim:          # derived: value came from the solve
            value = lim["_actual_value"]
        elif field:
            value = result.get(field)
        elif key == "motor_power_margin":
            mk, pt = result.get("motor_kw"), result.get("P_total")
            value = ((float(mk) / float(pt) - 1.0) * 100.0
                     if mk and pt else None)
        elif key == "startup_torque_margin":
            value = _dig(result, "startup.startup_margin")
        elif key == "chute_loading":
            value = _dig(result, "discharge_chute.performance.capacity_check.loading_pct")
        elif key == "mtbf_minimum":
            value = _dig(result, "maintenance.kpis.mtbf_h")
        else:
            value = None
        if not isinstance(value, (int, float)):
            rows.append({"limit_key": key, "parameter": lim["parameter"],
                         "units": lim.get("units"), "value": None, "status": None,
                         "margin_abs": None, "margin_pct": None,
                         "source": _source_of(lim),
                         "decision_type": lim.get("decision_type"),
                         "limit_class": lim.get("limit_class"),
                         "derived_from": lim.get("derived_from"),
                         "confidence": lim.get("confidence")})
            continue

        verdict = evaluate_limit(value, lim)
        v, status = verdict["value"], verdict["status"]
        bound, margin_pct = verdict["bound"], verdict["margin_pct"]
        margin_abs = verdict.get("margin_abs")

        rows.append({
            "limit_key": key, "parameter": lim["parameter"], "units": lim.get("units"),
            "value": round(v, 3), "bound": bound,
            "margin_abs": margin_abs, "margin_pct": margin_pct,
            "status": status, "source": _source_of(lim),
            "decision_type": lim.get("decision_type"),
            "limit_class": lim.get("limit_class"),
            "derived_from": lim.get("derived_from"),
            "confidence": lim.get("confidence"),
        })
    return rows


def _source_of(lim: Dict[str, Any]) -> str:
    """Human-readable provenance. Every decision_type gets an honest label --
    'unsourced' is reserved for a limit that genuinely has none, so it stays a
    meaningful warning rather than the default for anything unrecognised."""
    dt = lim.get("decision_type")
    if dt == "judgement":
        who = lim.get("author") or lim.get("source_name") or "VECTOMEC"
        rev = lim.get("revision")
        return f"{who} -- engineering judgement" + (f" ({rev})" if rev else "")
    if dt == "derived":
        return "Derived from selected component"
    if dt == "estimated":
        return "Estimated -- allowable NOT yet sourced"
    if dt == "measured":
        return f"Measured -- {lim.get('source_name') or 'test data'}"
    if dt == "validated_by_testing":
        return f"Validated by testing -- {lim.get('source_name') or 'internal'}"
    parts = [lim.get("source_name"), lim.get("source_edition"), lim.get("source_section")]
    return " ".join(str(p) for p in parts if p) or "unsourced"


def load_limits(db_path: str, equipment: str = "bucket_elevator") -> List[Dict[str, Any]]:
    """Read active limits from engineering_limits."""
    import sqlite3
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM engineering_limits WHERE is_active=1 AND equipment IN (?,'any')",
            (equipment,))]
    finally:
        con.close()