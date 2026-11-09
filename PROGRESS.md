# 진행 기록
현재 단계: P11 작업 기반 완료 (2026-11-09, 브랜치 `feat/map-console`). 다음은 docs/map/PLAN.md P12 지도 셸

## P11 작업 기반 — 완료 (2026-11-09)
지도 대시보드(docs/map/PLAN.md P11~P20)의 첫 단계. `public/*.html`·`api/`·`core/`는 건드리지 않음.
- [x] git: 이 폴더는 zip이라 저장소가 아니었음 → `git init` + `origin`(greekyogurt02/propedia-pretotype) fetch + `git reset origin/main`(작업 파일 유지)로 이력을 붙이고 `feat/map-console` 브랜치
  - 11-09 로컬 작업(로고 머리글·SHP 경로·.env 문서 등, `public/*.html`·`agents.md`·`HUMAN_TODO.md` 등 11파일 + `logo/`·`data_raw/11.공간정보/`)은 origin/main에 없어 **P11 커밋에 넣지 않고 그대로 둠**
- [x] Python 환경: `.venv` (Python 3.14.3) + requirements·requirements-build + playwright(chromium)
- [x] `web/`: `npm create vite@latest web -- --template react-ts --no-interactive` (create-vite 9.3.4)
- [x] `web/vite.config.ts`: base `/map/`, outDir `../public/map`, emptyOutDir, **port 3000 + strictPort**, `/api`·`/pages`·`/data` → 127.0.0.1:8000 프록시, vitest 설정
- [x] 디자인: `web/src/styles/tokens.css`(PLAN 블록 그대로), `glass.css`(규칙 1~6), `ui/GlassPanel.tsx`, `ui/useLiquidGlass.ts`(크롬 계열 판별 `ui/browser.ts`), `ui/LiquidGlassFilter.tsx`(SVG `#lg`), 지도 이동 중 `html.map-moving`(blur 8px·굴절 끔), 투명도 줄이기 `html.reduce-transparency`(불투명)
  - 지도 자리 회색은 새 색 없이 `color-mix(in srgb, var(--color-ink) 8%, white)` (2026-11-09 결정)
  - `.glass`가 글자색을 잉크로 고정(규칙 4)하므로 선택된 작업 탭은 굵기로만 구분
- [x] 로고: `pipeline/make_logo.py`(멱등 확인) → `web/public/brand/`
- [x] 빈 틀 `web/src/app/App.tsx`: 지도 자리 전체 화면 + 글래스 4개(상단 바 56·좌 320·우 400·타임라인 44/200), 키보드 L·I·T·Esc(`app/keys.ts`, `app/useShellEffects.ts`), 상태 `state/useMapStore.ts`(zustand), 브랜드 문구 `copy/brand.ts`
- [x] `tests/test_wording.py::test_web_src`: `web/src/**/*.ts(x)` 검사, 금지어 §9-6 + '시세', `web/src/copy/brand.ts`만 예외. 금지어를 넣은 임시 파일로 실패하는 것 확인 후 삭제
- [x] `vercel.json` buildCommand 추가(regions icn1 유지), `.gitignore`에 `web/node_modules/`·`public/map/`, `.vercelignore`에 `web/node_modules/`·`logo/`
- [ ] Preview 배포로 `/map/`·`/api/v1/health` 확인 — push가 필요해 아직 안 함

설치 버전 (`npm ls --depth=0`, Node 24.15.0 / npm 11.12.1)

| 패키지 | 버전 | 패키지 | 버전 |
|---|---|---|---|
| vite | 8.3.7 | react / react-dom | 19.3.1 |
| @vitejs/plugin-react | 6.3.0 | typescript | 7.0.2 |
| maplibre-gl | 6.17.0 | react-map-gl | 8.1.3 |
| zustand | 5.1.0 | @tanstack/react-query | 5.107.1 |
| tailwindcss / @tailwindcss/vite | 4.3.5 | lucide-react | 1.70.0 |
| pretendard | 1.3.9 | d3-scale / d3-shape | 4.0.3 / 3.2.1 |
| vitest | 5.1.0 | @types/d3-scale / @types/d3-shape | 4.0.9 / 3.2.0 |
| @types/react / @types/react-dom | 19.3.0 | oxlint (템플릿) | 1.93.0 |

로고 (`logo/` 원본 2개 모두 2348×586 RGBA 가로 워드마크·투명 배경, 정사각 심볼 없음, 반투명 잡점 많음)

| 결과 | 원본 | 크기 | 용량 |
|---|---|---|---|
| `logo-wordmark.png` (상단 바) | propedia_logo_transparent.png | 480×114 | 41,502 B |
| `logo-wordmark-white.png` (어두운 바탕) | propedia_logo_white.png | 480×114 | 14,732 B |
| `logo-mark.png` (심볼) | transparent의 첫 글자 'p' | 512×512 | 79,234 B |
| `favicon.png` | logo-mark | 64×64 | 3,107 B |

로고 그라디언트 재측정 (2348px PNG, 각 위치 ±12px 열의 불투명 픽셀 중앙값, ΔE2000) → **토큰은 PLAN 값 유지 (2026-11-09 결정)**

| 위치 | 측정 | PLAN 토큰 | ΔE2000 |
|---|---|---|---|
| 0% | #49BFFA | #4AB2E6 | 3.7 |
| 28% | #4064B8 | #5171C5 | 5.1 |
| 52% (글자 사이라 ±36px) | #592298 | #5D34A9 | 4.5 |
| 76% | #5C1A7B | #6E289E | 6.5 |
| 100% | #75105E | #7A2690 | 10.2 |

- 완료 확인
  - `npm --prefix web run build` 성공 → `public/map/index.html` 생성, 초기 JS 255.0kB(gzip 79.9kB)
  - uvicorn 8000 + `npm --prefix web run dev` → http://localhost:3000/map/ 200, 프록시 `localhost:3000/api/v1/health` 200, 빌드본 `127.0.0.1:8000/map/`도 200
  - strictPort: 3000번을 쓰는 중에 dev를 한 번 더 실행 → `Error: Port 3000 is already in use`로 종료(다른 포트로 넘어가지 않음)
  - Playwright(1440×900) 13/13: 상단 바 56·좌 320·우 400·타임라인 44, 지도 자리 1440×900, 로고 로드, `html.liquid-glass`(Chromium), L·I·T 토글·복원, Esc, 투명도 줄이기 → backdrop-filter none, 콘솔 오류 0 → `docs/screens/map_00_shell.png`
  - `pytest -q` 122 passed (기존 121 + test_web_src), `npm --prefix web run test` 5 passed
- 남은 문제: Preview 배포 확인(push 필요), 정사각 심볼 원본 없음('p'를 잘라 임시로 씀)

## P0 환경·뼈대 — 완료 (2026-10-24)
- [x] `python --version` → Python 3.11.3
- [x] `.venv` 생성, `PYTHONUTF8=1`
- [x] `requirements.txt`(fastapi, uvicorn), `requirements-build.txt`(pdfplumber, pypdf, pypdfium2, Pillow, PyYAML, httpx, python-dotenv, pytest) 작성 → 설치
  - 설치 버전: fastapi 0.162.0, uvicorn 0.54.0, pdfplumber 0.11.10, pypdf 6.21.2, pypdfium2 5.14.0, Pillow 13.0.0, PyYAML 6.0.3, httpx 0.28.1, python-dotenv 1.2.4, pytest 9.1.1
- [x] §6 폴더 생성 (data_raw, extractions, seed, pipeline, db, core, api, public/assets, public/pages, evals/goldset, tests, build), 빈 `__init__.py` (pipeline, core, evals), 빈 폴더에 `.gitkeep`
- [x] `db/schema.sql` (§7 그대로) — 메모리 SQLite로 실행해 테이블 19개 생성 확인
- [x] `PROGRESS.md`, `HUMAN_TODO.md` (§20 기본 5줄)
- [x] `.gitignore` 확인 (이미 있음) → `git init -b main`
- 완료 확인:
  - `python -c "import fastapi, pdfplumber, pypdfium2, pypdf, yaml, httpx, dotenv; print('ok')"` → `ok`
  - `git check-ignore .env` → `.env`
  - `git log --oneline | head -1` → P0 커밋 (아래 커밋 후 확인)
- 남은 문제: 없음

## P1 원문 준비·시연 주소·정답셋 초안 — 완료 (2026-10-25)
- [x] `pipeline/common.py`, `core/text.py`, `core/address.py`의 PNU·정규식 부분
- [x] `python -m pipeline.collect` → `data_raw/` 4개 + `manifest.csv` (D1 4.1MB, D2 6.1MB, D3 0.8MB, D4 0.6MB). 두 번 실행해 manifest 동일(멱등) 확인
- [x] `python -m pipeline.textify` → 쪽 텍스트·이미지(합계 15.7MB)·`build/page_heads.txt`. §3-2 표와 대조
  - 실제와 다른 점 → agents.md 수정·§21 기록: D2 인쇄 쪽 환산은 `pdf−6`(−4 아님), D2 p29 표지·p30 빈 쪽은 선택 제외, D1 굵은 글씨 중복은 `dedupe_chars`로 해결
- [x] `python -m pipeline.contact_sheet D2 113 151` 및 `D2 29 31` → 모아보기 확인 → `seed/d2_selected_pages.yaml` (12쪽: 115·116·118·119·122·123·132·133·136·137·138·140)
- [x] D2 선택 12쪽 + p31 전사 (§8-4) → 원본은 `seed/transcripts/D2/`(커밋), textify가 `build/text/D2/`로 합치고 `pages.json` 갱신
- [x] `seed/bjd_codes.csv` 생활권 확정: 압구정동·청담동·신사동 = 압구정·청담 (D2 p31·p115 "행정구역 : 신사동, 압구정동, 청담동"), `saenghwal_verified=1`. 강남구 6개 생활권은 D2 p14로 확인
- [x] `python -m pipeline.resolve_addresses` → **두 승인키 모두 `E0014` 개발승인키 기간 만료** → §19-3 대체 모드(지번만)
  - 출처 확인: A1·A3 압구정동 527(D1 p4), A10 서초구 방배동 818-14(서초구 고시 제2026-215호)
  - '예시·지번 미확인' 표시: A4 압구정동 429, A7 신사동 649-9, A8 역삼동 737, A9 대치동 316
  - 비움(키 재발급 후 확정): A2 도로명, A5, A6 / 법정동 코드 `code_verified=0` → HUMAN_TODO 6
- [x] `python -m pipeline.geocode` → A7·A8만 좌표(건물명). A1(한양7차)·A4·A9는 OSM에 없음 → 사업 중심점 없음, 500m 판정 생략 → HUMAN_TODO 7
  - Nominatim 지번 질의가 '선릉로 316' 같은 도로명 번호에 잘못 맞아 지번 질의를 뺐고, 경계·동네·정류장 결과는 거부
- [x] `evals/goldset/extraction.yaml`(D1 필드 19개, 추출 전 작성), `addresses.yaml`(A2·A5·A6 제외) 초안 (`draft: true`)
- 완료 확인: `python -m pipeline.check P1` → 15/15 통과 (텍스트 확보율 61/61 = 100%, D2 전사 12+1쪽, demo_addresses 10행)
- 남은 문제: 도로명주소 키 재발급(HUMAN_TODO 6), 좌표(HUMAN_TODO 7)

## P2 추출 — 완료 (2026-10-25)
- [x] `pipeline/init_db.py`, `load_seed.py` → 테이블 19개, 문서 4건 text_status 모두 ok, 시연 주소 10건, 단계 템플릿 13개
  - `seed/stage_templates.yaml`(§9-5 그대로), `seed/stage_rules.yaml`(§10-5)도 load_seed가 쓰므로 이때 작성
- [x] D1 추출 → `extractions/D1.json`: 필드 19, 항목 3(BJD), 사업 1(관련 이력 5건 — 원문에 1977 건설부 승인이 더 있어 실제대로) → 근거 33/33
- [x] D2 13항목(SGG 3, SAENGHWAL 10, 전부 needs_review) 13/13 → D3 9항목(SIDO 8, SGG 1 표 75 강남구 행) 9/9 → D4 8항목(SIDO 5, 동남권 SGG 3) 8/8
- [x] `evals/goldset/scope_labels.yaml` 초안 (33개 item_key, 추출자와 같은 작성자 명시)
- 완료 확인: `python -m pipeline.check P2` → 13/13 통과 (근거 일치율 63/63 = 100%)
- 남은 문제: 없음 (추출 중 `evals/goldset/extraction.yaml`은 열지 않음)

## P3 판정·DB 완성 — 완료 (2026-10-25)
- [x] `seed/stage_templates.yaml`(§9-5 그대로), `seed/stage_rules.yaml`(§10-5) — P2에서 작성
- [x] `build_projects.py`(단계는 D1 제목 + R1 → RB02, 대표 지번 → possible + 검수 큐), `events.py`, `review_queue.py`, `run_all.py`
- [x] `python -m pipeline.run_all` → 검수 큐 14건: parcel_inclusion 1, vision_item 11(D2 전사 쪽), scope_uncertain 2(D2 p12·p14 텍스트 쪽 — 2018 계획 범위 확인)
- 완료 확인: `python -m pipeline.check P3` → 10/10 통과
  - projects `apgujeong-6-1-hanyang7 | RB02 | 2026-10-06` / deadlines `2026-11-06` / change_events `4|new_project, 4|deadline_added` (step 1~3은 0건) / review_queue `parcel_inclusion | 1:1168011000105270000` / project_parcels `…105270000 | representative_only | 0`
- 남은 문제: 사업 중심 좌표 없음(HUMAN_TODO 7) → 주변 500m 판정은 좌표 확보 후 동작

## P4 조회 로직·API — 완료 (2026-10-25)
- [x] `core/db.py`(읽기 전용 `mode=ro&immutable=1`, SOURCE 조립), `timeutil.py`, `address.py`(normalize), `lookup.py`, `progress.py`, `review.py`, `catalog.py`(문서 DB·이벤트·검수 목록·평가 조회용으로 추가)
- [x] `api/index.py` (§11 엔드포인트 13개, 로컬은 API 등록 뒤 `public/` 마운트, Vercel은 `/`→`/index.html`). 요청 본문은 `dict`로 받아 pydantic 직접 import 없음
  - 진행상황 응답에 `facts`(고시 기재 면적·용도지역·세대수·용적률 — 추출값 + 근거 문장 + 원문 쪽)를 추가
  - 필지 층에 사업이 없으면 판정표 6번 문구(`no_project_message`), 좌표가 없으면 `nearby_note`로 생략 사유 표시
- [x] `tests/` 11개 파일 (§14) + `pytest.ini`
- 완료 확인:
  - `pytest -q` → 66 passed
  - `python -m uvicorn api.index:app --port 8000` 실행 후 A1 조회 → status ok, PNU 1168011000105270000, 서울 전역 13·자치구 7·법정동 13 항목, 필지에 한양7차 `possible`(review_id 1), 승인 결정 POST 시 `included`
- 남은 문제: 시연 화면(`public/`)은 P5

## P5 화면 — 완료 (2026-10-25)
- [x] `public/` 화면 5개(index·lookup·docs·review·eval) + `assets/style.css`, `app.js`(공통), 화면별 JS. 외부 CDN·글꼴 없음
  - health 응답에 `coverage_note` 추가(시작 화면 반영 범위 문구), 주소 조회 결과 위에 층별 바로가기 줄 추가, 빈 favicon 지정(브라우저 404 방지)
- [x] 수동 점검 → `tests/ui_check.py`(Playwright + 설치된 Edge)로 자동화, 28/28 통과
  - ① 시작 화면 링크 5개·대상 주소 일치, 반영 범위 4행
  - ② A1 조회: 4개 층(13·7·13·1건), 사업 카드 "재건축 13단계 중 2번째", "포함될 수 있음", D-12, "비교할 사례가 부족합니다", 원문 보기 모달(쪽 이미지 로드·Esc 닫힘), API 응답 보기(GET /api/v1/lookup, status ok)
  - ③ A8: "역삼·논현 지역생활권 장은 프리토타입 범위 밖입니다", 사업 없음 문구 / A10: "시연 범위(강남구) 밖입니다"
  - ④ 문서 DB D1 1쪽 근거 하이라이트 14곳, 필드 표 19행, 투입 1단계 "사업 상태 변화 없음", 4단계 변경 2건
  - ⑤ 검수 승인 → A1 "포함"·"이 필지는 …"·검수 결정 반영 알림·머리글 "검수 결정 1건 반영 중" → [초기화] → "포함될 수 있음"
  - ⑥ 평가 화면: "평가 전입니다…" 안내 (P6 전)
  - 모바일 390px 가로 넘침 없음, 콘솔 오류 없음
- [x] 스크린샷 10장 `docs/screens/` (Playwright 설치 성공 — 수동 캡처 불필요)
- 완료 확인: `pytest -q` → 66 passed (test_wording이 public/*.html·assets/*.js 포함 검사)
- 남은 문제: 없음

## P6 평가 — 완료 (2026-10-25)
- [x] `evals/run_eval.py` (§13): M1~M12 계산 → `evals/report.md` + `meta.eval_report` 저장. 층별 기대 항목(M6·M7)은 `core/lookup.py`를 쓰지 않고 정답셋(addresses + scope_labels)으로 따로 배치
- [x] `python -m evals.run_eval` → 12개 지표 모두 목표 달성 (텍스트화 61/61, 근거 63/63, D1 필드 19/19, 범위 33/33, 주소 7/7, 층별 재현율·정밀도 100%, 포함 판정 3/3, 원문 링크 169/169, p95 23ms, 금지어 0, 단계 RB02)
  - 주의: 정답셋 3개 모두 추출자와 같은 작성자의 초안이라 수치가 낙관적임 (화면·리포트에 "정답셋 초안" 배지) → HUMAN_TODO 1
  - 채점기 검증: 정답 3곳을 메모리에서 일부러 바꿔 돌리니 오류 6건·M6/M8 미달로 잡아냄 (채점이 형식적으로 통과하는 구조가 아님을 확인)
- 완료 확인: 종료 코드 0, `evals/report.md` 생성, `tests/ui_check.py` → 평가 화면 지표 카드 12개 표시 (29/29 통과)
- 남은 문제: 정답셋 사람 확정(HUMAN_TODO 1), 키 재발급 후 A2·A5·A6 정답 추가

## P7 시연 패키지 — 완료 (2026-10-25)
- [x] `README.md`(개발자·동혁용), `DEMO.md`(시연자용 5분 대본·예상 질문·문제 해결), `run_demo.bat`(UTF-8 + CRLF, `.gitattributes`로 CRLF 고정), `.vercelignore`(§15-2 + `docs/` — 스크린샷은 런타임에 불필요)
- [x] 처음부터 다시 빌드: `python -m pipeline.run_all && python -m evals.run_eval && pytest -q` → P3 SQL 기대값 일치, 지표 12개 통과, 66 passed. 재빌드 전후 DB 테이블 내용 동일(빌드 시각 제외)
- [x] 크기: `db/propedia.db` 388KB (≤10MB), `public/pages` 16MB (≤40MB)
- 완료 확인 — §2-2 성공 기준
  - 1 로컬 화면 5개 동작 ✓ (`tests/ui_check.py` 29/29) / Vercel은 P8
  - 2 A1 → 4개 층 모두 1건 이상(13·7·13·1) + 사업 카드 재건축 13단계 중 2번째 + 공람 기한 D-12 ✓
  - 3 모든 항목에 문서·쪽·기준일·근거 문장, 원문 보기 → 쪽 이미지 ✓ (M9 169/169, 모달 이미지 로드 확인)
  - 4 검수 승인 → "포함", 초기화 → "포함될 수 있음" ✓
  - 5 평가 화면에 §13 지표 12개 ✓
  - 6 `pytest -q` 66 passed, `python -m evals.run_eval` 종료 코드 0 ✓
  - 7 시연 경로 외부 네트워크·LLM 호출 0 ✓ (`test_no_network.py`: core/api에 httpx·requests·urllib.request·socket 없음, 표준 라이브러리+fastapi만 / `public/`에 외부 주소 없음)
- 남은 문제: HUMAN_TODO 11(계획 보고서 이용 조건)은 공개 배포 전 확인 필요

## P8 배포 — 완료 (2026-10-26)
- [x] `gh auth status` → 로그인 확인 → 커밋된 파일에 `.env` 키 값 없음 확인(값은 출력하지 않음) → `gh repo create propedia-pretotype --private --source . --push`
  - 저장소: https://github.com/greekyogurt02/propedia-pretotype (PRIVATE, main)
- [x] 동혁: Vercel 배포 완료 → https://propedia-pretotype.vercel.app (2026-10-26). HUMAN_TODO 11은 "링크 공유 안 함"으로 닫음
- [x] 동혁: 도로명주소 새 승인키 전달 → `.env`의 `JUSO_CONFM_KEY` 교체(값은 출력·커밋하지 않음)
- [x] 시연 주소 재확정 (`resolve_addresses` → `geocode` → `run_all` → `run_eval`)
  - 법정동 코드 14개 모두 API `admCd`로 확인(`code_verified=1`)
  - 압구정동 527은 도로명주소 검색 결과 없음(건물 주소 없는 필지; 526 청담고등학교, 528 한양아파트) → A1은 D1 지번 고정, A2는 인접 528 도로명 `압구정로61길 37`
  - A4 갤러리아백화점(494), A5 현대아파트(426), A6 청담자이(청담동 134-38), A7 신구중학교(신사동 621), A8 강남파이낸스센터(역삼동 737), A9 은마아파트(대치동 316), A10 방배초등학교(서초구 방배동 861-1) — 예전 예시 지번 중 역삼동 737·대치동 316은 실제와 일치
  - 좌표: 527·528은 OSM에 없음 → 사업 중심을 인접 필지 526(청담고등학교) OSM 좌표로 근사(`seed/project_coords.csv`, 출처 명시). A4 260m(주변), A5 1,595m·A6 1,383m·A7 995m(밖). Nominatim 결과에 법정동 이름이 있어야 받도록 조건 추가('한양아파트 강남구'가 신사동 건물로 맞던 문제)
  - 정답셋 `addresses.yaml` 초안 갱신(제외 주소 없음), 테스트 4개 추가(A2 도로명, A4 주변, A5 500m 밖, A10 도로명 범위 밖)
- 확인: `pytest -q` 70 passed / `run_eval` 지표 12개 통과(주소 10/10, 포함 판정 5/5, 원문 링크 265/265) / `pipeline.check P1` 15/15 / `tests/ui_check.py` 로컬 30/30
- Vercel이 1690c28 배포를 막음: GitHub 커밋 상태 "Git author butterdduck02 must have access to the project on Vercel" — 커밋 이메일이 저장소 주인(greekyogurt02)이 아닌 다른 GitHub 계정에 연결돼 있음 → 이 커밋부터 저장소 주인 계정의 noreply 이메일로 커밋해 다시 배포(전역 git 설정은 그대로)
- [x] push 후 Vercel 재배포본 점검 (`curl /api/v1/health`, `python tests/ui_check.py --base https://propedia-pretotype.vercel.app`)
- 완료 확인: 배포본 health `build_at 2026-10-26T09:40:44+09:00` / 배포 주소 API 조회 A1 `possible`, A2(도로명) PNU …105280000·같은 동 사업 1건, A4 주변 260m, A10 `out_of_scope` / `tests/ui_check.py --base https://propedia-pretotype.vercel.app --no-shots` 30/30 (새 브라우저 세션, 콘솔 오류 없음)

## P9 보정 (feedback.md) — 완료 (2026-10-26)
원 계획서의 축소판에 맞추기: 4개 층에는 지금 이 땅에 적용되는 결정만, 배경 설명은 참고로.
- [x] F1 규제 고시 추가: `../data/8.규제고시/` 파일 4개 확인 → D5(서울시 공고 제2026-1141호 토지거래허가구역 재지정, 압구정 아파트지구 1,149,476㎡, 2026.4.27~2027.4.26), D6(국토부공고 제2025-1219호 토지거래허가구역 지정, 서울 25개 구 아파트·연립·다세대, 2025.10.20~2026.12.31), D7(국토부공고 제2025-1223호 조정대상지역, 2025.10.16~지정 해제시까지), D8(국토부 보도참고자료 2026.6.30 현황표 — 투기과열지구 공고문이 없어 대신 씀, 출처 줄에 명시)
  - 원문 확인으로 고친 것: D7 공고의 신규 지정은 21개 구이고 강남구는 현황표 '현행·좌동'(feedback 표의 "서울 25개 구"는 지정 후 현황) / D6 종료일 2026-12-31은 공고문에서 확인
  - `collect`·`textify` 문서 8건, 추출 `extractions/D5~D8.json`(항목 1개씩), 근거는 쪽 텍스트 줄을 그대로 잘라 씀. 기간·면적·도면 근거는 `more_evidence`로 따로 붙여 같은 규칙으로 검사(D5 면적은 표 칸에서 '1,149,47 / 6'으로 줄바꿈된 원문 그대로)
  - 투입 단계 5~8 추가, `change_events` 0건(사업 상태 변화 없음)
- [x] F2 적용·배경: 모든 항목에 `tier`·`tier_class`·`applies_rank`·`reference_rank`·`tier_reason`(feedback §3-2 표대로, 요약·근거를 다시 읽고 확정, 바꾼 것 없음), `extractor_version` claude-code-v1.1. DB 컬럼 추가(schema_version 2), 층 배치 = applies + 효력 중 + 층별 5개 상한, 응답에 `reference`(넘침·효력 끝남 → reference_rank 순, 최대 5개), 검수 `editable_fields`에 `tier`
- [x] F3 지역생활권: SAENGHWAL 항목 전부 background, 층 배치에서 뺌, 참고에는 D2-11·D2-13만. 화면의 생활권 범위 배지 제거(정규화 줄에 '지역생활권(참고)'로만), coverage_note "2030 생활권계획(2018)은 참고로만 보여줍니다", 다른 생활권 안내 문구 삭제
- [x] F4 필지 층: `pipeline/fetch_buildings.py`(건축HUB 표제부, 동기 httpx, 원 응답 캐시·키 미출력·개인정보 칸 제외, 표제부에 지역·지구 칸이 없으면 기본개요에서 읽음) 작성, `buildings` 테이블·`parcel.building`/`building_note`·용도지역 우선순위(사업 문서 → 건축물대장 → 없음)·거리 기준 문구("사업 중심 근사값: 인접 필지 OSM 좌표") 완료
  - 키: 다른 폴더 `.env` 복사가 권한 확인에서 막혀 동혁이 키를 직접 전달 → `.env`에 기록(값 미출력, `.env.example`에는 이름만)
  - `python -m pipeline.fetch_buildings`: 8필지 중 7필지 조회(강남파이낸스센터, 청담자이아파트, 은마아파트, 신구중학교, 현대아파트, 갤러리아 백화점 생활관, 한양아파트 71·72동). **압구정동 527은 표제부 0건** → "이 지번에 건축물대장 표제부가 조회되지 않았습니다"로 그대로 기록(다른 지번으로 짐작해 바꾸지 않음)
  - 표제부(getBrTitleInfo)에는 지역·지구 칸이 없음 `[확인]` → 같은 서비스 기본개요(getBrBasisOulnInfo)의 `jiyukCdNm`·`jiguCdNm`·`guyukCdNm`에서 읽음. 사업 구역 밖 필지(A4 등)의 용도지역이 "건축물대장 기재 지역·지구 (2026.10.26 조회)"로 나옴
- [x] F5 정답셋(초안 유지)·평가·테스트·화면·문서
  - `scope_labels.yaml`: D5~D8 범위·효력 기간 + 모든 항목 tier 라벨(rank 포함) / `addresses.yaml`: `expect_regulations`(A1~A5 법정동 D5, 강남구 전부 서울 전역 D6·D7·D8)
  - 평가: M6·M7 기대 집합 = applies + 효력 중 + 층별 상한 후, M4 note에 tier 일치, 새 지표 M13 층별 상한·M14 효력 중 고시·M15 건축물 처리
  - 테스트: test_lookup(상한·배경 제외·D5/D6 위치·참고·효력 기간·끝남/시작 전), test_api(ITEM 키·reference·투입 8단계), test_review(tier 수정), test_db_build(D5~D8·tier), test_wording(target_note·tier_reason·효력 문구), 새 test_buildings
  - 화면: 효력 기간 배지·대상 기준·근거 여러 개, 참고 접기 상자, 건축물 요약 표, 문서 DB tier 배지·분류 이유, 검수 tier 선택, 시작 화면 반영 범위 8행·원칙 한 줄, 띠 문구 "공개 문서 8종"
  - 문서: agents.md(§1-2, §3, §6, §7, §9-2, §10-4, §11-3, §13-2, §17-2, §21), README, DEMO(A1 장면·예상 질문 2개)
- 확인: `pytest -q` 87 passed, 1 skipped(seed/buildings.json 없음) / `run_eval` M1~M14 통과, **M15 0/9 미달(키 대기)** — M2 근거 79/79, M13 9/9, M14 32/32 / `pipeline.check` P1 19/19·P2 21/21·P3 10/10 / `tests/ui_check.py` 로컬 40/40
  - A1: 서울 전역 5(D6·D7·D8·D3-07·D3-08) / 자치구 2(D4-07·D4-08) + 단계 분포 / 법정동 3(D5·D1-01·D1-02) / 필지: 용도지역 + 건축물 안내 + 사업 카드 / 참고 4(D3-06·D4-03 넘침, D2-11·D2-13)
  - A8: 서울 전역에 D6, 법정동 항목 없음
- 배포: fc6bc67 push → Vercel 배포 완료(health schema_version 2, build_at 2026-10-26T16:33) → `tests/ui_check.py --base https://propedia-pretotype.vercel.app --no-shots` 40/40
- 건축물대장 반영 후 확인: `run_all` → `run_eval` **M1~M15 전부 통과, 오류 0건** (M15 9/9, 표제부 조회 7/9) / `pytest -q` 88 passed / `pipeline.check` P1 19/19·P2 21/21·P3 10/10 / `tests/ui_check.py` 로컬 41/41 (A4 건축물 요약 표 점검 추가)
- 최종 배포: 030743a → Vercel 배포 완료(build_at 2026-10-26T17:05) → `tests/ui_check.py --base https://propedia-pretotype.vercel.app --no-shots` 41/41. 커밋된 파일에 키 값 없음 확인

## P10 토지 중심 + 실시간 조회 (feedback2.md) — 완료 (2026-10-26)
- [x] H1 `VWORLD_API_KEY` 동혁이 `.env`에 넣음(36자, 값 미출력) · H2 Vercel 환경변수 등록 완료(동혁)
- [x] L0 `python -m pipeline.check_keys` 작성·실행 → 처음에는 국가중점 API 인증 실패로 멈춤 → 동혁이 활용 API 수정 → 재점검 통과
  - 지오코더(getcoord parcel, 일원동 619) OK — 응답 `refined.structure.level4LC`에 PNU `1168011400106190000`이 있음(juso 대체 경로에 쓸 수 있음)
  - 이미지 API(getmap, 일원동 619 중심) OK — PNG 312KB
  - juso(테헤란로 427) errorCode 0, 1건
  - 국가중점 3종(getLandUseAttr·getLandCharacteristics·getIndvdLandPriceAttr, 압구정동 527·일원동 619) 전부 `INCORRECT_KEY`("인증키 정보가 올바르지 않습니다"). domain 없음·https/http·호스트만·localhost·127.0.0.1 모두 같음. 2D 데이터 API(LP_PA_CBND_BUBUN)도 `INCORRECT_KEY`
  - 저장 응답 `tests/fixtures/vworld/`·`tests/fixtures/juso/` (키 포함 여부 검사: 없음)
  - → HUMAN_TODO 18
  - 재점검(2026-10-26): 국가중점 3종 OK(토지이용계획 압구정동 527 18건·일원동 619 13건, 토지특성·공시지가 각 1건), 지오코더·이미지·juso OK. 응답 키 이름은 지시서 추정과 같음, 토지이용계획에 '관련 법률' 칸 없음. 결과 없는 지번은 `totalCount 0`(오류 아님)
  - 저장 응답 추가: juso(여러 건·강남구 밖·0건·가짜 키 E0001), 브이월드(결과 없음·가짜 키·지오코더 527/없음·도로명 검색) — 키 포함 여부 검사(test_live_vworld)
- [x] L1 `core/live/`: `http.py`(urllib GET 4초·재시도 1회, 메모리 캐시 1시간, .env 로더), `vworld.py`(토지 3종+지오코더+도로명 검색, land 블록, 결과 없음/불러오지 못함/키 없음 구분), `juso.py`(검색→PNU, E0001/E0014 예비 키, 실패 시 브이월드 검색 대체), `Live` 묶음·`PROPEDIA_LIVE=0`
  - 브이월드 도로명 검색 결과 `id`가 PNU, 지오코더 `refined.structure.level4LC`가 PNU `[확인]` → juso 대체 경로
- [x] L2 조회 흐름 ③ 실시간 검색·`ambiguous`·후보, `parcel.land`·`land_use_documented`, 좌표를 토지 정보로 교체(모든 주소 500m 판정), `dong.empty_note`, 화면 순서(이 땅 → 법정동 → 자치구 → 서울 전역 → 참고)·토지 정보 카드·후보 버튼·칩 묶음
- [x] L3 D9(대청마을 모아타운 관리계획안 공람, ZIP 안 PDF 16쪽)·D10(대치동 506 개발행위허가 제한 연장) 수집·텍스트화·추출(D9 항목 3·사업 1·사실 9, D10 항목 1), 모아타운 8단계 템플릿(원 계획서 문장)·규칙 M1·`project_facts`·세부 상태/단계 메모, 사업 카드 빌드를 모든 문서로 일반화
- [x] L4 지도 대조: `pipeline/daecheong_map.py` — D9 12쪽 결정도와 브이월드 연속지적도(1,058필지)를 FFT 상호상관으로 맞춤. 축척 막대(0.947m/px)로는 어긋나 배율을 넓혀 탐색 → 0.79m/px·회전 0°에서 북측 블록과 일치(대조 그림 확인, 고시의 1구역 629·2구역 626 일대도 경계 안). 경계 20m 안쪽 대지 257필지 중 서로 45m 이상 떨어진 16필지(경계까지 45~141m) → `seed/daecheong_map_reading.csv` → `map_reading`·`likely`·묶음 검수 1건(필지별 제외 가능)
- [x] L5 시연 주소 B1(일원동 619)·B2(개포로120길 55 = 633-2 단독)·B3(일원동 677-4, 사업 중심 275m)·B4(대치동 506)·B5(율현동 122, 지목 전·자연녹지) — B6는 D11을 받지 않아 없음. `fetch_land` 28필지 전부 ok → `seed/land_cache.json`, 사업 중심 좌표 = 대표 지번 지오코더(527·619). `fetch_buildings` 28필지 재조회
  - 좌표가 실제 값으로 바뀌어 A2(66m)·A4(293m)는 한양7차 '주변'이 됨 (정답셋도 규칙대로 갱신)
  - 정답셋 초안: addresses(B1~B5), land.yaml(13필지), scope_labels(D9·D10), live_addresses.yaml(강남구 지상 건물 도로명 20건)
  - 지표 M16 토지 정보 확보율, M17 토지 정보 정확도, M18(`--live`) 실시간 성공률·p95. M12에 모아타운 MT01 추가
  - 금지어 규칙(§9-6) 때문에 칩 묶음 "추천 시연" 대신 "대표 시연". 브이월드 원 자료 값(예: '비행안전제2구역')은 근거 문장처럼 금지어 검사에서 뺌
- 확인: `pytest -q` 121 passed(네트워크 없음) / `run_eval` M1~M17 통과·오류 0 / `run_eval --live` M18 20/20 · p95 1,084ms / `pipeline.check` P1·P2·P3 통과 / `tests/ui_check.py` 로컬 58/58 / G3 지번 5건(세곡·역삼·논현·삼성·개포) 토지 정보 표시·고시 없는 동 안내
- [x] L6 문서(README·DEMO·agents.md) 갱신 완료 → push(d57a54b) → Vercel 배포 → 배포본 확인
  - 배포본에서 도로명주소 검색(juso)은 정상, 브이월드는 실패 → 실패 이유를 응답 `land.errors`에 싣도록 함(HTTP 코드·결과 코드만)
  - 원인 1: Vercel 함수가 미국(iad1)에서 실행 → 브이월드가 연결을 끊음(`RemoteDisconnected`, `HTTP 502`) → `vercel.json` `regions: ["icn1"]`(서울)로 해결
  - 원인 2: 서울에서 호출하자 `INVALID_KEY`(등록되지 않은 인증키) → Vercel에 등록된 `VWORLD_API_KEY` 값이 로컬 `.env`와 다름 (따옴표·공백·'이름=' 접두어는 코드에서 걸러도 같음) → **HUMAN_TODO 26** (동혁이 Vercel 값 교체 후 재배포)
  - 배포본 `tests/ui_check.py --no-shots` 57/58 — 실패는 '자유 입력 → 토지 정보' 1건(원인 2). 시연 주소(B1·B2 포함)는 빌드 캐시로 정상
  - 동혁이 Vercel `VWORLD_API_KEY`를 로컬과 같은 값으로 교체 → 재배포(245eeb5) → 배포본 브이월드 정상
- 완료 확인 (배포본 https://propedia-pretotype.vercel.app, 서울 지역 icn1)
  - G1 시연 목록 밖 강남구 도로명 10건(`live_addresses.yaml` 앞 10건): 10/10 status ok + 토지 정보 카드, 건당 0.8~1.3초
  - G2 B1·B2: 토지 정보 + 모아타운 카드(8단계 중 1번째, 공람 마감, 단계 메모) + `possible`/`likely` + 일원동 항목 + 사실(근거·원문 쪽) — ui_check 통과
  - G3 대청마을 밖 지번 5건(세곡동 279·역삼동 823·논현동 100·삼성동 159·개포동 12): 5/5 토지 정보, 법정동 층 "확인된 고시가 없습니다"
  - `tests/ui_check.py --base https://propedia-pretotype.vercel.app --no-shots` 58/58 (자유 입력·여러 건 후보 포함)
  - 로컬: `pytest -q` 121 passed, `run_eval` M1~M17 + `--live` M18 20/20(p95 1,093ms) 오류 0, `pipeline.check` P1·P2·P3 통과, ui_check 58/58

## 화면 정리 (동혁 요청, 2026-10-26) — 완료
- 메뉴를 **시작 · 주소 조회 · 문서 DB** 3개로: 검수·평가 탭과 시작 화면 카드 2개, 조회 결과의 '검수 화면에서 확인' 버튼을 뺌
- 백엔드는 그대로: `review.html`·`eval.html` 파일, `/api/v1/review-queue`·`/api/v1/eval`, POST 조회의 `decisions` 유지
- 주소 조회는 검수 결정을 보내지 않고 GET으로만 조회 (브라우저에 예전 검수 결정이 남아 있어도 결과에 섞이지 않음), 머리글의 '검수 결정 n건 반영 중'도 뺌
- 확인: `pytest -q` 121 passed, `tests/ui_check.py` 로컬 50/50 (메뉴 3개·검수/평가 링크 없음·남은 결정 무시 점검 추가, 검수·평가 화면 점검 제거), 지난 검수·평가 화면 캡처 3장 삭제

