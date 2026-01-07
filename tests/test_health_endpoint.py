import importlib
import json
import time
from datetime import datetime

import pytest


def test_health_endpoint(monkeypatch, tmp_path):
    # Set up env and reload config/dashboard
    monkeypatch.setenv("AIRLOGGER_LOG_DIR", str(tmp_path))
    import airlogger.config as config
    importlib.reload(config)

    # Write heartbeat with recent timestamp
    hb = {"timestamp": time.time(), "iso": datetime.utcfromtimestamp(time.time()).isoformat()+"Z"}
    (tmp_path / "heartbeat.json").write_text(json.dumps(hb), encoding="utf-8")

    import dashboard
    importlib.reload(dashboard)
    client = dashboard.app.test_client()
    rv = client.get('/health')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['healthy'] is True

    # Simulate old heartbeat
    old_hb = {"timestamp": time.time() - 10000, "iso": datetime.utcfromtimestamp(time.time()).isoformat()+"Z"}
    (tmp_path / "heartbeat.json").write_text(json.dumps(old_hb), encoding="utf-8")
    rv2 = client.get('/health')
    assert rv2.status_code == 503
    data2 = rv2.get_json()
    assert data2['healthy'] is False
