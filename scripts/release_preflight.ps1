param(
  [ValidateSet("dev", "stage", "prod")]
  [string]$Environment = "stage"
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Command '$Name' not found in PATH."
  }
}

Write-Host "Release preflight for environment: $Environment"

Require-Command docker
Require-Command npm

if (-not (Test-Path ".env")) {
  throw ".env not found. Create it from env/.env.$Environment.example before release."
}

$requiredVars = @(
  "DATABASE_URL",
  "API_PORT",
  "ENFORCE_AUTH",
  "ENFORCE_RBAC",
  "AUTH_SECRET_KEY"
)

$envMap = @{}
Get-Content ".env" | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $parts = $_ -split '=', 2
  if ($parts.Count -eq 2) {
    $envMap[$parts[0].Trim()] = $parts[1].Trim()
  }
}

foreach ($key in $requiredVars) {
  if (-not $envMap.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envMap[$key])) {
    throw "Missing required variable in .env: $key"
  }
}

Write-Host "Building frontend..."
Push-Location "services/web"
npm run build | Out-Host
Pop-Location

Write-Host "Running smoke e2e..."
powershell -ExecutionPolicy Bypass -File "scripts/smoke_e2e.ps1" | Out-Host

Write-Host "Running smoke enterprise admin..."
powershell -ExecutionPolicy Bypass -File "scripts/smoke_enterprise_admin.ps1" | Out-Host

Write-Host "RELEASE_PREFLIGHT_OK env=$Environment"
