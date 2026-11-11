"""건축HUB 건축물대장 표제부 요약 → seed/buildings.json (feedback.md §5-1·§5-2, 네트워크 사용, 빌드 때 한 번만).

대상: 범위 안 시연 주소의 PNU + 사업 대표 필지. 원 응답은 build/buildings_raw/{pnu}.json (커밋 안 함).
- 키는 .env의 DATA_GO_KR_SERVICE_KEY. 값은 출력하지 않는다.
- 원 응답이 이미 있으면 다시 조회하지 않는다 (--refresh 로 강제).
- 표제부에 지역·지구 칸이 없으면 같은 서비스의 기본개요(getBrBasisOulnInfo)에서 읽는다.
- 요약에는 건물 정보만 담는다 (사람 이름 등 개인정보 칸은 옮기지 않는다).

사용: python -m pipeline.fetch_buildings [--refresh]
"""
import argparse
import json
import math
import os
from collections import Counter
from datetime import date
from urllib.parse import unquote

import httpx
from dotenv import load_dotenv

from pipeline.common import BUILD, ROOT, SEED, connect_rw, fail, log, setup_stdout

BASE = "https://apis.data.go.kr/1613000/BldRgstHubService"
SOURCE = "건축HUB 건축물대장 표제부(getBrTitleInfo)"
NOT_FOUND = "이 지번에 건축물대장 표제부가 조회되지 않았습니다"
RAW_DIR = BUILD / "buildings_raw"
ZONING_KEYS = {"jiyuk": "jiyukCdNm", "jigu": "jiguCdNm", "guyuk": "guyukCdNm"}


def request_params(pnu: str) -> dict:
    """PNU 19자리 → 건축HUB 요청값 (feedback.md §5-1-4). PNU 산 구분 1=일반·2=산 → platGbCd 0=대지·1=산."""
    return {"sigunguCd": pnu[0:5], "bjdongCd": pnu[5:10], "platGbCd": "0" if pnu[10] == "1" else "1",
            "bun": pnu[11:15], "ji": pnu[15:19]}


def fetch_all(client: httpx.Client, op: str, key: str, pnu: str) -> list[dict]:
    """한 지번의 결과를 페이지를 넘겨 가며 전부 받는다. 오류면 RuntimeError (키는 메시지에 넣지 않는다)."""
    items: list[dict] = []
    page, pages = 1, 1
    while page <= pages:
        res = client.get(f"{BASE}/{op}", params={"serviceKey": key, **request_params(pnu), "numOfRows": 100,
                                                 "pageNo": page, "_type": "json"})
        if res.status_code != 200:
            raise RuntimeError(f"{op} HTTP {res.status_code}")
        try:
            payload = res.json()
        except ValueError:
            raise RuntimeError(f"{op} 응답을 JSON으로 읽을 수 없습니다 (승인키·서비스 신청 확인)") from None
        header = (payload.get("response") or {}).get("header") or {}
        if header.get("resultCode") != "00":
            raise RuntimeError(f"{op} 오류 {header.get('resultCode')}: {header.get('resultMsg')}")
        body = payload["response"].get("body") or {}
        total = int(body.get("totalCount") or 0)
        raw = body.get("items") or {}
        item = raw.get("item") if isinstance(raw, dict) else None
        if item is None:
            break
        items.extend([item] if isinstance(item, dict) else item)   # 1건이면 dict, 여러 건이면 list
        pages = math.ceil(total / 100)
        page += 1
    return items


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else f


def _date(v) -> str | None:
    s = str(v or "").strip()
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 and s.isdigit() else None


def _mode(values) -> str | None:
    vals = [str(v).strip() for v in values if str(v or "").strip()]
    return Counter(vals).most_common(1)[0][0] if vals else None


def zoning_of(items: list[dict]) -> dict:
    out = {}
    for k, field in ZONING_KEYS.items():
        out[k] = _mode(it.get(field) for it in items)
    return out


def summarize(pnu: str, title: list[dict], basis: list[dict], fetched_at: str) -> dict:
    """표제부 여러 건 → 주건축물 기준 요약 (feedback.md §5-1-6). 판단 표현은 붙이지 않는다."""
    if not title:
        return {"pnu": pnu, "found": False, "note": NOT_FOUND, "fetched_at": fetched_at}
    main = [it for it in title if str(it.get("mainAtchGbCdNm") or "").strip() != "부속건축물"] or title
    names = []
    for it in main:
        n = str(it.get("bldNm") or "").strip()
        if n and n not in names:
            names.append(n)
    days = sorted(d for d in (_date(it.get("useAprDay")) for it in main) if d)
    zoning = zoning_of(title)
    if not any(zoning.values()):
        zoning = zoning_of(basis)
    return {
        "pnu": pnu, "found": True, "fetched_at": fetched_at, "source": SOURCE,
        "main_count": len(main),
        "bld_names": names[:3],
        "main_purpose": _mode(it.get("mainPurpsCdNm") for it in main),
        "detail_purposes": sorted({str(v).strip() for it in main for v in (it.get("mainPurpsCdNm"), it.get("etcPurps"))
                                   if v and str(v).strip()}),
        "structure": _mode(it.get("strctCdNm") for it in main),
        "use_apr_day": days[0] if days else None,
        "max_grnd_flr": max((_num(it.get("grndFlrCnt")) or 0 for it in main), default=None),
        "max_ugrnd_flr": max((_num(it.get("ugrndFlrCnt")) or 0 for it in main), default=None),
        "total_hhld": sum(_num(it.get("hhldCnt")) or 0 for it in main),
        "total_area": round(sum(_num(it.get("totArea")) or 0 for it in main), 2),
        "zoning": zoning,
        "note": None,
    }


def targets() -> list[str]:
    con = connect_rw()
    try:
        pnus = {r["pnu"] for r in con.execute("SELECT pnu FROM demo_addresses WHERE in_scope=1 AND pnu IS NOT NULL")}
        pnus |= {r["pnu"] for r in con.execute("SELECT pnu FROM project_parcels")}
    finally:
        con.close()
    return sorted(pnus)


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="원 응답이 있어도 다시 조회")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    key = (os.environ.get("DATA_GO_KR_SERVICE_KEY") or "").strip().strip('"')
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pnus = targets()
    if not pnus:
        fail("대상 PNU가 없습니다 (python -m pipeline.run_all 먼저)")
    need_net = args.refresh or any(not (RAW_DIR / f"{p}.json").exists() for p in pnus)
    if need_net and not key:
        fail(".env에 DATA_GO_KR_SERVICE_KEY가 없습니다 (HUMAN_TODO 참고)")
    if "%" in key:   # 인코딩된 키면 풀어서 넘긴다 (httpx가 한 번 인코딩한다)
        key = unquote(key)

    out, failed = [], []
    with httpx.Client(timeout=20) as client:
        for pnu in pnus:
            raw_path = RAW_DIR / f"{pnu}.json"
            if raw_path.exists() and not args.refresh:
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
            else:
                try:
                    title = fetch_all(client, "getBrTitleInfo", key, pnu)
                    basis = [] if not title or any(zoning_of(title).values()) else \
                        fetch_all(client, "getBrBasisOulnInfo", key, pnu)
                except (RuntimeError, httpx.HTTPError) as e:
                    failed.append(pnu)
                    log(f"  {pnu}: 조회 실패 — {str(e).replace(key, '***') if key else e}")
                    continue
                raw = {"pnu": pnu, "fetched_at": date.today().isoformat(), "title": title, "basis": basis}
                text = json.dumps(raw, ensure_ascii=False, indent=1)
                if key and key in text:
                    fail("원 응답에 승인키가 들어 있어 저장하지 않습니다")
                raw_path.write_text(text, encoding="utf-8")
            out.append(summarize(pnu, raw["title"], raw.get("basis", []), raw["fetched_at"]))

    (SEED / "buildings.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log("PNU | 조회 | 표제부 주건축물 | 건물명 | 주용도 | 지역·지구")
    for b in out:
        if b["found"]:
            z = " · ".join(v for v in b["zoning"].values() if v) or "(칸 없음)"
            log(f"{b['pnu']} | 있음 | {b['main_count']} | {', '.join(b['bld_names'])} | {b['main_purpose']} | {z}")
        else:
            log(f"{b['pnu']} | 없음 | {b['note']}")
    log(f"seed/buildings.json {len(out)}건 작성" + (f", 실패 {len(failed)}건: {', '.join(failed)}" if failed else ""))


if __name__ == "__main__":
    main()
