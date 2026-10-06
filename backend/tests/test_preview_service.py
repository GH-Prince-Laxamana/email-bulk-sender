from __future__ import annotations

import pytest
from app.services.preview import PreviewService, PreviewError
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
        name="Test",
        subject="Hello {{name}}",
        body_html="<p>Welcome {{name}}</p>",
        variables=["name"]
    )
    
    repo.insert_recipients(
        conn,
        campaign_id,
        [("test@example.com", {"name": "Alice"})]
    )

    yield conn, campaign_id
    conn.close()

def test_preview_campaign_returns_previews(db):
    conn, campaign_id = db
    service = PreviewService(conn, sender="sender@example.com")
    
    result = service.preview_campaign(campaign_id)
    assert result["clean"] is True
    assert result["total"] == 1
    assert result["valid"] == 1
    assert len(result["previews"]) == 1
    preview = result["previews"][0]
    assert preview["subject"] == "Hello Alice"
    assert "Welcome Alice" in preview["html"]

def test_preview_campaign_state_transitions_to_previewed(db):
    conn, campaign_id = db
    service = PreviewService(conn, sender="sender@example.com")
    
    result = service.preview_campaign(campaign_id)
    assert result["state"] == "previewed"

def test_preview_campaign_empty_recipients(db):
    conn, campaign_id = db
    conn.execute("DELETE FROM recipients")
    
    service = PreviewService(conn, sender="sender@example.com")
    result = service.preview_campaign(campaign_id)
    assert result["total"] == 0
    assert result["valid"] == 0
