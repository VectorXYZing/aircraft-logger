import os
import importlib

import airlogger.config as config


def test_missing_smtp():
    # Temporarily clear env vars
    for k in ["SMTP_SERVER", "EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_TO"]:
        if k in os.environ:
            del os.environ[k]
    importlib.reload(config)
    ok, missing = config.validate_smtp_config()
    assert not ok
    assert set(missing) == {"SMTP_SERVER", "EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_TO"}


def test_partial_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.setenv("EMAIL_USER", "a@example.com")
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    importlib.reload(config)
    ok, missing = config.validate_smtp_config()
    assert not ok
    assert "EMAIL_PASSWORD" in missing
