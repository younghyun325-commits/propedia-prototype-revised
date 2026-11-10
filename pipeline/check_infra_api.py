"""P18 1단계: 상가(상권)정보 API(sdsc2)의 오퍼레이션·요청 변수·응답 필드를 실제 응답으로 확인한다 (docs/map/PLAN.md P18).

- 키: .env DATA_GO_KR_SERVICE_KEY. 키 값·키가 든 URL은 출력·저장하지 않는다 (check_market_api.call/scrub 재사용).
- 오퍼레이션 경로 이름은 기술문서 페이지에 없어 후보를 차례로 시도하고, 맞은 이름을 보고한다.
- 원 응답(키 검사 후): build/infra_api_check/ (커밋 안 함)
- --counts: 업종 대·중·소분류 코드 목록 + 강남구 업종별 건수(numOfRows=1로 totalCount만 읽음)

사용: python -m pipeline.check_infra_api [--counts] [--small 중분류코드,...]
"""
import argparse
import json
import time

from pipeline.check_market_api import _key, call, has_key
from pipeline.common import BUILD, fail, log, setup_stdout

BASE = "https://apis.data.go.kr/B553077/api/open/sdsc2"
STORE_OPS = ["storeListInDong", "storeListInSigngu"]
LCLS_OPS = ["largeUpjongList"]
MCLS_OPS = ["middleUpjongList"]
SCLS_OPS = ["smallUpjongList"]
SGG = "11680"
RAW = BUILD / "infra_api_check"
CALLS = {"n": 0}


def get(op: str, params: dict, key: str) -> tuple[int | None, dict | None, str]:
    CALLS["n"] += 1
    st, body = call(f"{BASE}/{op}", {"type": "json", **params}, key)
    if has_key(body, key):
        fail("응답에 키 문자열이 있습니다 — 저장하지 않고 멈춥니다")
    try:
        return st, json.loads(body), body
    except ValueError:
        return st, None, body


def first_ok(ops: list[str], params: dict, key: str, tag: str):
    for op in ops:
        st, js, body = get(op, params, key)
        code = ((js or {}).get("header") or {}).get("resultCode")
        log(f"[{tag}] {op}: HTTP {st} · resultCode {code} · 앞부분 {body[:120].replace(chr(10), ' ')!r}")
        if st == 200 and js is not None and code in ("00", "0", "03"):
            return op, js
    return None, None


def save(name: str, js: dict) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_text(json.dumps(js, ensure_ascii=False, indent=1), encoding="utf-8")


def total(js: dict) -> int:
    return int(((js or {}).get("body") or {}).get("totalCount") or 0)


def items(js: dict) -> list:
    return ((js or {}).get("body") or {}).get("items") or []


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--small", default="", help="소분류 건수를 셀 중분류 코드(쉼표)")
    a = ap.parse_args()
    key = _key()
    t0 = time.time()

    op, js = first_ok(STORE_OPS, {"divId": "signguCd", "key": SGG, "pageNo": 1, "numOfRows": 1000}, key, "상가 목록")
    if not op:
        fail("상가 목록 오퍼레이션을 찾지 못했습니다")
    save("store_page1.json", js)
    its = items(js)
    log(f"상가 목록 오퍼레이션 = {op}, totalCount(강남구) = {total(js)}, 1쪽 항목 수 = {len(its)}")
    log(f"header = {js.get('header')}")
    log(f"body 키 = {sorted(k for k in js.get('body', {}) if k != 'items')}")
    if its:
        for k, v in its[0].items():
            log(f"  필드 {k} = {v!r}")
    # numOfRows 최대 확인: 1001 요청
    _, js2 = first_ok([op], {"divId": "signguCd", "key": SGG, "pageNo": 1, "numOfRows": 1001}, key, "numOfRows=1001")
    log(f"numOfRows=1001 → 항목 {len(items(js2)) if js2 else '오류'}")

    if a.counts:
        lop, ljs = first_ok(LCLS_OPS, {}, key, "대분류")
        mop, mjs = first_ok(MCLS_OPS, {}, key, "중분류")
        if ljs: save("lcls.json", ljs)
        if mjs: save("mcls.json", mjs)
        res = {"lcls": [], "mcls": [], "scls": []}
        for it in items(ljs):
            _, c = first_ok([op], {"divId": "signguCd", "key": SGG, "pageNo": 1, "numOfRows": 1, "indsLclsCd": it["indsLclsCd"]}, key, "건수")
            res["lcls"].append({**it, "gangnam": total(c)})
        for it in items(mjs):
            _, c = first_ok([op], {"divId": "signguCd", "key": SGG, "pageNo": 1, "numOfRows": 1, "indsMclsCd": it["indsMclsCd"]}, key, "건수")
            res["mcls"].append({**it, "gangnam": total(c)})
        for m in [s for s in a.small.split(",") if s]:
            sop, sjs = first_ok(SCLS_OPS, {"indsMclsCd": m}, key, f"소분류 {m}")
            for it in items(sjs):
                _, c = first_ok([op], {"divId": "signguCd", "key": SGG, "pageNo": 1, "numOfRows": 1, "indsSclsCd": it["indsSclsCd"]}, key, "건수")
                res["scls"].append({**it, "gangnam": total(c)})
        save("counts.json", res)
        log(f"건수 저장: lcls {len(res['lcls'])} · mcls {len(res['mcls'])} · scls {len(res['scls'])}")
    log(f"호출 {CALLS['n']}회, {time.time() - t0:.1f}초")


if __name__ == "__main__":
    main()
