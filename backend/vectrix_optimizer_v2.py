"""
VECTRIX™ — Optimizer v2: true multi-objective constrained optimization (NSGA-II)
═══════════════════════════════════════════════════════════════════════════════
Replaces the brute-force grid-search + weighted-sum-score optimizer
(calculations.py::run_optimizer(), left in place and unchanged for now so the
existing /api/bucket-elevator/optimize endpoint keeps working during review)
with a genuine multi-objective constrained search, per Jay's direction
(2026-06 design discussion):

  A. Material discharge-type/CR preference is a STRONG DEFAULT, not a hard
     wall — implemented as an extra minimisation objective (cr_dev: distance
     from the material's preferred CR target range), not a search-space
     filter. A non-preferred bucket can still win if it dominates decisively
     on the other objectives.
  B. Boundary-condition data lives as literal per-material columns in
     materials.py (pref_discharge_type / pref_bucket_style / pref_cr_min/max)
     rather than a category table or separate policy file.
  C. NSGA-II (derivative-free) instead of classical continuous NLP. Verified
     empirically (see findings log #21) that solve_elevator() is genuinely
     non-smooth in its continuous inputs — gradient-based scipy solvers
     (SLSQP, trust-constr) converge falsely after near-zero movement, giving
     a different "optimum" purely as an artifact of starting point. NSGA-II
     never computes a gradient, so it isn't fooled by the catalogue-snapping
     discontinuities (motor size, shaft diameter, bearing class, etc.).
  D. Output is a genuine Pareto-efficient front across real objectives, not
     a single weighted-sum score.

Decision variables (round 2, 2026-06): bucket series + chain strand count
(categorical), RPM + fill (continuous) -- AND, new this round, head pulley
diameter (D_mm) and boot pulley diameter (boot_D_mm), now also searched
rather than inherited fixed from base_input. boot_pulley_same_as_head is
explicitly forced False for every candidate so the independently-searched
boot_D_mm actually takes effect (otherwise calculations.py would silently
override it back to D_mm). Sprocket tooth counts are NOT separately
searched -- they stay on their existing "0 = auto-derive from diameter"
default, which is the same relationship the round-5 sprocket work already
established as correct; adding them as extra free variables would mostly
re-explore the same diameter space through a different parameterisation.

Single source of truth: every candidate is evaluated through the REAL
solve_elevator() (confirmed ~1.2ms/call — see findings log), not duplicated
physics. Constraints are read directly from solve_elevator()'s own checks[]
array (any fail-type check ⇒ infeasible) wherever that coverage already
exists, plus three additions that are NOT currently caught by any existing
check (see findings log #19, #22):
  - bucket style / conveyor type compatibility (e.g. "SC is CHAIN ONLY")
  - an absolute bearing-life floor (20,000h — matches the existing warn()
    threshold in calculations.py, just promoted to a hard optimizer floor)
  - boot pulley diameter <= head pulley diameter (real constraint, not just
    a flagged note -- added per Jay's explicit direction that boot > head
    isn't practical design, once D_mm/boot_D_mm became search variables)

Objectives (all minimised; L10 is negated to express "maximise life"):
  F0  motor_kw          — energy / operating cost proxy
  F1  R_headshaft_N     — structural load proxy (drives shaft/pulley/casing size)
  F2  -L10_h            — bearing life (maximise)
  F3  cr_deviation      — distance outside the material's preferred CR range
                          (this is the "strong default" mechanism for A)

Known limitation (flagged in findings log, not yet fixed): solve_elevator()
can raise an uncaught ValueError ("math domain error") under extreme-load
boot-pulley end-disc geometry (structural.py, negative arm). This optimizer
catches it defensively and scores it as maximally infeasible, but the root
cause is a separate latent bug in the core calc engine, not introduced here.
"""
import time
import warnings

from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Real, Choice
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.mixed import (
    MixedVariableMating, MixedVariableSampling, MixedVariableDuplicateElimination,
)
from pymoo.optimize import minimize as pymoo_minimize

from calculations import solve_elevator, BUCKET_SERIES
from models import BucketElevatorInput
from materials import get_material

_BUCKET_IDS = [b["id"] for b in BUCKET_SERIES]
L10_FLOOR_H = 20_000.0          # matches calculations.py's existing warn() threshold
RPM_BOUNDS  = (20.0, 300.0)
FILL_BOUNDS = (50.0, 95.0)
STRAND_OPTIONS = [1, 2, 3, 4]    # matches models.py chain_n_strands ge=1,le=4
# New this round -- matches models.py BucketElevatorInput.D_mm / .boot_pulley_D_mm
# exactly (ge=100,le=1500 / ge=100,le=1000), not invented bounds.
D_MM_BOUNDS      = (100.0, 1500.0)
BOOT_D_MM_BOUNDS = (100.0, 1000.0)
# #22 (remaining scope, per findings log): head/boot sprocket teeth as real
# search variables, not just the diameter<->teeth relationship that was
# already fixed. Matches models.py's chain_sprocket_teeth/chain_boot_
# sprocket_teeth (ge=0,le=32) -- excluding 0 from the searchable set since
# 0 means "auto" (diameter-derived), which isn't a distinct point to search,
# it's the absence of an explicit choice. 6 as a practical floor: CEMA-class
# sprockets below that have enough chordal/polygon action to be impractical
# at this scale, not a value worth the optimizer wasting evaluations on.
SPROCKET_TEETH_OPTIONS = list(range(6, 33))   # 6..32 inclusive

# Penalty assigned to a candidate that raises an exception inside
# solve_elevator() (e.g. the boot-pulley end-disc domain error under extreme
# loads) -- large enough to always lose to any successfully-evaluated point,
# without using inf/nan which some pymoo internals handle poorly.
_CRASH_PENALTY = 1.0e6


class ElevatorOptProblem(ElementwiseProblem):
    """Mixed discrete(bucket, chain strands, sprocket teeth)/continuous(rpm,
    fill, D_mm, boot_D_mm) problem, evaluated through the real solver. See
    module docstring for objectives and constraints."""

    def __init__(self, base_input: dict, mat: dict):
        variables = {
            "bucket":      Choice(options=_BUCKET_IDS),
            "rpm":         Real(bounds=RPM_BOUNDS),
            "fill":        Real(bounds=FILL_BOUNDS),
            "n_strands":   Choice(options=STRAND_OPTIONS),
            "D_mm":        Real(bounds=D_MM_BOUNDS),
            "boot_D_mm":   Real(bounds=BOOT_D_MM_BOUNDS),
            "head_teeth":  Choice(options=SPROCKET_TEETH_OPTIONS),
            "boot_teeth":  Choice(options=SPROCKET_TEETH_OPTIONS),
        }
        super().__init__(vars=variables, n_obj=4, n_ieq_constr=6)
        self.base_input = base_input
        self.mat = mat

    def _evaluate(self, X, out, *args, **kwargs):
        payload = dict(self.base_input)
        payload.update(
            auto_bucket=False,
            bucket_id=X["bucket"],
            n_rpm=float(X["rpm"]),
            fill_pct=float(X["fill"]),
            chain_n_strands=int(X["n_strands"]),
            D_mm=float(X["D_mm"]),
            boot_pulley_D_mm=float(X["boot_D_mm"]),
            # Forced False: otherwise calculations.py would silently override
            # the independently-searched boot_D_mm back to D_mm whenever
            # base_input happened to have this set, defeating the search.
            boot_pulley_same_as_head=False,
            # #22: only meaningful in chain mode (sprocket_geometry() is only
            # called inside calculations.py's is_chain branch -- same as how
            # chain_n_strands above is harmlessly unused in belt mode), but
            # included unconditionally for every run, matching n_strands'
            # own existing precedent rather than branching the variable set
            # by conveyor_type.
            chain_sprocket_teeth=int(X["head_teeth"]),
            chain_boot_sprocket_teeth=int(X["boot_teeth"]),
        )
        # FIX (Jay's direction: "add constraint, not practical design"): the
        # search previously had nothing tying boot diameter to head diameter,
        # so some Pareto points showed boot_D_mm > D_mm -- mathematically
        # valid given the objectives/constraints at the time, but not how a
        # real elevator is built (boot/tail pulley is normally the same size
        # or smaller than the head pulley). Added as a real inequality
        # constraint (continuous violation magnitude, not just binary --
        # gives the search a graded signal to climb down, same pattern as
        # l10_violation below), not merely a bound tweak, since the bound on
        # boot_D_mm needs to stay wide for cases where D_mm itself is small.
        boot_diameter_violation = max(0.0, float(X["boot_D_mm"]) - float(X["D_mm"]))
        try:
            inp = BucketElevatorInput(**payload)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = solve_elevator(inp)
        except Exception:
            out["F"] = [_CRASH_PENALTY] * 4
            out["G"] = [_CRASH_PENALTY] * 4
            return

        checks = r.get("checks", []) or []
        fail_count = float(sum(1 for c in checks if c.get("type") == "fail"))

        is_chain = bool(r.get("is_chain", False))
        bucket   = r.get("bucket", {}) or {}
        bstyle   = (bucket.get("style") or "").upper()
        # "SC is CHAIN ONLY — not compatible with belt mount" (bucket_recommendation()
        # notes this but nothing previously enforced it -- see findings log #19).
        sc_belt_violation = 1.0 if (bstyle == "SC" and not is_chain) else 0.0

        L10 = float(r.get("L10") or 0.0)
        l10_violation = max(0.0, L10_FLOOR_H - L10)

        # FIX (found during a backend-sync review, not previously flagged):
        # D_mm and boot_D_mm became independent search variables this
        # round, but only the HEAD shaft's L10 was ever floor-constrained.
        # The boot bearing has its own real, computed life (boot_pulley.
        # L10_boot_h) -- confirmed directly it only ever produces a warn()
        # in calculations.py, never a fail(), so it was invisible to the
        # fail_count constraint below too. A Pareto point could pick a
        # boot diameter that tanks boot bearing life with nothing to catch
        # it. Same floor, same violation-magnitude pattern as the head
        # shaft's l10_violation just above -- not a new mechanism.
        boot_pulley = r.get("boot_pulley") or {}
        L10_boot = float(boot_pulley.get("L10_boot_h") or 0.0)
        l10_boot_violation = max(0.0, L10_FLOOR_H - L10_boot)

        # FIX (same review): startup_margin/belt_rated_N (belt mode only)
        # are real computed quantities (calculations.py, startup_dyn dict)
        # but confirmed they never get a fail()/warn() appended to checks[]
        # anywhere -- so this safety margin was invisible to fail_count
        # too. Chain mode doesn't compute these fields at all (confirmed:
        # only set `if not is_chain`), so this constraint is a no-op
        # (violation=0) for chain runs rather than penalising them for a
        # quantity that doesn't apply.
        startup_dyn = r.get("startup_dynamic") or {}
        startup_margin = startup_dyn.get("startup_margin")
        startup_margin_violation = (
            max(0.0, 1.0 - float(startup_margin)) if startup_margin is not None else 0.0
        )

        cr = float(r.get("cr") or 0.0)
        lo, hi = self.mat["pref_cr_min"], self.mat["pref_cr_max"]
        cr_dev = 0.0 if lo <= cr <= hi else min(abs(cr - lo), abs(cr - hi))

        motor_kw = float(r.get("motor_kw") or _CRASH_PENALTY)
        R_head   = float(r.get("R_headshaft") or _CRASH_PENALTY)

        out["F"] = [motor_kw, R_head, -L10, cr_dev]
        out["G"] = [fail_count, sc_belt_violation, l10_violation, boot_diameter_violation,
                    l10_boot_violation, startup_margin_violation]


def _to_native(x):
    """numpy scalar -> native python, for clean JSON serialisation."""
    if hasattr(x, "item"):
        return x.item()
    return x


def run_nsga2_optimizer(
    base_input: dict,
    pop_size: int = 200,
    n_gen: int = 100,
    seed: int = 1,
) -> dict:
    """Run the NSGA-II multi-objective search and return a JSON-serialisable
    dict: the Pareto-efficient front plus run metadata. Raises ValueError if
    mat_id is missing/unknown (caller should map to a 4xx response).

    Default pop_size/n_gen bumped from 150/80 (~16s) to 200/100 (~29s) this
    round -- the search space grew from 4 to 6 decision variables (added
    D_mm/boot_D_mm), and side-by-side testing showed the larger budget finds
    a meaningfully denser/richer Pareto front (more intermediate tradeoff
    points) even though the best value at each individual objective's
    extreme converges similarly either way. ~29s is still reasonable for an
    interactive "optimize" action with a loading state, but this is a real
    runtime tradeoff worth knowing about, not a free improvement -- pass
    explicit pop_size/n_gen to go back to the faster budget if preferred.
    """
    mat_id = base_input.get("mat_id")
    if not mat_id:
        raise ValueError("base_input.mat_id is required")
    mat = get_material(mat_id)

    problem = ElevatorOptProblem(base_input, mat)
    # NSGA2's own type stubs infer overly narrow types for `sampling` and
    # `eliminate_duplicates` (e.g. FloatRandomSampling, bool) purely from their
    # default *values* -- pymoo's __init__ signatures carry no real type
    # annotations. Passing MixedVariable* substitutes is pymoo's own documented
    # pattern for mixed discrete/continuous problems (see pymoo's mixed-variable
    # optimization guide); these are real, correct, runtime-tested arguments
    # (every Pareto-front result in this module was produced this way), the
    # mismatch is a stub gap on pymoo's side, not a logic error here.
    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=MixedVariableSampling(),                              # type: ignore[reportArgumentType]
        mating=MixedVariableMating(
            eliminate_duplicates=MixedVariableDuplicateElimination()), # type: ignore[reportArgumentType]
        eliminate_duplicates=MixedVariableDuplicateElimination(),      # type: ignore[reportArgumentType]
    )

    t0 = time.perf_counter()
    res = pymoo_minimize(problem, algorithm, ("n_gen", n_gen), seed=seed, verbose=False)
    elapsed = time.perf_counter() - t0

    pareto_front = []
    is_chain_run = base_input.get("conveyor_type") == "chain"
    # pymoo's Result sets X/F/G to bare `None` in __init__ and never narrows
    # them in its own type stubs, so checking res.X alone doesn't narrow res.F/
    # res.G for the type checker -- narrow all three explicitly. (At runtime
    # pymoo always populates X/F/G together, never a subset, but check all
    # three anyway rather than asserting that invariant blindly.)
    X, F, G = res.X, res.F, res.G
    if X is not None and F is not None and G is not None:
        for x, f, g in zip(X, F, G):
            feasible = all(gi <= 1e-6 for gi in g)
            point = {
                "bucket_id":        x["bucket"],
                "n_rpm":            round(_to_native(x["rpm"]), 2),
                "fill_pct":         round(_to_native(x["fill"]), 1),
                "chain_n_strands":  (int(_to_native(x["n_strands"]))
                                      if is_chain_run else None),
                "D_mm":             round(_to_native(x["D_mm"]), 0),
                "boot_pulley_D_mm": round(_to_native(x["boot_D_mm"]), 0),
                # #22: only meaningful in chain mode, same display
                # convention as chain_n_strands just above.
                "chain_sprocket_teeth":      (int(_to_native(x["head_teeth"]))
                                               if is_chain_run else None),
                "chain_boot_sprocket_teeth": (int(_to_native(x["boot_teeth"]))
                                               if is_chain_run else None),
                "motor_kw":         round(_to_native(f[0]), 2),
                "R_headshaft_N":    round(_to_native(f[1]), 0),
                "L10_h":            round(_to_native(-f[2]), 0),
                "cr_deviation":     round(_to_native(f[3]), 4),
                "feasible":         bool(feasible),
                # Display-only extras (cr, capacity, speed) -- not used as
                # objectives/constraints, just useful context for a human
                # reviewing the table. Re-running solve_elevator() once more
                # per point (negligible: ~1.2ms x ~100 points) is simpler and
                # more robust than threading extra state through pymoo's
                # internal Result object, which only tracks X/F/G.
                "cr": None, "Q_th": None, "v_ms": None,
                "L10_boot_h": None, "startup_margin": None,
            }
            try:
                _payload = dict(base_input)
                _payload.update(
                    auto_bucket=False, bucket_id=point["bucket_id"],
                    n_rpm=point["n_rpm"], fill_pct=point["fill_pct"],
                    chain_n_strands=(point["chain_n_strands"] or 1),
                    D_mm=point["D_mm"], boot_pulley_D_mm=point["boot_pulley_D_mm"],
                    boot_pulley_same_as_head=False,
                    chain_sprocket_teeth=(point["chain_sprocket_teeth"] or 0),
                    chain_boot_sprocket_teeth=(point["chain_boot_sprocket_teeth"] or 0),
                )
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    _r = solve_elevator(BucketElevatorInput(**_payload))
                point["cr"]    = round(float(_r.get("cr") or 0), 3)
                point["Q_th"]  = round(float(_r.get("Q") or 0), 1)
                point["v_ms"]  = round(float(_r.get("v") or 0), 2)
                # Same display-only reasoning as cr/Q_th/v_ms above -- these
                # are the two quantities newly added as hard constraints
                # (see l10_boot_violation / startup_margin_violation), so
                # showing the actual number alongside is what makes a
                # "feasible: false" row legible rather than a black box.
                _boot = _r.get("boot_pulley") or {}
                if _boot.get("L10_boot_h") is not None:
                    point["L10_boot_h"] = round(float(_boot["L10_boot_h"]), 0)
                _sd = _r.get("startup_dynamic") or {}
                if _sd.get("startup_margin") is not None:
                    point["startup_margin"] = round(float(_sd["startup_margin"]), 2)
            except Exception:
                pass   # display-only -- leave as None rather than fail the point
            pareto_front.append(point)

    return {
        "pareto_front":        pareto_front,
        "n_pareto_points":     len(pareto_front),
        "n_evaluated":         pop_size * n_gen,
        "elapsed_s":           round(elapsed, 2),
        "material_preference": {
            "discharge_type": mat["pref_discharge_type"],
            "bucket_style":   mat["pref_bucket_style"],
            "cr_target_range": [mat["pref_cr_min"], mat["pref_cr_max"]],
        },
    }