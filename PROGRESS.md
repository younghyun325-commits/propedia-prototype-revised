# 진행 기록
현재 단계: P2 (시작 전)

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

## P2 추출 — 시작 전
- [ ] `pipeline/init_db.py`, `load_seed.py` → `python -m pipeline.init_db && python -m pipeline.load_seed`
- [ ] D1 추출 → `extractions/D1.json` → `python -m pipeline.load_extractions --check`
- [ ] D2 → D3 → D4 같은 방법
- [ ] `evals/goldset/scope_labels.yaml` 초안 (모든 item_key)
