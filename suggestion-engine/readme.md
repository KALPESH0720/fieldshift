# Field Shift - suggestion engine

Everything the engine needs, in one repository: the live path (API, rules, scoring, explanations; Developer A) and the
batch side (NASA data, features, simulation, Vertex pipelines, monitoring; Developer B).

> **Status: development skeleton, not for farmers.** The crop table, rules and simulation parameters in `knowledge/` are
> illustrative placeholders (no agronomist review), `tests/fixtures/pilot_cells.json` and `--source synthetic` data are
> invented, and the live-service adapters (NASA POWER, Earthdata/AppEEARS, NEX-GDDP, Vertex, Cloud Storage, Secret Manager)
> were built from their documentation and tested only with fake transports. Responses carry `KNOWLEDGE_NOT_REVIEWED` and
> `SYNTHETIC_CELL_DATA` in `notes`. See `docs/runbook.md` for what to verify first.

## Quick start (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,data,pipelines]"     # engine only: ".[dev]"
pytest                                      # 158 tests
uvicorn fieldshift.api.main:app --reload    # http://127.0.0.1:8000/docs
```
macOS/Linux: `source .venv/bin/activate`, the rest is identical (or `make install test run`).

Try the whole loop offline (invented data): see runbook section 2. A first request answers at once; the deep tier then
simulates the shortlisted crop sequences and the same request returns `status: refined`.

## Who owns what
| Area | Folders | Developer |
|---|---|---|
| API, rules, scoring, ranking, explanations, confidence | `src/fieldshift/api`, `engine`, `grid`, `contracts/`, `knowledge/crops|rules` | A |
| NASA/soil data clients, features, simulation, monitoring, pipelines, containers, infra | `data`, `features`, `simulation`, `monitor`, `learning`, `pipelines/`, `docker/`, `infra/`, `knowledge/simulation|regions` | B |
| Shared | `store`, `common`, `docs`, `.github` | both |

## Flow
```
LIVE   POST /v1/recommend -> snap to cell -> filter -> rules -> score -> rank -> explain -> answer (status fast)
                                  cache miss -> one Job per cache key -> launcher(job)
BATCH  P1  weather + soil + SMAP + NDVI + future deltas -> validated layers/{region}/{ver}/cells.json  -> engine store
       P2  job -> water-balance simulation (history + climate change) -> Indicator -> POST /v1/indicators -> status refined
       P3  observations -> sowing-window and drift alerts   (library only; pipeline is a Phase 3-4 item)
```

## Interfaces between the two sides (`src/fieldshift/store/models.py`)
`CellFeatures` (P1 -> engine), `Indicator` (P2 -> engine), `Job` (engine -> P2), `Alert` (P3 -> engine), `ActionLog`
(backend -> engine). Field meanings and units: `docs/data-dictionary.md`.

## Commands
| Task | Command |
|---|---|
| Run P1 locally | `python scripts/run_p1_local.py --region pune_demo --source synthetic --layer-version dev1` |
| Check live access | `python scripts/check_live_access.py --bucket gs://BUCKET` |
| New district | `python scripts/seed_pilot_region.py --id ID --name NAME --bbox MIN_LON MIN_LAT MAX_LON MAX_LAT` |
| Validate knowledge | `python scripts/validate_rules.py` |
| Compile pipelines | `python -m pipelines.compile` |
| Submit P1 to Vertex | `python scripts/submit_p1.py ...` |
| Regenerate API schemas and OpenAPI | `python -m fieldshift.api.schema_export` |

## Rules of the repo
- Knowledge changes need agronomist review and a `knowledge/CHANGELOG.md` entry (`docs/rules-authoring.md`).
- Changing `contracts/` changes the API: regenerate the schemas, commit them, tell the backend team. `tests/contract` fails on drift.
- Do not add `from __future__ import annotations` to files in `pipelines/`: KFP reads real annotations.

## Known limits
- **Storage:** `MemoryStore` loses data on restart and is not shared between instances. Run one engine instance until a database replaces it.
- **Simulation:** a transparent FAO-56-style water balance (water is the only yield limiter, heat/nutrients/pests are ignored, soil
  properties are estimated from texture, crop parameters are uncalibrated). WOFOST and AquaCrop adapters are not included;
  `simulate_sequence` is the interface they would implement. Soil benefit stays rule-based.
- **Sequences:** a long crop (e.g. pigeonpea) delays the next sowing instead of ruling the sequence out.
- **Data gaps:** a crop with no price or cost gets a neutral return score and lowers confidence; P3 has no real observation
  source yet; there is no P3/P4/P5 Vertex pipeline; the multi-field optimizer is not built.
- **Resolution:** results are regional estimates for a grid cell, not field-specific.
