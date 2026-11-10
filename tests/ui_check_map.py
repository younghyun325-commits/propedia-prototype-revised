"""지도 화면 점검 (docs/map/PLAN.md P12·P13). Playwright(Chromium), pytest 수집 대상 아님.

미리 띄울 것: uvicorn 8000 + `npm --prefix web run dev`(3000). 빌드본은 `npm --prefix web run build` 뒤 8000/map/.
- 개발 서버는 항상 http://localhost:3000/map/ 으로 연다 (브이월드 개발 키 서비스 URL이 localhost:3000).
- 키 값은 출력하지 않는다: 타일 주소의 키 자리는 *** 로 가린다.
- 빌드본은 ?debug=1로 연다 (지도 객체 window.__propediaMap은 개발 서버 또는 ?debug=1일 때만 노출).
- P13: Propedia 레이어 4종이 스타일에 있고 그려지는지, '확인 전' 라벨, 스크린샷 3장(--shot).
- P14: 레이어 끄기·URL·새로고침 복원, 투명도, 겹침 보기, 명령 팔레트(Ctrl+K), 필지 강조·툴팁, 사업 목록, 고시 칩·기준일,
  호버 툴팁·겹친 지점 선택 목록, 라벨 충돌, 키보드, 스크린샷 5장(--shot). 건수는 /api/v1/map/manifest에서 읽는다.
- P15: 공식 참고 레이어(지연 로딩·출처·WMS 줌 조건·타일 200), 빈 곳 클릭 필지 조회(강조·카드·URL 복원),
  클릭 우선순위(사업 구역 먼저), 참고 구역 이름, 스크린샷 3장(--shot). 클릭 지점은 GeoJSON에서 계산한다(shapely).
- P18: 생활 인프라(학교·역 기본 켜짐, 정류장 줌 15 안내, 클러스터·이름, 편의시설 분류 행), 역·정류장 인스펙터, 노선 선택 모드,
  반경 보기, 겹침 보기, Ctrl+K 역·정류장 번호·노선, 스크린샷 5장(map_06a~e), --perf로 프레임 시간

사용: python tests/ui_check_map.py [--built] [--shot]
"""
import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "docs" / "screens"
SHOT = SCREENS / "map_02a_layers_preview.png"
SHOT_HANYANG = SCREENS / "map_02b_hanyang7.png"
SHOT_DAECHEONG = SCREENS / "map_02c_daecheong.png"
PROPEDIA_SOURCES = ["propedia-project", "propedia-impact", "propedia-parcel", "propedia-regulation"]
PADDING = "{left: 380, right: 460, top: 130, bottom: 110}"
COUNT_JS = """() => { const m = window.__propediaMap; if (!m) return null;
  const out = {};
  for (const s of %s) {
    const ids = m.getStyle().layers.filter(l => l.source === s).map(l => l.id);
    out[s] = ids.length ? m.queryRenderedFeatures({layers: ids}).length : -1;
  }
  return out }""" % PROPEDIA_SOURCES
FIT_JS = """async (key) => { const m = window.__propediaMap;
  const fc = await (await fetch('/data/layers/propedia_projects.geojson')).json();
  const f = fc.features.find(x => x.properties.project_key === key);
  let w = 999, s = 999, e = -999, n = -999;
  const walk = c => typeof c[0] === 'number' ? (w = Math.min(w, c[0]), e = Math.max(e, c[0]), s = Math.min(s, c[1]), n = Math.max(n, c[1])) : c.forEach(walk);
  walk(f.geometry.coordinates);
  m.fitBounds([[w, s], [e, n]], {padding: %s, duration: 0});
  await new Promise(r => m.once('idle', r));
  return m.getZoom() }""" % PADDING
KEY_RE = re.compile(r"(/req/wmts/1\.0\.0/)[^/]+/")
WMS_KEY_RE = re.compile(r"(KEY=)[^&]+", re.I)
WORKER_RE = re.compile(r"worker", re.I)


def mask(url: str) -> str:
    return WMS_KEY_RE.sub(r"\1***", KEY_RE.sub(r"\1***/", url))


SHOT_LAYERS = SCREENS / "map_02_layers.png"
SHOT_OVERLAP = SCREENS / "map_02d_overlap.png"
SHOT_SEARCH = SCREENS / "map_02e_search.png"
SHOT_STATUS = SCREENS / "map_02f_status.png"
SHOT_LABELS_AFTER = SCREENS / "map_02g_labels_after.png"

JS_VIS = "(id) => window.__propediaMap.getLayoutProperty(id, 'visibility') ?? 'visible'"
JS_PAINT = "([id, p]) => window.__propediaMap.getPaintProperty(id, p)"
JS_CENTER = "() => { const c = window.__propediaMap.getCenter(); return [c.lng, c.lat, window.__propediaMap.getZoom()] }"
JS_RENDERED = """(ids) => { const m = window.__propediaMap; const ok = ids.filter(i => m.getLayer(i));
  return ok.length ? m.queryRenderedFeatures({layers: ok}).length : -1 }"""
JS_IDLE = """() => new Promise(r => { const m = window.__propediaMap;
  if (m.loaded() && !m.isMoving()) r(true); else m.once('idle', () => r(true)); setTimeout(() => r(false), 6000) })"""
# 겹침 보기: 지도에 걸린 페인트 식을 도형 속성에 적용해 본 값 (영향권 밖 = impact_buffer_m null)
JS_OVERLAP = """() => { const m = window.__propediaMap;
  const ev = (e, v) => Array.isArray(e) && e[0] === 'case' ? (v === null || v === undefined ? e[2] : e[3]) : e;
  const out = {};
  for (const [src, layer, prop, likely] of [['propedia-regulation', 'propedia-regulation-fill', 'fill-opacity', null],
                                            ['propedia-parcel', 'propedia-parcel-line', 'line-opacity', false],
                                            ['propedia-parcel', 'propedia-parcel-line-likely', 'line-opacity', true]]) {
    const e = m.getPaintProperty(layer, prop);
    const seen = new Set(); const vals = [];
    for (const f of m.querySourceFeatures(src)) {
      if (seen.has(f.properties.id)) continue; seen.add(f.properties.id);
      if (likely !== null && likely !== (f.properties.inclusion === 'likely')) continue;
      vals.push([f.properties.id, ev(e, f.properties.impact_buffer_m)]) }
    out[layer] = vals }
  return out }"""
JS_PROJECT_PT = """(fid) => { const m = window.__propediaMap;
  const f = m.querySourceFeatures('propedia-project').find(x => x.properties.id === fid);
  if (!f) return null; let sx = 0, sy = 0, n = 0;
  const walk = c => typeof c[0] === 'number' ? (sx += c[0], sy += c[1], n++) : c.forEach(walk);
  walk(f.geometry.coordinates); const p = m.project([sx / n, sy / n]);
  const r = m.getCanvas().getBoundingClientRect(); return [p.x + r.left, p.y + r.top] }"""
JS_PARCEL_PT = """async (pnu) => { const m = window.__propediaMap;
  const fc = await (await fetch('/data/layers/propedia_parcels.geojson')).json();
  const f = fc.features.find(x => x.properties.pnu === pnu); if (!f) return null;
  const p = m.project([f.properties.centroid_lon, f.properties.centroid_lat]);
  const r = m.getCanvas().getBoundingClientRect(); return [p.x + r.left, p.y + r.top] }"""


def _q(page, key: str) -> str | None:
    from urllib.parse import parse_qs, urlparse
    v = parse_qs(urlparse(page.url).query, keep_blank_values=True).get(key)
    return v[0] if v else None


def _wait_url(page, pred, timeout=3000) -> bool:
    end = time.time() + timeout / 1000
    while time.time() < end:
        if pred(page.url):
            return True
        page.wait_for_timeout(100)
    return pred(page.url)


def _ready(page) -> None:
    page.wait_for_function("() => window.__propediaMap && window.__propediaMap.loaded()", timeout=20000)
    page.wait_for_selector("[data-testid=layer-tree]", timeout=20000)
    page.wait_for_load_state("networkidle")
    page.evaluate(JS_IDLE)


def _open(page, url: str, extra: str = "") -> None:
    sep = "&" if "?" in url else "?"
    page.goto(url + (sep + extra if extra else ""))
    _ready(page)


def _palette(page, query: str) -> None:
    page.keyboard.press("Control+K")
    page.wait_for_selector("[data-testid=palette-input]", timeout=5000)
    page.fill("[data-testid=palette-input]", query)
    page.wait_for_timeout(400)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)


def _text(page, sel: str) -> str:
    return page.inner_text(sel) if page.locator(sel).count() else ""


def p14_checks(page, url: str, check, shot: bool) -> None:
    man = page.evaluate("async () => (await fetch('/api/v1/map/manifest')).json()")
    layers = {x["id"]: x for x in man["layers"]}
    projects = page.evaluate("async () => (await fetch('/api/v1/map/projects')).json()")["projects"]

    # ---- 첫 화면 (URL 파라미터 없음)
    _open(page, url)
    check("[P14] 레이어 트리 role=tree·체크박스는 실제 input",
          page.locator("[role=tree] [role=treeitem]").count() > 5
          and page.locator("[data-testid=layer-toggle-projects]").evaluate("e => e.tagName") == "INPUT")
    shown = {i: page.inner_text(f"[data-testid=layer-count-{i}]") for i in ("projects", "parcels", "impact250")}
    want = {i: f"{layers[i]['count']}건" for i in shown}
    check("[P14] 레이어 건수 = manifest", shown == want, f"{shown}")
    legend = page.inner_text("[data-testid=parcel-legend]")
    by = layers["parcels"]["count_by_judgment"]
    check("[P14] 필지 범례 두 줄 + 판정별 건수 (manifest)",
          "실선" in legend and "점선" in legend and f"{by['likely']}건" in legend
          and f"{by['included'] + by['possible']}건" in legend, legend.replace("\n", " / "))
    check("[P14] D5 행: 비활성 + '경계 확인 전'",
          page.locator("[data-testid=layer-toggle-regulation-d5]").is_disabled()
          and "경계 확인 전" in page.inner_text("[data-testid=layer-row-regulation-d5]"))
    infra_on = [i for i in ("schools", "stations", "bus_stops", "pois")
                if not page.locator(f"[data-testid=layer-toggle-{i}]").is_disabled()]
    check("[P14→P18] 생활 인프라 4종 활성 (준비 중 레이어 없음)", len(infra_on) == 4, str(infra_on))
    page.hover("[data-testid=layer-row-projects] button[aria-label$='레이어 정보']")
    page.wait_for_timeout(200)
    tip = _text(page, "[data-testid=layer-info-projects]")
    check("[P14] 정보 툴팁(포털): 원천·기준일·라이선스·근거 쪽",
          all(k in tip for k in ("원천", "기준일", "라이선스", "근거 쪽")) and "D1 p18" in tip
          and page.locator("#portal-root [data-testid=layer-info-projects]").count() == 1, tip.replace("\n", " ")[:120])
    page.mouse.move(700, 600)
    page.wait_for_timeout(150)
    if shot:
        page.screenshot(path=str(SHOT_LAYERS))

    # 상단 바: 고시 칩·기준일
    chips = page.locator("[data-testid=notice-chip]").count()
    as_of = page.inner_text("[data-testid=as-of]")
    check("[P14] 고시 칩 1개 이상 (최대 3)", 1 <= chips <= 3, f"{chips}개")
    check("[P14] 기준일: 오늘(KST)·DB 기준", "오늘" in as_of and "DB 기준" in as_of and "2026-10-06" in as_of,
          as_of.replace("\n", " "))
    page.locator("[data-testid=notice-chip]").first.click()
    page.wait_for_timeout(150)
    pop = _text(page, "[data-testid=notice-popover]")
    check("[P14] 고시 칩 팝오버: 종류·효력·근거 쪽", all(k in pop for k in ("종류", "효력", "근거")), pop.replace("\n", " ")[:120])
    page.keyboard.press("Escape")

    # 라벨 충돌 (강남구 전체 줌): 규제 구역을 켜도 보이는 라벨끼리 겹치지 않음, 규제 라벨은 줌 14 미만에서 숨김
    page.click("[data-testid=layer-toggle-regulations]")
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(300)
    loc = page.locator("[data-testid=area-label]")
    boxes = [loc.nth(i).bounding_box() for i in range(loc.count())]
    clash = any(a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and a["y"] < b["y"] + b["height"]
                and b["y"] < a["y"] + a["height"] for i, a in enumerate(boxes) for b in boxes[i + 1:])
    kinds = page.eval_on_selector_all("[data-testid=area-label]", "es => es.map(e => e.dataset.kind)")
    check("[P14] 라벨 충돌 없음 (강남구 전체 줌, 규제 라벨 숨김)", not clash and "regulation" not in kinds, f"{kinds}")
    if shot:
        page.screenshot(path=str(SHOT_LABELS_AFTER))
    page.evaluate("() => window.__propediaMap.jumpTo({center: [127.0605, 37.5025], zoom: 14.5})")
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(300)
    kinds = page.eval_on_selector_all("[data-testid=area-label]", "es => es.map(e => e.dataset.kind)")
    check("[P14] 줌 14 이상에서는 규제 라벨 표시", "regulation" in kinds, f"{kinds}")
    page.click("[data-testid=layer-toggle-regulations]")
    page.click("[data-testid=work-tab-gangnam]")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)

    # ---- 레이어 끄기 → 지도에서 사라짐 + URL → 새로고침 복원
    page.click("[data-testid=layer-toggle-projects]")
    page.evaluate(JS_IDLE)
    vis = page.evaluate(JS_VIS, "propedia-project-fill")
    n = page.evaluate(JS_RENDERED, ["propedia-project-fill", "propedia-project-line"])
    ok_url = _wait_url(page, lambda u: _q(page, "layers") is not None and "projects" not in (_q(page, "layers") or ""))
    check("[P14] 사업 구역 끄기 → visibility none·그려진 도형 0·URL layers", vis == "none" and n == 0 and ok_url,
          f"{vis}, {n}, layers={_q(page, 'layers')}")
    page.click("[data-testid=layer-expand-impact250]")
    page.locator("[data-testid=layer-opacity-impact250]").fill("50")
    page.wait_for_timeout(100)
    op = page.evaluate(JS_PAINT, ["propedia-impact250-fill", "fill-opacity"])
    ok_op = _wait_url(page, lambda u: "impact250:50" in (_q(page, "op") or ""))
    check("[P14] 투명도 50% → fill-opacity 0.04 (= 8% × 50%)·URL op", op == 0.04 and ok_op, f"{op}, op={_q(page, 'op')}")
    _wait_url(page, lambda u: _q(page, "c") is not None)
    before = page.evaluate(JS_CENTER)
    page.wait_for_timeout(400)
    page.reload()
    _ready(page)
    after = page.evaluate(JS_CENTER)
    restored = (not page.is_checked("[data-testid=layer-toggle-projects]")
                and page.evaluate(JS_VIS, "propedia-project-fill") == "none"
                and page.evaluate(JS_PAINT, ["propedia-impact250-fill", "fill-opacity"]) == 0.04)
    near = abs(before[0] - after[0]) < 1e-4 and abs(before[1] - after[1]) < 1e-4 and abs(before[2] - after[2]) < 0.02
    check("[P14] 새로고침 후 같은 화면 (레이어·투명도·카메라)", restored and near,
          f"{[round(x, 5) for x in before]} → {[round(x, 5) for x in after]}")

    # ---- 겹침 보기 (규제 구역 켜고): 영향권 밖 도형만 25%
    _open(page, url.split("?")[0] + ("?debug=1" if "debug=1" in url else ""),
          "layers=projects,impact250,impact500,parcels,regulations")
    page.click("[data-testid=overlap-switch]")
    page.evaluate(JS_IDLE)
    # 필지는 줌 14 이상에서만 타일에 들어가므로 두 사업이 다 보이는 곳으로 옮겨 원천 도형을 채운다
    page.evaluate("() => window.__propediaMap.jumpTo({center: [127.085, 37.494], zoom: 14.2})")
    page.evaluate(JS_IDLE)
    ov = page.evaluate(JS_OVERLAP)
    page.evaluate("() => window.__propediaMap.jumpTo({center: [127.0435, 37.5294], zoom: 15})")
    page.evaluate(JS_IDLE)
    ov2 = page.evaluate(JS_OVERLAP)
    reg = dict(ov["propedia-regulation-fill"])
    par = dict(ov["propedia-parcel-line"] + ov["propedia-parcel-line-likely"]
               + ov2["propedia-parcel-line"] + ov2["propedia-parcel-line-likely"])
    check("[P14] 겹침 보기: 영향권 밖(D10) 25%, 영향권 안 필지는 그대로(전체)",
          reg.get("regulation:D10") == 0.25 and bool(par) and all(v == 1 for v in par.values())
          and len(par) == layers["parcels"]["count"] and _q(page, "ov") == "1",
          f"D10 {reg.get('regulation:D10')}, 필지 {sorted(set(par.values()))}×{len(par)}, ov={_q(page, 'ov')}")
    if shot:
        page.evaluate("""() => window.__propediaMap.fitBounds([[127.055, 37.488], [127.092, 37.508]],
                          {padding: {left: 360, right: 440, top: 100, bottom: 80}, duration: 0})""")
        page.evaluate(JS_IDLE)
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_OVERLAP))

    # ---- 명령 팔레트
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    _open(page, home)
    _palette(page, "일원동 619")
    groups = page.locator("[data-testid=palette-group]").all_inner_texts()
    if shot:
        page.screenshot(path=str(SHOT_SEARCH))
    check("[P14] Ctrl+K 팔레트: 사업·주소 두 그룹", groups[:2] == ["사업", "주소"], str(groups))
    c0 = page.evaluate(JS_CENTER)
    page.keyboard.press("Enter")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    c1 = page.evaluate(JS_CENTER)
    moved = abs(c1[0] - 127.084) < 0.01 and abs(c1[1] - 37.494) < 0.01 and c1[2] > c0[2]
    check("[P14] '일원동 619' → 지도 이동", moved and page.locator("[data-testid=palette]").count() == 0,
          f"{[round(x, 4) for x in c0]} → {[round(x, 4) for x in c1]}")
    _palette(page, "한양")
    has_proj = page.locator("[data-testid=palette-item-project]").count() >= 1
    page.keyboard.press("Enter")
    ok = _wait_url(page, lambda u: _q(page, "sel") == "project:1")
    check("[P14] '한양' → 사업 결과 → sel=project:1", has_proj and ok, f"sel={_q(page, 'sel')}")
    page.wait_for_selector("[data-testid=inspector-title]", timeout=8000)
    check("[P14→P16] 선택 → 인스펙터에 그 사업", _text(page, "[data-testid=inspector-title]") == "한양7차아파트 재건축",
          _text(page, "[data-testid=inspector-title]"))
    page.keyboard.press("Escape")
    check("[P14] Esc → 선택 해제", _wait_url(page, lambda u: _q(page, "sel") is None))

    _palette(page, "압구정동 528")
    page.wait_for_selector("[data-testid=palette-item-address]", timeout=8000)
    page.keyboard.press("Enter")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    flt = page.evaluate("() => window.__propediaMap.getFilter('propedia-parcel-search')")
    drawn = page.evaluate(JS_RENDERED, ["propedia-parcel-search"])
    check("[P14] '압구정동 528' → 필지 경계 강조", bool(flt) and flt[2] == "1168011000105280000" and drawn > 0,
          f"{flt}, {drawn}")
    pt = page.evaluate(JS_PARCEL_PT, "1168011000105280000")
    page.mouse.move(pt[0], pt[1])
    page.wait_for_timeout(300)
    tt = _text(page, "[data-testid=map-tooltip]")
    check("[P14] 528 툴팁: '압구정동 528 · 포함된 것으로 보임 · 사람 확인 전'",
          tt == "압구정동 528 · 포함된 것으로 보임 · 사람 확인 전", tt)
    page.mouse.click(pt[0], pt[1])
    page.wait_for_timeout(300)
    items = page.eval_on_selector_all("[data-testid=pick-item]", "es => es.map(e => e.dataset.id)")
    check("[P14] 겹친 지점 클릭 → 선택 목록 (사업 → 필지 순)",
          items[:1] == ["project:1"] and "parcel:1:1168011000105280000" in items, str(items))
    if items:
        page.click("[data-testid=pick-item][data-id='parcel:1:1168011000105280000']")
        ok = _wait_url(page, lambda u: _q(page, "sel") == "parcel:1:1168011000105280000")
        sf = page.evaluate("() => window.__propediaMap.getFilter('propedia-parcel-selected')")
        check("[P14] 선택 목록에서 필지 → sel·브랜드색 외곽선 강조", ok and sf[2] == "parcel:1:1168011000105280000", str(sf))

    # ---- 호버 툴팁 (사업): 문구는 /api/v1/map/projects의 hover_line 그대로
    _open(page, home)
    pt = page.evaluate(JS_PROJECT_PT, "project:2")
    page.mouse.move(pt[0], pt[1])
    page.wait_for_timeout(300)
    tt = _text(page, "[data-testid=map-tooltip]")
    hl = [p["hover_line"] for p in projects if p["id"] == 2][0]
    check("[P14] 사업 호버 툴팁 = API hover_line + 사람 확인 전", tt == f"{hl} · 사람 확인 전", tt)

    # ---- 사업 목록 카드 → 이동·선택
    page.click("[data-testid=left-tab-projects]")
    page.wait_for_selector("[data-testid=project-card-1]")
    c0 = page.evaluate(JS_CENTER)
    page.click("[data-testid=project-card-1]")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    c1 = page.evaluate(JS_CENTER)
    bb = [p["bbox"] for p in projects if p["id"] == 1][0]
    inside = bb[0] - 0.01 < c1[0] < bb[2] + 0.01 and bb[1] - 0.01 < c1[1] < bb[3] + 0.01
    ok = _wait_url(page, lambda u: _q(page, "sel") == "project:1" and _q(page, "tab") == "projects")
    check("[P14] 사업 카드 → 구역으로 이동·sel=project:1", inside and c1[2] > c0[2] and ok,
          f"{[round(x, 4) for x in c1]}, sel={_q(page, 'sel')}")
    page.click("[data-testid=work-tab-gangnam]")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    z_home = page.evaluate(JS_CENTER)[2]
    page.click("[data-testid=work-tab-project]")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    check("[P14] 작업 탭: '강남구 전체' → 첫 화면, '선택한 사업' → 그 구역",
          z_home < c1[2] and abs(page.evaluate(JS_CENTER)[2] - c1[2]) < 0.3)

    # ---- 데이터 상태 탭 (강남구 전체 화면으로 돌아가 선택 해제)
    page.click("[data-testid=work-tab-gangnam]")
    page.keyboard.press("Escape")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    page.click("[data-testid=left-tab-status]")
    page.wait_for_selector("[data-testid=status-table]")
    st = {r: page.get_attribute(f"[data-testid=status-row-{r}]", "data-status")
          for r in ("projects", "regulation-d5", "ref-seoulplan", "schools")}
    keys = _text(page, "[data-testid=status-keys]")
    # P18부터 준비 중(pending) 레이어가 없다 (생활 인프라 4종 ready)
    check("[P14] 데이터 상태: ready·not_adopted, 키는 있음/없음만",
          st == {"projects": "ready", "regulation-d5": "not_adopted", "ref-seoulplan": "ready", "schools": "ready"}
          and re.fullmatch(r"실시간 조회 키: 브이월드 (있음|없음) · 도로명주소 (있음|없음)", keys) is not None, f"{st} {keys}")
    if shot:
        page.screenshot(path=str(SHOT_STATUS))

    # ---- 키보드: L·T, 입력창 안에서는 꺼짐
    page.click("[data-testid=left-tab-layers]")
    page.mouse.click(1000, 780)
    page.keyboard.press("Escape")
    page.keyboard.press("l")
    gone = page.locator("[data-testid=left-panel]").count() == 0
    page.keyboard.press("l")
    page.keyboard.press("t")
    tl = page.get_attribute("[data-testid=timeline]", "data-open")
    page.keyboard.press("t")
    page.keyboard.press("Control+K")
    page.wait_for_selector("[data-testid=palette-input]")
    page.keyboard.type("lit")
    still = (page.locator("[data-testid=left-panel]").count() == 1
             and page.get_attribute("[data-testid=timeline]", "data-open") == "false")
    page.keyboard.press("Escape")
    check("[P14] 키보드 L·T, 입력창 안에서는 단축키 꺼짐", gone and tl == "true" and still
          and page.locator("[data-testid=palette]").count() == 0)


SHOT_REF = SCREENS / "map_03a_reference.png"
SHOT_WMS = SCREENS / "map_03b_wms_cadastral.png"
SHOT_CLICK = SCREENS / "map_03c_parcel_click.png"
JS_PT = """([lon, lat]) => { const m = window.__propediaMap; const p = m.project([lon, lat]);
  const r = m.getCanvas().getBoundingClientRect(); return [p.x + r.left, p.y + r.top] }"""
JS_JUMP = "([lon, lat, z]) => window.__propediaMap.jumpTo({center: [lon, lat], zoom: z})"


def _click_points() -> dict:
    """클릭 지점 (빌드 GeoJSON·live_parcels.yaml에서 계산, 지오코더 아님)."""
    import json as _json

    import yaml
    from shapely.geometry import shape
    from shapely.ops import unary_union
    lay = ROOT / "public" / "data" / "layers"

    def fc(n):
        return _json.loads((lay / f"{n}.geojson").read_text(encoding="utf-8"))["features"]
    parcels = unary_union([shape(f["geometry"]) for f in fc("propedia_parcels")])
    others = unary_union([shape(f["geometry"]) for f in fc("propedia_projects") + fc("propedia_regulations")])
    proj2 = next(shape(f["geometry"]) for f in fc("propedia_projects") if f["properties"]["id"] == "project:2")
    in_proj = proj2.difference(parcels.buffer(0.00005)).representative_point()
    eunma = next(shape(f["geometry"]) for f in fc("ref_seoulplan") if f["properties"]["DGM_NM"] == "은마아파트")
    in_ref = eunma.difference(others.union(parcels).buffer(0.00005)).representative_point()
    lp = yaml.safe_load((ROOT / "evals" / "goldset" / "live_parcels.yaml").read_text(encoding="utf-8"))["parcels"]
    by = {x["label"]: x for x in lp}
    yeok, nonh = by["강남구 역삼동 823"], by["강남구 논현동 100"]
    return {"project2": (in_proj.x, in_proj.y), "eunma": (in_ref.x, in_ref.y),
            "yeoksam": (yeok["lon"], yeok["lat"], yeok["pnu"]), "nonhyeon": (nonh["lon"], nonh["lat"], nonh["pnu"])}


def _wait_card(page, timeout=12000) -> str | None:
    try:
        page.wait_for_function("""() => { const c = document.querySelector('[data-testid=parcel-card]');
          return c && c.dataset.status !== 'loading' }""", timeout=timeout)
    except Exception:
        return None
    return page.get_attribute("[data-testid=parcel-card]", "data-status")


def p15_checks(page, url: str, check, shot: bool, tiles: dict, built: bool) -> None:
    pts = _click_points()
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    reqs: list[str] = []
    page.on("request", lambda r: reqs.append(r.url.rsplit("/", 1)[-1]) if "/data/layers/ref_" in r.url else None)

    # ---- 1. 참고 레이어 2종: 처음 켤 때만 불러옴, 지도에 그려짐, 출처 표시
    _open(page, home)
    attr0 = page.inner_text("[data-testid=attribution]")
    n0 = len(reqs)
    rows = {i: page.inner_text(f"[data-testid=layer-row-{i}]") for i in ("ref-seoulplan", "ref-uije")}
    check("[P15] 참고 행: 켜기 가능 + '참고·비상업' 배지, 켜기 전 요청 0",
          all("참고·비상업" in t for t in rows.values()) and n0 == 0
          and not page.locator("[data-testid=layer-toggle-ref-seoulplan]").is_disabled(),
          f"{ {k: v.replace(chr(10), ' ') for k, v in rows.items()} } 요청 {n0}")
    page.evaluate(JS_JUMP, [127.062, 37.497, 14.6])
    for lid in ("ref-seoulplan", "ref-uije"):
        page.click(f"[data-testid=layer-toggle-{lid}]")
        page.wait_for_function(f"() => !!window.__propediaMap.getLayer('{lid}-fill')", timeout=8000)
        page.evaluate(JS_IDLE)
    drawn = {lid: page.evaluate(JS_RENDERED, [f"{lid}-fill", f"{lid}-line"]) for lid in ("ref-seoulplan", "ref-uije")}
    for lid in ("ref-seoulplan", "ref-uije"):          # 끄고 다시 켜도 다시 받지 않음
        page.click(f"[data-testid=layer-toggle-{lid}]")
        page.click(f"[data-testid=layer-toggle-{lid}]")
    page.evaluate(JS_IDLE)
    got = sorted(reqs)
    check("[P15] 참고 2종: 처음 켤 때만 한 번씩 불러옴, 지도에 그려짐",
          got == ["ref_seoulplan.geojson", "ref_uije.geojson"] and all(v > 0 for v in drawn.values()), f"{got} {drawn}")
    dash = page.evaluate(JS_PAINT, ["ref-seoulplan-line", "line-dasharray"])
    fop = page.evaluate(JS_PAINT, ["ref-seoulplan-fill", "fill-opacity"])
    check("[P15] 참고 모양: 회색 점선 + 면 8%", bool(dash) and fop == 0.08, f"{dash} {fop}")
    attr1 = page.inner_text("[data-testid=attribution]")
    check("[P15] 출처 표시: 켜진 참고 레이어 출처를 이어 붙임",
          "도시계획사업 현황" not in attr0 and "도시계획사업 현황" in attr1 and "의제처리구역" in attr1, attr1)
    page.evaluate(JS_JUMP, [127.0625, 37.4985, 15.6])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(500)
    rl = page.eval_on_selector_all("[data-testid=ref-label]", "es => es.map(e => e.textContent)")
    check("[P15] 줌 15 이상 참고 라벨: DGM_NM + '참고'", bool(rl) and all(t.endswith("· 참고") for t in rl), str(rl[:4]))
    if shot:
        page.screenshot(path=str(SHOT_REF))

    # ---- 2. WMS 지적도 (API 프록시): 줌 17 미만 안내, 17 이상 타일 200 (연속지적도 WMS는 0.6m/px보다 거칠면 빈 그림)
    _open(page, home)
    page.click("[data-testid=layer-toggle-ref-cadastral]")
    page.evaluate(JS_IDLE)
    hint = _text(page, "[data-testid=layer-zoomhint-ref-cadastral]")
    before = len(tiles.get("wms:lp_pa_cbnd_bubun", []))
    check("[P15] 줌 17 미만: 지적도 행에 '줌 17 이상에서 표시', 타일 요청 없음",
          hint == "줌 17 이상에서 표시" and before == 0, f"'{hint}' 타일 {before}")
    yl, ya, ypnu = pts["yeoksam"]
    page.evaluate(JS_JUMP, [yl, ya, 17.2])
    page.evaluate(JS_IDLE)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)
    st = tiles.get("wms:lp_pa_cbnd_bubun", [])
    gone = page.locator("[data-testid=layer-zoomhint-ref-cadastral]").count() == 0
    if built:
        check("[P15] 줌 17 이상: 안내 사라짐 (빌드본은 타일 결과 기록만)", gone,
              f"200×{st.count(200)} 기타 {sorted(set(st) - {200})}")
    else:
        check("[P15] 줌 17 이상: 안내 사라짐, 지적도 WMS 타일 200 (API 프록시)", gone and st.count(200) > 0
              and all(x == 200 for x in st),
              f"200×{st.count(200)} 기타 {[x for x in st if x != 200][:5]}")
    if shot:
        page.screenshot(path=str(SHOT_WMS))

    # ---- 3. 빈 곳 클릭 → 필지 강조 + 인스펙터 카드 (역삼동 823 경계 중심점)
    _open(page, home)
    page.evaluate(JS_JUMP, [yl, ya, 17])
    page.evaluate(JS_IDLE)
    page.mouse.click(*page.evaluate(JS_PT, [yl, ya]))
    status = _wait_card(page)
    page.evaluate(JS_IDLE)
    pnu = _text(page, "[data-testid=parcel-pnu]")
    land = _text(page, "[data-testid=parcel-land]")
    hl = page.evaluate(JS_RENDERED, ["click-parcel-line"])
    ok_url = _wait_url(page, lambda u: _q(page, "sel") == f"parcel:{ypnu}")
    check("[P15] 빈 곳 클릭(역삼동 823) → 필지 강조 + 카드(PNU·토지 정보) + sel=parcel:{pnu}",
          status == "ok" and pnu == ypnu and "지목" in land and "개별공시지가" in land and hl > 0 and ok_url,
          f"{status} {pnu} 강조 {hl} sel={_q(page, 'sel')}")
    card = _text(page, "[data-testid=parcel-card]")
    counts = _text(page, "[data-testid=parcel-counts]")
    check("[P15] 카드: 층별 고시 수·주변 500m·참고 구역 섹션",
          "서울 전역" in counts and "필지" in counts and "주변 500m 사업" in card and "이 지점의 참고 구역" in card,
          counts.replace("\n", " "))
    if shot:
        page.screenshot(path=str(SHOT_CLICK))
    page.reload()
    _ready(page)
    st2 = _wait_card(page)
    page.evaluate(JS_IDLE)
    check("[P15] 새로고침 → 같은 필지 다시 조회·강조",
          st2 == "ok" and _text(page, "[data-testid=parcel-pnu]") == ypnu
          and page.evaluate(JS_RENDERED, ["click-parcel-line"]) > 0, f"{st2}")

    # 빠르게 두 번 → 마지막 것만 (이전 요청 취소)
    nl, na, npnu = pts["nonhyeon"]
    page.evaluate(JS_JUMP, [(yl + nl) / 2, (ya + na) / 2, 14.2])
    page.evaluate(JS_IDLE)
    page.mouse.click(*page.evaluate(JS_PT, [yl, ya]))
    page.mouse.click(*page.evaluate(JS_PT, [nl, na]))
    _wait_card(page)
    page.wait_for_timeout(1500)
    check("[P15] 빠르게 두 번 누르면 마지막 필지만 (이전 요청 취소)",
          _text(page, "[data-testid=parcel-pnu]") == npnu and _q(page, "sel") == f"parcel:{npnu}",
          f"{_text(page, '[data-testid=parcel-pnu]')} sel={_q(page, 'sel')}")

    # ---- 4. 우선순위: 대청마을 구역 안(사업 필지 아님) → 사업 구역 선택
    _open(page, home)
    plon, plat = pts["project2"]
    page.evaluate(JS_JUMP, [plon, plat, 16])
    page.evaluate(JS_IDLE)
    page.mouse.click(*page.evaluate(JS_PT, [plon, plat]))
    ok = _wait_url(page, lambda u: _q(page, "sel") == "project:2")
    check("[P15] 대청마을 구역 안 클릭 → 사업 구역 선택 (필지 조회 아님)",
          ok and page.locator("[data-testid=parcel-card]").count() == 0, f"sel={_q(page, 'sel')}")

    # ---- 5. 서울플랜+ 구역(은마아파트) 안 일반 필지 → 필지 조회 + 참고 구역 이름
    page.keyboard.press("Escape")
    elon, elat = pts["eunma"]
    page.evaluate(JS_JUMP, [elon, elat, 16.5])
    page.evaluate(JS_IDLE)
    page.mouse.click(*page.evaluate(JS_PT, [elon, elat]))
    st3 = _wait_card(page)
    zones = page.eval_on_selector_all("[data-testid=parcel-ref-zone]", "es => es.map(e => e.textContent)")
    check("[P15] 서울플랜+ 구역 안 필지 → 필지 조회 + '이 지점의 참고 구역'에 이름(참고 배지·출처)",
          st3 == "ok" and any("은마아파트" in z and "참고" in z and "공공누리" in z for z in zones), f"{st3} {zones[:3]}")


# ==== P16 우측 인스펙터 ====
SHOT_P16 = {k: SCREENS / f"map_04{k}.png" for k in
            ("a_project_hanyang", "b_project_daecheong", "c_evidence_modal", "d_regulation_d10", "e_parcel_528")}
PNU_528 = "1168011000105280000"
JS_CONTRAST = """(sels) => { const lum = (c) => { const m = c.match(/[\\d.]+/g).map(Number);
    const f = v => (v /= 255) <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]) };
  const out = {};
  for (const s of sels) { const e = document.querySelector(s); if (!e) { out[s] = null; continue }
    const L = lum(getComputedStyle(e).color); out[s] = Math.round((1.05 / (L + 0.05)) * 100) / 100 }
  return out }"""


def _p16_points() -> dict:
    """사업 구역·규제 구역 안에서 다른 Propedia 도형과 겹치지 않는 점 (선택 목록 없이 바로 선택되게)."""
    import json as _json

    from shapely.geometry import shape
    from shapely.ops import unary_union
    lay = ROOT / "public" / "data" / "layers"

    def fc(n):
        return _json.loads((lay / f"{n}.geojson").read_text(encoding="utf-8"))["features"]
    parcels = unary_union([shape(f["geometry"]) for f in fc("propedia_parcels")])
    projs = {f["properties"]["id"]: shape(f["geometry"]) for f in fc("propedia_projects")}
    regs = {f["properties"]["id"]: shape(f["geometry"]) for f in fc("propedia_regulations")}
    others = unary_union(list(projs.values()) + [parcels])
    p1 = projs["project:1"].difference(parcels.buffer(0.00003)).representative_point()
    d10 = regs["regulation:D10"].difference(others.buffer(0.00003)).representative_point()
    c528 = next(f["properties"] for f in fc("propedia_parcels") if f["properties"]["pnu"] == PNU_528)
    return {"project1": (p1.x, p1.y), "d10": (d10.x, d10.y), "p528": (c528["centroid_lon"], c528["centroid_lat"])}


def _inspector_ready(page, timeout=12000) -> bool:
    try:
        page.wait_for_selector("[data-testid=inspector-title]", timeout=timeout)
        page.wait_for_function("() => !document.querySelector('[data-testid=inspector-loading]')", timeout=timeout)
        return True
    except Exception:
        return False


def _click_map(page, lon: float, lat: float, z: float, want: str) -> str | None:
    """지도 점을 누르고, 겹친 도형 선택 목록이 뜨면 want를 고른다 → URL sel"""
    page.evaluate(JS_JUMP, [lon, lat, z])
    page.evaluate(JS_IDLE)
    page.mouse.click(*page.evaluate(JS_PT, [lon, lat]))
    page.wait_for_timeout(300)
    if page.locator("[data-testid=pick-list]").count():
        page.click(f"[data-testid=pick-item][data-id='{want}']")
    _wait_url(page, lambda u: _q(page, "sel") == want, 4000)
    return _q(page, "sel")


def p16_checks(page, url: str, check, shot: bool) -> None:
    pts = _click_points() | _p16_points()
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    with_q = home + ("&" if "?" in home else "?")

    # ---- 1. 한양7차 구역 클릭 → 13단계 중 2번째, 마감(2026.11.06), 콜아웃
    _open(page, home)
    sel = _click_map(page, *pts["project1"], 16.2, "project:1")
    ok = _inspector_ready(page)
    line = _text(page, "[data-testid=stepper-line]")
    dday = _text(page, "[data-testid=deadline-dday]")
    check("[P16] 한양7차 구역 클릭 → 인스펙터 '재건축 13단계 중 2번째 · 앞으로 11단계 · 다음: 정비구역 지정 고시'",
          ok and sel == "project:1" and "재건축 13단계 중 2번째 · 앞으로 11단계 · 다음: 정비구역 지정 고시" in line,
          f"sel={sel} '{line}'")
    check("[P16] 한양7차 기한 '마감(2026.11.06)'·남은 기간 '비교할 사례가 부족합니다'",
          "마감(2026.11.06)" in dday and _text(page, "[data-testid=project-remaining]") == "비교할 사례가 부족합니다", dday)
    cells = page.eval_on_selector_all("[data-testid=stepper-cell]", "es => es.map(e => e.dataset.state)")
    check("[P16] 스테퍼 13칸: 지난 1 · 현재 1 · 남은 11", len(cells) == 13 and cells.count("done") == 1
          and cells.index("current") == 1 and cells.count("upcoming") == 11, str(cells))
    page.focus("[data-testid=stepper-cell] >> nth=1")
    page.wait_for_timeout(200)
    tip = _text(page, "[data-testid=stepper-tooltip]")
    check("[P16] 단계 툴팁: 단계 설명 안내 + '법령 대조 전 초안'", "법령 대조 전 초안" in tip and "정비계획" in tip,
          tip.replace("\n", " "))
    facts = _text(page, "[data-testid=project-facts]")
    check("[P16] 고시 수치 표: 항목·값·출처 줄", "D1 ·" in facts and "쪽" in facts and len(facts.splitlines()) >= 3, facts[:120])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(300)
    co = page.locator("[data-testid=callout]")
    side = co.get_attribute("data-side") if co.count() else None
    cot = _text(page, "[data-testid=callout]")
    check("[P16] 지도 콜아웃: 이름·단계·기한", side in ("left", "right") and "13단계 중 2번째" in cot
          and "마감(2026.11.06)" in cot, f"side={side} '{cot}'")
    bx = co.bounding_box() if co.count() else None
    rp = page.locator("[data-testid=right-panel]").bounding_box()
    check("[P16] 콜아웃이 우측 인스펙터와 겹치지 않음", bool(bx and rp) and bx["x"] + bx["width"] <= rp["x"], f"{bx} {rp}")
    tl = page.get_attribute("[data-testid=inspector-tabs]", "role")
    tabs = page.eval_on_selector_all("[data-testid=inspector-tabs] [role=tab]",
                                     "es => es.map(e => [e.textContent, e.getAttribute('aria-selected')])")
    check("[P16] 탭 role=tablist: 개요·근거·필지·영향권 안 단지·이력", tl == "tablist"
          and [t for t, _ in tabs] == ["개요", "근거", "필지", "영향권 안 단지", "이력"]
          and tabs[0][1] == "true", str(tabs))
    page.focus("[data-testid=inspector-tab-overview]")
    page.keyboard.press("ArrowRight")
    k1 = page.get_attribute("[data-testid=inspector-tab-evidence]", "aria-selected")
    page.keyboard.press("End")
    k2 = page.get_attribute("[data-testid=inspector-tab-history]", "aria-selected")
    hist = _text(page, "[data-testid=history-list]")
    check("[P16] 탭 키보드(→·End) + 이력 탭 시간순·출처 줄",
          k1 == "true" and k2 == "true" and "2026.10.06" in hist and "D1 ·" in hist, f"{k1} {k2} {hist[:80]!r}")
    page.keyboard.press("Home")
    ratio = page.evaluate(JS_CONTRAST, ["[data-testid=stepper-line]", "[data-testid=inspector-as-of]",
                                        "[data-testid=evidence-line]", "[data-testid=inspector-title]"])
    check("[P16] 글자 대비 4.5:1 이상 (흰 바탕 기준)", all(v is not None and v >= 4.5 for v in ratio.values()), str(ratio))
    if shot:
        page.screenshot(path=str(SHOT_P16["a_project_hanyang"]))

    # ---- 2. 출처 줄 → 원문 모달 (이미지·근거·문서 DB 링크·이전/다음·포커스 가두기·Esc·포커스 복귀)
    page.locator("[data-testid=project-deadline] [data-testid=evidence-line]").first.click()
    page.wait_for_selector("[data-testid=evidence-modal]", timeout=5000)
    page.wait_for_function("() => document.querySelector('[data-testid=evidence-image]')?.dataset.state === 'ok'",
                           timeout=8000)
    nat = page.evaluate("() => document.querySelector('[data-testid=evidence-image]').naturalWidth")
    am = page.get_attribute("[data-testid=evidence-modal]", "aria-modal")
    dl = page.get_attribute("[data-testid=evidence-docs-link]", "href") or ""
    src = page.get_attribute("[data-testid=evidence-image]", "src") or ""
    check("[P16] 출처 줄 클릭 → 원문 모달(aria-modal)에 쪽 이미지·근거·'문서 DB에서 보기'",
          am == "true" and nat > 0 and src.startswith("/pages/D1/") and dl.startswith("/docs.html?doc=D1&page="),
          f"{am} {src} {dl}")
    if shot:
        page.screenshot(path=str(SHOT_P16["c_evidence_modal"]))
    inside = True
    for _ in range(12):
        page.keyboard.press("Tab")
        inside = inside and page.evaluate("() => !!document.activeElement.closest('[data-testid=evidence-modal]')")
    page.keyboard.press("+")
    z = _text(page, "[data-testid=evidence-zoom]")
    pos0 = _text(page, "[data-testid=evidence-position]")
    page.click("[data-testid=evidence-next]")
    pos1 = _text(page, "[data-testid=evidence-position]")
    check("[P16] 모달: Tab 포커스가 모달 안에 갇힘, + 확대, 다음 근거로 이동",
          inside and z != "100%" and pos0 != pos1, f"{inside} {z} {pos0}→{pos1}")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    gone = page.locator("[data-testid=evidence-modal]").count() == 0
    back = page.evaluate("() => document.activeElement?.dataset?.testid")
    check("[P16] Esc → 모달 닫힘, 선택 유지(sel=project:1), 포커스는 연 출처 줄로",
          gone and _q(page, "sel") == "project:1" and back == "evidence-line", f"{gone} sel={_q(page, 'sel')} focus={back}")

    # ---- 3. 필지 탭 528 행 → 지도 강조·이동
    page.click("[data-testid=inspector-tab-parcels]")
    row = page.locator(f"[data-testid=project-parcel-row][data-pnu='{PNU_528}']")
    rtxt = row.inner_text() if row.count() else ""
    page.evaluate(JS_JUMP, [127.06, 37.49, 13])
    page.evaluate(JS_IDLE)
    row.click()
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    flt = page.evaluate("() => window.__propediaMap.getFilter('propedia-parcel-search')")
    c = page.evaluate(JS_CENTER)
    plon, plat = pts["p528"]
    near = abs(c[0] - plon) < 0.002 and abs(c[1] - plat) < 0.002 and c[2] >= 16
    drawn = page.evaluate(JS_RENDERED, ["propedia-parcel-search"])
    check("[P16] 필지 탭 528 행('포함된 것으로 보임 · 사람 확인 전 (검수 17)') → 지도 강조·이동",
          "포함된 것으로 보임" in rtxt and "검수 17" in rtxt and PNU_528 in str(flt) and near and drawn > 0,
          f"{rtxt!r} flt={flt} center={c} drawn={drawn}")

    # ---- 4. 대청마을 구역 → 8단계 중 1번째
    page.keyboard.press("Escape")
    sel = _click_map(page, *pts["project2"], 16, "project:2")
    _inspector_ready(page)
    line2 = _text(page, "[data-testid=stepper-line]")
    sub = _text(page, "[data-testid=project-sub-status]")
    check("[P16] 대청마을 구역 클릭 → '모아타운 8단계 중 1번째'·세부 상태(마감)·단계 메모",
          sel == "project:2" and "모아타운 8단계 중 1번째" in line2 and "앞으로 7단계" in line2 and "마감" in sub
          and bool(_text(page, "[data-testid=project-stage-note]")), f"'{line2}' '{sub}'")
    bev = page.locator("[data-testid=boundary-evidence]")
    btxt = bev.inner_text() if bev.count() else ""
    check("[P16] 대청마을 구역 경계 근거 = D9 12쪽 (결정도)", "D9 · 12쪽" in btxt, btxt)
    if shot:
        page.screenshot(path=str(SHOT_P16["b_project_daecheong"]))

    # ---- 5. D10 규제 클릭 → 효력 기간 막대·오늘 표시
    _open(page, with_q + "layers=projects,impact250,impact500,parcels,regulations")
    sel = _click_map(page, *pts["d10"], 16, "regulation:D10")
    _inspector_ready(page)
    st = _text(page, "[data-testid=period-status]")
    lbl = _text(page, "[data-testid=period-label]")
    check("[P16] D10 규제 클릭 → 효력 기간 막대 + 오늘 표시 + '효력 기간 중'",
          sel == "regulation:D10" and page.locator("[data-testid=period-bar]").count() == 1
          and page.locator("[data-testid=period-today]").count() == 1 and st == "효력 기간 중"
          and lbl == "효력 기간 2026.04.01 ~ 2028.04.01", f"sel={sel} '{st}' '{lbl}'")
    if shot:
        page.screenshot(path=str(SHOT_P16["d_regulation_d10"]))
    page.evaluate(JS_JUMP, [127.06, 37.49, 13])
    page.evaluate(JS_IDLE)
    page.click("[data-testid=regulation-show-on-map]")
    page.wait_for_timeout(900)
    page.evaluate(JS_IDLE)
    c = page.evaluate(JS_CENTER)
    check("[P16] '지도에서 보기' → 규제 구역으로 이동", c[2] >= 15 and abs(c[0] - pts["d10"][0]) < 0.004, str(c))

    # ---- 6. 사업 필지 528 (URL) → 필지 보기 맨 위 사업 줄
    _open(page, with_q + f"sel=parcel:1:{PNU_528}")
    _inspector_ready(page)
    ban = _text(page, "[data-testid=parcel-banner-text]")
    check("[P16] sel=parcel:1:528 → '한양7차아파트 재건축 사업 구역 필지 · 포함된 것으로 보임 · 사람 확인 전 (검수 17)'",
          ban == "한양7차아파트 재건축 사업 구역 필지 · 포함된 것으로 보임 · 사람 확인 전 (검수 17)", ban)
    if shot:
        page.evaluate(JS_JUMP, [*pts["p528"], 17.3])
        page.evaluate(JS_IDLE)
        page.wait_for_timeout(400)
        page.screenshot(path=str(SHOT_P16["e_parcel_528"]))

    # ---- 7. 빈 곳 클릭(역삼동 823) → 필지 보기 정식 카드
    _open(page, home)
    yl, ya, ypnu = pts["yeoksam"]
    page.evaluate(JS_JUMP, [yl, ya, 17])
    page.evaluate(JS_IDLE)
    page.mouse.click(*page.evaluate(JS_PT, [yl, ya]))
    stc = _wait_card(page)
    srcl = _text(page, "[data-testid=parcel-land-source]")
    if page.locator("[data-testid=parcel-layer-city]").count():
        page.click("[data-testid=parcel-layer-city]")
    items = _text(page, "[data-testid=parcel-layer-items]")
    check("[P16] 빈 곳 클릭 → 정식 필지 카드: 토지 정보(출처 '브이월드 · 기준일')·층별 고시 펼치기(출처 줄)",
          stc == "ok" and _text(page, "[data-testid=inspector-title]").endswith("역삼동 823") and "브이월드" in srcl
          and "쪽" in items, f"{stc} '{srcl}' {items[:60]!r}")
    tabs = page.eval_on_selector_all("[data-testid=inspector-tabs] [role=tab]", "es => es.map(e => e.textContent)")
    check("[P16] 필지 보기 탭: 개요·근거", tabs == ["개요", "근거"], str(tabs))

    # ---- 8. URL 공유: sel=project:1로 새로 열면 같은 내용
    _open(page, with_q + "sel=project:1")
    _inspector_ready(page)
    check("[P16] URL sel=project:1로 새로 열기 → 같은 인스펙터",
          _text(page, "[data-testid=inspector-title]") == "한양7차아파트 재건축"
          and _text(page, "[data-testid=stepper-line]") == line, _text(page, "[data-testid=inspector-title]"))

    # ---- 9. 상단 고시 칩 → 인스펙터, 사업 목록 상태 배지, 데이터 상태 라이선스
    _open(page, home)
    page.click("[data-testid=notice-chip] >> nth=0")
    page.click("[data-testid=notice-open-inspector]")
    ok_n = _wait_url(page, lambda u: (_q(page, "sel") or "").startswith("regulation:D"))
    _inspector_ready(page)
    check("[P16] 상단 고시 칩 → '인스펙터에서 보기' → 규제 보기",
          ok_n and _text(page, "[data-testid=inspector-kind]") == "규제", f"sel={_q(page, 'sel')}")
    page.click("[data-testid=left-tab-projects]")
    page.wait_for_selector("[data-testid=project-card-2]")
    b1 = page.locator("[data-testid=project-card-1] [data-testid=project-status-badge]").all_inner_texts()
    b2 = page.locator("[data-testid=project-card-2] [data-testid=project-status-badge]").all_inner_texts()
    check("[P16] 사업 목록 상태 배지: 한양7차 '공람 마감' / 대청마을 '공람 마감'·'승인 고시 미확인'",
          b1 == ["공람 마감"] and b2 == ["공람 마감", "승인 고시 미확인"], f"{b1} {b2}")
    page.click("[data-testid=left-tab-status]")
    page.wait_for_selector("[data-testid=status-table]")
    lic = [page.inner_text(f"[data-testid=status-row-{i}]") for i in ("ref-seoulplan", "ref-uije")]
    check("[P16 0-3] 데이터 상태 탭: 서울플랜+·의제처리구역 모두 '공공누리 4유형'", all("4유형" in t for t in lic),
          " | ".join(t.replace("\n", " ")[:60] for t in lic))



# ---- P17 0단계: 카메라(c·z) 없이 sel만 있는 URL → 그 대상이 패널을 뺀 영역 가운데
JS_SEL_CENTER = """async ([file, fid]) => { const m = window.__propediaMap;
  const fc = await (await fetch(file)).json(); const f = fc.features.find(x => x.properties.id === fid);
  if (!f) return null; let w = 1e9, s = 1e9, e = -1e9, n = -1e9;
  const walk = c => typeof c[0] === 'number' ? (w = Math.min(w, c[0]), e = Math.max(e, c[0]), s = Math.min(s, c[1]),
    n = Math.max(n, c[1])) : c.forEach(walk);
  walk(f.geometry.coordinates); const p = m.project([(w + e) / 2, (s + n) / 2]);
  const r = m.getCanvas().getBoundingClientRect(); return [p.x + r.left, p.y + r.top] }"""
JS_FREE_AREA = """() => { const box = s => { const el = document.querySelector(s); return el ? el.getBoundingClientRect() : null };
  const L = box('[data-testid=left-panel]'), R = box('[data-testid=right-panel]'), T = box('[data-testid=topbar]');
  return [L ? L.right : 0, T ? T.bottom : 0, R ? R.left : innerWidth, innerHeight - 60] }"""
SEL_FIT_CASES = [("parcel:1:1168011000105280000", "/data/layers/propedia_parcels.geojson"),
                 ("project:1", "/data/layers/propedia_projects.geojson"),
                 ("regulation:D10", "/data/layers/propedia_regulations.geojson")]


def p17_fit_checks(page, url: str, check) -> None:
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    for fid, file in SEL_FIT_CASES:
        _open(page, home, f"sel={fid}")
        page.evaluate(JS_IDLE)
        pt = page.evaluate(JS_SEL_CENTER, [file, fid])
        x0, y0, x1, y1 = page.evaluate(JS_FREE_AREA)
        ok = bool(pt) and x0 < pt[0] < x1 and y0 < pt[1] < y1
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        near = bool(pt) and abs(pt[0] - cx) <= 0.15 * (x1 - x0) and abs(pt[1] - cy) <= 0.15 * (y1 - y0)
        z = page.evaluate(JS_CENTER)[2]
        check(f"[P17-0] 카메라 없이 sel={fid} → 패널 제외 영역 가운데 (줌 {z:.1f})", ok and near and z >= 14,
              f"점 {[round(v) for v in pt] if pt else None} 영역 {[round(v) for v in (x0, y0, x1, y1)]}")

# ---- P17 아파트 단지·실거래 (docs/map/PLAN.md P17 7·8단계)
SHOT_P17 = {k: SCREENS / f"map_05{k}.png" for k in ("a_apartments", "b_apartment_inspector", "c_project_nearby")}
EUNMA = "apt:11680-218"
JS_APT_OVERLAP = """() => { const m = window.__propediaMap;
  const ev = (e, v) => Array.isArray(e) && e[0] === 'case' ? (v === null || v === undefined ? e[2] : e[3]) : e;
  const e = m.getPaintProperty('apartments-fill', 'fill-opacity'); const seen = new Set(); const out = {inside: [], outside: []};
  for (const f of m.querySourceFeatures('apartments')) { if (seen.has(f.properties.id)) continue; seen.add(f.properties.id);
    const v = ev(e, f.properties.impact_buffer_m); (f.properties.impact_buffer_m == null ? out.outside : out.inside).push(v) }
  return out }"""


def _apt_points() -> dict:
    """은마 대표점(빌드 GeoJSON lon·lat = 필지 경계 대표점) + 최근 거래 20건 안에 해제가 있는 단지 (market.db 읽기 전용)"""
    import json as _json
    import sqlite3
    fc = _json.loads((ROOT / "public" / "data" / "layers" / "apartments.geojson").read_text(encoding="utf-8"))["features"]
    by = {f["properties"]["id"]: f["properties"] for f in fc}
    con = sqlite3.connect((ROOT / "db" / "market.db").as_uri() + "?mode=ro", uri=True)
    cancel = None
    for cid, band in con.execute("""SELECT complex_id, area_band FROM apt_trades WHERE is_cancelled=1 AND complex_id IS NOT NULL
                                     GROUP BY complex_id, area_band ORDER BY MAX(contract_date) DESC"""):
        n_bands = con.execute("SELECT COUNT(DISTINCT area_band) FROM apt_trades WHERE complex_id=?", (cid,)).fetchone()[0]
        rows = con.execute("""SELECT is_cancelled FROM apt_trades WHERE complex_id=? AND area_band=?
                              ORDER BY contract_date DESC, id DESC LIMIT 20""", (cid, band)).fetchall()
        if cid in by and n_bands >= 2 and any(r[0] for r in rows):
            cancel = (cid, band)
            break
    con.close()
    e = by[EUNMA]
    return {"eunma": (e["lon"], e["lat"]), "cancel": cancel}


def p17_checks(page, url: str, check, shot: bool) -> None:
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    with_q = home + ("&" if "?" in home else "?")
    pts = _apt_points()
    # 1. 레이어: 켤 때만 불러오기 → 면 28% + 외곽선, 범례 '실거래 신고 단지 기준'
    reqs: list[str] = []
    page.on("request", lambda r: "apartments.geojson" in r.url and reqs.append(r.url))
    _open(page, home)
    before = len(reqs)
    page.click("[data-testid=layer-toggle-apartments]")
    page.wait_for_function("() => !!window.__propediaMap.getLayer('apartments-fill')", timeout=10000)
    page.evaluate(JS_JUMP, [127.0605, 37.4985, 14.6])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(400)
    n = page.evaluate(JS_RENDERED, ["apartments-fill"])
    fill = page.evaluate(JS_PAINT, ["apartments-fill", "fill-opacity"])
    note = _text(page, "[data-testid=apartment-legend-note]")
    check("[P17] 아파트 단지 레이어: 켤 때 1번 불러옴·그려짐·면 28%·범례 '실거래 신고 단지 기준'",
          before == 0 and len(reqs) == 1 and n > 0 and fill == 0.28 and "실거래 신고 단지 기준" in note,
          f"요청 {before}→{len(reqs)} 도형 {n} 면 {fill} '{note[:40]}'")
    page.evaluate(JS_JUMP, [pts["eunma"][0], pts["eunma"][1], 15.6])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(500)
    labels = page.locator("[data-testid=apartment-label]").all_inner_texts()
    check("[P17] 단지 라벨 줌 15 이상 (은마 포함)", "은마" in labels, f"{len(labels)}개")
    if shot:
        page.screenshot(path=str(SHOT_P17["a_apartments"]))

    # 2. 은마 클릭 → 인스펙터: 기본 정보 없음 문구·준공연도·차트 두 개·최근 거래 표
    sel = _click_map(page, *pts["eunma"], 16.2, EUNMA)
    ok = _inspector_ready(page)
    page.wait_for_selector("[data-testid=price-chart]", timeout=12000)
    page.wait_for_timeout(300)
    title = _text(page, "[data-testid=inspector-title]")
    basis = _text(page, "[data-testid=apt-basis-missing]")
    year = _text(page, "[data-testid=apt-build-year]")
    check("[P17] 은마 클릭 → 인스펙터 '은마' · '기본 정보 확인 전' · 준공연도(실거래 신고 기준)",
          ok and sel == EUNMA and title == "은마" and basis == "기본 정보 확인 전" and "1979년 (실거래 신고 기준)" in year,
          f"sel={sel} '{title}' '{basis}' '{year}'")
    pc = page.locator("[data-testid=price-chart]").bounding_box()
    cc = page.locator("[data-testid=count-chart]").bounding_box()
    line_n = page.locator("[data-testid=median-line]").count()
    pts_n = page.locator("[data-testid=trade-point]").count()
    bars_n = page.locator("[data-testid=count-bar]").count()
    check("[P17] 차트 두 개 위아래 분리 (가격 선·점 / 건수 막대, 같은 너비)",
          bool(pc and cc) and pc["y"] + pc["height"] <= cc["y"] + 1 and abs(pc["width"] - cc["width"]) < 1
          and line_n == 1 and pts_n > 0 and bars_n > 0, f"{pc} {cc} 선 {line_n} 점 {pts_n} 막대 {bars_n}")
    rows = page.locator("[data-testid=apt-recent-row]").count()
    src = _text(page, "[data-testid=apt-sources]")
    check("[P17] 최근 거래 20건 표 + 출처 '실거래가(국토교통부 신고 자료, 계약일 기준) · 수집일'",
          rows == 20 and "실거래가(국토교통부 신고 자료, 계약일 기준)" in src and "수집일" in src, f"{rows}행 '{src}'")
    pressed = page.eval_on_selector_all("[data-testid^=apt-band-]",
                                        "es => es.map(e => [e.dataset.testid, e.getAttribute('aria-pressed')])")
    check("[P17] 면적대 칩: 기본 = 최근 3년 최다 (은마 60~85)", ["apt-band-60~85", "true"] in pressed, str(pressed))
    if shot:
        page.screenshot(path=str(SHOT_P17["b_apartment_inspector"]))

    # 3. 해제 표시 + 면적대 칩 전환 (최근 20건 안에 해제 거래가 있고 면적대가 둘 이상인 단지)
    cid, band = pts["cancel"] or (None, None)
    check("[P17] 해제 거래가 있는 단지를 market.db에서 찾음", cid is not None, str(pts["cancel"]))
    if cid:
        _open(page, with_q + f"layers=projects,impact250,impact500,parcels,apartments&sel=apt:{cid.split(':', 1)[1]}")
        _inspector_ready(page)
        page.wait_for_selector("[data-testid=apt-recent-table]", timeout=12000)
        chip = f"[data-testid='apt-band-{band}']"
        if page.get_attribute(chip, "aria-pressed") != "true":
            page.click(chip)
            page.wait_for_timeout(500)
            page.wait_for_selector("[data-testid=apt-recent-table]", timeout=12000)
        page.wait_for_timeout(300)
        canc = page.locator("[data-testid=apt-cancelled]").all_inner_texts()
        hollow = page.locator("[data-testid=trade-point][data-cancelled='1']").count()
        check(f"[P17] 해제 표시: 표 '해제 (날짜)' + 차트 빈 원 ({cid} {band})",
              bool(canc) and all(t.startswith("해제") for t in canc) and hollow > 0, f"{canc[:2]} 빈 원 {hollow}")
        chips = page.eval_on_selector_all("[data-testid^=apt-band-]", "es => es.map(e => e.dataset.testid)")
        other = next((c for c in chips if c != f"apt-band-{band}"), None)
        first_before = page.locator("[data-testid=apt-recent-row]").first.inner_text()
        page.click(f"[data-testid='{other}']")
        page.wait_for_timeout(500)
        page.wait_for_selector("[data-testid=apt-recent-table]", timeout=12000)
        page.wait_for_timeout(300)
        now = page.get_attribute(f"[data-testid='{other}']", "aria-pressed")
        first_after = page.locator("[data-testid=apt-recent-row]").first.inner_text()
        check("[P17] 면적대 칩 전환 → 차트·표가 그 면적대로", now == "true" and first_after != first_before,
              f"{other} {now} '{first_before[:30]}' → '{first_after[:30]}'")

    # 4. 겹침 보기: 영향권 밖 단지 25%
    _open(page, with_q + "layers=projects,impact250,impact500,parcels,apartments&ov=1")
    page.wait_for_function("() => !!window.__propediaMap.getLayer('apartments-fill')", timeout=10000)
    page.evaluate(JS_IDLE)
    ov = page.evaluate(JS_APT_OVERLAP)
    ins, outs = ov["inside"], ov["outside"]
    check("[P17] 겹침 보기: 영향권 밖 단지 28%→7% (25%), 안은 28%",
          bool(ins) and bool(outs) and all(v == 0.28 for v in ins) and all(v == 0.07 for v in outs),
          f"안 {len(ins)} {set(ins)} 밖 {len(outs)} {set(outs)}")

    # 5. Ctrl+K '은마' → 단지 그룹 → 선택
    _open(page, home)
    _palette(page, "은마")
    groups = page.locator("[data-testid=palette-group]").all_inner_texts()
    items = page.locator("[data-testid=palette-item-apartment]").all_inner_texts()
    ok = "단지" in groups and any(t.startswith("은마") for t in items)
    if ok:
        page.locator("[data-testid=palette-item-apartment]").first.dispatch_event("mousedown")
        _wait_url(page, lambda u: _q(page, "sel") == EUNMA, 5000)
    check("[P17] Ctrl+K '은마' → '단지' 그룹 → 은마 선택·레이어 켜짐",
          ok and _q(page, "sel") == EUNMA and "apartments" in (_q(page, "layers") or ""),
          f"{groups} {items[:2]} sel={_q(page, 'sel')} layers={_q(page, 'layers')}")

    # 6. 한양7차 '영향권 안 단지' 탭
    _open(page, with_q + "sel=project:1")
    _inspector_ready(page)
    page.click("[data-testid=inspector-tab-nearby]")
    page.wait_for_selector("[data-testid=project-nearby]")
    t250 = _text(page, "[data-testid=project-nearby-250]")
    t500 = _text(page, "[data-testid=project-nearby-500]")
    rows = page.locator("[data-testid=project-nearby-row]").count()
    check("[P17] 한양7차 '영향권 안 단지' 탭: 250m·500m 구분, 이름·준공연도·최근 거래일",
          "영향권 250m 안 단지" in t250 and "영향권 500m 안 단지" in t500 and rows > 0 and "준공연도" in t250
          and "한양7" in t250, f"{rows}행")
    if shot:
        page.screenshot(path=str(SHOT_P17["c_project_nearby"]))
    page.locator("[data-testid=project-nearby-row] button").first.click()
    _wait_url(page, lambda u: (_q(page, "sel") or "").startswith("apt:"), 4000)
    check("[P17] 영향권 안 단지 행 → 그 단지 선택", (_q(page, "sel") or "").startswith("apt:"), str(_q(page, "sel")))

    # 7. 데이터 상태 탭: 실거래·단지·M22·M23·기본 정보 연결 / 236
    _open(page, home)
    page.click("[data-testid=left-tab-status]")
    page.wait_for_selector("[data-testid=status-market]")
    mk = _text(page, "[data-testid=status-market]")
    check("[P17] 데이터 상태: 실거래 기간·건수·수집일·M23 / 단지 수·M22·기본 정보 연결 n / 236",
          all(k in mk for k in ("M22", "M23", "수집일", "해제", "기본 정보 연결 0 / 236")), mk.replace("\n", " / ")[:200])


SHOT_P18 = {k: SCREENS / f"map_06{k}.png" for k in ("a_poi", "b_radius", "c_station", "d_bus_stops", "e_bus_route")}
LAYER_FILES = ROOT / "public" / "data" / "layers"
JS_ICON_PT = """([src, id]) => { const m = window.__propediaMap;
  const f = m.querySourceFeatures(src).find(x => x.properties.id === id); if (!f) return null;
  const p = m.project(f.geometry.coordinates); const r = m.getCanvas().getBoundingClientRect();
  return [p.x + r.left, p.y + r.top] }"""
JS_FRAMES = """(ms) => new Promise(res => { const m = window.__propediaMap; const ts = []; let last = performance.now();
  const steps = [[127.0276, 37.4979, 15], [127.0490, 37.5045, 16], [127.0631, 37.5088, 15.5], [127.0400, 37.5150, 14.5],
                 [127.0276, 37.4979, 16.5], [127.0550, 37.4950, 15]];
  let i = 0; const go = () => { const [x, y, z] = steps[i++ % steps.length]; m.easeTo({center: [x, y], zoom: z, duration: 900}) };
  go(); const iv = setInterval(go, 950);
  const tick = (t) => { ts.push(t - last); last = t; if (performance.now() - start < ms) requestAnimationFrame(tick);
    else { clearInterval(iv); ts.sort((a, b) => a - b); const avg = ts.reduce((a, b) => a + b, 0) / ts.length;
      res({frames: ts.length, avg, p95: ts[Math.floor(ts.length * 0.95)], max: ts[ts.length - 1], over33: ts.filter(x => x > 33.4).length}) } };
  const start = performance.now(); requestAnimationFrame(tick) })"""


def _infra_props() -> dict:
    import json
    out = {}
    for name in ("stations", "bus_stops", "schools"):
        for f in json.loads((LAYER_FILES / f"{name}.geojson").read_text(encoding="utf-8"))["features"]:
            out[f["id"]] = f["properties"]
    return out


def _infra_wait(page, layer: str, timeout=10000) -> None:
    page.wait_for_function(f"() => !!window.__propediaMap.getLayer('{layer}')", timeout=timeout)


def p18_checks(page, url: str, check, shot: bool) -> None:
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    with_q = home + ("&" if "?" in home else "?")
    P = _infra_props()
    station = next(k for k, v in P.items() if v.get("kind") == "station" and v["name"] == "삼성")
    stop = "bus:22339"          # 강남역8번출구 (노선 있음)
    no_route = "bus:23811"      # 역삼역 (노선 연결 없음, D3)

    # 1. 기본: 학교·역 켜짐, 정류장·편의시설 꺼짐 (URL 기본값과 같음)
    _open(page, home)
    on = {i: page.locator(f"[data-testid=layer-toggle-{i}]").is_checked() for i in ("schools", "stations", "bus_stops", "pois")}
    _infra_wait(page, "stations-icon")
    check("[P18] 기본: 학교·지하철역 켜짐, 버스정류장·편의시설 꺼짐 (URL layers 없음)",
          on == {"schools": True, "stations": True, "bus_stops": False, "pois": False} and _q(page, "layers") is None, str(on))

    # 2. 버스정류장 켜기 → 줌 15 미만 안내·안 그려짐, 15 이상 그려짐
    reqs: list[str] = []
    page.on("request", lambda r: ("bus_stops.geojson" in r.url or "bus_routes.json" in r.url) and reqs.append(r.url))
    page.evaluate(JS_JUMP, [127.0276, 37.4979, 14.0])
    page.evaluate(JS_IDLE)
    page.click("[data-testid=layer-toggle-bus_stops]")
    _infra_wait(page, "bus-icon")
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(400)
    hint = _text(page, "[data-testid=layer-zoomhint-bus_stops]")
    n14 = page.evaluate(JS_RENDERED, ["bus-icon"])
    page.evaluate(JS_JUMP, [127.0276, 37.4979, 16.0])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(600)
    n16 = page.evaluate(JS_RENDERED, ["bus-icon"])
    hint16 = page.locator("[data-testid=layer-zoomhint-bus_stops]").count()
    check("[P18] 버스정류장: 켤 때 불러옴, 줌 14 '줌 15 이상에서 표시'·0개, 줌 16 그려짐·안내 사라짐",
          len(reqs) >= 1 and "줌 15 이상에서 표시" in hint and n14 == 0 and n16 > 0 and hint16 == 0,
          f"요청 {len(reqs)} '{hint}' z14={n14} z16={n16}")
    central = page.evaluate("() => JSON.stringify(window.__propediaMap.getLayoutProperty('bus-icon', 'icon-image'))")
    check("[P18] 중앙차로 정류장만 칩 테두리가 다름 (색 같음)", "chip-bus-central" in (central or ""), central or "")
    if shot:
        page.screenshot(path=str(SHOT_P18["d_bus_stops"]))

    # 3. 편의시설 켜기 → 클러스터(개수 마커) → 줌 16 이름, 분류·하위 분류 행
    _open(page, with_q + "c=127.03500,37.50300&z=13.5")
    page.click("[data-testid=layer-toggle-pois]")
    _infra_wait(page, "pois-cluster")
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(800)
    cl = page.locator("[data-testid=cluster-count]").count()
    cl_pois = page.locator("[data-testid=cluster-count][data-source=infra-pois]").count()
    cl_sch = page.locator("[data-testid=cluster-count][data-source=infra-schools]").count()
    rows = page.locator("[data-testid=poi-categories] > li").count()
    check("[P18] 줌 15 미만 클러스터(개수 원): 편의시설·학교, 편의시설 분류 행 6개",
          cl_pois > 0 and cl_sch > 0 and rows == 6, f"클러스터 {cl} (편의시설 {cl_pois}, 학교 {cl_sch}) 분류 행 {rows}")
    if shot:
        page.screenshot(path=str(SHOT_P18["a_poi"]))
    page.evaluate(JS_JUMP, [127.0280, 37.4990, 16.5])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(800)
    names = page.locator("[data-testid=infra-label][data-kind=poi]").count()
    check("[P18] 줌 16 이상 이름 (편의시설)", names > 0 and page.locator("[data-testid=cluster-count]").count() == 0, f"{names}개")
    before = page.evaluate(JS_RENDERED, ["pois-icon"])
    page.click("[data-testid=poi-cat-toggle-cafe]")
    page.wait_for_timeout(600)
    page.evaluate(JS_IDLE)
    after = page.evaluate(JS_RENDERED, ["pois-icon"])
    page.click("[data-testid=poi-cat-expand-clinic]")
    page.click("[data-testid=poi-sub-row][data-key='clinic/치과'] [data-testid=poi-sub-toggle]")
    _wait_url(page, lambda u: "clinic/" in (_q(page, "ph") or ""), 3000)
    ph = _q(page, "ph") or ""
    subs = page.locator("[data-testid=poi-sub-row]").all_inner_texts()
    check("[P18] 편의시설 분류 끄기(카페) → 그려진 수 줄어듦, 병원·의원 펼쳐 '치과' 끄기 → URL ph",
          after < before and "cafe" in ph and "clinic/치과" in ph and len(subs) == 4, f"{before}→{after} ph={ph} 하위 {len(subs)}")
    page.click("[data-testid=poi-cat-toggle-cafe]")
    page.click("[data-testid=poi-sub-row][data-key='clinic/치과'] [data-testid=poi-sub-toggle]")
    _wait_url(page, lambda u: _q(page, "ph") is None, 3000)

    # 4. 역 클릭 → 인스펙터: 호선·원자료 이름 (삼성 = 삼성 + 삼성(무역센터))
    _open(page, home)
    lon, lat = P[station]["lon"], P[station]["lat"]
    page.evaluate(JS_JUMP, [lon, lat, 16.5])
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(400)
    page.mouse.click(*page.evaluate(JS_PT, [lon, lat]))
    page.wait_for_timeout(300)
    if page.locator("[data-testid=pick-list]").count():
        page.click(f"[data-testid=pick-item][data-id='{station}']")
    _wait_url(page, lambda u: _q(page, "sel") == station, 4000)
    _inspector_ready(page)
    lines = _text(page, "[data-testid=poi-lines]")
    aliases = _text(page, "[data-testid=poi-aliases]")
    check("[P18] 역 클릭 → 인스펙터 '삼성' 호선 2개·원자료 이름 '삼성(무역센터)'",
          _q(page, "sel") == station and _text(page, "[data-testid=inspector-title]") == "삼성"
          and "2호선" in lines and "수도권 광역급행철도" in lines and "삼성(무역센터)" in aliases, f"{lines} / {aliases}")
    if shot:
        page.screenshot(path=str(SHOT_P18["c_station"]))
    # 히트 반경: 칩 중심에서 20px 떨어진 곳은 아이콘 선택이 아님
    page.click("[data-testid=inspector-close]")
    x, y = page.evaluate(JS_PT, [lon, lat])
    page.mouse.click(x + 20, y + 20)
    page.wait_for_timeout(500)
    check("[P18] 아이콘 밖(20px)을 누르면 아이콘을 고르지 않음", _q(page, "sel") != station, str(_q(page, "sel")))

    # 5. 정류장 클릭 → ARS(고정폭)·지나는 노선 칩 → 노선 선택 모드 → 해제
    _open(page, with_q + "layers=projects,impact250,impact500,parcels,schools,stations,bus_stops")
    sp = P[stop]
    page.evaluate(JS_JUMP, [sp["lon"], sp["lat"], 17.2])
    page.evaluate(JS_IDLE)
    _infra_wait(page, "bus-icon")
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(500)
    page.mouse.click(*page.evaluate(JS_PT, [sp["lon"], sp["lat"]]))
    page.wait_for_timeout(300)
    if page.locator("[data-testid=pick-list]").count():
        page.click(f"[data-testid=pick-item][data-id='{stop}']")
    _wait_url(page, lambda u: _q(page, "sel") == stop, 4000)
    _inspector_ready(page)
    ars = _text(page, "[data-testid=poi-ars]")
    mono = page.evaluate("() => getComputedStyle(document.querySelector('[data-testid=poi-ars] span')).fontFamily")
    chips = page.locator("[data-testid=route-chip-button]").count()
    rsrc = _text(page, "[data-testid=poi-route-source]")
    check("[P18] 정류장 클릭 → ARS(고정폭)·지나는 노선 칩·노선 자료 출처 줄, '노선 정보 없음' 문구 없음",
          _q(page, "sel") == stop and "22339" in ars and "mono" in mono.lower() and chips > 0 and "노선-정류장 마스터" in rsrc
          and page.locator("[data-testid=poi-no-routes]").count() == 0, f"'{ars}' {mono[:30]} 칩 {chips} '{rsrc}'")
    rid = page.get_attribute("[data-testid=route-chip-button] >> nth=0", "data-route")
    page.click("[data-testid=route-chip-button] >> nth=0")
    _wait_url(page, lambda u: _q(page, "route") == rid, 4000)
    page.wait_for_selector("[data-testid=route-chip]", timeout=5000)
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(500)
    chip = _text(page, "[data-testid=route-chip]")
    hi = page.evaluate(JS_RENDERED, ["bus-route"])
    dim = page.evaluate(JS_PAINT, ["bus-icon", "icon-opacity"])
    check("[P18] 노선 칩 → 노선 선택 모드: 상단 칩 '노선 … · 강남구 정류장 n곳'·정류장 강조·나머지 흐림·URL route",
          _q(page, "route") == rid and "강남구 정류장" in chip and hi > 0 and dim == 0.3, f"route={rid} '{chip}' 강조 {hi} 흐림 {dim}")
    if shot:
        page.evaluate(JS_JUMP, [sp["lon"], sp["lat"], 14.6])
        page.evaluate(JS_IDLE)
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOT_P18["e_bus_route"]))
    page.reload()
    _ready(page)
    page.wait_for_selector("[data-testid=route-chip]", timeout=8000)
    check("[P18] 새로고침 후 노선 선택 복원 (URL route)", _q(page, "route") == rid)
    page.click("[data-testid=route-clear]")
    _wait_url(page, lambda u: _q(page, "route") is None, 3000)
    check("[P18] 노선 해제 → 칩·URL route 사라짐", _q(page, "route") is None and page.locator("[data-testid=route-chip]").count() == 0)

    # 노선 없는 정류장 → '노선 정보는 이 자료에 없습니다'
    _open(page, with_q + f"layers=projects,stations,bus_stops&sel={no_route}")
    _inspector_ready(page)
    page.wait_for_timeout(300)
    check("[P18] 노선이 연결되지 않은 정류장(역삼역 23811) → '노선 정보는 이 자료에 없습니다'",
          "노선 정보는 이 자료에 없습니다" in _text(page, "[data-testid=poi-no-routes]"))

    # 6. 반경 보기 500m (강남역 부근) → 분류별 개수 표: 정류장 수·이름 수·노선 수, 학원 하위 분류 괄호
    _open(page, home)
    page.evaluate(JS_JUMP, [127.0276, 37.4979, 15.2])
    page.evaluate(JS_IDLE)
    page.click("[data-testid=radius-tool]")
    page.mouse.click(*page.evaluate(JS_PT, [127.0276, 37.4979]))
    page.wait_for_selector("[data-testid=radius-panel]", timeout=5000)
    page.wait_for_function("() => !document.querySelector('[data-testid=radius-row-pois]').textContent.includes('불러오는')"
                           " && !document.querySelector('[data-testid=radius-row-bus]').textContent.includes('불러오는')", timeout=20000)
    page.evaluate(JS_IDLE)
    page.wait_for_timeout(500)
    bus = _text(page, "[data-testid=radius-row-bus]")
    pois = _text(page, "[data-testid=radius-row-pois]")
    r = _q(page, "r") or ""
    check("[P18] 반경 보기 500m: 표에 정류장 수·이름 수·지나는 노선 수, 학원·병원·의원 하위 분류 괄호, URL r",
          r.endswith(",500") and re.search(r"정류장 \d+곳 · 이름 \d+개 · 지나는 노선 \d+개", bus) is not None
          and re.search(r"학원 \d+ \(교과 \d+ · 외국어 \d+ · 예체능·기타 \d+\)", pois) is not None
          and "병원·의원" in pois and "(병원" in pois, f"r={r} | {bus} | {pois.replace(chr(10), ' / ')[:160]}")
    if shot:
        page.screenshot(path=str(SHOT_P18["b_radius"]))
    page.click("[data-testid=radius-250]")
    _wait_url(page, lambda u: (_q(page, "r") or "").endswith(",250"), 3000)
    check("[P18] 반경 250m 전환 → URL r", (_q(page, "r") or "").endswith(",250"), str(_q(page, "r")))
    page.click("[data-testid=radius-tool]")
    _wait_url(page, lambda u: _q(page, "r") is None, 3000)

    # 7. 겹침 보기: 생활 인프라 칩도 영향권 밖 25%
    page.click("[data-testid=overlap-switch]")
    page.wait_for_timeout(400)
    e = page.evaluate(JS_PAINT, ["schools-icon", "icon-opacity"])
    e2 = page.evaluate(JS_PAINT, ["stations-icon", "icon-opacity"])
    check("[P18] 겹침 보기: 학교·역 칩 영향권 밖 25%",
          isinstance(e, list) and e[2] == 0.25 and isinstance(e2, list) and e2[2] == 0.25, f"{e} {e2}")
    page.click("[data-testid=overlap-switch]")

    # 8. Ctrl+K: '선릉' → 역, 정류장 번호 5자리 → 정류장(먼저), '146' → 노선 → 노선 선택 모드
    _open(page, home)
    _palette(page, "선릉")
    groups = page.locator("[data-testid=palette-group]").all_inner_texts()
    places = page.locator("[data-testid=palette-item-place]").all_inner_texts()
    check("[P18] Ctrl+K '선릉' → '역·학교' 그룹에 선릉", "역·학교" in groups and any(t.startswith("선릉") for t in places),
          f"{groups} {places[:3]}")
    page.keyboard.press("Escape")
    _palette(page, "22339")
    page.wait_for_selector("[data-testid=palette-item-stop]", timeout=8000)
    groups = page.locator("[data-testid=palette-group]").all_inner_texts()
    check("[P18] Ctrl+K 정류장 번호 '22339' → '정류장' 그룹이 맨 위", groups[:1] == ["정류장"], str(groups))
    page.keyboard.press("Escape")
    _palette(page, "146")
    page.wait_for_selector("[data-testid=palette-item-route]", timeout=8000)
    groups = page.locator("[data-testid=palette-group]").all_inner_texts()
    first = page.locator("[data-testid=palette-item-route] >> nth=0").inner_text()
    page.click("[data-testid=palette-item-route] >> nth=0")
    page.wait_for_selector("[data-testid=route-chip]", timeout=8000)
    _wait_url(page, lambda u: _q(page, "route") is not None, 3000)
    check("[P18] Ctrl+K '146' → '노선' 그룹 → 고르면 노선 선택 모드", "노선" in groups and first.startswith("146")
          and _q(page, "route") is not None and "146" in _text(page, "[data-testid=route-chip]"), f"{groups} '{first}'")
    page.click("[data-testid=route-clear]")


PERF_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]


def perf_check(pw, url: str, check) -> dict:
    """줌·이동 중 rAF 프레임 간격 (8초): 생활 인프라 끔 vs 정류장·편의시설까지 모두 켬.
    헤드리스 기본(SwiftShader 소프트웨어 GL)은 레이어와 상관없이 느리므로 GPU를 켠 브라우저를 따로 띄운다."""
    home = url.split("?")[0] + ("?debug=1" if "debug=1" in url else "")
    with_q = home + ("&" if "?" in home else "?")
    b = pw.chromium.launch(args=PERF_ARGS)
    page = b.new_page(viewport={"width": 1440, "height": 900})
    gl = page.evaluate("() => { const c = document.createElement('canvas').getContext('webgl2'); "
                       "const d = c && c.getExtension('WEBGL_debug_renderer_info'); return d ? c.getParameter(d.UNMASKED_RENDERER_WEBGL) : 'n/a' }")
    out = {"gl": gl}
    for k, layers in (("off", "projects,impact250,impact500,parcels"),
                      ("all", "projects,impact250,impact500,parcels,schools,stations,bus_stops,pois")):
        _open(page, with_q + f"layers={layers}&c=127.02760,37.49790&z=15")
        if k == "all":
            _infra_wait(page, "pois-icon", 20000)
            _infra_wait(page, "bus-icon", 20000)
        page.wait_for_timeout(2000)
        page.evaluate(JS_IDLE)
        out[k] = page.evaluate(JS_FRAMES, 8000)
    b.close()
    r, o = out["all"], out["off"]
    gpu = "SwiftShader" not in gl
    check("[P18] 성능(GPU): 정류장·편의시설 모두 켠 채 줌·이동 — 프레임 p95 ≤ 20ms (50fps 이상)", gpu and r["p95"] <= 20,
          f"{gl[:40]} · 모두 켬 평균 {r['avg']:.1f}ms p95 {r['p95']:.1f}ms 최대 {r['max']:.1f}ms 33ms 초과 {r['over33']}/{r['frames']}"
          f" · 끔 평균 {o['avg']:.1f}ms p95 {o['p95']:.1f}ms")
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--built", action="store_true", help="빌드본 http://127.0.0.1:8000/map/ 점검")
    ap.add_argument("--shot", action="store_true", help=f"스크린샷 저장 {SHOT.relative_to(ROOT)}")
    ap.add_argument("--perf", action="store_true", help="P18 프레임 시간 측정")
    a = ap.parse_args()
    url = "http://127.0.0.1:8000/map/?debug=1" if a.built else "http://localhost:3000/map/"

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    console_errors: list[str] = []
    tiles: dict[str, list[int]] = {}

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: m.type == "error" and console_errors.append(mask(m.text)))
        page.on("pageerror", lambda e: console_errors.append(mask(f"pageerror: {e}")))

        def on_resp(r):
            if "api.vworld.kr/req/wmts" in r.url:
                layer = r.url.split("/req/wmts/1.0.0/")[1].split("/")[1]
                ok = r.status == 200 and (r.headers.get("content-type") or "").startswith("image")
                tiles.setdefault(layer, []).append(200 if ok else r.status)
            elif "/api/v1/map/wms/" in r.url:          # P15 참고 WMS (API 프록시)
                m = re.search(r"/api/v1/map/wms/([^/]+)/", r.url)
                ok = r.status == 200 and (r.headers.get("content-type") or "").startswith("image")
                tiles.setdefault("wms:" + (m.group(1) if m else "?"), []).append(200 if ok else r.status)

        page.on("response", on_resp)
        aborted: list[str] = []

        def on_failed(r):
            # 화면 밖으로 나간 타일을 MapLibre가 취소하면 ERR_ABORTED — 오류가 아니라 따로 센다
            if "ERR_ABORTED" in (r.failure or ""):
                aborted.append(r.url)
            else:
                console_errors.append(mask(f"requestfailed {r.failure} {r.url}"))

        page.on("requestfailed", on_failed)
        page.goto(url)

        page.wait_for_selector("[data-testid=dong-label]", timeout=20000)
        page.wait_for_load_state("networkidle")
        labels = page.locator("[data-testid=dong-label]").all_inner_texts()
        check("법정동 라벨 14개", len(labels) == 14, f"{len(labels)}개")

        layers = page.get_attribute("[data-testid=map]", "data-layers") or ""
        need = ["mask", "bjd-line", "gu-line"]
        check("마스크·구 경계·법정동 경계 레이어", all(n in layers.split(",") for n in need), layers)
        check("기본 배경 = 회색", page.get_attribute("[data-testid=map]", "data-basemap") == "gray")
        # 첫 화면: 법정동 라벨 14개가 모두 패널에 가리지 않는 영역(좌 344·우 424·상 80·하 68px 안쪽)에 있다
        page.wait_for_timeout(800)
        boxes = [page.locator("[data-testid=dong-label]").nth(i).bounding_box() for i in range(len(labels))]
        vw, vh = 1440, 900
        inside = [bx for bx in boxes if bx and bx["x"] >= 344 and bx["x"] + bx["width"] <= vw - 424
                  and bx["y"] >= 80 and bx["y"] + bx["height"] <= vh - 68]
        check("첫 화면에 강남구 전체(라벨 14개가 보이는 영역 안)", len(inside) == 14, f"{len(inside)}/14")

        # P13 Propedia 레이어: 스타일에 4종, 강남구 전체 화면에서 사업·영향권·규제가 그려짐 (필지는 줌 14 이상)
        page.wait_for_function("() => window.__propediaMap && window.__propediaMap.loaded()", timeout=20000)
        layers = page.get_attribute("[data-testid=map]", "data-layers") or ""
        need_p = ["propedia-impact500-fill", "propedia-impact500-line", "propedia-impact250-fill",
                  "propedia-impact250-line", "propedia-regulation-fill", "propedia-regulation-line",
                  "propedia-project-fill", "propedia-project-line", "propedia-parcel-line", "propedia-parcel-line-likely"]
        check("Propedia 레이어 4종이 스타일에 있음", all(n in layers.split(",") for n in need_p),
              ", ".join(n for n in need_p if n not in layers.split(",")) or f"{len(need_p)}개 레이어")
        order = layers.split(",")
        check("Propedia 레이어는 마스크 위·구 경계선 아래",
              order.index("mask") < order.index("propedia-impact500-fill") < order.index("gu-line"))
        cnt = page.evaluate(COUNT_JS)
        check("강남구 전체 화면: 사업·영향권 도형이 그려짐 (규제는 기본 꺼짐)",
              bool(cnt) and all(cnt[s] > 0 for s in ["propedia-project", "propedia-impact"])
              and cnt["propedia-regulation"] == 0, str(cnt))
        area_labels = page.locator("[data-testid=area-label]").all_inner_texts()
        check("사업 라벨에 '확인 전' (규제 라벨은 줌 14 이상)", len(area_labels) >= 2 and all("확인 전" in t for t in area_labels),
              " | ".join(area_labels))
        hatch = page.evaluate("() => window.__propediaMap.hasImage('propedia-hatch')")
        check("규제 빗금 패턴 등록", hatch)
        if a.shot:
            SCREENS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT))

        check("worker 오류 0", not [e for e in console_errors if WORKER_RE.search(e)],
              "; ".join(e for e in console_errors if WORKER_RE.search(e))[:300])

        # 커서 위치 표시줄: 지도 보이는 영역 가운데
        box = page.locator("[data-testid=map]").bounding_box()
        cx, cy = box["x"] + (12 + 320 + 12 + box["width"] - 12 - 400 - 12) / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        page.wait_for_timeout(300)
        bar = page.inner_text("[data-testid=cursor-bar]")
        check("커서 표시줄(위도·경도·법정동)", bool(re.search(r"위도 37\.\d{5} · 경도 127\.\d{5} · \S+동", bar)), bar)

        # 드래그 중 html.map-moving
        page.mouse.down()
        moving_seen = False
        for i in range(12):
            page.mouse.move(cx + 8 * (i + 1), cy + 4 * (i + 1))
            if page.evaluate("document.documentElement.classList.contains('map-moving')"):
                moving_seen = True
        page.mouse.up()
        cleared = False
        for _ in range(30):
            if not page.evaluate("document.documentElement.classList.contains('map-moving')"):
                cleared = True
                break
            time.sleep(0.1)
        check("드래그 중 .map-moving 붙음", moving_seen)
        check("멈추면 .map-moving 떨어짐", cleared)

        # 이동 범위: 지도를 왼쪽으로 크게 끌어(동쪽으로 이동) 화면 중심이 강남구 동쪽 끝 127.1242 + 2km(0.0226°) ≈ 127.147에서 멈추는지
        for _ in range(4):
            page.mouse.move(cx + 300, cy)
            page.mouse.down()
            page.mouse.move(cx - 300, cy, steps=10)
            page.mouse.up()
        page.wait_for_timeout(600)
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(300)
        m = re.search(r"경도 (\d+\.\d+)", page.inner_text("[data-testid=cursor-bar]"))
        lon = float(m.group(1)) if m else 0
        check("이동 범위(중심 ≤ 경계 + 약 2km)", 127.12 < lon < 127.152, f"동쪽으로 끈 뒤 화면 중심 경도 {lon}")

        # 배경 4종 전환
        for bid, layer in [("base", "Base"), ("satellite", "Satellite"), ("hybrid", "Hybrid"), ("gray", "white")]:
            page.click(f"[data-basemap-option={bid}]")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            st = tiles.get(layer, [])
            on = page.get_attribute("[data-testid=map]", "data-basemap") == bid
            if a.built:
                check(f"배경 '{bid}' 전환", on, f"타일 {layer}: 200 {st.count(200)} / 기타 {sorted(set(s for s in st if s != 200))}")
            else:
                check(f"배경 '{bid}' 전환·타일 200", on and st.count(200) > 0 and all(s == 200 for s in st),
                      f"{layer}: 200×{st.count(200)}, 기타 {[s for s in st if s != 200][:5]}")

        # 회색 배경: white 레이어에 raster-saturation -1 (P13). 다른 배경에는 걸지 않는다.
        sat_js = ("() => { const m = window.__propediaMap; if (!m) return null;"
                  " return m.getStyle().layers.filter(l => l.type === 'raster' && l.id.startsWith('basemap-'))"
                  ".map(l => [l.id, m.getPaintProperty(l.id, 'raster-saturation') ?? null]) }")
        sat = page.evaluate(sat_js)
        check("회색 배경 raster-saturation = -1", bool(sat) and all(v == -1 for _, v in sat), str(sat))
        page.click("[data-basemap-option=base]")
        page.wait_for_timeout(500)
        sat_base = page.evaluate(sat_js)
        check("기본 배경에는 채도 설정 없음", bool(sat_base) and all(v is None for _, v in sat_base), str(sat_base))
        page.click("[data-basemap-option=gray]")
        page.wait_for_timeout(500)

        # 3D 토글
        page.click("[data-testid=tilt-toggle]")
        page.wait_for_timeout(800)
        check("3D 토글", page.get_attribute("[data-testid=tilt-toggle]", "aria-pressed") == "true")
        page.click("[data-testid=tilt-toggle]")
        page.wait_for_timeout(800)

        # 선택된 작업 탭: 잉크 글자 + 브랜드색 2px 막대
        tab = page.locator("[data-testid=topbar] [role=tab][aria-selected=true]").first
        after = tab.evaluate("e => { const s = getComputedStyle(e, '::after'); return [s.backgroundColor, s.height] }")
        color = tab.evaluate("e => getComputedStyle(e).color")
        check("선택 탭 2px 브랜드 막대", after == ["rgb(93, 52, 169)", "2px"], f"{after}, 글자 {color}")
        check("선택 탭 글자색 = 잉크", color == "rgb(31, 35, 40)", color)
        check("상단 작업 탭 aria-selected 1개", page.locator("[data-testid=topbar] [role=tab][aria-selected=true]").count() == 1)

        # 사업 구역 확대: 필지 외곽선까지 그려지는지 + 스크린샷
        for key, shot, label in [("apgujeong-6-1-hanyang7", SHOT_HANYANG, "한양7차"),
                                 ("ilwon-daecheong-north-moatown", SHOT_DAECHEONG, "대청마을")]:
            z = page.evaluate(FIT_JS, key)
            page.wait_for_timeout(1200)
            cnt = page.evaluate(COUNT_JS)
            check(f"{label} 확대: 사업 구역·필지 외곽선 그려짐 (줌 {z:.1f})",
                  cnt["propedia-project"] > 0 and cnt["propedia-parcel"] > 0, str(cnt))
            if a.shot:
                page.screenshot(path=str(shot))

        p14_checks(page, url, check, a.shot)
        p15_checks(page, url, check, a.shot, tiles, a.built)
        p16_checks(page, url, check, a.shot)
        p17_fit_checks(page, url, check)
        p17_checks(page, url, check, a.shot)
        p18_checks(page, url, check, a.shot)
        if a.perf:
            perf = perf_check(p, url, check)
            print(f"성능(P18): {perf}")

        if a.built:
            other = [e for e in console_errors if "api.vworld.kr" not in e and "Failed to load resource" not in e]
            check("콘솔 오류 0 (타일 차단 제외)", not other, "; ".join(other)[:400])
        else:
            check("콘솔 오류 0", not console_errors, "; ".join(console_errors)[:400])
        b.close()

    print(f"점검 대상: {url}")
    for name, ok, detail in results:
        print(f"[{'통과' if ok else '실패'}] {name}" + (f" — {detail}" if detail else ""))
    print(f"취소된 요청(ERR_ABORTED, 정상): {len(aborted)}건")
    print("타일 응답:", {k: f"200×{v.count(200)}, 기타 {sorted(set(s for s in v if s != 200))}" for k, v in tiles.items()})
    if console_errors:
        print("콘솔 오류(키 가림):")
        for e in console_errors[:10]:
            print("  ", e[:300])
    n_ok = sum(ok for _, ok, _ in results)
    print(f"{n_ok}/{len(results)} 통과")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
