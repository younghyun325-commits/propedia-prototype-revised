"""tests/_target.py — 점검 대상 판정·키 가림·스크린샷 이름 (P20)"""
import _target


def test_is_remote():
    assert not _target.is_remote("http://localhost:8000")
    assert not _target.is_remote("http://127.0.0.1:8000/")
    assert _target.is_remote("https://propedia-prototype.vercel.app")


def test_shot_name():
    assert _target.shot_name("map_02a.png", False) == "map_02a.png"
    assert _target.shot_name("map_02a.png", True) == "prod_map_02a.png"


def test_mask_text_tile_urls_and_env(monkeypatch):
    monkeypatch.setattr(_target, "_ENV", {"FAKE_KEY": "abcdef1234567890"})
    s = ("https://api.vworld.kr/req/wmts/1.0.0/ZZZZ-TEST-0000/white/7/1/2.png "
         "https://api.vworld.kr/req/wms?KEY=QQQQ-TEST&LAYERS=x local abcdef1234567890")
    out = _target.mask_text(s)
    assert "ZZZZ-TEST-0000" not in out and "QQQQ-TEST" not in out and "abcdef1234567890" not in out
    assert "/req/wmts/1.0.0/***/white/" in out and "KEY=***&LAYERS=x" in out
