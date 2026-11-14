#!/bin/bash
set -e

cat > /tmp/engine-env.yaml << 'EOC'
FIELDSHIFT_LAUNCHER: "local"
FIELDSHIFT_REGION: "pune_demo"
FIELDSHIFT_CELL_SIZE_DEG: "0.1"
FIELDSHIFT_CELLS_PATH: "gs://fieldshift-514614-fieldshift-data/data/layers/pune_demo/2026a/cells.json"
FIELDSHIFT_SEASON_CYCLE: "kharif,rabi"
FIELDSHIFT_KNOWLEDGE_DIR: "knowledge"
FIELDSHIFT_ENGINE_URL: "https://fieldshift-suggestion-engine-32936898580.asia-south1.run.app"
EOC

gcloud run deploy fieldshift-suggestion-engine \
  --image asia-south1-docker.pkg.dev/fieldshift-514614/fieldshift/pipeline:0.2 \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 1 \
  --memory 2Gi \
  --cpu 2 \
  --port 8080 \
  --service-account fieldshift-pipelines@fieldshift-514614.iam.gserviceaccount.com \
  --env-vars-file /tmp/engine-env.yaml \
  --set-secrets "FIELDSHIFT_API_KEY=fieldshift-api-key:latest" \
  --command "uvicorn" \
  --args "fieldshift.api.main:app,--host,0.0.0.0,--port,8080"
