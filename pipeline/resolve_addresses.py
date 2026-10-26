"""시연 주소 10건 확정 (도로명주소 검색 API, 빌드 때만 네트워크 사용) (agents.md §8-7).

- .env의 JUSO_CONFM_KEY(실패 시 JUSO_CONFM_KEY_ALT)를 쓴다. 키 값·요청 URL은 절대 출력하지 않는다.
- 응답 원본은 build/juso_raw/{addr_id}.json 에 저장한다 (응답에는 키가 없다).
- 결과: seed/demo_addresses.csv, seed/bjd_codes.csv 의 code_verified 갱신.

사용:
  python -m pipeline.resolve_addresses               # A1~A10 확정
  python -m pipeline.resolve_addresses --search 키워드  # 검색 결과만 보기 (주소 고를 때)
"""
import argparse
import csv
import json
import os
import re
import sys

import httpx
from dotenv import load_dotenv

from pipeline.common import BUILD, ROOT, SEED, fail, log, setup_stdout
from core.address import make_pnu, pnu_from_juso

API = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
KEY_ERRORS = {"E0001", "E0014"}   # E0001 승인키 오류, E0014 개발승인키 기간 만료
RAW = BUILD / "juso_raw"
ADDR_COLS = ["addr_id", "label", "input_text", "road_address", "jibun_address", "pnu", "bjd_code", "sgg_code",
             "building_name", "lat", "lon", "coord_source", "aliases", "in_scope"]

# 시연 주소 후보 (§4). keyword = API 검색어, pick = 결과 중 고를 행의 조건.
# A4·A5는 geocode 후 한양7차 중심과의 거리를 확인하고, 조건이 안 맞으면 여기 검색어를 바꿔 다시 실행한다.
# [확인 2026-10-26] 압구정동 527은 도로명주소 검색 결과가 없다(건물 주소가 없는 필지로 보임. 526 청담고등학교,
#   528 한양아파트 '압구정로61길 37'). 그래서 A1은 D1 근거 지번으로 고정하고(fixed), A2는 인접 528의 도로명 입력으로 한다.
CANDIDATES = [
    {"addr_id": "A1", "type": "사업 대표 지번", "input_text": "강남구 압구정동 527",
     "keyword": "서울특별시 강남구 압구정동 527", "pick": {"jibun_main": 527, "jibun_sub": 0},
     "fixed": ("강남구", "압구정동", 527, 0), "building_name": "한양7차아파트",
     "aliases": ["서울특별시 강남구 압구정동 527번지", "서울 강남구 압구정동 527"]},
    {"addr_id": "A2", "type": "도로명주소 입력 (527은 도로명 없음 → 인접 528)", "keyword": "서울특별시 강남구 압구정로61길 37",
     "pick": {"dong": "압구정동", "jibun_main": 528}, "road_input": True},
    {"addr_id": "A3", "type": "입력 변형", "input_text": "서울특별시 강남구 압구정동 527번지", "same_as": "A1", "use": "input"},
    # A4: 압구정 한양아파트(513, 압구정로 401)는 OSM에 번지가 없어 좌표를 못 얻었다 → OSM에 번지가 있는 갤러리아백화점(494)
    {"addr_id": "A4", "type": "같은 동, 사업 500m 이내", "keyword": "압구정동 갤러리아",
     "pick": {"dong": "압구정동", "jibun_main": 494}},
    {"addr_id": "A5", "type": "같은 동, 500m 밖", "keyword": "압구정 현대아파트", "pick": {"dong": "압구정동", "jibun_main": 426}},
    {"addr_id": "A6", "type": "같은 생활권, 다른 동", "keyword": "강남구 청담동 청담자이", "pick": {"dong": "청담동"}},
    {"addr_id": "A7", "type": "생활권 확인용", "keyword": "강남구 신사동 신구중학교", "pick": {"dong": "신사동"}},
    {"addr_id": "A8", "type": "다른 생활권", "keyword": "강남파이낸스센터", "pick": {"dong": "역삼동"}},
    {"addr_id": "A9", "type": "다른 생활권", "keyword": "대치동 은마아파트", "pick": {"dong": "대치동"}},
    {"addr_id": "A10", "type": "범위 밖", "keyword": "서초구 방배동 방배초등학교", "pick": {"dong": "방배동", "jibun_main": 861}},
    # P10 토지 중심 시연 주소 (feedback2.md §6). B2·B3은 지도 대조 후보와 브이월드 토지 정보로 골랐다 (2026-10-26)
    {"addr_id": "B1", "type": "대청마을 대표 (모아타운 대표 지번)", "input_text": "강남구 일원동 619",
     "keyword": "서울특별시 강남구 일원동 619", "pick": {"dong": "일원동", "jibun_main": 619, "jibun_sub": 0},
     "fixed": ("강남구", "일원동", 619, 0), "label": "★ 대청마을 대표 (일원동 619)"},
    {"addr_id": "B2", "type": "대청마을 안 단독주택 필지 (지도 대조 후보)", "keyword": "서울특별시 강남구 개포로120길 55",
     "pick": {"dong": "일원동", "jibun_main": 633, "jibun_sub": 2}, "road_input": True,
     "label": "★ 대청마을 안 단독주택 (개포로120길 55)"},
    {"addr_id": "B3", "type": "대청마을 밖 일원동 필지 (사업 중심 500m 안)", "input_text": "강남구 일원동 677-4",
     "keyword": "서울특별시 강남구 일원동 677-4", "pick": {"dong": "일원동", "jibun_main": 677, "jibun_sub": 4},
     "label": "★ 대청마을 밖 일원동 677-4"},
    {"addr_id": "B4", "type": "개발행위허가 제한 (D10)", "input_text": "강남구 대치동 506",
     "keyword": "서울특별시 강남구 대치동 506", "pick": {"dong": "대치동", "jibun_main": 506, "jibun_sub": 0},
     "fixed": ("강남구", "대치동", 506, 0), "label": "대치동 506 (선경아파트, 개발행위허가 제한)"},
    {"addr_id": "B5", "type": "녹지 필지 (지목 전)", "input_text": "강남구 율현동 122",
     "keyword": "서울특별시 강남구 율현동 122", "pick": {"dong": "율현동", "jibun_main": 122, "jibun_sub": 0},
     "fixed": ("강남구", "율현동", 122, 0), "label": "율현동 122 (녹지 필지, 지목 전)"},
]


# 도로명주소 API를 쓸 수 없을 때(§19-3)의 대체 목록: 지번 입력만 지원, 도로명 칸은 비운다.
# - source=doc: 원문 문서에 기재된 지번
# - source=example: 널리 알려진 시설의 지번(Claude Code 일반 지식) → 화면에 '예시·지번 미확인' 표시, 키 재발급 후 교체
# - source=pending: 확인할 방법이 없어 비워 둠 (PNU 없음, 시연 칩 비활성)
FALLBACK = [
    {"addr_id": "A1", "source": "doc", "jibun": ("강남구", "압구정동", 527, 0), "building_name": "한양7차아파트",
     "note": "D1 p4 '527번지 일대'", "aliases": ["서울특별시 강남구 압구정동 527번지", "서울 강남구 압구정동 527"]},
    {"addr_id": "A2", "source": "pending", "label": "A2 도로명주소 (키 재발급 후 추가)"},
    {"addr_id": "A3", "source": "doc", "same_as": "A1", "input_text": "서울특별시 강남구 압구정동 527번지"},
    {"addr_id": "A4", "source": "example", "jibun": ("강남구", "압구정동", 429, 0), "building_name": "현대백화점 압구정본점",
     "note": "같은 동 다른 필지. 500m 판정은 좌표 확보 후"},
    {"addr_id": "A5", "source": "pending", "label": "A5 압구정동 500m 밖 지점 (키 재발급 후 확정)"},
    {"addr_id": "A6", "source": "pending", "label": "A6 청담동 (키 재발급 후 확정)"},
    {"addr_id": "A7", "source": "example", "jibun": ("강남구", "신사동", 649, 9), "building_name": "도산공원"},
    {"addr_id": "A8", "source": "example", "jibun": ("강남구", "역삼동", 737, 0), "building_name": "강남파이낸스센터"},
    {"addr_id": "A9", "source": "example", "jibun": ("강남구", "대치동", 316, 0), "building_name": "은마아파트"},
    {"addr_id": "A10", "source": "doc", "jibun": ("서초구", "방배동", 818, 14), "building_name": "",
     "note": "서초구 고시 제2026-215호 '방배동 818-14번지 일대'"},
]


def load_bjd() -> dict[str, dict]:
    with open(SEED / "bjd_codes.csv", encoding="utf-8-sig", newline="") as f:
        return {r["dong_name"]: r for r in csv.DictReader(f)}


def resolve_fallback() -> list[dict]:
    bjd = load_bjd()
    out: dict[str, dict] = {}
    for c in FALLBACK:
        aid = c["addr_id"]
        if c["source"] == "pending":
            out[aid] = {"addr_id": aid, "label": c["label"], "input_text": "", "road_address": "", "jibun_address": "",
                        "pnu": "", "bjd_code": "", "sgg_code": "", "building_name": "", "lat": "", "lon": "",
                        "coord_source": "", "aliases": "[]", "in_scope": 1}
            continue
        if "same_as" in c:
            base = dict(out[c["same_as"]])
            base.update(addr_id=aid, input_text=c["input_text"], aliases="[]",
                        label=f"{aid} 입력 변형 ({c['input_text']})")
            out[aid] = base
            continue
        gu, dong, main, sub = c["jibun"]
        short = f"{gu} {dong} {main}" + (f"-{sub}" if sub else "")
        in_scope = int(gu == "강남구")
        code = bjd[dong]["bjd_code"] if in_scope else ""
        tag = " · 예시·지번 미확인" if c["source"] == "example" else ""
        bd = c.get("building_name") or ""
        out[aid] = {
            "addr_id": aid,
            "label": f"{aid} {short.replace('강남구 ', '')}" + (f" ({bd}{tag})" if bd else (f" ({tag[3:]})" if tag else "")),
            "input_text": short,
            "road_address": "",
            "jibun_address": f"서울특별시 {short}",
            "pnu": make_pnu(code, main, sub) if in_scope else "",
            "bjd_code": code,
            "sgg_code": "11680" if in_scope else "",
            "building_name": bd,
            "lat": "", "lon": "", "coord_source": "",
            "aliases": json.dumps(c.get("aliases", []), ensure_ascii=False),
            "in_scope": in_scope,
        }
    return [out[c["addr_id"]] for c in FALLBACK]


def clean_keyword(s: str) -> str:
    return re.sub(r"[%=><\[\]]", "", s).strip()


class JusoError(Exception):
    pass


def _call(key: str, keyword: str) -> dict:
    params = {"confmKey": key, "currentPage": 1, "countPerPage": 10, "keyword": clean_keyword(keyword),
              "resultType": "json"}
    try:
        r = httpx.get(API, params=params, timeout=15)
    except httpx.HTTPError as e:
        # 예외 메시지에 요청 URL(키 포함)이 들어갈 수 있으므로 종류만 알린다
        raise JusoError(f"네트워크 오류 ({type(e).__name__})") from None
    if r.status_code != 200:
        raise JusoError(f"HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise JusoError("응답이 JSON이 아님") from None


def search(keyword: str) -> dict:
    load_dotenv(ROOT / ".env")
    keys = [os.environ.get("JUSO_CONFM_KEY"), os.environ.get("JUSO_CONFM_KEY_ALT")]
    keys = [k for k in keys if k]
    if not keys:
        raise JusoError(".env에 JUSO_CONFM_KEY가 없습니다")
    last = None
    for i, key in enumerate(keys):
        data = _call(key, keyword)
        common = data.get("results", {}).get("common", {})
        code = common.get("errorCode")
        if code == "0":
            return data
        last = f"{code} {common.get('errorMessage', '')}"
        if code not in KEY_ERRORS:
            break          # 승인키 문제일 때만 다른 키로 다시 시도
        log(f"  승인키 문제({code}) → {'예비 키로 다시 시도' if i == 0 and len(keys) > 1 else '두 키 모두 실패'}")
    raise JusoError(f"API 오류: {last}")


def rows_of(data: dict) -> list[dict]:
    return data.get("results", {}).get("juso") or []


def matches(row: dict, pick: dict) -> bool:
    if "dong" in pick and row.get("emdNm") != pick["dong"]:
        return False
    if "jibun_main" in pick and int(row.get("lnbrMnnm") or -1) != pick["jibun_main"]:
        return False
    if "jibun_sub" in pick and int(row.get("lnbrSlno") or -1) != pick["jibun_sub"]:
        return False
    return str(row.get("mtYn", "0")) == "0"


def jibun_short(row: dict) -> str:
    main, sub = int(row["lnbrMnnm"]), int(row["lnbrSlno"] or 0)
    return f"{row['sggNm']} {row['emdNm']} {main}" + (f"-{sub}" if sub else "")


def resolve() -> list[dict]:
    RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    for c in CANDIDATES:
        aid = c["addr_id"]
        if "same_as" in c:
            base = dict(out[c["same_as"]])
            base["addr_id"] = aid
            if c["use"] == "road":
                base["input_text"] = base["road_address"]
                base["label"] = f"{aid} 도로명 {base['road_address'].replace('서울특별시 ', '')}"
            else:
                base["input_text"] = c["input_text"]
                base["label"] = f"{aid} 입력 변형 ({c['input_text']})"
            base["aliases"] = "[]"
            out[aid] = base
            continue
        data = search(c["keyword"])
        (RAW / f"{aid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        cands = [r for r in rows_of(data) if matches(r, c.get("pick", {}))]
        if not cands and "fixed" in c:
            # 도로명주소가 없는 필지: 원문(D1) 지번으로 고정하고 법정동 코드표로 PNU를 만든다
            gu, dong, main, sub = c["fixed"]
            code = load_bjd()[dong]["bjd_code"]
            short = f"{gu} {dong} {main}" + (f"-{sub}" if sub else "")
            bd = c.get("building_name", "")
            out[aid] = {"addr_id": aid,
                        "label": c.get("label") or f"{aid} {short.replace('강남구 ', '')}" + (f" ({bd})" if bd else ""),
                        "input_text": c.get("input_text") or short, "road_address": "",
                        "jibun_address": f"서울특별시 {short}", "pnu": make_pnu(code, main, sub), "bjd_code": code,
                        "sgg_code": code[:5], "building_name": bd, "lat": "", "lon": "", "coord_source": "",
                        "aliases": json.dumps(c.get("aliases", []), ensure_ascii=False), "in_scope": 1,
                        "_type": c["type"]}
            log(f"  {aid}: 도로명주소 검색 결과 없음 → 원문 지번 {short}로 고정")
            continue
        if not cands:
            fail(f"{aid} 검색 결과에서 조건에 맞는 행이 없습니다 (검색어: {c['keyword']}). CANDIDATES를 고치세요.")
        row = cands[0]
        in_scope = int(row.get("sggNm") == "강남구")
        bd = row.get("bdNm") or ""
        short = jibun_short(row)
        road = row.get("roadAddrPart1") or row.get("roadAddr")
        if c.get("road_input"):
            label = f"{aid} 도로명 {road.replace('서울특별시 ', '').replace('강남구 ', '')} ({short.replace('강남구 ', '')}" \
                    + (f" {bd})" if bd else ")")
        else:
            label = f"{aid} {short.replace('강남구 ', '')}" + (f" ({bd})" if bd else "")
        label = c.get("label") or label
        out[aid] = {
            "addr_id": aid,
            "label": label,
            "input_text": road if c.get("road_input") else (c.get("input_text") or short),
            "road_address": row.get("roadAddrPart1") or row.get("roadAddr"),
            "jibun_address": f"서울특별시 {short}",
            "pnu": pnu_from_juso(row),
            "bjd_code": row["admCd"],
            "sgg_code": row["admCd"][:5],
            "building_name": bd,
            "lat": "", "lon": "", "coord_source": "",
            "aliases": json.dumps(c.get("aliases", []), ensure_ascii=False),
            "in_scope": in_scope,
            "_type": c["type"],
        }
    return [out[c["addr_id"]] for c in CANDIDATES]


def keep_coords(rows: list[dict]) -> None:
    """이미 geocode로 채운 좌표가 있으면 PNU가 같을 때 유지한다 (재실행해도 좌표가 지워지지 않게)."""
    p = SEED / "demo_addresses.csv"
    if not p.exists():
        return
    with open(p, encoding="utf-8-sig", newline="") as f:
        old = {r["addr_id"]: r for r in csv.DictReader(f)}
    for r in rows:
        o = old.get(r["addr_id"])
        if o and o.get("pnu") == r["pnu"] and o.get("lat"):
            r["lat"], r["lon"], r["coord_source"] = o["lat"], o["lon"], o["coord_source"]


def verify_bjd(rows: list[dict]) -> list[str]:
    """시연 주소와 동별 검색 결과의 admCd로 bjd_codes.csv 코드를 확인한다."""
    p = SEED / "bjd_codes.csv"
    with open(p, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        bjd = list(reader)
    seen = {r["bjd_code"]: True for r in rows if r["in_scope"]}
    notes = []
    for b in bjd:
        if b["bjd_code"] in seen:
            b["code_verified"] = "1"
            continue
        try:
            data = search(f"서울특별시 강남구 {b['dong_name']} 1")
        except JusoError as e:
            notes.append(f"{b['dong_name']}: {e}")
            continue
        adms = {r["admCd"] for r in rows_of(data) if r.get("emdNm") == b["dong_name"]}
        if b["bjd_code"] in adms:
            b["code_verified"] = "1"
        elif adms:
            notes.append(f"{b['dong_name']}: 코드표 {b['bjd_code']} ≠ API {sorted(adms)}")
        else:
            notes.append(f"{b['dong_name']}: 검색 결과 없음")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(bjd)
    return notes


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", help="검색 결과만 출력")
    ap.add_argument("--offline", action="store_true", help="API 없이 대체 목록(FALLBACK)으로 작성")
    args = ap.parse_args()
    notes: list[str] = []
    try:
        if args.search:
            for r in rows_of(search(args.search)):
                log(f"{r.get('jibunAddr')} | {r.get('roadAddrPart1')} | bd={r.get('bdNm')} | admCd={r.get('admCd')} "
                    f"| {r.get('lnbrMnnm')}-{r.get('lnbrSlno')} mt={r.get('mtYn')}")
            return
        if args.offline:
            raise JusoError("--offline 지정")
        rows = resolve()
        notes = verify_bjd(rows)
    except JusoError as e:
        if args.search:
            fail(f"도로명주소 API 실패: {e}")
        log(f"[대체 모드] 도로명주소 API를 쓸 수 없습니다 ({e}). agents.md §19-3에 따라 지번 입력만 지원하는 대체 목록으로 작성합니다.")
        log("  → 키 재발급 후 `python -m pipeline.resolve_addresses`를 다시 실행하면 API 결과로 바뀝니다 (HUMAN_TODO).")
        rows = resolve_fallback()
    keep_coords(rows)
    with open(SEED / "demo_addresses.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ADDR_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log("addr_id | 입력 | 도로명 | 지번 | PNU | in_scope")
    for r in rows:
        log(f"{r['addr_id']} | {r['input_text']} | {r['road_address']} | {r['jibun_address']} | {r['pnu']} | {r['in_scope']}")
    for n in notes:
        log(f"  ※ 법정동 코드 확인: {n}")
    log("seed/demo_addresses.csv, seed/bjd_codes.csv 갱신")


if __name__ == "__main__":
    main()
