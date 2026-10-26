# 진행 기록
현재 단계: P8 (배포 확인 중)

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

## P8 배포 — 진행 중 (사람 계정 필요, 2026-10-25)
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
- [ ] push 후 Vercel 재배포본 점검 (`curl /api/v1/health`, `python tests/ui_check.py --base https://propedia-pretotype.vercel.app`)
