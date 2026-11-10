"""지도 화면 점검 (docs/map/PLAN.md P12·P13). Playwright(Chromium), pytest 수집 대상 아님.

미리 띄울 것: uvicorn 8000 + `npm --prefix web run dev`(3000). 빌드본은 `npm --prefix web run build` 뒤 8000/map/.
- 개발 서버는 항상 http://localhost:3000/map/ 으로 연다 (브이월드 개발 키 서비스 URL이 localhost:3000).
- 키 값은 출력하지 않는다: 타일 주소의 키 자리는 *** 로 가린다.
- 빌드본은 ?debug=1로 연다 (지도 객체 window.__propediaMap은 개발 서버 또는 ?debug=1일 때만 노출).
- P13: Propedia 레이어 4종이 스타일에 있고 그려지는지, '확인 전' 라벨, 스크린샷 3장(--shot).
- P14: 레이어 끄기·URL·새로고침 복원, 투명도, 겹침 보기, 명령 팔레트(Ctrl+K), 필지 강조·툴팁, 사업 목록, 고시 칩·기준일,
  호버 툴팁·겹친 지점 선택 목록, 라벨 충돌, 키보드, 스크린샷 5장(--shot). 건수는 /api/v1/map/manifest에서 읽는다.

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
WORKER_RE = re.compile(r"worker", re.I)


def mask(url: str) -> str:
    return KEY_RE.sub(r"\1***/", url)


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
    pend = [i for i in ("ref-seoulplan", "apartments", "schools")
            if page.locator(f"[data-testid=layer-toggle-{i}]").is_disabled()]
    check("[P14] 준비 중 레이어(P15·P17·P18) 비활성", len(pend) == 3, str(pend))
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
    check("[P14] 선택 → 인스펙터 자리표시(P16)", "P16" in _text(page, "[data-testid=inspector-selected]"))
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
          for r in ("projects", "regulation-d5", "ref-seoulplan", "apartments")}
    keys = _text(page, "[data-testid=status-keys]")
    check("[P14] 데이터 상태: ready·not_adopted·pending, 키는 있음/없음만",
          st == {"projects": "ready", "regulation-d5": "not_adopted", "ref-seoulplan": "pending", "apartments": "pending"}
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


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--built", action="store_true", help="빌드본 http://127.0.0.1:8000/map/ 점검")
    ap.add_argument("--shot", action="store_true", help=f"스크린샷 저장 {SHOT.relative_to(ROOT)}")
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
                  " return m.getStyle().layers.filter(l => l.type === 'raster')"
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
