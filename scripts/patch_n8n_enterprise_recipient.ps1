param(
  [string]$N8nBaseUrl = "http://localhost:5678",
  [string]$ApiKey = $env:N8N_API_KEY,
  [string]$WorkflowNameLike = "ticket intake",
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

  $headers = @{
    "X-N8N-API-KEY" = $ApiKey
  }

  $url = "$($N8nBaseUrl.TrimEnd('/'))$Path"

  if ($null -ne $Body) {
    return Invoke-RestMethod -Method $Method -Uri $url -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 100)
  }

  return Invoke-RestMethod -Method $Method -Uri $url -Headers $headers
}

$resolveDestinationCode = @'
const body = $json;
const route = $items("DB Lookup Route", 0, 0)[0]?.json ?? {};

const override = Array.isArray(body.notification?.to_emails)
  ? body.notification.to_emails
      .map((x) => String(x || "").trim().toLowerCase())
      .filter(Boolean)
  : [];

const routeEmails = String(route.to_emails || "")
  .split(",")
  .map((x) => x.trim().toLowerCase())
  .filter(Boolean);

const to_emails = override.length > 0 ? override : routeEmails;

if (to_emails.length === 0) {
  throw new Error("No destination email resolved");
}

return [
  {
    json: {
      ...body,
      destination: {
        to_emails,
      },
    },
  },
];
'@

$normalizeCode = @'
const src = $json?.body ?? $json ?? {};

const tenant_id = (src.tenant_id ?? "demo").toString().trim() || "demo";
const subject   = (src.subject ?? "").toString().trim() || "No subject";

const pr = (src.priority ?? "P3").toString().trim().toUpperCase();
const priority = ["P1","P2","P3","P4"].includes(pr) ? pr : "P3";

const description_raw =
  (src.description_raw ?? src.description ?? "").toString().trim() || "-";

const requester_name =
  (src.requester?.name ?? src.requester_name ?? "Unknown").toString().trim() || "Unknown";

const requester_email_raw =
  (src.requester?.email ?? src.requester_email ?? "unknown@example.com").toString().trim();

const requester_email =
  requester_email_raw.includes("@") ? requester_email_raw : "unknown@example.com";

const machine_line    = (src.machine?.line ?? src.machine_line ?? "").toString().trim();
const machine_station = (src.machine?.station ?? src.machine_station ?? "").toString().trim();
const machine_serial  = (src.machine?.serial ?? src.machine_serial ?? "").toString().trim();

const notification_to_emails = Array.isArray(src.notification?.to_emails)
  ? src.notification.to_emails
      .map((x) => String(x || "").trim().toLowerCase())
      .filter(Boolean)
  : [];

return [{
  json: {
    tenant_id,
    source: (src.source ?? "webhook").toString(),
    subject,
    priority,
    description_raw,
    requester: { name: requester_name, email: requester_email },
    machine: { line: machine_line, station: machine_station, serial: machine_serial },
    notification: { to_emails: notification_to_emails },
  }
}];
'@

$assemblePayloadCode = @'
const n = $node["Normalize"].json;
const t = $node["Create Ticket"].json;

const routeRow = ($node["DB Lookup Route"].json && Object.keys($node["DB Lookup Route"].json).length)
  ? $node["DB Lookup Route"].json
  : null;

const overrideTo = Array.isArray(n.notification?.to_emails)
  ? n.notification.to_emails.map(s => String(s || "").trim()).filter(Boolean)
  : [];

const routeTo = (routeRow?.to_emails || "ashraf.ch1998@gmail.com")
  .split(",")
  .map(s => s.trim())
  .filter(Boolean);

const to = overrideTo.length > 0 ? overrideTo : routeTo;
const cc = (routeRow?.cc_emails || "").split(",").map(s => s.trim()).filter(Boolean);
const bcc = (routeRow?.bcc_emails || "").split(",").map(s => s.trim()).filter(Boolean);
const replyTo = (routeRow?.reply_to || "").trim();

const subject = `[TICKET ${t.ticket_id}] ${n.subject} (${n.priority})`;

const html = `
<div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.4;">
  <h2 style="margin:0 0 10px 0;">Nuovo ticket creato</h2>
  <p><strong>ID:</strong> ${t.ticket_id}</p>
  <p><strong>Stato:</strong> ${t.status}</p>
  <hr style="margin:12px 0;" />
  <p><strong>Oggetto:</strong> ${n.subject}</p>
  <p><strong>Priorita:</strong> ${n.priority}</p>
  <p><strong>Richiedente:</strong> ${n.requester.name} (${n.requester.email})</p>
  <p><strong>Macchina:</strong> Linea ${n.machine.line}, Stazione ${n.machine.station}, Seriale ${n.machine.serial}</p>
  <p><strong>Descrizione:</strong><br/>${n.description_raw}</p>
</div>
`.trim();

return [{
  json: {
    tenant_id: n.tenant_id,
    ticket_id: t.ticket_id,
    status: t.status,
    mail: { to, cc, bcc, replyTo, subject, html }
  }
}];
'@

$wfList = Invoke-N8nApi -Method GET -Path "/api/v1/workflows"
$workflows = @($wfList.data)
if (-not $workflows -or $workflows.Count -eq 0) {
  throw "No workflows returned from n8n API."
}

$candidate = $workflows |
  Where-Object { $_.name -match $WorkflowNameLike } |
  Select-Object -First 1

if (-not $candidate) {
  throw "No workflow found matching '$WorkflowNameLike'."
}

Write-Host "Workflow selected: $($candidate.id) - $($candidate.name)"

$wf = Invoke-N8nApi -Method GET -Path "/api/v1/workflows/$($candidate.id)"
$nodes = @($wf.nodes)
if (-not $nodes -or $nodes.Count -eq 0) {
  throw "Workflow has no nodes."
}

$targetNode = $nodes | Where-Object { $_.name -eq "Resolve Destination" } | Select-Object -First 1
if (-not $targetNode) {
  $targetNode = $nodes | Where-Object { $_.name -match "Resolve Destination" } | Select-Object -First 1
}
if (-not $targetNode) {
  throw "Node 'Resolve Destination' not found."
}

$currentType = [string]$targetNode.type
if ($currentType -notmatch "code|function") {
  throw "Node '$($targetNode.name)' is not a Code/Function node (type=$currentType)."
}

$params = $targetNode.parameters
if ($null -eq $params) {
  $params = @{}
}

if ($null -ne $params.jsCode) {
  $params.jsCode = $resolveDestinationCode
} elseif ($null -ne $params.functionCode) {
  $params.functionCode = $resolveDestinationCode
} else {
  # Default for modern Code node
  $params.jsCode = $resolveDestinationCode
}

$targetNode.parameters = $params

$normalizeNode = $nodes | Where-Object { $_.name -eq "Normalize" } | Select-Object -First 1
if ($normalizeNode) {
  $np = $normalizeNode.parameters
  if ($null -eq $np) { $np = @{} }
  if ($null -ne $np.jsCode) { $np.jsCode = $normalizeCode } else { $np.functionCode = $normalizeCode }
  $normalizeNode.parameters = $np
}

$assembleNode = $nodes | Where-Object { $_.name -eq "Assemble Payload" } | Select-Object -First 1
if ($assembleNode) {
  $ap = $assembleNode.parameters
  if ($null -eq $ap) { $ap = @{} }
  if ($null -ne $ap.jsCode) { $ap.jsCode = $assemblePayloadCode } else { $ap.functionCode = $assemblePayloadCode }
  $assembleNode.parameters = $ap
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
Write-Host "Workflow updated successfully: id=$($updated.id) name=$($updated.name)"
