from __future__ import annotations

import re
from enum import Enum
from html import escape
from typing import Any, Mapping

# {{ Name }} or {{ Name | default text }}. No braces or pipes inside the name;
# no braces inside the default. This is deliberately NOT a template language.
_PLACEHOLDER = re.compile(r"\{\{\s*([^{}|]+?)\s*(?:\|([^{}]*))?\}\}")
_NEWLINES = re.compile(r"[\r\n]+")


class RenderMode(str, Enum):
    HTML = "html"
    TEXT = "text"
    FILENAME = "filename"


class TemplateError(ValueError):
    """Base class for anything the user can fix by editing data or templates."""


class MissingVariablesError(TemplateError):
    def __init__(self, names: list[str]):
        self.names = names
        super().__init__("Missing values for: " + ", ".join(names))


class UnsafeValueError(TemplateError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Value for '{name}' is not allowed in a file name")


def extract_variables(template: str) -> list[str]:
    """Variable names used in a template, in order of first appearance."""
    names: list[str] = []
    for match in _PLACEHOLDER.finditer(template):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return names


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sanitize(name: str, value: str, mode: RenderMode) -> str:
    if mode is RenderMode.HTML:
        return escape(value, quote=True)
    if mode is RenderMode.TEXT:
        return _NEWLINES.sub(" ", value)
    # FILENAME
    if any(ch in value for ch in "/\\\0\r\n") or ".." in value:
        raise UnsafeValueError(name)
    return value


def render(
    template: str,
    values: Mapping[str, Any],
    mode: RenderMode = RenderMode.TEXT,
) -> str:
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        value = _clean(values.get(name))
        if not value:
            if default is None:
                if name not in missing:
                    missing.append(name)
                return ""
            value = default.strip()
        return _sanitize(name, value, mode)

    result = _PLACEHOLDER.sub(replace, template)
    if missing:
        raise MissingVariablesError(missing)
    return result
