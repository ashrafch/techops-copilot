param(
  [string]$BaseUrl = "http://localhost:8001",
  [string]$AdminEmail = "admin@example.com",
  [string]$AdminPassword = "ChangeMe123!",
  [string]$ApiKey = ""
)

$ErrorActionPreference = "Stop"

function Wait-ForHealth {
  param(
    [string]$Url,
    [int]$Retries = 30,
    [int]$DelaySeconds = 2
  )
  for ($i = 1; $i -le $Retries; $i++) {
    try {
      $resp = Invoke-RestMethod -Method Get -Uri "$Url/health"
      if ($resp.status -eq "ok") { return }
    } catch {}
    Start-Sleep -Seconds $DelaySeconds
  }
  throw "Health check failed after $Retries attempts."
}

function Assert-True {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw $Message }
}

function Build-Headers {
  $h = @{ "X-User-Role" = "admin" }
  if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $h["X-API-Key"] = $ApiKey
  }
  return $h
}

Write-Output "Starting containers..."
docker compose up -d postgres_app minio api | Out-Null
Write-Output "Applying database migrations..."
powershell -ExecutionPolicy Bypass -File scripts/apply_db_migrations.ps1 | Out-Null

Write-Output "Waiting for API health..."
Wait-ForHealth -Url $BaseUrl

$headers = Build-Headers

Write-Output "Admin login..."
try {
  $loginBody = @{ email = $AdminEmail; password = $AdminPassword } | ConvertTo-Json
  $loginResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" -Headers $headers -ContentType "application/json" -Body $loginBody
  if ($loginResp.access_token) {
    $headers["Authorization"] = "Bearer $($loginResp.access_token)"
  }
} catch {
  Write-Output "AUTH_OPTIONAL_FALLBACK"
}

$tenantId = "demo"

Write-Output "Update tenant route..."
$routeBody = @{ to_emails = @("ops.primary@example.com", "ops.backup@example.com") } | ConvertTo-Json
$routeResp = Invoke-RestMethod -Method Patch -Uri "$BaseUrl/tenant-routes/$tenantId" -Headers $headers -ContentType "application/json" -Body $routeBody
Assert-True -Condition ($routeResp.to_emails.Count -ge 2) -Message "Route update failed."

Write-Output "Update tenant SLA policy..."
$slaBody = @{
  p1_minutes = 30
  p2_minutes = 120
  p3_minutes = 360
  p4_minutes = 720
} | ConvertTo-Json
$slaResp = Invoke-RestMethod -Method Patch -Uri "$BaseUrl/tenant-sla-policies/$tenantId" -Headers $headers -ContentType "application/json" -Body $slaBody
Assert-True -Condition ($slaResp.p1_minutes -eq 30) -Message "SLA update failed."

Write-Output "Update tenant automation policy..."
$automationBody = @{
  correlation_window_minutes = 240
  at_risk_lead_minutes = 60
  auto_assign_name = "Automation Dispatcher"
  auto_assign_email = "dispatch@example.com"
} | ConvertTo-Json
$automationResp = Invoke-RestMethod -Method Patch -Uri "$BaseUrl/tenant-automation-policies/$tenantId" -Headers $headers -ContentType "application/json" -Body $automationBody
Assert-True -Condition ($automationResp.correlation_window_minutes -eq 240) -Message "Automation policy update failed."

$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$newUserEmail = "ops.$suffix@example.com"

Write-Output "Create admin-managed user..."
$createUserBody = @{
  email = $newUserEmail
  full_name = "Ops User $suffix"
  password = "ChangeMe123!"
  role = "operator"
  tenant_id = $tenantId
  is_active = $true
} | ConvertTo-Json
$createdUser = Invoke-RestMethod -Method Post -Uri "$BaseUrl/admin/users" -Headers $headers -ContentType "application/json" -Body $createUserBody
Assert-True -Condition ($createdUser.email -eq $newUserEmail) -Message "User creation failed."

Write-Output "Disable created user..."
$disableBody = @{ is_active = $false } | ConvertTo-Json
$disabledUser = Invoke-RestMethod -Method Patch -Uri "$BaseUrl/admin/users/$($createdUser.id)" -Headers $headers -ContentType "application/json" -Body $disableBody
Assert-True -Condition ($disabledUser.is_active -eq $false) -Message "User disable failed."

Write-Output "Read audit log..."
$audit = Invoke-RestMethod -Method Get -Uri "$BaseUrl/admin/audit-logs?tenant_id=$tenantId&limit=50" -Headers $headers
Assert-True -Condition ($audit.Count -ge 1) -Message "Audit log is empty."

Write-Output "Read ticket metrics..."
$metrics = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/metrics?tenant_id=$tenantId" -Headers $headers
Assert-True -Condition ($null -ne $metrics.open_total) -Message "Metrics endpoint failed."

Write-Output "SMOKE_ENTERPRISE_ADMIN_OK tenant_id=$tenantId user_email=$newUserEmail"
