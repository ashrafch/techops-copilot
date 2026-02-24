param(
  [string]$DbUser = "techops",
  [string]$DbName = "techops",
  [string]$ContainerName = "techops-postgres-app"
)

$ErrorActionPreference = "Stop"

$migrationDir = "infra/postgres/migrations"
$files = Get-ChildItem -Path $migrationDir -Filter "*.sql" | Sort-Object Name

if ($files.Count -eq 0) {
  Write-Output "No migration files found."
  exit 0
}

foreach ($file in $files) {
  Write-Output "Applying migration $($file.Name)..."
  $sql = Get-Content -Raw -Path $file.FullName
  $sql | docker exec -i $ContainerName psql -v ON_ERROR_STOP=1 -U $DbUser -d $DbName | Out-Null
}

Write-Output "DB_MIGRATIONS_OK"
