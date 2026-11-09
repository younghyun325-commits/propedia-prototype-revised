"""고시 도면 정합 → 경계 (docs/map/PLAN.md P13-3·4). 네트워크 사용(연속지적도, 캐시 있으면 안 씀), 빌드 때만.

입력: seed/boundaries/{doc}_px.yaml (도면 쪽·이미지 방식·지도 틀·축척 막대·경계 꼭짓점 또는 영역 규칙)
     data_raw/{doc}.pdf, seed/parcels.geojson(기준점), 브이월드 연속지적도
출력: seed/boundaries/{doc}.geojson (채택한 것만), build/align/{doc}.json, build/align/{doc}_parcels.csv,
     build/overlay_{doc}.png

- 배율은 막대 값(또는 A3 1/1000 계산값)의 ±range_pct% 안에서 1% 간격, 회전 -1~1°로 찾고 1위 둘레를 다시 잘게 찾는다.
- 1위/2위 < 1.05면 '모호함'으로 알린다 (멈추지 않음).
- 사업 구역(D1)은 고시 면적 ±5%를 넘어도 경계 파일은 쓰되 종료 코드 2로 알린다 (멈춤 조건, P13-3-3).
- 규제 구역 D5는 ±5% 밖이면 채택하지 않는다: 경계 파일을 쓰지 않고(있으면 지움) build/align/D5.json에 미채택으로 남긴다.

사용: python -m pipeline.align_drawings D1 [D10 D5 ...] [--refresh]
"""
import argparse
import csv
import sys

import numpy as np
import yaml
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, shape

from pipeline import drawing_align as da
from pipeline.boundaries import BOUNDARIES, compare_reference, write_boundary
from pipeline.common import BUILD, SEED, log, setup_stdout
from pipeline.geo import to_5186

DOC_AREA = {  # 고시 면적 (evals/goldset/boundaries.yaml과 같은 값)
    "D1": 22123.6, "D9": 90992.0, "D10": 79269.1, "D5": 1149476.0}
KIND = {"D1": "project", "D9": "project", "D10": "regulation", "D5": "regulation"}
PROJECT_KEY = {"D1": "apgujeong-6-1-hanyang7", "D9": "ilwon-daecheong-north-moatown"}
REFERENCE = {"D9": "일원동 대청마을 북측구역", "D10": "대치선경"}   # 서울플랜+ (비교에만)
MUST_LIST = {"D1": ["1168011000105270000", "1168011000105280000", "1168011000105050000", "1168011000105080000",
                    "1168011000105040000"]}
TOLERANCE = 0.05
MARGIN_M = 6.0
COLORS = {"project": (93, 52, 169), "regulation": (176, 122, 0)}


def red_region(crop: Image.Image, cfg: dict) -> "Polygon":
    """빨간 일점쇄선·빗금 → 면 (지도 틀 픽셀 좌표). 1/f로 줄여 닫힘(팽창→구멍 메움→침식)."""
    from PIL import ImageFilter
    f = cfg["downsample"]
    a = np.asarray(crop).astype(int)
    red = da.color_mask(a, "red")
    h, w = red.shape
    red = red[: h // f * f, : w // f * f].reshape(h // f, f, w // f, f).any(axis=(1, 3))
    img = Image.fromarray((red * 255).astype(np.uint8))
    k = cfg["close_px"] * 2 + 1
    img = img.filter(ImageFilter.MaxFilter(k))
    # 바깥에서 채워 들어가 구멍을 메운다
    pad = Image.new("L", (img.width + 2, img.height + 2), 0)
    pad.paste(img, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)
    filled = np.asarray(pad)[1:-1, 1:-1] != 128
    img = Image.fromarray((filled * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(k))
    m = np.asarray(img) > 0
    poly = da.mask_to_polygon(m, None, None, simplify_px=cfg.get("simplify_px", 1.0))
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = Polygon(poly.exterior)      # 안쪽 구멍(글자 등)은 없앤다
    from shapely.affinity import scale
    return scale(poly, xfact=f, yfact=f, origin=(0, 0))


def classify(feats, boundary5186, frame: da.Frame) -> list[dict]:
    rows = []
    edge = boundary5186.exterior
    for f in feats:
        g = to_5186(shape(f["geometry"]))
        if not g.is_valid:
            g = g.buffer(0)
        rp = g.representative_point()
        inside = boundary5186.contains(rp)
        d = edge.distance(rp)
        ov = g.intersection(boundary5186).area / g.area if g.area else 0.0
        if inside and d >= MARGIN_M:
            cls = "안쪽"
        elif inside:
            cls = "경계 걸침(안)"
        elif d < MARGIN_M:
            cls = "경계 걸침(밖)"
        else:
            cls = "밖"
        rows.append({"pnu": f["properties"]["pnu"], "jibun": f["properties"].get("jibun"), "class": cls,
                     "edge_m": round(d, 1), "overlap_pct": round(ov * 100, 1), "parcel_m2": round(g.area, 1)})
    return rows


def run(doc: str, refresh: bool) -> dict:
    cfg = yaml.safe_load((BOUNDARIES / f"{doc}_px.yaml").read_text(encoding="utf-8"))
    im = cfg["image"]
    img, meta = da.page_image(doc, cfg["pdf_page"], im["method"], index=im.get("index", 0),
                              render_w=im.get("render_w", 3000))
    if list(img.size) != im["size"]:
        log(f"  ※ 이미지 크기 {img.size}가 yaml {im['size']}와 다릅니다")
    bx0, by0, bx1, by1 = cfg["map_box"]
    crop = img.crop((bx0, by0, bx1, by1))
    s = cfg["search"]
    center = da.parcel_center(cfg["center_pnu"])
    frame = da.Frame(center)
    hw, hh = cfg["cadastral_half_m"]
    feats, fmeta = da.fetch_cadastral(doc, center, hw, hh, tuple(cfg.get("cadastral_tiles", (1, 1))), refresh)
    log(f"{doc}: 연속지적도 {fmeta['parcels']}필지 · 요청 {fmeta['requests']}회 {fmeta['seconds']}초 · 타일 {fmeta['tiles']}")
    polys = [r for f in feats for r in frame.rings(f)]
    draw = da.line_mask(crop, exclude=tuple(s["exclude_colors"]), dark=s["line_dark"])
    s0 = cfg["scale_bar"]["m_per_px"]
    rp = s["range_pct"] / 100
    scales = s0 * np.exp(np.arange(np.log(1 - rp), np.log(1 + rp) + 1e-9, 0.01))
    res = da.align(draw, polys, scales, s["angles"], work=s.get("work", 1))
    fit = da.refine(draw, polys, res["best"])
    log(f"{doc}: 배율 {fit.scale:.4f}m/px (막대 {s0:.4f}, {fit.scale / s0 * 100 - 100:+.1f}%), 회전 {fit.angle}°, "
        f"상관 {fit.score:.3f} · 탐색 1위 {res['best'].score:.3f} / 2위 {res['second'].score:.3f} = {res['ratio']:.3f}"
        + (" ※ 모호함" if res["ambiguous"] else ""))

    if "vertices" in cfg:
        bpx = [(x - bx0, y - by0) for x, y in cfg["vertices"]]
        poly = da.vertices_to_5186(bpx, fit, frame)
        method = f"도면 꼭짓점 {len(bpx)}개 × 연속지적도 FFT 정합"
    else:
        ppx = red_region(crop, cfg["region"])
        bpx = list(ppx.exterior.coords)[:-1]
        poly = da.px_polygon_to_5186(ppx, fit, frame)
        method = f"빨간 경계·빗금 영역 자동 추출(꼭짓점 {len(bpx)}개) × 연속지적도 FFT 정합"
    if not poly.is_valid:
        poly = poly.buffer(0)
    area_doc = DOC_AREA[doc]
    diff = poly.area / area_doc - 1
    ok = abs(diff) <= TOLERANCE
    ref = compare_reference(poly, REFERENCE[doc]) if doc in REFERENCE else None
    kind = KIND[doc]
    adopted = ok or kind == "project"     # 사업 구역은 파일을 쓰되 멈춤 신호, 규제 구역은 ±5% 밖이면 미채택
    rows = classify(feats, poly, frame)
    rows = [r for r in rows if r["overlap_pct"] > 0 or r["pnu"] in MUST_LIST.get(doc, [])]
    rows.sort(key=lambda r: (-r["overlap_pct"], r["pnu"]))
    BUILD.joinpath("align").mkdir(parents=True, exist_ok=True)
    with open(BUILD / "align" / f"{doc}_parcels.csv", "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    out = BOUNDARIES / f"{doc}.geojson"
    if adopted:
        props = {"doc_id": doc, "kind": kind, "source_page": f"{doc} p{cfg['pdf_page']:03d}", "area_m2_doc": area_doc,
                 "align_score": round(fit.score, 4), "align_ratio": round(res["ratio"], 3),
                 "m_per_px": round(fit.scale, 4), "method": method}
        if doc in PROJECT_KEY:
            props["project_key"] = PROJECT_KEY[doc]
        write_boundary(doc, poly, props)
    elif out.exists():
        out.unlink()
    result = {
        "doc": doc, "page": cfg["pdf_page"], "image": dict(meta, map_box=cfg["map_box"]),
        "scale_bar_m_per_px": s0, "search": f"막대 ±{s['range_pct']}% 1% 간격, 회전 {s['angles']}, 1위 둘레 ±1.2% 0.2% 간격",
        "best": da.fit_json(fit), "coarse_best": da.fit_json(res["best"]), "second": da.fit_json(res["second"]),
        "ratio": round(res["ratio"], 3), "ambiguous": res["ambiguous"], "cadastral": fmeta,
        "center_pnu": cfg["center_pnu"], "method": method, "area_m2_geom": round(poly.area, 1),
        "area_m2_doc": area_doc, "area_diff_pct": round(diff * 100, 2), "within_5pct": ok,
        "adopted": adopted and ok if kind == "regulation" else adopted, "reference": ref,
        "parcels_inside": sum(r["class"] == "안쪽" for r in rows)}
    da.save_result(doc, result)
    labels = {r["pnu"]: (0, 120, 0) if r["class"] == "안쪽" else (200, 0, 0)
              for r in rows if r["pnu"] in MUST_LIST.get(doc, [])}
    da.overlay(crop, feats, frame, fit, bpx, BUILD / f"overlay_{doc}.png", color=COLORS[kind],
               title=f"{doc} p{cfg['pdf_page']:03d}  {fit.scale:.4f} m/px  score {fit.score:.3f}  area {diff * 100:+.2f}%",
               labels=labels or None, zoom=1.0 if crop.width > 2000 else 2.0)
    log(f"{doc}: 면적 {poly.area:,.1f}㎡ / 고시 {area_doc:,.1f}㎡ = {diff * 100:+.2f}% → "
        + ("채택" if result["adopted"] else ("±5% 밖 (멈춤 조건)" if kind == "project" else "미채택"))
        + (f" · 서울플랜+ {ref['name']} {ref['area_m2']:,.1f}㎡ IoU {ref['iou']:.3f} 하우스도르프 {ref['hausdorff_m']}m" if ref else ""))
    return result


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    code = 0
    for doc in a.docs:
        r = run(doc, a.refresh)
        if KIND[doc] == "project" and not r["within_5pct"]:
            code = 2
    return code


if __name__ == "__main__":
    sys.exit(main())
