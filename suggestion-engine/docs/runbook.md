# Runbook

Status of each step is marked: **verified** means covered by automated tests in this repository; **unverified** means it
talks to a service the development sandbox could not reach, so run it once and fix what differs.

## 1. Local setup (Windows PowerShell) - verified
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,data,pipelines]"
pytest
```
`data` adds raster/NetCDF readers, `pipelines` adds Kubeflow Pipelines and Google Cloud clients. For the engine alone,
`pip install -e ".[dev]"` is enough.

## 2. Run P1 on your machine with invented data - verified
```powershell
python scripts/run_p1_local.py --region pune_demo --source synthetic --layer-version dev1
$env:FIELDSHIFT_CELLS_PATH = "data_local/layers/pune_demo/dev1/cells.json"
$env:FIELDSHIFT_LAUNCHER = "local"; $env:FIELDSHIFT_REGION = "pune_demo"
uvicorn fieldshift.api.main:app --reload
```
A request to `/v1/recommend` now answers at once (`status: fast`); the deep tier runs in a background thread, and the next
identical request returns `status: refined`.

## 3. Check access to the real services - unverified (needs internet)
```powershell
$env:EARTHDATA_USERNAME = "..."; $env:EARTHDATA_PASSWORD = "..."
python scripts/check_live_access.py --bucket gs://YOUR_BUCKET
```
It tests NASA POWER, the Earthdata login, whether the SMAP L4 and MODIS product versions named in `data/smap.py` and
`data/modis.py` exist (and lists the versions that do), and a Cloud Storage write/read. Fix product versions in those files
if the check says they are not listed.

## 4. Real data for one district
1. `python scripts/seed_pilot_region.py --id nashik --name "Nashik" --bbox MIN_LON MIN_LAT MAX_LON MAX_LAT`, then confirm season windows with the agronomist.
2. Soil: download SoilGrids sand, silt, clay, phh2o and soc (0-30 cm), reproject to EPSG:4326, and list them in a JSON file
   `{"sand": "...tif", "silt": "...", "clay": "...", "phh2o": "...", "soc": "..."}`; use `--soil-source raster --soil-path that.json`.
   Or prepare a CSV (`cell_id,sand_pct,silt_pct,clay_pct,ph,oc_g_kg`) and use `--soil-source csv`.
3. SMAP and NDVI: export AppEEARS point-sample CSVs for the cell centres (ids = cell ids) and pass `--smap-csv`, `--ndvi-csv`.
4. Future climate: pass `--future-json` with `{"ssp245": {"temp_delta_c": 1.4, "rain_change_pct": 4.0}}` from a projection you trust.
5. `python scripts/run_p1_local.py --region nashik --source power --layer-version 2026a ...` and read `report.json`.

## 5. Google Cloud - unverified
```powershell
gcloud auth login; gcloud config set project PROJECT_ID; gcloud auth application-default login
cd infra; terraform init; terraform validate; terraform plan -var project_id=PROJECT_ID; terraform apply -var project_id=PROJECT_ID
gcloud artifacts repositories create fieldshift --repository-format=docker --location=asia-south1
gcloud auth configure-docker asia-south1-docker.pkg.dev
docker build -f docker/pipeline-base.Dockerfile -t asia-south1-docker.pkg.dev/PROJECT_ID/fieldshift/pipeline:0.1 .
docker push asia-south1-docker.pkg.dev/PROJECT_ID/fieldshift/pipeline:0.1
echo -n "THE_KEY" | gcloud secrets versions add fieldshift-api-key --data-file=-
```
Confirm Vertex AI Pipelines is available in your chosen region and check your quotas first.

## 6. Pipelines on Vertex - unverified
```powershell
$env:FIELDSHIFT_BASE_IMAGE = "asia-south1-docker.pkg.dev/PROJECT_ID/fieldshift/pipeline:0.1"
python -m pipelines.compile                 # build/p1.yaml, build/p2.yaml
gcloud storage cp build/p2.yaml gs://BUCKET/templates/p2.yaml
$env:FIELDSHIFT_GCP_PROJECT = "PROJECT_ID"; $env:FIELDSHIFT_PIPELINE_ROOT = "gs://BUCKET/pipeline-root"
$env:FIELDSHIFT_DATA_ROOT = "gs://BUCKET/data"; $env:FIELDSHIFT_SERVICE_ACCOUNT = "fieldshift-pipelines@PROJECT_ID.iam.gserviceaccount.com"
python scripts/submit_p1.py --region-id nashik --layer-version 2026a --source power --soil-source raster --soil-path gs://BUCKET/soil/rasters.json
```
In the first week measure pipeline start-up time and cost per run with a small region. If start-up is slow, lean on the fast
tier and pre-warm cells instead of launching per request.

## 7. Engine with the Vertex deep tier - unverified
Environment for the engine service: `FIELDSHIFT_LAUNCHER=vertex`, `FIELDSHIFT_REGION`, `FIELDSHIFT_CELLS_PATH=gs://BUCKET/data/layers/REGION/VERSION/cells.json`,
`FIELDSHIFT_GCP_PROJECT`, `FIELDSHIFT_PIPELINE_ROOT`, `FIELDSHIFT_DATA_ROOT`, `FIELDSHIFT_ENGINE_URL` (the service's own URL),
`FIELDSHIFT_P2_TEMPLATE=gs://BUCKET/templates/p2.yaml`, `FIELDSHIFT_API_KEY` from Secret Manager.
P2 reads the layer and weather from the bucket and posts indicators back to `POST /v1/indicators` using the same key.

**Important:** the engine still uses an in-memory store. Run exactly one instance (`--min-instances=1 --max-instances=1` on
Cloud Run); results and jobs are lost on restart. A shared database must replace `MemoryStore` before scaling out.

## Not verified against live services
NASA POWER, Earthdata/AppEEARS (login, task, bundle download, product versions), NEX-GDDP-CMIP6 bucket file names, Vertex
submission, Secret Manager and Cloud Storage access, Terraform apply, Docker builds, Cloud Run deployment. Each has an
offline test of our own logic (fake transports, small synthetic files); none replaces a first real run.
