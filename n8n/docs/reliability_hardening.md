## n8n Reliability Hardening

Obiettivo: ridurre failure transitori su API/SMTP con retry automatici sui nodi critici.

Script:
`scripts/patch_n8n_reliability.ps1`

Nodi aggiornati:
- `Create Ticket`
- `Send email`
- `HTTP Log Email_Sent`
- `HTTP Log NOTE (Email Failed)`

Policy applicata:
- `retryOnFail = true`
- `maxTries = 3`
- `waitBetweenTries = 2000ms`

Esecuzione:

```powershell
$env:N8N_API_KEY="YOUR_TEMP_KEY"
powershell -ExecutionPolicy Bypass -File scripts/patch_n8n_reliability.ps1
```

Dry run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/patch_n8n_reliability.ps1 -DryRun
```
