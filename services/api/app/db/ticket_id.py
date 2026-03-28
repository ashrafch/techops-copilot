from datetime import date


def next_ticket_id(conn) -> str:
    today = date.today()
    ymd = today.strftime("%Y%m%d")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ticket_sequences (day, last_seq)
            VALUES (%s, 0)
            ON CONFLICT (day) DO NOTHING
            """,
            (today,),
        )
        cur.execute("SELECT last_seq FROM ticket_sequences WHERE day = %s FOR UPDATE", (today,))
        last = cur.fetchone()[0]
        new_seq = last + 1
        cur.execute("UPDATE ticket_sequences SET last_seq = %s WHERE day = %s", (new_seq, today))

    return f"TCK-{ymd}-{new_seq:04d}"
