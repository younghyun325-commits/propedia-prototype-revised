# 진행 기록
현재 단계: P1 (시작 전)

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

## P1 원문 준비·시연 주소·정답셋 초안 — 시작 전
- [ ] `pipeline/common.py`, `core/text.py`, `core/address.py`의 PNU·정규식 부분
- [ ] `python -m pipeline.collect` → `data_raw/` 4개 + `manifest.csv`
- [ ] `python -m pipeline.textify` → 쪽 텍스트·이미지·`build/page_heads.txt`. §3-2 표와 대조
- [ ] `python -m pipeline.contact_sheet D2 113 151` 및 `D2 29 31` → 모아보기 확인 → `seed/d2_selected_pages.yaml`
- [ ] D2 선택 쪽 + 29~31쪽 전사 (§8-4) → `pages.json` 갱신
- [ ] D2 12~14쪽과 생활권 범위 쪽으로 `seed/bjd_codes.csv` 생활권 확정(압구정동·청담동·신사동)
- [ ] `python -m pipeline.resolve_addresses` → `seed/demo_addresses.csv`, `bjd_codes.csv` 코드 확인
- [ ] `python -m pipeline.geocode` → 좌표, A4·A5 거리 확인 후 필요 시 주소 교체
- [ ] `evals/goldset/extraction.yaml`, `addresses.yaml` 초안 (`draft: true`)
