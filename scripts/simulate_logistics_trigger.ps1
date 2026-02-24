param(
  [string]$BaseUrl = "http://localhost:8001"
)

$ErrorActionPreference = "Stop"

$eventId = "evt-" + [Guid]::NewGuid().ToString("N").Substring(0, 10)
$headers = @{ "X-User-Role" = "operator" }

$payload = @{
  tenant_id = "demo"
  source_system = "wms"
  event_id = $eventId
  event_type = "CONVEYOR_JAM"
  severity = "high"
  asset_id = "CONV-LINE-01"
  location = "DC-NORTH-L1"
  summary = "Conveyor lane jam detected by PLC"
  details = "Sensor mismatch and motor current spike."
} | ConvertTo-Json

Write-Output "Sending logistics trigger..."
$resp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/automation/external-intake" -ContentType "application/json" -Body $payload -Headers $headers
$resp | ConvertTo-Json -Depth 6

Write-Output "Fetching created/correlated ticket..."
try {
  $ticket = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/$($resp.ticket_id)" -Headers $headers
} catch {
  $loginBody = @{ email = "operator@example.com"; password = "ChangeMe123!" } | ConvertTo-Json
  $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" -ContentType "application/json" -Body $loginBody -Headers $headers
  if ($login.access_token) {
    $headers["Authorization"] = "Bearer $($login.access_token)"
  }
  $ticket = Invoke-RestMethod -Method Get -Uri "$BaseUrl/tickets/$($resp.ticket_id)" -Headers $headers
}
$ticket | ConvertTo-Json -Depth 6
