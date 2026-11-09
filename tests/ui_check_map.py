"""지도 화면 점검 (docs/map/PLAN.md P12). Playwright(Chromium), pytest 수집 대상 아님.

미리 띄울 것: uvicorn 8000 + `npm --prefix web run dev`(3000). 빌드본은 `npm --prefix web run build` 뒤 8000/map/.
- 개발 서버는 항상 http://localhost:3000/map/ 으로 연다 (브이월드 개발 키 서비스 URL이 localhost:3000).
- 키 값은 출력하지 않는다: 타일 주소의 키 자리는 *** 로 가린다.

사용: python tests/ui_check_map.py [--built] [--shot]
"""
import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "docs" / "screens" / "map_01_base.png"
KEY_RE = re.compile(r"(/req/wmts/1\.0\.0/)[^/]+/")
WORKER_RE = re.compile(r"worker", re.I)


def mask(url: str) -> str:
    return KEY_RE.sub(r"\1***/", url)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--built", action="store_true", help="빌드본 http://127.0.0.1:8000/map/ 점검")
    ap.add_argument("--shot", action="store_true", help=f"스크린샷 저장 {SHOT.relative_to(ROOT)}")
    a = ap.parse_args()
    url = "http://127.0.0.1:8000/map/" if a.built else "http://localhost:3000/map/"

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
        if a.shot:
            SHOT.parent.mkdir(parents=True, exist_ok=True)
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
            page.click(f"[data-basemap={bid}]")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            st = tiles.get(layer, [])
            on = page.get_attribute("[data-testid=map]", "data-basemap") == bid
            if a.built:
                check(f"배경 '{bid}' 전환", on, f"타일 {layer}: 200 {st.count(200)} / 기타 {sorted(set(s for s in st if s != 200))}")
            else:
                check(f"배경 '{bid}' 전환·타일 200", on and st.count(200) > 0 and all(s == 200 for s in st),
                      f"{layer}: 200×{st.count(200)}, 기타 {[s for s in st if s != 200][:5]}")

        # 3D 토글
        page.click("[data-testid=tilt-toggle]")
        page.wait_for_timeout(800)
        check("3D 토글", page.get_attribute("[data-testid=tilt-toggle]", "aria-pressed") == "true")
        page.click("[data-testid=tilt-toggle]")
        page.wait_for_timeout(800)

        # 선택된 작업 탭: 잉크 글자 + 브랜드색 2px 막대
        tab = page.locator("[role=tab][aria-selected=true]").first
        after = tab.evaluate("e => { const s = getComputedStyle(e, '::after'); return [s.backgroundColor, s.height] }")
        color = tab.evaluate("e => getComputedStyle(e).color")
        check("선택 탭 2px 브랜드 막대", after == ["rgb(93, 52, 169)", "2px"], f"{after}, 글자 {color}")
        check("선택 탭 글자색 = 잉크", color == "rgb(31, 35, 40)", color)
        check("aria-selected 탭 1개", page.locator("[role=tab][aria-selected=true]").count() == 1)


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
