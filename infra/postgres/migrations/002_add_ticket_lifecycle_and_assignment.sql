-- Extend ticket lifecycle and assignment fields.
-- Safe to run multiple times.

ALTER TABLE tickets
  ADD COLUMN IF NOT EXISTS assignee_name TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS assignee_email TEXT NOT NULL DEFAULT '';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'tickets_status_check'
  ) THEN
    ALTER TABLE tickets DROP CONSTRAINT tickets_status_check;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'tickets_status_check1'
  ) THEN
    ALTER TABLE tickets DROP CONSTRAINT tickets_status_check1;
  END IF;
END $$;

DO $$
BEGIN
  ALTER TABLE tickets
    ADD CONSTRAINT tickets_status_check
    CHECK (status IN ('OPEN', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'CLOSED'));
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_tickets_assignee_email ON tickets (assignee_email);
