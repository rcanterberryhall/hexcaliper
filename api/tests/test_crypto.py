"""
test_crypto.py — Unit tests for crypto.py (Fernet at-rest encryption).
"""
import pytest


@pytest.fixture(autouse=True)
def reset_fernet(monkeypatch):
    """Reset the module-level Fernet singleton before every test."""
    import crypto
    monkeypatch.setattr(crypto, "_fernet", None)


# ── Pass-through mode (no key) ────────────────────────────────────────────────

def test_encrypt_passthrough_no_key(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "")
    assert crypto.encrypt_secret("my-password") == "my-password"


def test_decrypt_passthrough_no_key(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "")
    assert crypto.decrypt_secret("some-plain-text") == "some-plain-text"


def test_empty_string_passthrough(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "test-key-value")
    assert crypto.encrypt_secret("") == ""
    assert crypto.decrypt_secret("") == ""


# ── Encrypt / decrypt roundtrip ───────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "test-key-value")
    plaintext = "super-secret-api-key-12345"
    token = crypto.encrypt_secret(plaintext)
    assert token != plaintext
    assert token.startswith("gAAAAA")
    assert crypto.decrypt_secret(token) == plaintext


def test_different_keys_produce_different_tokens(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "key-one")
    t1 = crypto.encrypt_secret("hello")
    crypto._fernet = None
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "key-two")
    t2 = crypto.encrypt_secret("hello")
    assert t1 != t2


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_already_encrypted_not_double_encrypted(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "test-key-value")
    token = crypto.encrypt_secret("plain")
    token2 = crypto.encrypt_secret(token)
    assert token == token2


def test_plaintext_returned_unchanged_without_key(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "")
    # Even if value looks encrypted, return as-is when no key.
    fake_token = "gAAAAA_not_really_encrypted"
    assert crypto.decrypt_secret(fake_token) == fake_token


# ── Config dict helpers ───────────────────────────────────────────────────────

def test_encrypt_config_encrypts_secret_fields(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "cfg-key")
    cfg = {"host": "mfiles.local", "password": "s3cr3t", "port": 443}
    encrypted = crypto.encrypt_config(cfg)
    assert encrypted["host"] == "mfiles.local"
    assert encrypted["port"] == 443
    assert encrypted["password"].startswith("gAAAAA")


def test_decrypt_config_roundtrip(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "cfg-key")
    cfg = {"host": "sp.example.com", "client_secret": "abc123", "token": "tok"}
    roundtrip = crypto.decrypt_config(crypto.encrypt_config(cfg))
    assert roundtrip["client_secret"] == "abc123"
    assert roundtrip["token"] == "tok"
    assert roundtrip["host"] == "sp.example.com"


def test_non_secret_fields_untouched(monkeypatch):
    import config, crypto
    monkeypatch.setattr(config, "CREDENTIALS_KEY", "cfg-key")
    cfg = {"username": "admin", "host": "example.com"}
    assert crypto.encrypt_config(cfg) == cfg
