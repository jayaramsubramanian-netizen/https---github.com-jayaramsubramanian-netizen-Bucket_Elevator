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

BOM categories
──────────────
  SHAFT      Head shaft + keyway
  PULLEY     Head pulley shell, end discs, lagging, boot pulley
  BELT       Belt, buckets, bucket bolts
  DRIVE      Motor, gearbox, coupling guard
  TAKE-UP    Counterweight frame, counterweight ballast, screw take-up (alt)
  CASING     Casing plates, stiffener angles, inspection doors
  CHUTE      Back-plate, side plates, liner, wear bars
  BEARINGS   Head shaft pillow blocks × 2
  FASTENERS  Anchor bolts, belt splice, bucket bolt set
"""

import math
from typing import Any

# ─── Physical constants ───────────────────────────────────────────────────────
RHO_STEEL  = 7850.0    # kg/m³
RHO_RUBBER = 1200.0    # kg/m³
RHO_AR500  = 7700.0    # kg/m³ (wear-resistant)

# ─── Helpers ─────────────────────────────────────────────────────────────────
def _f(v, dp=1, fb="—"):
    try:
        return round(float(v), dp)
    except (TypeError, ValueError):
        return fb

def _steel_cyl_kg(od_m, id_m, length_m):
    """Mass of a hollow steel cylinder [kg]."""
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

    # ── Key dimensions from results ────────────────────────────────────────────
    d_m        = float(r.get("d_mm") or 60)   / 1000.0  # shaft OD [m]
    D_m        = float(inp.get("D_mm") or 500)/ 1000.0  # head pulley OD [m]
    BW_m       = float(r.get("belt_w") or 400)/ 1000.0  # belt width [m]
    H_m        = float(inp.get("H_m")  or 25)           # lift height [m]
    n_rpm      = float(inp.get("n_rpm") or 60)
    motor_kw   = float(r.get("motor_kw") or r.get("motor_kW") or 11)
    span_m     = float(r.get("shaft_span_mm") or (BW_m * 1000 + 330)) / 1000.0
    casing_t_m = float(r.get("casing_t_mm") or 5) / 1000.0

    # Hub / key
    hub_od_m   = float(hub.get("d_hub_mm") or D_m * 1000 * 0.7) / 1000.0
    hub_len_m  = float(hub.get("L_hub_mm") or span_m * 0.15)    / 1000.0

    # End disc
    ed_t_m = float(ed.get("t_governing_mm") or 12) * 1.2 / 1000.0   # +20% spec
    # Shell thickness — typical 10–16mm for head pulley
    shell_t_m = max(0.010, casing_t_m * 2)

    # Lagging
    lag_t_m  = float(lag.get("thickness_mm") or 12) / 1000.0
    lag_type = (lag.get("lagging_type") or "rubber_herringbone").replace("_", " ")

    # Belt
    belt_ply   = r.get("belt_ply") or "4 PLY"
    belt_len_m = H_m * 2.15        # approx: 2 × height + head + boot wrap

    # Buckets
    bkt_w_m    = float(bkt.get("W") or 250) / 1000.0
    bkt_h_m    = float(bkt.get("H") or 200) / 1000.0
    bkt_p_m    = float(bkt.get("P") or 150) / 1000.0
    bkt_mass   = float(r.get("bucket_mass_kg") or 2.5)
    spacing_m  = float(r.get("spacing") or 0.25)
    n_buckets  = max(1, int(belt_len_m / spacing_m))

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
    shaft_mass = _steel_cyl_kg(d_m, 0.0, span_m * 1.25)   # +25% for journal steps
    add("Head shaft with integral hub keyway",
        1, "EA",
        "S355JR / C45E",
        "EN 10025-2 / EN 10083-2",
        f"Ø{r.get('d_mm'):.0f} × {span_m*1250:.0f} mm lg",
        shaft_mass,
        "SHAFT",
        f"Governed by {r.get('governed_by','stress')}; "
        f"deflection {_f(r.get('d_deflect_mm'))} mm")

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

    add(f"Buckets — Series {bkt.get('id','—')}  {bkt.get('W','—')}×{bkt.get('H','—')}mm",
        n_buckets, "EA",
        "HDPE / cast steel" if bkt.get("id","B") in ("HF","AA") else "HDPE",
        "CEMA 375 §6",
        f"{bkt.get('W','—')}×{bkt.get('H','—')}×{bkt.get('P','—')}mm  {bkt.get('V','—')}L",
        bkt_mass,
        "BELT",
        f"Spacing = {spacing_m*1000:.0f}mm c/c  ×{n_buckets} off")

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
    ]

    return {
        "items":   items,
        "summary": {
            "total_items":  len(items),
            "total_mass_kg": round(total_mass, 1),
            "by_category":  by_cat,
        },
        "notes":   notes,
        "version": "1.0.0",
    }