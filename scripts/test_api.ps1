param(
  [string]$PytestArgs = "app/tests -q",
  [string]$ApiKey = "",
  [string]$RequireApiKey = "false",
  [string]$RateLimitRpm = "0"
)

$ErrorActionPreference = "Stop"

Write-Output "Starting dependencies..."
docker compose up -d postgres_app minio | Out-Null

Write-Output "Building API image..."
docker compose build api | Out-Null

Write-Output "Running API tests..."
docker compose run --rm -w /app -e PYTHONPATH=/app -e API_KEY=$ApiKey -e REQUIRE_API_KEY=$RequireApiKey -e RATE_LIMIT_RPM=$RateLimitRpm api sh -lc "pytest $PytestArgs"
