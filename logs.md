FieldShift — Vertex AI & Cloud Run Deployment Log

Date: 2026-11-13
GCP Project: fieldshift-514614
Region: asia-south1

Summary of All Changes
1. Google Cloud Infrastructure (Cloud Shell)
Resource	Name / Value	Status
GCP Project	fieldshift-514614	✅ Used
Cloud Storage Bucket	gs://fieldshift-514614-fieldshift-data	✅ Created
Service Account	fieldshift-pipelines@fieldshift-514614.iam.gserviceaccount.com	✅ Created
IAM Role: Vertex AI User	Assigned to SA	✅ Done
IAM Role: Secret Manager Accessor	Assigned to SA	✅ Done
IAM Role: Storage Object Admin	Assigned to SA on bucket	✅ Done
Artifact Registry Repo	asia-south1/fieldshift	✅ Created
Container Image	asia-south1-docker.pkg.dev/fieldshift-514614/fieldshift/pipeline:0.1	✅ Built & Pushed
Secret Manager Secret	fieldshift-api-key	✅ Created
Cloud Run Service	fieldshift-suggestion-engine	✅ Deployed
Cloud Run URL	https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app	✅ Live
Vertex AI P1 Pipeline Job	fieldshift-p1-pune_demo-2026a	✅ Submitted (running)
P1 YAML Template in GCS	gs://fieldshift-514614-fieldshift-data/templates/p1.yaml	✅ Uploaded
P2 YAML Template in GCS	gs://fieldshift-514614-fieldshift-data/templates/p2.yaml	✅ Uploaded
2. GCP APIs Enabled
aiplatform.googleapis.com
storage.googleapis.com
artifactregistry.googleapis.com
run.googleapis.com
secretmanager.googleapis.com
cloudscheduler.googleapis.com
cloudbuild.googleapis.com
3. Cloud Run Service Configuration

Service: fieldshift-suggestion-engine
URL: https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app
Image: asia-south1-docker.pkg.dev/fieldshift-514614/fieldshift/pipeline:0.1
Command: uvicorn fieldshift.api.main:app --host 0.0.0.0 --port 8080

Environment Variables:

FIELDSHIFT_LAUNCHER=local
FIELDSHIFT_REGION=pune_demo
FIELDSHIFT_GCP_PROJECT=fieldshift-514614
FIELDSHIFT_GCP_REGION=asia-south1
FIELDSHIFT_PIPELINE_ROOT=gs://fieldshift-514614-fieldshift-data/pipeline-root
FIELDSHIFT_DATA_ROOT=gs://fieldshift-514614-fieldshift-data/data
FIELDSHIFT_SERVICE_ACCOUNT=fieldshift-pipelines@fieldshift-514614.iam.gserviceaccount.com
FIELDSHIFT_P2_TEMPLATE=gs://fieldshift-514614-fieldshift-data/templates/p2.yaml
FIELDSHIFT_SEASON_CYCLE=kharif,rabi
FIELDSHIFT_KNOWLEDGE_DIR=knowledge
FIELDSHIFT_CELLS_PATH=tests/fixtures/pilot_cells.json  ← update after P1 finishes
FIELDSHIFT_ENGINE_URL=https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app
FIELDSHIFT_API_KEY=<from Secret Manager: fieldshift-api-key>

Note: FIELDSHIFT_CELLS_PATH is currently using synthetic test fixtures. After P1 pipeline completes, update to: gs://fieldshift-514614-fieldshift-data/data/layers/pune_demo/2026a/cells.json

4. Vertex AI Pipeline

P1 Pipeline Job:

Display Name: fieldshift-p1-pune_demo-2026a
Resource: projects/32936898580/locations/asia-south1/pipelineJobs/fieldshift-p1-grid-layers-20261113171211
Pipeline View: https://console.cloud.google.com/vertex-ai/locations/asia-south1/pipelines/runs/fieldshift-p1-grid-layers-20261113171211?project=32936898580
Source: NASA POWER API (power.larc.nasa.gov)
Soil Source: synthetic
Output: gs://fieldshift-514614-fieldshift-data/data/layers/pune_demo/2026a/cells.json

P2 Pipeline Template (staged, not yet triggered):

gs://fieldshift-514614-fieldshift-data/templates/p2.yaml
Triggered automatically by Cloud Run engine when a recommendation job needs deep simulation
5. Local File Changes
backend/.env
diff
- SUGGESTION_ENGINE_URL=http://suggestion-engine:8000
+ SUGGESTION_ENGINE_URL=https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app
suggestion-engine/.env (newly created)
FIELDSHIFT_API_KEY=fieldshift-dev-suggestion-engine-api-key-32chars
FIELDSHIFT_PORT=8080
FIELDSHIFT_KNOWLEDGE_DIR=knowledge
FIELDSHIFT_REGION=pune_demo
FIELDSHIFT_CELL_SIZE_DEG=0.1
FIELDSHIFT_SEASON_CYCLE=kharif,rabi
FIELDSHIFT_HORIZON_SEASONS=2
FIELDSHIFT_TOP_N=3
FIELDSHIFT_SCENARIO=ssp245
FIELDSHIFT_CELLS_PATH=tests/fixtures/pilot_cells.json
FIELDSHIFT_LAUNCHER=vertex
FIELDSHIFT_GCP_PROJECT=fieldshift-514614
FIELDSHIFT_GCP_REGION=asia-south1
FIELDSHIFT_PIPELINE_ROOT=gs://fieldshift-514614-fieldshift-data/pipeline-root
FIELDSHIFT_DATA_ROOT=gs://fieldshift-514614-fieldshift-data/data
FIELDSHIFT_SERVICE_ACCOUNT=fieldshift-pipelines@fieldshift-514614.iam.gserviceaccount.com
FIELDSHIFT_P2_TEMPLATE=gs://fieldshift-514614-fieldshift-data/templates/p2.yaml
FIELDSHIFT_ENGINE_URL=https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app
FIELDSHIFT_BASE_IMAGE=asia-south1-docker.pkg.dev/fieldshift-514614/fieldshift/pipeline:0.1
6. Pending Actions
Action	Command	Priority
Wait for P1 pipeline to finish	Check Vertex AI console	🔴 High
Update FIELDSHIFT_CELLS_PATH on Cloud Run	See command below	🔴 High
Update FIELDSHIFT_ENGINE_URL on Cloud Run	Already noted in deploy	🟡 Medium
Switch FIELDSHIFT_LAUNCHER to vertex on Cloud Run	See command below	🟡 Medium
Commit & push all local changes to GitHub	git add . && git commit && git push	🟡 Medium

After P1 pipeline completes, run this in Cloud Shell:

bash
gcloud run services update fieldshift-suggestion-engine \
  --region asia-south1 \
  --update-env-vars "FIELDSHIFT_CELLS_PATH=gs://fieldshift-514614-fieldshift-data/data/layers/pune_demo/2026a/cells.json,FIELDSHIFT_LAUNCHER=vertex,FIELDSHIFT_ENGINE_URL=https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app"
7. Architecture (Production State)
Frontend (React/Vite PWA)
    │  VITE_API_URL → https://your-backend-domain/api/v1
    ▼
Backend (FastAPI + Docker Compose locally / Cloud Run future)
    │  SUGGESTION_ENGINE_URL → https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app
    │  X-API-Key: fieldshift-dev-suggestion-engine-api-key-32chars
    ▼
Suggestion Engine (Cloud Run — LIVE)
    │  Fast tier: rule engine + cells.json (synthetic now, NASA real after P1)
    │  Deep tier: triggers P2 Vertex AI pipeline
    ▼
Vertex AI Pipelines
    ├── P1 (Weekly): NASA POWER → cells.json → GCS ✅ Running
    └── P2 (Per-request): Monte Carlo simulation → indicators → engine callback
8. Health Check
bash
# Verify suggestion engine is live:
curl https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app/v1/health
# Expected: {"status":"ok","model":"...","rules":"..."}

Log generated: 2026-11-13 22:47 IST