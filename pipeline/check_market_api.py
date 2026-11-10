"""P17 1단계: 공공데이터포털 API 3종을 1~2건만 호출해 실제 오퍼레이션·요청 변수·응답 필드를 확인한다 (docs/map/PLAN.md P17).

- 키: .env DATA_GO_KR_SERVICE_KEY (일반 인증키 Decoding). httpx params로 넘겨 한 번만 인코딩한다.
  키 값·키가 든 URL은 출력·저장하지 않는다. 예외는 종류 이름만 출력하고, 응답 본문은 키 문자열을 가린 뒤에만 다룬다.
- 오퍼레이션 이름은 기술문서에 없어(2026-11-11 확인) 후보를 차례로 시도하고, 맞은 이름을 보고한다.
- 원 응답(키 검사 후): build/market_api_check/ (커밋 안 함)
- 견본: tests/fixtures/rtms/, tests/fixtures/apt/ — 항목 수를 줄이고 개인 정보 성격 필드는 뺀다.

사용: python -m pipeline.check_market_api [--trade-only|--list-only] [--kapt CODE]
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote, quote_plus

import httpx
from dotenv import load_dotenv

from pipeline.common import BUILD, ROOT, fail, log, setup_stdout

BASE = "https://apis.data.go.kr/1613000"
TRADE = (f"{BASE}/RTMSDataSvcAptTradeDev", ["getRTMSDataSvcAptTradeDev"])
LIST = (f"{BASE}/AptListService4", ["getSigunguAptList4", "getSigunguAptList3", "getSigunguAptList"])
BASIS = (f"{BASE}/AptBasisInfoServiceV5", ["getAphusBassInfoV5", "getAphusBassInfoV4", "getAphusBassInfo"])

RAW = BUILD / "market_api_check"
FIX_RTMS = ROOT / "tests" / "fixtures" / "rtms"
FIX_APT = ROOT / "tests" / "fixtures" / "apt"
SAMPLE_NOTE = "P17 1단계 견본: 항목 수를 줄이고 개인 정보 성격 필드는 뺌 (키 없음)"

# 개인 정보 성격 필드 후보 (이름에 이 조각이 들어가면 값을 가린다)
# 확인(2026-11-11): buyerGbn·slerGbn(거래 주체 구분), estateAgentSggNm(중개사 소재지). rgstDate(등기일자)는 해당 없음
PERSONAL_PARTS = ("buyer", "sler", "seller", "agent", "owner")
SVC_KEY_RE = re.compile(r"(?i)(servicekey=)[^&\"'<>\s]+")


def _key() -> str:
    load_dotenv(ROOT / ".env")
    k = (os.environ.get("DATA_GO_KR_SERVICE_KEY") or "").strip()
    if not k:
        fail(".env의 DATA_GO_KR_SERVICE_KEY가 비어 있습니다")
    return k


def scrub(text: str, key: str) -> str:
    for v in {key, quote(key, safe=""), quote_plus(key)}:
        text = text.replace(v, "***")
    return SVC_KEY_RE.sub(r"\1***", text)


def has_key(text: str, key: str) -> bool:
    return any(v in text for v in {key, quote(key, safe=""), quote_plus(key)})


def call(url: str, params: dict, key: str) -> tuple[int | None, str]:
    try:
        r = httpx.get(url, params={"serviceKey": key, **params}, timeout=30)
    except httpx.HTTPError as e:
        return None, f"요청 실패 ({type(e).__name__})"
    return r.status_code, scrub(r.text, key)


def is_personal(name: str) -> bool:
    n = name.lower()
    return any(p in n for p in PERSONAL_PARTS)


def try_ops(svc: tuple, params: dict, key: str, tag: str) -> tuple[str | None, int | None, str]:
    base, ops = svc
    for op in ops:
        st, body = call(f"{base}/{op}", params, key)
        log(f"[{tag}] {op}: HTTP {st} · 본문 앞부분 {body[:160].replace(chr(10), ' ')!r}")
        if st == 200 and not re.search(r"(?i)unexpected errors|api not found|<returnReasonCode>", body[:400]):
            return op, st, body
    return None, st, body


def save_raw(name: str, body: str, key: str) -> None:
    if has_key(body, key):
        fail(f"{name}: 응답에 키 문자열이 있어 저장하지 않습니다")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_text(body, encoding="utf-8", newline="\n")


def xml_items(body: str) -> tuple[dict, list[dict]]:
    root = ET.fromstring(body)
    head = {e.tag: (e.text or "").strip() for e in root.iter() if e.tag in
            ("resultCode", "resultMsg", "numOfRows", "pageNo", "totalCount")}
    items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
    return head, items


def trade(key: str, offline: bool = False) -> None:
    raw = RAW / "trade_202610_p1.xml"
    if offline and raw.exists():          # 저장한 원 응답으로 견본만 다시 만든다 (네트워크 안 씀)
        body = raw.read_text(encoding="utf-8")
    else:
        op, st, body = try_ops(TRADE, {"LAWD_CD": "11680", "DEAL_YMD": "202610", "pageNo": 1, "numOfRows": 1000},
                               key, "실거래")
        if not op:
            fail(f"실거래: 맞는 오퍼레이션 없음 (마지막 HTTP {st})")
        save_raw("trade_202610_p1.xml", body, key)
    head, items = xml_items(body)
    log(f"[실거래] 머리: {head} · 받은 항목 {len(items)}")
    names: list[str] = []
    for it in items:
        names += [k for k in it if k not in names]
    filled = {n: sum(1 for it in items if it.get(n)) for n in names}
    ex = items[0] if items else {}
    log("[실거래] 필드 (이름 · 값이 있는 항목 수 · 예시):")
    for n in names:
        v = "(가림)" if is_personal(n) else next((it[n] for it in items if it.get(n)), "")
        log(f"  {n} · {filled[n]}/{len(items)} · {v!r}")
    # 견본: 앞 10건(해제 거래가 있으면 1건 포함), 개인 정보 성격 필드는 견본값
    cancel = [it for it in items if any("cdeal" in k.lower() and it.get(k) for k in it)]
    keep = items[:9] + (cancel[:1] if cancel and cancel[0] not in items[:9] else items[9:10])
    root = ET.fromstring(body)
    parent = next(root.iter("items"), None)
    if parent is not None:
        for it in list(parent):
            parent.remove(it)
        for d in keep:
            e = ET.SubElement(parent, "item")
            for k, v in d.items():
                if not is_personal(k):        # 개인 정보 성격 필드는 견본에 넣지 않는다
                    ET.SubElement(e, k).text = v
    for e in root.iter("totalCount"):
        e.text = e.text  # 원래 총건수 유지
    FIX_RTMS.mkdir(parents=True, exist_ok=True)
    out = f"<!-- {SAMPLE_NOTE} -->\n" + ET.tostring(root, encoding="unicode")
    if has_key(out, key):
        fail("견본에 키 문자열이 있습니다")
    (FIX_RTMS / "trade_202610_p1.xml").write_text(out + "\n", encoding="utf-8", newline="\n")
    log(f"[실거래] 견본 {len(keep)}건 → tests/fixtures/rtms/trade_202610_p1.xml · 원래 총건수 {head.get('totalCount')}")
    # ⑤ 대조용: 단지 일련번호 후보 필드 예시
    seq = [n for n in names if "seq" in n.lower() or "cd" in n.lower()]
    log(f"[실거래] 코드성 필드: {seq}")


def json_body(body: str) -> dict:
    try:
        return json.loads(body)
    except ValueError:
        fail(f"JSON이 아닌 응답: {body[:200]!r}")


def apt_list(key: str) -> str | None:
    op, st, body = try_ops(LIST, {"sigunguCode": "11680", "pageNo": 1, "numOfRows": 1000}, key, "단지 목록")
    if not op:
        log(f"[단지 목록] 맞는 오퍼레이션 없음 (마지막 HTTP {st})")
        return None
    save_raw("list_11680_p1.json", body, key)
    d = json_body(body)
    log(f"[단지 목록] 최상위 키: {list(d)} · response 키: {list((d.get('response') or {}))}")
    resp = d.get("response") or d
    bd = resp.get("body") or {}
    log(f"[단지 목록] header: {resp.get('header')} · body(items 제외): { {k: bd[k] for k in bd if k != 'items'} }")
    items = bd.get("items")
    if isinstance(items, dict):
        items = items.get("item", items)
    items = items if isinstance(items, list) else [items] if items else []
    log(f"[단지 목록] 받은 항목 {len(items)}")
    if items:
        log(f"[단지 목록] 필드: {list(items[0])}")
        for it in items[:3]:
            log(f"  예시 {it}")
    sample = json.loads(json.dumps(d))
    tgt = (sample.get("response") or sample).get("body") or {}
    its = tgt.get("items")
    if isinstance(its, dict) and isinstance(its.get("item"), list):
        its["item"] = its["item"][:10]
    elif isinstance(its, list):
        tgt["items"] = its[:10]
    sample["_sample_note"] = SAMPLE_NOTE
    FIX_APT.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(sample, ensure_ascii=False, indent=1)
    if has_key(txt, key):
        fail("견본에 키 문자열이 있습니다")
    (FIX_APT / "list_11680_p1.json").write_text(txt + "\n", encoding="utf-8", newline="\n")
    code_field = next((k for k in (items[0] if items else {}) if "code" in k.lower()), None)
    return items[0][code_field] if code_field else None


def basis(key: str, kapt: str) -> None:
    op, st, body = try_ops(BASIS, {"kaptCode": kapt}, key, "기본 정보")
    if not op:
        log(f"[기본 정보] 맞는 오퍼레이션 없음 (마지막 HTTP {st}) — 활용신청 여부 확인 필요")
        return
    save_raw(f"basis_{kapt}.json", body, key)
    d = json_body(body)
    resp = d.get("response") or d
    log(f"[기본 정보] header: {resp.get('header')}")
    item = (resp.get("body") or {}).get("item") or {}
    log(f"[기본 정보] 필드 {len(item)}개:")
    for k, v in item.items():
        log(f"  {k}: {('(가림)' if is_personal(k) else v)!r}")
    sample = json.loads(json.dumps(d))
    sample["_sample_note"] = SAMPLE_NOTE
    txt = json.dumps(sample, ensure_ascii=False, indent=1)
    if has_key(txt, key):
        fail("견본에 키 문자열이 있습니다")
    (FIX_APT / f"basis_{kapt}.json").write_text(txt + "\n", encoding="utf-8", newline="\n")


def key_scan(key: str) -> None:
    bad = []
    for d in (ROOT / "tests" / "fixtures", BUILD):
        for f in d.rglob("*"):
            if f.is_file() and f.stat().st_size < 50_000_000:
                try:
                    if has_key(f.read_text(encoding="utf-8", errors="ignore"), key):
                        bad.append(str(f.relative_to(ROOT)))
                except OSError:
                    pass
    log(f"[키 검사] tests/fixtures·build 안 키 문자열(원 키·URL 인코딩): {len(bad)}건 {bad}")


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--trade-only", action="store_true")
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--offline", action="store_true", help="실거래는 저장한 원 응답으로 견본만 다시 만든다")
    ap.add_argument("--kapt", help="기본 정보에 쓸 단지 코드 (없으면 단지 목록 첫 단지)")
    a = ap.parse_args()
    key = _key()
    if not a.list_only:
        trade(key, a.offline)
    if not a.trade_only:
        code = apt_list(key)
        if a.kapt or code:
            basis(key, a.kapt or code)
    key_scan(key)


if __name__ == "__main__":
    sys.exit(main())
