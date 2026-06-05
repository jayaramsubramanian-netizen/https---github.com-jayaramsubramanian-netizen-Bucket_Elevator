"""
VECTRIX™ — Bulk Material Database
ANSI/CEMA 550-2020 "Classification and Definitions of Bulk Materials"

v1.1.0 — Expanded from 16 → 410 materials
─────────────────────────────────────────────────────────────────────────────
Schema (all entries are plain dicts — compatible with MaterialBehaviorEngine):

    id                  str     unique lowercase identifier
    name                str     display name
    category            str     category code (GRAIN, FOOD, FERT, MIN, etc.)
    rho_loose           float   loose bulk density  [kg/m³]
    rho_vib             float   vibrated bulk density [kg/m³]
    angle_repose        float   angle of repose [°]
    angle_surcharge     float   angle of surcharge [°]
    angle_internal_friction float internal friction angle [°]
    moisture_pct        float   typical moisture content [% by weight]
    cohesion            float   0.0=free-flowing, 1.0=highly cohesive
                                (maps to COHESION_* constants below)
    abr_code            int     1–7 CEMA 550 abrasion code
    flowability         int     1=very free, 2=free, 3=average, 4=poor
    size_code           str     A=fine, B=granular, C=coarse, D=fibrous, E=irregular
    hazard_codes        list    CEMA B-series hazard strings e.g. ["B10","B11"]
    Km                  float   material factor (power correction)
    Ceff_default        float   drive efficiency factor
    Leq_default         int     length equivalency
    wall_friction_deg   float   material-to-steel wall friction [°]
    bucket_fill_factor  float   CEMA §6 fill factor (0.5–0.95)

─────────────────────────────────────────────────────────────────────────────
Cohesion mapping (CEMA 550 §A-10):
    0.00  COHESION_NONE      dry granular: sand, dry grain
    0.10  slight             free-flowing with minimal cohesion
    0.20  COHESION_SLIGHT    slightly damp: coal, salt
    0.30  moderate-light     average: potash, NPK
    0.40  moderate           average-poor: fly ash, gypsum
    0.50  COHESION_MODERATE  cohesive: cement, wet ash
    0.70  moderate-high      wet cohesive: sludge, wet clay
    0.90  COHESION_EXTREME   extreme: wet cement, filter cake
─────────────────────────────────────────────────────────────────────────────
"""

# ── CEMA 550 cohesion constants ───────────────────────────────────────────────
COHESION_NONE     = 0.00
COHESION_SLIGHT   = 0.20
COHESION_MODERATE = 0.50
COHESION_EXTREME  = 1.00

# ── CEMA 550 flowability codes ────────────────────────────────────────────────
FLOWABILITY_VERY_FREE = 1
FLOWABILITY_FREE      = 2
FLOWABILITY_AVERAGE   = 3
FLOWABILITY_POOR      = 4

# ── Category codes ────────────────────────────────────────────────────────────
CAT_GRAIN = "GRAIN"     # grains, seeds, pulses
CAT_FOOD  = "FOOD"      # food products, powders, additives
CAT_FERT  = "FERT"      # fertilizers, agro-chemicals
CAT_MIN   = "MIN"       # minerals, ores, rocks
CAT_CHEM  = "CHEM"      # industrial chemicals
CAT_CONST = "CONST"     # construction materials
CAT_COAL  = "COAL"      # coal, coke, carbon
CAT_METAL = "METAL"     # metals, metal powders
CAT_BIO   = "BIO"       # biomass, organic, wood
CAT_POLY  = "POLY"      # plastics, rubber, polymers
CAT_ENV   = "ENV"       # environmental, waste materials
CAT_CEM   = "CEM"       # cement, lime, gypsum
CAT_SALT  = "SALT"      # salts, alkali, inorganic salts
CAT_GLASS = "GLASS"     # glass, ceramics, advanced materials
CAT_PETRO = "PETRO"     # petroleum, refinery products
CAT_PHARM = "PHARM"     # pharmaceutical, fine food ingredients


def _m(id, nm, cat, rl, rv, ar, asr, aif, mo, coh, abr, fl, sz, haz, km, ce, lq, wf, bf=0.75):
    """
    Compact constructor for material dict entries.
    bf = bucket_fill_factor (default 0.75; override for specific materials).
    """
    return {
        "id": id, "name": nm, "category": cat,
        "rho_loose": rl, "rho_vib": rv,
        "angle_repose": ar, "angle_surcharge": asr,
        "angle_internal_friction": aif,
        "moisture_pct": mo, "cohesion": coh,
        "abr_code": abr, "flowability": fl, "size_code": sz,
        "hazard_codes": haz,
        "Km": km, "Ceff_default": ce, "Leq_default": lq,
        "wall_friction_deg": wf,
        "bucket_fill_factor": bf,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MATERIAL DATABASE — 410 entries
# Columns: id, name, cat, ρ_l, ρ_v, θ_r, θ_s, θ_if, moist, coh, abr, fl, sz,
#          hazards, Km, Ceff, Leq, wall_fric, fill_factor
# ═══════════════════════════════════════════════════════════════════════════════

MATERIALS = [

    # ── GRAINS & SEEDS ────────────────────────────────────────────────────────
    _m("wheat",         "Wheat",                CAT_GRAIN, 769,  833,  28, 10, 30, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("corn",          "Corn (Maize)",          CAT_GRAIN, 720,  785,  25,  5, 28, 14.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("soybeans",      "Soybeans",              CAT_GRAIN, 769,  800,  29, 12, 31, 13.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("rice_rough",    "Rice (rough)",           CAT_GRAIN, 577,  625,  38, 20, 40, 14.0, 0.10, 2, 3, "B", [],             1.10, 1.15,  8, 24, 0.75),
    _m("rice_white",    "Rice (milled/white)",    CAT_GRAIN, 801,  865,  30, 15, 32, 13.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("barley",        "Barley",                CAT_GRAIN, 609,  673,  25,  8, 28, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("oats",          "Oats",                  CAT_GRAIN, 432,  480,  28, 12, 30, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.75),
    _m("rye",           "Rye",                   CAT_GRAIN, 705,  769,  27, 10, 29, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("sorghum",       "Sorghum",               CAT_GRAIN, 721,  785,  30, 12, 32, 12.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 18, 0.80),
    _m("millet",        "Millet",                CAT_GRAIN, 769,  833,  26,  8, 28, 12.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 16, 0.80),
    _m("sunflower",     "Sunflower Seeds",        CAT_GRAIN, 353,  400,  36, 18, 38,  8.0, 0.10, 1, 3, "B", [],             1.00, 1.15,  8, 20, 0.75),
    _m("cottonseed",    "Cottonseed",             CAT_GRAIN, 561,  625,  35, 16, 37,  8.0, 0.10, 1, 3, "B", [],             1.00, 1.15,  8, 20, 0.75),
    _m("peanuts",       "Peanuts (shelled)",      CAT_GRAIN, 545,  609,  30, 14, 32,  7.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 18, 0.75),
    _m("coffee_beans",  "Coffee Beans (green)",   CAT_GRAIN, 561,  625,  30, 14, 32, 10.0, 0.10, 1, 2, "B", ["B11"],        1.00, 1.15,  7, 18, 0.75),
    _m("cocoa_beans",   "Cocoa Beans",            CAT_GRAIN, 593,  641,  28, 10, 30,  7.0, 0.10, 2, 2, "B", [],             1.00, 1.15,  7, 16, 0.75),
    _m("flaxseed",      "Flaxseed (Linseed)",     CAT_GRAIN, 721,  785,  25,  8, 27,  8.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("canola",        "Canola (Rapeseed)",       CAT_GRAIN, 673,  737,  25,  8, 27,  8.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("sesame",        "Sesame Seeds",            CAT_GRAIN, 625,  689,  26, 10, 28,  7.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("lentils",       "Lentils",                CAT_GRAIN, 737,  801,  28, 12, 30, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("chickpeas",     "Chickpeas",              CAT_GRAIN, 769,  833,  26, 10, 28, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("peas_dry",      "Peas (dry)",             CAT_GRAIN, 753,  817,  25,  8, 27, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("beans_dry",     "Beans (dry, various)",   CAT_GRAIN, 801,  865,  27, 10, 29, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("malt_dry",      "Malt (dry)",             CAT_GRAIN, 529,  577,  35, 18, 37,  5.0, 0.10, 1, 3, "B", [],             1.00, 1.15,  8, 20, 0.75),
    _m("malt_wet",      "Malt (wet/green)",        CAT_GRAIN, 625,  689,  38, 20, 40, 25.0, 0.30, 1, 3, "B", [],             1.10, 1.20,  8, 22, 0.65),
    _m("rapeseed",      "Rapeseed",               CAT_GRAIN, 673,  737,  24,  6, 26,  8.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("triticale",     "Triticale",              CAT_GRAIN, 689,  753,  28, 10, 30, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("buckwheat",     "Buckwheat",              CAT_GRAIN, 625,  689,  27, 10, 29, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("spelt",         "Spelt",                  CAT_GRAIN, 609,  673,  28, 10, 30, 12.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("lupins",        "Lupins (seeds)",          CAT_GRAIN, 721,  785,  26,  8, 28, 10.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("safflower",     "Safflower Seeds",         CAT_GRAIN, 577,  641,  32, 14, 34,  7.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 18, 0.75),

    # ── FOOD PRODUCTS ─────────────────────────────────────────────────────────
    _m("flour_wheat",   "Flour (wheat)",           CAT_FOOD,  561,  641,  42, 22, 44, 12.0, 0.40, 2, 4, "A", ["B1","B11"],   1.20, 1.20,  9, 26, 0.55),
    _m("corn_meal",     "Corn Meal",               CAT_FOOD,  609,  689,  40, 20, 42, 12.0, 0.30, 2, 4, "A", ["B1","B11"],   1.10, 1.20,  9, 24, 0.60),
    _m("starch_corn",   "Starch (corn)",           CAT_FOOD,  641,  737,  42, 22, 44, 10.0, 0.40, 2, 4, "A", ["B1","B11"],   1.20, 1.20,  9, 26, 0.55),
    _m("sugar_gran",    "Sugar (granulated)",       CAT_FOOD,  849,  961,  35, 15, 38,  0.5, 0.10, 1, 2, "A", ["B8","B11"],   1.00, 1.15,  7, 18, 0.80),
    _m("sugar_powder",  "Sugar (icing/powder)",     CAT_FOOD,  641,  769,  45, 25, 47,  0.3, 0.50, 1, 4, "A", ["B1","B8","B11"], 1.20, 1.20, 9, 28, 0.55),
    _m("salt_fine",     "Salt (fine evaporated)",   CAT_FOOD, 1201, 1362,  32, 15, 35,  0.2, 0.20, 3, 3, "A", ["B4"],         1.10, 1.20,  8, 20, 0.75),
    _m("milk_powder",   "Milk Powder (dried)",      CAT_FOOD,  481,  561,  38, 20, 40,  3.0, 0.40, 1, 4, "A", ["B1","B8"],    1.10, 1.20,  8, 24, 0.60),
    _m("coffee_ground", "Coffee (ground/roasted)",  CAT_FOOD,  385,  433,  40, 22, 42,  7.0, 0.40, 2, 3, "A", [],             1.10, 1.20,  8, 24, 0.60),
    _m("cocoa_powder",  "Cocoa Powder",             CAT_FOOD,  481,  561,  43, 25, 45,  3.0, 0.50, 2, 4, "A", ["B8","B11"],   1.20, 1.20,  9, 26, 0.55),
    _m("bran",          "Bran (wheat/rice)",         CAT_FOOD,  257,  289,  38, 20, 40, 12.0, 0.20, 1, 3, "A", ["B11"],        1.10, 1.15,  8, 22, 0.65),
    _m("dried_milk",    "Dried Milk (skim/whole)",   CAT_FOOD,  481,  545,  40, 22, 42,  3.0, 0.40, 1, 4, "A", ["B1","B8"],   1.20, 1.20,  9, 26, 0.55),
    _m("citric_acid",   "Citric Acid",              CAT_FOOD,  769,  865,  40, 20, 42,  1.0, 0.30, 3, 4, "A", ["B4","B8"],    1.10, 1.20,  8, 24, 0.65),
    _m("pet_food",      "Pet Food Pellets",          CAT_FOOD,  561,  641,  30, 12, 32,  8.0, 0.10, 2, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("animal_feed",   "Animal Feed Pellets",       CAT_FOOD,  641,  721,  28, 10, 30, 10.0, 0.10, 2, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("bone_meal",     "Bone Meal",                CAT_FOOD,  769,  865,  38, 20, 40,  5.0, 0.30, 3, 4, "A", ["B8","B11"],   1.20, 1.20,  9, 24, 0.65),
    _m("fish_meal",     "Fish Meal",                CAT_FOOD,  641,  721,  38, 20, 40, 10.0, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("soy_meal",      "Soy Meal (defatted)",       CAT_FOOD,  577,  641,  28, 12, 30, 12.0, 0.20, 1, 3, "A", [],             1.00, 1.15,  8, 18, 0.70),
    _m("dextrose",      "Dextrose (glucose)",        CAT_FOOD,  641,  737,  35, 17, 37,  5.0, 0.20, 1, 3, "A", [],             1.10, 1.15,  8, 20, 0.70),
    _m("lactose",       "Lactose",                  CAT_FOOD,  577,  673,  38, 18, 40,  3.0, 0.30, 1, 3, "A", [],             1.10, 1.15,  8, 22, 0.65),
    _m("corn_syrup_sol","Corn Syrup Solids",         CAT_FOOD,  609,  689,  35, 17, 37,  5.0, 0.30, 1, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("whey_powder",   "Whey Powder",              CAT_FOOD,  417,  497,  42, 22, 44,  4.0, 0.50, 1, 4, "A", ["B1","B8"],    1.20, 1.20,  9, 26, 0.55),
    _m("tapioca",       "Tapioca Starch",           CAT_FOOD,  577,  673,  42, 22, 44, 10.0, 0.40, 1, 4, "A", ["B1"],         1.20, 1.20,  9, 26, 0.55),
    _m("blood_meal",    "Blood Meal",               CAT_FOOD,  561,  641,  40, 22, 42,  7.0, 0.40, 2, 4, "A", ["B11"],        1.20, 1.20,  9, 26, 0.55),
    _m("maltodextrin",  "Maltodextrin",             CAT_FOOD,  577,  673,  45, 25, 47,  5.0, 0.50, 1, 4, "A", ["B1"],         1.30, 1.20,  9, 28, 0.50),
    _m("salt_coarse",   "Salt (coarse / rock)",      CAT_FOOD, 1201, 1346,  35, 18, 37,  0.2, 0.20, 4, 3, "C", ["B4"],         1.10, 1.20,  8, 22, 0.75),

    # ── FERTILIZERS ───────────────────────────────────────────────────────────
    _m("amm_nitrate",   "Ammonium Nitrate",          CAT_FERT,  721,  801,  32, 14, 34,  0.3, 0.20, 2, 3, "B", ["B10","B11"],  1.10, 1.20,  8, 20, 0.75),
    _m("amm_sulfate",   "Ammonium Sulfate",           CAT_FERT,  849,  961,  32, 14, 35,  0.5, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 20, 0.75),
    _m("urea_gran",     "Urea (granular)",             CAT_FERT,  769,  865,  30, 12, 32,  0.2, 0.10, 2, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("urea_prilled",  "Urea (prilled)",              CAT_FERT,  769,  849,  30, 12, 32,  0.2, 0.10, 2, 2, "A", [],             1.00, 1.15,  7, 18, 0.80),
    _m("potash_mur",    "Potassium Chloride (MOP)",    CAT_FERT, 1201, 1362,  35, 15, 37,  0.2, 0.20, 4, 3, "B", [],             1.10, 1.20,  8, 22, 0.75),
    _m("superphosph",   "Superphosphate (SSP)",        CAT_FERT,  961, 1090,  35, 16, 38,  1.0, 0.30, 4, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("tsp",           "Triple Superphosphate (TSP)", CAT_FERT,  961, 1090,  35, 15, 38,  1.0, 0.30, 4, 3, "B", [],             1.10, 1.20,  9, 22, 0.70),
    _m("dap",           "DAP (Di-Ammonium Phosphate)", CAT_FERT,  897, 1009,  33, 14, 35,  0.5, 0.20, 4, 3, "B", [],             1.10, 1.20,  8, 20, 0.75),
    _m("map",           "MAP (Mono-Ammonium Phosphate)",CAT_FERT, 897, 1009,  34, 15, 36,  0.5, 0.20, 4, 3, "B", [],             1.10, 1.20,  8, 22, 0.75),
    _m("npk",           "NPK Compound Fertilizer",     CAT_FERT,  849,  961,  34, 15, 36,  0.5, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 20, 0.75),
    _m("potash_sulf",   "Potassium Sulfate (SOP)",     CAT_FERT, 1201, 1346,  36, 18, 38,  0.2, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 22, 0.75),
    _m("can",           "Calcium Ammonium Nitrate",    CAT_FERT,  801,  897,  35, 16, 37,  0.3, 0.20, 2, 3, "B", ["B10","B11"],  1.10, 1.20,  8, 20, 0.75),
    _m("sulfur_gran",   "Sulfur (granulated/prilled)", CAT_FERT, 1362, 1506,  28, 10, 30,  0.0, 0.10, 2, 2, "B", ["B10","B11"],  1.00, 1.15,  7, 16, 0.80),
    _m("sulfur_lumps",  "Sulfur (lump)",               CAT_FERT, 1281, 1442,  30, 12, 32,  0.0, 0.10, 3, 3, "C", ["B10","B11"],  1.10, 1.15,  8, 18, 0.75),
    _m("potash_nitrate","Potassium Nitrate",            CAT_FERT, 1201, 1346,  32, 14, 34,  0.2, 0.20, 3, 3, "B", ["B10"],        1.10, 1.20,  8, 20, 0.75),
    _m("amm_bicarb",    "Ammonium Bicarbonate",         CAT_FERT,  769,  865,  38, 18, 40,  1.0, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.70),
    _m("calcium_nitrate","Calcium Nitrate",             CAT_FERT, 1090, 1201,  34, 15, 36,  0.5, 0.30, 2, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("phosphate_fert","Phosphate Rock (fert grade)", CAT_FERT, 1201, 1362,  38, 20, 40,  3.0, 0.20, 5, 3, "C", [],             1.30, 1.20, 10, 24, 0.70),
    _m("compost",       "Compost (mature)",             CAT_FERT,  641,  737,  40, 22, 42, 30.0, 0.50, 1, 4, "B", [],             1.20, 1.20,  9, 26, 0.55),
    _m("peat_gran",     "Peat (granulated)",            CAT_FERT,  385,  433,  42, 22, 44, 45.0, 0.40, 1, 4, "A", ["B11"],        1.20, 1.20,  9, 26, 0.55),

    # ── MINERALS & ORES ───────────────────────────────────────────────────────
    _m("limestone",     "Limestone (crushed, dry)",    CAT_MIN, 1442, 1602,  38, 20, 40,  2.0, 0.10, 6, 3, "C", ["B8"],         1.20, 1.20,  9, 24, 0.70),
    _m("limestone_pwd", "Limestone Powder",             CAT_MIN, 1201, 1362,  42, 22, 44,  1.0, 0.30, 5, 4, "A", ["B8"],         1.20, 1.20,  9, 26, 0.65),
    _m("sand_dry",      "Sand (dry, washed)",           CAT_MIN, 1602, 1762,  35, 15, 37,  0.5, 0.10, 6, 2, "A", ["B8"],         1.20, 1.20,  9, 18, 0.75),
    _m("sand_wet",      "Sand (wet/damp)",              CAT_MIN, 1762, 1922,  38, 20, 40,  8.0, 0.20, 5, 3, "A", [],             1.20, 1.20,  9, 22, 0.65),
    _m("gravel_dry",    "Gravel (dry)",                 CAT_MIN, 1442, 1602,  30, 12, 32,  1.0, 0.10, 5, 2, "C", [],             1.10, 1.15,  8, 18, 0.75),
    _m("gravel_wet",    "Gravel (wet)",                 CAT_MIN, 1602, 1762,  35, 15, 37,  6.0, 0.10, 5, 3, "C", [],             1.20, 1.20,  8, 22, 0.65),
    _m("granite",       "Granite (crushed)",            CAT_MIN, 1506, 1666,  40, 20, 42,  1.0, 0.10, 7, 3, "C", [],             1.30, 1.25, 10, 24, 0.70),
    _m("basalt",        "Basalt (crushed)",             CAT_MIN, 1522, 1682,  40, 20, 42,  1.0, 0.10, 7, 3, "C", [],             1.30, 1.25, 10, 24, 0.70),
    _m("dolomite",      "Dolomite",                     CAT_MIN, 1362, 1506,  38, 18, 40,  1.0, 0.10, 5, 3, "C", [],             1.20, 1.20,  9, 22, 0.70),
    _m("bauxite_dry",   "Bauxite (dry)",                CAT_MIN, 1281, 1442,  38, 20, 40,  2.0, 0.20, 5, 3, "C", [],             1.20, 1.20,  9, 24, 0.70),
    _m("bauxite_wet",   "Bauxite (wet)",                CAT_MIN, 1442, 1602,  42, 22, 44, 10.0, 0.30, 5, 4, "C", [],             1.30, 1.20, 10, 26, 0.60),
    _m("copper_ore",    "Copper Ore",                   CAT_MIN, 1922, 2163,  42, 22, 44,  3.0, 0.10, 7, 3, "C", [],             1.30, 1.25, 10, 26, 0.70),
    _m("lead_ore",      "Lead Ore",                     CAT_MIN, 2403, 2724,  45, 25, 47,  2.0, 0.10, 7, 4, "C", [],             1.40, 1.25, 11, 28, 0.65),
    _m("zinc_ore",      "Zinc Ore",                     CAT_MIN, 1922, 2163,  40, 20, 42,  3.0, 0.10, 7, 3, "C", [],             1.30, 1.25, 10, 26, 0.70),
    _m("ironore",       "Iron Ore (fines)",              CAT_MIN, 2002, 2243,  42, 25, 45,  5.0, 0.10, 7, 4, "A", [],             1.40, 1.25, 11, 28, 0.65),
    _m("ironore_pellet","Iron Ore Pellets",              CAT_MIN, 2163, 2403,  28, 10, 30,  2.0, 0.00, 6, 1, "B", [],             1.20, 1.20,  8, 16, 0.85),
    _m("magnetite",     "Magnetite",                    CAT_MIN, 2403, 2724,  35, 15, 37,  2.0, 0.10, 7, 3, "A", [],             1.30, 1.25, 10, 22, 0.70),
    _m("hematite",      "Hematite",                     CAT_MIN, 2243, 2484,  38, 18, 40,  3.0, 0.10, 7, 3, "A", [],             1.30, 1.25, 10, 24, 0.70),
    _m("manganese_ore", "Manganese Ore",                CAT_MIN, 1922, 2163,  38, 18, 40,  5.0, 0.20, 7, 3, "C", [],             1.30, 1.25, 10, 24, 0.70),
    _m("nickel_ore",    "Nickel Ore",                   CAT_MIN, 1602, 1762,  38, 18, 40,  4.0, 0.20, 7, 3, "C", [],             1.30, 1.25, 10, 24, 0.70),
    _m("chrome_ore",    "Chrome Ore",                   CAT_MIN, 2002, 2243,  40, 20, 42,  3.0, 0.10, 7, 3, "C", [],             1.40, 1.25, 11, 26, 0.70),
    _m("phosphate",     "Phosphate Rock",               CAT_MIN, 1201, 1362,  38, 20, 40,  3.0, 0.20, 5, 3, "C", [],             1.30, 1.20, 10, 24, 0.70),
    _m("potash_ore",    "Potash Ore (sylvinite)",        CAT_MIN, 1281, 1442,  36, 18, 38,  0.5, 0.10, 5, 3, "C", [],             1.20, 1.20,  9, 22, 0.75),
    _m("gypsum_raw",    "Gypsum (raw, crushed)",         CAT_MIN, 1361, 1506,  38, 18, 40,  1.0, 0.20, 4, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("gypsum_calc",   "Gypsum (calcined)",             CAT_MIN,  961, 1090,  42, 22, 44,  0.5, 0.30, 3, 4, "A", ["B8"],         1.20, 1.20,  9, 26, 0.65),
    _m("kaolin",        "Kaolin (dry)",                  CAT_MIN, 1009, 1201,  42, 22, 44,  2.0, 0.40, 3, 4, "A", ["B8"],         1.20, 1.20,  9, 26, 0.60),
    _m("bentonite",     "Bentonite (dry)",               CAT_MIN,  673,  801,  42, 22, 44,  8.0, 0.50, 2, 4, "A", ["B8"],         1.30, 1.20,  9, 26, 0.55),
    _m("talc",          "Talc",                          CAT_MIN,  769,  865,  35, 17, 37,  0.5, 0.30, 3, 3, "A", ["B8"],         1.10, 1.20,  8, 22, 0.65),
    _m("feldspar",      "Feldspar (ground)",             CAT_MIN, 1281, 1442,  38, 18, 40,  0.5, 0.10, 5, 3, "B", ["B8"],         1.20, 1.20,  9, 22, 0.70),
    _m("silica_sand",   "Silica Sand",                   CAT_MIN, 1442, 1602,  35, 15, 37,  0.5, 0.10, 7, 2, "A", ["B8"],         1.20, 1.25,  9, 18, 0.75),
    _m("quartz",        "Quartz (crushed)",              CAT_MIN, 1522, 1682,  38, 18, 40,  0.5, 0.10, 7, 3, "B", ["B8"],         1.20, 1.25,  9, 22, 0.70),
    _m("silica_flour",  "Silica Flour (fine)",           CAT_MIN, 1201, 1362,  42, 22, 44,  0.5, 0.40, 7, 4, "A", ["B8"],         1.30, 1.25, 10, 28, 0.60),
    _m("sinter",        "Sinter (hot/cold)",             CAT_MIN, 1762, 1922,  40, 20, 42,  0.5, 0.10, 7, 3, "D", [],             1.30, 1.25, 10, 26, 0.70),
    _m("clinker",       "Clinker (cement)",              CAT_MIN, 1298, 1442,  45, 25, 48,  0.1, 0.10, 7, 4, "E", ["B8"],         1.50, 1.30, 12, 28, 0.65),
    _m("diatomite",     "Diatomite / Diatomaceous Earth",CAT_MIN,  225,  273,  40, 22, 42,  5.0, 0.40, 2, 4, "A", [],             1.20, 1.20,  8, 26, 0.60),
    _m("pumice",        "Pumice (crushed)",              CAT_MIN,  641,  721,  35, 17, 37,  5.0, 0.20, 3, 3, "B", [],             1.10, 1.15,  8, 22, 0.70),
    _m("perlite_ore",   "Perlite (raw ore)",             CAT_MIN,  897, 1009,  35, 17, 37,  2.0, 0.10, 3, 3, "B", [],             1.10, 1.15,  8, 20, 0.75),
    _m("perlite_exp",   "Perlite (expanded)",            CAT_MIN,   48,   80,  35, 17, 37,  1.0, 0.20, 1, 3, "B", [],             1.10, 1.15,  8, 22, 0.65),
    _m("vermiculite",   "Vermiculite (expanded)",        CAT_MIN,  160,  209,  35, 17, 37,  5.0, 0.20, 1, 3, "B", [],             1.10, 1.15,  8, 22, 0.65),
    _m("zeolite",       "Zeolite (natural)",             CAT_MIN,  769,  865,  38, 18, 40,  5.0, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("rock_salt",     "Rock Salt",                     CAT_MIN, 1201, 1362,  35, 17, 37,  0.2, 0.20, 4, 3, "C", ["B4"],         1.10, 1.20,  8, 22, 0.75),
    _m("borax",         "Borax (ore/crushed)",           CAT_MIN,  849,  961,  32, 14, 34,  0.5, 0.20, 2, 3, "B", [],             1.10, 1.20,  8, 20, 0.75),
    _m("magnesite",     "Magnesite",                     CAT_MIN, 1009, 1137,  38, 18, 40,  0.5, 0.10, 5, 3, "B", [],             1.20, 1.20,  9, 22, 0.70),
    _m("pyrite",        "Pyrite (iron sulfide)",         CAT_MIN, 2243, 2484,  38, 18, 40,  1.0, 0.10, 7, 3, "B", [],             1.30, 1.25, 10, 24, 0.70),
    _m("rutile",        "Rutile (titanium ore)",          CAT_MIN, 2082, 2323,  38, 18, 40,  0.5, 0.10, 6, 3, "A", [],             1.30, 1.25, 10, 24, 0.70),
    _m("ilmenite",      "Ilmenite",                      CAT_MIN, 2243, 2484,  38, 18, 40,  0.5, 0.10, 6, 3, "A", [],             1.30, 1.25, 10, 24, 0.70),
    _m("galena",        "Galena (lead sulfide)",         CAT_MIN, 3204, 3525,  38, 18, 40,  0.5, 0.10, 7, 3, "B", [],             1.40, 1.25, 11, 24, 0.70),
    _m("calcite",       "Calcite",                       CAT_MIN, 1362, 1506,  38, 18, 40,  0.5, 0.10, 5, 3, "B", [],             1.20, 1.20,  9, 22, 0.70),
    _m("marble_chips",  "Marble Chips",                  CAT_MIN, 1442, 1602,  35, 17, 37,  0.5, 0.10, 6, 3, "C", [],             1.20, 1.20,  9, 22, 0.70),
    _m("quartzite",     "Quartzite",                     CAT_MIN, 1442, 1602,  40, 20, 42,  0.5, 0.10, 7, 3, "C", ["B8"],         1.20, 1.25,  9, 24, 0.70),
    _m("mica",          "Mica (flake)",                   CAT_MIN,  209,  257,  35, 18, 37,  1.0, 0.20, 3, 3, "A", [],             1.10, 1.15,  8, 20, 0.65),
    _m("wollastonite",  "Wollastonite",                   CAT_MIN, 1137, 1281,  38, 18, 40,  0.5, 0.20, 5, 3, "A", ["B8"],         1.20, 1.20,  9, 22, 0.70),

    # ── CHEMICALS ─────────────────────────────────────────────────────────────
    _m("calcium_carb",  "Calcium Carbonate (fine)",      CAT_CHEM, 1201, 1362, 40, 20, 42,  0.5, 0.30, 4, 4, "A", ["B8"],         1.20, 1.20,  9, 24, 0.65),
    _m("calcium_chlor", "Calcium Chloride (flake)",       CAT_CHEM,  961, 1090, 36, 17, 38,  0.5, 0.30, 3, 3, "B", ["B4"],         1.20, 1.20,  9, 22, 0.65),
    _m("calcium_hydr",  "Calcium Hydroxide (hydrated lime)",CAT_CHEM, 433, 497, 42, 22, 44,  1.0, 0.50, 3, 4, "A", ["B4","B8"],    1.30, 1.20,  9, 28, 0.55),
    _m("sodium_carb",   "Sodium Carbonate (soda ash)",   CAT_CHEM,  849, 1009, 40, 20, 42,  1.0, 0.40, 2, 4, "A", ["B4"],         1.20, 1.20,  9, 26, 0.60),
    _m("sodium_bicarb", "Sodium Bicarbonate (baking soda)",CAT_CHEM, 801, 897, 40, 20, 42,  1.0, 0.40, 2, 4, "A", ["B4"],         1.20, 1.20,  9, 26, 0.60),
    _m("sodium_chlor",  "Sodium Chloride (salt, chem)",  CAT_CHEM, 1137, 1281, 35, 16, 37,  0.2, 0.20, 3, 3, "A", ["B4"],         1.10, 1.20,  8, 22, 0.75),
    _m("sodium_sulfate","Sodium Sulfate (anhydrous)",     CAT_CHEM, 1201, 1346, 38, 18, 40,  0.5, 0.30, 3, 3, "B", [],             1.20, 1.20,  8, 22, 0.70),
    _m("soda_ash_lt",   "Soda Ash (light)",               CAT_CHEM,  481,  545, 42, 22, 44,  0.5, 0.40, 2, 4, "A", ["B1","B4"],    1.20, 1.20,  9, 28, 0.55),
    _m("soda_ash_dn",   "Soda Ash (dense)",               CAT_CHEM, 1009, 1137, 40, 20, 42,  0.5, 0.30, 2, 3, "A", ["B4"],         1.20, 1.20,  9, 24, 0.65),
    _m("titanium_diox", "Titanium Dioxide",               CAT_CHEM,  961, 1090, 42, 22, 44,  0.2, 0.40, 4, 4, "A", ["B8"],         1.20, 1.25,  9, 26, 0.60),
    _m("zinc_oxide",    "Zinc Oxide",                     CAT_CHEM,  481,  561, 38, 20, 40,  0.2, 0.30, 3, 3, "A", ["B8"],         1.20, 1.20,  9, 24, 0.65),
    _m("magnesium_ox",  "Magnesium Oxide",                CAT_CHEM,  721,  801, 40, 22, 42,  1.0, 0.40, 3, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("alumina",       "Aluminum Oxide (alumina)",       CAT_CHEM,  961, 1090, 40, 20, 42,  0.2, 0.30, 7, 3, "A", ["B8"],         1.30, 1.25, 10, 24, 0.65),
    _m("activated_C",   "Activated Carbon",               CAT_CHEM,  209,  257, 38, 20, 40,  5.0, 0.30, 3, 3, "A", ["B10","B11"],  1.10, 1.20,  8, 22, 0.65),
    _m("carbon_black",  "Carbon Black",                   CAT_CHEM,  160,  209, 45, 25, 47,  0.5, 0.60, 2, 4, "A", ["B10","B11"],  1.40, 1.25, 11, 30, 0.50),
    _m("silica_gel",    "Silica Gel",                     CAT_CHEM,  641,  737, 38, 18, 40,  5.0, 0.30, 3, 3, "A", [],             1.20, 1.20,  8, 22, 0.65),
    _m("calcium_carb2", "Calcium Carbide",                CAT_CHEM, 1362, 1522, 40, 20, 42,  0.0, 0.30, 6, 4, "B", ["B6","B10","B11"], 1.30, 1.25, 10, 26, 0.65),
    _m("ferric_oxide",  "Ferric Oxide (red iron oxide)",  CAT_CHEM, 1362, 1522, 40, 20, 42,  0.5, 0.30, 4, 4, "A", [],             1.20, 1.20,  9, 26, 0.65),
    _m("potass_perm",   "Potassium Permanganate",          CAT_CHEM, 1201, 1346, 38, 18, 40,  0.5, 0.30, 3, 3, "A", ["B4","B10"],   1.20, 1.20,  9, 24, 0.65),
    _m("activated_alu", "Activated Alumina",              CAT_CHEM,  769,  865, 40, 20, 42,  5.0, 0.30, 6, 4, "A", [],             1.20, 1.25,  9, 24, 0.65),
    _m("alum_sulfate",  "Aluminum Sulfate",               CAT_CHEM, 1073, 1201, 38, 18, 40,  0.5, 0.30, 4, 3, "A", ["B4"],         1.20, 1.20,  9, 24, 0.65),
    _m("copper_sulfate","Copper Sulfate",                  CAT_CHEM, 1201, 1362, 36, 17, 38,  0.5, 0.20, 4, 3, "A", ["B4"],         1.10, 1.20,  8, 22, 0.70),
    _m("alum_hydrox",   "Aluminum Hydroxide",             CAT_CHEM,  385,  449, 42, 22, 44,  1.0, 0.50, 3, 4, "A", [],             1.20, 1.20,  9, 26, 0.55),
    _m("sodium_sil_pwd","Sodium Silicate Powder",          CAT_CHEM,  961, 1090, 40, 20, 42,  1.0, 0.30, 3, 4, "A", ["B4"],         1.20, 1.20,  9, 24, 0.65),
    _m("boric_acid",    "Boric Acid",                     CAT_CHEM,  865,  961, 40, 20, 42,  0.5, 0.30, 2, 4, "A", [],             1.20, 1.20,  9, 24, 0.65),
    _m("potass_carb",   "Potassium Carbonate",            CAT_CHEM, 1073, 1201, 40, 20, 42,  0.5, 0.30, 3, 4, "A", ["B4"],         1.20, 1.20,  9, 24, 0.65),

    # ── CONSTRUCTION ──────────────────────────────────────────────────────────
    _m("cement",        "Cement (dry, Portland)",         CAT_CEM, 1506, 1762, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("cement_white",  "Cement (white)",                 CAT_CEM, 1346, 1602, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("quicklime",     "Quicklime (calcium oxide)",      CAT_CEM,  769,  865, 38, 20, 40,  0.1, 0.50, 4, 4, "A", ["B4","B8"],    1.30, 1.20,  9, 26, 0.55),
    _m("hydrated_lime", "Hydrated Lime",                  CAT_CEM,  481,  561, 42, 22, 44,  1.0, 0.60, 3, 4, "A", ["B4","B8"],    1.40, 1.25, 10, 28, 0.50),
    _m("slag_gran",     "Slag (granulated, GGBS)",        CAT_CONST,1201, 1362, 35, 17, 37,  5.0, 0.20, 5, 3, "B", [],             1.20, 1.20,  9, 22, 0.70),
    _m("slag_blas",     "Slag (blast furnace, lump)",     CAT_CONST,1201, 1362, 35, 17, 37,  3.0, 0.10, 5, 3, "C", [],             1.20, 1.20,  9, 22, 0.70),
    _m("concrete_dry",  "Concrete (dry premix)",          CAT_CONST,1442, 1602, 38, 18, 40,  2.0, 0.30, 5, 3, "B", [],             1.20, 1.20,  9, 24, 0.65),
    _m("aggregate",     "Concrete Aggregate",             CAT_CONST,1442, 1602, 32, 14, 34,  1.0, 0.10, 5, 2, "C", [],             1.10, 1.15,  8, 20, 0.75),
    _m("brick_chips",   "Brick Chips / Rubble",           CAT_CONST,1201, 1362, 38, 18, 40,  2.0, 0.10, 6, 3, "C", [],             1.20, 1.20,  9, 24, 0.70),
    _m("glass_cullet",  "Glass Cullet (mixed)",           CAT_CONST,1281, 1442, 38, 18, 40,  0.5, 0.10, 7, 3, "B", [],             1.20, 1.25,  9, 24, 0.70),
    _m("crushed_stone", "Crushed Stone",                  CAT_CONST,1442, 1602, 38, 18, 40,  1.0, 0.10, 6, 3, "C", [],             1.20, 1.20,  9, 24, 0.70),
    _m("recycled_conc", "Recycled Concrete Aggregate",    CAT_CONST,1362, 1522, 38, 18, 40,  5.0, 0.20, 5, 3, "C", [],             1.20, 1.20,  9, 22, 0.70),
    _m("plaster",       "Plaster / Stucco (dry)",         CAT_CONST, 849,  961, 42, 22, 44,  2.0, 0.40, 3, 4, "A", ["B8"],         1.20, 1.20,  9, 26, 0.60),
    _m("bottom_ash",    "Bottom Ash (coal-fired)",        CAT_CONST, 897, 1009, 38, 18, 40,  5.0, 0.30, 6, 3, "B", [],             1.20, 1.25,  9, 24, 0.65),
    _m("asphalt_gran",  "Asphalt (granulated/pellets)",   CAT_CONST,1009, 1137, 35, 17, 37,  0.5, 0.20, 4, 3, "B", ["B11"],        1.10, 1.20,  8, 22, 0.70),
    _m("flyash",        "Fly Ash (coal)",                 CAT_CONST, 801,  961, 42, 22, 44,  0.5, 0.40, 3, 4, "A", ["B1","B8"],    1.20, 1.20,  9, 26, 0.60),
    _m("expanded_clay", "Expanded Clay (LECA)",           CAT_CONST, 561,  641, 32, 14, 34,  2.0, 0.10, 3, 2, "B", [],             1.10, 1.15,  7, 20, 0.75),
    _m("perlite_bld",   "Perlite (building, expanded)",   CAT_CONST,  80,  112, 35, 17, 37,  1.0, 0.20, 1, 3, "B", [],             1.10, 1.15,  8, 22, 0.65),
    _m("phosphogypsum", "Phosphogypsum",                  CAT_CONST,1090, 1201, 40, 20, 42,  5.0, 0.40, 3, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("calcium_sil",   "Calcium Silicate Board (chunks)",CAT_CONST, 481,  561, 42, 22, 44,  2.0, 0.40, 3, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),

    # ── COAL & COKE ──────────────────────────────────────────────────────────
    _m("coal_bit",      "Coal (bituminous, slack)",        CAT_COAL,  833,  913, 38, 20, 38,  8.0, 0.20, 5, 3, "D", ["B6","B8","B10","B11"], 1.10, 1.20, 9, 22, 0.70),
    _m("coal_anth",     "Coal (anthracite)",               CAT_COAL,  961, 1057, 35, 17, 37,  5.0, 0.10, 5, 3, "D", ["B6","B10","B11"],      1.10, 1.20, 8, 20, 0.70),
    _m("coal_lignite",  "Coal (lignite/brown coal)",       CAT_COAL,  769,  865, 42, 22, 44, 15.0, 0.30, 4, 4, "D", ["B6","B10","B11"],      1.20, 1.20, 9, 26, 0.65),
    _m("coal_subbit",   "Coal (sub-bituminous)",           CAT_COAL,  801,  897, 40, 20, 42, 12.0, 0.20, 4, 3, "D", ["B6","B10","B11"],      1.10, 1.20, 9, 24, 0.65),
    _m("coal_fine",     "Coal (fine, washed fines)",       CAT_COAL,  769,  865, 42, 22, 44, 10.0, 0.30, 4, 4, "A", ["B6","B8","B10","B11"], 1.20, 1.25, 9, 26, 0.60),
    _m("coke_petro",    "Petroleum Coke (green)",          CAT_COAL,  865,  961, 35, 17, 37,  5.0, 0.10, 5, 3, "B", ["B11"],                 1.10, 1.20, 8, 20, 0.70),
    _m("coke_calc",     "Petroleum Coke (calcined)",        CAT_COAL,  769,  865, 35, 17, 37,  1.0, 0.10, 5, 3, "B", ["B8","B11"],           1.10, 1.20, 8, 20, 0.70),
    _m("coke_coal",     "Coke (metallurgical)",            CAT_COAL,  449,  529, 38, 20, 40,  3.0, 0.10, 5, 3, "D", ["B8","B11"],            1.20, 1.20, 9, 22, 0.70),
    _m("coke_breeze",   "Coke Breeze (fine)",              CAT_COAL,  433,  497, 40, 22, 42,  8.0, 0.20, 5, 4, "A", ["B8","B11"],            1.20, 1.20, 9, 24, 0.65),
    _m("coal_dust",     "Coal Dust",                       CAT_COAL,  609,  689, 45, 25, 47,  8.0, 0.40, 4, 4, "A", ["B6","B8","B10","B11"], 1.30, 1.25,10, 28, 0.55),
    _m("charcoal",      "Charcoal",                        CAT_COAL,  353,  401, 42, 22, 44,  5.0, 0.20, 2, 4, "A", ["B10","B11"],           1.20, 1.20, 9, 26, 0.65),
    _m("coal_pellets",  "Coal Pellets",                    CAT_COAL,  849,  945, 28, 10, 30,  5.0, 0.10, 4, 2, "B", ["B10","B11"],           1.00, 1.15, 8, 18, 0.80),
    _m("graphite_flake","Graphite (flake)",                 CAT_COAL,  481,  561, 40, 20, 42,  2.0, 0.20, 3, 4, "A", ["B10","B11"],           1.20, 1.20, 9, 24, 0.65),
    _m("graphite_pwd",  "Graphite Powder",                  CAT_COAL,  385,  449, 42, 22, 44,  2.0, 0.30, 3, 4, "A", ["B8","B10","B11"],      1.20, 1.20, 9, 26, 0.60),
    _m("activated_coke","Activated Coke",                   CAT_COAL,  385,  449, 38, 18, 40,  3.0, 0.20, 4, 3, "B", ["B10","B11"],           1.20, 1.20, 9, 22, 0.65),

    # ── METALS & METAL PRODUCTS ───────────────────────────────────────────────
    _m("steel_shot",    "Steel Shot / Steel Balls",        CAT_METAL,4805, 5285, 25,  8, 27,  0.0, 0.00, 7, 1, "A", [],             1.20, 1.25,  8, 14, 0.90),
    _m("steel_grit",    "Steel Grit",                      CAT_METAL,4805, 5285, 28, 10, 30,  0.0, 0.10, 7, 2, "A", [],             1.20, 1.25,  8, 16, 0.85),
    _m("alum_powder",   "Aluminum Powder",                 CAT_METAL,1009, 1137, 38, 20, 40,  0.0, 0.20, 4, 3, "A", ["B6","B8","B10","B11"], 1.30, 1.25, 10, 24, 0.65),
    _m("alum_chips",    "Aluminum Chips / Turnings",       CAT_METAL, 481,  561, 35, 17, 37,  0.5, 0.20, 5, 3, "E", [],             1.20, 1.20,  9, 22, 0.60),
    _m("copper_powder", "Copper Powder",                   CAT_METAL,2002, 2243, 38, 18, 40,  0.0, 0.20, 5, 3, "A", [],             1.30, 1.25, 10, 24, 0.65),
    _m("iron_powder",   "Iron Powder",                     CAT_METAL,2402, 2724, 40, 20, 42,  0.0, 0.20, 5, 4, "A", [],             1.30, 1.25, 10, 26, 0.65),
    _m("zinc_powder",   "Zinc Powder",                     CAT_METAL,1762, 1922, 38, 18, 40,  0.0, 0.20, 4, 3, "A", ["B10","B11"],  1.20, 1.25,  9, 24, 0.65),
    _m("zinc_gran",     "Zinc Granules",                   CAT_METAL,2082, 2323, 30, 12, 32,  0.0, 0.10, 5, 2, "A", [],             1.10, 1.20,  8, 18, 0.80),
    _m("copper_gran",   "Copper Granules",                 CAT_METAL,2404, 2644, 30, 12, 32,  0.0, 0.10, 6, 2, "A", [],             1.20, 1.25,  8, 18, 0.80),
    _m("nickel_powder", "Nickel Powder",                   CAT_METAL,2082, 2323, 40, 20, 42,  0.0, 0.20, 5, 4, "A", [],             1.30, 1.25, 10, 26, 0.65),
    _m("silicon_carb",  "Silicon Carbide",                 CAT_METAL,1442, 1602, 38, 18, 40,  0.2, 0.10, 7, 3, "A", [],             1.30, 1.30, 10, 24, 0.70),
    _m("lead_shot",     "Lead Shot",                       CAT_METAL,6805, 7405, 25,  8, 27,  0.0, 0.00, 5, 1, "A", [],             1.30, 1.25,  9, 14, 0.90),
    _m("manganese_diox","Manganese Dioxide",               CAT_METAL,1281, 1442, 40, 20, 42,  1.0, 0.20, 5, 4, "A", [],             1.20, 1.20,  9, 26, 0.65),
    _m("magnesium_pwd", "Magnesium Powder",                CAT_METAL, 865,  961, 38, 18, 40,  0.0, 0.20, 5, 3, "A", ["B6","B10","B11"], 1.30, 1.25, 10, 24, 0.65),
    _m("tungsten_carb", "Tungsten Carbide",                CAT_METAL,3525, 3845, 35, 17, 37,  0.0, 0.10, 7, 3, "A", [],             1.40, 1.30, 11, 22, 0.70),

    # ── BIOMASS & ORGANIC ─────────────────────────────────────────────────────
    _m("woodchips",     "Wood Chips",                      CAT_BIO,   240,  290, 40, 22, 42, 25.0, 0.20, 1, 4, "E", ["B6","B11"],   1.10, 1.15,  8, 24, 0.65),
    _m("sawdust",       "Sawdust",                          CAT_BIO,   177,  209, 42, 22, 44, 20.0, 0.30, 1, 4, "A", ["B6","B10","B11"], 1.20, 1.15, 9, 26, 0.60),
    _m("wood_pellets",  "Wood Pellets",                     CAT_BIO,   641,  721, 28, 10, 30,  8.0, 0.10, 2, 2, "B", ["B11"],        1.00, 1.15,  7, 18, 0.80),
    _m("bark",          "Bark (wood)",                      CAT_BIO,   225,  273, 45, 25, 47, 30.0, 0.30, 1, 4, "E", ["B11"],        1.20, 1.15,  9, 28, 0.60),
    _m("straw_chop",    "Straw (chopped)",                  CAT_BIO,    80,  112, 40, 22, 42, 15.0, 0.20, 1, 4, "E", ["B11"],        1.20, 1.15,  8, 26, 0.55),
    _m("bagasse",       "Bagasse (sugar cane)",             CAT_BIO,   192,  241, 45, 25, 47, 50.0, 0.50, 1, 4, "E", ["B11"],        1.30, 1.20, 10, 30, 0.50),
    _m("rice_husks",    "Rice Husks",                       CAT_BIO,   112,  145, 40, 22, 42, 12.0, 0.20, 1, 4, "A", ["B11"],        1.20, 1.15,  8, 26, 0.55),
    _m("corn_cobs",     "Corn Cobs",                        CAT_BIO,   225,  273, 38, 20, 40, 15.0, 0.20, 1, 3, "E", ["B11"],        1.10, 1.15,  8, 24, 0.65),
    _m("peat",          "Peat (raw)",                       CAT_BIO,   353,  401, 45, 25, 47, 50.0, 0.50, 1, 4, "A", ["B11"],        1.30, 1.20,  9, 30, 0.50),
    _m("compost_dry",   "Compost (dry/cured)",              CAT_BIO,   529,  609, 38, 20, 40, 15.0, 0.30, 1, 3, "B", [],             1.10, 1.20,  8, 24, 0.65),
    _m("coconut_shell", "Coconut Shell (chips)",            CAT_BIO,   529,  609, 35, 17, 37,  8.0, 0.10, 2, 3, "B", [],             1.10, 1.15,  8, 22, 0.70),
    _m("groundnut_sh",  "Groundnut Shells",                 CAT_BIO,   193,  241, 38, 20, 40, 10.0, 0.20, 1, 3, "E", [],             1.10, 1.15,  8, 24, 0.65),
    _m("tobacco",       "Tobacco (cut)",                    CAT_BIO,   209,  257, 40, 22, 42, 15.0, 0.30, 1, 4, "B", ["B11"],        1.20, 1.15,  8, 26, 0.60),
    _m("wood_flour",    "Wood Flour",                       CAT_BIO,   289,  337, 42, 22, 44, 12.0, 0.30, 1, 4, "A", ["B10","B11"],  1.20, 1.15,  9, 26, 0.60),
    _m("biomass_pell",  "Biomass Pellets (mixed)",          CAT_BIO,   609,  689, 30, 12, 32, 10.0, 0.10, 2, 2, "B", ["B11"],        1.00, 1.15,  7, 18, 0.80),
    _m("spent_grain",   "Spent Grain (brewery, wet)",       CAT_BIO,   529,  609, 40, 22, 42, 70.0, 0.50, 1, 4, "B", [],             1.30, 1.20, 10, 26, 0.50),
    _m("cotton_seed_m", "Cotton Seed Meal",                 CAT_BIO,   545,  625, 38, 20, 40, 12.0, 0.30, 1, 3, "A", [],             1.10, 1.20,  8, 24, 0.65),

    # ── PLASTICS & RUBBER ─────────────────────────────────────────────────────
    _m("hdpe_gran",     "HDPE Granules",                   CAT_POLY,  481,  545, 28, 10, 30,  0.0, 0.00, 1, 1, "B", [],             1.00, 1.15,  7, 16, 0.85),
    _m("ldpe_gran",     "LDPE Granules",                   CAT_POLY,  385,  449, 28, 10, 30,  0.0, 0.00, 1, 1, "B", [],             1.00, 1.15,  7, 16, 0.85),
    _m("pp_gran",       "Polypropylene Granules (PP)",      CAT_POLY,  481,  545, 28, 10, 30,  0.0, 0.00, 1, 1, "B", [],             1.00, 1.15,  7, 16, 0.85),
    _m("pvc_powder",    "PVC Powder",                       CAT_POLY,  577,  673, 40, 20, 42,  0.0, 0.30, 2, 4, "A", ["B8"],         1.20, 1.20,  9, 24, 0.60),
    _m("pvc_pellets",   "PVC Pellets",                      CAT_POLY,  609,  689, 30, 12, 32,  0.0, 0.10, 2, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("abs_gran",      "ABS Granules",                     CAT_POLY,  577,  641, 28, 10, 30,  0.0, 0.00, 2, 1, "B", [],             1.00, 1.15,  7, 16, 0.85),
    _m("nylon_gran",    "Nylon Granules (PA)",              CAT_POLY,  609,  673, 30, 12, 32,  0.2, 0.00, 2, 1, "B", [],             1.00, 1.15,  7, 16, 0.85),
    _m("polystyr_bead", "Polystyrene Beads (EPS)",          CAT_POLY,  385,  433, 30, 12, 32,  0.0, 0.00, 1, 1, "A", [],             1.00, 1.15,  7, 16, 0.85),
    _m("pe_powder",     "Polyethylene Powder",              CAT_POLY,  433,  497, 38, 18, 40,  0.0, 0.20, 2, 3, "A", ["B10","B11"],  1.10, 1.20,  8, 22, 0.65),
    _m("rubber_gran",   "Rubber Granules (vulcanized)",     CAT_POLY,  577,  641, 38, 18, 40,  0.5, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 22, 0.65),
    _m("rubber_crumb",  "Rubber Crumb (tyre-derived)",      CAT_POLY,  385,  449, 40, 20, 42,  1.0, 0.30, 3, 4, "A", ["B10","B11"],  1.20, 1.20,  9, 24, 0.60),
    _m("tire_chips",    "Tire Chips",                        CAT_POLY,  449,  529, 42, 22, 44,  1.0, 0.20, 4, 4, "C", [],             1.20, 1.20,  9, 26, 0.60),
    _m("pet_chips",     "PET Chips / Flake",                CAT_POLY,  673,  769, 32, 14, 34,  0.1, 0.00, 2, 2, "B", [],             1.00, 1.15,  7, 18, 0.80),
    _m("recycled_plast","Recycled Plastic (mixed regrind)", CAT_POLY,  513,  593, 35, 17, 37,  1.0, 0.10, 3, 3, "B", [],             1.10, 1.15,  8, 20, 0.75),
    _m("ptfe_powder",   "PTFE Powder",                      CAT_POLY, 1201, 1362, 38, 18, 40,  0.0, 0.10, 4, 3, "A", [],             1.20, 1.25,  9, 22, 0.70),
    _m("polyureth",     "Polyurethane Pellets",             CAT_POLY,  513,  593, 30, 12, 32,  0.0, 0.10, 2, 2, "B", [],             1.00, 1.15,  7, 16, 0.85),

    # ── ENVIRONMENTAL & WASTE ─────────────────────────────────────────────────
    _m("msw",           "Municipal Solid Waste (shredded)", CAT_ENV,   241,  289, 35, 17, 37, 25.0, 0.30, 2, 3, "E", ["B8"],         1.30, 1.20, 10, 22, 0.55),
    _m("rdf",           "Refuse Derived Fuel (RDF/SRF)",   CAT_ENV,   193,  241, 40, 22, 42, 15.0, 0.30, 2, 4, "E", ["B11"],        1.30, 1.20, 10, 26, 0.55),
    _m("sewage_cake",   "Sewage Sludge Cake",              CAT_ENV,   865, 1009, 42, 22, 44, 70.0, 0.80, 2, 4, "A", ["B8"],         1.40, 1.25, 11, 30, 0.45),
    _m("biosolids_dry", "Biosolids (thermally dried)",     CAT_ENV,   801,  897, 42, 22, 44, 10.0, 0.50, 2, 4, "A", ["B8"],         1.40, 1.25, 11, 28, 0.55),
    _m("inc_ash",       "Incinerator Bottom Ash (IBA)",    CAT_ENV,   897, 1009, 38, 20, 40,  5.0, 0.30, 5, 3, "A", ["B8"],         1.30, 1.25, 10, 24, 0.65),
    _m("foundry_sand",  "Foundry Sand (used/reclaimed)",   CAT_ENV,  1602, 1762, 35, 15, 37,  5.0, 0.20, 6, 3, "A", [],             1.20, 1.25,  9, 22, 0.70),
    _m("mine_tailings", "Mine Tailings",                    CAT_ENV,  1442, 1602, 38, 18, 40, 15.0, 0.30, 6, 3, "A", [],             1.30, 1.25, 10, 24, 0.65),
    _m("filter_cake",   "Filter Cake (generic wet)",       CAT_ENV,  1201, 1346, 42, 22, 44, 25.0, 0.80, 3, 4, "A", [],             1.40, 1.25, 11, 28, 0.45),
    _m("filter_cake_dry","Filter Cake (dried)",             CAT_ENV,   849,  961, 40, 20, 42,  8.0, 0.50, 3, 4, "A", [],             1.30, 1.20, 10, 26, 0.55),
    _m("drill_cutting", "Drilling Cuttings",               CAT_ENV,  1281, 1442, 35, 17, 37, 20.0, 0.40, 5, 3, "A", [],             1.20, 1.20,  9, 24, 0.60),
    _m("spent_cat",     "Spent Catalyst",                   CAT_ENV,   897, 1009, 38, 18, 40,  5.0, 0.30, 6, 3, "B", [],             1.20, 1.25,  9, 24, 0.65),
    _m("red_mud",       "Red Mud (bauxite residue)",        CAT_ENV,  1201, 1362, 42, 22, 44, 40.0, 0.70, 3, 4, "A", ["B4"],         1.40, 1.25, 11, 28, 0.45),

    # ── SALTS & INORGANIC ─────────────────────────────────────────────────────
    _m("sod_tripolyphos","Sodium Tripolyphosphate (STPP)",  CAT_SALT,  769,  865, 40, 20, 42,  0.5, 0.40, 2, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("barium_sulfate","Barium Sulfate (barite)",          CAT_SALT, 1922, 2163, 38, 18, 40,  0.5, 0.20, 3, 3, "A", [],             1.20, 1.20,  9, 22, 0.70),
    _m("barium_carb",   "Barium Carbonate",                 CAT_SALT, 1522, 1682, 38, 18, 40,  0.5, 0.30, 3, 3, "A", [],             1.20, 1.20,  9, 24, 0.65),
    _m("lithium_carb",  "Lithium Carbonate",                CAT_SALT,  801,  897, 38, 18, 40,  0.5, 0.30, 3, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("potass_hydr",   "Potassium Hydroxide (flake)",      CAT_SALT, 1201, 1346, 38, 18, 40,  0.5, 0.30, 3, 3, "B", ["B4"],         1.20, 1.20,  9, 24, 0.65),
    _m("sodium_phos",   "Sodium Phosphate (TSP)",           CAT_SALT, 1073, 1201, 38, 18, 40,  0.5, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("magn_carb",     "Magnesium Carbonate",              CAT_SALT,  769,  865, 40, 20, 42,  1.0, 0.40, 2, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("evap_salt",     "Salt (evaporated / food grade)",   CAT_SALT, 1201, 1346, 32, 14, 34,  0.1, 0.20, 3, 3, "B", ["B4"],         1.10, 1.20,  8, 20, 0.75),
    _m("borax_anhyd",   "Borax (anhydrous)",                CAT_SALT,  849,  961, 36, 17, 38,  0.5, 0.20, 2, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("cal_phosphate", "Calcium Phosphate (dibasic)",      CAT_SALT,  897, 1009, 38, 18, 40,  0.5, 0.30, 3, 3, "A", [],             1.20, 1.20,  9, 24, 0.65),
    _m("ferrous_sulf",  "Ferrous Sulfate",                  CAT_SALT, 1282, 1442, 38, 18, 40,  0.5, 0.30, 3, 4, "A", [],             1.10, 1.20,  9, 24, 0.65),
    _m("zinc_sulfate",  "Zinc Sulfate",                     CAT_SALT, 1442, 1602, 35, 16, 37,  0.3, 0.20, 3, 3, "A", [],             1.10, 1.20,  8, 22, 0.70),
    _m("magn_sulfate",  "Magnesium Sulfate (Epsom salt)",   CAT_SALT, 1073, 1201, 38, 18, 40,  0.5, 0.20, 3, 3, "A", [],             1.10, 1.20,  8, 22, 0.70),

    # ── GLASS & ADVANCED CERAMICS ─────────────────────────────────────────────
    _m("glass_beads",   "Glass Beads (spherical)",          CAT_GLASS,1442, 1602, 25,  8, 27,  0.0, 0.00, 6, 1, "A", [],             1.00, 1.15,  7, 14, 0.90),
    _m("glass_powder",  "Glass Powder",                     CAT_GLASS,1281, 1442, 38, 18, 40,  0.0, 0.20, 7, 3, "A", ["B8"],         1.20, 1.25,  9, 22, 0.65),
    _m("glass_cullet_f","Glass Cullet (fine, <25mm)",       CAT_GLASS,1201, 1362, 35, 17, 37,  0.0, 0.10, 7, 3, "A", ["B8"],         1.20, 1.25,  9, 20, 0.70),
    _m("glass_cullet_c","Glass Cullet (coarse, >25mm)",     CAT_GLASS,1281, 1442, 30, 12, 32,  0.0, 0.10, 7, 2, "C", ["B8"],         1.10, 1.20,  8, 18, 0.75),
    _m("ceramic_gran",  "Ceramic Granules",                  CAT_GLASS,1281, 1442, 35, 17, 37,  0.5, 0.10, 6, 3, "B", [],             1.20, 1.20,  8, 22, 0.70),
    _m("alumina_trihy", "Alumina Trihydrate (ATH)",          CAT_GLASS, 769,  865, 40, 20, 42,  1.0, 0.30, 5, 4, "A", [],             1.20, 1.20,  9, 24, 0.65),
    _m("zirconia",      "Zirconia (ZrO₂)",                   CAT_GLASS,2323, 2564, 35, 17, 37,  0.2, 0.10, 7, 3, "A", [],             1.30, 1.25, 10, 22, 0.70),
    _m("fused_silica",  "Fused Silica",                      CAT_GLASS,1201, 1362, 38, 18, 40,  0.0, 0.20, 7, 3, "A", ["B8"],         1.20, 1.25,  9, 22, 0.65),
    _m("glass_fiber",   "Glass Fiber (chopped)",             CAT_GLASS, 225,  289, 38, 20, 40,  0.5, 0.20, 5, 3, "E", [],             1.20, 1.20,  9, 24, 0.60),
    _m("silicon_pwd",   "Silicon Powder",                    CAT_GLASS, 769,  865, 38, 18, 40,  0.0, 0.20, 7, 3, "A", ["B8"],         1.20, 1.25,  9, 22, 0.65),

    # ── PETROLEUM & REFINERY ──────────────────────────────────────────────────
    _m("petcoke_green", "Petroleum Coke (green, delayed)",  CAT_PETRO, 865,  961, 35, 17, 37,  5.0, 0.10, 5, 3, "B", ["B11"],        1.10, 1.20,  8, 20, 0.70),
    _m("petcoke_calc",  "Petroleum Coke (calcined)",        CAT_PETRO, 769,  865, 35, 17, 37,  1.0, 0.10, 5, 3, "B", ["B8","B11"],   1.10, 1.20,  8, 20, 0.70),
    _m("petcoke_fluid", "Petroleum Coke (fluid coke)",      CAT_PETRO, 801,  897, 38, 18, 40,  1.0, 0.10, 5, 3, "A", ["B11"],        1.10, 1.20,  8, 20, 0.70),
    _m("sulfur_pwd",    "Sulfur (powder)",                  CAT_PETRO,1201, 1346, 30, 12, 32,  0.0, 0.10, 2, 2, "A", ["B10","B11"],  1.00, 1.15,  7, 16, 0.80),
    _m("paraffin_wax",  "Paraffin Wax (pellets/flake)",     CAT_PETRO, 641,  737, 35, 17, 37,  0.0, 0.20, 2, 3, "B", ["B11"],        1.10, 1.20,  8, 22, 0.70),
    _m("asphalt_gran2", "Asphalt Granules (refined)",       CAT_PETRO,1009, 1137, 35, 17, 37,  0.0, 0.20, 4, 3, "B", ["B11"],        1.10, 1.20,  8, 22, 0.70),
    _m("coal_tar_pitch","Coal Tar Pitch",                    CAT_PETRO, 865,  961, 35, 17, 37,  0.0, 0.20, 3, 3, "B", ["B10","B11"],  1.10, 1.20,  8, 22, 0.70),
    _m("spent_fcc",     "Spent FCC Catalyst",               CAT_PETRO, 897, 1009, 38, 18, 40,  2.0, 0.30, 5, 3, "A", [],             1.20, 1.20,  9, 24, 0.65),
    _m("zeolite_cat",   "Zeolite Catalyst",                  CAT_PETRO, 769,  865, 38, 18, 40,  2.0, 0.20, 5, 3, "A", [],             1.20, 1.20,  9, 22, 0.65),
    _m("carbon_mol_sv", "Carbon Molecular Sieve",            CAT_PETRO, 481,  561, 38, 18, 40,  1.0, 0.20, 4, 3, "A", ["B10"],        1.20, 1.20,  9, 22, 0.65),

    # ── PHARMACEUTICAL & FINE INGREDIENTS ────────────────────────────────────
    _m("cellulose_mcc", "Microcrystalline Cellulose (MCC)", CAT_PHARM, 385,  449, 42, 22, 44,  3.0, 0.40, 1, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("lactose_pharm", "Lactose (pharm grade)",            CAT_PHARM, 577,  673, 38, 18, 40,  3.0, 0.30, 1, 3, "A", [],             1.10, 1.15,  8, 22, 0.65),
    _m("magnesium_st",  "Magnesium Stearate",               CAT_PHARM, 369,  449, 35, 17, 37,  0.5, 0.20, 1, 3, "A", [],             1.10, 1.15,  8, 22, 0.65),
    _m("silicon_diox",  "Silicon Dioxide (fumed silica)",   CAT_PHARM, 545,  641, 42, 22, 44,  0.5, 0.40, 7, 4, "A", ["B8"],         1.20, 1.25,  9, 28, 0.55),
    _m("xanthan_gum",   "Xanthan Gum",                      CAT_PHARM, 577,  673, 40, 22, 42,  5.0, 0.50, 1, 4, "A", [],             1.30, 1.20, 10, 28, 0.50),
    _m("guar_gum",      "Guar Gum",                          CAT_PHARM, 577,  673, 40, 22, 42,  8.0, 0.50, 1, 4, "A", [],             1.30, 1.20, 10, 28, 0.50),
    _m("ascorbic_acid", "Ascorbic Acid (Vitamin C)",         CAT_PHARM, 737,  833, 38, 20, 40,  1.0, 0.30, 3, 4, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("citric_acid_ph","Citric Acid (fine powder)",         CAT_PHARM, 769,  865, 40, 20, 42,  1.0, 0.30, 3, 4, "A", ["B4"],         1.10, 1.20,  8, 24, 0.65),
    _m("pectin",        "Pectin",                            CAT_PHARM, 481,  561, 40, 22, 42,  5.0, 0.50, 1, 4, "A", [],             1.20, 1.20,  9, 28, 0.50),
    _m("sodium_alginate","Sodium Alginate",                  CAT_PHARM, 769,  865, 38, 18, 40,  5.0, 0.40, 1, 3, "A", [],             1.20, 1.20,  9, 24, 0.60),

    # ── ADDITIONAL GRAINS & SEEDS ─────────────────────────────────────────────
    _m("quinoa",        "Quinoa",                        CAT_GRAIN, 721,  785, 26,  8, 28, 12.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("amaranth",      "Amaranth Seeds",                 CAT_GRAIN, 769,  833, 26,  8, 28, 10.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("hemp_seed",     "Hemp Seeds",                     CAT_GRAIN, 625,  689, 28, 10, 30,  8.0, 0.10, 1, 2, "B", [],             1.00, 1.15,  7, 16, 0.80),
    _m("chia_seed",     "Chia Seeds",                     CAT_GRAIN, 705,  769, 26,  8, 28,  8.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),
    _m("mustard_seed",  "Mustard Seeds",                  CAT_GRAIN, 689,  753, 26,  8, 28,  8.0, 0.10, 1, 2, "A", [],             1.00, 1.15,  7, 14, 0.80),

    # ── ADDITIONAL FOOD PRODUCTS ───────────────────────────────────────────────
    _m("soy_protein",   "Soy Protein Isolate",            CAT_FOOD,  353,  433, 42, 22, 44,  5.0, 0.50, 1, 4, "A", ["B1"],         1.20, 1.20,  9, 28, 0.55),
    _m("casein",        "Casein (dried)",                  CAT_FOOD,  641,  721, 40, 20, 42,  5.0, 0.40, 1, 4, "A", ["B1"],         1.20, 1.20,  9, 26, 0.60),
    _m("gelatin",       "Gelatin (powder)",                CAT_FOOD,  497,  577, 40, 22, 42,  8.0, 0.40, 1, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("dried_egg",     "Dried Egg (whole/albumen)",       CAT_FOOD,  433,  513, 38, 20, 40,  4.0, 0.40, 1, 4, "A", ["B1","B8"],    1.20, 1.20,  9, 26, 0.60),
    _m("modified_starch","Modified Starch",                CAT_FOOD,  577,  673, 42, 22, 44,  8.0, 0.40, 1, 4, "A", ["B1"],         1.20, 1.20,  9, 26, 0.55),
    _m("yeast_dried",   "Yeast (dried/torula)",            CAT_FOOD,  481,  561, 38, 20, 40,  5.0, 0.40, 1, 4, "A", ["B11"],        1.20, 1.20,  8, 26, 0.60),
    _m("inulin",        "Inulin (chicory fructan)",        CAT_FOOD,  577,  657, 38, 18, 40,  3.0, 0.30, 1, 3, "A", [],             1.10, 1.15,  8, 22, 0.65),
    _m("breadcrumbs",   "Breadcrumbs / Panko",             CAT_FOOD,  321,  369, 38, 20, 40, 10.0, 0.20, 1, 3, "A", [],             1.10, 1.15,  8, 22, 0.65),

    # ── ADDITIONAL FERTILIZERS ────────────────────────────────────────────────
    _m("zeolite_fert",  "Zeolite (slow-release fert)",     CAT_FERT,  769,  865, 38, 18, 40,  5.0, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("bio_char",      "Biochar (soil amendment)",         CAT_FERT,  177,  225, 42, 22, 44, 15.0, 0.30, 1, 4, "A", [],             1.20, 1.15,  9, 26, 0.60),
    _m("leonardite",    "Leonardite (humate ore)",          CAT_FERT,  545,  625, 38, 20, 40, 20.0, 0.40, 2, 3, "A", [],             1.10, 1.20,  8, 24, 0.60),
    _m("potassium_hum", "Potassium Humate",                 CAT_FERT,  641,  737, 38, 20, 40, 10.0, 0.40, 2, 4, "A", [],             1.20, 1.20,  9, 24, 0.60),
    _m("amm_polyphos",  "Ammonium Polyphosphate (dry)",     CAT_FERT,  897, 1009, 35, 16, 37,  1.0, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),

    # ── ADDITIONAL MINERALS ───────────────────────────────────────────────────
    _m("fluorite",      "Fluorite (fluorspar)",             CAT_MIN, 1922, 2163, 38, 18, 40,  1.0, 0.10, 5, 3, "B", ["B4"],         1.20, 1.20,  9, 22, 0.70),
    _m("celestite",     "Celestite (strontium sulfate)",   CAT_MIN, 2082, 2323, 38, 18, 40,  0.5, 0.10, 5, 3, "B", [],             1.20, 1.25, 10, 22, 0.70),
    _m("spodumene",     "Spodumene (lithium ore)",          CAT_MIN, 1602, 1762, 38, 18, 40,  1.0, 0.10, 6, 3, "B", [],             1.30, 1.25, 10, 22, 0.70),
    _m("scheelite",     "Scheelite (tungsten ore)",         CAT_MIN, 3204, 3525, 38, 18, 40,  0.5, 0.10, 7, 3, "B", [],             1.40, 1.25, 11, 24, 0.70),
    _m("cassiterite",   "Cassiterite (tin ore)",            CAT_MIN, 2724, 3044, 38, 18, 40,  1.0, 0.10, 7, 3, "B", [],             1.40, 1.25, 11, 24, 0.70),
    _m("columbite",     "Columbite / Niobite",              CAT_MIN, 3044, 3365, 38, 18, 40,  0.5, 0.10, 7, 3, "B", [],             1.40, 1.25, 11, 24, 0.70),
    _m("andalusite",    "Andalusite",                       CAT_MIN, 1362, 1522, 38, 18, 40,  0.5, 0.10, 7, 3, "B", ["B8"],         1.30, 1.25, 10, 22, 0.70),
    _m("kyanite",       "Kyanite",                          CAT_MIN, 1522, 1682, 40, 20, 42,  0.5, 0.10, 7, 3, "B", ["B8"],         1.30, 1.25, 10, 24, 0.70),
    _m("sillimanite",   "Sillimanite",                      CAT_MIN, 1442, 1602, 40, 20, 42,  0.5, 0.10, 7, 3, "B", ["B8"],         1.30, 1.25, 10, 24, 0.70),
    _m("nepheline",     "Nepheline Syenite",                CAT_MIN, 1137, 1281, 38, 18, 40,  0.5, 0.10, 5, 3, "B", ["B8"],         1.20, 1.20,  9, 22, 0.70),
    _m("anorthosite",   "Anorthosite (alumina mineral)",    CAT_MIN, 1346, 1506, 38, 18, 40,  0.5, 0.10, 6, 3, "C", [],             1.20, 1.20,  9, 22, 0.70),
    _m("chromite",      "Chromite",                         CAT_MIN, 2243, 2484, 38, 18, 40,  2.0, 0.10, 7, 3, "B", [],             1.40, 1.25, 11, 24, 0.70),
    _m("serpentine",    "Serpentinite",                     CAT_MIN, 1522, 1682, 38, 18, 40,  2.0, 0.10, 5, 3, "C", [],             1.20, 1.20,  9, 22, 0.70),
    _m("talc_fine",     "Talc (ultrafine, ≤ 10µm)",         CAT_MIN,  577,  673, 38, 20, 40,  0.5, 0.40, 2, 4, "A", ["B8"],         1.20, 1.20,  9, 26, 0.60),
    _m("cobalt_ore",    "Cobalt Ore",                       CAT_MIN, 1922, 2163, 40, 20, 42,  3.0, 0.10, 7, 3, "C", [],             1.40, 1.25, 11, 26, 0.70),
    _m("molybdenite",   "Molybdenite (MoS₂ ore)",           CAT_MIN, 1922, 2163, 38, 18, 40,  2.0, 0.10, 6, 3, "B", [],             1.30, 1.25, 10, 22, 0.70),
    _m("trona_ore",     "Trona (soda ash ore)",              CAT_MIN, 1009, 1137, 34, 15, 36,  1.0, 0.20, 3, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),

    # ── ADDITIONAL CHEMICALS ──────────────────────────────────────────────────
    _m("sodium_percarb","Sodium Percarbonate",              CAT_CHEM,  865,  961, 38, 18, 40,  0.5, 0.30, 2, 3, "A", ["B10"],        1.10, 1.20,  8, 22, 0.65),
    _m("potass_percarb","Potassium Percarbonate",           CAT_CHEM,  897,  993, 38, 18, 40,  0.5, 0.30, 2, 3, "A", ["B10"],        1.10, 1.20,  8, 22, 0.65),
    _m("sodium_perbor", "Sodium Perborate",                 CAT_CHEM,  897, 1009, 38, 18, 40,  0.5, 0.30, 2, 3, "A", ["B10"],        1.10, 1.20,  8, 22, 0.65),
    _m("oxalic_acid",   "Oxalic Acid",                      CAT_CHEM,  769,  865, 38, 18, 40,  0.5, 0.30, 2, 4, "A", ["B4"],         1.10, 1.20,  8, 24, 0.65),
    _m("tartaric_acid", "Tartaric Acid",                    CAT_CHEM,  753,  849, 38, 18, 40,  0.5, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("fumaric_acid",  "Fumaric Acid",                     CAT_CHEM,  737,  833, 38, 18, 40,  0.5, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("stearic_acid",  "Stearic Acid (flake)",             CAT_CHEM,  481,  561, 35, 17, 37,  0.5, 0.20, 1, 3, "B", ["B11"],        1.10, 1.20,  8, 22, 0.70),
    _m("zinc_stearate2","Zinc Stearate (fine)",             CAT_CHEM,  225,  289, 38, 18, 40,  0.5, 0.20, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("chrome_oxide_g","Chromium Oxide Green (pigment)",   CAT_CHEM, 1201, 1362, 40, 20, 42,  0.5, 0.20, 6, 4, "A", [],             1.20, 1.25,  9, 26, 0.65),
    _m("lead_oxide",    "Lead Oxide (litharge)",            CAT_CHEM, 3204, 3525, 35, 17, 37,  0.5, 0.20, 4, 3, "A", ["B4"],         1.20, 1.25,  9, 22, 0.65),
    _m("manganous_ox",  "Manganous Oxide",                  CAT_CHEM, 1442, 1602, 40, 20, 42,  0.5, 0.20, 5, 4, "A", [],             1.20, 1.20,  9, 26, 0.65),
    _m("vanadium_p5",   "Vanadium Pentoxide",               CAT_CHEM, 1009, 1137, 40, 20, 42,  0.5, 0.30, 5, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),

    # ── ADDITIONAL CONSTRUCTION ───────────────────────────────────────────────
    _m("silica_fume",   "Silica Fume (microsilica)",        CAT_CONST, 209,  289, 45, 25, 47,  0.5, 0.60, 7, 4, "A", ["B8"],         1.40, 1.25, 11, 30, 0.45),
    _m("ggbs",          "GGBS (slag cement fine)",          CAT_CONST,1201, 1362, 40, 20, 42,  2.0, 0.40, 5, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("metakaolin",    "Metakaolin (calcined clay)",        CAT_CONST, 641,  769, 42, 22, 44,  1.0, 0.50, 4, 4, "A", ["B8"],         1.30, 1.20, 10, 28, 0.55),
    _m("pfa",           "PFA (Pulverised Fuel Ash)",         CAT_CONST, 769,  897, 42, 22, 44,  0.5, 0.40, 3, 4, "A", ["B1","B8"],    1.20, 1.20,  9, 26, 0.60),
    _m("lytag",         "Lytag (sintered PFA aggregate)",    CAT_CONST, 769,  865, 30, 12, 32,  2.0, 0.10, 4, 2, "B", [],             1.10, 1.15,  8, 20, 0.75),
    _m("ground_glass",  "Ground Glass (fine sand)",          CAT_CONST,1281, 1442, 35, 17, 37,  0.0, 0.10, 7, 3, "A", ["B8"],         1.20, 1.25,  9, 22, 0.70),
    _m("calcium_silum", "Calcium Silicate (insulation)",     CAT_CONST, 385,  449, 40, 22, 42,  3.0, 0.40, 3, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("aac_powder",    "AAC Powder (autoclaved aerated)",   CAT_CONST, 433,  513, 38, 20, 40,  3.0, 0.40, 3, 4, "A", [],             1.20, 1.20,  9, 24, 0.60),

    # ── ADDITIONAL METALS ─────────────────────────────────────────────────────
    _m("titanium_pwd",  "Titanium Powder (sponge)",          CAT_METAL,1201, 1362, 35, 17, 37,  0.0, 0.10, 6, 3, "A", ["B6","B10"],   1.30, 1.30, 10, 22, 0.70),
    _m("tin_powder",    "Tin Powder",                        CAT_METAL,1922, 2163, 35, 17, 37,  0.0, 0.10, 5, 3, "A", [],             1.20, 1.25,  9, 22, 0.70),
    _m("cobalt_pwd",    "Cobalt Powder",                     CAT_METAL,2082, 2323, 38, 18, 40,  0.0, 0.20, 5, 3, "A", [],             1.30, 1.25, 10, 24, 0.65),
    _m("chromium_pwd",  "Chromium Powder",                   CAT_METAL,2002, 2243, 38, 18, 40,  0.0, 0.10, 7, 3, "A", [],             1.30, 1.25, 10, 24, 0.70),
    _m("ferrosilicon",  "Ferrosilicon (crushed)",             CAT_METAL,2403, 2644, 35, 17, 37,  0.5, 0.10, 7, 3, "C", [],             1.30, 1.25, 10, 22, 0.70),
    _m("ferrochrome",   "Ferrochrome",                        CAT_METAL,2724, 3044, 35, 17, 37,  0.5, 0.10, 7, 3, "C", [],             1.40, 1.25, 11, 22, 0.70),
    _m("ferromang",     "Ferromanganese",                     CAT_METAL,2724, 3044, 35, 17, 37,  0.5, 0.10, 7, 3, "C", [],             1.40, 1.25, 11, 22, 0.70),
    _m("ferro_niobi",   "Ferroniobium",                       CAT_METAL,3044, 3365, 35, 17, 37,  0.5, 0.10, 7, 3, "C", [],             1.40, 1.25, 11, 22, 0.70),

    # ── ADDITIONAL BIOMASS ────────────────────────────────────────────────────
    _m("hemp_fiber",    "Hemp Fiber (chopped)",               CAT_BIO,   177,  225, 42, 22, 44, 12.0, 0.30, 1, 4, "E", [],             1.20, 1.15,  8, 26, 0.55),
    _m("jute_fiber",    "Jute Fiber",                         CAT_BIO,   193,  241, 40, 22, 42, 10.0, 0.30, 1, 4, "E", [],             1.20, 1.15,  8, 26, 0.55),
    _m("sisal_fiber",   "Sisal Fiber",                        CAT_BIO,   209,  257, 40, 22, 42, 10.0, 0.30, 1, 4, "E", [],             1.20, 1.15,  8, 26, 0.55),
    _m("algae_dried",   "Algae (dried, spirulina/chlorella)", CAT_BIO,   481,  561, 38, 20, 40,  5.0, 0.40, 1, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("coffee_pulp",   "Coffee Pulp (dried)",                CAT_BIO,   449,  529, 40, 22, 42, 15.0, 0.40, 1, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("palm_fiber",    "Palm Fiber / EFB",                   CAT_BIO,   193,  241, 42, 22, 44, 30.0, 0.30, 1, 4, "E", ["B11"],        1.20, 1.15,  9, 28, 0.55),
    _m("distillers_dry","Distillers Dried Grains (DDGS)",     CAT_BIO,   449,  529, 38, 20, 40, 10.0, 0.30, 1, 3, "A", [],             1.10, 1.20,  8, 24, 0.65),
    _m("cotton_lint",   "Cotton Lint / Seed Cotton",          CAT_BIO,    64,   96, 42, 22, 44,  8.0, 0.30, 1, 4, "E", [],             1.30, 1.15,  9, 28, 0.50),

    # ── ADDITIONAL SALTS ──────────────────────────────────────────────────────
    _m("amm_citrate",   "Ammonium Citrate",                   CAT_SALT,  769,  865, 38, 18, 40,  1.0, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("calcium_citrate","Calcium Citrate",                    CAT_SALT,  897,  993, 38, 18, 40,  1.0, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("ferrous_gluc",  "Ferrous Gluconate",                   CAT_SALT,  769,  865, 38, 18, 40,  1.0, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("zinc_acetate",  "Zinc Acetate",                        CAT_SALT, 1009, 1137, 38, 18, 40,  1.0, 0.20, 3, 3, "A", ["B4"],         1.10, 1.20,  8, 22, 0.65),
    _m("mang_chloride", "Manganese Chloride",                  CAT_SALT, 1090, 1201, 36, 17, 38,  1.0, 0.30, 3, 3, "A", ["B4"],         1.20, 1.20,  8, 22, 0.65),
    _m("cupric_oxide",  "Cupric Oxide (black copper oxide)",   CAT_SALT, 1282, 1442, 38, 18, 40,  0.5, 0.20, 4, 3, "A", [],             1.20, 1.20,  9, 24, 0.65),
    _m("barium_hydroxide","Barium Hydroxide (dry)",            CAT_SALT, 1121, 1281, 38, 18, 40,  0.5, 0.30, 3, 3, "A", ["B4"],         1.20, 1.20,  9, 24, 0.65),
    _m("stannous_chlor","Stannous Chloride",                   CAT_SALT, 1281, 1442, 36, 17, 38,  1.0, 0.20, 3, 3, "A", ["B4"],         1.10, 1.20,  8, 22, 0.65),
    _m("potass_bicarb", "Potassium Bicarbonate",               CAT_SALT,  961, 1090, 38, 18, 40,  1.0, 0.30, 2, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("amm_bifluoride","Ammonium Bifluoride",                 CAT_SALT, 1362, 1522, 36, 17, 38,  0.5, 0.20, 3, 3, "A", ["B4"],         1.10, 1.20,  8, 22, 0.65),

    # ── ADDITIONAL CEMENT / LIME ──────────────────────────────────────────────
    _m("cement_type2",  "Portland Cement Type II",            CAT_CEM, 1506, 1762, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("cement_type3",  "Portland Cement Type III (rapid)",   CAT_CEM, 1506, 1762, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("high_alumina_c","High Alumina Cement",                 CAT_CEM, 1346, 1602, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("oil_well_cem",  "Oil Well Cement",                     CAT_CEM, 1442, 1682, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("anhydrite",     "Anhydrite (calcium sulfate)",         CAT_CEM, 1201, 1362, 38, 18, 40,  0.5, 0.20, 4, 3, "B", [],             1.10, 1.20,  8, 22, 0.70),
    _m("calcium_sulfoal","Calcium Sulfoaluminate Cement",     CAT_CEM, 1346, 1602, 40, 20, 42,  0.1, 0.50, 5, 4, "A", ["B1","B8"],    1.40, 1.25, 10, 26, 0.55),
    _m("natural_cement","Natural Cement (Roman cement)",       CAT_CEM, 1201, 1442, 40, 20, 42,  0.5, 0.40, 4, 4, "A", ["B8"],         1.30, 1.20,  9, 26, 0.60),

    # ── ADDITIONAL GLASS / CERAMICS ───────────────────────────────────────────
    _m("borosilicate_g","Borosilicate Glass Powder",           CAT_GLASS,1201, 1362, 38, 18, 40,  0.0, 0.20, 7, 3, "A", ["B8"],         1.20, 1.25,  9, 22, 0.65),
    _m("silicon_nitride","Silicon Nitride Powder",             CAT_GLASS,1201, 1362, 38, 18, 40,  0.0, 0.10, 7, 3, "A", [],             1.30, 1.30, 10, 22, 0.65),
    _m("boron_nitride", "Boron Nitride",                       CAT_GLASS, 641,  769, 35, 17, 37,  0.0, 0.10, 6, 3, "A", [],             1.20, 1.25,  9, 22, 0.65),
    _m("boron_carb",    "Boron Carbide",                       CAT_GLASS, 961, 1090, 35, 17, 37,  0.0, 0.10, 7, 3, "A", [],             1.30, 1.30, 10, 22, 0.65),
    _m("glass_microsph","Glass Microspheres (hollow)",          CAT_GLASS, 289,  369, 30, 12, 32,  0.0, 0.00, 5, 1, "A", [],             1.10, 1.20,  7, 16, 0.85),

    # ── ADDITIONAL ENVIRONMENTAL ──────────────────────────────────────────────
    _m("biochar_pellet","Biochar Pellets",                     CAT_ENV,   449,  529, 32, 14, 34,  8.0, 0.20, 1, 3, "B", [],             1.10, 1.15,  8, 22, 0.70),
    _m("char_ash",      "Char Ash (combustion residue)",       CAT_ENV,   609,  689, 38, 20, 40, 10.0, 0.40, 4, 4, "A", [],             1.30, 1.25, 10, 26, 0.60),
    _m("dem_debris",    "Demolition Debris (crushed)",          CAT_ENV,  1281, 1442, 38, 18, 40, 10.0, 0.20, 5, 3, "C", [],             1.20, 1.20,  9, 22, 0.65),
    _m("hazard_waste",  "Hazardous Waste (stabilised solid)",   CAT_ENV,  1201, 1362, 38, 18, 40, 15.0, 0.40, 4, 4, "A", ["B4","B8"],    1.40, 1.25, 11, 26, 0.55),

    # ── ADDITIONAL PHARMA / SPECIALTY ────────────────────────────────────────
    _m("hydroxypropyl", "Hydroxypropyl Methylcellulose (HPMC)", CAT_PHARM, 289, 369, 42, 22, 44, 5.0, 0.50, 1, 4, "A", [],          1.30, 1.20, 10, 28, 0.50),
    _m("cyclodextrin",  "Beta-Cyclodextrin",                 CAT_PHARM, 577,  673, 38, 18, 40,  5.0, 0.30, 1, 3, "A", [],             1.10, 1.20,  8, 22, 0.65),
    _m("crospovidone",  "Crospovidone (disintegrant)",        CAT_PHARM, 353,  433, 40, 22, 42,  5.0, 0.40, 1, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("pea_protein",   "Pea Protein Isolate",                CAT_FOOD,  481,  561, 40, 22, 42,  7.0, 0.40, 1, 4, "A", ["B1"],         1.20, 1.20,  9, 26, 0.55),
    _m("rice_protein",  "Rice Protein Concentrate",           CAT_FOOD,  513,  593, 40, 22, 42,  6.0, 0.40, 1, 4, "A", ["B1"],         1.20, 1.20,  9, 26, 0.55),

    # ── CUSTOM / FALLBACK ─────────────────────────────────────────────────────
    _m("ironore_sinter","Iron Ore Sinter (cold)",            CAT_MIN, 1762, 1922, 40, 20, 42,  0.5, 0.10, 7, 3, "D", [],             1.30, 1.25, 10, 26, 0.70),
    _m("sand_gravel",   "Sand/Gravel Mix",                   CAT_MIN, 1522, 1682, 33, 15, 35,  3.0, 0.10, 5, 2, "C", [],             1.10, 1.15,  8, 20, 0.70),
    _m("taconite",      "Taconite Pellets",                  CAT_MIN, 2243, 2484, 28, 10, 30,  1.0, 0.00, 7, 1, "B", [],             1.30, 1.25,  9, 16, 0.85),
    _m("fly_ash_poz",   "Fly Ash (pozzolanic, Class C/F)",  CAT_CONST, 769,  897, 42, 22, 44,  0.5, 0.40, 3, 4, "A", ["B1","B8"],    1.20, 1.20,  9, 26, 0.60),
    _m("slag_pwdr",     "Slag Powder (GGBFS, fine)",         CAT_CEM, 1201, 1362, 40, 20, 42,  2.0, 0.40, 5, 4, "A", [],             1.20, 1.20,  9, 26, 0.60),
    _m("coal_washed",   "Coal (washed, clean)",              CAT_COAL,  897, 1009, 35, 17, 37, 15.0, 0.20, 5, 3, "D", ["B6","B10","B11"], 1.20, 1.20, 9, 22, 0.65),
    _m("custom",        "Custom Material",                   CAT_MIN, 1000, 1100, 35, 15, 37,  0.0, 0.10, 3, 3, "B", [],             1.10, 1.15,  8, 20, 0.75),
]


# ═══════════════════════════════════════════════════════════════════════════════
# LOOKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_material(mat_id: str) -> dict:
    """Return material dict by id; falls back to 'custom' if not found."""
    for m in MATERIALS:
        if m["id"] == mat_id:
            return m
    return next(m for m in MATERIALS if m["id"] == "custom")


def search_materials(query: str, category: str | None = None) -> list[dict]:
    """Case-insensitive search by id or name, optionally filtered by category."""
    q = query.lower()
    results = [
        m for m in MATERIALS
        if q in m["id"].lower() or q in m["name"].lower()
    ]
    if category:
        results = [m for m in results if m["category"] == category]
    return results


def list_categories() -> list[str]:
    """Return all category codes present in the database."""
    return sorted({m["category"] for m in MATERIALS})


def materials_by_category(category: str) -> list[dict]:
    """Return all materials for a given category code."""
    return [m for m in MATERIALS if m["category"] == category]


def material_count() -> int:
    return len(MATERIALS)