CREATE TABLE IF NOT EXISTS tenant_sla_policies (
  tenant_id TEXT PRIMARY KEY,
  p1_minutes INTEGER NOT NULL DEFAULT 60,
  p2_minutes INTEGER NOT NULL DEFAULT 240,
  p3_minutes INTEGER NOT NULL DEFAULT 480,
  p4_minutes INTEGER NOT NULL DEFAULT 1440,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO tenant_sla_policies (tenant_id, p1_minutes, p2_minutes, p3_minutes, p4_minutes)
VALUES
('demo', 60, 240, 480, 1440),
('mypulsar', 30, 120, 240, 720)
ON CONFLICT (tenant_id) DO UPDATE SET
  p1_minutes = EXCLUDED.p1_minutes,
  p2_minutes = EXCLUDED.p2_minutes,
  p3_minutes = EXCLUDED.p3_minutes,
  p4_minutes = EXCLUDED.p4_minutes,
  updated_at = NOW();
