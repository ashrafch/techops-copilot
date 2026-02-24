-- Add SLA policy table and ticket SLA lifecycle fields.
-- Safe to run multiple times.

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
VALUES ('demo', 60, 240, 480, 1440)
ON CONFLICT (tenant_id) DO NOTHING;

ALTER TABLE tickets
  ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMP NULL,
  ADD COLUMN IF NOT EXISTS first_response_at TIMESTAMP NULL,
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP NULL;

CREATE INDEX IF NOT EXISTS idx_tickets_sla_due_at ON tickets (sla_due_at);
