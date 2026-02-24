param(
  [string]$N8nBaseUrl = "http://localhost:5678",
  [string]$ApiKey = $env:N8N_API_KEY,
  [string]$WorkflowNameLike = "Ticket_Intake",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
  throw "Missing API key. Pass -ApiKey or set N8N_API_KEY."
}

function Invoke-N8nApi {
  param(
    [string]$Method,
    [string]$Path,
    [object]$Body = $null
  )

  $headers = @{ "X-N8N-API-KEY" = $ApiKey }
  $url = "$($N8nBaseUrl.TrimEnd('/'))$Path"

  if ($null -ne $Body) {
    return Invoke-RestMethod -Method $Method -Uri $url -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 100)
  }
  return Invoke-RestMethod -Method $Method -Uri $url -Headers $headers
}

function Set-RetryPolicy {
  param(
    [object]$Node,
    [int]$MaxTries = 3,
    [int]$WaitMs = 2000
  )
  $Node | Add-Member -NotePropertyName retryOnFail -NotePropertyValue $true -Force
  $Node | Add-Member -NotePropertyName maxTries -NotePropertyValue $MaxTries -Force
  $Node | Add-Member -NotePropertyName waitBetweenTries -NotePropertyValue $WaitMs -Force
  return $Node
}

$wfList = Invoke-N8nApi -Method GET -Path "/api/v1/workflows"
$candidate = @($wfList.data) | Where-Object { $_.name -match $WorkflowNameLike } | Select-Object -First 1
if (-not $candidate) {
  throw "No workflow found matching '$WorkflowNameLike'."
}

Write-Host "Workflow selected: $($candidate.id) - $($candidate.name)"

$wf = Invoke-N8nApi -Method GET -Path "/api/v1/workflows/$($candidate.id)"

$targetNames = @(
  "Create Ticket",
  "Send email",
  "HTTP Log Email_Sent",
  "HTTP Log NOTE (Email Failed)"
)

foreach ($node in $wf.nodes) {
  if ($targetNames -contains $node.name) {
    Set-RetryPolicy -Node $node -MaxTries 3 -WaitMs 2000 | Out-Null
  }
}

if ($DryRun) {
  Write-Host "DryRun enabled. No update sent."
  exit 0
}

$updateBody = @{
  name = $wf.name
  nodes = $wf.nodes
  connections = $wf.connections
  settings = $wf.settings
}

$updated = Invoke-N8nApi -Method PUT -Path "/api/v1/workflows/$($candidate.id)" -Body $updateBody
Write-Host "Workflow reliability updated: id=$($updated.id) name=$($updated.name)"
