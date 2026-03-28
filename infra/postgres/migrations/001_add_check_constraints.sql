-- Apply check constraints on existing databases (idempotent).
-- Safe to run multiple times.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'tickets_status_check'
  ) THEN
    ALTER TABLE tickets
      ADD CONSTRAINT tickets_status_check
      CHECK (status IN ('OPEN', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'CLOSED'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'tickets_priority_check'
  ) THEN
    ALTER TABLE tickets
      ADD CONSTRAINT tickets_priority_check
      CHECK (priority IN ('P1', 'P2', 'P3', 'P4'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ticket_events_event_type_check'
  ) THEN
    ALTER TABLE ticket_events
      ADD CONSTRAINT ticket_events_event_type_check
      CHECK (event_type IN ('CREATED', 'EMAIL_SENT', 'CLOSED', 'NOTE'));
  END IF;
END $$;
