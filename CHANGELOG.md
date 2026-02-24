# Changelog

## [Unreleased]

### Added
- Auth hardening: refresh token, session revocation/logout, login lockout.
- Password policy configurabile.
- Tenant isolation guard su endpoint business.
- Security/GDPR admin endpoints (`gdpr export`, `gdpr purge`, `security cleanup`).
- Scheduler SLA monitor opzionale.
- Action webhook retry + dead letter.
- DB backup/restore scripts e documentazione operativa.
- API v1 alias routing.

### Changed
- Policy automazione tenant estesa con webhook orchestration.
- Test API estesi per auth hardening.
