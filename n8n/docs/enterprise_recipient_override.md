## Enterprise Recipient Override (Per Ticket)

Obiettivo: usare il destinatario scelto in UI solo per il ticket corrente, senza aggiornare la route globale del tenant.

### Payload atteso dal webhook

La UI invia:

```json
{
  "tenant_id": "demo",
  "requester": { "name": "Mario", "email": "mario@acme.it" },
  "subject": "Issue",
  "description_raw": "Details",
  "machine": { "line": "L1", "station": "S1", "serial": "M001" },
  "priority": "P3",
  "notification": {
    "to_emails": ["ops@acme.it"]
  }
}
```

### Patch del nodo "Resolve Destination" (Code node)

Usa prima `notification.to_emails`, altrimenti fallback su `tenant_routes.to_emails`.

```javascript
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
```

### Patch automatico via API n8n

Script incluso:
`scripts/patch_n8n_enterprise_recipient.ps1`

Esempio:

```powershell
$env:N8N_API_KEY="YOUR_TEMP_KEY"
powershell -ExecutionPolicy Bypass -File scripts/patch_n8n_enterprise_recipient.ps1
```

Opzioni:
- `-N8nBaseUrl http://localhost:5678`
- `-WorkflowNameLike "ticket intake"`
- `-DryRun`

### Nodo invio email

- Campo `To`: `={{$json.destination.to_emails.join(",")}}`

### Nodo log evento EMAIL_SENT (opzionale ma consigliato)

- `meta.to` deve salvare `{{$json.destination.to_emails}}` per audit.
