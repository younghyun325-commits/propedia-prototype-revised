"""강남구 아파트 매매 실거래가 상세 수집 (docs/map/PLAN.md P17 2단계). 네트워크 사용, 빌드 때만.

- 공공데이터포털 RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev 만 쓴다 (다른 사이트 스크래핑 금지).
- LAWD_CD=11680, 2016-01부터 이번 달까지 월별, numOfRows=1000, totalCount로 쪽 수 계산.
- 원 응답: build/rtms_raw/{YYYYMM}_p{n}.xml (커밋 안 함, 키 문자열 검사 후 저장)
- 체크포인트: build/trades_checkpoint.json {"done": [YYYYMM...]} — 완료 월은 건너뛴다. 최근 2개월은 매번 다시 받는다 (신고 기한 30일).
- 결과 코드가 정상이 아니면(한도 초과 포함) 체크포인트를 저장하고 종료 코드 2.
- 리포트: build/trades_report.csv (월·쪽 수·건수·해제 건수·이번 실행 호출 수·초)
- 키 값·키가 든 URL은 출력·저장하지 않는다.

사용: python -m pipeline.fetch_trades [--probe] [--from 201601] [--to 202611] [--max-calls N]
"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

from pipeline.check_market_api import _key, has_key, scrub
from pipeline.common import BUILD, log, setup_stdout
from pipeline.rtms_parse import RtmsError, check_head, parse_xml

URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
LAWD = "11680"
ROWS = 1000
RAW = BUILD / "rtms_raw"
CKPT = BUILD / "trades_checkpoint.json"
REPORT = BUILD / "trades_report.csv"
START = "201601"
PROBE_MONTHS = ("201601", "201901", "202201", "202401")
PROBE_FIELDS = ("aptSeq", "umdCd", "landCd", "bonbun", "bubun", "cdealType", "cdealDay", "rgstDate", "dealingGbn")
SLEEP = 0.2
KST = timezone(timedelta(hours=9))


class Calls:
    n = 0
    sec = 0.0


def this_month() -> str:
    return datetime.now(KST).strftime("%Y%m")


def months(a: str, b: str) -> list[str]:
    y, m = int(a[:4]), int(a[4:])
    out = []
    while f"{y:04d}{m:02d}" <= b:
        out.append(f"{y:04d}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def recent(last: str, k: int = 2) -> set[str]:
    ms = months("200001", last)
    return set(ms[-k:])


def fetch_page(client: httpx.Client, key: str, ym: str, page: int) -> str:
    time.sleep(SLEEP)
    t0 = time.perf_counter()
    try:
        r = client.get(URL, params={"serviceKey": key, "LAWD_CD": LAWD, "DEAL_YMD": ym,
                                    "pageNo": page, "numOfRows": ROWS})
    except httpx.HTTPError as e:
        raise RtmsError("NET", f"요청 실패 ({type(e).__name__})") from None
    finally:
        Calls.n += 1
        Calls.sec += time.perf_counter() - t0
    body = scrub(r.text, key)
    if r.status_code != 200:
        raise RtmsError(f"HTTP{r.status_code}", body[:120])
    if "<response" not in body[:300] and "<OpenAPI_ServiceResponse" not in body[:300]:
        raise RtmsError("FORMAT", body[:120])
    if has_key(body, key):
        raise RtmsError("KEY", "응답에 키 문자열이 있어 저장하지 않습니다")
    return body


def save(name: str, body: str) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_text(body, encoding="utf-8", newline="\n")


def month_files(ym: str) -> list:
    return sorted(RAW.glob(f"{ym}_p*.xml"), key=lambda p: int(p.stem.split("_p")[1]))


def fetch_month(client, key: str, ym: str) -> tuple[int, int, int]:
    """→ (쪽 수, 건수, 해제 건수). 실패하면 RtmsError (그 달 파일은 지운다: 반쪽 저장 방지)"""
    body = fetch_page(client, key, ym, 1)
    head, items = parse_xml(body)
    check_head(head)
    total = int(head.get("totalCount") or 0)
    pages = max(1, -(-total // ROWS))
    bodies = [body]
    for p in range(2, pages + 1):
        b = fetch_page(client, key, ym, p)
        h, its = parse_xml(b)
        check_head(h)
        bodies.append(b)
        items += its
    for old in month_files(ym):
        old.unlink()
    for i, b in enumerate(bodies, 1):
        save(f"{ym}_p{i}.xml", b)
    if len(items) != total:
        log(f"  ! {ym}: 받은 항목 {len(items)} ≠ totalCount {total}")
    return pages, len(items), sum(1 for it in items if (it.get("cdealType") or "").upper() == "O")


def count_cached(ym: str) -> tuple[int, int, int]:
    fs = month_files(ym)
    n = c = 0
    for f in fs:
        _, its = parse_xml(f.read_text(encoding="utf-8"))
        n += len(its)
        c += sum(1 for it in its if (it.get("cdealType") or "").upper() == "O")
    return len(fs), n, c


def read_ckpt() -> dict:
    try:
        return json.loads(CKPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_ckpt() -> set[str]:
    return set(read_ckpt().get("done") or [])


def save_ckpt(done: set[str], fetched: bool = False) -> None:
    """fetched_on = 마지막으로 응답을 받은 날 (KST). 화면의 '수집일'"""
    on = datetime.now(KST).date().isoformat() if fetched else read_ckpt().get("fetched_on")
    CKPT.parent.mkdir(parents=True, exist_ok=True)
    CKPT.write_text(json.dumps({"done": sorted(done), "fetched_on": on}, indent=1) + "\n",
                    encoding="utf-8", newline="\n")


def probe(key: str) -> None:
    rows = []
    with httpx.Client(timeout=30) as c:
        for ym in PROBE_MONTHS:
            try:
                body = fetch_page(c, key, ym, 1)
                head, items = parse_xml(body)
                check_head(head)
            except RtmsError as e:
                log(f"{ym}: 결과 코드 {e.code} — {e.msg[:80]}")
                continue
            save(f"probe_{ym}.xml", body)
            names = {k for it in items for k in it}
            row = {"ym": ym, "total": head.get("totalCount"), "items": len(items)}
            for f in PROBE_FIELDS:
                if f not in names:
                    row[f] = "필드 없음"
                else:
                    empty = sum(1 for it in items if not it.get(f))
                    row[f] = f"{empty / len(items):.0%} 빈" if items else "-"
            rows.append(row)
    cols = ["ym", "total", "items", *PROBE_FIELDS]
    log("| " + " | ".join(cols) + " |")
    log("|" + "---|" * len(cols))
    for r in rows:
        log("| " + " | ".join(str(r.get(k, "")) for k in cols) + " |")
    log(f"호출 {Calls.n}회 · {Calls.sec:.1f}초")


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--from", dest="start", default=START)
    ap.add_argument("--to", dest="end", default=None)
    ap.add_argument("--max-calls", type=int, default=None, help="이 호출 수를 넘으면 멈춤 (이어받기 시험용)")
    a = ap.parse_args()
    key = _key()
    if a.probe:
        probe(key)
        return 0
    last = a.end or this_month()
    allm = months(a.start, last)
    again = recent(this_month())
    done = load_ckpt() - again
    t0 = time.perf_counter()
    report: dict[str, dict] = {}
    stopped = None
    with httpx.Client(timeout=30) as c:
        for ym in allm:
            if ym in done and month_files(ym):
                pages, n, cn = count_cached(ym)
                report[ym] = {"ym": ym, "pages": pages, "count": n, "cancelled": cn, "fetched": 0}
                continue
            if a.max_calls is not None and Calls.n >= a.max_calls:
                stopped = f"--max-calls {a.max_calls} 도달"
                break
            before = Calls.n
            try:
                pages, n, cn = fetch_month(c, key, ym)
            except RtmsError as e:
                stopped = f"{ym}: 결과 코드 {e.code} {e.msg[:80]}"
                break
            done.add(ym)
            save_ckpt(done, fetched=True)
            report[ym] = {"ym": ym, "pages": pages, "count": n, "cancelled": cn, "fetched": Calls.n - before}
            log(f"{ym}: {pages}쪽 · {n}건 · 해제 {cn}")
    save_ckpt(done)
    with open(REPORT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ym", "pages", "count", "cancelled", "fetched"])
        w.writeheader()
        for ym in sorted(report):
            w.writerow(report[ym])
        w.writerow({"ym": "합계", "pages": sum(r["pages"] for r in report.values()),
                    "count": sum(r["count"] for r in report.values()),
                    "cancelled": sum(r["cancelled"] for r in report.values()), "fetched": Calls.n})
    tot = sum(r["count"] for r in report.values())
    log(f"월 {len(report)}/{len(allm)} · 거래 {tot}건 · 해제 {sum(r['cancelled'] for r in report.values())}건 · "
        f"이번 실행 호출 {Calls.n}회 · 호출 {Calls.sec:.1f}초 · 전체 {time.perf_counter() - t0:.1f}초 → {REPORT.name}")
    if stopped:
        log(f"멈춤: {stopped}. 체크포인트를 저장했습니다 — 내일 이어서 실행하세요 (python -m pipeline.fetch_trades)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
