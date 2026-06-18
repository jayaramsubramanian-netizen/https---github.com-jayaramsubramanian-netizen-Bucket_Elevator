"""
VECTRIX™ — Bill of Materials Generator
AKSHAYVIPRA EL-MEC · VECTOMEC™

generate_bom(results, inputs) → structured BOM dict

Produces a preliminary fabrication and procurement BOM from the result dict
returned by solve_elevator().  All component specifications come directly from
the calculation outputs — no additional inputs required.

Mass estimates use standard carbon-steel density (7850 kg/m³) and catalogue
values where available (motor, bearings, gearbox).  These are order-of-magnitude
estimates for preliminary budget and weight studies; final fabrication BOM
should be issued by the mechanical discipline engineer.

v1.9.9 CHANGES (BOM/quantities audit)
──────────────────────────────────────
1. Belt length & bucket count now read from the proper geometric calculation
   (belt_length_and_bucket_count() in calculations.py — straight runs + pulley
   half-wraps) instead of the old H_m*2.15 flat approximation.
2. Shaft line item now reflects the ACTUALLY SELECTED shaft_material grade
   (previously always hardcoded "S355JR / C45E" regardless of selection) and
   the ACTUALLY SELECTED section (solid/hollow — previously always computed
   as a solid cylinder even when shaft_section="hollow" was chosen).
3. Hub connection line item now branches on shaft_hub_connection: a keyed
   shaft gets the existing key spec line; a welded shaft gets a new weld
   throat spec line instead (no key — there is no keyway when welded).
4. Bucket line item now reflects bucket_thickness_override_mm when set,
   instead of always using the unmodified catalogue mass.
5. Pulley shell line item now reflects pulley_shell_t_override_mm when set,
   instead of an independent 'typical 10-16mm' estimate disconnected from
   the actual override.
6. NEW: Casing assembly fastener line item (bolt count + size from
   casing_bolt_quantities() in structural.py) — the FASTENERS category was
   defined in this module's docstring and in BOMCard.jsx's display layer
   but was never actually populated by any line item before this version.

BOM categories
──────────────
  SHAFT      Head shaft + keyway/weld
  PULLEY     Head pulley shell, end discs, lagging, boot pulley
  BELT       Belt, buckets, bucket bolts
  DRIVE      Motor, gearbox, coupling guard
  TAKE-UP    Counterweight frame, counterweight ballast, screw take-up (alt)
  CASING     Casing plates, stiffener angles, inspection doors
  CHUTE      Back-plate, side plates, liner, wear bars
  BEARINGS   Head shaft pillow blocks × 2
  FASTENERS  Casing assembly bolts, belt splice, bucket bolt set
"""

import math
from typing import Any

try:
    from .structural import StructuralStressEngine
except ImportError:
    from structural import StructuralStressEngine

# ─── Physical constants ───────────────────────────────────────────────────────
RHO_STEEL  = 7850.0    # kg/m³ — applies to all SHAFT_MATERIALS grades (all
                        # are carbon/alloy steel; density does not vary
                        # meaningfully across A36/1045/4140 for BOM purposes)
RHO_RUBBER = 1200.0    # kg/m³
RHO_AR500  = 7700.0    # kg/m³ (wear-resistant)

# Shaft material display name lookup — mirrors SHAFT_MATERIALS in
# constants.py, kept as a local copy so bom.py has no hard dependency on the
# calculations package import chain (BOM generation should not fail just
# because an unrelated module is mid-edit).
_SHAFT_MATERIAL_LABELS = {
    "A36":     "ASTM A36 Mild Steel",
    "1045_HR": "AISI/SAE 1045 Hot Rolled",
    "1045_CD": "AISI/SAE 1045 Cold Drawn",
    "4140_QT": "AISI/SAE 4140 Quenched & Tempered",
}

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _f(v, dp=1, fb="—"):
    try:
        return round(float(v), dp)
    except (TypeError, ValueError):
        return fb

def _steel_cyl_kg(od_m, id_m, length_m):
    """Mass of a hollow steel cylinder [kg]. id_m=0 for a solid cylinder."""
    area = math.pi / 4.0 * (od_m**2 - id_m**2)
    return area * length_m * RHO_STEEL

def _steel_disc_kg(od_m, id_m, t_m):
    """Mass of a steel disc / annular plate [kg]."""
    area = math.pi / 4.0 * (od_m**2 - id_m**2)
    return area * t_m * RHO_STEEL

def _steel_rect_kg(w_m, h_m, t_m):
    """Mass of a steel flat plate [kg]."""
    return w_m * h_m * t_m * RHO_STEEL

def _next_pos(state):
    state[0] += 1
    return f"{state[0]:02d}"


# ─── Main generator ───────────────────────────────────────────────────────────

def generate_bom(results: dict, inputs: dict) -> dict:
    """
    Generate a structured preliminary Bill of Materials.

    Parameters
    ----------
    results : dict
        Output of solve_elevator()
    inputs  : dict
        BucketElevatorInput dict (or model_dump())

    Returns
    -------
    {
        "items":   [BOMItem, ...],
        "summary": {total_items, total_mass_kg, by_category},
        "notes":   [str, ...],
        "version": "1.0.0",
    }

    BOMItem keys
    ────────────
    pos          str   "01" … "99"
    tag          str   Equipment tag (e.g. "BE-001-SHAFT-001")
    description  str   Plain-English item description
    qty          int   Quantity
    unit         str   "EA" | "SET" | "m" | "kg"
    material     str   Material specification
    standard     str   Applicable standard or grade
    spec         str   Key dimension string
    mass_ea_kg   float Estimated mass per item [kg]
    mass_tot_kg  float qty × mass_ea_kg
    category     str   BOM category code
    notes        str   Advisory or qualification note
    """

    r   = results or {}
    inp = inputs  or {}
    mat = r.get("mat") or r.get("material") or {}
    bkt = r.get("bucket") or {}
    hub = r.get("hub") or {}
    lag = r.get("lagging") or {}
    ed  = r.get("end_disc") or {}
    tg  = r.get("takeup_gravity") or {}
    ts  = r.get("takeup_screw") or {}
    dc  = (r.get("discharge_chute") or {}).get("geometry") or {}
    mnt = (r.get("discharge_chute") or {}).get("maintenance") or {}
    cs  = r.get("casing_stiffener") or {}
    key_check  = r.get("key_check")    # None if welded
    weld_check = r.get("weld_check")   # None if keyed
    pulley_shell_r = r.get("pulley_shell") or {}
    bucket_thickness_r = r.get("bucket_thickness")   # None if no override

    # ── Key dimensions from results ────────────────────────────────────────────
    d_m        = float(r.get("d_mm") or 60)   / 1000.0  # shaft OD [m]
    D_m        = float(inp.get("D_mm") or 500)/ 1000.0  # head pulley OD [m]
    BW_m       = float(r.get("belt_w") or 400)/ 1000.0  # belt width [m]
    H_m        = float(inp.get("H_m")  or 25)           # lift height [m]
    n_rpm      = float(inp.get("n_rpm") or 60)
    motor_kw   = float(r.get("motor_kw") or r.get("motor_kW") or 11)
    span_m     = float(r.get("shaft_span_mm") or (BW_m * 1000 + 330)) / 1000.0
    casing_t_m = float(r.get("casing_t_mm") or 5) / 1000.0

    # v1.9.9 — Shaft material grade & section (was always hardcoded
    # "S355JR / C45E" + solid cylinder regardless of selection).
    shaft_mat_id     = r.get("shaft_material") or "A36"
    shaft_mat_label  = r.get("shaft_material_name") or _SHAFT_MATERIAL_LABELS.get(
        shaft_mat_id, shaft_mat_id)
    shaft_section    = r.get("shaft_section") or "solid"
    shaft_bore_ratio = float(r.get("shaft_bore_ratio") or 0.0)
    d_inner_m        = (d_m * shaft_bore_ratio) if shaft_section == "hollow" else 0.0
    hub_connection   = r.get("shaft_hub_connection") or "keyed"

    # Hub / key
    hub_od_m   = float(hub.get("d_hub_mm") or D_m * 1000 * 0.7) / 1000.0
    hub_len_m  = float(hub.get("L_hub_mm") or span_m * 0.15)    / 1000.0

    # End disc
    ed_t_m = float(ed.get("t_governing_mm") or 12) * 1.2 / 1000.0   # +20% spec
    # v1.9.9 — Pulley shell thickness now reads the actual calculated/override
    # value from pulley_shell_thickness() rather than an independent
    # 'typical 10-16mm' estimate disconnected from the real design.
    shell_t_m = float(pulley_shell_r.get("t_use_mm") or max(10.0, casing_t_m * 2000)) / 1000.0

    # Lagging
    lag_t_m  = float(lag.get("thickness_mm") or 12) / 1000.0
    lag_type = (lag.get("lagging_type") or "rubber_herringbone").replace("_", " ")

    # v1.9.9 — Belt length & bucket count now read from
    # belt_length_and_bucket_count() (proper geometry: straight runs + pulley
    # half-wraps + splice allowance) instead of the old H_m*2.15 flat
    # approximation, which ignored actual pulley diameters entirely.
    belt_ply       = r.get("belt_ply") or "4 PLY"
    belt_len_m     = float(r.get("belt_length_total_m") or (H_m * 2.15))
    n_buckets      = int(r.get("n_buckets") or max(1, int(H_m * 2.15 / 0.25)))
    spacing_m      = float(r.get("spacing_actual_m") or r.get("spacing") or 0.25)

    # Buckets
    bkt_w_m    = float(bkt.get("W") or 250) / 1000.0
    bkt_h_m    = float(bkt.get("H") or 200) / 1000.0
    bkt_p_m    = float(bkt.get("P") or 150) / 1000.0
    # v1.9.9 — bucket_mass_kg already reflects bucket_thickness_override_mm
    # (calculations.py applies the scaling before exposing this field), so
    # no separate adjustment is needed here — just don't silently ignore it.
    bkt_mass   = float(r.get("bucket_mass_kg") or 2.5)

    # Counterweight
    cw_kg = float(tg.get("W_counterweight_kg_gross") or 150)

    # Chute
    chute_w_m  = float(dc.get("spout_width_mm") or (bkt_w_m * 1000 + 100)) / 1000.0
    liner_mat  = mnt.get("liner_material") or "mild steel"
    liner_t_m  = float(mnt.get("liner_thickness_mm") or 10) / 1000.0

    # Casing: 4 faces × height × plate thickness, plus stiffeners at recommended pitch
    stiff_pitch_m = float(cs.get("recommended_mm") or 600) / 1000.0
    n_stiff_sets  = max(1, int(H_m / stiff_pitch_m))
    # 2 × casing faces × face area (approx)
    cas_area_m2   = 2.0 * (BW_m + 0.12) * H_m + 2.0 * 0.20 * H_m

    # ── Position counter ──────────────────────────────────────────────────────
    pos = [0]
    items = []

    def add(description, qty, unit, material, standard, spec,
            mass_ea_kg, category, notes="", tag_suffix=None):
        p = _next_pos(pos)
        tag = f"BE-001-{category}-{p}"
        if tag_suffix:
            tag = f"BE-001-{tag_suffix}"
        m_tot = round(float(mass_ea_kg) * qty, 1)
        items.append({
            "pos":         p,
            "tag":         tag,
            "description": description,
            "qty":         qty,
            "unit":        unit,
            "material":    material,
            "standard":    standard,
            "spec":        spec,
            "mass_ea_kg":  round(float(mass_ea_kg), 1),
            "mass_tot_kg": m_tot,
            "category":    category,
            "notes":       notes,
        })

    # ══════════════════════════════════════════════════════════════════════════
    # SHAFT
    # ══════════════════════════════════════════════════════════════════════════
    # v1.9.9 — was always _steel_cyl_kg(d_m, 0.0, ...) i.e. solid, even when
    # shaft_section="hollow" was selected; now uses the actual bore. Material
    # spec now reflects the actually selected shaft_material grade rather
    # than a hardcoded "S355JR / C45E" regardless of selection.
    shaft_mass = _steel_cyl_kg(d_m, d_inner_m, span_m * 1.25)   # +25% for journal steps
    section_spec = (
        f"Ø{r.get('d_mm'):.0f} (bore Ø{d_inner_m*1000:.0f}) × {span_m*1250:.0f} mm lg"
        if shaft_section == "hollow"
        else f"Ø{r.get('d_mm'):.0f} × {span_m*1250:.0f} mm lg"
    )
    shaft_note = (
        f"Governed by {r.get('governed_by','stress')}; "
        f"deflection {_f(r.get('d_deflect_mm'))} mm"
    )
    if shaft_section == "hollow":
        shaft_note += f"; hollow, bore ratio {shaft_bore_ratio:.2f}, ~{r.get('shaft_mass_saving_pct',0):.0f}% mass saving vs solid"
    add(f"Head shaft ({'hollow' if shaft_section=='hollow' else 'solid'} section)",
        1, "EA",
        shaft_mat_label,
        "ASME B17.1 / CEMA 375 §4",
        section_spec,
        shaft_mass,
        "SHAFT",
        shaft_note)

    # v1.9.9 — Hub connection: keyed gets the existing key spec line; welded
    # gets a weld throat spec line instead (no keyway when welded).
    if hub_connection == "welded" and weld_check:
        add("Head pulley hub — welded connection",
            1, "EA",
            "E70xx weld metal (AWS D1.1)",
            "AWS D1.1",
            f"Fillet throat {weld_check.get('t_throat_mm','—')}mm, full 360° around shaft OD",
            0.0,   # weld metal mass is negligible vs. parent components; not separately tracked
            "SHAFT",
            f"Governed by {weld_check.get('governed_by','torsion').replace('_',' ')}; "
            f"no keyway — field pulley removal requires re-welding")
    elif key_check:
        add("Head shaft key",
            1, "EA",
            "AISI 1018 (standard key stock)",
            "ASME B17.1",
            f"{key_check.get('b_key_mm','—')}×{key_check.get('h_key_mm','—')}mm × {hub_len_m*1000:.0f}mm lg",
            0.0,   # key mass negligible vs shaft/hub; not separately tracked
            "SHAFT",
            key_check.get("recommendation", ""))

    # ══════════════════════════════════════════════════════════════════════════
    # PULLEY
    # ══════════════════════════════════════════════════════════════════════════
    shell_mass = _steel_cyl_kg(D_m, D_m - 2*shell_t_m, BW_m + 0.050)
    add("Head pulley shell",
        1, "EA",
        "S355JR",
        "EN 10025-2",
        f"Ø{inp.get('D_mm')} × {BW_m*1000+50:.0f} mm F2F, t={shell_t_m*1000:.0f}mm",
        shell_mass,
        "PULLEY")

    disc_mass = _steel_disc_kg(D_m - 2*shell_t_m, d_m, ed_t_m)
    add("Head pulley end disc (annular plate)",
        2, "EA",
        "S355JR",
        "EN 10025-2",
        f"OD={D_m*1000-2*shell_t_m*1000:.0f}mm  ID={d_m*1000:.0f}mm  t={ed_t_m*1000:.0f}mm",
        disc_mass,
        "PULLEY",
        f"Specify {ed_t_m*1000:.0f}mm (+20% over {ed.get('t_governing_mm','—')}mm calc minimum)")

    lag_mass = (math.pi * D_m * (BW_m + 0.050) * lag_t_m * RHO_RUBBER)
    add(f"Head pulley lagging — {lag_type}",
        1, "EA",
        "NR/SBR rubber" if "rubber" in lag_type else "Ceramic",
        "CEMA 375 §4",
        f"t={lag_t_m*1000:.0f}mm  OD={D_m*1000+2*lag_t_m*1000:.0f}mm",
        lag_mass,
        "PULLEY",
        f"μ operating = {lag.get('mu_operating','—')}")

    # Boot pulley (assume similar to head, 72% dia)
    D_boot_m   = float(inp.get("boot_pulley_D_mm") or D_m * 720) / 1000.0
    boot_shell = _steel_cyl_kg(D_boot_m, D_boot_m - shell_t_m, BW_m + 0.050)
    add("Boot / tail pulley assembly (shell + discs)",
        1, "EA",
        "S355JR",
        "EN 10025-2",
        f"Ø{D_boot_m*1000:.0f} × {BW_m*1000+50:.0f} mm F2F",
        boot_shell * 1.35,   # × 1.35 for discs and shaft stub
        "PULLEY",
        "Take-up point; snub or gravity arrangement")

    # ══════════════════════════════════════════════════════════════════════════
    # BELT & BUCKETS
    # ══════════════════════════════════════════════════════════════════════════
    belt_kgm = 8.0   # kg/m typical EP belt (matches BELT_WEIGHT_DEFAULT)
    add(f"Elevator belt — {belt_ply}",
        1, "SET",
        f"EP {belt_ply} rubber conveyor belt",
        "IS 1891 / DIN 22102",
        f"BW={BW_m*1000:.0f}mm  L={belt_len_m:.0f}m  mass≈{belt_len_m*belt_kgm:.0f}kg",
        belt_len_m * belt_kgm,
        "BELT",
        "Include 2 splices; splice type per belt manufacturer recommendation")

    bucket_note = f"Spacing = {spacing_m*1000:.0f}mm c/c  ×{n_buckets} off"
    if bucket_thickness_r:
        bucket_note += (
            f"; plate {bucket_thickness_r.get('t_override_mm','—')}mm specified "
            f"vs {bucket_thickness_r.get('t_implied_mm','—')}mm catalogue standard"
        )
    add(f"Buckets — Series {bkt.get('id','—')}  {bkt.get('W','—')}×{bkt.get('H','—')}mm",
        n_buckets, "EA",
        "HDPE / cast steel" if bkt.get("id","B") in ("HF","AA") else "HDPE",
        "CEMA 375 §6",
        f"{bkt.get('W','—')}×{bkt.get('H','—')}×{bkt.get('P','—')}mm  {bkt.get('V','—')}L",
        bkt_mass,
        "BELT",
        bucket_note)

    bolt_set_mass = n_buckets * 0.085   # ~85g per bucket bolt set (M12 × 2)
    add("Bucket attachment bolt set — M12 stainless",
        n_buckets, "SET",
        "A2-70 stainless steel",
        "ISO 3506",
        "M12 × 35 HHB + washer + nylock nut (2 per bucket)",
        0.085,
        "BELT",
        "Replace at every bucket change; inspect at 8,000h")

    # ══════════════════════════════════════════════════════════════════════════
    # DRIVE
    # ══════════════════════════════════════════════════════════════════════════
    # Motor mass estimate: ~6 kg/kW for IE3 frames up to 55kW
    motor_mass = motor_kw * 6.2
    add(f"Drive motor — {motor_kw:.0f} kW IE3",
        1, "EA",
        "IE3 efficiency class",
        "IEC 60034 / IS 325",
        f"{motor_kw:.0f}kW  {4*n_rpm:.0f}/{2*n_rpm:.0f} rpm  B3/B5 frame",
        motor_mass,
        "DRIVE",
        f"SF = {inp.get('sf',1.25)}; confirm frame and mounting with supplier")

    # Gearbox mass estimate: ~10 kg/kW for helical-bevel
    gbx_mass = motor_kw * 10.5
    ratio = 1450.0 / max(n_rpm, 1)
    add("Helical-bevel gearbox",
        1, "EA",
        "Cast iron housing / alloy steel gears",
        "IS 3734 / DIN 3990",
        f"i = {ratio:.1f}:1  T_out = {_f(r.get('T_Nm'))} Nm  {n_rpm:.0f} rpm output",
        gbx_mass,
        "DRIVE",
        "Confirm service factor with gearbox manufacturer; oil bath lubrication")

    # ══════════════════════════════════════════════════════════════════════════
    # TAKE-UP
    # ══════════════════════════════════════════════════════════════════════════
    cw_frame_mass = cw_kg * 0.30   # frame ≈ 30% of ballast
    add("Gravity take-up counterweight (ballast + frame)",
        1, "SET",
        "Cast iron / concrete ballast; S275 frame",
        "CEMA 375 §4",
        f"Total mass = {cw_kg:.0f} kg  "
        f"(frame {cw_frame_mass:.0f} kg + ballast {cw_kg-cw_frame_mass:.0f} kg)",
        cw_kg,
        "TAKE-UP",
        f"Travel = {round(float(tg.get('travel_m',0))*1000)} mm min; "
        f"allow 20% headroom for field adjustment")

    # ══════════════════════════════════════════════════════════════════════════
    # CASING
    # ══════════════════════════════════════════════════════════════════════════
    casing_mass = _steel_rect_kg(cas_area_m2, 1.0, casing_t_m)  # area × unit × t
    add("Casing plate (fabricated panels)",
        1, "SET",
        "S275JR",
        "EN 10025-2",
        f"t = {casing_t_m*1000:.0f}mm  area ≈ {cas_area_m2:.0f} m²",
        casing_mass,
        "CASING",
        f"Stiffener pitch = {stiff_pitch_m*1000:.0f}mm; "
        f"min {n_stiff_sets} stiffener sets over height")

    # v1.9.9 — NEW: casing assembly fasteners. FASTENERS was defined as a
    # category in this module's docstring and in BOMCard.jsx's display
    # layer, but no line item ever actually populated it before this
    # version — this was a genuine gap, not a refinement of an existing item.
    #
    # Reads casing_bolts from solve_elevator()'s result dict (added at the
    # same time as this BOM feature) rather than recomputing independently —
    # avoids the two consumers silently drifting if the bolt-pitch model is
    # ever tuned in one place and not the other. Falls back to a direct call
    # only if an older results dict without the field is passed in.
    casing_bolts = r.get("casing_bolts")
    if not casing_bolts:
        casing_bolts = StructuralStressEngine.casing_bolt_quantities(
            height_m=H_m, belt_width_mm=BW_m * 1000.0,
            plate_thickness_mm=casing_t_m * 1000.0, n_stiffener_sets=n_stiff_sets,
        )
    bolt_mass_ea = {"M8": 0.020, "M10": 0.035, "M12": 0.055, "M16": 0.110}.get(
        casing_bolts["bolt_size"], 0.035)
    add(f"Casing assembly bolt set — {casing_bolts['bolt_size']}",
        casing_bolts["n_bolts_total"], "SET",
        "Zinc-plated steel, Class 8.8",
        "ISO 4017 / ISO 4032",
        f"{casing_bolts['bolt_size']} hex bolt + nut + washer, panel-to-panel "
        f"and panel-to-stiffener fixing",
        bolt_mass_ea,
        "FASTENERS",
        f"{casing_bolts['n_bolts_seams']} seam + {casing_bolts['n_bolts_stiffeners']} "
        f"stiffener-band bolts; first-order fabrication estimate, not a "
        f"structural connection design — confirm against actual panel module size")

    # ══════════════════════════════════════════════════════════════════════════
    # BEARINGS
    # ══════════════════════════════════════════════════════════════════════════
    # Bearing mass estimate based on shaft diameter
    bearing_mass = 0.006 * (d_m * 1000)**1.5   # empirical; ~2kg for 60mm, ~4kg for 80mm
    add("Head shaft pillow block bearing assembly",
        2, "EA",
        "Chrome steel (GCr15)",
        "ISO 281 / IS 3823",
        f"Shaft Ø{d_m*1000:.0f}mm  "
        f"L10 = {float(r.get('L10',0)):,.0f}h at {n_rpm:.0f}rpm",
        bearing_mass,
        "BEARINGS",
        "SNL plummer block with labyrinth seal; grease-lubricated")

    # ══════════════════════════════════════════════════════════════════════════
    # DISCHARGE CHUTE
    # ══════════════════════════════════════════════════════════════════════════
    chute_back_mass = _steel_rect_kg(chute_w_m + 0.20, 0.60, 0.008)  # 8mm mild steel
    liner_mass      = _steel_rect_kg(chute_w_m + 0.20, 0.60, liner_t_m) * (
        RHO_AR500 / RHO_STEEL if "AR" in liner_mat.upper() else 1.0
    )
    add("Discharge chute fabrication (back, side plates)",
        1, "SET",
        "S275JR",
        "EN 10025-2",
        f"W={chute_w_m*1000+200:.0f}mm  angle={dc.get('back_plate_angle_deg','—')}°",
        chute_back_mass,
        "CHUTE")

    add(f"Chute wear liner — {liner_mat}",
        1, "SET",
        liner_mat,
        "ASTM A514 / Hardox" if "AR" in liner_mat.upper() else "IS 2062",
        f"t={mnt.get('liner_thickness_mm','—')}mm  W={chute_w_m*1000+200:.0f}mm",
        liner_mass,
        "CHUTE",
        f"Wear index = {mnt.get('wear_index','—')}  ({mnt.get('wear_rating','—')}); "
        f"plugging risk = {mnt.get('plugging_risk','LOW')}")

    # ══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    total_mass = sum(i["mass_tot_kg"] for i in items
                     if isinstance(i["mass_tot_kg"], (int, float)))
    by_cat: dict[str, Any] = {}
    for item in items:
        cat = item["category"]
        if cat not in by_cat:
            by_cat[cat] = {"count": 0, "mass_kg": 0.0}
        by_cat[cat]["count"]   += item["qty"]
        by_cat[cat]["mass_kg"] = round(
            by_cat[cat]["mass_kg"] + (item["mass_tot_kg"]
            if isinstance(item["mass_tot_kg"], (int, float)) else 0), 1
        )

    notes = [
        "Mass estimates are preliminary (±25%) for budget and logistics study only.",
        "Final BOM to be issued by mechanical discipline after detailed design.",
        "Material specifications are minimum grades; upgrade for corrosive environments.",
        "Quantities include no construction allowance — add 2–5% wastage for plates.",
        "Bearing L10 from ISO 281 basic dynamic capacity calculation at constant load.",
        "Belt length includes splice allowance; bucket count derived from actual "
        "geometric belt length, not a flat height-based approximation.",
        "Casing fastener quantities are a first-order fabrication estimate based on "
        "panel perimeter and stiffener band count — confirm against actual panel "
        "module size and shop joining practice.",
    ]

    return {
        "items":   items,
        "summary": {
            "total_items":  len(items),
            "total_mass_kg": round(total_mass, 1),
            "by_category":  by_cat,
        },
        "notes":   notes,
        "version": "1.9.9",
    }