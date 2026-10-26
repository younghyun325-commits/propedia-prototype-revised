"""대청마을 지도 대조 (feedback2.md §5-4, 네트워크 사용, 빌드 때만).

원 계획서 판정표 2번(경계 재작도)의 축소판이다. 고시(D9)에 지번 조서가 없어서:
 1. D9 12쪽 '관리지역 결정도'를 2000px로 렌더링한다 (축척 막대 0~180m로 픽셀당 미터를 잰다).
 2. 브이월드 2D 데이터(연속지적도 LP_PA_CBND_BUBUN)로 일원동 619 주변 필지 경계·지번을 받는다.
 3. 결정도의 회색 지적선과 지적도 필지선을 같은 축척으로 그려 상호상관(FFT)으로 위치를 맞춘다 (배율·회전 소폭 탐색).
 4. 결정도의 관리지역 경계(빨간 점선) 꼭짓점을 지적도 좌표로 옮기고, 필지 대표점이 경계 안쪽으로 충분히 들어간 필지를
    후보로 뽑는다. 경계에 걸리거나 가까운 필지는 넣지 않는다.
 5. 대조 그림(build/daecheong/overlay.png)과 후보 목록(build/daecheong/candidates.csv)을 남긴다.
    사람(Claude Code)이 그림을 보고 10~20필지를 골라 seed/daecheong_map_reading.csv에 쓴다 (checked_by는 빈칸 → 동혁 확인).

사용: python -m pipeline.daecheong_map
"""
import csv
import json
import math
import os

import httpx
import numpy as np
import pypdfium2 as pdfium
from dotenv import load_dotenv
from PIL import Image, ImageDraw

from pipeline.common import BUILD, ROOT, log, original_path, setup_stdout

OUT = BUILD / "daecheong"
DOMAIN = "https://propedia-pretotype.vercel.app"
CENTER = (37.49401251826346, 127.081389385546)      # 일원동 619 (브이월드 지오코더, L0 점검)
RENDER_W = 2000
# 2000px 렌더링 기준 (확인 2026-10-26)
MAP_BOX = (405, 481, 1365, 1285)                     # 위쪽 지도 틀 (범례 칸 제외: x < 405+960)
M_PER_PX = 180 / 190                                 # 축척 막대 0~180m = 190px
# 관리지역 경계(빨간 점선) 꼭짓점 — MAP_BOX 안 좌표 (d9_p12_top.png에서 읽음, 시계 방향)
BOUNDARY_PX = [(128, 348), (708, 112), (722, 117), (845, 432), (836, 448), (455, 608), (437, 600), (377, 457),
               (357, 465), (198, 528)]
MARGIN_M = 6.0                                       # 경계에서 이만큼 안쪽에 있는 필지만 후보


def render_drawing() -> Image.Image:
    pdf = pdfium.PdfDocument(str(original_path("D9")))
    page = pdf[11]
    w, _ = page.get_size()
    img = page.render(scale=RENDER_W / w).to_pil().convert("RGB")
    page.close()
    pdf.close()
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "d9_p12.png")
    return img


def fetch_cadastral(key: str) -> list[dict]:
    lat, lon = CENTER
    box = f"BOX({lon - 0.0065},{lat - 0.0050},{lon + 0.0065},{lat + 0.0050})"
    feats, page = [], 1
    with httpx.Client(timeout=30) as c:
        while True:
            r = c.get("https://api.vworld.kr/req/data", params={
                "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN", "key": key, "domain": DOMAIN,
                "geomFilter": box, "format": "json", "size": 1000, "page": page, "geometry": "true",
                "attribute": "true", "crs": "EPSG:4326"})
            resp = r.json()["response"]
            if resp.get("status") != "OK":
                raise SystemExit(f"연속지적도 조회 실패: {resp.get('status')} {(resp.get('error') or {}).get('code')}")
            feats += resp["result"]["featureCollection"]["features"]
            if page >= int(resp["page"]["total"]):
                break
            page += 1
    (OUT / "cadastral.json").write_text(json.dumps(feats, ensure_ascii=False), encoding="utf-8")
    return feats


def to_m(lon: float, lat: float) -> tuple[float, float]:
    lat0, lon0 = CENTER
    return ((lon - lon0) * math.cos(math.radians(lat0)) * 111320.0, (lat - lat0) * 110540.0)


def rings(feat) -> list[list[tuple[float, float]]]:
    g = feat["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [[to_m(x, y) for x, y in poly[0]] for poly in polys]


def drawing_lines(img: Image.Image) -> np.ndarray:
    x0, y0, x1, y1 = MAP_BOX
    a = np.asarray(img.crop((x0, y0, x1, y1))).astype(int)
    s = a.sum(axis=2)
    red = (a[..., 0] > 160) & (a[..., 1] < 120) & (a[..., 2] < 120)
    line = (s < 700) & ~red          # 회색 지적선 (흰 바탕 765)
    return line.astype(np.float32)


def raster(polys_m, origin, scale, angle_deg, shape) -> np.ndarray:
    """미터 좌표 필지선을 결정도 픽셀 격자에 그린다. origin = 그림 (0,0) 픽셀의 미터 좌표."""
    h, w = shape
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    for ring in polys_m:
        pts = []
        for x, y in ring:
            xr, yr = x * ca - y * sa, x * sa + y * ca
            pts.append(((xr - origin[0]) / scale, (origin[1] - yr) / scale))
        d.line(pts, fill=255, width=1)
    return np.asarray(img, dtype=np.float32) / 255.0


def dilate(a: np.ndarray, r: int = 2) -> np.ndarray:
    out = a.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out = np.maximum(out, np.roll(np.roll(a, dy, 0), dx, 1))
    return out


def best_offset(draw: np.ndarray, cad: np.ndarray) -> tuple[int, int, float]:
    """cad를 (dy, dx)만큼 옮겼을 때 draw와 가장 많이 겹치는 이동 (FFT 상호상관)."""
    A = np.fft.rfft2(draw - draw.mean())
    B = np.fft.rfft2(cad - cad.mean())
    corr = np.fft.irfft2(A * np.conj(B), s=draw.shape)
    i = int(np.argmax(corr))
    dy, dx = np.unravel_index(i, corr.shape)
    h, w = draw.shape
    dy = dy - h if dy > h // 2 else dy
    dx = dx - w if dx > w // 2 else dx
    return int(dy), int(dx), float(corr.max() / (np.linalg.norm(draw - draw.mean()) * np.linalg.norm(cad - cad.mean()) + 1e-9))


def point_in_poly(x, y, poly) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def dist_to_poly(x, y, poly) -> float:
    best = float("inf")
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def centroid(ring) -> tuple[float, float]:
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if abs(a) < 1e-9:
        return ring[0]
    return cx / (3 * a), cy / (3 * a)


def main() -> None:
    setup_stdout()
    load_dotenv(ROOT / ".env")
    key = (os.environ.get("VWORLD_API_KEY") or "").strip()
    img = render_drawing()
    cache = OUT / "cadastral.json"
    feats = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else fetch_cadastral(key)
    log(f"연속지적도 필지 {len(feats)}개")
    polys = [r for f in feats for r in rings(f)]
    draw = dilate(drawing_lines(img), 1)
    h, w = draw.shape
    # 그림 중심이 대략 일원동 619 근처라고 두고 시작 → 배율·회전을 조금씩 바꿔 상관이 가장 큰 값을 고른다
    # 축척 막대(0.947m/px)와 기준 필지 간격으로 잰 값(약 0.79m/px)이 달라서 배율을 넓게 탐색한다
    best = None
    for scale in np.arange(0.70, 1.001, 0.01):
        for ang in (-1.0, 0.0, 1.0):
            origin = (-(w / 2) * scale, (h / 2) * scale)
            cad = dilate(raster(polys, origin, scale, ang, (h, w)), 1)
            dy, dx, score = best_offset(draw, cad)
            if best is None or score > best[0]:
                best = (score, scale, ang, dy, dx, origin)
    score, scale, ang, dy, dx, origin = best
    log(f"맞춤: 상관 {score:.3f}, 픽셀당 {scale:.4f}m, 회전 {ang}°, 이동 ({dx}, {dy})px")
    # 이동을 반영한 원점: 지적도를 (dx, dy) 옮긴 것 = 그림 원점을 반대로 옮긴 것
    origin = (origin[0] - dx * scale, origin[1] + dy * scale)
    ca, sa = math.cos(math.radians(-ang)), math.sin(math.radians(-ang))

    def px_to_m(px, py):
        xr, yr = origin[0] + px * scale, origin[1] - py * scale
        return xr * ca - yr * sa, xr * sa + yr * ca          # 회전을 되돌린 지적도 좌표

    boundary = [px_to_m(x, y) for x, y in BOUNDARY_PX]
    rows = []
    for f in feats:
        p = f["properties"]
        jibun = p.get("jibun") or ""
        ring = rings(f)[0]
        cx, cy = centroid(ring)
        inside = point_in_poly(cx, cy, boundary)
        d = dist_to_poly(cx, cy, boundary)
        all_in = all(point_in_poly(x, y, boundary) for x, y in ring[:-1])
        rows.append({"pnu": p["pnu"], "jibun": jibun, "addr": p.get("addr"), "inside": inside, "all_vertices_in": all_in,
                     "edge_m": round(d, 1), "cx": round(cx, 1), "cy": round(cy, 1)})
    with open(OUT / "candidates.csv", "w", encoding="utf-8-sig", newline="") as fp:
        wr = csv.DictWriter(fp, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(sorted(rows, key=lambda r: (not r["inside"], -r["edge_m"])))

    # 대조 그림: 결정도 위에 지적도 필지선(파랑)·지번(검정), 경계(빨강)
    base = img.crop(MAP_BOX).convert("RGB")
    ov = base.copy()
    dr = ImageDraw.Draw(ov)
    ca2, sa2 = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def m_to_px(x, y):
        xr, yr = x * ca2 - y * sa2, x * sa2 + y * ca2
        return (xr - origin[0]) / scale, (origin[1] - yr) / scale

    for f, r in zip(feats, rows):
        for ring in rings(f):
            dr.line([m_to_px(x, y) for x, y in ring], fill=(40, 90, 220), width=1)
        px, py = m_to_px(r["cx"], r["cy"])
        if 0 <= px < base.width and 0 <= py < base.height:
            col = (0, 140, 0) if r["inside"] and r["edge_m"] >= MARGIN_M else (60, 60, 60)
            dr.text((px - 10, py - 5), r["jibun"].replace(" ", ""), fill=col)
    dr.line([m_to_px(*xy) for xy in boundary + boundary[:1]], fill=(230, 0, 0), width=2)
    ov.save(OUT / "overlay.png")
    n_in = sum(r["inside"] and r["edge_m"] >= MARGIN_M for r in rows)
    log(f"경계 안쪽(여유 {MARGIN_M}m 이상) 필지 {n_in}개 → build/daecheong/candidates.csv, overlay.png")


if __name__ == "__main__":
    main()
