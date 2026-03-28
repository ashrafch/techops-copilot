CREATE TABLE IF NOT EXISTS tenant_automation_policies (
  tenant_id TEXT PRIMARY KEY,
  correlation_window_minutes INTEGER NOT NULL DEFAULT 1440,
  auto_assign_name TEXT NOT NULL DEFAULT '',
  auto_assign_email TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO tenant_automation_policies (tenant_id, correlation_window_minutes, auto_assign_name, auto_assign_email)
VALUES
('demo', 1440, 'Automation Dispatcher', ''),
('mypulsar', 720, 'Automation Dispatcher', '')
ON CONFLICT (tenant_id) DO UPDATE SET
  correlation_window_minutes = EXCLUDED.correlation_window_minutes,
  auto_assign_name = EXCLUDED.auto_assign_name,
  auto_assign_email = EXCLUDED.auto_assign_email,
  updated_at = NOW();
