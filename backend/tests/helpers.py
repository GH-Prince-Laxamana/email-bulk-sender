import json

from app.storage.db import now_iso


def make_campaign(
    conn,
    emails,
    *,
    subject="Hi {{Name}}",
    body="<p>Hello {{Name}}</p>",
    state="previewed",
    values=None,
    rules=(),
):
    values = values or {}
    cur = conn.execute(
        "INSERT INTO campaigns(name, subject, body_html, state, created_at, updated_at) "
        "VALUES ('test', ?, ?, ?, ?, ?)",
        (subject, body, state, now_iso(), now_iso()),
    )
    campaign_id = cur.lastrowid
    for position, email in enumerate(emails):
        data = values.get(email, {"Name": email.split("@")[0].title()})
        conn.execute(
            "INSERT INTO recipients(campaign_id, email, values_json, position) "
            "VALUES (?, ?, ?, ?)",
            (campaign_id, email, json.dumps(data), position),
        )
    for position, rule in enumerate(rules):
        conn.execute(
            "INSERT INTO attachment_rules(campaign_id, path, folder, filename_template, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                campaign_id,
                rule.get("path"),
                rule.get("folder"),
                rule.get("filename_template"),
                position,
            ),
        )
    return campaign_id


def statuses(conn, campaign_id):
    rows = conn.execute(
        "SELECT email, status FROM recipients WHERE campaign_id = ?", (campaign_id,)
    )
    return {row["email"]: row["status"] for row in rows}


def recipient(conn, campaign_id, email):
    return conn.execute(
        "SELECT * FROM recipients WHERE campaign_id = ? AND email = ?",
        (campaign_id, email),
    ).fetchone()
