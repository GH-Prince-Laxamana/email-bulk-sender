import os

import keyring
import keyring.errors
import pytest

from app.storage.secret_store import (
    FileSecretStore,
    KeyringSecretStore,
    default_secret_store,
)


def test_file_store_round_trip(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")
    assert store.get("gmail") is None
    store.set("gmail", "pw-1")
    assert store.get("gmail") == "pw-1"


def test_file_store_overwrite_and_delete(tmp_path):
    store = FileSecretStore(tmp_path / "secrets.json")
    store.set("gmail", "pw-1")
    store.set("gmail", "pw-2")
    assert store.get("gmail") == "pw-2"
    store.delete("gmail")
    assert store.get("gmail") is None


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_file_store_is_owner_only(tmp_path):
    path = tmp_path / "secrets.json"
    FileSecretStore(path).set("gmail", "pw")
    assert path.stat().st_mode & 0o077 == 0


def test_falls_back_to_file_when_keyring_is_unusable(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise keyring.errors.KeyringError("no backend")

    monkeypatch.setattr(keyring, "set_password", boom)
    assert isinstance(default_secret_store(tmp_path), FileSecretStore)


def test_uses_keyring_when_it_works(tmp_path, monkeypatch):
    memory = {}
    monkeypatch.setattr(
        keyring, "set_password", lambda s, n, v: memory.__setitem__((s, n), v)
    )
    monkeypatch.setattr(keyring, "get_password", lambda s, n: memory.get((s, n)))
    monkeypatch.setattr(
        keyring, "delete_password", lambda s, n: memory.pop((s, n), None)
    )
    store = default_secret_store(tmp_path)
    assert isinstance(store, KeyringSecretStore)
    store.set("gmail", "pw")
    assert store.get("gmail") == "pw"
