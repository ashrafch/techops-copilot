param(
  [string]$PytestArgs = "app/tests -q"
)

$ErrorActionPreference = "Stop"

Write-Output "Starting dependencies..."
docker compose up -d postgres_app minio | Out-Null

Write-Output "Building API image..."
docker compose build api | Out-Null

Write-Output "Running API tests..."
docker compose run --rm -w /app -e PYTHONPATH=/app api sh -lc "pytest $PytestArgs"
