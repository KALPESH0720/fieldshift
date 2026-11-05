# Data dictionary

The tables below describe what pipelines write and the engine reads. Code: `src/fieldshift/store/models.py`.

## Storage layout (local folder or `gs://bucket`)
| Path | Written by | Contents |
|---|---|---|
| `raw/power/{region}/{cell_id}.json` | P1 | Daily weather for one cell (columnar JSON, see `data/weather.py`) |
| `layers/{region}/{layer_version}/cells.json` | P1 | `{"cells": [CellFeatures, ...]}`, the file the engine loads |
| `layers/{region}/{layer_version}/report.json` | P1 | Counts, warnings, failed cells, validation errors |
| `runs/{pipeline}/{run_id}/` | pipelines | Run inputs, outputs, logs (reserved) |
| `models/{param_version}/` | calibration | Calibrated parameters (reserved) |

## CellFeatures (one per grid cell, from P1)
| Field | Unit | How it is computed |
|---|---|---|
| `cell_id` | | `g{size}_{iy}_{ix}`; the regular grid in `grid/snap.py` |
| `layer_version` | | Chosen when P1 runs; shown to users |
| `synthetic` | | True when weather or soil are invented development data |
| `soil_class` | USDA class | From sand/silt/clay (`data/soilgrids.py: texture_class`) |
| `soil_ph` | pH | 0-30 cm mean (SoilGrids value / 10) |
| `soil_organic_carbon` | g/kg | 0-30 cm mean (SoilGrids dg/kg / 10) |
| `sand_pct`, `clay_pct` | % | 0-30 cm mean; used for soil water properties |
| `seasons.{name}.rain_mm_median` | mm | Median over years of season rainfall (POWER) |
| `seasons.{name}.rain_mm_dry_year` | mm | 20th percentile of season rainfall |
| `seasons.{name}.stored_water_mm_at_sowing` | mm | Plant-available water in the top 1 m around the season start, median over years. From SMAP L4 root-zone moisture, or a modelled stand-in for synthetic runs |
| `seasons.{name}.tmean_c` | deg C | Mean over years of the season mean temperature |
| `seasons.{name}.heat_stress_days` | days | Median number of days with Tmax at or above 35 deg C |
| `seasons.{name}.longest_dry_spell_days` | days | 80th percentile (a bad year) of the longest run of days under 2.5 mm |
| `drought_frequency` | 0-1 | Share of years whose total rain over all seasons is below 75% of the median. Rain-based proxy |
| `ndvi_cv` | ratio | Variation of season-mean NDVI across years (MODIS), if supplied |
| `future.{scenario}.temp_delta_c`, `rain_change_pct` | deg C, % | Change against the baseline (NEX-GDDP-CMIP6 or a supplied table) |

A season needs at least 8 years with 90% valid days; otherwise its features are left empty and the report warns.
The engine treats missing values as unknown (neutral score, lower confidence), never as zero.

## Indicator (one per crop sequence, from P2)
| Field | Meaning |
|---|---|
| `sequence` | Crop ids joined with `>`, e.g. `soybean>chickpea` |
| `water_score_median` | Median over historical years of the mean relative yield (water only) across the crops |
| `water_score_pessimistic` | 20th percentile of the historical and climate-change years pooled |
| `yield_factor_pessimistic` | pessimistic / median, i.e. what a bad year costs relative to a typical one |

## Job, Alert, ActionLog
- **Job**: created by the engine on a cache miss; carries cell, start season, irrigation, soil class, scenario and the
  sequences to simulate. Status `queued`, `running`, `done`, `failed`.
- **Alert** (P3): `cell_id`, optional `crop`, `type` (`sowing_window`, `drift`), `severity` (`info`, `watch`, `act`),
  `code` and `params` for the frontend to translate.
- **ActionLog**: what the farmer did. Pseudonymous plot id and grid cell only; no names, phone numbers or exact locations.

## Units
Rain in mm, temperature in deg C, moisture in m3/m3, area in acres, prices in INR per quintal.
`common/units.py` converts hectares, guntha, INR/kg and INR/tonne.
