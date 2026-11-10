# Propedia 프리토타입 — 강남구 · 토지 정보 + 고시 (대청마을 모아타운, 한양7차 재건축)

강남구 **땅 주소**(도로명 또는 지번) 하나를 넣으면 먼저 **그 땅의 토지 정보**(지목·면적·용도지역·지역지구·공시지가, 브이월드 실시간)를 보여주고, 그 땅에 해당하는 공공 문서(고시·공고·계획)를 **4개 층**(필지·법정동·자치구·서울 전역)으로 모아 한 응답으로 돌려줍니다. 필지가 정비사업(모아타운·재건축) 구역에 걸리면 **현재 단계·기한**을 기준일·원문 쪽과 함께 보여줍니다. 대상은 토지 소유자입니다.

- 작업 지시서: [agents.md](agents.md) · 지도 계획: [docs/map/PLAN.md](docs/map/PLAN.md) · 진행 기록: [PROGRESS.md](PROGRESS.md) · 사람 확인 목록: [HUMAN_TODO.md](HUMAN_TODO.md)
- 시연 대본: 지도 화면 [DEMO_MAP.md](DEMO_MAP.md) (5분, P20) · 기존 화면 [DEMO.md](DEMO.md)
- GitHub(비공개): https://github.com/greekyogurt02/propedia-pretotype
- 배포 주소: https://propedia-pretotype.vercel.app (Vercel Hobby, GitHub `main` push 시 자동 배포)

## 지도 화면 (`/map/`, P11~P20)

첫 화면(`/`)은 **`/map/`으로 넘어갑니다**(307 임시 리디렉트 — Vercel은 `vercel.json` `redirects`, 로컬 FastAPI도 같은 동작).
기존 화면은 그대로 둡니다: `/index.html`(시작·주소 조회), `/lookup.html`, `/docs.html`(문서 DB). 지도 상단 바 톱니(설정) 메뉴에 '주소로 조회(기존 화면)'·'문서 DB' 링크가 있습니다.

- 강남구 지도 위에 Propedia 레이어(사업 구역·영향권 250m/500m·포함 판정 필지·규제 구역), 공식 참고 레이어(서울시 도시계획사업 현황·의제처리구역·용도지역/지구단위계획/지적도 WMS), 아파트 실거래 단지, 생활 인프라(학교·역·버스·편의시설 6분류).
- 좌측 패널(레이어·사업 목록·고시 피드·데이터 상태), 우측 인스펙터(사업·규제·필지·단지·시설), 하단 타임라인('그날 기준' 보기, URL `t`), 상단 서울 전역·구 단위 고시 칩, `Ctrl+K` 검색, 반경 보기.
- 지도 경계가 없는 규제(P20): D5(압구정 아파트지구, 경계 확인 전)는 압구정동 법정동 경계를 점선으로 강조하고 '법정동 단위 표시 · 경계 확인 전', 서울 전역 고시(D6·D7·D8)는 강남구 전체 + 구 경계 강조와 '서울 전역 적용 · 지도 경계 없음'을 표시합니다.
- 접근성(P20): 설정 메뉴 '투명도 줄이기'(이 브라우저에 저장), `?` 단축키 도움말, `prefers-reduced-motion`이면 지도 이동 애니메이션 없음, axe serious·critical 0건(`tests/axe_map.py`).
- 반응형(P20): 1280px 이상 기본 배치 / 1024~1279px 좌측 패널 접힘(아이콘 줄)·인스펙터 겹침 / 1024px 미만 보기 전용(하단 시트 3단, 반경 보기·스크러버 끌기 숨김).
- 화면 문구는 `web/src/copy/ui.ts` 한 곳에 있고 금지어 검사(`tests/test_wording.py`, '예정'·'시세'·평가어 포함) 대상입니다. 색은 `web/src/styles/tokens.css` 토큰만, 글래스는 `GlassPanel`만 씁니다.

### 로컬 실행 (터미널 2개)

```bash
# 터미널 1 — API (8000번). 새 경로가 404면 남은 uvicorn worker 프로세스부터 확인
.venv/Scripts/python.exe -m uvicorn api.index:app --port 8000 --reload
# 터미널 2 — 지도 화면 개발 서버 (3000번 고정: 브이월드 개발 키 서비스 URL이 localhost:3000)
npm --prefix web run dev            # http://localhost:3000/map/  (/api는 8000으로 프록시)
```

빌드본 확인: `npm --prefix web run build` → `public/map/` → `http://127.0.0.1:8000/map/` (점검 스크립트는 `?debug=1`).

### 지도 데이터 빌드 순서

아래 '빌드 순서'(고시 DB) 다음에 지도 레이어를 만듭니다. 모두 빌드 때만 네트워크를 쓰고, 화면·API는 만들어진 파일·DB만 읽습니다.

| 순서 | 명령 | 네트워크 | 결과 |
|---|---|---|---|
| 1 | `python -m pipeline.build_map_base` | 사용 (브이월드 2D) | `public/data/base/gangnam.geojson`·`bjd.geojson` |
| 2 | `python -m pipeline.fetch_parcels` → `align_drawings` → `boundaries` | 사용 | `seed/parcels.geojson`, `seed/boundaries/` (도면 정합 경계) |
| 3 | `python -m pipeline.import_reference` | – | `public/data/layers/ref_*.geojson` (서울플랜+·의제처리구역 SHP) |
| 4 | 실거래 (아래 'market.db 갱신 규칙') | 사용 (공공데이터포털) | `db/market.db`, `seed/apartments.geojson` |
| 5 | `python -m pipeline.fetch_pois` | 사용 (상가 API, 캐시 있으면 0회) | `public/data/layers/` 학교·역·정류장·노선·편의시설 |
| 6 | `python -m pipeline.build_map_layers` | – | `public/data/layers/propedia_*.geojson`, `manifest.json` (좌표 소수 6자리) |
| 7 | `npm --prefix web run build` | – | `public/map/` (Vercel은 `vercel.json` `buildCommand`가 다시 빌드) |
| 8 | `python -m evals.run_eval` (`--live`) | (`--live`만) | M1~M24 (`--live`면 M18·M21까지) |
| 9 | `python -m pipeline.check_secrets` | – | 빌드 산출물·커밋 파일의 키 노출 건수(변수 이름별, 값은 출력 안 함) |

## 반영 범위

| ID | 문서 | 층 | 쓴 쪽(PDF) |
|---|---|---|---|
| D1 | 강남구 공고 제2026-2347호 (구보 제1871호) 한양7차 재건축 정비계획(안) 공람·공고 | 법정동·필지·사업 카드 | 1~21 (18~21 도면은 원문 보기용) |
| D2 | 2030 서울생활권계획 강남구 (2018) | 참고만 (지역생활권은 층에 두지 않음) | 12~14, 31, 압구정·청담 장 12쪽 전사 |
| D3 | 2030 도시·주거환경정비기본계획 (2025.6.26 변경) | 서울 전역 (용적률 기준) | 243~248, 262~268, 275~277 |
| D4 | 2040 서울도시기본계획 (2023) | 서울 전역·동남권 | 73, 75~80, 175~179 |
| D5 | 서울특별시 공고 제2026-1141호 토지거래허가구역 재지정 (2026.4.9) | 법정동 (압구정 아파트지구) | 1~2 (4~9 지형도면은 원문 보기용) |
| D6 | 국토교통부공고 제2025-1219호 토지거래허가구역 지정 (2025.10.15) | 서울 전역 | 1~2 |
| D7 | 국토교통부공고 제2025-1223호 조정대상지역 지정 (2025.10.16) | 서울 전역 | 1~2 |
| D8 | 국토교통부 보도참고자료 투기과열지구·조정대상지역 추가 지정 (2026.6.30) — 공고문이 아님 | 서울 전역 (현황표) | 1, 5 |
| D9 | 강남구 공고 제2026-1034호 대청마을 북측구역(일원동 619번지 일원) 모아타운 관리계획(안) 공람 (구보 ZIP 안 PDF) | 법정동(일원동)·필지·모아타운 사업 카드 | 1~11 (12~16 도면은 원문 보기·지도 대조용) |
| D10 | 강남구 고시 제2026-69호 개발행위허가 제한 연장 — 대치동 506 일대(선경아파트) (구보 ZIP 안 PDF) | 법정동(대치동) | 1~3 |
| 토지 | 브이월드 토지이용계획·토지특성·개별공시지가·지오코더 (실시간, 시연 주소는 빌드 캐시) | 필지 (토지 정보 카드) | — |

원칙: 사실만 보여준다 / 모든 항목에 근거 문장·원문 쪽·기준일 / **4개 층에는 지금 이 땅에 적용되는 결정만(층별 5개 이하), 배경 설명은 '참고'로 접어 둔다** / 사업 단계는 고시 문서 제목 + 규칙으로만 / 단계 설명·안내 문구는 사람이 쓴 템플릿에서만 / 남은 기간은 비교 사례가 부족하면 비워 둔다.

## 폴더

```
api/index.py        FastAPI 앱 (Vercel 진입점, 로컬은 public/도 서빙)
core/               조회·판정 로직 (표준 라이브러리만, 네트워크 없음, DB 읽기 전용)
public/             화면 5개 + assets + 원문 쪽 이미지(pages/)
db/                 schema.sql, propedia.db (빌드 산출물, 커밋함)
pipeline/           빌드 스크립트 (시연 코드에서 import 금지)
seed/               법정동 코드·시연 주소·단계 템플릿/규칙·D2 쪽 선택·전사 원본(transcripts/)·건축물대장 요약(buildings.json)
extractions/        Claude Code가 직접 추출한 D1~D8.json (claude-code-v1.1: tier·효력 기간 포함)
data_raw/           원본에서 쓰는 쪽만 뽑은 발췌 PDF + manifest.csv
evals/              정답셋(goldset/, 초안), run_eval.py, report.md
tests/              pytest (+ ui_check.py: 브라우저 화면 점검, 수동 실행)
docs/screens/       화면 캡처
```

## 설치

Python 3.11 이상 (Vercel은 3.12).

```bash
python -m venv .venv
source .venv/Scripts/activate        # PowerShell: .venv\Scripts\Activate.ps1
export PYTHONUTF8=1
pip install -r requirements.txt -r requirements-build.txt
```

- 런타임 의존성은 `fastapi`, `uvicorn`뿐입니다. `requirements-build.txt`는 빌드·테스트용입니다.
- 화면 점검(`tests/ui_check.py`)을 쓰려면 `pip install playwright` (설치된 Edge를 쓰므로 브라우저 내려받기는 필요 없음).

## 빌드 순서

원본 PDF는 `../data/`에 있어야 합니다(수정·이동 금지).

| 순서 | 명령 | 네트워크 | 비고 |
|---|---|---|---|
| 1 | `python -m pipeline.collect` | – | 발췌 PDF + manifest |
| 2 | `python -m pipeline.textify` | – | 쪽 텍스트·이미지, `seed/transcripts/` 전사본 합치기 |
| 3 | `python -m pipeline.contact_sheet D2 113 151` | – | D2 쪽 고르기용 모아보기 |
| 4 | (Claude Code) D2 전사 → `seed/transcripts/D2/`, 추출 → `extractions/` | – | 외부 LLM API 없음 |
| 5 | `python -m pipeline.resolve_addresses` | **사용** | 도로명주소 API(.env 키). 키가 안 되면 지번만 쓰는 대체 목록으로 작성 |
| 6 | `python -m pipeline.geocode` | **사용** | OSM Nominatim, 초당 1회, `build/geocode_cache.json` 캐시 |
| 7 | `python -m pipeline.check_keys` | **사용** | P10 L0: 브이월드·도로명주소 키 점검(상태·건수만 출력), 테스트용 저장 응답 `tests/fixtures/` |
| 8 | `python -m pipeline.run_all` | – | DB 전체 재빌드 + P3 확인 SQL 출력 |
| 9 | `python -m pipeline.daecheong_map` | **사용** | D9 결정도와 브이월드 연속지적도를 맞대 후보 목록·대조 그림(`build/daecheong/`) → Claude Code가 골라 `seed/daecheong_map_reading.csv` |
| 10 | `python -m pipeline.fetch_land` | **사용** | 브이월드 토지 정보 빌드 캐시 `seed/land_cache.json`, 사업 중심 좌표 `seed/project_coords.csv` |
| 11 | `python -m pipeline.fetch_buildings` | **사용** | 건축HUB 건축물대장 표제부(.env `DATA_GO_KR_SERVICE_KEY`) → `seed/buildings.json`. 원 응답은 `build/buildings_raw/` 캐시 |
| 12 | `python -m pipeline.run_all` | – | 캐시·좌표·건축물 요약을 DB에 넣으려고 한 번 더 |
| 13 | `python -m evals.run_eval` | – | 지표 M1~M17 (네트워크 없음) → `evals/report.md`, `meta.eval_report` |
| 14 | `python -m evals.run_eval --live` | **사용** | M18 실시간 조회(시연 목록 밖 강남구 도로명주소 20건)까지 |
| 15 | `python -m pipeline.fetch_pois` | **사용** (상가 API 67회, 캐시 있으면 0회) | P18 생활 인프라: `data_raw/12.생활인프라/` CSV(학교·역·버스 3종, 커밋 안 함) + 상가(상권)정보 API(.env `DATA_GO_KR_SERVICE_KEY`, 원 응답 `build/pois_raw/`) → `public/data/layers/` 학교·역·정류장·노선·편의시설 6분류. `--offline`은 캐시만. 분류표 `seed/poi_categories.yaml` |

### 환경변수

로컬은 `.env`(커밋 금지), Vercel은 프로젝트 Settings → Environment Variables에서 읽습니다. 키 값은 출력·로그·커밋하지 않습니다(`python -m pipeline.check_secrets`로 건수만 점검).

| 이름 | 용도 | Vercel 환경 | 필수 여부 |
|---|---|---|---|
| `VITE_VWORLD_KEY` | 브라우저 배경지도(WMTS 타일). **빌드 때 번들(`public/map/assets/*.js`)에 그대로 들어가는 것이 정상**이므로, 브이월드에서 **서비스 URL 제한을 건 키**(배포 주소만 허용)여야 합니다 | Production · Preview (빌드 때 필요) | 지도 배경에 필수 (없으면 경계·레이어만 보임) |
| `VWORLD_API_KEY` | 서버 실시간 조회: 토지 정보·필지 클릭 조회·지오코더·참고 WMS 프록시 (`core/live/vworld.py`) | Production · Preview | 필수 (없으면 시연 주소만 빌드 캐시로 동작) |
| `VWORLD_DOMAIN` | 브이월드 요청의 `domain` (인증키에 등록한 서비스 URL). 없으면 운영 주소 | Production · Preview | 선택 |
| `JUSO_CONFM_KEY` | 도로명주소 검색 (`core/live/juso.py`). 없거나 실패하면 브이월드 검색으로 대체 | Production · Preview | 선택 |
| `DATA_GO_KR_SERVICE_KEY` (+ `DATA_GO_KR_*_URL`) | 실거래·단지 목록·상가·건축물대장 **로컬 빌드용** (`fetch_trades`·`fetch_pois`·`fetch_buildings`·`fetch_apt_basis`) | **넣지 않음** (런타임에서 쓰지 않음) | 빌드 때만 |
| `VWORLD_API_KEY_DEV`, `VWORLD_DEV_DOMAIN` | 로컬 개발 서버(localhost:3000)용 브이월드 키·서비스 URL | 넣지 않음 | 로컬 선택 |
| `PROPEDIA_LIVE` | `0`이면 실시간 조회를 끈다 (pytest·오프라인 평가가 자동 설정) | 넣지 않음 | – |

- 같은 키를 서버와 브라우저에 함께 쓰면 서버용 키도 번들에 드러납니다. 브라우저용(`VITE_VWORLD_KEY`)은 서비스 URL 제한 키로 따로 발급하는 것을 권장합니다(HUMAN_TODO 29).
- `/api/v1/health`는 키마다 '있음/없음'만 알려 줍니다.

### 실시간 조회 구조

```
입력 → ① 시연 주소 일치 ② 지번 정규식 → PNU (네트워크 없음)
     → ③ 도로명주소 검색(juso, 실패하면 브이월드 검색) → PNU / 여러 건이면 후보 / 강남구 밖이면 안내
PNU → 토지 정보: 빌드 캐시(land_cache) → 메모리 캐시(1시간) → 브이월드 실시간(타임아웃 4초·재시도 1회)
    → 좌표(지오코더)로 주변 500m 판정 → 4개 층 배치 (필지 → 법정동 → 자치구 → 서울 전역 → 참고)
```
외부 호출은 `core/live/`에서만 합니다(`tests/test_no_network.py`가 검사). 실패하면 "토지 정보를 지금 불러오지 못했습니다" 같은 안내로 대신하고 화면은 깨지지 않습니다.

단계별 점검: `python -m pipeline.check P1|P2|P3`

## 실행·테스트

- 로컬 실행: `run_demo.bat` 더블클릭 (가상환경이 없으면 만들고 `http://127.0.0.1:8000/`을 엽니다)
- 개발 중: `python -m uvicorn api.index:app --port 8000 --reload`
- 테스트: `pytest -q`
- 화면 점검 + 캡처: `python tests/ui_check.py` (배포본은 `--base https://….vercel.app`)
- 화면 메뉴는 **시작 · 주소 조회 · 문서 DB** 세 개입니다 (2026-10-26 동혁 결정). 검수(`review.html`)·평가(`eval.html`) 화면은 메뉴와 링크에서 뺐지만 파일과 API(`/api/v1/review-queue`, `/api/v1/eval`, POST `/api/v1/lookup`의 `decisions`)는 그대로 남아 있습니다. 주소 조회 화면은 검수 결정을 보내지 않고 GET으로만 조회합니다.

## 배포 (Vercel)

### 지도 화면 배포 절차 (P20)

1. **Preview**: `feat/map-console` 브랜치를 push하면 Vercel이 Preview 배포를 만듭니다. Preview 주소에서 확인 목록(PROGRESS.md P20-A)을 봅니다.
   - 브랜치의 마지막 커밋 작성자는 저장소 주인 noreply(`232514334+greekyogurt02@users.noreply.github.com`)여야 Hobby 플랜에서 배포가 막히지 않습니다(아래 1번 참고). `git config`는 바꾸지 않고 `--author`로 커밋합니다.
2. **Production**: 사람이 `main`을 `feat/map-console`로 **빨리감기 push** 합니다 (`git push origin feat/map-console:main`, 병합 커밋 없이). `main` push가 운영 배포를 만듭니다.
3. **되돌리기**: Vercel 대시보드 → Deployments → 직전 운영 배포 → **Instant Rollback** (다시 빌드하지 않고 바로 바뀝니다). 코드는 그다음 `git revert`로 맞춥니다.
4. 검색엔진 노출 막기: 모든 응답에 `X-Robots-Tag: noindex`(`vercel.json` `headers`), 지도 화면 `index.html`에 `<meta name="robots" content="noindex">`.

### 처음 설정 (2026-10, 완료)

1. GitHub 비공개 저장소에 push (`gh repo create propedia-pretotype --private --source . --push`, 완료).
   - 이후 `git push`가 "Repository not found"로 실패하면 Windows 자격 증명 관리자에 다른 GitHub 계정이 저장된 것입니다. 전역 설정을 바꾸지 않고 `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push`로 올립니다.
   - push했는데 Vercel이 배포하지 않고 GitHub 커밋 상태에 "Git author … must have access to the project on Vercel"가 뜨면, 커밋 이메일이 저장소 주인(greekyogurt02)이 아닌 다른 GitHub 계정에 연결된 것입니다(Hobby 플랜은 프로젝트 주인이 작성한 커밋만 배포). `git -c user.email=232514334+greekyogurt02@users.noreply.github.com commit …`으로 커밋하거나 Vercel 화면에서 Redeploy합니다.
2. vercel.com → New Project → 저장소 Import → Framework 자동(FastAPI) → Deploy.
3. 확인: `curl -s https://<주소>/api/v1/health`, 화면 5개.
4. `/api/*`가 404면 루트에 `vercel.json` `{ "rewrites": [ { "source": "/api/(.*)", "destination": "/api/index" } ] }` 추가 후 재배포 (agents.md §15-3).

`.vercelignore`가 빌드 전용 파일(pipeline, seed, extractions, data_raw, tests, docs 등)을 뺍니다. `db/propedia.db`, `db/market.db`, `core/`, `api/`, `public/`, `requirements.txt`는 올라갑니다. Hobby 플랜은 운영 주소가 기본 공개이며 비상업·개인 용도 조건입니다.

### 실거래 DB(`db/market.db`) 갱신 규칙 (P17)

- `db/market.db`(약 14.5MB)는 **시연·배포 직전에만** 다시 빌드해 커밋합니다. 바이너리 파일이라 커밋할 때마다 저장소 이력이 그만큼 커지므로, 평소에는 로컬에서만 갱신하고 커밋하지 않습니다.
- 갱신 순서 (공공데이터포털 API, `.env`의 `DATA_GO_KR_SERVICE_KEY`):
  `python -m pipeline.fetch_trades` → `python -m pipeline.build_trade_complexes` → `python -m pipeline.build_market_db` → (기본 정보 API가 등록되면) `python -m pipeline.fetch_apt_basis` → `python -m pipeline.build_map_layers` → `python -m evals.run_eval`
- 커밋 전 확인: 개인 정보 성격 필드(buyerGbn·slerGbn·estateAgentSggNm) 0건, 키 문자열 0건, `PRAGMA freelist_count = 0`(VACUUM 상태).
- 배포본에 market.db가 없으면 실거래 API만 503이고 다른 기능은 그대로입니다.

- 마지막 실거래 수집일(`market.db` meta `fetched_on`)이 **7일 이내면 갱신하지 않습니다**. 넘었으면 위 순서대로 갱신하고 크기·M22·M23을 확인한 뒤 커밋 여부를 정합니다.

화면 캡처: [docs/screens/](docs/screens/) (`python tests/ui_check.py`, `tests/ui_check_map.py --shot`, `tests/demo_map_run.py`가 다시 만듭니다)

## 데이터·라이선스

| 데이터 | 원천 | 이용 조건 | 화면 표시 |
|---|---|---|---|
| 고시·공고 원문 (D1~D10) | 강남구·서울시·국토교통부 공개 문서 | 공공저작물(고시·공고는 저작권 보호 대상 아님) | 출처 줄(문서·쪽·기준일), 원문 쪽 이미지 |
| 배경지도·2D 데이터·토지 정보·WMS | 브이월드(국토교통부) | 공공누리 1유형(출처표시) | 오른쪽 아래 출처 |
| 서울시 도시계획사업 현황 (서울플랜+, 참고 레이어) | 서울 열린데이터광장 OA-22712 | **공공누리 4유형 (출처표시·상업적 이용금지·변경금지)** | '참고·비상업' 배지 + 출처, 좌표계 변환·선택만 |
| 의제처리구역 (참고 레이어) | 공공데이터포털 15082965 | **공공누리 4유형 (출처표시·상업적 이용금지·변경금지)** | '참고·비상업' 배지 + 출처 |
| 아파트 매매 실거래가 | 국토교통부 (공공데이터포털 15126468) | 이용허락범위 제한 없음 | 단지 인스펙터 출처, 개인 정보 성격 필드는 저장 안 함 |
| 학교 위치 | 전국초중등학교위치표준데이터 (15021148) | 이용허락범위 제한 없음 | 인스펙터 출처 |
| 지하철역·버스정류장·노선 | 서울 열린데이터광장 OA-21232·21231·21230·21233 | 공공누리 1유형(출처표시) | 인스펙터 출처 |
| 편의시설 6분류 | 소상공인시장진흥공단 상가(상권)정보 (15012005) | 이용허락범위 제한 없음 | 인스펙터 출처 |

참고 레이어 2종은 비상업 조건이므로, 서비스를 상업적으로 쓰기 전에 빼거나 이용 허락을 따로 받아야 합니다.

## 알려진 한계

- **압구정동 527은 도로명주소가 없는 필지**입니다(도로명주소 API 검색 결과 없음, 2026-10-26). 그래서 A2는 인접 528(한양아파트, 압구정로61길 37)의 도로명 입력으로 바꿨습니다. 건축물대장 표제부도 0건입니다.
- 좌표는 P10부터 브이월드 지오코더(지번 → 좌표)를 씁니다. 사업 중심은 대표 지번(527·619)의 지오코더 좌표입니다(이전의 OSM 근사값은 `build/project_anchors_osm.csv`에만 남김).
- 경계 데이터가 없어 포함 판정은 대표 지번(`possible`), 지도 대조 후보(`likely`, 대청마을 16필지 + 한양7차 528번지 1필지(D1 p18 결정도 대조)), 사람 검수(`included`)만 씁니다. 지도 대조는 D9 결정도와 연속지적도를 맞댄 결과이며, 결정도의 축척 막대가 실제와 달라(0.947 vs 0.79m/px) 지적도 선에 맞춘 값을 썼습니다.
- 토지 정보는 브이월드 원 자료를 그대로 보여주며 참고용입니다(토지이음과 같은 원천). 해석(가치·개발 가능 등)은 하지 않고, 소유자 정보는 쓰지 않습니다. 법정동 층 고시는 모은 문서가 있는 동(압구정동·일원동·대치동)에서만 나옵니다.
- 지역생활권 계획은 2018년판이며 압구정·청담 장만 반영했습니다. 4개 층에는 두지 않고 '참고'로만 보여줍니다. 이미지 쪽은 Claude Code가 전사했고 모두 검수 대상입니다.
- 규제 고시는 대상 기준과 효력 기간만 원문대로 보여주고, 개별 필지가 허가 대상인지는 판정하지 않습니다. 투기과열지구(D8)는 지정 공고문 대신 국토교통부 보도참고자료의 현황표입니다(HUMAN_TODO).
- 건축물 요약은 빌드 때 시연 주소의 필지만 조회했습니다. 다른 지번은 '조회하지 않았습니다'로 나옵니다.
- 재건축 단계 템플릿 문구(설명·법령 근거)는 법령 대조 전 초안이라 비어 있습니다(HUMAN_TODO 2).
- 정답셋 3개는 추출자와 같은 작성자의 초안이라 평가 수치가 낙관적입니다(HUMAN_TODO 1).
