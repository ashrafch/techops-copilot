ALTER TABLE app_users
  ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS mfa_secret TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS tenant_sso_configs (
  tenant_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL DEFAULT 'oidc',
  issuer TEXT NOT NULL DEFAULT '',
  audience TEXT NOT NULL DEFAULT '',
  client_id TEXT NOT NULL DEFAULT '',
  sso_shared_secret TEXT NOT NULL DEFAULT '',
  is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO tenant_sso_configs (tenant_id, provider, issuer, audience, client_id, sso_shared_secret, is_enabled)
VALUES ('demo', 'oidc', 'techops-sso-demo', 'techops-copilot', 'techops-demo-client', '', FALSE)
ON CONFLICT (tenant_id) DO NOTHING;
