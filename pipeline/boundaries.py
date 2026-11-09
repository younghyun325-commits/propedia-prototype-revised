"""도면 정합 경계 저장·비교 (docs/map/PLAN.md P13-3).

- write_boundary: EPSG:5186 면 → seed/boundaries/{doc}.geojson (EPSG:4326, 소수 6자리, 같은 입력이면 같은 바이트).
  면적(area_m2_geom)은 5186에서 계산해 속성에 넣는다.
- compare_reference: 서울플랜+ 사업현황(UQ120, 공공누리 4유형) 도형과 면적·IoU·하우스도르프 거리만 계산한다.
  UQ120 도형은 비교에만 쓰고 어디에도 내보내지 않는다.
  UQ120 .prj = Korean 1985 Modified Central Belt (Bessel) → EPSG:5174로 읽어 데이텀 변환을 거친다.
"""
import json
from functools import lru_cache

import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import shape

from pipeline.common import SEED, SHP_SEOULPLAN
from pipeline.geo import geom_out, to_4326, write_fc

BOUNDARIES = SEED / "boundaries"
_UQ_TO_5186 = Transformer.from_crs("EPSG:5174", "EPSG:5186", always_xy=True)


def write_boundary(doc: str, poly5186, props: dict) -> None:
    if not poly5186.is_valid:
        poly5186 = poly5186.buffer(0)
    p = dict(props, area_m2_geom=round(poly5186.area, 1))
    write_fc(BOUNDARIES / f"{doc}.geojson",
             [{"type": "Feature", "id": doc, "properties": p, "geometry": geom_out(to_4326(poly5186))}],
             note="고시 도면을 연속지적도와 맞춰 읽은 경계 (사람 확인 전)")


def read_boundary(doc: str):
    """seed/boundaries/{doc}.geojson → (feature dict) 또는 None."""
    path = BOUNDARIES / f"{doc}.geojson"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["features"][0]


@lru_cache(maxsize=1)
def _uq120() -> list[tuple[str, object]]:
    r = shapefile.Reader(str(SHP_SEOULPLAN), encoding="cp949")
    names = [f[0] for f in r.fields[1:]]
    i = names.index("DGM_NM")
    out = []
    for sr in r.iterShapeRecords():
        if sr.record[names.index("SIGNGU_SE")] != "11680":
            continue
        g = shape(sr.shape.__geo_interface__)
        out.append((sr.record[i], shapely.transform(g, lambda x, y: _UQ_TO_5186.transform(x, y), interleaved=False)))
    return out


def reference_geom(name: str):
    for n, g in _uq120():
        if n == name:
            return g if g.is_valid else g.buffer(0)
    return None


def compare_reference(poly5186, name: str) -> dict | None:
    ref = reference_geom(name)
    if ref is None:
        return None
    inter = poly5186.intersection(ref).area
    union = poly5186.union(ref).area
    return {"source": "서울플랜+ 사업현황 UPIS_C_UQ120 (공공누리 4유형, 비교에만 사용)", "name": name,
            "area_m2": round(ref.area, 1), "iou": round(inter / union, 4) if union else 0.0,
            "hausdorff_m": round(poly5186.hausdorff_distance(ref), 1),
            "area_diff_pct": round((poly5186.area / ref.area - 1) * 100, 2)}
