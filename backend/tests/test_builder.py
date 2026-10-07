import pytest

from app.mail_core import builder
from app.mail_core.builder import (
    AttachmentRule,
    BuildError,
    Content,
    Recipient,
    build_message,
)

SENDER = "org@gmail.com"
CONTENT = Content(subject="Hello {{Name}}", body_html="<p>Hi <b>{{Name}}</b></p>")


def person(email="ana@example.com", **values):
    return Recipient(email, {"Name": "Ana", **values})


def html_of(msg):
    return msg.get_body(("html",)).get_content()


def test_builds_text_and_html_versions():
    msg = build_message(SENDER, CONTENT, [], person())
    assert msg["Subject"] == "Hello Ana"
    assert msg["To"] == "ana@example.com"
    assert "Hi Ana" in msg.get_body(("plain",)).get_content()
    assert "<b>Ana</b>" in html_of(msg)


def test_body_values_can_contain_html_markup():
    msg = build_message(
        SENDER,
        CONTENT,
        [],
        person(Name='<a href="https://example.com">Ana</a>'),
    )
    assert '<b><a href="https://example.com">Ana</a></b>' in html_of(msg)
    assert "Ana" in msg.get_body(("plain",)).get_content()


@pytest.mark.parametrize(
    "bad",
    ["", "no-at-sign", "a b@example.com", "a@example", "a@example.com\nBcc: e@x.com"],
)
def test_invalid_email_is_rejected(bad):
    with pytest.raises(BuildError) as err:
        build_message(SENDER, CONTENT, [], person(email=bad))
    assert err.value.code == "invalid_email"


def test_missing_variable_is_classified():
    with pytest.raises(BuildError) as err:
        build_message(SENDER, CONTENT, [], Recipient("a@example.com", {}))
    assert err.value.code == "missing_variable"


def test_fixed_attachment(tmp_path):
    flyer = tmp_path / "flyer.pdf"
    flyer.write_bytes(b"%PDF-1.4 data")
    msg = build_message(SENDER, CONTENT, [AttachmentRule(path=str(flyer))], person())
    assert [p.get_filename() for p in msg.iter_attachments()] == ["flyer.pdf"]


def test_templated_attachment(tmp_path):
    (tmp_path / "Ana.pdf").write_bytes(b"x")
    rule = AttachmentRule(folder=str(tmp_path), filename_template="{{Name}}.pdf")
    msg = build_message(SENDER, CONTENT, [rule], person())
    assert [p.get_filename() for p in msg.iter_attachments()] == ["Ana.pdf"]


def test_missing_attachment_file(tmp_path):
    rule = AttachmentRule(folder=str(tmp_path), filename_template="{{Name}}.pdf")
    with pytest.raises(BuildError) as err:
        build_message(SENDER, CONTENT, [rule], person())
    assert err.value.code == "attachment_missing"


def test_hostile_value_in_filename_is_rejected(tmp_path):
    rule = AttachmentRule(folder=str(tmp_path), filename_template="{{Name}}.pdf")
    with pytest.raises(BuildError) as err:
        build_message(SENDER, CONTENT, [rule], person(Name="../secret"))
    assert err.value.code == "attachment_unsafe"


@pytest.mark.parametrize("escape", ["../secret.txt", "ABSOLUTE"])
def test_template_escaping_the_folder_is_rejected(tmp_path, escape):
    folder = tmp_path / "certs"
    folder.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    template = str(secret) if escape == "ABSOLUTE" else escape
    rule = AttachmentRule(folder=str(folder), filename_template=template)
    with pytest.raises(BuildError) as err:
        build_message(SENDER, CONTENT, [rule], person())
    assert err.value.code == "attachment_unsafe"


def test_dry_run_validates_but_attaches_nothing(tmp_path):
    flyer = tmp_path / "flyer.pdf"
    flyer.write_bytes(b"data")
    rule = AttachmentRule(path=str(flyer))
    msg = build_message(SENDER, CONTENT, [rule], person(), attach_files=False)
    assert list(msg.iter_attachments()) == []

    missing = AttachmentRule(path=str(tmp_path / "nope.pdf"))
    with pytest.raises(BuildError):
        build_message(SENDER, CONTENT, [missing], person(), attach_files=False)


def test_total_attachment_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "MAX_TOTAL_ATTACHMENT_BYTES", 5)
    big = tmp_path / "big.bin"
    big.write_bytes(b"123456")
    with pytest.raises(BuildError) as err:
        build_message(SENDER, CONTENT, [AttachmentRule(path=str(big))], person())
    assert err.value.code == "attachment_too_large"
