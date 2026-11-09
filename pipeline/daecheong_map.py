"""대청마을 지도 대조 (feedback2.md §5-4, P13에서 pipeline/drawing_align.py로 정리). 네트워크 사용, 빌드 때만.

원 계획서 판정표 2번(경계 재작도)의 축소판이다. 고시(D9)에 지번 조서가 없어서:
 1. data_raw/D9.pdf 12쪽 '관리지역 결정도'를 2000px로 렌더링한다 (아래 꼭짓점을 이 크기에서 읽었다).
 2. 브이월드 2D 데이터(연속지적도 LP_PA_CBND_BUBUN)로 일원동 619 주변 필지 경계·지번을 받는다.
    기준점은 619 필지 경계 중심점(seed/parcels.geojson)이다. 지오코더 좌표는 쓰지 않는다.
 3. 결정도의 회색 지적선과 지적도 필지선을 같은 축척으로 그려 상호상관(FFT)으로 위치를 맞춘다 (배율·회전 탐색).
    축척 막대(0.947m/px)와 실제(약 0.79m/px)가 달라 배율을 넓게 찾는다.
 4. 결정도의 관리지역 경계(빨간 점선) 꼭짓점을 지적도 좌표로 옮기고, 필지 대표점이 경계 안쪽으로 충분히 들어간 필지를
    후보로 뽑는다 (build/daecheong/candidates.csv). seed/daecheong_map_reading.csv(P10에서 고른 16필지)와 비교해 알린다.
 5. --export-boundary: 경계를 seed/boundaries/D9.geojson으로, 정합 결과를 build/align/D9.json, 대조 그림을
    build/overlay_D9.png로 쓴다.

사용: python -m pipeline.daecheong_map [--export-boundary] [--refresh]
"""
import argparse
import csv
import json

import numpy as np

from pipeline import drawing_align as da
from pipeline.boundaries import compare_reference, write_boundary
from pipeline.common import BUILD, SEED, log, setup_stdout

OUT = BUILD / "daecheong"
DOC, PAGE = "D9", 12
CENTER_PNU = "1168011400106190000"                   # 일원동 619 (대표 지번)
RENDER_W = 2000
# 2000px 렌더링 기준 (확인 2026-10-26)
MAP_BOX = (405, 481, 1365, 1285)                     # 위쪽 지도 틀 (범례 칸 제외: x < 405+960)
M_PER_PX_BAR = 180 / 190                             # 축척 막대 0~180m = 190px
# 관리지역 경계(빨간 점선) 꼭짓점 — MAP_BOX 안 좌표 (d9_p12_top.png에서 읽음, 시계 방향)
BOUNDARY_PX = [(128, 348), (708, 112), (722, 117), (845, 432), (836, 448), (455, 608), (437, 600), (377, 457),
               (357, 465), (198, 528)]
LINE_DARK = 750                                      # 이 도면의 지적선은 아주 옅은 회색 (700이면 대부분 놓침)
SCALE_MIN, SCALE_MAX = 0.60, 1.00                    # 배율 탐색 범위 (m/px)
P10_SCALE = 0.79                                     # P10에서 쓴 값 (회귀 비교용)
MARGIN_M = 6.0                                       # 경계에서 이만큼 안쪽에 있는 필지만 후보
AREA_DOC = 90992.0                                   # D9 고시 면적 (관리지역 면적)
REF_NAME = "일원동 대청마을 북측구역"                   # 서울플랜+(UQ120) 비교 대상 — 비교만, 내보내지 않음


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-boundary", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    img, img_meta = da.page_image(DOC, PAGE, "render", render_w=RENDER_W)
    OUT.mkdir(parents=True, exist_ok=True)
    crop = img.crop(MAP_BOX)
    center = da.parcel_center(CENTER_PNU)
    frame = da.Frame(center)
    feats, fetch_meta = da.fetch_cadastral("D9", center, 600, 560, refresh=args.refresh)
    log(f"연속지적도 필지 {len(feats)}개 (요청 {fetch_meta['requests']}회 {fetch_meta['seconds']}초)")
    polys = [r for f in feats for r in frame.rings(f)]
    draw = da.line_mask(crop, exclude=("red",), dark=LINE_DARK)
    # P10 탐색(0.70~1.00)은 실제 배율(약 0.68)을 넣지 못해 0.79라는 틀린 봉우리를 골랐다 (P13 확인) → 0.60부터 찾는다
    res = da.align(draw, polys, np.arange(SCALE_MIN, SCALE_MAX + 1e-9, 0.005), (-1.0, -0.5, 0.0, 0.5, 1.0))
    fit = da.refine(draw, polys, res["best"])
    log(f"P10 기록 배율 {P10_SCALE}m/px와 차이 {fit.scale / P10_SCALE * 100 - 100:+.1f}%")
    log(f"맞춤: 상관 {fit.score:.3f}, 픽셀당 {fit.scale:.4f}m, 회전 {fit.angle}°, 이동 ({fit.dx}, {fit.dy})px · "
        f"2위 {res['second'].score:.3f} (1위/2위 {res['ratio']:.3f}{' 모호함' if res['ambiguous'] else ''})")

    boundary_m = [fit.px_to_m(x, y) for x, y in BOUNDARY_PX]
    rows = []
    for f in feats:
        p = f["properties"]
        ring = frame.rings(f)[0]
        cx, cy = da.centroid(ring)
        inside = da.point_in_poly(cx, cy, boundary_m)
        d = da.dist_to_poly(cx, cy, boundary_m)
        rows.append({"pnu": p["pnu"], "jibun": p.get("jibun") or "", "addr": p.get("addr"), "inside": inside,
                     "edge_m": round(d, 1), "cx": round(cx, 1), "cy": round(cy, 1)})
    with open(OUT / "candidates.csv", "w", encoding="utf-8-sig", newline="") as fp:
        wr = csv.DictWriter(fp, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(sorted(rows, key=lambda r: (not r["inside"], -r["edge_m"])))
    n_in = sum(r["inside"] and r["edge_m"] >= MARGIN_M for r in rows)
    log(f"경계 안쪽(여유 {MARGIN_M}m 이상) 필지 {n_in}개 → build/daecheong/candidates.csv")

    # P10에서 고른 16필지가 그대로 안쪽에 있는지
    with open(SEED / "daecheong_map_reading.csv", encoding="utf-8-sig", newline="") as fp:
        chosen = [r["pnu"] for r in csv.DictReader(fp)]
    by = {r["pnu"]: r for r in rows}
    still = [p for p in chosen if p in by and by[p]["inside"] and by[p]["edge_m"] >= MARGIN_M]
    log(f"seed/daecheong_map_reading.csv {len(chosen)}필지 중 여전히 경계 안쪽 {len(still)}필지"
        + ("" if len(still) == len(chosen) else f" — 빠짐: {sorted(set(chosen) - set(still))}"))

    if not args.export_boundary:
        return
    poly = da.vertices_to_5186(BOUNDARY_PX, fit, frame)
    ref = compare_reference(poly, REF_NAME)
    write_boundary(DOC, poly, {
        "doc_id": DOC, "source_page": f"{DOC} p{PAGE:03d}", "kind": "project",
        "project_key": "ilwon-daecheong-north-moatown", "area_m2_doc": AREA_DOC,
        "align_score": round(fit.score, 4), "align_ratio": round(res["ratio"], 3), "m_per_px": round(fit.scale, 4),
        "method": "도면 꼭짓점 10개(2000px 렌더) × 연속지적도 FFT 정합"})
    da.save_result(DOC, {
        "doc": DOC, "page": PAGE, "image": dict(img_meta, map_box=list(MAP_BOX)),
        "scale_bar_m_per_px": round(M_PER_PX_BAR, 4), "search": f"{SCALE_MIN}~{SCALE_MAX} m/px 0.005 간격, 회전 -1~1° 0.5° 간격, 1위 둘레 ±1.2% 0.2% 간격 다시 찾음", "p10_scale": P10_SCALE, "line_dark": LINE_DARK,
        "best": da.fit_json(fit), "second": da.fit_json(res["second"]), "ratio": round(res["ratio"], 3),
        "ambiguous": res["ambiguous"], "cadastral": fetch_meta, "center_pnu": CENTER_PNU,
        "area_m2_geom": round(poly.area, 1), "area_m2_doc": AREA_DOC, "reference": ref,
        "candidates_inside": n_in, "reading_still_inside": f"{len(still)}/{len(chosen)}"})
    bpx = BOUNDARY_PX
    da.overlay(crop, feats, frame, fit, bpx, BUILD / "overlay_D9.png",
               title=f"D9 p012  {fit.scale:.3f} m/px  score {fit.score:.3f}",
               labels={p: (0, 120, 0) for p in chosen})
    log(f"seed/boundaries/D9.geojson 면적 {poly.area:,.1f}㎡ (고시 {AREA_DOC:,.1f}㎡, {poly.area / AREA_DOC * 100 - 100:+.2f}%)"
        + (f" · 서울플랜+ {ref['area_m2']:,.1f}㎡ IoU {ref['iou']:.3f} 하우스도르프 {ref['hausdorff_m']:.1f}m" if ref else ""))


if __name__ == "__main__":
    main()
