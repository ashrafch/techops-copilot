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