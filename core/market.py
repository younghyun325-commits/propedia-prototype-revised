"""아파트 단지·실거래 조회 (docs/map/PLAN.md P17 6단계). 표준 라이브러리만, market.db 읽기 전용, 네트워크 없음.

- 단지의 기준은 '실거래 단지'(aptSeq·PNU). 기본 정보(세대수·동수·사용승인일)는 덧붙이는 정보다.
- 금액은 만원 정수. 집계는 해제 거래를 뺀다. 평가·예측·비교 문구는 만들지 않는다 (사실만).
- 면적대 area_band는 빌드(pipeline/build_market_db)와 화면이 같은 함수를 쓴다.
"""

import statistics
from datetime import date

from core.db import loads

# Propedia 표시 구간 (㎡): 하한 포함·상한 미포함. 60.00 → '60~85'
AREA_BANDS = [("~60", 0.0, 60.0), ("60~85", 60.0, 85.0), ("85~102", 85.0, 102.0), ("102~135", 102.0, 135.0),
              ("135~", 135.0, float("inf"))]
BAND_IDS = [b[0] for b in AREA_BANDS]

TRADE_SOURCE = "실거래가(국토교통부 신고 자료, 계약일 기준)"
BASIS_SOURCE = "국토교통부 공동주택 기본 정보"
BUILD_YEAR_NOTE = "실거래 신고 기준"
BASIS_LABEL = {"pending": "기본 정보 확인 전", "not_in_list": "공동주택 기본 정보 목록에 없음", "linked": None}
IMPACT_LABEL = "{name} 영향권 {m}m 안 (Propedia 표시 기준)"
UNAVAILABLE = "실거래 자료 파일(db/market.db)이 없습니다. pipeline.build_market_db를 먼저 실행해 주세요"
NOT_FOUND = "아파트 단지 {id}를 찾지 못했습니다"
DISCLAIMER = ("국토교통부 실거래가 신고 자료를 계약일 기준으로 모은 사실 정보입니다. 신고 뒤 해제되거나 정정될 수 있으며, "
              "개별 가치 판단은 하지 않습니다.")


class MarketUnavailable(Exception):
    """market.db 없음 → 503"""


class ApartmentNotFound(Exception):
    """없는 단지 → 404"""


def area_band(m2: float | None) -> str | None:
    if m2 is None:
        return None
    for bid, lo, hi in AREA_BANDS:
        if lo <= m2 < hi:
            return bid
    return None


def meta(mcon) -> dict:
    return {r["key"]: r["value"] for r in mcon.execute("SELECT key, value FROM meta")}


def _row(mcon, cid: str):
    r = mcon.execute("SELECT * FROM apt_complexes WHERE id=?", (cid,)).fetchone()
    if r is None:
        raise ApartmentNotFound(NOT_FOUND.format(id=cid))
    return r


def _months_back(today: date, n: int) -> str:
    y, m = today.year, today.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}-01"


def default_band(counts_3y: dict) -> str | None:
    """최근 3년 거래가 가장 많은 면적대 (같으면 작은 면적대)"""
    best = [b for b in BAND_IDS if counts_3y.get(b)]
    return max(best, key=lambda b: (counts_3y[b], -BAND_IDS.index(b))) if best else None


def basis_info(r) -> dict:
    st = r["basis_info_status"]
    return {"status": st, "label": BASIS_LABEL.get(st), "kapt_code": r["kapt_code"], "households": r["households"],
            "buildings": r["buildings"], "approval_date": r["approval_date"], "road_addr": r["road_addr"],
            "jibun_addr": r["jibun_addr"], "source": BASIS_SOURCE if st == "linked" else None}


def layer_props(cid: str) -> dict:
    from core.map import _features
    f = next((f for f in _features("apartments") if f["properties"].get("id") == cid), None)
    return (f or {}).get("properties") or {}


def impacts(con, props: dict) -> list[dict]:
    """빌드 때 계산한 '걸친 영향권'(apartments.geojson impacts) + 사업 이름"""
    names = {r["id"]: (loads(r["aliases"], []) or [r["name"]])[0] for r in con.execute(
        "SELECT id, name, aliases FROM projects")} if con is not None else {}
    out = []
    for it in props.get("impacts") or []:
        nm = names.get(it["project_id"], f"사업 {it['project_id']}")
        out.append({"project_id": it["project_id"], "project_name": nm, "buffer_m": it["buffer_m"],
                    "label": IMPACT_LABEL.format(name=nm, m=it["buffer_m"])})
    return out


def sources(m: dict, r) -> list[dict]:
    out = [{"kind": "trade", "label": TRADE_SOURCE, "date": m.get("fetched_on"), "date_label": "수집일"}]
    if r["basis_info_status"] == "linked":
        out.append({"kind": "basis", "label": BASIS_SOURCE, "date": m.get("basis_fetched_on"), "date_label": "기준일"})
    return out


def apartment(mcon, con, cid: str, today: date) -> dict:
    r = _row(mcon, cid)
    m = meta(mcon)
    since12, since3y = _months_back(today, 12), _months_back(today, 36)
    bands = []
    c3 = {}
    for b in BAND_IDS:
        q = mcon.execute("""SELECT SUM(contract_date >= ?) n12, SUM(contract_date >= ?) n3, COUNT(*) n,
                                   MAX(contract_date) last FROM apt_trades
                            WHERE complex_id=? AND area_band=? AND is_cancelled=0""", (since12, since3y, cid, b)).fetchone()
        if q["n"]:
            bands.append({"band": b, "count_12m": q["n12"] or 0, "count_3y": q["n3"] or 0, "count": q["n"],
                          "last_trade_date": q["last"]})
            c3[b] = q["n3"] or 0
    tot = mcon.execute("""SELECT COUNT(*) n, MAX(contract_date) last FROM apt_trades
                          WHERE complex_id=? AND is_cancelled=0""", (cid,)).fetchone()
    ncanc = mcon.execute("SELECT COUNT(*) FROM apt_trades WHERE complex_id=? AND is_cancelled=1", (cid,)).fetchone()[0]
    props = layer_props(cid)
    return {
        "id": cid, "name": r["name"], "aliases": loads(r["aliases"], []), "apt_seq": r["apt_seq"],
        "pnus": loads(r["pnus"], []), "jibuns": props.get("jibuns") or [], "bjd_code": r["bjd_code"],
        "lat": r["lat"], "lon": r["lon"], "build_year": r["build_year"], "build_year_note": BUILD_YEAR_NOTE,
        "basis": basis_info(r),
        "trade_summary": {"bands": bands, "default_band": default_band(c3) or (bands[0]["band"] if bands else None),
                          "count": tot["n"], "cancelled_count": ncanc, "last_trade_date": tot["last"],
                          "since_12m": since12, "since_3y": since3y, "from": m.get("trade_from"), "to": m.get("trade_to")},
        "impacts": impacts(con, props),
        "sources": sources(m, r), "as_of": r["as_of"], "disclaimer": DISCLAIMER,
    }


def trades(mcon, cid: str, band: str | None = None, from_: str | None = None, limit: int = 20,
           as_of: date | None = None) -> dict:
    """as_of(P19): 계약일 ≤ 기준일 거래만. 월별은 기준일이 든 달만 원자료에서 다시 센다 (빌드와 같은 규칙: 해제 제외, 중위값)."""
    _row(mcon, cid)
    if band is not None and band not in BAND_IDS:
        raise ValueError("면적대(band)는 " + "·".join(BAND_IDS) + " 중 하나입니다")
    if from_:
        date.fromisoformat(from_ if len(from_) == 10 else f"{from_}-01")
        from_ = from_ if len(from_) == 10 else f"{from_}-01"
    where, args = ["complex_id=?"], [cid]
    if band:
        where.append("area_band=?")
        args.append(band)
    if from_:
        where.append("contract_date>=?")
        args.append(from_)
    if as_of:
        where.append("contract_date<=?")
        args.append(as_of.isoformat())
    w = " AND ".join(where)
    mw, margs = ["complex_id=?"], [cid]
    if from_:
        mw.append("ym>=?")
        margs.append(from_[:7])
    if as_of:                      # 기준일이 든 달은 아래에서 원자료로 다시 센다
        mw.append("ym<?")
        margs.append(as_of.isoformat()[:7])
    if band:       # 면적대 하나 → 그 달 중위값·건수 (해제 제외, 빌드 때 계산)
        monthly = [dict(x) for x in mcon.execute(
            f"""SELECT ym, median_amount, count FROM apt_trade_monthly WHERE {' AND '.join(mw)} AND area_band=?
                ORDER BY ym""", [*margs, band])]
    else:          # 면적대를 합친 월별 건수만 (중위값은 면적대별로만 낸다)
        monthly = [{"ym": x["ym"], "median_amount": None, "count": x["c"]} for x in mcon.execute(
            f"SELECT ym, SUM(count) c FROM apt_trade_monthly WHERE {' AND '.join(mw)} GROUP BY ym ORDER BY ym", margs)]
    if as_of and (not from_ or from_[:7] <= as_of.isoformat()[:7]):
        ym = as_of.isoformat()[:7]
        part = [x["amount_10k_won"] for x in mcon.execute(
            f"""SELECT amount_10k_won FROM apt_trades WHERE {w} AND is_cancelled=0 AND area_band IS NOT NULL
                AND substr(contract_date, 1, 7)=?""", [*args, ym])]
        if part:
            monthly.append({"ym": ym, "median_amount": float(statistics.median(part)) if band else None,
                            "count": len(part), "partial_to": as_of.isoformat()})
    cols = ("contract_date, exclusive_area_m2, area_band, floor, amount_10k_won, deal_type, is_cancelled, "
            "cancelled_date, apt_dong")
    points = [dict(x) for x in mcon.execute(
        f"SELECT contract_date, amount_10k_won, exclusive_area_m2, floor, is_cancelled FROM apt_trades WHERE {w} "
        "ORDER BY contract_date, id", args)]
    recent = [dict(x) for x in mcon.execute(
        f"SELECT {cols} FROM apt_trades WHERE {w} ORDER BY contract_date DESC, id DESC LIMIT ?", [*args, limit])]
    return {"id": cid, "band": band, "from": from_, "as_of": as_of.isoformat() if as_of else None,
            "monthly": monthly, "points": points, "recent": recent,
            "source": TRADE_SOURCE, "fetched_on": meta(mcon).get("fetched_on")}


def nearby_for_project(con, pid: int) -> dict:
    """사업 영향권 안 단지 (250m·500m 구분). 이름·준공연도·최근 거래일만 — 집계 없음. market.db 없이 레이어만 읽는다."""
    from core.map import _features
    out = {"250": [], "500": []}
    for f in _features("apartments"):
        p = f["properties"]
        hit = next((i for i in p.get("impacts") or [] if i["project_id"] == pid), None)
        if hit:
            out[str(hit["buffer_m"])].append({"id": p["id"], "name": p["name"], "build_year": p.get("build_year"),
                                              "last_trade_date": p.get("last_trade_date")})
    for k in out:
        out[k].sort(key=lambda x: x["name"])
    return out


def bbox_of(props: dict) -> list | None:
    from core.map import _bbox, _features
    f = next((f for f in _features("apartments") if f["properties"].get("id") == props.get("id")), None)
    return _bbox(f["geometry"]) if f and f.get("geometry") else None


def feature_apartment(mcon, con, cid: str, today: date) -> dict:
    """인스펙터 공통 틀 (core/map.map_feature와 같은 키)"""
    a = apartment(mcon, con, cid, today)
    badges = []
    if a["basis"]["label"]:
        badges.append({"text": a["basis"]["label"], "tone": "muted"})
    for i in a["impacts"]:
        badges.append({"text": f"영향권 {i['buffer_m']}m", "tone": "info"})
    sub = " · ".join(x for x in [", ".join(a["jibuns"][:2]),
                                 f"{a['build_year']}년 준공({BUILD_YEAR_NOTE})" if a["build_year"] else None] if x)
    return {"kind": "apartment", "id": cid, "kind_label": "아파트 단지", "title": a["name"], "subtitle": sub or None,
            "badges": badges, "unverified": False, "as_of": today.isoformat(), "data_as_of": a["as_of"],
            "bbox": bbox_of({"id": cid}), "sections": {"apartment": a}, "evidence": [], "disclaimer": DISCLAIMER}
