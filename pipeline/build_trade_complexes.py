"""실거래 단지와 위치 (docs/map/PLAN.md P17 3단계). 브이월드 필지 경계만 네트워크 사용(캐시 있으면 안 씀).

단지의 기준은 '실거래 단지'다 (영현 결정 2026-11-11):
- 단지 키: aptSeq가 있으면 aptSeq, 없으면 'pnu:{PNU}'. 같은 aptSeq가 여러 PNU에 걸치면 모두 그 단지의 PNU 목록에 넣는다.
- aptSeq 없는 거래는 PNU가 같은 aptSeq 단지가 있으면 그 단지에 붙인다 (없으면 pnu: 단지).
- 이름 = 가장 최근 거래(해제 포함, 계약일·원 순서)의 aptNm, 다른 이름은 aliases.
- 위치: 단지 PNU마다 LP_PA_CBND_BUBUN 필지 경계(seed/parcels.geojson에 있으면 재사용, 캐시 build/vworld_raw/apartments/)
  → EPSG:5186에서 합집합 → 4326. 위치 = 합집합에서 가장 큰 면의 representative_point. 지오코더는 쓰지 않는다.
- 출력: seed/apartments.geojson (커밋, 지도 빌드 원천. 위치를 못 찾은 단지도 geometry null로 넣는다 — M22 분모)
  build/apartments_unmatched.csv (사유: PNU 없음·필지 없음·조회 실패)

사용: python -m pipeline.build_trade_complexes [--refresh]
"""
import argparse
import csv
import json
from collections import Counter, defaultdict

from shapely.geometry import shape
from shapely.ops import unary_union

from pipeline.common import BUILD, SEED, log, setup_stdout, sha256
from pipeline.fetch_trades import CKPT, RAW as RTMS_RAW
from pipeline.geo import RAW, Stats, geom_out, get_feature, to_4326, to_5186, write_fc
from pipeline.rtms_parse import number_same, parse_xml, record

OUT = SEED / "apartments.geojson"
UNMATCHED = BUILD / "apartments_unmatched.csv"
DATA = "LP_PA_CBND_BUBUN"
CACHE = RAW / "apartments"
SOURCE = "국토교통부 아파트 매매 실거래가 상세 자료(공공데이터포털) · 필지 경계: 브이월드 2D 데이터 LP_PA_CBND_BUBUN"
NOTE = "단지 경계는 실거래 신고 지번의 필지 경계를 합쳐 표시. 신고되지 않은 필지는 빠질 수 있음"


def load_trades() -> tuple[list[dict], int]:
    """build/rtms_raw의 월별 원 응답 전체 → (저장 레코드 목록(원 순서), 같은 달 안 같은 레코드에 순번을 붙인 수).
    같은 달 응답 안에서 저장 필드가 모두 같은 레코드는 서로 다른 거래로 보고 모두 남긴다 (rtms_parse.number_same).
    다른 달 응답에 같은 레코드가 또 나오면(raw_hash 같음) 하나만 남긴다."""
    by_month: dict[str, list] = defaultdict(list)
    for f in RTMS_RAW.glob("[0-9]*_p*.xml"):
        ym, pg = f.stem.split("_p")
        by_month[ym].append((int(pg), f))
    out, seen, same = [], set(), 0
    for ym in sorted(by_month):
        recs = []
        for _, f in sorted(by_month[ym]):
            recs += [record(it) for it in parse_xml(f.read_text(encoding="utf-8"))[1]]
        same += number_same(recs)
        for r in recs:
            if r["raw_hash"] in seen:
                continue
            seen.add(r["raw_hash"])
            r["src_ym"] = ym
            out.append(r)
    return out, same


def fetched_on() -> str | None:
    try:
        return json.loads(CKPT.read_text(encoding="utf-8")).get("fetched_on")
    except (OSError, ValueError):
        return None


def complex_key(r: dict, seq_by_pnu: dict) -> str | None:
    if r["apt_seq"]:
        return r["apt_seq"]
    if r["pnu"]:
        return seq_by_pnu.get(r["pnu"]) or f"pnu:{r['pnu']}"
    return None


def group(trades: list[dict]) -> dict[str, dict]:
    """→ {단지 키: {key, apt_seq, names(최근 순), pnus, jibuns, trades}}"""
    seq_by_pnu: dict[str, str] = {}
    for r in trades:
        if r["apt_seq"] and r["pnu"]:
            seq_by_pnu.setdefault(r["pnu"], r["apt_seq"])
    cx: dict[str, dict] = {}
    for i, r in enumerate(trades):
        k = complex_key(r, seq_by_pnu)
        if not k:
            continue
        c = cx.setdefault(k, {"key": k, "apt_seq": k if not k.startswith("pnu:") else None, "rows": []})
        c["rows"].append((r["contract_date"] or "", i, r))
    for c in cx.values():
        rows = sorted(c["rows"])
        recs = [r for _, _, r in rows]
        names = []
        for r in reversed(recs):
            if r["apt_name_raw"] and r["apt_name_raw"] not in names:
                names.append(r["apt_name_raw"])
        c["name"] = names[0] if names else c["key"]
        c["aliases"] = names[1:]
        c["pnus"] = sorted({r["pnu"] for r in recs if r["pnu"]})
        c["jibuns"] = sorted({f"{r['umd_name']} {r['jibun']}" for r in recs if r["umd_name"] and r["jibun"]})
        live = [r for r in recs if not r["is_cancelled"]]
        c["trade_count"] = len(live)
        c["last_trade_date"] = max((r["contract_date"] for r in live if r["contract_date"]), default=None)
        yrs = Counter(r["build_year"] for r in recs if r["build_year"])
        c["build_year"] = min(y for y, n in yrs.items() if n == max(yrs.values())) if yrs else None
        bjd = Counter(r["pnu"][:10] for r in recs if r["pnu"])
        c["bjd_code"] = bjd.most_common(1)[0][0] if bjd else (
            f"{recs[0]['sgg_cd']}{recs[0]['umd_cd']}" if recs[0]["sgg_cd"] and recs[0]["umd_cd"] else None)
        c["no_pnu_reason"] = Counter(r["pnu_reason"] for r in recs if not r["pnu"]).most_common(1)
        del c["rows"]
    return cx


def seed_parcels() -> dict[str, dict]:
    p = SEED / "parcels.geojson"
    if not p.exists():
        return {}
    return {f["properties"]["pnu"]: f["geometry"] for f in json.loads(p.read_text(encoding="utf-8"))["features"]}


def parcel_geom(pnu: str, known: dict, refresh: bool) -> tuple[object | None, str | None]:
    """→ (EPSG:5186 도형, 실패 사유)"""
    if pnu in known and not refresh:
        return to_5186(shape(known[pnu])), None
    try:
        raw = get_feature(DATA, CACHE / f"{pnu}.json", refresh=refresh, attrFilter=f"pnu:=:{pnu}")
    except SystemExit:                       # get_feature는 오류를 fail()로 알린다 → 이 단지만 '조회 실패'
        return None, "조회 실패"
    fs = [f for f in raw["features"] if f["properties"].get("pnu") == pnu]
    if not fs:
        return None, "필지 없음"
    g = to_5186(unary_union([shape(f["geometry"]) for f in fs]))
    return (g if g.is_valid else g.buffer(0)), None


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    trades, dup = load_trades()
    cx = group(trades)
    as_of = fetched_on()
    known = seed_parcels()
    feats, unmatched = [], []
    geo_cache: dict[str, tuple] = {}
    for k in sorted(cx):
        c = cx[k]
        parts, reasons = [], []
        for p in c["pnus"]:
            if p not in geo_cache:
                geo_cache[p] = parcel_geom(p, known, a.refresh)
            g, why = geo_cache[p]
            if g is not None:
                parts.append(g)
            else:
                reasons.append(f"{p} {why}")
        geom = None
        if parts:
            u = unary_union(parts)
            u = u if u.is_valid else u.buffer(0)
            biggest = max(getattr(u, "geoms", [u]), key=lambda x: x.area)
            rp = to_4326(biggest.representative_point())
            geom = geom_out(to_4326(u))
            lon, lat = round(rp.x, 6), round(rp.y, 6)
        else:
            lon = lat = None
            reason = ("PNU 없음" if not c["pnus"] else
                      "조회 실패" if any("조회 실패" in r for r in reasons) else "필지 없음")
            unmatched.append({"id": f"apt:{k}", "name": c["name"], "pnus": " ".join(c["pnus"]), "reason": reason,
                              "detail": "; ".join(reasons) or (c["no_pnu_reason"][0][0] if c["no_pnu_reason"] else "")})
        feats.append({"type": "Feature", "id": f"apt:{k}", "geometry": geom, "properties": {
            "id": f"apt:{k}", "name": c["name"], "aliases": c["aliases"], "apt_seq": c["apt_seq"],
            "pnus": c["pnus"], "pnus_missing": [r.split(" ")[0] for r in reasons], "jibuns": c["jibuns"],
            "bjd_code": c["bjd_code"], "build_year": c["build_year"], "trade_count": c["trade_count"],
            "last_trade_date": c["last_trade_date"], "lon": lon, "lat": lat,
            "kapt_code": None, "households": None, "buildings": None, "approval_date": None,
            "basis_info": "pending", "as_of": as_of}})
    write_fc(OUT, feats, source=SOURCE, note=NOTE, as_of=as_of)
    UNMATCHED.parent.mkdir(parents=True, exist_ok=True)
    with open(UNMATCHED, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "pnus", "reason", "detail"])
        w.writeheader()
        w.writerows(unmatched)
    n_seq = sum(1 for c in cx.values() if c["apt_seq"])
    multi = sorted((c for c in cx.values() if len(c["pnus"]) >= 2), key=lambda c: (-len(c["pnus"]), c["key"]))
    log(f"거래 {len(trades)}건 (같은 달 안 같은 레코드 {dup}건은 순번을 붙여 모두 포함) · 단지 {len(cx)} (aptSeq {n_seq} · pnu: {len(cx) - n_seq}) · "
        f"PNU 2개 이상 {len(multi)}")
    for c in multi[:10]:
        log(f"  {c['key']} {c['name']}: {len(c['pnus'])}필지 {', '.join(c['jibuns'][:4])}")
    log(f"위치 찾음 {len(cx) - len(unmatched)}/{len(cx)} · 못 찾음 {len(unmatched)} {dict(Counter(u['reason'] for u in unmatched))}"
        f" → {UNMATCHED.name}")
    log(f"브이월드 요청 {Stats.requests}회 {Stats.seconds:.1f}초 · seed/apartments.geojson "
        f"{OUT.stat().st_size / 1e6:.2f}MB sha256 {sha256(OUT)[:16]}")


if __name__ == "__main__":
    main()
