"""브이월드 토지 정보 파싱 (저장 응답, 네트워크 없음) — feedback2.md §3-2, §8-3."""
from datetime import datetime

import pytest

from core.live import vworld
from core.live.http import KST
from live_fixtures import FixtureFetch, load

PNU_619 = "1168011400106190000"
ADDR_619 = "서울특별시 강남구 일원동 619"
NOW = datetime(2026, 10, 26, 20, 0, tzinfo=KST)


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", "test-key")
    vworld._land_cache.clear()
    yield
    vworld._land_cache.clear()


def test_land_ok_from_saved_responses():
    land = vworld.get_land(PNU_619, ADDR_619, fetch=FixtureFetch(), now=NOW, use_cache=False)
    assert land["status"] == "ok" and land["missing"] == [] and land["found"] is True
    assert (land["jimok"], land["area_m2"], land["land_use_zone"]) == ("대", 377.1, "제2종일반주거지역")
    assert land["official_price"] == {"won_per_m2": 11080000, "year": 2026, "announced_on": "2026-04-30"}
    assert land["location"]["source"] == "vworld-geocoder:parcel" and 37.4 < land["location"]["lat"] < 37.6
    assert land["terrain"] == "평지 · 정방형" and land["road_side"] == "광대소각" and land["use_situation"] == "상업용"
    names = [(z["name"], z["relation"]) for z in land["zones"]]
    assert ("도로", "접함") in names and len(names) == len(set(names))      # 같은 지역지구는 한 번만
    assert land["source"].startswith("브이월드") and land["note"]


def test_records_dict_or_list():
    j = load("vworld", f"getLandCharacteristics_{PNU_619}.json")
    top = next(iter(j))
    as_dict = {top: dict(j[top], field=j[top]["field"][0])}    # 1건이면 dict로 오는 경우
    assert vworld.ned_records(j) == vworld.ned_records(as_dict)


def test_no_data_means_not_found():
    land = vworld.get_land("1168011400199990000", "서울특별시 강남구 일원동 9999", fetch=FixtureFetch(), now=NOW,
                           use_cache=False)
    assert land["status"] == "unavailable" and land["found"] is False
    assert land["note"] == vworld.NOT_FOUND_NOTE


def test_timeout_is_unavailable_not_error():
    land = vworld.get_land(PNU_619, ADDR_619, fetch=FixtureFetch(fail_all=True), now=NOW, use_cache=False)
    assert land["status"] == "unavailable" and land["found"] is None
    assert land["note"] == vworld.UNAVAILABLE_NOTE


def test_wrong_key_response_is_unavailable():
    assert vworld.ned_records(load("vworld", "getLandUseAttr_wrongkey.json")) is None


def test_missing_key(monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", "")
    monkeypatch.setattr("core.live.http._ENV_LOADED", True)    # .env를 다시 읽지 않게
    land = vworld.get_land(PNU_619, ADDR_619, fetch=FixtureFetch(), now=NOW, use_cache=False)
    assert land["status"] == "unavailable" and land["note"] == vworld.NO_KEY_NOTE


def test_partial_when_geocoder_misses():
    land = vworld.get_land(PNU_619, "서울특별시 강남구 일원동 없는주소", fetch=FixtureFetch(), now=NOW, use_cache=False)
    assert land["status"] == "partial" and land["missing"] == ["좌표"] and land["location"] is None


def test_memory_cache():
    f = FixtureFetch()
    a = vworld.get_land(PNU_619, ADDR_619, fetch=f, now=NOW)
    n = len(f.calls)
    b = vworld.get_land(PNU_619, ADDR_619, fetch=f, now=NOW)
    assert len(f.calls) == n and b["from_cache"] is True and a["from_cache"] is False


def test_geocode_gives_pnu():
    g = vworld.geocode_parcel(ADDR_619, fetch=FixtureFetch(), key="test-key")
    assert g["pnu"] == PNU_619


def test_no_key_value_in_saved_fixtures():
    """저장 응답·토지 캐시에 .env 키 값이 섞이지 않았는지 (키 값은 출력하지 않는다)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    env = root / ".env"
    if not env.exists():
        pytest.skip(".env 없음")
    secrets = [ln.split("=", 1)[1].strip().strip('"') for ln in env.read_text(encoding="utf-8").splitlines()
               if "=" in ln and not ln.lstrip().startswith("#")]
    secrets = [s for s in secrets if len(s) > 8]
    files = list((root / "tests" / "fixtures").rglob("*.json")) + [root / "seed" / "land_cache.json"]
    for f in files:
        if f.exists():
            text = f.read_text(encoding="utf-8")
            assert not any(s in text for s in secrets), f.name


def test_domain_from_env(monkeypatch):
    """domain 파라미터: VWORLD_DOMAIN이 있으면 그 값, 비어 있으면 운영 주소 (P12)."""
    import core.live.http as live_http
    monkeypatch.setattr(live_http, "_ENV_LOADED", True)      # 로컬 .env 값이 끼어들지 않게
    monkeypatch.setenv("VWORLD_DOMAIN", "")
    assert vworld.domain() == vworld.DEFAULT_DOMAIN == "https://propedia-pretotype.vercel.app"
    monkeypatch.setenv("VWORLD_DOMAIN", "http://localhost:3000")
    assert vworld.domain() == "http://localhost:3000"
    assert vworld._params("k")["domain"] == "http://localhost:3000"
