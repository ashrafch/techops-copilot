CREATE TABLE IF NOT EXISTS tenant_routes (
  tenant_id TEXT PRIMARY KEY,
  channel TEXT NOT NULL DEFAULT 'email',
  to_emails TEXT NOT NULL,
  cc_emails TEXT DEFAULT '',
  bcc_emails TEXT DEFAULT '',
  reply_to TEXT DEFAULT '',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO tenant_routes (tenant_id, channel, to_emails, cc_emails, bcc_emails, reply_to)
VALUES
('demo', 'email', 'ashraf.ch1998@gmail.com', '', '', ''),
('mypulsar', 'email', 'assistenza@mypulsar.net', 'quality@mypulsar.net', '', 'account@mypulsar.net')
ON CONFLICT (tenant_id) DO UPDATE SET
  channel = EXCLUDED.channel,
  to_emails = EXCLUDED.to_emails,
  cc_emails = EXCLUDED.cc_emails,
  bcc_emails = EXCLUDED.bcc_emails,
  reply_to = EXCLUDED.reply_to,
  updated_at = NOW();
