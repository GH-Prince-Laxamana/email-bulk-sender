import threading

import pytest

from app.mail_core.engine import CampaignRunner
from app.providers.base import (
    AuthenticationFailed,
    DeliveryUncertain,
    LimitReached,
    RecipientRejected,
    TemporaryFailure,
)
from app.storage import repo
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.fakes import FakeProvider
from tests.helpers import make_campaign, recipient, statuses

EMAILS = ["a@x.com", "b@x.com", "c@x.com"]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "app.db"
    conn = connect(path)
    migrate(conn, path)
    yield path, conn
    conn.close()


def run(db, provider, campaign_id, *, stop=None, **options):
    path, conn = db
    assert repo.claim_run(conn, campaign_id)
    options.setdefault("delay_range", (0, 0))
    options.setdefault("retry_backoff", 0)
    runner = CampaignRunner(path, provider, "org@gmail.com", **options)
    return runner.run(campaign_id, stop or threading.Event())


def test_sends_to_everyone_then_finishes(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    provider = FakeProvider()
    result = run(db, provider, cid)
    assert result.state == "finished"
    assert [m["To"] for m in provider.sent] == EMAILS
    assert repo.status_counts(conn, cid)["sent"] == 3
    assert repo.get_campaign(conn, cid).locked is True
    assert provider.closes == 1


def test_a_bad_recipient_fails_alone(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS, values={"b@x.com": {}})  # no Name for b
    provider = FakeProvider()

    result = run(db, provider, cid)

    assert result.state == "draft"
    assert "preview" in result.reason.lower()
    assert provider.sent == []
    assert statuses(conn, cid) == {
        "a@x.com": "pending",
        "b@x.com": "pending",
        "c@x.com": "pending",
    }
    assert repo.get_campaign(conn, cid).locked is False


def test_provider_rejecting_one_recipient_continues_the_run(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    provider = FakeProvider({"b@x.com": [RecipientRejected("no such user")]})
    assert run(db, provider, cid).state == "finished"
    row = recipient(conn, cid, "b@x.com")
    assert row["status"] == "failed"
    assert row["error_code"] == "recipient_rejected"
    assert "no such user" in row["error_message"]
    assert [m["To"] for m in provider.sent] == ["a@x.com", "c@x.com"]


def test_temporary_error_is_retried_then_succeeds(db):
    _, conn = db
    cid = make_campaign(conn, ["a@x.com"])
    provider = FakeProvider({"a@x.com": [TemporaryFailure("try later")] * 2})
    run(db, provider, cid, max_retries=2)
    assert statuses(conn, cid) == {"a@x.com": "sent"}


def test_temporary_error_gives_up_after_the_retry_limit(db):
    _, conn = db
    cid = make_campaign(conn, ["a@x.com"])
    provider = FakeProvider({"a@x.com": [TemporaryFailure("try later")] * 3})
    run(db, provider, cid, max_retries=2)
    row = recipient(conn, cid, "a@x.com")
    assert row["status"] == "failed"
    assert row["error_code"] == "temporary_failure"


def test_login_failure_halts_before_anything_is_sent(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    provider = FakeProvider(connect_error=AuthenticationFailed("bad password"))
    result = run(db, provider, cid)
    assert result.state == "paused"
    assert "bad password" in result.reason
    assert provider.sent == []
    assert repo.status_counts(conn, cid)["pending"] == 3
    assert repo.get_campaign(conn, cid).locked is False


def test_run_level_error_halts_and_the_run_can_be_resumed(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    first = FakeProvider({"b@x.com": [LimitReached("daily limit")]})
    result = run(db, first, cid)
    assert result.state == "paused"
    assert "daily limit" in result.reason
    # b was not accepted by Gmail, so it goes back to pending, not failed
    assert statuses(conn, cid) == {
        "a@x.com": "sent",
        "b@x.com": "pending",
        "c@x.com": "pending",
    }

    second = FakeProvider()
    assert run(db, second, cid).state == "finished"
    assert [m["To"] for m in second.sent] == ["b@x.com", "c@x.com"]


def test_uncertain_delivery_is_flagged_and_never_retried(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    provider = FakeProvider({"b@x.com": [DeliveryUncertain("connection dropped")]})
    assert run(db, provider, cid).state == "finished"
    assert statuses(conn, cid) == {
        "a@x.com": "sent",
        "b@x.com": "interrupted",
        "c@x.com": "sent",
    }
    assert [m["To"] for m in provider.sent] == ["a@x.com", "c@x.com"]


def test_stop_pauses_after_the_current_email_and_resumes(db):
    _, conn = db
    cid = make_campaign(conn, ["a@x.com", "b@x.com", "c@x.com", "d@x.com", "e@x.com"])
    stop = threading.Event()

    class StopAfterTwo(FakeProvider):
        def send(self, message):
            super().send(message)
            if len(self.sent) == 2:
                stop.set()

    first = StopAfterTwo()
    result = run(db, first, cid, stop=stop)
    assert result.state == "paused"
    assert len(first.sent) == 2
    assert repo.status_counts(conn, cid)["pending"] == 3

    second = FakeProvider()
    assert run(db, second, cid).state == "finished"
    assert [m["To"] for m in second.sent] == ["c@x.com", "d@x.com", "e@x.com"]


def test_preflight_sends_nothing_when_an_attachment_vanished(db, tmp_path):
    _, conn = db
    flyer = tmp_path / "flyer.pdf"
    flyer.write_bytes(b"x")
    cid = make_campaign(conn, EMAILS, rules=[{"path": str(flyer)}])
    flyer.unlink()
    provider = FakeProvider()
    result = run(db, provider, cid)
    assert result.state == "draft"
    assert "preview" in result.reason.lower()
    assert provider.sent == []
    assert repo.get_campaign(conn, cid).locked is False


def test_unexpected_error_pauses_and_flags_the_inflight_recipient(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    provider = FakeProvider({"a@x.com": [RuntimeError("boom")]})
    result = run(db, provider, cid)
    assert result.state == "paused"
    assert "boom" in result.reason
    row = recipient(conn, cid, "a@x.com")
    assert row["status"] == "interrupted"
    assert row["error_code"] == "unexpected_error"
    assert repo.get_campaign(conn, cid).state == "paused"


def test_only_one_campaign_can_run_at_a_time(db):
    _, conn = db
    one = make_campaign(conn, ["a@x.com"])
    two = make_campaign(conn, ["b@x.com"])
    draft = make_campaign(conn, ["c@x.com"], state="draft")
    assert repo.claim_run(conn, draft) is False
    assert repo.claim_run(conn, one) is True
    assert repo.claim_run(conn, two) is False
    assert repo.claim_run(conn, one) is False


def test_recover_after_crash_flags_stuck_sends_and_pauses_runs(db):
    _, conn = db
    cid = make_campaign(conn, EMAILS)
    repo.claim_run(conn, cid)
    conn.execute("UPDATE recipients SET status = 'sending' WHERE email = 'b@x.com'")
    assert repo.recover_after_crash(conn) == (1, 1)
    assert statuses(conn, cid)["b@x.com"] == "interrupted"
    assert repo.get_campaign(conn, cid).state == "paused"
