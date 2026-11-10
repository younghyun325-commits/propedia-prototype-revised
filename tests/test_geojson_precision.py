"""P20 성능: public/data 아래 모든 GeoJSON 좌표가 소수 6자리(약 0.1m) 이하인지 — 파일 크기·전송량을 줄이는 빌드 규칙."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "public" / "data").rglob("*.geojson"))
# JSON 숫자 문자열에서 소수 자릿수를 센다 (float 변환 전 원문 그대로)
NUM = re.compile(r"-?\d+\.(\d+)")


def _coords_text(geom) -> list[str]:
    out = []
    stack = [geom.get("coordinates")] if geom else []
    while stack:
        c = stack.pop()
        if isinstance(c, list):
            stack.extend(c)
        elif isinstance(c, (int, float, str)):
            out.append(c)
    return out


def test_files_exist():
    assert len(FILES) >= 10, [f.name for f in FILES]


def test_coordinates_at_most_6_decimals():
    bad = {}
    total = 0
    for f in FILES:
        fc = json.loads(f.read_text(encoding="utf-8"), parse_float=str)   # 원문 자릿수 그대로
        n = 0
        for feat in fc.get("features") or []:
            geoms = [feat.get("geometry")]
            if feat.get("geometry", {}) and feat["geometry"].get("type") == "GeometryCollection":
                geoms = feat["geometry"].get("geometries") or []
            for g in geoms:
                for v in _coords_text(g):
                    total += 1
                    m = NUM.fullmatch(v) if isinstance(v, str) else None
                    if m and len(m.group(1)) > 6:
                        n += 1
        if n:
            bad[str(f.relative_to(ROOT))] = n
    assert total > 10000, total             # 좌표를 실제로 읽었는지
    assert not bad, f"소수 6자리를 넘는 좌표 수: {bad}"
