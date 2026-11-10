"""L0 키·응답 점검 (feedback2.md §4). 네트워크 사용, 빌드 때만.

- .env에 VWORLD_API_KEY가 없으면 멈춘다 (H1).
- 브이월드 토지 3종(압구정동 527, 일원동 619), 지오코더(일원동 619), 이미지(일원동 619 중심), juso(테헤란로 427)를 부른다.
- 화면에는 상태 코드·결과 개수만 찍는다. 키 값은 출력하지 않는다.
- 받은 응답은 키가 들어 있지 않은지 확인한 뒤 build/check_keys/{vworld,juso}/ 에 저장한다 (기본, 커밋 안 함).
- 테스트 저장 응답(tests/fixtures/{vworld,juso}/)은 --update-fixtures를 줄 때만 갱신한다 (같은 키 검사를 거침).

사용: python -m pipeline.check_keys [--update-fixtures]
"""
import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv

from core.address import make_pnu
from core.live.vworld import domain as vworld_domain
from pipeline.common import BUILD, ROOT, fail, log, setup_stdout

FIX = ROOT / "tests" / "fixtures"     # --update-fixtures일 때만 쓴다
OUT = BUILD / "check_keys"            # 기본 출력 위치
DOMAIN = vworld_domain()          # VWORLD_DOMAIN, 없으면 운영 주소 (core/live/vworld.py)
NED = "https://api.vworld.kr/ned/data"
PNU_527 = "1168011000105270000"
PNU_619 = make_pnu("1168011400", 619)            # 일원동 619
ADDR_619 = "서울특별시 강남구 일원동 619"
JUSO_Q = "서울특별시 강남구 테헤란로 427"


def scrub(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s and s in text:
            text = text.replace(s, "***")
    return text


def save(path, data, secrets) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=1)
    text = scrub(text, secrets)
    if any(s and s in text for s in secrets):
        fail(f"{path.name}: 키가 남아 있어 저장하지 않습니다")
    path.write_text(text, encoding="utf-8")


def count_ned(j: dict) -> tuple[str, int]:
    """국가중점 API 응답에서 (결과 코드, 건수). 응답 최상위 키는 서비스마다 다르다."""
    for top in j.values():
        if isinstance(top, dict) and ("field" in top or "totalCount" in top or "resultCode" in top):
            n = top.get("totalCount")
            fields = top.get("field") or []
            return str(top.get("resultCode", "")) or "OK", int(n) if n not in (None, "") else len(fields)
    return "?", 0


def main(argv=None) -> None:
    setup_stdout()
    ap = argparse.ArgumentParser(description="브이월드·도로명주소 키와 응답 점검")
    ap.add_argument("--update-fixtures", action="store_true",
                    help="tests/fixtures/ 의 테스트 저장 응답을 갱신 (기본은 build/check_keys/)")
    args = ap.parse_args(argv)
    dest = FIX if args.update_fixtures else OUT
    load_dotenv(ROOT / ".env")
    vkey = (os.environ.get("VWORLD_API_KEY") or "").strip()
    jkey = (os.environ.get("JUSO_CONFM_KEY") or "").strip()
    if not vkey:
        fail("VWORLD_API_KEY가 .env에 없습니다 (feedback2.md H1)")
    secrets = [vkey, jkey, (os.environ.get("JUSO_CONFM_KEY_ALT") or "").strip()]
    raw = BUILD / "vworld_raw"
    rows = []

    with httpx.Client(timeout=15) as c:
        for op, extra in (("getLandUseAttr", {"numOfRows": 1000, "pageNo": 1}),
                          ("getLandCharacteristics", {"stdrYear": 2026, "numOfRows": 10, "pageNo": 1}),
                          ("getIndvdLandPriceAttr", {"stdrYear": 2026, "numOfRows": 10, "pageNo": 1})):
            for pnu in (PNU_527, PNU_619):
                try:
                    r = c.get(f"{NED}/{op}", params={"key": vkey, "domain": DOMAIN, "pnu": pnu, "format": "json", **extra})
                    try:
                        j = r.json()
                        code, n = count_ned(j)
                        save(dest / "vworld" / f"{op}_{pnu}.json", j, secrets)
                    except ValueError:
                        code, n = "응답이 JSON 아님", 0
                        save(raw / f"{op}_{pnu}.txt", r.text[:4000], secrets)
                    rows.append((op, pnu, r.status_code, code, n))
                except httpx.HTTPError as e:
                    rows.append((op, pnu, "실패", type(e).__name__, 0))

        # 지오코더 (지번 주소 → 좌표)
        try:
            r = c.get("https://api.vworld.kr/req/address", params={
                "service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326", "type": "parcel",
                "address": ADDR_619, "format": "json", "key": vkey, "domain": DOMAIN})
            j = r.json()
            resp = j.get("response", {})
            save(dest / "vworld" / f"getcoord_{PNU_619}.json", j, secrets)
            rows.append(("getcoord", ADDR_619, r.status_code, resp.get("status"), 1 if resp.get("result") else 0))
        except (httpx.HTTPError, ValueError) as e:
            rows.append(("getcoord", ADDR_619, "실패", type(e).__name__, 0))

        # 이미지 API (일원동 619 중심 지적도)
        lon, lat = None, None
        try:
            got = dest / "vworld" / f"getcoord_{PNU_619}.json"
            pt = json.loads((got if got.exists() else FIX / "vworld" / got.name).read_text(encoding="utf-8"))
            p = pt["response"]["result"]["point"]
            lon, lat = float(p["x"]), float(p["y"])
        except (OSError, KeyError, TypeError, ValueError):
            pass
        if lon is not None:
            try:
                r = c.get("https://api.vworld.kr/req/image", params={
                    "service": "image", "request": "getmap", "key": vkey, "domain": DOMAIN, "format": "png",
                    "basemap": "GRAPHIC", "center": f"{lon},{lat}", "crs": "epsg:4326", "zoom": 18,
                    "size": "1024,1024"})
                ctype = r.headers.get("content-type", "")
                if ctype.startswith("image"):
                    (raw).mkdir(parents=True, exist_ok=True)
                    (raw / "image_619.png").write_bytes(r.content)
                    rows.append(("image getmap", "일원동 619", r.status_code, ctype, len(r.content)))
                else:
                    save(raw / "image_619.txt", r.text[:4000], secrets)
                    rows.append(("image getmap", "일원동 619", r.status_code, ctype, 0))
            except httpx.HTTPError as e:
                rows.append(("image getmap", "일원동 619", "실패", type(e).__name__, 0))

        # juso
        try:
            r = c.get("https://business.juso.go.kr/addrlink/addrLinkApi.do", params={
                "confmKey": jkey, "currentPage": 1, "countPerPage": 5, "keyword": JUSO_Q, "resultType": "json"})
            j = r.json()
            com = j.get("results", {}).get("common", {})
            save(dest / "juso" / "teheran_427.json", j, secrets)
            rows.append(("juso", JUSO_Q, r.status_code, com.get("errorCode"), int(com.get("totalCount") or 0)))
        except (httpx.HTTPError, ValueError) as e:
            rows.append(("juso", JUSO_Q, "실패", type(e).__name__, 0))

        # 테스트용 저장 응답 추가: 여러 건·강남구 밖·결과 없음·키 오류(가짜 키로 받은 실제 오류 응답)·없는 지번·브이월드 검색
        extra = [
            ("juso", "ambiguous_dogok_ro.json", "https://business.juso.go.kr/addrlink/addrLinkApi.do",
             {"confmKey": jkey, "currentPage": 1, "countPerPage": 5, "keyword": "강남구 도곡로", "resultType": "json"}),
            ("juso", "out_of_scope_seocho.json", "https://business.juso.go.kr/addrlink/addrLinkApi.do",
             {"confmKey": jkey, "currentPage": 1, "countPerPage": 5, "keyword": "서울특별시 서초구 방배중앙로13길 26",
              "resultType": "json"}),
            ("juso", "empty.json", "https://business.juso.go.kr/addrlink/addrLinkApi.do",
             {"confmKey": jkey, "currentPage": 1, "countPerPage": 5, "keyword": "아무말대잔치길 99999",
              "resultType": "json"}),
            ("juso", "error_bad_key.json", "https://business.juso.go.kr/addrlink/addrLinkApi.do",
             {"confmKey": "invalid-key-for-test", "currentPage": 1, "countPerPage": 5, "keyword": JUSO_Q,
              "resultType": "json"}),
            ("vworld", "getLandUseAttr_nodata.json", f"{NED}/getLandUseAttr",
             {"key": vkey, "domain": DOMAIN, "pnu": "1168011400199990000", "format": "json", "numOfRows": 1000,
              "pageNo": 1}),
            ("vworld", "getLandCharacteristics_nodata.json", f"{NED}/getLandCharacteristics",
             {"key": vkey, "domain": DOMAIN, "pnu": "1168011400199990000", "stdrYear": 2026, "format": "json",
              "numOfRows": 10, "pageNo": 1}),
            ("vworld", "getcoord_527.json", "https://api.vworld.kr/req/address",
             {"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326", "type": "parcel",
              "address": "서울특별시 강남구 압구정동 527", "format": "json", "key": vkey, "domain": DOMAIN}),
            ("vworld", "getcoord_notfound.json", "https://api.vworld.kr/req/address",
             {"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326", "type": "parcel",
              "address": "서울특별시 강남구 일원동 99999", "format": "json", "key": vkey, "domain": DOMAIN}),
            ("vworld", "search_road_teheran_427.json", "https://api.vworld.kr/req/search",
             {"service": "search", "request": "search", "version": "2.0", "query": JUSO_Q, "type": "address",
              "category": "road", "format": "json", "size": 5, "key": vkey, "domain": DOMAIN}),
            ("vworld", "getLandUseAttr_wrongkey.json", f"{NED}/getLandUseAttr",
             {"key": "00000000-0000-0000-0000-000000000000", "domain": DOMAIN, "pnu": PNU_619, "format": "json",
              "numOfRows": 10, "pageNo": 1}),
        ]
        for folder, name, url, params in extra:
            try:
                r = c.get(url, params=params)
                save(dest / folder / name, r.json(), secrets)
                rows.append((f"저장 {folder}", name, r.status_code, "", ""))
            except (httpx.HTTPError, ValueError) as e:
                rows.append((f"저장 {folder}", name, "실패", type(e).__name__, 0))

    log(f"응답 저장 위치: {dest.relative_to(ROOT)}")
    log("API | 대상 | HTTP | 결과 코드 | 건수(바이트)")
    for r in rows:
        log(" | ".join(str(x) for x in r))


if __name__ == "__main__":
    sys.exit(main())
