ALTER TABLE tenant_automation_policies
  ADD COLUMN IF NOT EXISTS human_review_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.7500,
  ADD COLUMN IF NOT EXISTS auto_execute_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.8500;

CREATE TABLE IF NOT EXISTS agent_pending_decisions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  confidence NUMERIC(5,4) NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')) DEFAULT 'PENDING',
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  approved_by TEXT NOT NULL DEFAULT '',
  approved_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_pending_decisions_tenant_status_created
  ON agent_pending_decisions (tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_playbooks (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  version INTEGER NOT NULL,
  team TEXT NOT NULL,
  runbook TEXT NOT NULL,
  action TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, event_type, severity, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_playbooks_lookup
  ON agent_playbooks (tenant_id, event_type, severity, is_active, version DESC);

INSERT INTO agent_playbooks (tenant_id, event_type, severity, version, team, runbook, action, is_active)
VALUES
('demo', 'CONVEYOR_JAM', 'high', 1, 'automation-maintenance', 'RB-LOG-001', 'Isolate conveyor lane, clear jam, restart PLC sequence.', TRUE),
('demo', 'ROBOT_STALL', 'critical', 1, 'robotics-support', 'RB-AUTO-014', 'Check E-stop chain, inspect cell safety relays, recalibrate robot.', TRUE)
ON CONFLICT (tenant_id, event_type, severity, version) DO NOTHING;
