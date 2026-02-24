param(
  [string]$BaseUrl = "http://localhost:8001",
  [string]$UserRole = "operator",
  [string]$AuthEmail = "operator@example.com",
  [string]$AuthPassword = "ChangeMe123!"
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
      if ($resp.status -eq "ok") {
        Write-Output "HEALTH_OK"
        return
      }
    } catch {
      Start-Sleep -Seconds $DelaySeconds
    }
  }

  throw "Health check failed after $Retries attempts."
}

function Assert-Equal {
  param(
    $Actual,
    $Expected,
    [string]$Message
  )

  if ($Actual -ne $Expected) {
    throw "$Message. Expected '$Expected' but got '$Actual'."
  }
}

Write-Output "Starting containers..."
docker compose up -d postgres_app minio api | Out-Null
Write-Output "Applying database migrations..."
powershell -ExecutionPolicy Bypass -File scripts/apply_db_migrations.ps1 | Out-Null

Write-Output "Waiting for API health..."
Wait-ForHealth -Url $BaseUrl

Write-Output "Checking readiness..."
$ready = Invoke-RestMethod -Method Get -Uri "$BaseUrl/ready"
Assert-Equal -Actual $ready.status -Expected "ready" -Message "Readiness status mismatch"

$headers = @{ "X-User-Role" = $UserRole }

function Try-LoginAuth {
  param([string]$Url, [hashtable]$TargetHeaders)
  try {
    $loginBody = @{ email = $AuthEmail; password = $AuthPassword } | ConvertTo-Json
    $loginResp = Invoke-RestMethod -Method Post -Uri "$Url/auth/login" -ContentType "application/json" -Body $loginBody
    if ($loginResp.access_token) {
      $TargetHeaders["Authorization"] = "Bearer $($loginResp.access_token)"
      Write-Output "AUTH_LOGIN_OK"
      return $true
    }
  } catch {
    return $false
  }
  return $false
}

$payload = @{
  tenant_id = "demo"
  source = "smoke-script"
  requester = @{
    name = "Smoke Tester"
    email = "smoke@example.com"
  }
  subject = "Smoke validation ticket"
  description_raw = "Automated e2e check"
  machine = @{
    line = "L-01"
    station = "ST-01"
    serial = "SN-SMOKE-001"
  }
  priority = "P3"
} | ConvertTo-Json -Depth 10

Write-Output "Creating ticket..."
try {
  $intake = Invoke-RestMethod -Method Post -Uri "$BaseUrl/intake" -ContentType "application/json" -Body $payload -Headers $headers
} catch {
  if ($_.Exception.Message -match "401" -or $_.Exception.Message -match "Unauthorized") {
    $ok = Try-LoginAuth -Url $BaseUrl -TargetHeaders $headers
    if (-not $ok) { throw }
    $intake = Invoke-RestMethod -Method Post -Uri "$BaseUrl/intake" -ContentType "application/json" -Body $payload -Headers $headers
  } else {
    throw
  }
}
Assert-Equal -Actual $intake.status -Expected "OPEN" -Message "Intake status mismatch"
$ticketId = $intake.ticket_id

if ([string]::IsNullOrWhiteSpace($ticketId)) {
  throw "Intake returned empty ticket_id."
}

Write-Output "Fetching ticket..."
$ticket = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/$ticketId" -Headers $headers
Assert-Equal -Actual $ticket.status -Expected "OPEN" -Message "Ticket status before close mismatch"

Write-Output "Checking events before close..."
$eventsBefore = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/$ticketId/events" -Headers $headers
if ($eventsBefore.Count -lt 1) {
  throw "Expected at least one event before close."
}

Write-Output "Closing ticket..."
$closed = Invoke-RestMethod -Method Patch -Uri "$BaseUrl/tickets/$ticketId/close" -Headers $headers
Assert-Equal -Actual $closed.status -Expected "CLOSED" -Message "Close status mismatch"

Write-Output "Checking events after close..."
$eventsAfter = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/$ticketId/events" -Headers $headers
if ($eventsAfter.Count -lt ($eventsBefore.Count + 1)) {
  throw "Expected one additional event after close."
}

$closedAfterFirst = @($eventsAfter | Where-Object { $_.event_type -eq "CLOSED" }).Count

Write-Output "Closing ticket again (idempotency check)..."
$closedAgain = Invoke-RestMethod -Method Patch -Uri "$BaseUrl/tickets/$ticketId/close" -Headers $headers
Assert-Equal -Actual $closedAgain.status -Expected "CLOSED" -Message "Second close status mismatch"

$eventsAfterSecondClose = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/$ticketId/events" -Headers $headers
$closedAfterSecond = @($eventsAfterSecondClose | Where-Object { $_.event_type -eq "CLOSED" }).Count
if ($closedAfterSecond -ne $closedAfterFirst) {
  throw "Idempotency check failed: duplicate CLOSED event detected."
}

Write-Output "SMOKE_E2E_OK ticket_id=$ticketId"
