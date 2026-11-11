"""화면 점검 + 스크린샷 (agents.md §18 P5). pytest 수집 대상이 아니다. 빌드 PC에서 수동 실행:

  python tests/ui_check.py            # 로컬 서버를 띄워 점검 (Playwright + 설치된 브라우저)
  python tests/ui_check.py --base https://xxx.vercel.app   # 배포 주소 점검
  python tests/ui_check.py --strict              # SKIP도 실패로 센다
  python tests/ui_check.py --update-screens      # 실패 0건일 때만 docs/screens/ 갱신

`--channel` 기본값은 OS별로 다르다: Windows는 Edge(`msedge`), 그 밖에는 Chrome(`chrome`) — macOS에는 Edge가 없는 경우가 많다.

점검: ① 시작 화면 링크 3개 ②-0 대청마을 B1·B2 ② A1 조회 4개 층·사업 카드·D-day·원문 보기 모달·API 응답 보기
     ·효력 기간 배지·참고 접기 상자·건축물 요약 ③ A8·A10 안내 ④ 문서 DB D1 1쪽 근거 하이라이트·투입 순서 1~10
     ⑤ 메뉴 3개(검수·평가 화면은 메뉴에서 뺌)·남은 검수 결정 무시 ⑤-3 자유 입력·여러 건 후보

결과는 PASS / FAIL / SKIP 세 가지다. 한 단계에서 예외가 나도 FAIL로 적고 다음 단계로 간다.

실시간 외부 API에 기대는 단계 (LIVE_STEPS). 시작 전에 서버 API로 한 번 물어보고(사전 조회), 키가 설정되지 않은
상태면 화면을 누르지 않고 SKIP(사유: 키 없음)으로 적는다. 키가 있는데 실패하면 SKIP이 아니라 FAIL이다.
  | 단계 | 외부 API | SKIP 조건 |
  |---|---|---|
  | ⑤-3 자유 입력 → 토지 정보 | 도로명주소 검색(juso, 오류면 브이월드 검색) + 브이월드 토지 정보 | 브이월드 토지 정보가 '키가 설정되지 않아' |
  | ⑤-3 여러 건 → 후보 고르기 | 같음 | 같음 |
  - 사전 조회 지점: 강남구 역삼동 823 (빌드 캐시에 없는 지번 → 실시간 토지 조회를 탄다).
  - juso 키만 없으면 브이월드 검색으로 대체되므로 SKIP하지 않는다(통과하면 비고에 'juso 대신 브이월드 검색').
  - ②-0·③의 토지·건축물 정보는 빌드 캐시(land_cache·buildings)라 실시간 단계가 아니다.
SKIP은 기본적으로 실패가 아니다. --strict면 SKIP도 실패로 보고 종료 코드 1.

캡처: 기본 tmp/ui_check/<타임스탬프>/. docs/screens/는 --update-screens이고 FAIL 0건일 때만 갱신한다.
"""
import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import _target  # tests/_target.py: 원격 판정·키 가림·prod_ 스크린샷·캡처 폴더

from core.address import MSG_SEARCH_DOWN  # noqa: E402  (_target이 프로젝트 루트를 sys.path에 넣는다)
from core.live.vworld import NO_KEY_NOTE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROBE_JIBUN = "강남구 역삼동 823"          # 빌드 캐시에 없는 지번: 토지 정보가 실시간 조회를 탄다
LIVE_STEPS = {
    "free": ("⑤-3 자유 입력 → 토지 정보", "서울특별시 강남구 테헤란로 427"),
    "ambiguous": ("⑤-3 여러 건 → 후보 고르기 → 조회", "강남구 도곡로"),
}


def wait_server(base: str) -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/api/v1/health", timeout=1)
            return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("서버가 뜨지 않았습니다")


def api_lookup(base: str, address: str) -> dict:
    url = f"{base}/api/v1/lookup?" + urllib.parse.urlencode({"address": address})
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.load(r)


def land_of(j: dict) -> dict:
    return (((j.get("layers") or {}).get("parcel") or {}).get("land")) or {}


def live_state(base: str) -> tuple[str, str]:
    """실시간 토지 정보 상태: ('ok'|'no_key'|'error', 설명). 값은 응답의 상태·안내 문구만 본다 (키 값 없음)."""
    try:
        land = land_of(api_lookup(base, PROBE_JIBUN))
    except Exception as e:  # noqa: BLE001
        return "error", f"사전 조회 실패 {type(e).__name__}"
    if land.get("status") == "unavailable" and land.get("note") == NO_KEY_NOTE:
        return "no_key", "브이월드 키 없음 (토지 정보 '키가 설정되지 않아')"
    if land.get("status") in ("ok", "partial"):
        return "ok", f"토지 정보 {land.get('status')}"
    return "error", f"토지 정보 {land.get('status')}: {land.get('note')}"


def search_note(base: str, address: str) -> str:
    """주소 검색 경로 비고 (juso가 안 되면 브이월드 검색으로 대체됨)"""
    try:
        j = api_lookup(base, address)
    except Exception as e:  # noqa: BLE001
        return f"사전 조회 실패 {type(e).__name__}"
    if j.get("status") == "not_found" and j.get("message") == MSG_SEARCH_DOWN:
        return "주소 검색 사용 불가 (juso·브이월드 검색 모두 실패)"
    via = (j.get("normalized") or {}).get("match_via")
    return "juso 대신 브이월드 검색" if via == "vworld-search" else (f"검색 경로 {via}" if via else "")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    ap.add_argument("--channel", default="msedge" if sys.platform == "win32" else "chrome")
    ap.add_argument("--no-shots", action="store_true", help="캡처하지 않음")
    ap.add_argument("--strict", action="store_true", help="SKIP도 실패로 센다 (종료 코드 1)")
    ap.add_argument("--update-screens", action="store_true",
                    help="FAIL 0건일 때만 이번 캡처로 docs/screens/ 갱신 (기본은 tmp/ui_check/<타임스탬프>/에만 저장)")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    proc = None
    base = args.base
    if not base:
        base = "http://127.0.0.1:8765"
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.index:app", "--port", "8765"], cwd=ROOT,
                                env=dict(os.environ, PYTHONUTF8="1"), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    base = base.rstrip("/")
    remote = _target.is_remote(base)        # 원격이면 스크린샷 prod_ 접두 (로컬 스크린샷을 덮어쓰지 않음)
    results: list[tuple[str, str, str]] = []          # (이름, PASS|FAIL|SKIP, 비고)
    shots_dir = None if args.no_shots else _target.run_dir("ui_check")

    def check(name, ok, detail=""):
        results.append((name, "PASS" if ok else "FAIL", detail))

    def skip(name, reason):
        results.append((name, "SKIP", reason))

    @contextlib.contextmanager
    def step(name):
        """단계 하나: 예외가 나도 FAIL로 적고 다음 단계로 간다"""
        try:
            yield
        except Exception as e:  # noqa: BLE001
            check(f"{name}: 실행 중 오류", False, f"{type(e).__name__}: {str(e).splitlines()[0][:160]}")

    try:
        wait_server(base)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=args.channel)
            page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="ko-KR")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource"
                    not in m.text else None)
            page.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)

            def shot(name):
                if shots_dir:
                    # 전체 캡처에서 고정 머리글이 가운데 찍히지 않도록 캡처할 때만 풀어 둔다
                    page.add_style_tag(content=".site-header{position:static !important}")
                    page.screenshot(path=str(shots_dir / _target.shot_name(name, remote)), full_page=True)

            # ① 시작 화면
            with step("①"):
                page.goto(f"{base}/index.html")
                page.wait_for_selector("#coverage-body tr td b")
                check("① 시작 화면 링크 3개", page.locator("#steps a").count() == 3)
                check("① 반영 범위 11행 (문서 10 + 브이월드)", page.locator("#coverage-body tr").count() == 11)
                hrefs = [page.locator("#steps a").nth(i).get_attribute("href") for i in range(3)]
                check("① 링크 대상", hrefs == ["lookup.html?addr=B1", "docs.html?doc=D9", "docs.html#steps"], str(hrefs))
                check("① 땅 주소 소개", "땅 주소 하나로" in page.inner_text("h1"))
                shot("01_index.png")

            # ②-0 P10 대청마을 (feedback2.md §9 G2): 토지 정보 카드가 첫 섹션, 모아타운 카드, 포함 판정
            with step("②-0"):
                page.goto(f"{base}/lookup.html?addr=B1")
                page.wait_for_selector(".project-card", timeout=20000)
                first = page.locator("section.layer").first
                check("②-0 B1 첫 섹션이 '필지 · 이 땅'", first.get_attribute("id") == "layer-parcel"
                      and "필지 · 이 땅" in first.locator("h2").inner_text())
                landc = page.locator(".land-card").first.inner_text()
                check("②-0 B1 토지 정보 카드", all(k in landc for k in ("지목", "면적", "용도지역", "공시지가", "원/㎡"))
                      and "브이월드" in landc, landc.split("\n")[0][:40])
                mcard = page.locator(".project-card").inner_text()
                check("②-0 B1 모아타운 8단계 중 1번째", "모아타운 8단계 중 1번째 (관리계획 수립 중)" in mcard)
                check("②-0 B1 공람 마감·단계 메모", "마감(2026.05.01)" in mcard and "승인·고시는 확인된 문서가 없습니다" in mcard)
                check("②-0 B1 사실(면적·노후도·세대수·종상향)", all(k in mcard for k in ("관리지역 면적", "노후·불량", "세대수", "종상향")))
                check("②-0 B1 포함될 수 있음", page.locator(".badge.warn", has_text="포함될 수 있음").count() >= 1)
                check("②-0 B1 일원동 항목", "대청마을 북측 모아타운 관리계획(안)" in page.inner_text("#layer-dong"))
                shot("02_lookup_B1.png")
                page.goto(f"{base}/lookup.html?addr=B2")
                page.wait_for_selector(".project-card", timeout=20000)
                check("②-0 B2 포함된 것으로 보임", page.locator(".badge", has_text="포함된 것으로 보임").count() >= 1
                      and "확인해 주세요" in page.inner_text("#layer-parcel"))
                check("②-0 B2 단독 필지", "단독" in page.locator(".land-card").first.inner_text())
                shot("02c_lookup_B2.png")

            # ② A1 조회
            with step("②"):
                page.goto(f"{base}/lookup.html?addr=A1")
                page.wait_for_selector(".project-card", timeout=15000)
                check("② 4개 층 (이 땅 → 법정동 → 자치구 → 서울 전역)",
                      [page.locator("section.layer").nth(i).get_attribute("id") for i in range(4)]
                      == ["layer-parcel", "layer-dong", "layer-gu", "layer-city"])
                counts = [page.locator("section.layer").nth(i).locator(".layer-head .badge").inner_text() for i in range(4)]
                check("② 층마다 1건 이상", all(not c.startswith("0") for c in counts), str(counts))
                card = page.locator(".project-card").inner_text()
                check("② 사업 카드 13단계 중 2번째", "재건축 13단계 중 2번째" in card)
                check("② 포함될 수 있음 배지", page.locator(".badge.warn", has_text="포함될 수 있음").count() >= 1)
                dday = re.search(r"D-\d+|D-day|마감\(", card)
                check("② D-day 표시", bool(dday), dday.group(0) if dday else "")
                check("② 남은 기간 문구", "비교할 사례가 부족합니다" in card)
                # P9: 층별 5개 이하, 효력 기간 배지, 참고 접기 상자, 건축물 요약(또는 안내)
                n_items = [page.locator(f"#layer-{k} .layer-body > .item").count() for k in ("city", "gu", "dong")]
                check("② 서울 전역·자치구·법정동 5개 이하", all(n <= 5 for n in n_items), str(n_items))
                city = page.inner_text("#layer-city")
                check("② 효력 기간 배지 (D6)", "토지거래허가구역 지정: 서울 전역 아파트" in city and "효력 기간 중" in city
                      and "효력 기간 2025.10.20 ~ 2026.12.31" in city)
                dong = page.inner_text("#layer-dong")
                check("② 법정동 D5 대상 기준", "압구정 아파트지구" in dong and "대상: 압구정 아파트지구" in dong)
                check("② 생활권 배지 없음", "지역생활권 압구정·청담" not in page.inner_text("#result"))
                ref = page.locator("#reference")
                ref_title = ref.locator(":scope > summary").inner_text()
                check("② 참고 접기 상자", ref.count() == 1 and ref_title.startswith("참고: 배경 설명과 참고 계획")
                      and ref.get_attribute("open") is None, ref_title)
                ref.locator(":scope > summary").click()
                n_ref = ref.locator(":scope > .item").count()
                check("② 참고 5개 이하", 0 < n_ref <= 5, f"{n_ref}개")
                parcel = page.inner_text("#layer-parcel")
                check("② 건축물 요약 또는 안내", "건축물 요약" in parcel, parcel.split("건축물 요약", 1)[-1][:40].strip())
                page.locator("[data-page-ref]").first.click()
                page.wait_for_selector("#page-modal.open")
                page.wait_for_function("document.getElementById('page-modal-img').naturalWidth > 0")
                check("② 원문 보기 모달·쪽 이미지", True)
                shot("02b_lookup_modal.png")
                page.keyboard.press("Escape")
                check("② Esc로 닫힘", page.locator("#page-modal.open").count() == 0)
                viewer = page.locator("#result > details").last      # 조회 응답 (사업 카드 안의 것은 진행상황 응답)
                viewer.locator("summary").click()
                pres = viewer.locator("pre")
                check("② API 응답 보기", "GET /api/v1/lookup" in pres.nth(0).inner_text()
                      and '"status": "ok"' in pres.nth(1).inner_text())
                shot("02_lookup_A1.png")

            # ③ A8·A10
            with step("③"):
                page.goto(f"{base}/lookup.html?addr=A8")
                page.wait_for_selector("section.layer")
                body = page.inner_text("#result")
                check("③ A8 서울 전역 D6", "토지거래허가구역 지정: 서울 전역 아파트" in page.inner_text("#layer-city"))
                check("③ A8 법정동 압구정 항목 없음", "압구정" not in page.inner_text("#layer-dong"))
                check("③ A8 사업 없음 문구", "진행 중인 사업이 없습니다" in body)
                shot("03_lookup_A8.png")
                page.goto(f"{base}/lookup.html?addr=A4")
                page.wait_for_selector("section.layer")
                near_items = page.locator("#layer-parcel .item", has_text="주변에서 진행 중인 사업")
                a4 = near_items.first.inner_text() if near_items.count() else ""
                m4 = re.search(r"(\d+)m\b", a4)
                check("③ A4 주변 500m 사업·거리", bool(m4) and int(m4.group(1)) <= 500, m4.group(0) if m4 else "")
                bld = page.locator("#layer-parcel .item.building")
                check("③ A4 건축물 요약 표", bld.count() == 1 and "건축HUB 건축물대장" in bld.inner_text(),
                      bld.locator("tbody td").first.inner_text() if bld.count() else "")
                shot("03b_lookup_A4_nearby.png")
                page.goto(f"{base}/lookup.html?addr=A10")
                page.wait_for_selector("#result .box.info")
                check("③ A10 시연 범위 밖", "시연 범위(강남구) 밖입니다" in page.inner_text("#result"))

            # ④ 문서 DB
            with step("④"):
                page.goto(f"{base}/docs.html?doc=D1&page=1")
                page.wait_for_selector(".page-text mark", timeout=15000)
                marks = page.locator(".page-text mark").count()
                check("④ D1 1쪽 근거 하이라이트", marks >= 3, f"mark {marks}개")
                check("④ D1 필드 표 19행", page.locator("table").first.locator("tbody tr").count() == 19)
                shot("04_docs_D1.png")
                page.locator('[data-step="1"]').click()
                check("④ 투입 1단계 변화 없음", "사업 상태 변화 없음" in page.inner_text("#step-detail"))
                page.locator('[data-step="4"]').click()
                check("④ 투입 4단계 변경 2건", page.locator("#step-detail tbody tr").count() == 2)
                check("④ 투입 단계 10개", page.locator("[data-step]").count() == 10)
                page.locator('[data-step="9"]').click()
                check("④ 투입 9단계(D9) 새 사업 카드", "새 사업 카드" in page.inner_text("#step-detail"))
                page.locator('[data-step="5"]').click()
                check("④ 투입 5단계(규제 고시) 변화 없음", "사업 상태 변화 없음" in page.inner_text("#step-detail"))
                page.locator("#steps").scroll_into_view_if_needed()
                shot("04b_docs_steps.png")

            # ⑤ 메뉴: 검수·평가 화면은 메뉴에서 뺐다 (2026-10-26). 조회는 검수 결정을 보내지 않는다
            with step("⑤"):
                page.goto(f"{base}/lookup.html?addr=A1")
                page.wait_for_selector(".project-card", timeout=15000)
                nav = [page.locator("#site-header nav a").nth(i).inner_text()
                       for i in range(page.locator("#site-header nav a").count())]
                check("⑤ 메뉴 3개 (시작·주소 조회·문서 DB)", nav == ["시작", "주소 조회", "문서 DB"], str(nav))
                check("⑤ 검수·평가 링크 없음", page.locator("a[href^='review.html'], a[href^='eval.html']").count() == 0)
                rid = page.evaluate("fetch('/api/v1/review-queue').then(r => r.json()).then(q => q[0].id)")
                page.evaluate(f"localStorage.setItem('propedia.pretotype.decisions.v1', JSON.stringify([{{review_id: {rid}, action: 'approve'}}]))")
                page.reload()
                page.wait_for_selector(".project-card", timeout=15000)
                check("⑤ 남아 있는 검수 결정은 조회에 쓰지 않음", page.locator(".badge.warn", has_text="포함될 수 있음").count() >= 1
                      and "구역에 포함되어 있습니다" not in page.inner_text("#result")
                      and "검수 결정" not in page.inner_text("#site-header"))
                page.evaluate("localStorage.removeItem('propedia.pretotype.decisions.v1')")

            # ⑤-3 자유 입력(실시간 도로명 검색·토지 정보)과 여러 건 후보 — LIVE_STEPS (실시간 외부 API)
            with step("⑤-3"):
                page.goto(f"{base}/lookup.html")
                page.wait_for_selector("#chips .chip")
                check("⑤-3 대표 시연 칩이 맨 앞", page.locator("#chips .chip").first.get_attribute("data-addr") == "B1")
            state, state_note = live_state(base)
            print(f"실시간 사전 조회({PROBE_JIBUN}): {state} — {state_note}")

            name, q = LIVE_STEPS["free"]
            if state == "no_key":
                skip(name, f"키 없음: {state_note}")
            else:
                with step(name):
                    note = search_note(base, q)
                    page.goto(f"{base}/lookup.html")
                    page.wait_for_selector("#chips .chip")
                    page.fill("#q", q)
                    page.locator("#search-form button").click()
                    page.wait_for_selector("#result .land-card, #result .box.info", timeout=30000)
                    landc = (page.locator("#result .land-card").first.inner_text()
                             if page.locator("#result .land-card").count() else "")
                    check(name, "공시지가" in landc and "삼성동" in page.inner_text("#result"),
                          " · ".join(x for x in (landc.split("\n")[0][:30], note) if x))

            name, q = LIVE_STEPS["ambiguous"]
            if state == "no_key":
                skip(name, f"키 없음: {state_note}")
            else:
                with step(name):
                    note = search_note(base, q)
                    page.goto(f"{base}/lookup.html")
                    page.wait_for_selector("#chips .chip")
                    page.fill("#q", q)
                    page.locator("#search-form button").click()
                    page.wait_for_selector("#result .candidate", timeout=30000)
                    n_c = page.locator("#result .candidate").count()
                    page.locator("#result .candidate").first.click()
                    page.wait_for_selector("#result .land-card", timeout=30000)
                    check(name, n_c >= 2 and "도곡동" in page.inner_text("#result"),
                          " · ".join(x for x in (f"후보 {n_c}개", note) if x))
                    shot("09_lookup_free_input.png")

            # 좁은 화면(390px)에서 가로 스크롤 없음
            with step("모바일"):
                m = browser.new_page(viewport={"width": 390, "height": 844})
                m.goto(f"{base}/lookup.html?addr=A1")
                m.wait_for_selector(".project-card", timeout=15000)
                sw = m.evaluate("document.documentElement.scrollWidth")
                check("모바일 390px 가로 넘침 없음", sw <= 392, f"scrollWidth {sw}")
                if shots_dir:
                    m.screenshot(path=str(shots_dir / _target.shot_name("08_lookup_mobile.png", remote)),
                                 full_page=False)
            check("콘솔 오류 없음", not errors, "; ".join(errors[:3]))
            browser.close()
    finally:
        if proc:
            proc.terminate()
            proc.wait(5)
    w = max(len(n) for n, _, _ in results)
    for n, st, d in results:
        print(f"{st} | {n.ljust(w)} | {_target.mask_text(str(d))}")
    n_pass, n_fail, n_skip = (sum(1 for _, st, _ in results if st == k) for k in ("PASS", "FAIL", "SKIP"))
    print(f"→ PASS {n_pass} · FAIL {n_fail} · SKIP {n_skip} (전체 {len(results)})"
          + (" · --strict: SKIP도 실패로 셈" if args.strict and n_skip else ""))
    if shots_dir:
        _target.publish_shots(shots_dir, args.update_screens, n_fail)
    elif args.update_screens:
        print("docs/screens/ 갱신 안 함: --no-shots")
    return 1 if n_fail or (args.strict and n_skip) else 0

if __name__ == "__main__":
    sys.exit(main())
