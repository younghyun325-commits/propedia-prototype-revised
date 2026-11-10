"""이 지점의 공식 참고 구역 (docs/map/PLAN.md P15-3-2). 표준 라이브러리만, 네트워크 없음.

빌드한 public/data/layers/ref_seoulplan.geojson·ref_uije.geojson(pipeline/import_reference.py)을 한 번 읽어
도형마다 bbox를 만들어 두고, 점이 들어 있는 도형의 이름·종류·출처를 돌려준다 (bbox 선필터 → 짝홀 규칙).
참고 레이어는 공공누리 4유형이라 결과에 출처·라이선스를 그대로 붙이고 판정·해석 문구는 만들지 않는다.
"""
import json
from pathlib import Path

from core.geo import bbox, contains

LAYERS_DIR = Path(__file__).resolve().parents[1] / "public" / "data" / "layers"
REF_LAYERS = ("ref_seoulplan", "ref_uije")
KIND_FIELD = {"ref_seoulplan": "SCLAS_CL", "ref_uije": "ATRB_SE"}
BADGE = "참고·비상업"


_CACHE: list = []      # 한 번만 읽는다 (함수 인스턴스 메모리)


def _index() -> tuple:
    if _CACHE:
        return _CACHE[0]
    out = []
    for name in REF_LAYERS:
        try:
            fc = json.loads((LAYERS_DIR / f"{name}.geojson").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        title = fc.get("title")
        for f in fc.get("features") or []:
            g = f.get("geometry") or {}
            b = bbox(g)
            if b is None:
                continue
            p = f.get("properties") or {}
            out.append((b, g, {"layer": name, "layer_title": title, "name": p.get("DGM_NM"),
                               "kind_code": p.get(KIND_FIELD[name]), "present_sn": p.get("PRESENT_SN"),
                               "source": p.get("_source"), "license": p.get("_license"), "as_of": p.get("_as_of"),
                               "badge": BADGE}))
    if out:
        _CACHE.append(tuple(out))
    return tuple(out)


def zones_at(lat: float, lon: float) -> list[dict]:
    hits = []
    for (w, s, e, n), g, info in _index():
        if w <= lon <= e and s <= lat <= n and contains(g, lon, lat):
            hits.append(dict(info))
    hits.sort(key=lambda h: (REF_LAYERS.index(h["layer"]), h["name"] or ""))
    return hits


def loaded_count() -> int:
    return len(_index())
