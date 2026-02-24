CREATE TABLE IF NOT EXISTS app_users (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
  tenant_id TEXT NOT NULL DEFAULT 'demo',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO app_users (email, full_name, password_hash, password_salt, role, tenant_id, is_active)
VALUES
  ('admin@example.com', 'Demo Admin', 'e4afaa3235fddb12492bcb1f92ff20f4f33eff1e994cb47523e54f449fabe5f9', '15e89406b619846efd04a93a040334b7', 'admin', 'demo', TRUE),
  ('operator@example.com', 'Demo Operator', 'dcbb0f400736d66f0a3f826e56a05eba18488a7a58cd063750a761ac1d5dc2a8', '1ad9b370c793e562f5dd1cdf509551a7', 'operator', 'demo', TRUE),
  ('viewer@example.com', 'Demo Viewer', '7c1826c7f58a53024dc6f9d186318c771c5e789fd2956343747829065676592f', '80684a0e274b1c0bba7d1457787e2916', 'viewer', 'demo', TRUE)
ON CONFLICT (email) DO NOTHING;
