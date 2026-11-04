
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$ComposeFile = "infra/deployment/docker-compose.yml"
$EnvFile = "infra/.env"

Write-Host "===================================="
Write-Host "       FieldShift Deployment"
Write-Host "===================================="

# Docker availability
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not available in PATH."
}

docker info | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running."
}

# Environment file
if (-not (Test-Path $EnvFile)) {
    throw "infra/.env missing. Copy infra/.env.example to infra/.env."
}

# Validate configuration
Write-Host "`nValidating infrastructure configuration..."

py infra/scripts/validate_config.py

if ($LASTEXITCODE -ne 0) {
    throw "Configuration validation failed."
}

# Build
Write-Host "`nBuilding FieldShift image..."

docker compose --env-file $EnvFile -f $ComposeFile build

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed."
}

# Run pipeline container
Write-Host "`nExecuting FieldShift pipeline..."

docker compose --env-file $EnvFile -f $ComposeFile run --rm fieldshift

if ($LASTEXITCODE -ne 0) {
    throw "FieldShift pipeline execution failed."
}

Write-Host "`nFieldShift pipeline execution completed."
