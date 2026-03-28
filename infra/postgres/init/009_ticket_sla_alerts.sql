CREATE TABLE IF NOT EXISTS ticket_sla_alerts (
  id BIGSERIAL PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
  alert_type TEXT NOT NULL CHECK (alert_type IN ('AT_RISK', 'BREACHED')),
  alerted_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (ticket_id, alert_type)
);

CREATE INDEX IF NOT EXISTS idx_ticket_sla_alerts_alerted_at
  ON ticket_sla_alerts (alerted_at DESC);
