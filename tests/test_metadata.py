import airlogger.metadata as metadata
import requests


class DummyResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


def test_fetch_metadata_opensky_success(monkeypatch):
    def fake_get(url, timeout=5):
        return DummyResponse(
            200,
            {
                "registration": "N12345",
                "model": "Cessna 172",
                "manufacturerName": "Cessna",
                "operator": "Acme Air",
                "operatorCallsign": "ACME123",
                "timestamp": 1600000000000,
                "icao24": "ab1234",
            },
        )

    monkeypatch.setattr("requests.get", fake_get)

    reg, model, operator, callsign = metadata.fetch_metadata("ab1234")
    assert reg == "N12345"
    assert "Cessna" in model
    assert operator == "Acme Air"
    assert callsign == "ACME123"


def test_fetch_metadata_non_200(monkeypatch):
    def fake_get(url, timeout=5):
        return DummyResponse(404, None)

    monkeypatch.setattr("requests.get", fake_get)

    reg, model, operator, callsign = metadata.fetch_metadata("deadbe")
    assert reg == ""
    assert model == ""
    assert operator == ""
    assert callsign == ""


def test_fetch_metadata_cache(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, timeout=5):
        call_count["n"] += 1
        return DummyResponse(200, {"registration": "N1"})

    monkeypatch.setattr("requests.get", fake_get)
    metadata.clear_cache()

    r1 = metadata.fetch_metadata("ab0001")
    r2 = metadata.fetch_metadata("ab0001")
    # second call should be served from cache
    assert call_count["n"] == 1
    assert r1[0] == r2[0]


def test_fetch_metadata_retries(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, timeout=5):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.RequestException("network")
        return DummyResponse(200, {"registration": "N_RETRY"})

    monkeypatch.setattr("requests.get", fake_get)
    metadata.clear_cache()

    reg, model, operator, callsign = metadata.fetch_metadata("ab9999")
    assert reg == "N_RETRY"
    assert calls["n"] >= 3
