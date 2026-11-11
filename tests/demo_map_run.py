"""DEMO_MAP.md 5분 대본 재현 (P20). Playwright(Chromium), pytest 수집 대상 아님.

대본 순서대로 누르고, 장면마다 화면에 나와야 할 것을 확인하고, 스크린샷(docs/screens/demo_0N_*.png)과 걸린 시간을 남긴다.
사람이 말하는 시간은 빼고 화면 동작 시간만 잰다 (리허설 때 말할 시간은 대본의 장면별 목표 시간을 따른다).

미리 띄울 것: 빌드본 uvicorn 8000 (기본) 또는 개발 서버 3000 (--dev).
사용: python tests/demo_map_run.py [--dev] [--base https://...vercel.app]
"""
import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import _target  # tests/_target.py: 원격 판정·키 가림·prod_ 스크린샷

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "docs" / "screens"
# 대치동 학원가 (대치역~은마아파트 사거리 사이) 500m
DAECHI_ACADEMY = "127.06200,37.49460,500"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="개발 서버 http://localhost:3000/map/")
    ap.add_argument("--base", help="배포 주소 (예: https://….vercel.app)")
    a = ap.parse_args()
    if a.base:
        home = a.base.rstrip("/") + "/map/?debug=1"
    else:
        home = "http://localhost:3000/map/" if a.dev else "http://127.0.0.1:8000/map/?debug=1"
    q = home + ("&" if "?" in home else "?")
    remote = bool(a.base) and _target.is_remote(a.base)

    def shot(name: str) -> str:
        """원격이면 prod_ 접두 (로컬 스크린샷을 덮어쓰지 않음)"""
        return str(SCREENS / _target.shot_name(name, remote))

    results: list[tuple[str, float, bool, str]] = []
    errors: list[str] = []

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))

        def ready() -> None:
            page.wait_for_function("() => window.__propediaMap && window.__propediaMap.loaded()", timeout=30000)
            page.wait_for_load_state("networkidle")

        def idle() -> None:
            page.evaluate("""() => new Promise(r => { const m = window.__propediaMap;
              if (m.loaded() && !m.isMoving()) r(true); else m.once('idle', () => r(true)); setTimeout(() => r(false), 6000) })""")

        def text(sel: str) -> str:
            loc = page.locator(sel)
            return loc.first.inner_text() if loc.count() else ""

        def scene(n: int, name: str, slug: str, fn) -> None:
            t0 = time.perf_counter()
            ok, detail = True, ""
            try:
                ok, detail = fn()
            except Exception as e:  # noqa: BLE001 — 장면 하나가 실패해도 나머지를 돈다
                ok, detail = False, f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
            dt = time.perf_counter() - t0
            SCREENS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=shot(f"demo_{n:02d}_{slug}.png"))
            results.append((f"{n}. {name}", dt, ok, detail))

        # 1. 강남구 전체와 상단 고시 칩
        def s1():
            page.goto(home)
            ready()
            idle()
            dongs = page.locator("[data-testid=dong-label]").count()
            page.locator("[data-testid=notice-chip]").first.click()
            page.click("[data-testid=notice-open-inspector]")
            page.wait_for_selector("[data-testid=inspector-title]", timeout=10000)
            page.wait_for_selector("[data-testid=scope-label]", timeout=8000)
            idle()
            title, lab = text("[data-testid=inspector-title]"), text("[data-testid=scope-label]")
            return dongs == 14 and "토지거래허가" in title and lab == "서울 전역 적용 · 지도 경계 없음", f"법정동 {dongs}, {title} / {lab}"
        scene(1, "강남구 전체와 상단 고시 칩", "gangnam_chips", s1)

        # 2. 레이어 패널: 사업 구역·영향권·참고 레이어(참고·비상업 배지)
        def s2():
            page.keyboard.press("Escape")
            page.click("[data-testid=left-tab-layers]")
            on = [page.is_checked(f"[data-testid=layer-toggle-{i}]") for i in ("projects", "impact250", "impact500")]
            page.click("[data-testid=layer-toggle-ref-seoulplan]")
            page.wait_for_function("() => window.__propediaMap.getLayer('ref-seoulplan-fill')", timeout=10000)
            idle()
            badge = text("[data-testid=layer-row-ref-seoulplan]")
            attr = text("[data-testid=attribution]")
            ok = all(on) and "참고·비상업" in badge and "서울" in attr
            page.screenshot(path=shot("demo_02_layers.png"))
            page.click("[data-testid=layer-toggle-ref-seoulplan]")
            return ok, f"켜짐 {on}, 배지 {'참고·비상업' in badge}, 출처 '{attr[:40]}'"
        scene(2, "레이어 패널 (사업 구역·영향권·참고 레이어)", "layers", s2)

        # 3. 대청마을 북측 모아타운: 8단계 중 1번째 → 원문 보기(D9 p12 결정도)
        def s3():
            page.click("[data-testid=left-tab-projects]")
            page.click("[data-testid=project-card-2]")
            page.wait_for_selector("[data-testid=inspector-title]", timeout=10000)
            page.wait_for_timeout(300)
            idle()
            body = text("[data-testid=right-panel]")
            page.locator("[data-testid=boundary-evidence]").first.click()
            page.wait_for_selector("[data-testid=evidence-modal] img", timeout=10000)
            src = page.get_attribute("[data-testid=evidence-modal] img", "src") or ""
            page.wait_for_timeout(400)
            page.screenshot(path=shot("demo_03_daecheong.png"))
            page.keyboard.press("Escape")
            return "8단계 중 1번째" in body and "/D9/p012" in src, f"단계 문구 {'8단계 중 1번째' in body}, 원문 {src}"
        scene(3, "대청마을 북측 모아타운 (원문 D9 p12)", "daecheong_evidence", s3)

        # 4. 한양7차: 13단계 중 2번째 → 마감(2026.11.06) → 필지 528(사람 확인 전) → 영향권 안 단지
        def s4():
            page.click("[data-testid=project-card-1]")
            page.wait_for_function("() => document.querySelector('[data-testid=inspector-title]')?.innerText.includes('한양')", timeout=10000)
            idle()
            body = text("[data-testid=right-panel]")
            page.click("[data-testid=inspector-tab-parcels]")
            row = page.locator("[data-testid=project-parcel-row]", has_text="528").first
            row_text = row.inner_text()
            row.click()
            page.wait_for_timeout(500)
            idle()
            page.click("[data-testid=inspector-tab-nearby]")
            page.wait_for_selector("[data-testid=project-nearby]", timeout=10000)
            n = page.locator("[data-testid=project-nearby-row]").count()
            ok = "13단계 중 2번째" in body and "마감(2026.11.06)" in body and "사람 확인 전" in row_text and n > 0
            return ok, f"단계·마감 {('13단계 중 2번째' in body, '마감(2026.11.06)' in body)}, 528 '{row_text[:40]}', 단지 {n}"
        scene(4, "한양7차 재건축 (필지 528·영향권 안 단지)", "hanyang", s4)

        # 5. 은마: 실거래 차트와 면적대 칩
        def s5():
            page.keyboard.press("Control+K")
            page.fill("[data-testid=palette-input]", "은마")
            page.wait_for_timeout(500)
            page.wait_for_load_state("networkidle")
            page.keyboard.press("Enter")
            page.wait_for_selector("[data-testid=apt-chart]", timeout=15000)
            idle()
            bands = page.locator("[data-testid^=apt-band-]").count()
            title = text("[data-testid=inspector-title]")
            return "은마" in title and bands > 0, f"{title}, 면적대 칩 {bands}"
        scene(5, "은마 실거래 차트·면적대", "eunma", s5)

        # 6. 반경 보기: 대치동 학원가 500m, 학원 하위 분류 숫자
        def s6():
            page.goto(q + f"layers=projects,impact250,impact500,parcels,schools,stations,pois&poi=academy&r={DAECHI_ACADEMY}")
            ready()
            page.wait_for_selector("[data-testid=radius-panel]", timeout=15000)
            page.wait_for_selector("[data-testid=radius-poi-sub]", timeout=15000)
            idle()
            # 편의시설 줄: 분류별 건수와 하위 분류 숫자 (학원 → 교과·예체능 …)
            pois = text("[data-testid=radius-row-pois]")
            lines = [ln.strip() for ln in pois.splitlines() if ln.strip()]
            i = next((k for k, ln in enumerate(lines) if ln.startswith("학원")), None)
            academy = f"{lines[i]} ({' · '.join(lines[i + 1:i + 4])})" if i is not None else ""
            return bool(re.search(r"학원\D*\d", pois)), academy or pois.replace("\n", " ")[:120]
        scene(6, "반경 보기 (대치동 학원가 500m)", "radius_academy", s6)

        # 7. 타임라인 2026-05-01: 한양7차 사라짐, 대청마을 공람 중 D-day → '오늘로'
        def s7():
            page.goto(q + "t=2026-05-01&sel=project:2")
            ready()
            page.wait_for_selector("[data-testid=inspector-title]", timeout=10000)
            idle()
            body = text("[data-testid=right-panel]")
            page.click("[data-testid=left-tab-projects]")
            page.wait_for_selector("[data-testid=project-list]", timeout=8000)
            hanyang = page.locator("[data-testid=project-card-1]").count()
            page.screenshot(path=shot("demo_07_timeline_0501.png"))
            page.click("[data-testid=as-of-today]")
            page.wait_for_timeout(600)
            t_after = page.evaluate("() => new URLSearchParams(location.search).get('t')")
            ok = hanyang == 0 and "공람 중" in body and "D-day" in body and t_after is None
            return ok, f"한양7차 카드 {hanyang}, 공람 중 {'공람 중' in body}, D-day {'D-day' in body}, 오늘로 뒤 t={t_after}"
        scene(7, "타임라인 2026-05-01 → 오늘로", "timeline", s7)

        # 8. 마무리: 모든 표시에 문서·쪽·기준일
        def s8():
            page.goto(q + "sel=project:1")
            ready()
            page.wait_for_selector("[data-testid=evidence-line]", timeout=10000)
            lines = page.locator("[data-testid=right-panel] [data-testid=evidence-line]").all_inner_texts()
            as_of = text("[data-testid=inspector-as-of]")
            page.locator("[data-testid=right-panel] [data-testid=evidence-line]").first.click()
            page.wait_for_selector("[data-testid=evidence-modal]", timeout=10000)
            page.wait_for_timeout(400)
            ok = bool(lines) and all("쪽" in x for x in lines) and "기준일" in as_of
            return ok, f"출처 줄 {len(lines)}개 모두 쪽 표시 {all('쪽' in x for x in lines)}, '{as_of}'"
        scene(8, "마무리: 문서·쪽·기준일", "closing", s8)
        b.close()

    total = sum(r[1] for r in results)
    print(f"대상: {home}")
    print("| 장면 | 화면 동작 시간 | 결과 | 확인 |")
    print("|---|---:|---|---|")
    for name, dt, ok, detail in results:
        print(f"| {name} | {dt:.1f}초 | {'통과' if ok else '실패'} | {_target.mask_text(str(detail))} |")
    print(f"전체 화면 동작 시간 {total:.1f}초 · 페이지 오류 {len(errors)}건")
    for e in errors[:5]:
        print("  ", _target.mask_text(e))
    return 0 if all(r[2] for r in results) and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
