# VECTRIX Engineering Field Dictionary

*Generated from the live schema on 2026-07-21. Do not edit by hand -- edit `generate_field_dictionary.py` and regenerate.*

This is the engineering contract. If a field's meaning changes, change it here -- not in the solver.

**Tier**: A = populate now &nbsp;|&nbsp; B = as data becomes available &nbsp;|&nbsp; C = future modules &nbsp;|&nbsp; - = not populated in Phase 1

## `materials_v2`  &nbsp;&nbsp;*L1*

Identity & classification. No engineering values.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `material_id` **PK** | INTEGER | Surrogate primary key | - | ALL | A |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `material_name` *NOT NULL* | TEXT | Official material name | - | ALL | A |
| `common_name` | TEXT | Alternate / common name | - | UI | A |
| `category` | TEXT | Industry category (Cement, Mining, Food...) | - | UI, filtering | A |
| `subcategory` | TEXT | Sub-classification (Clinker, Fly Ash...) | - | UI | A |
| `cema_material_code` | TEXT | Full CEMA material code, e.g. 100B36M | - | Classification | A |
| `material_class` | TEXT | Form factor (Powder/Granular/Pellet/...) | - | UI, filtering | A |
| `material_family` | TEXT | Mineral/Organic/Metal/Agricultural/... | - | UI | A |
| `description` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_standard` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_reference` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_revision` | TEXT | _(undocumented)_ | ? | ? | ? |
| `is_active` *NOT NULL* | INTEGER | Source still considered valid | 0/1 | QA | A |
| `created_date` | TEXT | _(undocumented)_ | ? | ? | ? |
| `modified_date` | TEXT | _(undocumented)_ | ? | ? | ? |
| `revision` *NOT NULL* | INTEGER | _(undocumented)_ | ? | ? | ? |

## `material_core`  &nbsp;&nbsp;*L2*

Intrinsic physical + flow properties. True for 1 kg sent to ANY machine.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `material_id` **PK** | INTEGER | Surrogate primary key | - | ALL | A |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `rho_loose` | REAL | Loose-poured bulk density | kg/m3 | ALL solvers | A |
| `rho_bulk` | REAL | Operating bulk density | kg/m3 | Bucket, Screw | A |
| `rho_vib` | REAL | Vibrated / tapped density | kg/m3 | Screw, Air classifier | B |
| `rho_min` | REAL | Density range minimum | kg/m3 | Tolerance studies | B |
| `rho_max` | REAL | Density range maximum | kg/m3 | Tolerance studies | B |
| `specific_gravity` | REAL | Specific gravity (dimensionless) | - | General | B |
| `moisture` | REAL | Typical moisture content | % | Flow, carryback | A |
| `moisture_max` | REAL | Maximum moisture content | % | Flow | B |
| `free_moisture` | REAL | Free (unbound) moisture | % | Carryback, plugging | C |
| `particle_class` | TEXT | CEMA lump-size class A/B/C/D | - | Bucket, Screw | A |
| `particle_size_mm` | REAL | Representative particle size | mm | Bucket, Screw | A |
| `maximum_lump_size` | REAL | Maximum lump size (engineering property) | mm | Bucket, Screw clearance | A |
| `angle_repose` | REAL | Angle of repose | deg | Bucket, Screw, Belt, Hopper | A |
| `angle_surcharge` | REAL | Surcharge angle | deg | Belt, Bucket | A |
| `dynamic_angle_repose` | REAL | Dynamic angle of repose | deg | Discharge trajectory | B |
| `flowability` | INTEGER | Flowability index 1=excellent .. 4=poor | 1-4 | Calculations, fill factor | A |
| `flow_regime` | TEXT | Categorical flow class (Free Flowing/Cohesive/...) | - | Reports, UI | A |
| `flowability_method` | TEXT | How flowability was determined (traceability) | - | QA | A |
| `cohesion` | REAL | Cohesion index | kPa | Screw, Hopper, trajectory | B |
| `compressibility` | REAL | Compressibility | - | Storage, hopper | C |
| `porosity` | REAL | Porosity (0-1) | - | Air classifier | C |
| `void_fraction` | REAL | Void fraction (0-1) | - | Air classifier, DEM | C |
| `mohs_hardness` | REAL | Mohs hardness | 1-10 | Wear models | B |
| `temp_max` | REAL | Maximum service temperature | degC | Belt selection, drive advisory | A |

## `material_particles`  &nbsp;&nbsp;*L2.5*

Particle characterization: PSD, shape, surface, DEM inputs.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `material_id` **PK** | INTEGER | Surrogate primary key | - | ALL | A |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `d10` | REAL | _(undocumented)_ | ? | ? | ? |
| `d20` | REAL | _(undocumented)_ | ? | ? | ? |
| `d30` | REAL | _(undocumented)_ | ? | ? | ? |
| `d40` | REAL | _(undocumented)_ | ? | ? | ? |
| `d50` | REAL | _(undocumented)_ | ? | ? | ? |
| `d60` | REAL | _(undocumented)_ | ? | ? | ? |
| `d70` | REAL | _(undocumented)_ | ? | ? | ? |
| `d80` | REAL | _(undocumented)_ | ? | ? | ? |
| `d90` | REAL | _(undocumented)_ | ? | ? | ? |
| `d95` | REAL | _(undocumented)_ | ? | ? | ? |
| `d99` | REAL | _(undocumented)_ | ? | ? | ? |
| `minimum_particle_size` | REAL | _(undocumented)_ | ? | ? | ? |
| `mean_particle_size` | REAL | _(undocumented)_ | ? | ? | ? |
| `median_particle_size` | REAL | _(undocumented)_ | ? | ? | ? |
| `maximum_particle_size` | REAL | _(undocumented)_ | ? | ? | ? |
| `nominal_top_size` | REAL | _(undocumented)_ | ? | ? | ? |
| `uniformity_coefficient` | REAL | _(undocumented)_ | ? | ? | ? |
| `curvature_coefficient` | REAL | _(undocumented)_ | ? | ? | ? |
| `gradation_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `span` | REAL | _(undocumented)_ | ? | ? | ? |
| `sorting_coefficient` | REAL | _(undocumented)_ | ? | ? | ? |
| `aspect_ratio` | REAL | _(undocumented)_ | ? | ? | ? |
| `sphericity` | REAL | _(undocumented)_ | ? | ? | ? |
| `roundness` | REAL | _(undocumented)_ | ? | ? | ? |
| `angularity` | REAL | _(undocumented)_ | ? | ? | ? |
| `elongation` | REAL | _(undocumented)_ | ? | ? | ? |
| `flatness` | REAL | _(undocumented)_ | ? | ? | ? |
| `flake_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `elongation_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `surface_texture` | TEXT | _(undocumented)_ | ? | ? | ? |
| `surface_roughness` | REAL | _(undocumented)_ | ? | ? | ? |
| `specific_surface_area` | REAL | _(undocumented)_ | ? | ? | ? |
| `surface_porosity` | REAL | _(undocumented)_ | ? | ? | ? |
| `surface_energy` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_75um` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_150um` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_300um` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_600um` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_1mm` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_2mm` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_5mm` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_10mm` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_20mm` | REAL | _(undocumented)_ | ? | ? | ? |
| `passing_50mm` | REAL | _(undocumented)_ | ? | ? | ? |
| `fines_percent` | REAL | _(undocumented)_ | ? | ? | ? |
| `coarse_percent` | REAL | _(undocumented)_ | ? | ? | ? |
| `oversize_percent` | REAL | _(undocumented)_ | ? | ? | ? |
| `undersize_percent` | REAL | _(undocumented)_ | ? | ? | ? |
| `friability_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `breakage_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `attrition_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `abrasion_index` | REAL | _(undocumented)_ | ? | ? | ? |
| `rolling_friction` | REAL | _(undocumented)_ | ? | ? | ? |
| `sliding_friction` | REAL | _(undocumented)_ | ? | ? | ? |
| `restitution_coefficient` | REAL | _(undocumented)_ | ? | ? | ? |
| `rolling_resistance` | REAL | _(undocumented)_ | ? | ? | ? |
| `particle_density` | REAL | _(undocumented)_ | ? | ? | ? |
| `poissons_ratio` | REAL | _(undocumented)_ | ? | ? | ? |
| `psd_method` | TEXT | _(undocumented)_ | ? | ? | ? |

## `material_handling`  &nbsp;&nbsp;*L2.75*

CEMA 550 handling behaviour & operational tendencies.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `material_id` **PK** | INTEGER | Surrogate primary key | - | ALL | A |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `abr_code` | INTEGER | Abrasion rating 1=negligible .. 7=extreme | 1-7 | Wear, liner, ALL | A |
| `dust_level` | INTEGER | Dustiness severity 0=none .. 5=severe | 0-5 | Dust control spec | B |
| `corrosion_level` | INTEGER | Corrosivity severity | 0-5 | Material of construction | B |
| `stickiness_index` | INTEGER | Stickiness severity | 0-5 | Discharge, carryback | B |
| `bridging_index` | INTEGER | Bridging tendency severity | 0-5 | Hopper, boot | B |
| `caking_index` | INTEGER | Caking severity | 0-5 | Storage | C |
| `segregation_index` | INTEGER | Segregation severity | 0-5 | Blending | C |
| `fluidization_index` | INTEGER | Fluidization severity | 0-5 | Powder handling | C |
| `sticky` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `corrosive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `hygroscopic` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `fibrous` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `friable` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `interlocking` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `free_flowing` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `aerates` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `packs` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `bridges` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `cakes` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `segregates` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `smears` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `degradable` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `oxidizing` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `toxic` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `explosive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `food_grade` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `recyclable` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `impact_sensitive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `particle_breakdown` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `dust_generation` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `static_prone` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `conductive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `grounding_required` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `long_term_caking` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `temperature_sensitive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `freeze_sensitive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `angle_stability` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `arch_tendency` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `rathole_tendency` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `flooding_tendency` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `moisture_absorption` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `wear_mode` | TEXT | Dominant wear mechanism | - | Liner selection | B |
| `handling_notes` | TEXT | _(undocumented)_ | ? | ? | ? |
| `storage_notes` | TEXT | _(undocumented)_ | ? | ? | ? |
| `conveying_notes` | TEXT | _(undocumented)_ | ? | ? | ? |

## `material_hazards`  &nbsp;&nbsp;*L2B*

Safety / regulatory / compliance. Changes equipment SPEC, not calculations.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `material_id` **PK** | INTEGER | Surrogate primary key | - | ALL | A |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `combustible_dust` | INTEGER | Classified as combustible dust | 0/1 | Spec generator, safety | A |
| `dust_class` | TEXT | Dust explosion class St0-St3 | - | Explosion protection | B |
| `kst` | REAL | Deflagration index Kst | bar.m/s | Vent sizing | B |
| `pmax` | REAL | Maximum explosion pressure | bar | Vent sizing | B |
| `mec` | REAL | Minimum explosible concentration | g/m3 | Safety | C |
| `mit_cloud` | REAL | Minimum ignition temperature (cloud) | degC | Safety | C |
| `mit_layer` | REAL | Minimum ignition temperature (layer) | degC | Safety | C |
| `minimum_ignition_energy` | REAL | Minimum ignition energy | mJ | Static control | C |
| `flash_point` | REAL | _(undocumented)_ | ? | ? | ? |
| `autoignition_temperature` | REAL | _(undocumented)_ | ? | ? | ? |
| `fire_class` | TEXT | _(undocumented)_ | ? | ? | ? |
| `flammable` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `oxidizer` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `toxic` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `carcinogenic` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `respiratory_hazard` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `skin_irritant` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `eye_irritant` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `osha_class` | TEXT | _(undocumented)_ | ? | ? | ? |
| `environmental_hazard` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `water_reactive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `air_reactive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `corrosive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `radioactive` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `sds_reference` | TEXT | _(undocumented)_ | ? | ? | ? |
| `nfpa_health` | INTEGER | NFPA 704 health rating | 0-4 | Compliance | B |
| `nfpa_flammability` | INTEGER | NFPA 704 flammability rating | 0-4 | Compliance | B |
| `nfpa_reactivity` | INTEGER | NFPA 704 reactivity rating | 0-4 | Compliance | B |
| `nfpa_special` | TEXT | _(undocumented)_ | ? | ? | ? |
| `atex_zone` | TEXT | ATEX zone classification | - | Electrical spec | B |
| `ghs_classification` | TEXT | _(undocumented)_ | ? | ? | ? |
| `un_number` | TEXT | _(undocumented)_ | ? | ? | ? |
| `hazard_notes` | TEXT | _(undocumented)_ | ? | ? | ? |

## `material_model_coefficients`  &nbsp;&nbsp;*L3*

Model calibration constants. VERSIONED (1-to-many). EMPTY in Phase 1.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `material_id` **PK** | INTEGER | Surrogate primary key | - | ALL | A |
| `model_version` **PK** | TEXT | VECTRIX model version these coefficients tune | - | Physics engine | - |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `calibration_source` | TEXT | _(undocumented)_ | ? | ? | ? |
| `calibration_date` | TEXT | _(undocumented)_ | ? | ? | ? |
| `confidence_level` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `verified` *NOT NULL* | INTEGER | _(undocumented)_ | ? | ? | ? |
| `km` | REAL | Material flow coefficient | - | Physics engine | - |
| `lambda_ref` | REAL | Reference flow decay coefficient | - | Physics engine | - |
| `flow_decay_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `stream_spread_factor` | REAL | Dispersion tendency INPUT coefficient (not the calculated spread) | - | Trajectory model | - |
| `trajectory_drag_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `trajectory_scatter_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `bucket_loading_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `inlet_capture_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `discharge_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `centrifugal_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `rollback_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `material_retention_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `screw_loading_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `power_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `torque_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `axial_flow_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `leakage_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `surcharge_decay_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `surcharge_angle_bias` | REAL | _(undocumented)_ | ? | ? | ? |
| `skirt_loss_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `carryback_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `loading_profile_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `wear_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `impact_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `abrasion_multiplier` | REAL | _(undocumented)_ | ? | ? | ? |
| `degradation_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `fines_generation_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `rolling_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `collision_damping_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `cohesion_decay_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `agglomeration_factor` | REAL | _(undocumented)_ | ? | ? | ? |
| `regression_dataset` | TEXT | _(undocumented)_ | ? | ? | ? |
| `sample_count` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `calibration_notes` | TEXT | _(undocumented)_ | ? | ? | ? |

## `material_sources`  &nbsp;&nbsp;*--*

Provenance & engineering configuration management.

| Field | Type | Meaning | Units | Used by | Tier |
|---|---|---|---|---|---|
| `source_id` **PK** | INTEGER | _(undocumented)_ | ? | ? | ? |
| `material_id` *NOT NULL* | INTEGER | Surrogate primary key | - | ALL | A |
| `mat_id` *NOT NULL* | TEXT | Stable internal material code (canonical join key) | - | ALL | A |
| `property_name` *NOT NULL* | TEXT | Which property this record traces (schema-evolution safe) | - | QA | A |
| `units` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_value` | TEXT | Value the source PUBLISHED (immutable, historical) | varies | QA | A |
| `accepted_value` | TEXT | Value VECTRIX ADOPTED (echoed in the engineering table) | varies | QA | A |
| `source_type` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_name` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_document` | TEXT | _(undocumented)_ | ? | ? | ? |
| `source_edition` | TEXT | _(undocumented)_ | ? | ? | ? |
| `page_number` | TEXT | _(undocumented)_ | ? | ? | ? |
| `table_number` | TEXT | _(undocumented)_ | ? | ? | ? |
| `figure_number` | TEXT | _(undocumented)_ | ? | ? | ? |
| `decision_type` | TEXT | published / measured / calculated / estimated / overridden | - | QA | A |
| `override_reason` | TEXT | _(undocumented)_ | ? | ? | ? |
| `confidence` | INTEGER | _(undocumented)_ | ? | ? | ? |
| `verification_status` | TEXT | _(undocumented)_ | ? | ? | ? |
| `entered_by` | TEXT | _(undocumented)_ | ? | ? | ? |
| `entered_date` | TEXT | _(undocumented)_ | ? | ? | ? |
| `verified_by` | TEXT | _(undocumented)_ | ? | ? | ? |
| `verified_date` | TEXT | _(undocumented)_ | ? | ? | ? |
| `review_due` | TEXT | _(undocumented)_ | ? | ? | ? |
| `is_current` *NOT NULL* | INTEGER | This record produced today's engineering value (one per property) | 0/1 | QA | A |
| `is_active` *NOT NULL* | INTEGER | Source still considered valid | 0/1 | QA | A |
| `comments` | TEXT | _(undocumented)_ | ? | ? | ? |

## Undocumented columns

These exist in the database but have no dictionary entry. Add them to `META` in `generate_field_dictionary.py`:

- `materials_v2.description`
- `materials_v2.source_standard`
- `materials_v2.source_reference`
- `materials_v2.source_revision`
- `materials_v2.created_date`
- `materials_v2.modified_date`
- `materials_v2.revision`
- `material_particles.d10`
- `material_particles.d20`
- `material_particles.d30`
- `material_particles.d40`
- `material_particles.d50`
- `material_particles.d60`
- `material_particles.d70`
- `material_particles.d80`
- `material_particles.d90`
- `material_particles.d95`
- `material_particles.d99`
- `material_particles.minimum_particle_size`
- `material_particles.mean_particle_size`
- `material_particles.median_particle_size`
- `material_particles.maximum_particle_size`
- `material_particles.nominal_top_size`
- `material_particles.uniformity_coefficient`
- `material_particles.curvature_coefficient`
- `material_particles.gradation_index`
- `material_particles.span`
- `material_particles.sorting_coefficient`
- `material_particles.aspect_ratio`
- `material_particles.sphericity`
- `material_particles.roundness`
- `material_particles.angularity`
- `material_particles.elongation`
- `material_particles.flatness`
- `material_particles.flake_index`
- `material_particles.elongation_index`
- `material_particles.surface_texture`
- `material_particles.surface_roughness`
- `material_particles.specific_surface_area`
- `material_particles.surface_porosity`
- `material_particles.surface_energy`
- `material_particles.passing_75um`
- `material_particles.passing_150um`
- `material_particles.passing_300um`
- `material_particles.passing_600um`
- `material_particles.passing_1mm`
- `material_particles.passing_2mm`
- `material_particles.passing_5mm`
- `material_particles.passing_10mm`
- `material_particles.passing_20mm`
- `material_particles.passing_50mm`
- `material_particles.fines_percent`
- `material_particles.coarse_percent`
- `material_particles.oversize_percent`
- `material_particles.undersize_percent`
- `material_particles.friability_index`
- `material_particles.breakage_index`
- `material_particles.attrition_index`
- `material_particles.abrasion_index`
- `material_particles.rolling_friction`
- `material_particles.sliding_friction`
- `material_particles.restitution_coefficient`
- `material_particles.rolling_resistance`
- `material_particles.particle_density`
- `material_particles.poissons_ratio`
- `material_particles.psd_method`
- `material_handling.sticky`
- `material_handling.corrosive`
- `material_handling.hygroscopic`
- `material_handling.fibrous`
- `material_handling.friable`
- `material_handling.interlocking`
- `material_handling.free_flowing`
- `material_handling.aerates`
- `material_handling.packs`
- `material_handling.bridges`
- `material_handling.cakes`
- `material_handling.segregates`
- `material_handling.smears`
- `material_handling.degradable`
- `material_handling.oxidizing`
- `material_handling.toxic`
- `material_handling.explosive`
- `material_handling.food_grade`
- `material_handling.recyclable`
- `material_handling.impact_sensitive`
- `material_handling.particle_breakdown`
- `material_handling.dust_generation`
- `material_handling.static_prone`
- `material_handling.conductive`
- `material_handling.grounding_required`
- `material_handling.long_term_caking`
- `material_handling.temperature_sensitive`
- `material_handling.freeze_sensitive`
- `material_handling.angle_stability`
- `material_handling.arch_tendency`
- `material_handling.rathole_tendency`
- `material_handling.flooding_tendency`
- `material_handling.moisture_absorption`
- `material_handling.handling_notes`
- `material_handling.storage_notes`
- `material_handling.conveying_notes`
- `material_hazards.flash_point`
- `material_hazards.autoignition_temperature`
- `material_hazards.fire_class`
- `material_hazards.flammable`
- `material_hazards.oxidizer`
- `material_hazards.toxic`
- `material_hazards.carcinogenic`
- `material_hazards.respiratory_hazard`
- `material_hazards.skin_irritant`
- `material_hazards.eye_irritant`
- `material_hazards.osha_class`
- `material_hazards.environmental_hazard`
- `material_hazards.water_reactive`
- `material_hazards.air_reactive`
- `material_hazards.corrosive`
- `material_hazards.radioactive`
- `material_hazards.sds_reference`
- `material_hazards.nfpa_special`
- `material_hazards.ghs_classification`
- `material_hazards.un_number`
- `material_hazards.hazard_notes`
- `material_model_coefficients.calibration_source`
- `material_model_coefficients.calibration_date`
- `material_model_coefficients.confidence_level`
- `material_model_coefficients.verified`
- `material_model_coefficients.flow_decay_factor`
- `material_model_coefficients.trajectory_drag_factor`
- `material_model_coefficients.trajectory_scatter_factor`
- `material_model_coefficients.bucket_loading_bias`
- `material_model_coefficients.inlet_capture_factor`
- `material_model_coefficients.discharge_bias`
- `material_model_coefficients.centrifugal_bias`
- `material_model_coefficients.rollback_factor`
- `material_model_coefficients.material_retention_factor`
- `material_model_coefficients.screw_loading_bias`
- `material_model_coefficients.power_bias`
- `material_model_coefficients.torque_bias`
- `material_model_coefficients.axial_flow_factor`
- `material_model_coefficients.leakage_factor`
- `material_model_coefficients.surcharge_decay_factor`
- `material_model_coefficients.surcharge_angle_bias`
- `material_model_coefficients.skirt_loss_factor`
- `material_model_coefficients.carryback_factor`
- `material_model_coefficients.loading_profile_factor`
- `material_model_coefficients.wear_factor`
- `material_model_coefficients.impact_factor`
- `material_model_coefficients.abrasion_multiplier`
- `material_model_coefficients.degradation_factor`
- `material_model_coefficients.fines_generation_factor`
- `material_model_coefficients.rolling_factor`
- `material_model_coefficients.collision_damping_factor`
- `material_model_coefficients.cohesion_decay_factor`
- `material_model_coefficients.agglomeration_factor`
- `material_model_coefficients.regression_dataset`
- `material_model_coefficients.sample_count`
- `material_model_coefficients.calibration_notes`
- `material_sources.source_id`
- `material_sources.units`
- `material_sources.source_type`
- `material_sources.source_name`
- `material_sources.source_document`
- `material_sources.source_edition`
- `material_sources.page_number`
- `material_sources.table_number`
- `material_sources.figure_number`
- `material_sources.override_reason`
- `material_sources.confidence`
- `material_sources.verification_status`
- `material_sources.entered_by`
- `material_sources.entered_date`
- `material_sources.verified_by`
- `material_sources.verified_date`
- `material_sources.review_due`
- `material_sources.comments`
