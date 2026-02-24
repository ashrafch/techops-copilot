# Manuale Utente - TechOps Copilot

## 1. Scopo del software

TechOps Copilot e una console operativa per:
- ricevere ticket manuali o da trigger esterni;
- gestire assegnazioni, stati e note operative;
- monitorare KPI e SLA;
- configurare utenti, routing email e policy di automazione.

Il prodotto e pensato per ambienti aziendali (automazione, logistica, operations).

## 2. Ruoli utente

I ruoli applicativi sono:
- `viewer`: sola lettura (ticket, KPI).
- `operator`: gestione operativa (creazione, assegnazione, stato, note).
- `admin`: pieno controllo (operator + configurazione amministrativa).

Con autenticazione attiva, il ruolo viene letto dal token login.

## 3. Requisiti minimi

- Docker + Docker Compose.
- Browser moderno (Chrome, Edge, Firefox).
- API e Web avviati.
- Database inizializzato e migrazioni applicate.

## 4. Avvio rapido

Dalla root progetto:

```powershell
docker compose up -d postgres_app minio api web
powershell -ExecutionPolicy Bypass -File scripts/apply_db_migrations.ps1
```

Verifica:
- API health: `http://localhost:8001/health`
- Frontend: `http://localhost:5173`

## 5. Accesso alla console

Apri `http://localhost:5173`.

Se auth e abilitata (`ENFORCE_AUTH=true`):
- usa schermata login;
- utenti demo: `admin@example.com`, `operator@example.com`, `viewer@example.com`;
- password iniziale: `ChangeMe123!`.

## 6. Panoramica interfaccia

La UI e divisa in tre aree:
- **Operazioni**: ticketing giornaliero.
- **Performance**: KPI operativi.
- **Admin** (solo admin): configurazione tenant e governance.

Nella parte alta trovi:
- stato API (`Health` e `Ready`);
- utente attivo;
- metriche rapide (ticket aperti, at risk, breached, media risoluzione).

## 7. Flusso operativo standard (utente operator)

### 7.1 Creazione ticket manuale

In **Operazioni**:
1. Compila `Email destinatario notifica`.
2. Compila `Nome richiedente`, `Email richiedente`, `Oggetto`, `Priorita`, `Descrizione`.
3. Se necessario, apri `Mostra campi tecnici` e compila linea/stazione/seriale.
4. Clicca `Crea Ticket`.

Risultato:
- ticket creato in inbox;
- timeline con evento di creazione;
- notifica inviata secondo workflow configurato.

### 7.2 Gestione inbox

Usa i filtri:
- cliente (`tenant`);
- stato ticket;
- coda (`ALL`, `MY_TICKETS`, `UNASSIGNED`, `AT_RISK`, `BREACHED`);
- ricerca testuale;
- ticket per pagina.

Azione `Refresh` aggiorna immediatamente lista e KPI.

### 7.3 Gestione dettaglio ticket

Seleziona un ticket dalla tabella e usa:
- **Assegnazione**: nome/email operatore.
- **Stato**: `OPEN`, `IN_PROGRESS`, `WAITING`, `RESOLVED`, `CLOSED`.
- **Nota operativa**: annotazioni tecniche.
- **Chiudi ticket**: chiusura definitiva.

La timeline registra ogni passaggio.

## 8. Dashboard Performance

In **Performance** trovi:
- volumi ticket (aperti, in progress, waiting, resolved, closed);
- indicatori ultime 24h;
- ticket SLA a rischio/superati;
- tempo medio di risoluzione.

Usala per controllo giornaliero di carico e criticita.

## 9. Pannello Admin (solo admin)

## 9.1 Utenti

- crea utenti (`email`, nome, ruolo, password, attivo/non attivo);
- abilita/disabilita account;
- reset password.

## 9.2 Routing notifiche

Configura destinatari default tenant:
- salva elenco email per notifiche ticket.

## 9.3 SLA

Configura policy SLA tenant (minuti):
- `P1`, `P2`, `P3`, `P4`.

## 9.4 Automation

Configura comportamento agente AI:
- `Finestra correlazione (minuti)`: decide quando un evento esterno si correla a ticket gia aperto.
- `Anticipo alert AT_RISK (minuti)`: soglia preallarme SLA.
- `Nome/Email assegnazione automatica`: owner automatico sui ticket da trigger esterni.

Azioni:
- `Salva policy automazione`.
- `Esegui monitor SLA`: lancia controllo automatico ticket SLA.

Nota:
- il monitor SLA genera alert idempotenti (`AT_RISK`, `BREACHED`) e li scrive in timeline una sola volta per tipo alert/ticket.

## 9.5 Audit

Mostra log amministrativi:
- chi ha fatto cosa;
- quando;
- su quale oggetto (utente, policy, route).

## 9.6 Tecnico

Sezione avanzata (collassabile) per supporto:
- API base URL;
- API key;
- intake mode (`webhook` consigliata);
- webhook URL;
- ruolo simulato (solo se auth non forzata).

## 10. Trigger esterni e automazione AI

Endpoint esterno:
- `POST /automation/external-intake`

Comportamento:
- deduplica su `(tenant_id, source_system, event_id)`;
- correlazione su ticket aperto dello stesso asset/evento entro finestra policy;
- creazione nuovo ticket se non correlabile;
- playbook consigliato in risposta;
- assegnazione automatica se configurata.

Script demo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/simulate_logistics_trigger.ps1
```

## 11. Test funzionale consigliato (prima di andare in produzione)

### 11.1 Smoke completo base

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_e2e.ps1
```

### 11.2 Smoke enterprise (admin + governance)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_enterprise_admin.ps1
```

### 11.3 Suite test API

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_api.ps1
```

## 12. Troubleshooting rapido

### 12.1 Errore 401 (Unauthorized)

Cause tipiche:
- token scaduto/non presente;
- ruolo non autorizzato;
- auth/RBAC attivati senza header corretti.

Azioni:
- rifai login;
- verifica ruolo utente;
- controlla variabili `ENFORCE_AUTH`, `ENFORCE_RBAC`.

### 12.2 Errore CORS dal frontend

Verifica `CORS_ALLOWED_ORIGINS` lato API (deve includere `http://localhost:5173` in sviluppo).

### 12.3 Ticket creato ma email non ricevuta

Controlla:
- workflow n8n attivo;
- nodo `Respond to Webhook` con output JSON valido;
- route tenant o override destinatario;
- credenziali provider email.

### 12.4 Trigger esterno non crea ticket

Controlla:
- payload obbligatorio (`tenant_id`, `source_system`, `event_id`, `event_type`, `asset_id`, `summary`);
- endpoint raggiungibile;
- API key/token se richiesti;
- log API e n8n.

## 13. Best practice operative

- Mantieni un tenant separato per ambiente (`dev`, `staging`, `prod`).
- Assegna sempre owner ai ticket critici.
- Esegui `Run SLA Monitor` a intervalli regolari o schedulalo via workflow.
- Usa audit log per verifiche governance.
- Prima di ogni rilascio esegui smoke base + enterprise.

## 13.1 Nuove funzioni UX e governance AI

- **Onboarding guidato**: al primo accesso compare un wizard in 4 step per configurare rapidamente tenant, ticket test e policy AI.
- **Notification center in-app**: nella card dettaglio trovi segnalazioni immediate (SLA breached/at risk e decisioni AI pending).
- **Executive report KPI**: nella vista Performance trovi SLA attainment, MTTR, copertura automazione, ore risparmiate e stima impatto economico.
- **Human-in-the-loop**: in Admin > Automation puoi approvare/rifiutare decisioni AI sotto soglia.
- **Catalogo playbook versionato**: in Admin > Automation puoi creare playbook per evento/severità con versione controllata.
- **Localizzazione IT/EN**: pulsante lingua in header per passare rapidamente tra italiano e inglese.

## 14. Glossario

- **Tenant**: cliente/ambiente logico isolato.
- **SLA**: tempo massimo concordato per presa in carico/risoluzione.
- **AT_RISK**: ticket vicino alla scadenza SLA.
- **BREACHED**: ticket oltre la scadenza SLA.
- **Correlazione**: riuso ticket esistente per eventi simili, evitando duplicati.

