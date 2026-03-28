import json
from typing import Any, Dict, Optional

def log_event(
    conn,
    ticket_id: str,
    event_type: str,
    message: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Scrive un evento su ticket_events usando la stessa connessione/transaction.
    La tabella ha colonne: ticket_id, event_type, message, meta, created_at
    """
    if meta is None:
        meta = {}

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ticket_events (ticket_id, event_type, message, meta)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (ticket_id, event_type, message, json.dumps(meta)),
        )
