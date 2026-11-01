# Field Shift - suggestion engine

Live path of the suggestion engine (Developer A): rule engine, scoring, ranking, explanations and
the HTTP API the backend team calls. Vertex pipelines, NASA data access and crop simulation are
Developer B's part and plug in through `src/fieldshift/store/`.

> **Status: development skeleton.** Crop table and rules in `knowledge/` are illustrative placeholders,
> and `tests/fixtures/pilot_cells.json` holds SYNTHETIC climate values, not NASA data. Responses say so in
> `notes` (`KNOWLEDGE_NOT_REVIEWED`, `SYNTHETIC_CELL_DATA`). Do not show them to farmers.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest                                   # 48 tests
uvicorn fieldshift.api.main:app --reload # http://127.0.0.1:8000/docs
```

macOS/Linux: `source .venv/bin/activate`, the rest is identical (or use `make install test run`).

Mock server for the backend team (canned answer, no engine needed):
`cd contracts/mock_server; uvicorn app:app --port 8001`

## How a request flows

```
POST /v1/recommend
  snap location to grid cell -> read cell features from the store
  -> filter crops per season (EcoCrop-style limits, water supply, pH)        engine/filter.py
  -> enumerate crop sequences, apply hard rules (exclude)                     engine/rules.py
  -> soft rules + scores: soil, pest, net return, water/climate risk          engine/scoring.py
  -> weighted rank, dry-year score, top-3 stability                           engine/ranking.py
  -> reason codes + trade-off code                                            engine/explain.py
  -> confidence level, human-review flag                                      engine/confidence.py
  -> cache miss: fast answer + one job per cache key (never blocks on Vertex) engine/recommend.py
```

Endpoints: `POST /v1/recommend`, `POST /v1/rescore`, `GET /v1/jobs/{id}`, `GET /v1/alerts`,
`POST /v1/actions`, `DELETE /v1/actions/{plot_id}`, `POST /v1/optimize` (501 until Phase 3), `GET /v1/health`.

## Interface with Developer B (data / pipelines)

All in `src/fieldshift/store/models.py`:

| Model | Written by | Read by |
|---|---|---|
| `CellFeatures` (per-season climate, soil, future deltas) | pipeline P1 | engine filter and scoring |
| `Indicator` (simulated water score, dry-year yield factor) | pipeline P2 | engine scoring (status becomes `refined`) |
| `Alert` | pipeline P3 | `GET /v1/alerts` |
| `Job` | engine creates; P2 updates | `GET /v1/jobs/{id}` |

`SeasonClimate.stored_water_mm_at_sowing` (SMAP root-zone water) is added to season rainfall as the
"effective water supply". Without it, residual-moisture rabi crops would be wrongly excluded.
To plug in a database, implement the `Store` protocol in `store/base.py` (see `memory_store.py`).

## Rules of the repo
- Knowledge (`knowledge/`) changes need agronomist review; update `knowledge/CHANGELOG.md`.
- Anything under `contracts/` changes the API: run `python -m fieldshift.api.schema_export`, commit the
  schemas, and tell the backend team. `tests/contract` fails if the schemas drift from the models.
- Scenario cases in `tests/scenarios/cases/` are placeholders until the agronomist supplies real ones.

## Known limits of this version
- A crop with no price or cost gets a neutral return score (0.5) and lowers confidence; the backend
  should send prices and costs for every pilot crop.
- Dry-year yield uses a heuristic until simulation indicators (P2) exist.
- Soil benefit is rule-based (WOFOST has no soil-carbon model).
- No persistence: `MemoryStore` loses data on restart.
