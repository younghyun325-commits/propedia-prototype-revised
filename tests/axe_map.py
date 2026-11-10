"""지도 화면 접근성 점검 (P20): axe-core를 Playwright로 주입해 화면 상태별 위반을 센다. pytest 수집 대상 아님.

준비: npm install --prefix build/axe axe-core@4.10.3   (build/는 git에 올리지 않음, 의존성 추가 없음)
미리 띄울 것: 빌드본 uvicorn 8000 (`npm --prefix web run build` 뒤) 또는 개발 서버 3000.
목표: serious·critical 위반 0개. 나머지(moderate·minor)는 목록으로만.
대상 상태: 첫 화면 · 사업 인스펙터 · 원문 모달 · 투명도 줄이기 · D5 범위 표시 · 단축키 도움말 · 1180px · 390px 하단 시트.
지도 캔버스(그림)는 글자가 아니므로 대비 검사에서 뺀다.

사용: python tests/axe_map.py [--dev]
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "build" / "axe" / "node_modules" / "axe-core" / "axe.min.js"
RUN_JS = """async () => {
  const r = await axe.run(document, { exclude: [['.maplibregl-canvas']],
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } });
  return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help,
    nodes: v.nodes.slice(0, 4).map(n => n.target.join(' ') + (n.any[0]?.data?.contrastRatio ? ` (대비 ${n.any[0].data.contrastRatio})` : '')),
    count: v.nodes.length })) }"""


def _ready(page) -> None:
    page.wait_for_function("() => document.querySelector('[data-testid=map]') && window.__propediaMap && window.__propediaMap.loaded()",
                           timeout=30000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="개발 서버 http://localhost:3000/map/")
    a = ap.parse_args()
    if not AXE.is_file():
        print(f"axe-core가 없습니다: {AXE.relative_to(ROOT)} — npm install --prefix build/axe axe-core@4.10.3")
        return 1
    base = "http://localhost:3000/map/" if a.dev else "http://127.0.0.1:8000/map/"
    dbg = "" if a.dev else "debug=1"

    def url(q: str = "") -> str:
        parts = [x for x in (dbg, q) if x]
        return base + ("?" + "&".join(parts) if parts else "")

    states = []
    with sync_playwright() as p:
        b = p.chromium.launch()

        def run(name: str, page) -> None:
            page.add_script_tag(path=str(AXE))
            states.append((name, page.evaluate(RUN_JS)))

        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.goto(url())
        _ready(page)
        run("첫 화면 (1440)", page)

        page.goto(url("sel=project:1"))
        _ready(page)
        page.wait_for_selector("[data-testid=inspector-title]", timeout=15000)
        run("사업 인스펙터 (한양7차)", page)

        page.locator("[data-testid=project-deadline] [data-testid=evidence-line]").first.click()
        page.wait_for_selector("[data-testid=evidence-modal]", timeout=10000)
        page.wait_for_timeout(600)
        run("원문 모달", page)
        page.keyboard.press("Escape")

        page.goto(url("sel=regulation:D5"))
        _ready(page)
        page.wait_for_selector("[data-testid=scope-label]", timeout=10000)
        run("D5 범위 표시 (법정동 단위)", page)

        # 흐려진 도형 라벨 (효력 전 규제: 기준일을 D10 효력 시작 전으로, 줌 15)
        page.goto(url("layers=projects,regulations&t=2026-03-01&c=127.06234,37.49205&z=15.5"))
        _ready(page)
        dim = page.locator("[data-testid=area-label][data-dim='1']").count()
        run(f"흐려진 규제 라벨 (기준일 2026-03-01, 흐린 라벨 {dim}개)", page)

        page.goto(url("sel=regulation:D5"))
        _ready(page)
        page.keyboard.press("Shift+Slash")
        page.wait_for_selector("[data-testid=shortcuts-modal]", timeout=5000)
        run("단축키 도움말", page)
        page.keyboard.press("Escape")

        page.evaluate("() => localStorage.setItem('propedia.map.reduceTransparency.v1', '1')")
        page.goto(url("sel=project:1"))
        _ready(page)
        run("투명도 줄이기 (사업 인스펙터)", page)
        page.evaluate("() => localStorage.removeItem('propedia.map.reduceTransparency.v1')")
        page.close()

        for w, h, q, name in [(1180, 800, "sel=project:1", "1180px (인스펙터 겹침)"), (390, 844, "sel=project:1", "390px (하단 시트)")]:
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto(url(q))
            _ready(pg)
            run(name, pg)
            pg.close()
        b.close()

    serious = 0
    print(f"점검 대상: {base}")
    for name, vs in states:
        sc = [v for v in vs if v["impact"] in ("serious", "critical")]
        serious += sum(v["count"] for v in sc)
        print(f"\n## {name}: serious·critical {sum(v['count'] for v in sc)}건 · 그 밖 {sum(v['count'] for v in vs if v not in sc)}건")
        for v in vs:
            print(f"- [{v['impact']}] {v['id']} ×{v['count']} — {v['help']}")
            for n in v["nodes"]:
                print(f"    · {n}")
    out = ROOT / "build" / "axe_map.json"
    out.write_text(json.dumps(states, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nserious·critical 합계 {serious}건 (상세 {out.relative_to(ROOT)})")
    return 0 if serious == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
