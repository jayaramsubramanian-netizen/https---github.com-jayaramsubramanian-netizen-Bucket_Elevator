"""
backend/duty_classifier.py -- derive duty class from the operating profile.
═══════════════════════════════════════════════════════════════════════════
Owns NO thresholds. Every rule is read from duty_class_rules, so changing the
classification is a SQL migration, not a code change -- and the classifier can
explain WHY a machine was classified as it was.

    operating profile -> duty_class_rules -> duty class -> required design life
                                                        -> engineering_limits

The output is deliberately not just a class. It carries the matched evidence:

    Duty Classification: HEAVY   (required L10 60,000 h)
      + annual operation 7,800 h/year        weight 3.0
      + starts/hour 18                       weight 2.0
      + shock loading moderate               weight 2.0
      - availability target 96% (SEVERE needs >=97%)

WEIGHTED, NOT FIRST-MATCH. Rules from different classes can fire at once (long
hours but low shock, or short hours with severe shock). The class with the
highest total weight wins; ties resolve to the MORE demanding class, because
under-classifying is the unsafe direction.
"""
from __future__ import annotations
import sqlite3
from typing import Any, Dict, List, Optional


def load_rules(db_path: str) -> Dict[str, Any]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        classes = {r["duty_class"]: dict(r) for r in con.execute(
            "SELECT * FROM duty_classes WHERE is_active=1 ORDER BY rank")}
        rules = [dict(r) for r in con.execute(
            "SELECT * FROM duty_class_rules WHERE is_active=1")]
        return {"classes": classes, "rules": rules}
    finally:
        con.close()


def _matches(value: Any, rule: Dict[str, Any]) -> bool:
    """Same comparison vocabulary as engineering_limits: min|max|range|boolean."""
    if value is None:
        return False
    cmp_ = rule["comparison"]
    vmin, vmax, vtext = rule["value_min"], rule["value_max"], rule["value_text"]

    if cmp_ == "boolean":
        # categorical or true/false match against value_text
        if vtext is None:
            return bool(value)
        if isinstance(value, bool):
            return value is (str(vtext).lower() == "true")
        return str(value).strip().lower() == str(vtext).strip().lower()

    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if cmp_ == "min":
        return vmin is not None and v >= vmin
    if cmp_ == "max":
        return vmax is not None and v <= vmax
    if cmp_ == "range":
        lo_ok = vmin is None or v >= vmin
        hi_ok = vmax is None or v < vmax      # half-open: bands must not overlap
        return lo_ok and hi_ok
    return False


def classify(profile: Dict[str, Any], rule_set: Dict[str, Any]) -> Dict[str, Any]:
    """Classify an operating profile. Returns the class AND its evidence."""
    classes, rules = rule_set["classes"], rule_set["rules"]
    scores: Dict[str, float] = {c: 0.0 for c in classes}
    evidence: Dict[str, List[Dict[str, Any]]] = {c: [] for c in classes}
    unevaluated: List[str] = []

    for rule in rules:
        dc = rule["duty_class"]
        if dc not in scores:
            continue
        value = profile.get(rule["parameter"])
        if value is None:
            unevaluated.append(f"{rule['parameter']} (not supplied)")
            continue
        if _matches(value, rule):
            scores[dc] += float(rule["weighting"])
            evidence[dc].append({
                "parameter": rule["parameter"], "value": value,
                "weighting": rule["weighting"], "rationale": rule["rationale"],
            })

    fired = {c: s for c, s in scores.items() if s > 0}
    if not fired:
        return {
            "duty_class": None, "required_life_h": None,
            "reason": "No classification rule matched the supplied profile.",
            "scores": scores, "evidence": {}, "unevaluated": sorted(set(unevaluated)),
        }

    # highest score wins; TIE -> the MORE demanding class, since
    # under-classifying is the unsafe direction
    best = max(fired.items(), key=lambda kv: (kv[1], classes[kv[0]]["rank"]))[0]
    cls = classes[best]
    return {
        "duty_class": best,
        "rank": cls["rank"],
        "description": cls["description"],
        "required_life_h": cls["target_design_life_h"],
        "scores": scores,
        "evidence": evidence[best],
        "other_evidence": {c: e for c, e in evidence.items() if e and c != best},
        "unevaluated": sorted(set(unevaluated)),
        "source": f"{cls.get('source_name')} {cls.get('source_revision') or ''}".strip(),
        "is_judgement": cls.get("source_type") == "judgement",
    }


def explain(result: Dict[str, Any]) -> str:
    """Human-readable reasoning -- what the UI and the report show."""
    if not result.get("duty_class"):
        return result.get("reason", "unclassified")
    lines = [f"Duty Classification: {result['duty_class']} "
             f"({result['description']}) — required L10 "
             f"{result['required_life_h']:,.0f} h"]
    for e in result["evidence"]:
        lines.append(f"  + {e['parameter']} = {e['value']}  (weight {e['weighting']})")
        lines.append(f"      {e['rationale']}")
    if result.get("other_evidence"):
        lines.append("  considered but not governing:")
        for c, evs in result["other_evidence"].items():
            for e in evs:
                lines.append(f"    · {c}: {e['parameter']} = {e['value']}")
    if result.get("unevaluated"):
        lines.append(f"  not supplied: {', '.join(result['unevaluated'])}")
    if result.get("is_judgement"):
        lines.append(f"  Source: {result['source']} (engineering judgement — "
                     f"no published standard defines these bands)")
    return "\n".join(lines)