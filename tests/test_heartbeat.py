import os
import json
import time
from datetime import datetime
import tempfile

import os
import importlib

# set env before importing the dashboard module so it picks up LOG_DIR

def test_dashboard_heartbeat(monkeypatch, tmp_path):
    monkeypatch.setenv("AIRLOGGER_LOG_DIR", str(tmp_path))
    # reload config and dashboard after setting env
    import airlogger.config as config
    importlib.reload(config)

    # Create a fake heartbeat file with current timestamp
    hb = {
        "timestamp": time.time(),
        "iso": datetime.utcfromtimestamp(time.time()).isoformat() + "Z",
        "pid": 12345,
        "cache_size": 0,
    }
    hb_file = tmp_path / "heartbeat.json"
    hb_file.write_text(json.dumps(hb), encoding="utf-8")

    # Now import (or reload) the dashboard module so it picks up the env changes
    import dashboard
    importlib.reload(dashboard)

    client = dashboard.app.test_client()
    rv = client.get('/status')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'heartbeat' in data
    assert data['heartbeat']['healthy'] is True
