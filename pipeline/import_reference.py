"""공식 참고 레이어 빌드 (docs/map/PLAN.md P15-1). 네트워크 없음, 멱등.

- 원본: data_raw/11.공간정보/ 의 서울플랜+ 사업현황(UPIS_C_UQ120)·의제처리구역(UPIS_C_UQ181) SHP. 읽기만 한다.
- 두 데이터 모두 공공누리 4유형(출처표시·상업적 이용금지·변경금지):
  · 도형을 자르기·단순화·병합하지 않고, 원본 필드 이름·값을 바꾸지 않는다.
  · 하는 일은 좌표계 변환(EPSG:5174 → 4326, 표시용 소수 6자리)과 강남구에 걸치는 도형 '선택'뿐이다.
  · 우리 메타는 '_' 접두어 필드로만 덧붙인다 (_source·_license·_as_of·_ref·_layer).
- 검증: P13 도면 정합 경계(seed/boundaries/D9·D10)와 서울플랜+ 같은 구역의 IoU가 P13 값(0.961·0.975)과 같아야 한다.
- 고르기: 강남구 경계와 겹친 면적이 0보다 큰 도형 (선만 닿는 이웃 구 도형은 제외). 경계 밖으로 나간 부분도 그대로 둔다.
  속성·도형이 완전히 같은 행은 처음 것만 두고 build/reference_dupes.csv에 적는다.
- 내보내기: public/data/layers/ref_seoulplan.geojson·ref_uije.geojson + manifest.json의 ref_* 항목만 바꾼다
  (propedia_* 항목은 pipeline/build_map_layers.py 소유).

사용: python -m pipeline.import_reference
"""
import collections
import csv
import datetime as dt
import json
import sys

import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import shape

from pipeline import sync_server_data
from pipeline.common import BUILD, PUBLIC, SEED, SHP_SEOULPLAN, SHP_UIJE, fail, log, setup_stdout, sha256
from pipeline.geo import to_5186, write_fc

OUT = PUBLIC / "data" / "layers"
GANGNAM = PUBLIC / "data" / "base" / "gangnam.geojson"
SRC_CRS = "EPSG:5174"      # Korean 1985 Modified Central Belt (Bessel), .prj AUTHORITY 5174 [확인 P13]
_TO_4326 = Transformer.from_crs(SRC_CRS, "EPSG:4326", always_xy=True)
ND = 6

LICENSE_4 = "공공누리 4유형(출처표시·상업적 이용금지·변경금지)"
NOTE = "표시용 좌표 변환(EPSG:5174 → EPSG:4326)·소수 6자리 반올림만, 도형 가공 없음 (자르기·단순화·병합 안 함)"
LAYERS = {
    "ref_seoulplan": {
        "shp": SHP_SEOULPLAN, "title": "서울시 도시계획사업 현황 (서울플랜+)",
        "source": "서울 열린데이터광장 OA-22712 서울시 도시계획사업 현황",
        "license": LICENSE_4,      # 데이터셋 페이지 '공공누리 4유형 : 출처표시+상업적 이용금지+변경금지' [확인 2026-11-10]
        "kind_field": "SCLAS_CL",
        "disclaimer": "본 자료는 법적 효력이 없으며 참고자료로만 활용 가능합니다 (데이터셋 페이지 안내)",
    },
    "ref_uije": {
        "shp": SHP_UIJE, "title": "의제처리구역",
        "source": "서울특별시 의제처리구역 위치정보(공공데이터포털)",
        # data.go.kr/data/15082965 이용허락범위 '공공저작물 : 출처표시, 상업적 이용금지, 변경금지 (제 4유형)' [확인 2026-11-10]
        "license": LICENSE_4,
        "kind_field": "ATRB_SE",
        "disclaimer": None,
    },
}
# P13 IoU (PROGRESS.md P13 표). 다르면 좌표계 변환이 틀린 것 → 멈춘다.
IOU_CHECK = [("D9", "일원동 대청마을 북측구역", 0.961), ("D10", "대치선경", 0.975)]


def _val(v):
    """원본 값 그대로 (날짜만 JSON에 넣을 수 있게 ISO 문자열로)."""
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("cp949", errors="replace")
    return v


def _rnd(c, nd: int | None = ND):
    if isinstance(c[0], (int, float)):
        x, y = _TO_4326.transform(c[0], c[1])
        return [round(x, nd), round(y, nd)] if nd is not None else [x, y]
    return [_rnd(x, nd) for x in c]


def read_layer(path):
    """[(원본 속성 dict, 원본 GeoJSON 도형(5174), 순번)]"""
    r = shapefile.Reader(str(path), encoding="cp949")
    names = [f[0] for f in r.fields[1:]]
    out = []
    for i, sr in enumerate(r.iterShapeRecords()):
        out.append(({k: _val(v) for k, v in zip(names, sr.record)}, sr.shape.__geo_interface__, i))
    return names, out


def _shp4326(geo: dict, nd: int | None = ND):
    g = shape({"type": geo["type"], "coordinates": _rnd(geo["coordinates"], nd)})
    return g if g.is_valid else g.buffer(0)       # 고르기·비교 계산용으로만 (내보내는 도형은 원본 그대로 변환)


def check_iou(rows) -> list[tuple]:
    by_name = {}
    for rec, geo, _ in rows:
        by_name.setdefault(rec.get("DGM_NM"), geo)
    res = []
    for doc, name, expect in IOU_CHECK:
        b = json.loads((SEED / "boundaries" / f"{doc}.geojson").read_text(encoding="utf-8"))["features"][0]
        ours = to_5186(shape(b["geometry"]))
        ref = by_name.get(name)
        if ref is None:
            fail(f"서울플랜+에 '{name}'이 없습니다")
        g = to_5186(_shp4326(ref, None))          # 좌표계 검증은 반올림 전 변환값으로 (P13과 같은 계산)
        iou = ours.intersection(g).area / ours.union(g).area
        gr = to_5186(_shp4326(ref))               # 참고: 내보내는 소수 6자리 좌표로 계산한 값
        res.append((doc, name, round(iou, 4), expect, round(ours.intersection(gr).area / ours.union(gr).area, 4)))
        if abs(iou - expect) > 0.0006:            # P13 표는 소수 3자리 (반올림 폭 ±0.0005)
            fail(f"좌표계 검증 실패: {doc} '{name}' IoU {iou:.4f} (P13 {expect}) — 변환을 확인해야 합니다")
    return res


def build(name: str, cfg: dict, gangnam5186, dupes: list) -> tuple[list, dict]:
    if not cfg["shp"].exists():
        fail(f"원본이 없습니다: data_raw/11.공간정보/.../{cfg['shp'].name}")
    names, rows = read_layer(cfg["shp"])
    seen = {}
    feats = []
    for rec, geo, i in rows:
        g5186 = to_5186(_shp4326(geo))
        if g5186.intersection(gangnam5186).area <= 0:
            continue
        key = json.dumps(rec, ensure_ascii=False, sort_keys=True, default=str) + json.dumps(geo["coordinates"])
        if key in seen:
            dupes.append({"layer": name, "row": i, "same_as_row": seen[key], "DGM_NM": rec.get("DGM_NM"),
                          "PRESENT_SN": rec.get("PRESENT_SN")})
            continue
        seen[key] = i
        feats.append((rec, geo, i))
    as_of = max((r.get("CREATE_DAT") or "" for r, _, _ in feats), default="") or None
    out = []
    for rec, geo, i in feats:
        props = dict(rec)
        props.update({"_source": cfg["source"], "_license": cfg["license"], "_as_of": as_of, "_ref": True,
                      "_layer": name, "_row": i})
        out.append({"type": "Feature", "properties": props,
                    "geometry": {"type": geo["type"], "coordinates": _rnd(geo["coordinates"])}})
    kinds = collections.Counter(r.get(cfg["kind_field"]) or "(빈 값)" for r, _, _ in feats)
    examples = {}
    for r, _, _ in feats:
        examples.setdefault(r.get(cfg["kind_field"]) or "(빈 값)", r.get("DGM_NM"))
    info = {"total_rows": len(rows), "count": len(out), "as_of": as_of, "kinds": kinds, "examples": examples,
            "crossing": sum(1 for r, geo, _ in feats if not to_5186(_shp4326(geo)).within(gangnam5186.buffer(0.5))),
            "fields": names}
    return out, info


def update_manifest(entries: dict) -> None:
    mp = OUT / "manifest.json"
    man = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {"layers": {}}
    man.setdefault("layers", {})
    for k in [k for k in man["layers"] if k.startswith("ref_")]:
        del man["layers"][k]
    man["layers"].update(entries)
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    setup_stdout()
    gangnam = shape(json.loads(GANGNAM.read_text(encoding="utf-8"))["features"][0]["geometry"])
    gangnam5186 = to_5186(gangnam)

    _, up_rows = read_layer(SHP_SEOULPLAN)
    log("좌표계 검증 (EPSG:5174 → 4326 → 5186, P13 도면 정합 경계와 IoU)")
    for doc, nm, iou, expect, iou6 in check_iou(up_rows):
        log(f"  {doc} '{nm}' IoU {iou:.4f} (P13 {expect}) 같음 · 소수 6자리 좌표로는 {iou6:.4f}")

    dupes, entries = [], {}
    for name, cfg in LAYERS.items():
        feats, info = build(name, cfg, gangnam5186, dupes)
        path = OUT / f"{name}.geojson"
        write_fc(path, feats, name=name, title=cfg["title"], source=cfg["source"], license=cfg["license"], note=NOTE)
        size = path.stat().st_size
        entries[name] = {
            "file": path.name, "title": cfg["title"], "source": cfg["source"], "license": cfg["license"],
            "as_of": info["as_of"], "count": info["count"], "status": "ready", "group": "공식 참고",
            "badge": "참고·비상업", "note": NOTE, "disclaimer": cfg["disclaimer"], "lazy": True,
            "size_bytes": size, "kind_field": cfg["kind_field"], "ref": True}
        log(f"\n{name}: 원본 {info['total_rows']}행 → 강남구 {info['count']}건 (경계 밖으로 걸침 {info['crossing']}) · "
            f"기준일 {info['as_of']} · {size:,} B ({size / 1024 / 1024:.2f} MB) · sha256 {sha256(path)[:16]}")
        log(f"  {cfg['kind_field']} | 건수 | 예 (DGM_NM)")
        for k, n in sorted(info["kinds"].items(), key=lambda x: (-x[1], x[0])):
            log(f"  {k} | {n} | {info['examples'][k]}")
    update_manifest(entries)
    log(f"\nmanifest.json sha256 {sha256(OUT / 'manifest.json')[:16]}")
    sync_server_data.sync(quiet=True)    # 서버가 읽는 사본 (P20-B, core/paths.py)

    dp = BUILD / "reference_dupes.csv"
    dp.parent.mkdir(parents=True, exist_ok=True)
    with open(dp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["layer", "row", "same_as_row", "DGM_NM", "PRESENT_SN"])
        w.writeheader()
        w.writerows(dupes)
    log(f"완전히 같은 행 {len(dupes)}건 → build/reference_dupes.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
