"""P20: 배경지도 키는 빌드에 넣지 않고 /api/v1/map/config로 실행 중에 받는다."""
from fastapi.testclient import TestClient

from api.index import app
from core.live import http

client = TestClient(app)


def _env(monkeypatch, **kv):
    monkeypatch.setattr(http, "_ENV_LOADED", True)      # 로컬 .env가 빈 값을 다시 채우지 않게
    for k, v in kv.items():
        monkeypatch.setenv(k, v)


def test_config_returns_browser_key(monkeypatch):
    _env(monkeypatch, VITE_VWORLD_KEY="test-browser-key", VWORLD_API_KEY="test-server-key")
    r = client.get("/api/v1/map/config")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert r.json() == {"basemap": {"key": "test-browser-key", "configured": True}}
    assert "test-server-key" not in r.text


def test_config_without_browser_key_does_not_fall_back_to_server_key(monkeypatch):
    _env(monkeypatch, VITE_VWORLD_KEY="", VWORLD_API_KEY="test-server-key")
    r = client.get("/api/v1/map/config")
    assert r.json() == {"basemap": {"key": None, "configured": False}}
    assert "test-server-key" not in r.text


def test_health_has_patched_fields_and_no_browser_key(monkeypatch):
    _env(monkeypatch, VITE_VWORLD_KEY="test-browser-key")
    h = client.get("/api/v1/health")
    assert h.status_code == 200
    body = h.json()
    assert "patched_at" in body and "patched_by" in body
    assert "test-browser-key" not in h.text
