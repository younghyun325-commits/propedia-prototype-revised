"""GeoJSON 도형 계산 (표준 라이브러리만, docs/map/PLAN.md P15). 경위도를 평면으로 보고 계산한다 (필지·구역 크기에서 충분).

- bbox(geom) → [서, 남, 동, 북]
- contains(geom, lon, lat): 짝홀 규칙. Polygon·MultiPolygon, 구멍(안쪽 고리) 처리
- centroid(geom): 가장 넓은 면의 면적 중심. 면 밖이면 None
"""


def _rings(geom: dict) -> list[list]:
    """[[바깥 고리, 구멍...], ...] (Polygon은 한 덩어리)"""
    t, c = geom.get("type"), geom.get("coordinates") or []
    if t == "Polygon":
        return [c]
    if t == "MultiPolygon":
        return list(c)
    return []


def bbox(geom: dict) -> list[float] | None:
    w = s = float("inf")
    e = n = float("-inf")
    for poly in _rings(geom):
        for ring in poly:
            for x, y, *_ in ring:
                w, e, s, n = min(w, x), max(e, x), min(s, y), max(n, y)
    return [w, s, e, n] if w <= e else None


def _in_ring(ring: list, x: float, y: float) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def contains(geom: dict, lon: float, lat: float) -> bool:
    for poly in _rings(geom):
        if poly and _in_ring(poly[0], lon, lat) and not any(_in_ring(h, lon, lat) for h in poly[1:]):
            return True
    return False


def _ring_area_centroid(ring: list) -> tuple[float, float, float]:
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    a /= 2
    if a == 0:
        return 0.0, ring[0][0], ring[0][1]
    return a, cx / (6 * a), cy / (6 * a)


def centroid(geom: dict) -> tuple[float, float] | None:
    """(경도, 위도). 가장 넓은 면 바깥 고리의 면적 중심이 그 도형 안에 있을 때만."""
    best = None
    for poly in _rings(geom):
        if not poly:
            continue
        a, x, y = _ring_area_centroid(poly[0])
        if best is None or abs(a) > best[0]:
            best = (abs(a), x, y)
    if best is None:
        return None
    _, x, y = best
    return (x, y) if contains(geom, x, y) else None
