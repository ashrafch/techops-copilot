ALTER TABLE tenant_automation_policies
  ADD COLUMN IF NOT EXISTS at_risk_lead_minutes INTEGER NOT NULL DEFAULT 60;

UPDATE tenant_automation_policies
SET at_risk_lead_minutes = 60
WHERE at_risk_lead_minutes IS NULL OR at_risk_lead_minutes < 1;

CREATE TABLE IF NOT EXISTS ticket_sla_alerts (
  id BIGSERIAL PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id),
  alert_type TEXT NOT NULL CHECK (alert_type IN ('AT_RISK', 'BREACHED')),
  alerted_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (ticket_id, alert_type)
);

CREATE INDEX IF NOT EXISTS idx_ticket_sla_alerts_alerted_at
  ON ticket_sla_alerts (alerted_at DESC);
