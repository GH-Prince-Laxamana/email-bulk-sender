from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from .db import now_iso, transaction

_STATUSES = ("pending", "sending", "sent", "failed", "interrupted")


@dataclass(frozen=True)
class CampaignRow:
    id: int
    name: str
    subject: str
    body_html: str
    state: str
    locked: bool
    halt_reason: str | None


@dataclass(frozen=True)
class RecipientRow:
    id: int
    email: str
    values: dict[str, Any]
    status: str
    attempts: int


def _recipient(row: sqlite3.Row) -> RecipientRow:
    return RecipientRow(
        row["id"],
        row["email"],
        json.loads(row["values_json"]),
        row["status"],
        row["attempts"],
    )


def get_campaign(conn: sqlite3.Connection, campaign_id: int) -> CampaignRow | None:
    row = conn.execute(
        "SELECT id, name, subject, body_html, state, locked, halt_reason "
        "FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()
    if row is None:
        return None
    return CampaignRow(
        row["id"],
        row["name"],
        row["subject"],
        row["body_html"],
        row["state"],
        bool(row["locked"]),
        row["halt_reason"],
    )


def get_attachment_rules(conn: sqlite3.Connection, campaign_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT path, folder, filename_template FROM attachment_rules "
        "WHERE campaign_id = ? ORDER BY position, id",
        (campaign_id,),
    )
    return [dict(row) for row in rows]


def claim_run(conn: sqlite3.Connection, campaign_id: int) -> bool:
    """Atomically move a campaign to 'running'. False if not allowed right now."""
    cur = conn.execute(
        "UPDATE campaigns SET state = 'running', halt_reason = NULL, updated_at = ? "
        "WHERE id = ? AND state IN ('previewed', 'paused') "
        "AND NOT EXISTS (SELECT 1 FROM campaigns WHERE state = 'running')",
        (now_iso(), campaign_id),
    )
    return cur.rowcount == 1


def set_state(
    conn: sqlite3.Connection,
    campaign_id: int,
    state: str,
    halt_reason: str | None = None,
) -> None:
    conn.execute(
        "UPDATE campaigns SET state = ?, halt_reason = ?, updated_at = ? WHERE id = ?",
        (state, halt_reason, now_iso(), campaign_id),
    )


def pending_recipients(
    conn: sqlite3.Connection, campaign_id: int
) -> list[RecipientRow]:
    rows = conn.execute(
        "SELECT id, email, values_json, status, attempts FROM recipients "
        "WHERE campaign_id = ? AND status = 'pending' ORDER BY position, id",
        (campaign_id,),
    )
    return [_recipient(row) for row in rows]


def next_pending(conn: sqlite3.Connection, campaign_id: int) -> RecipientRow | None:
    row = conn.execute(
        "SELECT id, email, values_json, status, attempts FROM recipients "
        "WHERE campaign_id = ? AND status = 'pending' ORDER BY position, id LIMIT 1",
        (campaign_id,),
    ).fetchone()
    return None if row is None else _recipient(row)


def has_pending(conn: sqlite3.Connection, campaign_id: int) -> bool:
    return next_pending(conn, campaign_id) is not None


def mark_sending(conn: sqlite3.Connection, recipient_id: int) -> None:
    """Also locks the campaign: from the first send on, its content is frozen."""
    with transaction(conn):
        conn.execute(
            "UPDATE recipients SET status = 'sending', attempts = attempts + 1, "
            "error_code = NULL, error_message = NULL WHERE id = ?",
            (recipient_id,),
        )
        conn.execute(
            "UPDATE campaigns SET locked = 1 "
            "WHERE id = (SELECT campaign_id FROM recipients WHERE id = ?)",
            (recipient_id,),
        )


def mark_sent(conn: sqlite3.Connection, recipient_id: int) -> None:
    conn.execute(
        "UPDATE recipients SET status = 'sent', sent_at = ?, "
        "error_code = NULL, error_message = NULL WHERE id = ?",
        (now_iso(), recipient_id),
    )


def mark_failed(
    conn: sqlite3.Connection, recipient_id: int, code: str, message: str
) -> None:
    conn.execute(
        "UPDATE recipients SET status = 'failed', error_code = ?, error_message = ? WHERE id = ?",
        (code, message, recipient_id),
    )


def mark_interrupted(
    conn: sqlite3.Connection, recipient_id: int, code: str, message: str
) -> None:
    conn.execute(
        "UPDATE recipients SET status = 'interrupted', error_code = ?, error_message = ? "
        "WHERE id = ?",
        (code, message, recipient_id),
    )


def mark_pending(conn: sqlite3.Connection, recipient_id: int) -> None:
    conn.execute(
        "UPDATE recipients SET status = 'pending' WHERE id = ?", (recipient_id,)
    )


def status_counts(conn: sqlite3.Connection, campaign_id: int) -> dict[str, int]:
    counts = {status: 0 for status in _STATUSES}
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM recipients WHERE campaign_id = ? GROUP BY status",
        (campaign_id,),
    )
    for row in rows:
        counts[row["status"]] = row["n"]
    return counts


def recover_after_crash(conn: sqlite3.Connection) -> tuple[int, int]:
    """Run once at startup. Returns (recipients flagged, campaigns paused)."""
    with transaction(conn):
        stuck = conn.execute(
            "UPDATE recipients SET status = 'interrupted', error_code = 'app_stopped', "
            "error_message = 'The app stopped while this email was being sent. "
            "It may or may not have been delivered.' WHERE status = 'sending'"
        ).rowcount
        paused = conn.execute(
            "UPDATE campaigns SET state = 'paused', updated_at = ?, "
            "halt_reason = 'The app stopped during a run.' WHERE state = 'running'",
            (now_iso(),),
        ).rowcount
    return stuck, paused


def list_campaigns(conn: sqlite3.Connection) -> list[CampaignRow]:
    rows = conn.execute(
        "SELECT id, name, subject, body_html, state, locked, halt_reason "
        "FROM campaigns ORDER BY created_at DESC, id DESC"
    )
    return [
        CampaignRow(
            row["id"],
            row["name"],
            row["subject"],
            row["body_html"],
            row["state"],
            bool(row["locked"]),
            row["halt_reason"],
        )
        for row in rows
    ]


def create_campaign(
    conn: sqlite3.Connection,
    *,
    name: str,
    subject: str = "",
    body_html: str = "",
    variables: list[str] | None = None,
) -> int:
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO campaigns "
        "(name, subject, body_html, variables, state, locked, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'draft', 0, ?, ?)",
        (
            name,
            subject,
            body_html,
            json.dumps(variables or [], ensure_ascii=False),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def update_campaign_content(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    name: str,
    subject: str,
    body_html: str,
    variables: list[str],
) -> None:
    conn.execute(
        "UPDATE campaigns SET "
        "name = ?, subject = ?, body_html = ?, variables = ?, updated_at = ? "
        "WHERE id = ?",
        (
            name,
            subject,
            body_html,
            json.dumps(variables, ensure_ascii=False),
            now_iso(),
            campaign_id,
        ),
    )


def duplicate_campaign(
    conn: sqlite3.Connection,
    campaign_id: int,
    *,
    new_name: str,
    carry_recipients: bool = False,
) -> int:
    row = conn.execute(
        "SELECT name, subject, body_html, variables " "FROM campaigns WHERE id = ?",
        (campaign_id,),
    ).fetchone()

    if row is None:
        raise ValueError("Campaign not found")

    now = now_iso()

    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO campaigns "
            "(name, subject, body_html, variables, state, locked, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'draft', 0, ?, ?)",
            (
                new_name,
                row["subject"],
                row["body_html"],
                row["variables"],
                now,
                now,
            ),
        )
        new_id = int(cur.lastrowid)

        conn.execute(
            "INSERT INTO attachment_rules "
            "(campaign_id, path, folder, filename_template, position) "
            "SELECT ?, path, folder, filename_template, position "
            "FROM attachment_rules WHERE campaign_id = ?",
            (new_id, campaign_id),
        )

        if carry_recipients:
            conn.execute(
                "INSERT INTO recipients "
                "(campaign_id, email, values_json, status, attempts, position) "
                "SELECT ?, email, values_json, 'pending', 0, position "
                "FROM recipients WHERE campaign_id = ? "
                "ORDER BY position, id",
                (new_id, campaign_id),
            )

    return new_id


@dataclass(frozen=True)
class RecipientDetailRow:
    id: int
    email: str
    values: dict[str, Any]
    status: str
    error_code: str | None
    error_message: str | None
    attempts: int
    sent_at: str | None
    position: int


def get_recipient(
    conn: sqlite3.Connection,
    recipient_id: int,
) -> RecipientDetailRow | None:
    row = conn.execute(
        "SELECT id, email, values_json, status, error_code, error_message, "
        "attempts, sent_at, position "
        "FROM recipients WHERE id = ?",
        (recipient_id,),
    ).fetchone()

    if row is None:
        return None

    return RecipientDetailRow(
        id=row["id"],
        email=row["email"],
        values=json.loads(row["values_json"]),
        status=row["status"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        attempts=row["attempts"],
        sent_at=row["sent_at"],
        position=row["position"],
    )


def list_recipients(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> list[RecipientDetailRow]:
    rows = conn.execute(
        "SELECT id, email, values_json, status, error_code, error_message, "
        "attempts, sent_at, position "
        "FROM recipients "
        "WHERE campaign_id = ? "
        "ORDER BY position, id",
        (campaign_id,),
    )

    return [
        RecipientDetailRow(
            id=row["id"],
            email=row["email"],
            values=json.loads(row["values_json"]),
            status=row["status"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            attempts=row["attempts"],
            sent_at=row["sent_at"],
            position=row["position"],
        )
        for row in rows
    ]


def insert_recipients(
    conn: sqlite3.Connection,
    campaign_id: int,
    recipients: list[tuple[str, dict[str, Any]]],
) -> int:
    if not recipients:
        return 0

    row = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS next_position "
        "FROM recipients WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    next_position = row["next_position"]

    inserted = 0

    for offset, (email, values) in enumerate(recipients):
        cur = conn.execute(
            "INSERT OR IGNORE INTO recipients "
            "(campaign_id, email, values_json, status, attempts, position) "
            "VALUES (?, ?, ?, 'pending', 0, ?)",
            (
                campaign_id,
                email,
                json.dumps(values, ensure_ascii=False),
                next_position + offset,
            ),
        )
        inserted += cur.rowcount

    return inserted


def retry_failed(
    conn: sqlite3.Connection,
    campaign_id: int,
) -> int:
    return conn.execute(
        "UPDATE recipients SET status = 'pending', "
        "error_code = NULL, error_message = NULL "
        "WHERE campaign_id = ? AND status = 'failed'",
        (campaign_id,),
    ).rowcount


def resolve_interrupted(
    conn: sqlite3.Connection,
    recipient_id: int,
    *,
    retry: bool,
) -> None:
    if retry:
        conn.execute(
            "UPDATE recipients SET status = 'pending', "
            "error_code = NULL, error_message = NULL "
            "WHERE id = ? AND status = 'interrupted'",
            (recipient_id,),
        )
        return

    conn.execute(
        "UPDATE recipients SET status = 'sent', sent_at = ?, "
        "error_code = NULL, error_message = NULL "
        "WHERE id = ? AND status = 'interrupted'",
        (now_iso(), recipient_id),
    )


def replace_attachment_rules(
    conn: sqlite3.Connection,
    campaign_id: int,
    rules: list[dict[str, Any]],
) -> None:
    with transaction(conn):
        conn.execute(
            "DELETE FROM attachment_rules WHERE campaign_id = ?",
            (campaign_id,),
        )

        for position, rule in enumerate(rules):
            conn.execute(
                "INSERT INTO attachment_rules "
                "(campaign_id, path, folder, filename_template, position) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    campaign_id,
                    rule.get("path"),
                    rule.get("folder"),
                    rule.get("filename_template"),
                    position,
                ),
            )
