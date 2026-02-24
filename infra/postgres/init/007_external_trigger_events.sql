CREATE TABLE IF NOT EXISTS external_trigger_events (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
  decision TEXT NOT NULL CHECK (decision IN ('CREATED', 'CORRELATED')),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, source_system, event_id)
);

CREATE INDEX IF NOT EXISTS idx_external_trigger_events_tenant_created
  ON external_trigger_events (tenant_id, created_at DESC);
