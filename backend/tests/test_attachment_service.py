from __future__ import annotations

import pytest
from pathlib import Path

from app.services.attachments import AttachmentService, AttachmentError
from app.storage import repo
from app.storage.db import connect
from app.storage.migrations import migrate

@pytest.fixture
def db(tmp_path):
    path = tmp_path / "app.db"
    conn = connect(path)
    migrate(conn, path)

    campaign_id = repo.create_campaign(
        conn,
        name="Attachments",
    )

    yield conn, campaign_id
    conn.close()

def test_list_attachments_empty(db):
    conn, campaign_id = db
    service = AttachmentService(conn)
    assert service.list(campaign_id) == []

def test_replace_fixed_attachment(db):
    conn, campaign_id = db
    service = AttachmentService(conn)
    rules = [{"path": "/tmp/test.pdf", "folder": None, "filename_template": None}]
    result = service.replace(campaign_id, rules)
    assert len(result) == 1
    assert result[0]["path"] == "/tmp/test.pdf"

def test_replace_templated_attachment(db):
    conn, campaign_id = db
    service = AttachmentService(conn)
    rules = [{"path": None, "folder": "/tmp", "filename_template": "{email}.pdf"}]
    result = service.replace(campaign_id, rules)
    assert len(result) == 1
    assert result[0]["folder"] == "/tmp"
    assert result[0]["filename_template"] == "{email}.pdf"

def test_invalid_attachment_rule(db):
    conn, campaign_id = db
    service = AttachmentService(conn)
    rules = [{"path": "/tmp/test.pdf", "folder": "/tmp", "filename_template": "{email}.pdf"}]
    with pytest.raises(AttachmentError) as exc_info:
        service.replace(campaign_id, rules)
    assert exc_info.value.code == "invalid_attachment_rule"

def test_check_path_valid(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.touch()
    
    result = AttachmentService.check_path(str(file_path))
    
    assert result["exists"] is True
    assert result["is_file"] is True

def test_replace_on_locked_campaign(db):
    conn, campaign_id = db
    conn.execute(
        "UPDATE campaigns SET locked = 1 WHERE id = ?",
        (campaign_id,),
    )

    service = AttachmentService(conn)

    with pytest.raises(AttachmentError) as exc_info:
        service.replace(campaign_id, [])

    assert exc_info.value.code == "campaign_locked"
