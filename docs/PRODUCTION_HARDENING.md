# Production Hardening e Release Process

## Sicurezza implementata

- Sessioni auth con refresh token e revoca (`/auth/refresh`, `/auth/logout`).
- Lockout login su tentativi falliti.
- Password policy forte configurabile da env.
- Isolamento tenant rigoroso lato API (`ENFORCE_TENANT_ISOLATION=true`).
- Security audit log + cleanup retention (`/admin/security/cleanup`).
- GDPR baseline:
  - export tenant (`/admin/gdpr/export`)
  - purge storico (`/admin/gdpr/purge`).

## Affidabilità implementata

- Scheduler SLA monitor automatico (`SLA_MONITOR_SCHEDULER_ENABLED=true`).
- Retry su action webhook (3 tentativi).
- Dead letter queue (`action_dead_letters`) su fallimento definitivo.
- Idempotency key storage (`api_idempotency_keys`).

## API versioning

Endpoint disponibili sia senza prefisso sia con prefisso `/v1`.

## Release process suggerito

1. Feature branch da `dev`.
2. Test locali:
   - `scripts/test_api.ps1`
   - `scripts/smoke_enterprise_admin.ps1`
   - `scripts/smoke_e2e.ps1`
   - `npm --prefix services/web run build`
3. PR verso `dev`.
4. Tag release (`vX.Y.Z`).
5. Deploy su stage.
6. Smoke stage.
7. Promote produzione.

## Configurazioni ambiente

- `APP_ENV=dev|stage|prod`
- `ENFORCE_AUTH=true`
- `ENFORCE_RBAC=true`
- `ENFORCE_TENANT_ISOLATION=true`
- `AUTH_SECRET_KEY` forte e ruotato periodicamente.
- `AUTH_REQUIRE_MFA_FOR_ADMIN=true` (con MFA header/code integrato nel flusso).
- `SLA_MONITOR_SCHEDULER_ENABLED=true`

## Note enterprise SSO

Roadmap successiva: integrazione OIDC piena (Azure AD/Okta) con redirect flow lato frontend.
