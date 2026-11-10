"""공동주택 기본 정보 덧붙이기 (docs/map/PLAN.md P17 5단계). 네트워크 사용, 빌드 때만. 멱등.

단지의 기준은 실거래 단지다. 이 스크립트는 db/market.db apt_complexes의 기본 정보 열만 채운다
(kapt_code·households·buildings·approval_date·road_addr·jibun_addr·basis_info_status). 3·4단계 결과는 덮어쓰지 않는다.

1. 단지 목록(AptListService4/getSigunguAptList4, 강남구) 첫 단지로 기본 정보(AptBasisInfoServiceV5/getAphusBassInfoV5)를
   1회 호출해 등록 여부를 확인한다. SERVICE_KEY_IS_NOT_REGISTERED_ERROR면 아무것도 바꾸지 않고 종료 코드 0.
2. 등록됐으면 실제 응답 필드를 표로 보여 주고 견본(tests/fixtures/apt/basis_*.json)을 남긴 뒤
   단지 목록 전체 → 기본 정보 → 지번 주소 → PNU → apt_complexes와 PNU로 연결, 안 되면 법정동 + 정규화 단지명.
   - 기본 정보 응답의 필드 이름은 실제 응답을 본 뒤에 FIELD_MAP에 확정한다 (확인 전에는 코드에 쓰지 않음).
3. 실거래 단지 중 목록과 연결되지 않은 것은 'not_in_list' ('공동주택 기본 정보 목록에 없음'으로만 표시, 이유는 단정하지 않음).
- 캐시 build/apt_basis_raw/ (키 검사 후 저장). 키 값·키가 든 URL은 출력·저장하지 않는다.

사용: python -m pipeline.fetch_apt_basis [--check-only]
"""
import argparse
import json
import sqlite3
import sys
import time

import httpx

from pipeline.check_market_api import BASE, _key, has_key, scrub
from pipeline.common import BUILD, ROOT, log, setup_stdout

LIST_URL = f"{BASE}/AptListService4/getSigunguAptList4"
BASIS_URL = f"{BASE}/AptBasisInfoServiceV5/getAphusBassInfoV5"
RAW = BUILD / "apt_basis_raw"
DB = ROOT / "db" / "market.db"
NOT_REGISTERED = "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"
SLEEP = 0.2
# 실제 응답을 확인한 뒤 채운다: {저장 열: 응답 필드 이름}
FIELD_MAP: dict[str, str] = {}


class NotRegistered(Exception):
    pass


def get(client, key: str, url: str, params: dict, cache_name: str) -> dict:
    cache = RAW / cache_name
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    time.sleep(SLEEP)
    try:
        r = client.get(url, params={"serviceKey": key, "_type": "json", **params})
    except httpx.HTTPError as e:
        raise RuntimeError(f"요청 실패 ({type(e).__name__})") from None
    body = scrub(r.text, key)
    if NOT_REGISTERED in body:
        raise NotRegistered(body[:200])
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {body[:120]}")
    if has_key(body, key):
        raise RuntimeError("응답에 키 문자열이 있어 저장하지 않습니다")
    d = json.loads(body)
    RAW.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(d, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return d


def list_items(d: dict) -> tuple[list[dict], int]:
    bd = ((d.get("response") or d).get("body") or {})
    items = bd.get("items")
    if isinstance(items, dict):
        items = items.get("item", [])
    items = items if isinstance(items, list) else [items] if items else []
    return items, int(bd.get("totalCount") or len(items))


def all_list(client, key: str) -> list[dict]:
    out, page = [], 1
    while True:
        items, total = list_items(get(client, key, LIST_URL, {"sigunguCode": "11680", "pageNo": page,
                                                              "numOfRows": 1000}, f"list_p{page}.json"))
        out += items
        if len(out) >= total or not items:
            return out
        page += 1


def set_meta(vals: dict) -> None:
    """market.db meta만 바꾼다 (기본 정보 열 외의 3·4단계 결과는 건드리지 않음)"""
    con = sqlite3.connect(DB)
    con.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", sorted(vals.items()))
    con.commit()
    con.close()


def reopen_todo() -> bool:
    p = ROOT / "HUMAN_TODO.md"
    t = p.read_text(encoding="utf-8")
    if "15058453 활용신청" in t:            # 이미 다시 열려 있음
        return False
    lines = t.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("| 28 |"):
            cells = ln.split("|")             # 이전 상태 문구는 지우지 않고 뒤에 둔다
            cells[-2] = (" **다시 열림 (P17)** — 기본 정보(AptBasisInfoServiceV5)는 키 미등록(SERVICE_KEY_IS_NOT_REGISTERED_ERROR). "
                         "15058453 활용신청 후 `python -m pipeline.fetch_apt_basis` 실행. (이전) "
                         + cells[-2].strip().replace("**", "") + " ")
            lines[i] = "|".join(cells)
            break
    p.write_text("\n".join(lines), encoding="utf-8", newline="")
    return True


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    if not DB.is_file():
        log("db/market.db가 없습니다 (pipeline.build_market_db 먼저)")
        return 1
    key = _key()
    with httpx.Client(timeout=30) as c:
        first, list_total = list_items(get(c, key, LIST_URL, {"sigunguCode": "11680", "pageNo": 1, "numOfRows": 1000},
                                           "list_p1.json"))
        kapt = first[0]["kaptCode"]
        try:
            d = get(c, key, BASIS_URL, {"kaptCode": kapt}, f"basis_{kapt}.json")
        except NotRegistered:
            set_meta({"list_total": str(list_total), "basis_info_check": "not_registered"})
            log(f"기본 정보 API 미등록 ({NOT_REGISTERED}) — 이 단계를 건너뜁니다. basis_info_status는 pending 그대로. "
                f"단지 목록 {list_total}개")
            state = "다시 열었습니다" if reopen_todo() else "이미 열려 있습니다"
            log(f"HUMAN_TODO 28 {state}: 15058453 활용신청 후 python -m pipeline.fetch_apt_basis 실행")
            return 0
        item = ((d.get("response") or d).get("body") or {}).get("item") or {}
        log(f"기본 정보 응답 필드 {len(item)}개 (단지 {kapt}):")
        for k, v in item.items():
            log(f"  {k}: {v!r}")
        fx = ROOT / "tests" / "fixtures" / "apt" / f"basis_{kapt}.json"
        txt = json.dumps(d, ensure_ascii=False, indent=1)
        if not has_key(txt, key):
            fx.write_text(txt + "\n", encoding="utf-8", newline="\n")
        if a.check_only or not FIELD_MAP:
            log("FIELD_MAP(저장 열 ↔ 응답 필드)을 위 필드로 확정한 뒤 다시 실행하세요. DB는 바꾸지 않았습니다.")
            return 0
        listed = all_list(c, key)
        basis = {}
        for it in listed:
            d = get(c, key, BASIS_URL, {"kaptCode": it["kaptCode"]}, f"basis_{it['kaptCode']}.json")
            basis[it["kaptCode"]] = ((d.get("response") or d).get("body") or {}).get("item") or {}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT id, name, aliases, pnus, bjd_code FROM apt_complexes")]
    res = link_basis(listed, basis, rows)
    for cid, vals in res["linked"].items():
        con.execute(f"UPDATE apt_complexes SET {', '.join(f'{k}=?' for k in vals)}, basis_info_status='linked' "
                    "WHERE id=?", [*vals.values(), cid])
    con.execute("UPDATE apt_complexes SET basis_info_status='not_in_list' WHERE basis_info_status!='linked'")
    today = time.strftime("%Y-%m-%d")
    for k, v in (("basis_fetched_on", today), ("list_total", str(len(listed))), ("basis_info_check", "linked"),
                 ("basis_list_unlinked", json.dumps(res["unlinked"], ensure_ascii=False))):
        con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    log(f"기본 정보 연결 단지 {len(res['linked'])} / 단지 목록 {len(listed)} · 목록 중 실거래 단지와 연결 안 됨 "
        f"{len(res['unlinked'])} (거래가 없는 단지일 수 있음, 지도에 올리지 않음)")
    for u in res["unlinked"]:
        log(f"  {u['kaptCode']} {u['kaptName']} ({u.get('jibun') or '-'})")
    return 0


def jibun_pnu(bjd_code: str | None, addr: str | None) -> str | None:
    """'서울특별시 강남구 대치동 316 은마아파트' + 법정동코드 → PNU (산 지번은 2)"""
    import re
    if not bjd_code or not addr:
        return None
    m = re.search(r"동\s+(산\s*)?(\d{1,4})(?:-(\d{1,4}))?", addr)
    if not m:
        return None
    return f"{bjd_code}{'2' if m.group(1) else '1'}{int(m.group(2)):04d}{int(m.group(3) or 0):04d}"


def link_basis(listed: list[dict], basis: dict, rows: list[dict]) -> dict:
    """단지 목록·기본 정보 → 실거래 단지 id. ① PNU ② 법정동 + 정규화 단지명(유일할 때만). 순수 함수 (테스트 대상)"""
    from pipeline.apt_names import norm_name
    by_pnu, by_name = {}, {}
    for r in rows:
        for p in json.loads(r["pnus"]):
            by_pnu.setdefault(p, r["id"])
        for nm in [r["name"], *json.loads(r["aliases"])]:
            by_name.setdefault((r["bjd_code"], norm_name(nm)), set()).add(r["id"])
    linked, unlinked = {}, []
    for it in listed:
        b = basis.get(it["kaptCode"]) or {}
        vals = {"kapt_code": it["kaptCode"], **{col: b.get(f) for col, f in FIELD_MAP.items()}}
        pnu = jibun_pnu(it.get("bjdCode"), vals.get("jibun_addr"))
        cid = by_pnu.get(pnu) if pnu else None
        if cid is None:
            hits = by_name.get((it.get("bjdCode"), norm_name(it.get("kaptName"))), set())
            cid = next(iter(hits)) if len(hits) == 1 else None
        if cid and cid not in linked:
            linked[cid] = vals
        else:
            unlinked.append({"kaptCode": it["kaptCode"], "kaptName": it.get("kaptName"), "jibun": vals.get("jibun_addr")})
    return {"linked": linked, "unlinked": unlinked}


if __name__ == "__main__":
    sys.exit(main())
