"""필지 경계 (docs/map/PLAN.md P13-2). 네트워크 사용, 빌드 때만.

대상 PNU: DB project_parcels(사업 필지) ∪ seed/demo_addresses.csv(범위 안 시연 주소).
브이월드 2D 데이터 LP_PA_CBND_BUBUN(연속지적도)을 PNU 속성 필터로 1건씩 받는다.
- 원 응답: build/vworld_raw/parcels/{pnu}.json (있으면 네트워크 안 씀, --refresh로 다시 받음)
- 출력: seed/parcels.geojson (EPSG:4326, 소수 6자리)
  속성 pnu, jibun, centroid_lon, centroid_lat (EPSG:5186 representative_point → 4326), area_m2 (EPSG:5186), as_of
- 못 찾은 PNU: build/parcels_missing.csv (사유) 후 계속.
- 중심점은 필지 경계에서 계산한 값이다. 지오코더 결과는 쓰지 않는다.

사용: python -m pipeline.fetch_parcels [--refresh]
"""
import argparse
import csv
import sqlite3

from shapely.geometry import shape
from shapely.ops import unary_union

from pipeline.common import BUILD, DB_PATH, ROOT, SEED, fail, log, setup_stdout, sha256
from pipeline.geo import RAW, Stats, geom_out, get_feature, to_4326, to_5186, write_fc

OUT = SEED / "parcels.geojson"
MISSING = BUILD / "parcels_missing.csv"
DATA = "LP_PA_CBND_BUBUN"


def targets() -> dict[str, list[str]]:
    t: dict[str, list[str]] = {}
    con = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)
    for pnu, basis, key in con.execute("""SELECT pp.pnu, pp.basis, p.project_key FROM project_parcels pp
                                          JOIN projects p ON p.id = pp.project_id ORDER BY pp.pnu"""):
        t.setdefault(pnu, []).append(f"사업 {key} ({basis})")
    con.close()
    with open(SEED / "demo_addresses.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["pnu"] and r["in_scope"] == "1":
                t.setdefault(r["pnu"], []).append(f"시연 {r['addr_id']}")
            elif r["pnu"]:
                log(f"  {r['addr_id']} 범위 밖(in_scope=0) → 받지 않음")
    return t


def as_of_of(p: dict) -> str | None:
    y, m = p.get("gosi_year"), p.get("gosi_month")
    if y and m:
        return f"{int(y):04d}-{int(m):02d}"
    return None


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    t = targets()
    has528 = "1168011000105280000" in t
    log(f"대상 PNU {len(t)}개 (사업 필지 {sum(any(x.startswith('사업') for x in v) for v in t.values())}, "
        f"528번지 포함 {'예' if has528 else '아니오'})")
    if not has528:
        t["1168011000105280000"] = ["비교용 압구정동 528"]

    feats, missing = [], []
    for pnu in sorted(t):
        raw = get_feature(DATA, RAW / "parcels" / f"{pnu}.json", refresh=args.refresh, attrFilter=f"pnu:=:{pnu}")
        fs = [f for f in raw["features"] if f["properties"].get("pnu") == pnu]
        if not fs:
            missing.append({"pnu": pnu, "why": "; ".join(t[pnu]), "reason": f"{DATA} 결과 없음 ({raw['status']})"})
            continue
        geom4326 = unary_union([shape(f["geometry"]) for f in fs])
        g = to_5186(geom4326)
        if not g.is_valid:
            g = g.buffer(0)
        rp = to_4326(g.representative_point())
        p = fs[0]["properties"]
        feats.append({"type": "Feature", "id": pnu, "properties": {
            "pnu": pnu, "jibun": p.get("jibun"), "addr": p.get("addr"),
            "centroid_lon": round(rp.x, 6), "centroid_lat": round(rp.y, 6),
            "area_m2": round(g.area, 1), "as_of": as_of_of(p), "why": t[pnu]},
            "geometry": geom_out(to_4326(g))})

    write_fc(OUT, feats, source="브이월드 2D 데이터 LP_PA_CBND_BUBUN (연속지적도, 국토교통부)")
    MISSING.parent.mkdir(parents=True, exist_ok=True)
    with open(MISSING, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pnu", "why", "reason"])
        w.writeheader()
        w.writerows(missing)
    log(f"seed/parcels.geojson {len(feats)}필지, 못 찾음 {len(missing)} → build/parcels_missing.csv")
    for m in missing:
        log(f"  못 찾음 {m['pnu']} {m['why']}: {m['reason']}")
    log(f"요청 {Stats.requests}회 {Stats.seconds:.1f}초 · sha256 {sha256(OUT)}")
    if not feats:
        fail("받은 필지가 없습니다")


if __name__ == "__main__":
    main()
