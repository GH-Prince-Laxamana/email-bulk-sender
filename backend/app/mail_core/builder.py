from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence

from .renderer import (
    MissingVariablesError,
    RenderMode,
    TemplateError,
    UnsafeValueError,
    render,
)

# Gmail's 25 MB limit applies to the base64-encoded message (~4/3 of raw size).
MAX_TOTAL_ATTACHMENT_BYTES = 18 * 1024 * 1024

_EMAIL = re.compile(r"[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+")


class BuildError(Exception):
    """A recipient-level, permanent failure. `code` is machine-readable."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class AttachmentRule:
    path: str | None = None  # a fixed file sent to everyone
    folder: str | None = None  # or: a folder + a filename template
    filename_template: str | None = None


@dataclass(frozen=True)
class Content:
    subject: str
    body_html: str


@dataclass(frozen=True)
class Recipient:
    email: str
    values: Mapping[str, Any] = field(default_factory=dict)


class _TextExtractor(HTMLParser):
    _BLOCKS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _render(template: str, values: Mapping[str, Any], mode: RenderMode) -> str:
    try:
        return render(template, values, mode)
    except MissingVariablesError as err:
        raise BuildError("missing_variable", str(err)) from err
    except TemplateError as err:
        raise BuildError("template_error", str(err)) from err


def resolve_attachments(
    rules: Sequence[AttachmentRule], values: Mapping[str, Any]
) -> list[Path]:
    """Turn rules into verified file paths for one recipient. Reads no file contents."""
    paths: list[Path] = []
    for rule in rules:
        if rule.path:
            candidate = Path(rule.path).expanduser().resolve()
        elif rule.folder and rule.filename_template:
            folder = Path(rule.folder).expanduser().resolve()
            try:
                name = render(rule.filename_template, values, RenderMode.FILENAME)
            except UnsafeValueError as err:
                raise BuildError("attachment_unsafe", str(err)) from err
            except MissingVariablesError as err:
                raise BuildError("missing_variable", str(err)) from err
            candidate = (folder / name).resolve()
            if not candidate.is_relative_to(folder):
                raise BuildError(
                    "attachment_unsafe",
                    f"'{name}' points outside the attachment folder",
                )
        else:
            raise BuildError("attachment_invalid", "Attachment rule is incomplete")

        if not candidate.is_file():
            raise BuildError("attachment_missing", f"File not found: {candidate}")
        paths.append(candidate)

    total = sum(p.stat().st_size for p in paths)
    if total > MAX_TOTAL_ATTACHMENT_BYTES:
        raise BuildError(
            "attachment_too_large",
            f"Attachments total {total / 1_048_576:.1f} MB, over the limit",
        )
    return paths


def build_message(
    sender: str,
    content: Content,
    rules: Sequence[AttachmentRule],
    recipient: Recipient,
    *,
    attach_files: bool = True,
) -> EmailMessage:
    address = recipient.email.strip()
    if not _EMAIL.fullmatch(address):
        raise BuildError("invalid_email", f"Invalid email address: {address!r}")

    subject = _render(content.subject, recipient.values, RenderMode.TEXT)
    html = _render(content.body_html, recipient.values, RenderMode.HTML)
    paths = resolve_attachments(rules, recipient.values)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = address
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    # Use the sender's domain so the machine's hostname never leaks into headers.
    msg["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1])
    msg.set_content(html_to_text(html))
    msg.add_alternative(html, subtype="html")

    if attach_files:
        for path in paths:
            ctype, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            msg.add_attachment(
                path.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=path.name,
            )
    return msg
