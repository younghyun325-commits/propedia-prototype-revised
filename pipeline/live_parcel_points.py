"""필지 클릭 조회 측정용 대표 좌표 (docs/map/PLAN.md P15-4). 네트워크 사용(2D 데이터), 빌드 때만.

지번 5건의 PNU를 만들고 브이월드 2D 데이터 연속지적도(LP_PA_CBND_BUBUN) 경계를 받아 중심점을 구해
evals/goldset/live_parcels.yaml에 쓴다. 좌표는 지오코더가 아니라 필지 경계 중심점이다 (저장 가능).
중심점이 필지 밖이면 shapely representative_point를 쓰고 basis에 적는다. 같은 입력이면 같은 출력 (멱등).

사용: python -m pipeline.live_parcel_points
"""
import sys

import yaml
from shapely.geometry import shape

from core.address import make_pnu
from pipeline.common import ROOT, connect_rw, fail, log, setup_stdout
from pipeline.geo import RAW, get_feature

PARCELS = [("세곡동", 279), ("역삼동", 823), ("논현동", 100), ("삼성동", 159), ("개포동", 12)]
OUT = ROOT / "evals" / "goldset" / "live_parcels.yaml"


def main() -> int:
    setup_stdout()
    con = connect_rw()
    codes = {r["dong_name"]: r["bjd_code"] for r in con.execute("SELECT dong_name, bjd_code FROM bjd_codes")}
    con.close()
    rows = []
    for dong, main_no in PARCELS:
        pnu = make_pnu(codes[dong], main_no)
        raw = get_feature("LP_PA_CBND_BUBUN", RAW / "parcels" / f"{pnu}.json", attrFilter=f"pnu:=:{pnu}")
        if not raw["features"]:
            fail(f"{dong} {main_no} ({pnu}): 연속지적도에 없음")
        g = shape(raw["features"][0]["geometry"])
        c = g.centroid
        basis = "centroid"
        if not g.contains(c):
            c, basis = g.representative_point(), "representative_point"
        rows.append({"label": f"강남구 {dong} {main_no}", "pnu": pnu, "lat": round(c.y, 6), "lon": round(c.x, 6),
                     "basis": f"vworld-2d:LP_PA_CBND_BUBUN {basis}"})
        log(f"{dong} {main_no} → {pnu} · ({c.y:.6f}, {c.x:.6f}) {basis}")
    doc = {"draft": True, "author": "claude-code (초안)",
           "note": "필지 클릭 조회(parcel-at) 측정: 지번 5건의 연속지적도 경계 중심점. 지오코더 좌표 아님. "
                   "docs/map/PLAN.md P15 완료 확인 지번.",
           "parcels": rows}
    OUT.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8", newline="\n")
    log(f"→ {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
