param(
  [string]$ContainerName = "techops-postgres-app",
  [string]$DbUser = "techops",
  [string]$DbName = "techops",
  [Parameter(Mandatory=$true)][string]$InputPath
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $InputPath)) {
  throw "Backup file not found: $InputPath"
}

Get-Content -Raw $InputPath | docker exec -i $ContainerName psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName | Out-Null
Write-Output "DB_RESTORE_OK path=$InputPath"
