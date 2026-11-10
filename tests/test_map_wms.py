"""참고 WMS 프록시 허용 목록·캐시 헤더·키 노출 (docs/map/PLAN.md P16 0단계). 네트워크 없음 — 가짜 fetch_bytes."""
import pytest

from core import map as map_mod
from core.live import vworld
from core.live.http import LiveError

GANGNAM_Z14 = (14, 13974, 6348)         # 대치동 부근
GANGNAM_Z17 = (17, 111797, 50788)
BUSAN_Z14 = (14, 14066, 6524)           # 강남구 밖
SECRET = "SECRET-KEY-0123456789abcdef"
DOMAIN = "https://secret-domain.example"
OK_CACHE = "public, max-age=86400, s-maxage=604800"


class FakeBytes:
    def __init__(self, ctype="image/png", fail=None):
        self.calls, self.ctype, self.fail = [], ctype, fail

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if self.fail:                    # 원 URL(키 포함)을 담은 오류 — 응답으로 새면 안 된다
            raise LiveError(f"{self.fail} {url}?KEY={params['KEY']}&DOMAIN={params['DOMAIN']}")
        return b"\x89PNG-test", self.ctype


@pytest.fixture()
def fake_live(monkeypatch):
    import api.index as api
    monkeypatch.setenv("VWORLD_API_KEY", SECRET)
    monkeypatch.setenv("VWORLD_DOMAIN", DOMAIN)
    state = {"fetch": FakeBytes()}

    class FakeLive:
        def wms_tile(self, layer, z, x, y, size=None):
            return vworld.wms_tile(layer, z, x, y, size=size, fetch_bytes=state["fetch"])
    monkeypatch.setattr(api.live_mod, "default", lambda: FakeLive())
    return state


def url(layer, t, q=""):
    z, x, y = t
    return f"/api/v1/map/wms/{layer}/{z}/{x}/{y}.png{q}"


def no_secret(r):
    text = r.text + " ".join(f"{k}:{v}" for k, v in r.headers.items())
    assert SECRET not in text and DOMAIN not in text and "api.vworld.kr" not in text


def test_gangnam_bbox_loaded():
    w, s, e, n = map_mod.gangnam_bbox()
    assert 127.0 < w < e < 127.2 and 37.4 < s < n < 37.6


@pytest.mark.parametrize("path", [
    url("lt_c_evil", GANGNAM_Z14),                                   # 허용 목록 밖 레이어
    url("LT_C_UQ111", GANGNAM_Z14),                                  # 대소문자도 정확히
    url("lt_c_uq111", BUSAN_Z14),                                    # 강남구 밖
    url("lt_c_uq111", (13, 6987, 3174)),                             # 최소 줌 미만
    url("lt_c_uq111", GANGNAM_Z14, "?size=300"),                     # 크기 256·512만
    url("lt_c_uq111", GANGNAM_Z14, "?format=image/jpeg"),            # 형식 png만
    url("lp_pa_cbnd_bubun", (16, 55898, 25394)),                     # 지적도 줌 16
    url("lp_pa_cbnd_bubun", GANGNAM_Z17, "?size=256"),               # 지적도 z17·256px = 1.19m/px
])
def test_rejects_400_no_store(client, fake_live, path):
    r = client.get(path)
    assert r.status_code == 400, path
    assert r.headers["cache-control"] == "no-store"
    detail = r.json()["detail"]
    assert any("가" <= ch <= "힣" for ch in detail)                 # 한국어 안내
    assert fake_live["fetch"].calls == []                            # 브이월드를 부르지 않음
    no_secret(r)


def test_ok_headers(client, fake_live):
    r = client.get(url("lt_c_uq111", GANGNAM_Z14))
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == OK_CACHE
    assert r.content == b"\x89PNG-test"
    no_secret(r)
    _, p = fake_live["fetch"].calls[0]
    assert p["WIDTH"] == 256 and p["FORMAT"] == "image/png"


def test_ok_cadastral_512(client, fake_live):
    r = client.get(url("lp_pa_cbnd_bubun", GANGNAM_Z17, "?size=512&format=image/png"))
    assert r.status_code == 200 and r.headers["cache-control"] == OK_CACHE
    assert fake_live["fetch"].calls[0][1]["WIDTH"] == 512


@pytest.mark.parametrize("fail,code", [("TimeoutError", 504), ("HTTPError 500", 502)])
def test_upstream_errors_hide_url(client, fake_live, fail, code):
    fake_live["fetch"] = FakeBytes(fail=fail)
    r = client.get(url("lt_c_uq111", GANGNAM_Z14))
    assert r.status_code == code and r.headers["cache-control"] == "no-store"
    no_secret(r)


def test_not_image_is_error(client, fake_live):
    fake_live["fetch"] = FakeBytes(ctype="application/xml")       # 브이월드 오류 XML 등
    r = client.get(url("lt_c_uq111", GANGNAM_Z14))
    assert r.status_code == 502 and r.headers["cache-control"] == "no-store"
    no_secret(r)


def test_live_off_503_no_store(client):
    r = client.get(url("lt_c_uq111", GANGNAM_Z14))                 # conftest: PROPEDIA_LIVE=0
    assert r.status_code == 503 and r.headers["cache-control"] == "no-store"


def test_vworld_note_has_no_url():
    r = vworld.wms_tile("lt_c_uq111", *GANGNAM_Z14, fetch_bytes=FakeBytes(fail="TimeoutError"), key=SECRET)
    assert r["status"] == "timeout" and SECRET not in r["note"] and "http" not in r["note"]
