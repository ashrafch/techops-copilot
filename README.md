📄 README.md — Descrizione tecnica
TechOps Copilot – Automated Ticket Intake & Notification System

TechOps Copilot è una piattaforma self-hosted per la gestione automatizzata delle segnalazioni tecniche in ambito industriale e B2B.

Il sistema riceve eventi tecnici (manuali o automatici), li normalizza, genera ticket strutturati e notifica in tempo reale i team operativi tramite canali di comunicazione aziendali (es. Microsoft Teams), garantendo tracciabilità, standardizzazione e integrazione con sistemi esistenti.

🧠 Architettura generale

Il progetto è composto da tre componenti principali, orchestrati tramite Docker:

1. API Backend (FastAPI – Python)

Responsabile della logica di business e della generazione dei ticket.

Funzionalità principali:

Endpoint REST /intake per la creazione di ticket

Validazione strutturata dei dati (Pydantic)

Generazione di ticket ID univoci

Base pronta per persistenza su database (PostgreSQL)

Pensata come servizio indipendente e scalabile

Tecnologie:

Python 3.11

FastAPI

Pydantic

Uvicorn

2. Workflow Engine (n8n – Self Hosted)

Responsabile dell’orchestrazione degli eventi e delle integrazioni esterne.

Il workflow principale:

Riceve un evento tramite Webhook HTTP

Normalizza e valida il payload (JavaScript)

Risolve dinamicamente il canale di notifica in base al cliente (tenant_id)

Chiama l’API backend per creare il ticket

Invia notifiche automatiche (es. Microsoft Teams)

Risponde al chiamante con l’esito dell’operazione

Caratteristiche:

Routing multi-cliente

Supporto a più canali di notifica

Error handling e fallback configurabili

Separazione chiara tra logica di processo e logica di business

Tecnologie:

n8n (self-hosted)

JavaScript (Code nodes)

HTTP Webhooks

3. Infrastructure Services

Servizi di supporto per storage e dati.

PostgreSQL
Database relazionale pronto per:

tickets

audit log

configurazioni cliente

MinIO (S3 compatible)
Storage oggetti per:

allegati futuri

report

esportazioni

🔁 Flusso operativo (runtime)

Un sistema esterno (HMI, web form, automazione, ecc.) invia una richiesta HTTP al webhook n8n

Il payload viene validato e normalizzato

In base al tenant_id viene determinato il canale di notifica

L’API backend genera un ticket strutturato

Il team operativo riceve una notifica in tempo reale

Il chiamante riceve una risposta sincrona con ticket_id e stato

🎯 Obiettivi del sistema

Standardizzare la gestione delle segnalazioni tecniche

Eliminare comunicazioni informali e non tracciate

Centralizzare eventi provenienti da sistemi diversi

Fornire una base scalabile per:

reportistica

## Documentazione operativa aggiornata

- Hardening produzione: `docs/PRODUCTION_HARDENING.md`
- Backup/restore: `docs/BACKUP_RESTORE.md`
- Manuale utente: `docs/MANUALE_UTENTE.md`
- Processo release: `docs/RELEASE_PROCESS.md`
- Profili ambiente: `env/.env.dev.example`, `env/.env.stage.example`, `env/.env.prod.example`

KPI tecnici

storico problemi

integrazione con ERP / CMMS / MES

🧩 Design principles

Self-hosted & vendor-independent

Separation of concerns

n8n → orchestrazione

API → business logic

Multi-tenant ready

Extensible by design

Enterprise-friendly

🚀 Stato del progetto

✅ Ticket intake funzionante

✅ Workflow di orchestrazione operativo

✅ Notifiche real-time (Teams)

⏳ Persistenza avanzata su database

⏳ Reporting e dashboard

⏳ Autenticazione e controllo accessi

🛠️ Stack tecnologico

Python / FastAPI

n8n (self-hosted)

PostgreSQL

MinIO (S3)

Docker / Docker Compose

JavaScript (workflow logic)

📌 Nota

Il progetto è pensato come base per un prodotto B2B, non come semplice automazione isolata.

## Smoke test rapido (obbligatorio dopo modifiche)

Per verificare avvio applicativo e flusso ticket end-to-end:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_e2e.ps1
```

Il test avvia `postgres_app`, `minio`, `api` e valida:
- `/health`
- `/ready`
- creazione ticket (`/intake`)
- lettura ticket (`/tickets/{ticket_id}`)
- timeline eventi (`/tickets/{ticket_id}/events`)
- chiusura ticket (`/tickets/{ticket_id}/close`)

## Smoke test enterprise (admin workflow)

Per validare un flusso enterprise completo (admin operations + governance):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_enterprise_admin.ps1
```

Il test copre:
- login admin (quando auth è attiva)
- update route tenant
- update policy SLA tenant
- creazione utente da control plane admin
- disattivazione utente
- lettura audit log amministrativo
- lettura KPI operativi (`/tickets/metrics`)

## Test API (suite rapida)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_api.ps1
```

## Sicurezza API (opzionale)

Se imposti `API_KEY` nell'ambiente API, gli endpoint business richiedono header:

`X-API-Key: <API_KEY>`

Per forzare la policy anche se `API_KEY` non è ancora valorizzata:

`REQUIRE_API_KEY=true`

Endpoint sempre pubblici: `/health`, `/ready`.

## RBAC (foundation enterprise, opzionale)

Se abiliti:
`ENFORCE_RBAC=true`

Le operazioni di scrittura (`/intake`, `/events`, `/tickets/*/assign`, `/tickets/*/status`, `/tickets/*/close`) richiedono header:

`X-User-Role: admin` oppure `X-User-Role: operator`

## Auth utente (login reale, opzionale)

Se abiliti:
`ENFORCE_AUTH=true`

l'API richiede `Authorization: Bearer <token>` sugli endpoint protetti da RBAC.

Endpoint:
- `POST /auth/login` con body `{"email":"...","password":"..."}`
- `GET /auth/me`

Seed utenti demo (password iniziale: `ChangeMe123!`):
- `admin@example.com`
- `operator@example.com`
- `viewer@example.com`

Con auth attiva, il ruolo viene letto dal token (non dal solo header `X-User-Role`).

## Rate limiting (opzionale)

`RATE_LIMIT_RPM` limita richieste/minuto per IP+path sugli endpoint business.

Esempio:

`RATE_LIMIT_RPM=120`

## CORS (UI locale)

Per frontend in locale su `http://localhost:5173`, API usa:

`CORS_ALLOWED_ORIGINS=http://localhost:5173`

## Tracciabilità richieste

Ogni risposta API include header `X-Request-ID`.
Se il client invia `X-Request-ID`, il valore viene mantenuto nella risposta.

## UI (Operations Console)

Avvio locale frontend:

```powershell
cd services/web
npm install
npm run dev
```

Oppure full stack via Docker Compose:

```powershell
docker compose up -d web
```

UI default: `http://localhost:5173`

Modalita' intake dalla UI:
- `VITE_INTAKE_MODE=webhook` (raccomandata): la creazione ticket passa da n8n e attiva le notifiche email/automation.
- `VITE_INTAKE_MODE=api`: la UI chiama direttamente `/intake` sull'API, utile per debug ma senza passare dal workflow n8n.

Webhook default usato dalla UI:
`VITE_WEBHOOK_URL=http://localhost:5678/webhook/ticket-intake`

Gestione destinatari email (nuovo):
- `GET /tenant-email-history?tenant_id=<id>`: ritorna storico email (requester storici + route correnti).
- `GET /tenant-routes/{tenant_id}`: legge la route email attiva per tenant.
- `PATCH /tenant-routes/{tenant_id}` con body `{"to_emails":["ops@azienda.it"]}`: aggiorna il destinatario di notifica usato dal workflow.

Nella UI puoi ora scegliere il destinatario da storico (o inserirne uno nuovo) prima di creare il ticket in modalita' `webhook`.

Modalita' enterprise consigliata:
- non aggiornare la route globale del tenant a ogni ticket;
- passa il destinatario nel payload webhook (`notification.to_emails`) e risolvilo nel workflow n8n con fallback alla route tenant.
- guida operativa: `n8n/docs/enterprise_recipient_override.md`

Workflow ticket enterprise (in sviluppo):
- stati supportati: `OPEN`, `IN_PROGRESS`, `WAITING`, `RESOLVED`, `CLOSED`
- assegnazione owner ticket:
  - `PATCH /tickets/{ticket_id}/assign` con body `{"assignee_name":"...","assignee_email":"..."}`
  - `PATCH /tickets/{ticket_id}/status` con body `{"status":"IN_PROGRESS"}`
- note operative:
  - `POST /tickets/{ticket_id}/notes` con body `{"message":"..."}`
- SLA:
  - policy per tenant (`tenant_sla_policies`)
  - campi ticket: `sla_due_at`, `first_response_at`, `resolved_at`, `sla_state`
  - summary coda: `GET /tickets/queue-summary?tenant_id=<id>&assignee_email=<email>`

Migrazioni DB idempotenti:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply_db_migrations.ps1
```

Hardening affidabilita' workflow n8n:
- guida: `n8n/docs/reliability_hardening.md`
- script patch automatico: `scripts/patch_n8n_reliability.ps1`

## AI Agent: external trigger automation (logistica/automazione)

Nuovo endpoint machine-to-machine:

- `POST /automation/external-intake`

Caso d'uso: sistemi esterni (WMS, PLC, telemetria linea) inviano eventi tecnici e l'agente crea o correla ticket in automatico.

Comportamento automatico:
- deduplica per `(tenant_id, source_system, event_id)`
- correlazione su ticket aperto stesso `asset_id` + `event_type`
- priorita' derivata da severita' + regole dominio
- playbook operativo suggerito nel payload di risposta

Script demo rapido:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/simulate_logistics_trigger.ps1
```

## Manuale utente

Guida completa all'utilizzo del prodotto:
- `docs/MANUALE_UTENTE.md`
- `docs/PRODUCTION_HARDENING.md`
- `docs/BACKUP_RESTORE.md`
- `docs/GO_TO_MARKET.md`
- `CHANGELOG.md`
