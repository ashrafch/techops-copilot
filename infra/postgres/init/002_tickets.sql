-- 002_tickets.sql

-- Sequenza giornaliera per ticket_id tipo: TCK-YYYYMMDD-0001
CREATE TABLE IF NOT EXISTS ticket_sequences (
  day DATE PRIMARY KEY,
  last_seq INTEGER NOT NULL DEFAULT 0
);

-- Tabella principale tickets
CREATE TABLE IF NOT EXISTS tickets (
  id BIGSERIAL PRIMARY KEY,
  ticket_id TEXT UNIQUE NOT NULL,

  tenant_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),

  subject TEXT NOT NULL,
  priority TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),  -- P1..P4
  description_raw TEXT NOT NULL,

  requester_name TEXT NOT NULL,
  requester_email TEXT NOT NULL,

  machine_line TEXT NOT NULL DEFAULT '',
  machine_station TEXT NOT NULL DEFAULT '',
  machine_serial TEXT NOT NULL DEFAULT '',

  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indici utili
CREATE INDEX IF NOT EXISTS idx_tickets_tenant_created ON tickets (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_status_created ON tickets (status, created_at DESC);

-- Trigger-like: aggiorna updated_at automaticamente (senza trigger, lo faremo da API per semplicità)
