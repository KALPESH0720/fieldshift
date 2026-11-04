
# FieldShift Infrastructure

Infrastructure configuration and execution support for the FieldShift
agricultural adaptation pipeline.

## Components

- config/: Application and logging configuration
- deployment/: Docker image and Compose configuration
- monitoring/: Prometheus configuration
- scripts/: Validation, health-check, and deployment utilities
- .env.example: Environment variable template
- .dockerignore: Docker build exclusions

## Requirements

- Python 3.14
- Docker Desktop
- Docker Compose
- Root requirements.txt
- PyYAML

## Environment Setup

Copy infra/.env.example to infra/.env.

Configure required environment variables.

Do not commit API secrets.

## Validate Infrastructure

py infra/scripts/validate_config.py

## Build Image

docker compose -f infra/deployment/docker-compose.yml build

## Execute Pipeline

docker compose -f infra/deployment/docker-compose.yml run --rm fieldshift

## Deploy and Execute

powershell -ExecutionPolicy Bypass -File infra/scripts/deploy.ps1

## Verify Pipeline Output

py infra/scripts/health_check.py

## View Containers

docker compose -f infra/deployment/docker-compose.yml ps

## View Logs

docker compose -f infra/deployment/docker-compose.yml logs

## Stop Services

docker compose -f infra/deployment/docker-compose.yml down

## Pipeline Integration

The execution runner imports run_fieldshift_pipeline from pipelines.compile.

The simulator and monitor functions must be configured using valid
Python module:function paths.

Execution configuration must supply the required pipeline inputs.

## Monitoring

Prometheus configuration is included.

FieldShift-specific metrics require a metrics exporter.
