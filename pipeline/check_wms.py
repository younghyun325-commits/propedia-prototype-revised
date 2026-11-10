"""브이월드 WMS 레이어 이름 확인 (docs/map/PLAN.md P15-2). 네트워크 사용, 빌드 때만.

GetCapabilities 응답에서 레이어 이름·제목·스타일과 GetLegendGraphic 지원 여부를 표로 보여 준다.
레이어 이름은 추측하지 않고 이 표에서 골라 web/src/map/wms.ts 상수로 둔다.
키는 출력·저장하지 않는다. 응답 원문도 저장하지 않는다 (표만 출력).

사용: python -m pipeline.check_wms [검색어 ...]   (기본: 용도지역·용도지구·지구단위·지적·lp_pa_cbnd)
"""
import re
import sys
import xml.etree.ElementTree as ET

import httpx

from core.live.vworld import domain as vworld_domain
from pipeline.build_map_base import api_key
from pipeline.common import fail, log, setup_stdout

WMS_URL = "https://api.vworld.kr/req/wms"
DEFAULT_TERMS = ["용도지역", "용도지구", "지구단위", "지적", "lp_pa_cbnd", "uq1", "uq"]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def capabilities() -> ET.Element:
    key = api_key()
    try:
        r = httpx.get(WMS_URL, params={"service": "WMS", "request": "GetCapabilities", "version": "1.3.0",
                                       "key": key, "domain": vworld_domain()}, timeout=30)
    except httpx.HTTPError as e:
        fail(f"GetCapabilities 요청 실패 ({type(e).__name__})")
    if r.status_code != 200:
        fail(f"GetCapabilities HTTP {r.status_code}")
    text = r.text
    if key and key in text:
        text = text.replace(key, "***")
    try:
        return ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        fail(f"응답이 XML이 아닙니다: {re.sub(r'\\s+', ' ', text[:200])}")


def main(argv=None) -> int:
    setup_stdout()
    terms = [t.lower() for t in (argv if argv is not None else sys.argv[1:]) or DEFAULT_TERMS]
    root = capabilities()
    ops = {_local(e.tag) for e in root.iter() if _local(e.tag).startswith("Get")}
    log(f"지원 요청: {', '.join(sorted(ops))}")
    rows = []
    for lay in root.iter():
        if _local(lay.tag) != "Layer":
            continue
        name = title = None
        styles, legend = [], False
        for ch in lay:
            t = _local(ch.tag)
            if t == "Name":
                name = (ch.text or "").strip()
            elif t == "Title":
                title = (ch.text or "").strip()
            elif t == "Style":
                for s in ch:
                    if _local(s.tag) == "Name":
                        styles.append((s.text or "").strip())
                    if _local(s.tag) == "LegendURL":
                        legend = True
        if not name:
            continue
        rows.append((name, title or "", ",".join(styles), "있음" if legend else "-"))
    log(f"레이어 전체 {len(rows)}개")
    hit = [r for r in rows if any(t in (r[0] + " " + r[1]).lower() for t in terms)]
    log("이름 | 제목 | 스타일 | 범례 URL")
    for r in hit:
        log(" | ".join(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
