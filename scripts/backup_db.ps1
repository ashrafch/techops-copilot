param(
  [string]$ContainerName = "techops-postgres-app",
  [string]$DbUser = "techops",
  [string]$DbName = "techops",
  [string]$OutputPath = "backups/techops_$(Get-Date -Format yyyyMMdd_HHmmss).sql"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath) | Out-Null

docker exec $ContainerName pg_dump -U $DbUser -d $DbName > $OutputPath
Write-Output "DB_BACKUP_OK path=$OutputPath"
