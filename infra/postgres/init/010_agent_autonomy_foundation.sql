ALTER TABLE tenant_automation_policies
  ADD COLUMN IF NOT EXISTS action_webhook_url TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS action_webhook_token TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS agent_decision_logs (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  decision TEXT NOT NULL,
  priority TEXT NOT NULL,
  reason TEXT NOT NULL,
  confidence NUMERIC(5,4) NOT NULL,
  playbook JSONB NOT NULL DEFAULT '{}'::jsonb,
  memory_hint TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_decision_logs_tenant_created
  ON agent_decision_logs (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_action_runs (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  action_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('SKIPPED', 'SUCCESS', 'FAILED')),
  detail TEXT NOT NULL DEFAULT '',
  request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_action_runs_tenant_created
  ON agent_action_runs (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_memory_feedback (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  outcome_score INTEGER NOT NULL CHECK (outcome_score BETWEEN 1 AND 5),
  resolution_note TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_feedback_lookup
  ON agent_memory_feedback (tenant_id, event_type, created_at DESC);
