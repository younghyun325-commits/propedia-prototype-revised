"""지도 바탕 경계 (docs/map/PLAN.md P12). 네트워크 사용, 빌드 때만.

브이월드 2D 데이터 API(req/data GetFeature)에서
- LT_C_ADSIGG_INFO (시군구, sig_cd = 11680 강남구)  → public/data/base/gangnam.geojson
- LT_C_ADEMD_INFO  (읍면동 = 법정동, emd_cd 11680…) → public/data/base/bjd.geojson
을 받아 EPSG:4326, 좌표 소수 6자리로 저장한다.

- 키: VWORLD_API_KEY, 비어 있으면 VWORLD_API_KEY_DEV. domain: VWORLD_DOMAIN(없으면 운영 주소, core/live/vworld.py).
  키 값은 어디에도 출력하지 않는다. 원 응답은 키를 지운 뒤 build/vworld_raw/에 캐시한다(있으면 네트워크 안 씀).
- 법정동 코드 집합이 seed/bjd_codes.csv(강남구 14개)와 다르면 실패한다.
- 같은 캐시면 같은 바이트가 나온다 (정렬·반올림·sort_keys).

사용: python -m pipeline.build_map_base [--refresh]
"""
import argparse
import csv
import json
import os

import httpx
from dotenv import load_dotenv

from core.live.vworld import domain as vworld_domain
from pipeline import sync_server_data
from pipeline.common import BUILD, PUBLIC, ROOT, SEED, fail, log, setup_stdout, sha256

DATA_URL = "https://api.vworld.kr/req/data"
RAW = BUILD / "vworld_raw"
OUT = PUBLIC / "data" / "base"
SGG = "11680"
LAYERS = {
    # 출력 파일: (브이월드 데이터 이름, attrFilter)
    "gangnam": ("LT_C_ADSIGG_INFO", f"sig_cd:=:{SGG}"),
    "bjd": ("LT_C_ADEMD_INFO", f"emd_cd:like:{SGG}"),
}
SIZE_WARN = 1_000_000


def api_key() -> str:
    load_dotenv(ROOT / ".env")
    for name in ("VWORLD_API_KEY", "VWORLD_API_KEY_DEV"):
        v = (os.environ.get(name) or "").strip().strip('"').strip("'")
        if v:
            return v
    fail("VWORLD_API_KEY(또는 VWORLD_API_KEY_DEV)가 .env에 없습니다")
    return ""


def fetch(data: str, attr_filter: str, key: str) -> dict:
    params = {"service": "data", "request": "GetFeature", "version": "2.0", "data": data,
              "attrFilter": attr_filter, "crs": "EPSG:4326", "format": "json", "size": 1000, "page": 1,
              "geometry": "true", "attribute": "true", "key": key, "domain": vworld_domain()}
    try:
        r = httpx.get(DATA_URL, params=params, timeout=30)
    except httpx.HTTPError as e:
        fail(f"{data}: 요청 실패 ({type(e).__name__})")
    if r.status_code != 200:
        fail(f"{data}: HTTP {r.status_code}")
    j = r.json()
    resp = j.get("response") or {}
    if resp.get("status") != "OK":
        err = resp.get("error") or {}
        fail(f"{data}: status={resp.get('status')} code={err.get('code')} ({err.get('text', '')[:60]})")
    text = json.dumps(j, ensure_ascii=False)
    if key in text:
        fail(f"{data}: 응답에 키 문자열이 들어 있어 저장하지 않습니다")
    return j


def raw_response(name: str, refresh: bool) -> dict:
    data, attr = LAYERS[name]
    path = RAW / f"{data}_{SGG}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    j = fetch(data, attr, api_key())
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    log(f"{data}: 받음 → build/vworld_raw/{path.name}")
    return j


def features_of(j: dict) -> list[dict]:
    resp = j["response"]
    page = resp.get("page") or {}
    if str(page.get("total", "1")) not in ("1", ""):
        fail(f"응답이 여러 쪽입니다 (page.total={page.get('total')})")
    return resp["result"]["featureCollection"]["features"]


def rnd(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 6), round(coords[1], 6)]
    return [rnd(c) for c in coords]


def geometry(g: dict) -> dict:
    return {"type": g["type"], "coordinates": rnd(g["coordinates"])}


def write(name: str, features: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection",
          "source": "브이월드 2D 데이터 (국토교통부)", "crs": "EPSG:4326",
          "features": features}
    path = OUT / f"{name}.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="캐시를 무시하고 다시 받음")
    args = ap.parse_args()

    # 강남구 경계
    sgg = features_of(raw_response("gangnam", args.refresh))
    if len(sgg) != 1:
        fail(f"강남구 경계가 {len(sgg)}건입니다 (1건이어야 함)")
    p = sgg[0]["properties"]
    if p.get("sig_cd") != SGG:
        fail(f"시군구 코드가 다릅니다: {p.get('sig_cd')}")
    write("gangnam", [{"type": "Feature", "id": SGG,
                       "properties": {"sgg_code": SGG, "name": p.get("sig_kor_nm")},
                       "geometry": geometry(sgg[0]["geometry"])}])

    # 법정동 경계: emd_cd 8자리 + "00" = 법정동코드 10자리
    emd = features_of(raw_response("bjd", args.refresh))
    feats = []
    for f in emd:
        q = f["properties"]
        code = f"{q['emd_cd']}00"
        feats.append({"type": "Feature", "id": code,
                      "properties": {"bjd_code": code, "sgg_code": SGG, "name": q.get("emd_kor_nm")},
                      "geometry": geometry(f["geometry"])})
    feats.sort(key=lambda x: x["id"])

    with (SEED / "bjd_codes.csv").open(encoding="utf-8-sig", newline="") as fp:
        seed = {r["bjd_code"]: r["dong_name"] for r in csv.DictReader(fp) if r["sgg_code"] == SGG}
    got = {f["id"]: f["properties"]["name"] for f in feats}
    if set(got) != set(seed) or len(feats) != len(got):
        fail(f"법정동 코드가 seed/bjd_codes.csv와 다릅니다: 응답에만 {sorted(set(got) - set(seed))}, "
             f"seed에만 {sorted(set(seed) - set(got))}, 응답 {len(feats)}건")
    diff_name = [c for c in seed if seed[c] != got[c]]
    if diff_name:
        fail(f"법정동 이름이 다릅니다: {[(c, seed[c], got[c]) for c in diff_name]}")
    write("bjd", feats)

    log(f"법정동 {len(feats)}개 = seed/bjd_codes.csv 와 같음")
    for name in LAYERS:
        path = OUT / f"{name}.geojson"
        n = path.stat().st_size
        log(f"public/data/base/{path.name}: {n:,} B  sha256 {sha256(path)}")
        if n > SIZE_WARN:
            log(f"  ※ 1MB를 넘습니다 — 단순화 여부 확인 필요")
    sync_server_data.sync(quiet=True)    # 서버가 읽는 사본 (P20-B, core/paths.py)


if __name__ == "__main__":
    main()
