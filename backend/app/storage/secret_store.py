from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

import keyring
import keyring.errors

APP_NAME = "bulkmailer"  # keyring service name; rename to match your app


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeyringSecretStore:
    def get(self, name: str) -> str | None:
        return keyring.get_password(APP_NAME, name)

    def set(self, name: str, value: str) -> None:
        keyring.set_password(APP_NAME, name, value)

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(APP_NAME, name)
        except keyring.errors.PasswordDeleteError:
            pass


class FileSecretStore:
    """Fallback when no OS keyring exists. Owner-only file, written atomically."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, str]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # mkstemp creates the file owner-only (0600) on POSIX systems.
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".secrets-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, name: str) -> str | None:
        return self._load().get(name)

    def set(self, name: str, value: str) -> None:
        data = self._load()
        data[name] = value
        self._save(data)

    def delete(self, name: str) -> None:
        data = self._load()
        if data.pop(name, None) is not None:
            self._save(data)


def default_secret_store(data_dir: str | Path) -> SecretStore:
    """OS keyring if it genuinely works here, otherwise the file fallback."""
    probe = "__probe__"
    try:
        keyring.set_password(APP_NAME, probe, "1")
        works = keyring.get_password(APP_NAME, probe) == "1"
    except Exception:
        works = False
    else:
        try:
            keyring.delete_password(APP_NAME, probe)
        except Exception:
            pass
    if works:
        return KeyringSecretStore()
    return FileSecretStore(Path(data_dir) / "secrets.json")
