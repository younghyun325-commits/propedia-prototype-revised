"""고시 도면 × 연속지적도 정합 공통 모듈 (docs/map/PLAN.md P13-3).

pipeline/daecheong_map.py(P10)의 방법을 함수로 옮겼다:
 1. 도면 지도 틀 안의 회색 지적선을 뽑는다 (경계선 색은 뺀다).
 2. 브이월드 연속지적도(LP_PA_CBND_BUBUN) 필지선을 같은 픽셀 격자에 그린다 (배율·회전 후보마다).
 3. FFT 상호상관으로 가장 잘 겹치는 이동량을 찾고, 배율·회전 중 상관이 가장 큰 값을 고른다.
 4. 1위와 위치(10m 이상) 또는 배율(3% 이상)이 다른 후보 중 최고점을 2위로 남긴다. 1위/2위 < 1.05면 '모호함'.

좌표: 기준점(대표 필지 경계 중심점, seed/parcels.geojson) 둘레의 EPSG:5186 미터 좌표 (기준점 = 0,0).
지오코더 좌표는 쓰지 않는다.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pypdf import PdfReader
from shapely.geometry import Polygon, shape

from pipeline.common import BUILD, DATA_RAW, SEED, fail
from pipeline.geo import RAW, Stats, get_feature, lonlat_to_5186, xy_to_lonlat

ALIGN_DIR = BUILD / "align"
AMBIGUOUS_RATIO = 1.05


# ── 도면 이미지 ─────────────────────────────────────────────────────────
def page_image(doc: str, pdf_page: int, method: str, *, index: int = 0, render_w: int = 3000) -> tuple[Image.Image, dict]:
    """data_raw/{doc}.pdf 한 쪽 → 이미지.
    method='embedded': 쪽에 들어 있는 이미지(index번째)를 원본 해상도로 꺼낸다.
    method='render':   pypdfium2로 쪽 전체를 가로 render_w px로 렌더링한다 (도면이 벡터이거나 이미지 추출이 안 될 때).
    """
    path = DATA_RAW / f"{doc}.pdf"
    if method == "embedded":
        page = PdfReader(str(path)).pages[pdf_page - 1]
        ims = list(page.images)
        if len(ims) <= index:
            fail(f"{doc} p{pdf_page}: 내장 이미지 {index}번이 없습니다 (render로 바꾸세요)")
        img = ims[index].image.convert("RGB")
        return img, {"method": "embedded", "index": index, "size": list(img.size), "pdf": f"data_raw/{doc}.pdf"}
    pdf = pdfium.PdfDocument(str(path))
    page = pdf[pdf_page - 1]
    w, _ = page.get_size()
    img = page.render(scale=render_w / w).to_pil().convert("RGB")
    page.close()
    pdf.close()
    return img, {"method": "render", "render_w": render_w, "size": list(img.size), "pdf": f"data_raw/{doc}.pdf"}


def color_mask(a: np.ndarray, color: str) -> np.ndarray:
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if color == "red":
        return (r > 150) & (g < 130) & (b < 130) & (r - g > 60)
    if color == "blue":
        return (b > 120) & (r < 120) & (b - r > 50) & (b - g > 20)
    raise ValueError(color)


def line_mask(img: Image.Image, exclude: tuple[str, ...] = ("red",), dark: int = 700) -> np.ndarray:
    """회색·검정 지적선 (흰 바탕 합 765). 경계선 색(exclude)은 뺀다."""
    a = np.asarray(img).astype(int)
    m = a.sum(axis=2) < dark
    for c in exclude:
        m &= ~dilate_bool(color_mask(a, c), 1)
    return m.astype(np.float32)


def dilate(a: np.ndarray, r: int = 2) -> np.ndarray:
    out = a.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out = np.maximum(out, np.roll(np.roll(a, dy, 0), dx, 1))
    return out


def dilate_bool(a: np.ndarray, r: int) -> np.ndarray:
    return dilate(a.astype(np.uint8), r).astype(bool)


def downsample_max(a: np.ndarray, f: int) -> np.ndarray:
    if f == 1:
        return a
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return a[:h, :w].reshape(h // f, f, w // f, f).max(axis=(1, 3))


# ── 연속지적도 ──────────────────────────────────────────────────────────
def parcel_center(pnu: str) -> tuple[float, float]:
    """seed/parcels.geojson의 필지 경계 중심점 (lon, lat)."""
    fc = json.loads((SEED / "parcels.geojson").read_text(encoding="utf-8"))
    for f in fc["features"]:
        if f["properties"]["pnu"] == pnu:
            return f["properties"]["centroid_lon"], f["properties"]["centroid_lat"]
    fail(f"seed/parcels.geojson에 {pnu}가 없습니다 (pipeline.fetch_parcels 먼저)")
    return 0.0, 0.0


def fetch_cadastral(tag: str, center_lonlat: tuple[float, float], half_w_m: float, half_h_m: float,
                    tiles: tuple[int, int] = (1, 1), refresh: bool = False) -> tuple[list[dict], dict]:
    """기준점 둘레 사각형의 연속지적도. bbox를 nx×ny로 나눠 받고 PNU로 중복을 없앤다.
    원 응답: build/vworld_raw/cadastral/{tag}_{i}_{j}.json"""
    cx, cy = lonlat_to_5186(*center_lonlat)
    nx, ny = tiles
    r0, s0 = Stats.requests, Stats.seconds
    by_pnu: dict[str, dict] = {}
    for i in range(nx):
        for j in range(ny):
            x0 = cx - half_w_m + 2 * half_w_m * i / nx
            x1 = cx - half_w_m + 2 * half_w_m * (i + 1) / nx
            y0 = cy - half_h_m + 2 * half_h_m * j / ny
            y1 = cy - half_h_m + 2 * half_h_m * (j + 1) / ny
            lo0, la0 = xy_to_lonlat(x0, y0)
            lo1, la1 = xy_to_lonlat(x1, y1)
            box = f"BOX({lo0:.6f},{la0:.6f},{lo1:.6f},{la1:.6f})"
            raw = get_feature("LP_PA_CBND_BUBUN", RAW / "cadastral" / f"{tag}_{int(half_w_m)}x{int(half_h_m)}_{i}_{j}.json", refresh=refresh,
                              geomFilter=box)
            for f in raw["features"]:
                by_pnu.setdefault(f["properties"]["pnu"], f)
    feats = [by_pnu[k] for k in sorted(by_pnu)]
    return feats, {"requests": Stats.requests - r0, "seconds": round(Stats.seconds - s0, 1), "tiles": [nx, ny],
                   "parcels": len(feats)}


class Frame:
    """기준점(lon, lat)을 0,0으로 둔 EPSG:5186 미터 좌표."""

    def __init__(self, center_lonlat: tuple[float, float]):
        self.center = center_lonlat
        self.ox, self.oy = lonlat_to_5186(*center_lonlat)

    def to_m(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = lonlat_to_5186(lon, lat)
        return x - self.ox, y - self.oy

    def to_lonlat(self, x: float, y: float) -> tuple[float, float]:
        return xy_to_lonlat(x + self.ox, y + self.oy)

    def to_5186(self, x: float, y: float) -> tuple[float, float]:
        return x + self.ox, y + self.oy

    def rings(self, feat: dict) -> list[list[tuple[float, float]]]:
        g = feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        return [[self.to_m(x, y) for x, y in poly[0]] for poly in polys]


# ── 정합 ────────────────────────────────────────────────────────────────
def raster(polys_m, origin, scale, angle_deg, shape_hw) -> np.ndarray:
    """미터 좌표 필지선을 도면 픽셀 격자에 그린다. origin = 그림 (0,0) 픽셀의 (회전된) 미터 좌표."""
    h, w = shape_hw
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


def _corr(draw: np.ndarray, cad: np.ndarray) -> np.ndarray:
    A = np.fft.rfft2(draw - draw.mean())
    B = np.fft.rfft2(cad - cad.mean())
    c = np.fft.irfft2(A * np.conj(B), s=draw.shape)
    return c / (np.linalg.norm(draw - draw.mean()) * np.linalg.norm(cad - cad.mean()) + 1e-9)


def _peak(corr: np.ndarray) -> tuple[int, int, float]:
    i = int(np.argmax(corr))
    dy, dx = np.unravel_index(i, corr.shape)
    h, w = corr.shape
    v = float(corr.flat[i])
    dy = dy - h if dy > h // 2 else dy
    dx = dx - w if dx > w // 2 else dx
    return int(dy), int(dx), v


def best_offset(draw: np.ndarray, cad: np.ndarray) -> tuple[int, int, float]:
    """cad를 (dy, dx)만큼 옮겼을 때 draw와 가장 많이 겹치는 이동 (FFT 상호상관). P10 daecheong_map과 같은 값."""
    return _peak(_corr(draw, cad))


def _peaks(draw: np.ndarray, cad: np.ndarray, suppress_px: int) -> list[tuple[int, int, float]]:
    """1위 봉우리와, 그 둘레 suppress_px를 지운 뒤의 봉우리."""
    c = _corr(draw, cad)
    p1 = _peak(c)
    h, w = c.shape
    yy = (np.arange(h)[:, None] - p1[0]) % h
    xx = (np.arange(w)[None, :] - p1[1]) % w
    yy = np.minimum(yy, h - yy)
    xx = np.minimum(xx, w - xx)
    c2 = np.where((yy ** 2 + xx ** 2) <= suppress_px ** 2, -1.0, c)
    return [p1, _peak(c2)]


@dataclass
class Fit:
    scale: float
    angle: float
    dy: int
    dx: int
    score: float
    w: int
    h: int

    @property
    def origin(self) -> tuple[float, float]:
        o = (-(self.w / 2) * self.scale, (self.h / 2) * self.scale)
        return o[0] - self.dx * self.scale, o[1] + self.dy * self.scale

    def px_to_m(self, px: float, py: float) -> tuple[float, float]:
        ox, oy = self.origin
        xr, yr = ox + px * self.scale, oy - py * self.scale
        ca, sa = math.cos(math.radians(-self.angle)), math.sin(math.radians(-self.angle))
        return xr * ca - yr * sa, xr * sa + yr * ca

    def m_to_px(self, x: float, y: float) -> tuple[float, float]:
        ca, sa = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
        xr, yr = x * ca - y * sa, x * sa + y * ca
        ox, oy = self.origin
        return (xr - ox) / self.scale, (oy - yr) / self.scale


def align(draw: np.ndarray, polys_m, scales, angles, *, work: int = 1, dilate_r: int = 1,
          distinct_m: float = 10.0, distinct_scale: float = 0.03) -> dict:
    """배율·회전 격자 탐색. draw는 원 해상도 선 마스크(0/1). work>1이면 그만큼 줄여 탐색한다.
    반환: best, second (Fit), ratio, ambiguous, candidates 수."""
    d0 = downsample_max(draw, work)
    d = dilate(d0, dilate_r)
    h, w = d.shape
    cands: list[Fit] = []
    for s in scales:
        sw = s * work
        origin = (-(w / 2) * sw, (h / 2) * sw)
        for ang in angles:
            cad = dilate(raster(polys_m, origin, sw, ang, (h, w)), dilate_r)
            for dy, dx, v in _peaks(d, cad, max(3, int(distinct_m / sw))):
                cands.append(Fit(float(s), float(ang), dy * work, dx * work, v, draw.shape[1], draw.shape[0]))
    cands.sort(key=lambda f: -f.score)
    best = cands[0]
    bx, by = best.px_to_m(best.w / 2, best.h / 2)

    def distinct(f: Fit) -> bool:
        fx, fy = f.px_to_m(f.w / 2, f.h / 2)
        return math.hypot(fx - bx, fy - by) >= distinct_m or abs(f.scale / best.scale - 1) >= distinct_scale

    second = next((f for f in cands[1:] if distinct(f)), None)
    ratio = best.score / second.score if second and second.score > 0 else float("inf")
    return {"best": best, "second": second, "ratio": ratio, "ambiguous": ratio < AMBIGUOUS_RATIO,
            "n_candidates": len(cands)}


def refine(draw: np.ndarray, polys_m, fit: Fit, *, span: float = 0.012, step: float = 0.002,
           angles=None, dilate_r: int = 1) -> Fit:
    """원 해상도에서 1위 둘레를 잘게 다시 찾는다."""
    d = dilate(draw, dilate_r)
    h, w = d.shape
    best = None
    angles = angles if angles is not None else [fit.angle - 0.25, fit.angle, fit.angle + 0.25]
    for s in np.arange(fit.scale * (1 - span), fit.scale * (1 + span) + 1e-12, fit.scale * step):
        origin = (-(w / 2) * s, (h / 2) * s)
        for ang in angles:
            cad = dilate(raster(polys_m, origin, s, ang, (h, w)), dilate_r)
            dy, dx, v = best_offset(d, cad)
            if best is None or v > best.score:
                best = Fit(float(s), float(ang), dy, dx, v, w, h)
    return best


def fit_json(f: Fit | None) -> dict | None:
    if f is None:
        return None
    return {"m_per_px": round(f.scale, 5), "angle_deg": f.angle, "offset_px": [f.dx, f.dy], "score": round(f.score, 4)}


def save_result(doc: str, data: dict) -> Path:
    ALIGN_DIR.mkdir(parents=True, exist_ok=True)
    p = ALIGN_DIR / f"{doc}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return p


# ── 점·다각형 (P10 daecheong_map에서 옮김) ────────────────────────────────
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


# ── 경계 영역 (색으로 칠한 구역을 면으로) ──────────────────────────────────
def mask_to_polygon(mask: np.ndarray, fit: Fit, frame: Frame, simplify_px: float = 1.5):
    """True 픽셀 영역 → 5186 면. 행 단위 구간을 상자로 만들어 합친 뒤 단순화."""
    from shapely.ops import unary_union
    from shapely.geometry import box
    boxes = []
    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any():
            continue
        diff = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts, ends = np.where(diff == 1)[0], np.where(diff == -1)[0]
        for x0, x1 in zip(starts, ends):
            boxes.append(box(x0, y, x1, y + 1))
    px_poly = unary_union(boxes).simplify(simplify_px)
    return px_poly


def px_polygon_to_5186(px_geom, fit: Fit, frame: Frame):
    import shapely

    def fn(xs, ys):
        pts = [frame.to_5186(*fit.px_to_m(x, y)) for x, y in zip(xs, ys)]
        return np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    return shapely.transform(px_geom, fn, interleaved=False)


def vertices_to_5186(vertices_px, fit: Fit, frame: Frame) -> Polygon:
    return Polygon([frame.to_5186(*fit.px_to_m(x, y)) for x, y in vertices_px])


# ── 대조 그림 ───────────────────────────────────────────────────────────
def overlay(base: Image.Image, feats: list[dict], frame: Frame, fit: Fit, boundary_px: list[tuple[float, float]],
            out: Path, *, color=(93, 52, 169), title: str = "", zoom_box: tuple[int, int, int, int] | None = None,
            zoom: float = 2.0, labels: dict[str, tuple[int, int, int]] | None = None) -> Path:
    """원 도면 위에 정합한 지적선(가는 회색)과 우리 경계(진한 색). 오른쪽에 확대 그림."""
    ov = base.convert("RGB").copy()
    dr = ImageDraw.Draw(ov)
    for f in feats:
        for ring in frame.rings(f):
            dr.line([fit.m_to_px(x, y) for x, y in ring], fill=(120, 120, 120), width=1)
        if labels and f["properties"]["pnu"] in labels:
            cx, cy = frame.to_m(*shape(f["geometry"]).representative_point().coords[0])
            px, py = fit.m_to_px(cx, cy)
            dr.text((px - 12, py + 6), (f["properties"].get("jibun") or "").split(" ")[0],
                    fill=labels[f["properties"]["pnu"]])
    if boundary_px:
        dr.line(list(boundary_px) + [boundary_px[0]], fill=color, width=3)
    if title:
        dr.rectangle((0, 0, 8 * len(title) + 10, 18), fill=(255, 255, 255))
        dr.text((4, 3), title, fill=(0, 0, 0))
    if zoom_box is None and boundary_px:
        xs, ys = [p[0] for p in boundary_px], [p[1] for p in boundary_px]
        m = 30
        zoom_box = (int(max(0, min(xs) - m)), int(max(0, min(ys) - m)), int(min(ov.width, max(xs) + m)),
                    int(min(ov.height, max(ys) + m)))
    if zoom_box:
        z = ov.crop(zoom_box)
        z = z.resize((int(z.width * zoom), int(z.height * zoom)), Image.LANCZOS)
        canvas = Image.new("RGB", (ov.width + z.width + 20, max(ov.height, z.height)), (255, 255, 255))
        canvas.paste(ov, (0, 0))
        canvas.paste(z, (ov.width + 20, 0))
        ImageDraw.Draw(ov).rectangle(zoom_box, outline=(0, 0, 0))
        ImageDraw.Draw(canvas).rectangle(zoom_box, outline=(0, 0, 0), width=2)
        ov = canvas
    out.parent.mkdir(parents=True, exist_ok=True)
    ov.save(out)
    return out
