-- 003_ticket_events.sql

CREATE TABLE IF NOT EXISTS ticket_events (
  id BIGSERIAL PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('CREATED', 'EMAIL_SENT', 'CLOSED', 'NOTE')),
  message TEXT NOT NULL DEFAULT '',
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id ON ticket_events(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_events_created_at ON ticket_events(created_at);
