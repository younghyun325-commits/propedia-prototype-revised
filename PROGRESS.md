# 진행 기록

## 작업 규칙
- 작업은 `feat/map-console`에서만 한다. `main` 병합은 P20에서 사람이 한다. (로컬 `.git/hooks/pre-commit`·`pre-push`가 main 커밋·push를 막음, 커밋되지 않는 로컬 훅)
- `origin/main`에는 2026-11-10까지 P13~P15가 실수로 먼저 올라가 있다(`c79cac0`). 되돌리지 않기로 결정. 운영 배포 영향은 HUMAN_TODO 45에서 확인.

현재 단계: P19 하단 타임라인·고시 피드 완료 (2026-11-11). 다음은 docs/map/PLAN.md P20 다듬기·테스트·배포

## P20-A 다듬기·테스트·문서·Preview 준비 — 완료 (2026-11-11) · main 병합·운영 배포는 사람이

범위: docs/map/PLAN.md P20 중 배포를 뺀 것. 브랜치 `feat/map-console`만. 시작 때 P19 커밋 4개 빨리감기 push(e13fbe7..3c13087).

### 0. 사전 점검
| 항목 | 결과 |
|---|---|
| `JUSO_CONFM_KEY`·`_ALT` | **없음** → check_keys·`run_eval --live` 재실행으로 HUMAN_TODO 39(양재대로55길 14 PNU)를 확인하지 못함 (M18은 브이월드 검색 경로로 20/20) |
| 공동주택 기본 정보(getAphusBassInfoV5) | `fetch_apt_basis --check-only` 단지 1개: **미등록**(SERVICE_KEY_IS_NOT_REGISTERED_ERROR) → 건너뜀, HUMAN_TODO 28 열림. 점검이 meta를 같은 값으로 다시 써 market.db 바이트가 바뀌어 `git checkout`으로 되돌림 |
| 서울플랜+ 새 판 | `data_raw/11.공간정보/서울플랜_사업현황_202609/` **없음** → 건너뜀 (HUMAN_TODO 41) |
| market.db | meta `fetched_on=2026-11-11` (7일 이내) → 갱신 안 함 |
| 커밋 작성자 `origin/main..feat/map-console` | 15커밋 모두 `younghyun325@g.skku.edu` (저장소 주인 noreply 아님) → 이번 마지막 커밋은 `--author` 저장소 주인 noreply |

### 1. 지도 경계가 없는 규제 선택
- API `/map/notices` regulations에 `scope_type`·`scope_ref`·`has_geometry` (D5 BJD 압구정동, D6·D7·D8 SIDO, 도형은 D10만).
- 화면 `web/src/map/scope.ts`: 도형 없는 규제를 고르면 BJD → 법정동 경계(`bjd.geojson`), SIDO·강남구 SGG → 구 경계를 선택 색 점선(`scope-highlight-line`)으로 강조하고 그 범위로 이동. 지도 위 라벨 '법정동 단위 표시 · 경계 확인 전' / '서울 전역 적용 · 지도 경계 없음', 인스펙터에도 같은 문구 + '지도에서 보기'. 선택을 풀면 강조·라벨이 사라짐.
- 피드·상단 칩·URL(`sel=regulation:D5`, `&t=2026-05-01`) 모두 같은 동작, D10은 기존 경계 그대로. 스크린샷 `map_08a_d5_bjd.png`, `map_08b_d6_gangnam.png`.

### 2. 성능
레이어 줌 범위 (지금 값):

| 레이어 | minzoom | maxzoom | 비고 |
|---|---|---|---|
| 배경 WMTS (소스) | 6 | 18 | 그 위는 확대 표시 |
| 참고 WMS 용도지역·지구단위계획 | 14 | 19 | 서버 프록시 |
| 참고 WMS 지적도 | 17 | 19 | 0.6m/px 조건 |
| 포함 판정 필지 (`propedia-parcel-hit/line/line-likely`) | 14 | – | |
| 버스정류장 아이콘 | 15 | – | 이름 17 |
| 학교 클러스터 | – | 15 | `CLUSTER_MAX_ZOOM + 1` |
| 사업·영향권·규제·아파트·법정동·참고 GeoJSON·역·편의시설 아이콘 | – | – | 제한 없음 (라벨만: 규제 14, 아파트·참고 15, 역 이름 13, 학교·편의시설 이름 16) |

- 제안(승인 전, 적용 안 함): 성능 94라 바꿀 필요는 크지 않음. 다만 `manifest.json` 아파트 항목의 `fill_min_zoom: 14`가 화면에는 적용돼 있지 않음 → ① 그 값을 지우거나 ② `apartments-fill/line`에 minzoom을 거는 것 중 택일.
- 좌표 소수 6자리: `tests/test_geojson_precision.py` (18개 파일, 좌표 1만 개 이상 읽음) 통과.
- 압축: 8000번 응답에 압축 없음(content-length만) → **로컬에만** `GZipMiddleware(minimum_size=1000)` (`fastapi.middleware.gzip`, `VERCEL != "1"`). 확인: `pois_academy.geojson` `content-encoding: gzip`. Vercel CDN 압축은 Preview 확인 목록.
- 청크 (`npm --prefix web run build`, gzip -9):

| 청크 | 원본 | gzip | 로드 |
|---|---:|---:|---|
| index | 316.4KB | 98.0KB | 초기 |
| useMapStore | 24.5KB | 9.8KB | 초기 |
| MapView (MapLibre 포함) | 1140.9KB | 308.5KB | 지연 (셸 다음) |
| d3-scale | 38.4KB | 13.8KB | 지연 |
| Inspector | 44.3KB | 11.5KB | 지연 |
| Timeline | 13.1KB | 5.1KB | 지연 |
| AptChart | 18.1KB | 4.7KB | 지연 |
| CommandPalette | 9.6KB | 3.8KB | 지연 |
| EvidenceModal | 8.9KB | 3.2KB | 지연 |
| ShortcutsModal (P20) | 2.5KB | 1.2KB | 지연 |
| 그 밖 8개 | 각 5KB 미만 | | 지연 |
| **초기 JS 합계** | | **107.8KB** | 예산 400KB |

- Lighthouse 12.8.2 데스크톱 (`http://127.0.0.1:8000/map/`, Playwright Chromium): **성능 94 · 접근성 100 · 권장사항 100** (FCP 0.9s, LCP 1.4s, TBT 40ms, CLS 0.003, SI 1.0s). 80 이상이라 추가 수정 없음.

### 3. 접근성·설정
- 상단 바 톱니 설정 메뉴: '투명도 줄이기'(switch, localStorage `propedia.map.reduceTransparency.v1`, try/catch — `state/prefs.ts`), '단축키 보기', '주소로 조회(기존 화면)' `/index.html`, '문서 DB' `/docs.html`. P11 임시 토글은 뺌.
- `?` 키 단축키 도움말(`ui/ShortcutsModal.tsx`): Ctrl+K·L·I·T·Esc·?·←/→·Shift+←/→·Home 9줄, 포커스 가두기, Esc는 도움말만 닫음(선택 유지), 닫으면 연 요소로 포커스 복귀.
- `prefers-reduced-motion`: 지도 fitBounds·easeTo 0ms, flyTo → jumpTo (`ui/motion.ts`), 패널 전환은 기존 glass.css 규칙.
- 키보드 점검표 (ui_check_map P20):

| 확인 | 결과 |
|---|---|
| Tab 순서: 지도 컨트롤(3D·반경) → 작업 탭 → 검색 → 고시 칩 → 설정 → 좌측 탭 → 겹침 보기 | 통과 |
| 포커스 링: Tab으로 지나간 14칸 모두 외곽선 | 통과 |
| 단축키 도움말: 포커스 가두기(Tab 6회 모두 모달 안)·Esc·설정 버튼으로 복귀 | 통과 |
| 원문 모달: 가두기·Esc·연 버튼 복귀 (P16 점검) | 통과 |
| DEMO_MAP 순서: Ctrl+K 검색 → 사업 카드 Enter → 인스펙터 탭 ←/→ → T 타임라인 ←/→·Shift+←/→·Home → Esc | 키로 모두 가능 (마우스가 필요한 곳: 지도 빈 곳 클릭 조회, 반경 보기 지점 고르기) |

- axe-core 4.10.3 (`tests/axe_map.py`, `build/axe/`에 설치, 의존성 추가 없음), 9개 상태 — 첫 화면·사업 인스펙터·원문 모달·D5 범위 표시·흐려진 규제 라벨(기준일 2026-03-01)·단축키 도움말·투명도 줄이기·1180px·390px: **serious·critical 0건, 그 밖 0건**. 처음 돌렸을 때 고친 것: 하단 시트 tablist 안의 높이 버튼(critical aria-required-children) → tablist 밖 group으로, 지도 영역 `role=region`, 안내 줄 `aside`, 로딩 자리 `aria-hidden`.

### 4. 반응형 (`ui/useViewport.ts`, html `data-viewport`)
- 1280px 이상 그대로 / 1024~1279px: 좌측 패널 기본 접힘 → 아이콘 줄(`panel/IconRail.tsx`, 누르면 그 탭으로 펼침, 패널의 접기 버튼), 인스펙터는 고른 것이 있을 때만 지도 위에 겹쳐 뜨고 닫기 버튼 강조, 타임라인 그대로.
- 1024px 미만: 보기 전용. 상단 바는 작업 탭·고시 칩을 빼고 검색 아이콘만, 안내 '큰 화면에서 모든 기능을 쓸 수 있습니다'. 좌측 패널·인스펙터·타임라인은 하단 시트(`ui/BottomSheet.tsx`, 접힘·절반·전체, 손잡이·높이 버튼) 탭. 반경 보기·스크러버·커서 표시줄 숨김. 대상을 고르면 시트가 '정보' 절반으로.
- 스크린샷 `map_08c_1440.png`, `map_08d_1180.png`, `map_08e_390.png`. 3폭 모두 가로 스크롤 없음.

### 5. 첫 화면·기존 화면
- `vercel.json` `redirects: [{"source": "/", "destination": "/map/", "permanent": false}]` (Vercel 문서: permanent false = 307), `headers` `/(.*)` → `X-Robots-Tag: noindex`. 지도 `web/index.html` `<meta name="robots" content="noindex">`.
- `api/index.py`: `/` → `/map/` 307을 Vercel·로컬 모두 등록 (예전 Vercel 전용 `/` → `/index.html`은 바뀜). 기존 `/index.html`·`/lookup.html`·`/docs.html` 200 (`tests/test_api.py`).
- `tests/ui_check.py`는 이미 `/index.html`로 시작하고 있어 바꿀 것이 없었음 (기대값 그대로).
- 8000번 reload 때 옛 worker가 계속 응답해 `/`가 200으로 남은 적 있음 → 서버를 끄고 남은 python 프로세스가 없는지 확인한 뒤 다시 띄움.

### 6. 보안·키 점검 (`python -m pipeline.check_secrets`, 값은 출력 안 함)
| 변수 이름 | public/map 건수 | git 파일 건수 | 판정 |
|---|---:|---:|---|
| VITE_VWORLD_KEY | 1 | 0 | 통과 (브라우저 배경지도, 정상) |
| VWORLD_API_KEY | 1 | 0 | 통과 — **값이 VITE_VWORLD_KEY와 같음** |
| VWORLD_API_KEY_DEV | 1 | 0 | 통과 — **값이 VITE_VWORLD_KEY와 같음** |
| DATA_GO_KR_SERVICE_KEY | 0 | 0 | 통과 |
| JUSO_CONFM_KEY·_ALT | 값 없음 | | |
| DATA_GO_KR_*_URL, VWORLD_DOMAIN, VWORLD_DEV_DOMAIN | 0 | 1~13 | 공개 주소 (참고) |

- 브이월드 키 3개가 같은 값이라 서버용 키도 번들에 드러남 → 브라우저 전용 서비스 URL 제한 키 분리 (HUMAN_TODO 51, 운영 배포 전).
- `/api/v1/health` `keys`: `{"vworld": "있음", "juso": "없음"}`만. WMS 프록시 허용 목록 테스트 16 통과.
- README: Vercel 환경변수 표(이름·용도·환경·필수), `DATA_GO_KR_SERVICE_KEY`는 로컬 빌드용이라 Vercel에 넣지 않음.

### 7. 문서
README(지도 화면·로컬 실행 2터미널·지도 빌드 순서·market.db 7일 규칙·환경변수 표·배포 절차·Instant Rollback·데이터 라이선스 표), `DEMO_MAP.md` 8장면 대본(누를 곳·기대 화면·말할 것·안 될 때, 목표 4:55, 넘치면 4·6 예비), `tests/demo_map_run.py`, HUMAN_TODO 정리(닫힘 15 / 운영 배포 전 9 / 배포 후 26, 새 51·52), PLAN.md P20 체크(배포 제외), agents.md §21.

### 8. 회귀
| 점검 | 결과 |
|---|---|
| `pytest -q` | 312 통과 |
| `npm --prefix web run test` | 13파일 156 통과 |
| `npm --prefix web run build` | 성공 (MapView 청크 500KB 경고는 기존과 같음) |
| `python -m evals.run_eval` | M1~M24 모두 통과, 오류 0 |
| `python -m evals.run_eval --live` | M18 100% (20/20, p95 279ms) · M21 100% (5/5, p95 233ms) |
| `tests/ui_check.py` (기존 화면, `/index.html`) | 50/50 |
| `tests/ui_check_map.py --shot` (3000) | 188/188 (P20 항목 포함: 범위 표시·설정·도움말·Tab·움직임 줄이기·반응형 3폭·`/` 307) |
| `tests/ui_check_map.py --built` (8000) | 188/188 |
| `tests/axe_map.py` | serious·critical 0 (9개 상태) |
| `tests/demo_map_run.py` | 8장면 통과, 화면 동작 18.1초, 페이지 오류 0 |

장면별 화면 동작 시간: 1 2.3초 · 2 0.6초 · 3 2.4초 · 4 2.5초 · 5 2.9초 · 6 1.5초 · 7 2.7초 · 8 3.2초 (말하는 시간 제외).

### Preview 확인 목록 (push 뒤 사람이, HUMAN_TODO 52)
| 주소 | 기대 결과 |
|---|---|
| `curl -sI <Preview>/` | 307, `location: /map/` |
| `<Preview>/map/` | 지도·배경 타일 (Preview 주소가 `VITE_VWORLD_KEY` 서비스 URL에 없으면 타일 차단 — HUMAN_TODO 34) |
| `curl -sI <Preview>/map/` | `x-robots-tag: noindex` |
| `curl -sI -H "Accept-Encoding: gzip, br" <Preview>/data/layers/pois_academy.geojson` | `content-encoding: br` 또는 `gzip` (CDN 압축) |
| `<Preview>/index.html`, `/lookup.html?addr=A1`, `/docs.html?doc=D1` | 기존 화면 정상 |
| `<Preview>/map/?sel=regulation:D5` | 압구정동 점선 강조 + '법정동 단위 표시 · 경계 확인 전' |
| `<Preview>/map/?sel=regulation:D6` | 강남구 전체 + '서울 전역 적용 · 지도 경계 없음' |
| `<Preview>/map/?t=2026-05-01&sel=project:2` | 한양7차 숨김, 대청마을 '공람 중' D-day |
| `<Preview>/api/v1/health` | 200, keys는 있음/없음만 |
| `<Preview>/api/v1/apartments/apt:11680-218` | 200 (은마, market.db) |
| `<Preview>/api/v1/map/wms/lt_c_uq111/14/13974/6348.png` 두 번 | 두 번째 `x-vercel-cache: HIT` |
| 폭 390px (휴대폰) | 하단 시트·안내 줄, 가로 스크롤 없음 |
| 톱니 → 투명도 줄이기 → 새로고침 | 유지 |

남은 문제: 줌 범위 제안(아파트 `fill_min_zoom`) 결정 필요, 브라우저 키 분리(51), Preview 확인(52), 도로명주소 키(39), 기본 정보 API(28).

## P19 하단 타임라인·고시 피드 (+ 편의시설 선택 수정) — 완료 (2026-11-11)

### 0. 정리 (커밋 d5c3853 `P19-0`)
- 학교 이용허락범위 '제한 없음'(2026-11-11 영현 확인) → `pipeline/fetch_pois.py` license·license_note, 다시 실행 sha256 같음. PLAN 카탈로그·출처, HUMAN_TODO 49 닫음
- `vercel.json` `excludeFiles` = `{web/**,public/pages/**}` (로컬 원문 보기 모달 이미지 확인). HUMAN_TODO 48에 'Preview 원문 보기 이미지 200·함수 크기 기록'
- 정류장 300m 검증: '{역}역'으로 시작하고 바로 뒤가 끝·공백·'.'·'·'·'('·숫자일 때만 짝지음(부분 문자열 안 씀) → 150곳 중 21곳 초과. HUMAN_TODO 50 새 목록. 좌표는 그대로

### 1. 편의시설 분류별·하위 분류별 선택 (커밋 d6c7aea `P19-1`, P18 보완)
- 원인: 켜기 키가 `layers.pois.visible` 하나 + 숨김 목록(`poiHidden`, 기본 빈 배열)이라 켜는 순간 6분류가 모두 보였고, 소스·레이어도 하나(`infra-pois`)라 하위 분류를 바꿀 때 걸러서 `setData`로 클러스터를 다시 계산했다
- 고친 구조: 분류마다 소스 `infra-poi-{분류}`·레이어 `poi-{분류}`(·`-cluster`·`-selected`). 하위 분류는 `clusterProperties`(n_{하위}) + `setFilter`만 — 낱점은 `sub_category`, 클러스터는 '켠 하위 분류 합 > 0', 개수 마커도 그 합. 분류 key `clinic` → `medical`
- 패널 3단 체크박스(실제 input, indeterminate, aria-checked=mixed), '이것만 보기'(버튼·Alt+클릭), 건수는 manifest. URL `?poi=supermarket,medical:dental+oriental,academy:language`(layers의 pois·ph 없앰)
- 반경 보기 꺼진 분류 흐리게 + '지도에서 꺼짐', 이름 클릭 = 이것만 보기. 범례는 켠 분류만
- 성능: 6분류 켠 채 하위 분류 20회 — setData·setStyle 0, setFilter만, 프레임 p95 16.8ms. 스크린샷 `map_06f_poi_before`·`06g_poi_convenience_only`·`06h_poi_dental`

### 2~3. '그날 기준' 판정·API (`core/map.py`, `api/index.py`)
- [x] `state_at(con, as_of)`: 문서 발행 여부, 사업 표시(첫 근거 문서 발행일 이후) + `progress(today=as_of)` 단계·기한·상태 배지, 규제 효력(`timeutil.effective` → 효력 중·효력 전·종료), 상단 칩. 날짜 계산은 `core/timeutil.py` 그대로(짧은 라벨 `EFFECTIVE_SHORT_LABELS`만 추가)
- [x] `/map/projects`·`/map/notices`(+ `regulations` 효력 상태)·`/map/feature`(숨긴 사업은 이름·안내만, 규제 `published`·`status`, 근거 문서는 발행된 것만)·`/timeline`·`/feed`가 모두 `state_at`을 씀
- [x] `/api/v1/timeline?from=&to=` 계열 5개(발행 10·공람 2·효력 4·단계 2·자료 기준일 13), `/api/v1/feed?limit=&as_of=`, `/apartments/{id}/trades?as_of=`(계약일 ≤ 기준일, 그 달은 원자료로 다시 셈 — 빌드와 같은 규칙). 잘못된 날짜 400 + 한국어
- 날짜별 기대값 (pytest `tests/test_timeline.py`):

| 기준일 | 한양7차 | 대청마을 | 규제·칩 |
|---|---|---|---|
| 2026-03-31 | 숨김 | 숨김 | D10 효력 전 · 칩 D6·D7 |
| 2026-04-01 | 숨김 | 숨김 | D10 효력 중 |
| 2026-05-01 | 숨김 (첫 근거 D1 2026-10-06) | 공람 중 · D-day | D5·D10 효력 중 |
| 2026-05-02 | 숨김 | 공람 마감 · 마감(2026.05.01) | |
| 2026-10-08 | 공람 중 · D-29 | 공람 마감 · 마감(2026.05.01) | 칩 D6·D7·D8 |
| 2026-11-10 | 공람 마감 · 마감(2026.11.06) | 공람 마감 · 마감(2026.05.01) | |
| 2027-01-01 | 공람 마감 | 공람 마감 | D6 종료 → 칩에서 빠짐 (D7·D8) |

### 4~7. 화면 (`web/src/`)
- [x] store `asOf`(null = 오늘) ↔ URL `?t=YYYY-MM-DD`(잘못된 날짜 무시). 조회 훅이 asOf를 쿼리 키·`as_of`에 넣고 받는 동안 이전 값 유지. `state/dates.ts`(오늘 KST·날짜 더하기)
- [x] 지도: 숨긴 사업은 사업·영향권·필지 레이어 `setFilter`(`['!', ['in', …]]`), 효력 중이 아닌 규제는 투명도 식 25% + 라벨 '· 효력 전/종료'. 스타일·소스 다시 만들지 않음
- [x] 상단 바 '기준일 2026-05-01 · 지난 시점 보기'(미래 '다른 날짜 보기')·'오늘로'·아래 가장자리 브랜드 색 띠
- [x] 하단 타임라인(지연 청크): 접힘 44px(기준일·◀ ▶·펼치기, T) / 펼침 200px(계열 5줄 + 단지 선택 때 거래량, 휠 확대·끌어서 이동·전체 보기·기본 범위, 오늘 선·스크러버, 호버·클릭, 재생 1·2·4배, ←/→·Shift·Home, aria-live). 같은 줄 겹침은 위아래로 비킴
- [x] 고시 피드 탭: 종류 배지·제목·발행일·관련 사업·규제·기한·출처 줄·'최근 30일', 누르면 지도 이동 + 인스펙터 (이동 요청 `{type: 'feature', id}` — 지도에 불러온 도형 범위)
- [x] 인스펙터: 숨긴 사업 안내, 미발행 규제 안내, 규제 기간 막대 '기준일' 선, 필지 클릭 조회 '오늘 기준 자료'. 실거래 차트 기준일 세로선·뒤 구간 비움
- [x] 바뀌지 않는 레이어(생활 인프라·공식 참고·아파트) 행에 '자료 기준 YYYY-MM, 날짜와 함께 바뀌지 않음'. 문구는 `web/src/copy/ui.ts`(금지어 검사 대상, '예정' 없음 — 미래 날짜도 '공람 마감일 …')

### 고친 것
- 8000번 API가 `--reload`인데 새 경로가 404: 예전 worker의 multiprocessing 자식(24664)이 소켓을 물고 남아 요청을 받고 있었음 → 그 프로세스를 끄고 같은 명령으로 다시 띄움
- 날짜 필터를 스타일에 넣을 때 필터 없는 레이어에 `filter: undefined`가 들어가 setStyle 검사 오류(편의시설을 켜면 레이어가 안 생김) → 있을 때만 넣음
- P16 테스트 `test_as_of_dates`의 2026-05-01 한양7차 기한 기대값 → P19 규칙대로 '숨김'으로 바꿈. `test_no_network` 허용 목록에 표준 라이브러리 `statistics`

### 확인
- pytest -q: **306 passed** (새 `tests/test_timeline.py` 49개)
- npm --prefix web run test: **151 passed** (새 `web/src/timeline/timeline.test.ts`) · build: 초기 JS `index` **98.04 kB gzip**, 타임라인 지연 청크 5.28 kB gzip(+ d3-scale 14.33 kB, 실거래 차트와 공유)
- python -m evals.run_eval: M1~M24 직전과 같음 (M10만 7→6ms), 오류 0
- ui_check_map: 개발 서버(3000) **152/152**, 빌드본(8000) **152/152**, 콘솔 오류 0. P19 점검 14개(원문 모달 이미지 포함) + P19-1 9개 · `--perf`: 편의시설 하위 분류 20회 setFilter만, p95 16.8ms
- 스크린샷: `map_06f_poi_before`·`06g_poi_convenience_only`·`06h_poi_dental`·`07a_timeline`·`07b_2026-05-01`·`07c_feed`·`07d_trades_asof`


## P18 생활 인프라 — 완료 (2026-11-11)
결정(영현): D1 분류표 확정(슈퍼마켓·편의점·병원·의원·약국·카페·학원, 하위 분류) · D2 정류장 좌표는 원자료 WGS84 그대로, 검증은 '역 이름이 들어간 정류장 ↔ 역 300m' · D3 노선 연결은 서울 정류장 마스터에 있는 정류장만 · D4 가상정류장·선착장 제외 · D5 역 합치기(괄호 뺀 이름 + 300m, 위치 = 호선 가장 많은 행) · D6 라이선스 직접 확인

### 0. push·Vercel (커밋 c1a6f7a `P18-0`)
- 5커밋 push(빨리감기 1a50069..a1fd19c), `vercel.json` `functions["api/index.py"].excludeFiles = "web/**"` (공식 문서: Python 함수는 빌드 때 닿는 파일을 모두 묶음, 한도 500MB). `public/pages/**`·`public/map/**`는 런타임이 파일로 읽지 않아 뺄 수 있음 — 제시만(HUMAN_TODO 48)
- 확인: pytest 239 · ui_check_map --built 111/111 · push c1a6f7a

### 1. 원천 확인 (커밋 a1fd19c `P18-1`)
- [x] `market.db` 커밋(3c8fc3a) — 개인 정보 성격 필드 0·키 0·freelist 0·41,566건. 갱신 규칙 README·PLAN(947ff44)
- [x] `.gitignore`에 `data_raw/12.생활인프라/`, `pipeline/check_infra_api.py`(상가 API 155회)

### 2. 수집·빌드 `pipeline/fetch_pois.py`
- [x] 상가: 첫 실행 67회 호출 40.8초(66,722건 = totalCount), 두 번째부터 캐시 0회. 분류표 업종만 9,895건(제외 '분류표에 없는 업종' 56,827)
- [x] 학교 79(초 34·중 24·고 21, 운영 아닌 학교 0) · 지하철역 31(경계+500m 44행 − 같은 역 다른 호선·이름 행 합침 13, 합친 역: 삼성 = 삼성 + 삼성(무역센터) 8m, 300m 넘어 안 합친 같은 이름 없음)
- [x] 버스정류장 609 = 경계+100m 625 − 가상정류장 15 − 선착장 1. 이름 453개(같은 이름 2곳 이상 135개), ARS 중복 0. 유형: 일반차로 438·마을버스 106·가로변시간 32·가로변전일 21·중앙차로 12
- [x] 노선: 288개(경기 151·간선 46·지선 30·마을 21·인천 16·공항 10·광역 8·유형 빈 값 6). 노선-정류장 88,811행 중 서울 정류장 마스터에 없는 정류장 43,300행 버림 → 전체 연결률 51.2%(45,511/88,811), 강남구 정류장 연결률 99.7%(607/609, 노선 없음: 역삼역 23811·강남관광정보센터 23910)
- [x] 정류장 300m 검증(D2): 173곳 중 143곳 300m 안, 30곳 초과(긴 역·출구 위치, 오매칭 1곳) — HUMAN_TODO 50. pytest로 강남역·선릉역·삼성역 관련 6곳 고정
- [x] 크기: 학교 32KB · 역 12KB · 정류장 348KB · 노선 62KB · 편의시설 6개 파일 합 4.45MB(1MB 초과라 분류별로 나눔: 학원 1.40MB·병원·의원 1.38MB·카페 0.90MB·편의점 0.36MB·약국 0.23MB·슈퍼마켓 0.18MB). 정류장·노선·편의시설은 켤 때(반경 보기·검색·선택 때) 불러옴
- [x] 두 번 실행 sha256 같음 (manifest 포함), 라이선스: 서울시 마스터 4종(OA-21230·21231·21232·21233) 공공누리 1유형, 상가 제한 없음, 학교 확인 필요(HUMAN_TODO 49)
- [x] M24 생활 인프라 건수 일치: 학교·지하철역·버스정류장·편의시설 4종 100% (+ 참고: 버스 노선 연결률 51.2% / 99.7%)

### 3~5. 지도·인스펙터·반경 보기 (`web/src/infra/`)
- [x] '생활 인프라' 그룹 ready, 학교·역 기본 켜짐(URL 기본값 같음), 흰 원형 칩 + lucide 아이콘(잉크 한 색), 클러스터 개수·이름은 HTML 마커(글꼴 없음)
- [x] 편의시설 6분류 행 + 병원·의원·학원 하위 분류 행(URL `ph`), 정류장 '줌 15 이상에서 표시', 슈퍼마켓 툴팁에 대형마트 note
- [x] 노선 선택 모드(`?route=`), 반경 보기(`?r=`, 250·500m, 경계 포함), 인스펙터 PoiView, Ctrl+K 역·학교/정류장 번호/노선, 겹침 보기 4종, 히트 반경 12·8px
- [x] 고친 것: 데이터가 늦게 와 스타일을 다시 만드는 중에 바뀐 상태(클릭 필지 강조)를 건너뛰던 문제 — 건너뛴 적용을 기억했다가 idle 때 다시 건다(새로고침 4/4). 검색 후보 같은 키 경고(같은 필지 다른 도로명) — 순번을 키에 넣음

### 확인
- pytest -q: **256 passed** (새 `tests/test_pois.py` 17개, 네트워크 없음)
- npm --prefix web run test: **114 passed** (새 `web/src/infra/infra.test.ts` 20개) · build: 초기 JS `index` **102.58 kB gzip**(전 97.21), MapView 지연 청크 317.4 kB gzip
- python -m evals.run_eval: M1~M23 직전과 같음(M10 응답 시간만 7→8ms) + M24 통과, 오류 0
- ui_check_map: 개발 서버(3000) **130/130**, 빌드본(8000) **131/131**(+ 성능), 콘솔 오류 0. P18 점검 19개 + P14 '준비 중 레이어' 점검을 '생활 인프라 4종 활성'으로 바꿈
- 성능(GPU, RTX 5060 D3D11): 정류장·편의시설 모두 켬 평균 16.9ms·p95 16.8ms·33ms 초과 3/473 프레임, 생활 인프라 끔 평균 16.6ms·p95 16.7ms → 줌별 표시 범위 조정 필요 없음. 헤드리스 기본(SwiftShader 소프트웨어 GL)은 생활 인프라를 꺼도 평균 40.8ms라 GPU 브라우저로 잼
- 스크린샷: `docs/screens/map_06a_poi.png`·`map_06b_radius.png`·`map_06c_station.png`·`map_06d_bus_stops.png`·`map_06e_bus_route.png` (기존 map_02~05도 학교·역 기본 켜짐으로 다시 찍힘)

## P17 아파트 단지·실거래 — 완료 (2026-11-11)
강남구 아파트 단지를 지도에 올리고, 누르면 실거래가 이력(국토교통부 신고 자료, 계약일 기준)을 보여 준다. **단지의 기준은 '실거래 단지'**(영현 결정): 실거래 응답의 aptSeq와 신고 지번 PNU로 단지를 만들고, 공동주택 단지 목록(236)·기본 정보는 덧붙이는 정보. 기본 정보 API(15058453)는 키 미등록이라 건너뜀(HUMAN_TODO 28 다시 열림).

### 0. 정리 (커밋 65e53ad `P17-0`)
- `git fetch --prune origin` → HEAD = origin/feat/map-console (1a50069) 확인 후 0단계 변경(MapView·geo·테스트)·`pipeline/check_market_api.py`·견본 커밋. 견본의 개인 정보 성격 필드(buyerGbn·slerGbn·estateAgentSggNm)는 '견본' 값 대신 **아예 뺌**(규칙: fixtures에 넣지 않음) — 저장한 원 응답으로 오프라인 재생성. 키 4종 미포함 검사 0건. push 안 함

### 2. 실거래 수집
- **2-0 옛 자료 형식** (`python -m pipeline.fetch_trades --probe`, 각 1쪽):

  | 월 | 건수 | aptSeq | umdCd | landCd | bonbun | bubun | cdealType | cdealDay | rgstDate | dealingGbn |
  |---|---|---|---|---|---|---|---|---|---|---|
  | 201601 | 277 | 0% 빈 | 0% | 0% | 0% | 0% | 100% 빈 | 100% 빈 | 100% 빈 | 100% 빈 |
  | 201901 | 74 | 0% 빈 | 0% | 0% | 0% | 0% | 100% 빈 | 100% 빈 | 100% 빈 | 100% 빈 |
  | 202201 | 62 | 0% 빈 | 0% | 0% | 0% | 0% | 92% 빈 | 92% 빈 | 100% 빈 | 0% |
  | 202401 | 195 | 0% 빈 | 0% | 0% | 0% | 0% | 94% 빈 | 94% 빈 | 6% 빈 | 0% |

  aptSeq·PNU 재료는 모든 기간에 있음 → `pnu:` 단지 키는 쓰이지 않음(코드는 둠). 해제·등기·거래유형은 2021년 무렵부터 채워짐
- `pipeline/rtms_parse.py`(순수 함수): 금액 쉼표 → 만원 정수, 계약일, 해제 'O' + 두 자리 연도 해제일(20YY), 등기일, PNU 자리 수 검사(사유), 음수 층, 면적 소수 2자리, `raw_hash` = 저장 필드 고정 순서 sha256. 같은 달 응답 안에서 저장 필드가 모두 같은 레코드 168건(2016~2026, 2021년 전 동 표기 없음 등)은 서로 다른 거래로 보고 `#n` 순번을 해시에 붙여 모두 저장(다른 달에 다시 나온 같은 레코드는 0건)
- `pipeline/fetch_trades.py`: 2016-01~2026-11 **131개월 · 133쪽 · 41,566건 · 해제 1,167건**, 첫 실행 호출 128회(체크포인트 시험 5회 뒤) · 호출 7.7초 · 전체 35초. 두 번째 실행은 최근 2개월만 다시 받음(호출 2회). `--max-calls`로 멈추면 체크포인트 저장 + 종료 코드 2 + '내일 이어서 실행' 안내 확인. 원 응답 `build/rtms_raw/`, 리포트 `build/trades_report.csv`(월별 건수·해제·호출)

### 3. 실거래 단지와 위치 (`pipeline/build_trade_complexes.py`)
- 단지 **697개** (aptSeq 697 · pnu: 0), PNU 2개 이상인 단지 **0개** — 이 API는 단지(aptSeq)마다 신고 지번 하나만 보냄(은마도 대치동 316 하나)
- 신고 지번 필지 경계(LP_PA_CBND_BUBUN) 합집합 → 대표점(지오코더 아님): **685/697 위치 찾음**, 못 찾음 12(전부 '필지 없음' — 개포주공 2·3·4단지 등, 신고 지번이 지금 연속지적도에 없음, HUMAN_TODO 47). 브이월드 요청 680회 40초(시간 초과 1건은 재실행 때 받음), 두 번째 실행 0회·sha256 같음(`616c5c39…`)
- `seed/apartments.geojson` 0.57MB → `build_map_layers`가 `public/data/layers/apartments.geojson`(685개, 0.63MB — 1.5MB 미만이라 점·면 분리 안 함) + `within_impact`(대표점, 기존 규칙)·`impacts`(면이 걸친 영향권, 사업별 최소 거리). 영향권 안 55개(250m 14 · 500m 41), 밖 630. 기존 propedia_* 레이어 바이트 같음

### 4. market.db (`db/market_schema.sql`, `pipeline/build_market_db.py`)
- `apt_complexes` 697 · `apt_trades` 41,566 · `apt_trade_monthly` 21,453행. 연결 aptSeq 41,566 · PNU 0 · 단지명 0 · 못 이음 0
- 검사: 월별 count 합 40,399 = 해제 제외 원자료 40,399 · raw_hash 중복 0 · 해제 1,167 = 원자료 1,167
- **db/market.db 14.54MB** (VACUUM 후, 20MB 미만). 재빌드 sha256 같음(`09dd05fb…`), 기본 정보 열·meta(list_total 등)는 재빌드 때 보존. **커밋하지 않음 — 사람 결정 대기(HUMAN_TODO 48)**
- **M22 98.3% (685/697)**, **M23 98.0% (40,745/41,566)** — 못 이은 거래 821건은 모두 '연결된 단지의 위치 없음'(위 12개 단지)

### 5. 기본 정보 (`pipeline/fetch_apt_basis.py`)
- `getAphusBassInfoV5` 1회 → `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` → **미등록으로 건너뜀**. basis_info_status 전부 pending, meta `list_total=236`·`basis_info_check=not_registered`, HUMAN_TODO 28 다시 열림(이전 문구 유지). 참고 수치 '기본 정보 연결 0 / 236'
- 등록 뒤 쓸 연결 단계(목록 236 → 지번 → PNU → 단지, 안 되면 법정동 + 정규화 단지명, 목록 밖 실거래 단지는 not_in_list)는 구현·순수 함수 테스트만. 응답 필드 이름은 확인 전이라 `FIELD_MAP`을 비워 두고, 비어 있으면 DB를 바꾸지 않음

### 6. API (`core/market.py`, `core/db.connect_market_ro`)
- `GET /api/v1/apartments/{id}`(기본 정보 또는 '기본 정보 확인 전'/'공동주택 기본 정보 목록에 없음', 준공연도 = 실거래 신고 기준, 면적대별 최근 12개월·3년 건수·마지막 거래일, 걸친 영향권, 출처), `/apartments/{id}/trades?band=&from=`(월별 중위값·건수, 개별 거래 점, 최근 20건), `/map/feature/apartment/{id}`(인스펙터 공통 틀). market.db 없으면 503 + 한국어 안내(다른 기능 정상). p95 **약 30ms**(로컬 20회)
- `/map/manifest`: apartments 레이어 ready + `market`(기간·건수·해제·수집일·M22·M23·기본 정보 연결/236). `/map/feature/project/{id}`에 `nearby_apartments`(250·500, 이름·준공연도·최근 거래일만)
- 면적대(Propedia 표시 구간): ~60 / 60~85 / 85~102 / 102~135 / 135~ ㎡, 하한 포함·상한 미포함(60.00 → 60~85)

### 7. 화면 (`web/src`)
- 레이어 '아파트 단지'(시장 그룹, 기본 꺼짐, 켤 때 한 번 불러옴): 면 28% + 외곽선 1px(`--color-layer-apartment`), 라벨 줌 15 이상(화면 안 단지만), 범례 '실거래 신고 단지 기준 · 단지 경계는 …'. 겹침 보기 대상(영향권 밖 25%)
- 클릭 우선순위: 사업 구역 → 규제 구역 → 사업 필지 → 아파트 단지 → (P18) → 빈 곳 필지 조회. 선택 `sel=apt:11680-218`
- `inspector/ApartmentView` + `inspector/AptChart`(따로 불러오는 청크, d3-scale·d3-shape SVG): 위 = 월별 중위 거래가 선 + 개별 거래 점(해제 = 빈 원), 아래 = 월별 거래 건수 막대, 같은 x축·위아래 분리. 면적대 칩(최근 3년 최다가 기본), 최근 거래 20건 표(계약일·전용면적·층·금액·거래 유형·해제(해제일)·동), 영향권 안 사업 + 이동, 출처 줄 '실거래가(국토교통부 신고 자료, 계약일 기준) · 수집일'. 금액 표기 `market/format.ts` (319000 → '31억 9,000만', 50000 → '5억')
- 사업 인스펙터 '영향권 안 단지' 탭(250m·500m, 이름·준공연도·최근 거래일, 행 → 그 단지 선택). 데이터 상태 탭에 실거래·아파트 단지 행
- 검색(Ctrl+K) '단지' 그룹: 단지명·다른 이름·신고 지번 부분 일치. 그룹 순서는 사업 → 주소 → 단지(지번 입력이면 Enter = 주소 — 기존 '압구정동 528' 점검 유지)
- 문구는 모두 `copy/ui.ts`. 금지어에 시세·상승·하락·저평가·고평가 추가(`tests/test_wording.py`, web/src + 실거래 API 문구)

### 완료 확인 (2026-11-11)
- `pytest -q` **239 passed** (전 198 → `test_rtms_parse.py` 10, `test_market.py` 30, wording 실거래 1)
- `npm --prefix web run test` **94 passed** (`market/market.test.ts` 금액 표기·면적대 기본·기본 정보 문구·차트 스케일·단지 검색)
- `npm --prefix web run build`: 초기 JS `index` **97.21 kB gzip**(전 95.76), `AptChart` 42.8 kB(14.2 kB gzip) 따로 나뉜 청크
- `python -m evals.run_eval`: M1~M20 직전과 같음(M10 시간만), **M22 98% (685/697)**, **M23 98% (40,745/41,566)** 통과, 오류 0
- `tests/ui_check_map.py --shot`(3000) **111/111**, `--built`(8000) **111/111**, 콘솔 오류 0. P17 점검 18개(레이어 켤 때 1번 불러옴·면 28%·범례, 라벨 줌 15, 은마 클릭 → '기본 정보 확인 전'·1979년(실거래 신고 기준)·차트 두 개 위아래·20건 표·출처, 면적대 기본 60~85, 해제 표시(표 '해제 (2026.11.03)' + 빈 원), 칩 전환, 겹침 보기 28%/7%, Ctrl+K '은마', 한양7차 '영향권 안 단지' 47행·행 → 단지 선택, 데이터 상태 M22·M23·0/236). P14 '준비 중 레이어'·데이터 상태, P16 탭 목록은 apartments ready·'영향권 안 단지' 탭에 맞게 바꿈
- 스크린샷: `docs/screens/map_05a_apartments.png`, `map_05b_apartment_inspector.png`(은마), `map_05c_project_nearby.png`
- 사람 대조표: HUMAN_TODO 46 아래 '실거래 대조표'(은마·청담자이·압구정동 426 = 신고명 '신현대9차', 각 10건)

### 남은 것
- 기본 정보 API 활용신청 뒤 `python -m pipeline.fetch_apt_basis` (응답 필드 확인 → FIELD_MAP 확정) — HUMAN_TODO 28
- `db/market.db` 커밋·배포 여부(HUMAN_TODO 48), 위치 못 찾은 12개 단지(47), 실거래 대조(46)
- 5단계 등록 전이라 '공동주택 기본 정보 목록에 없음' 문구는 화면에 아직 나오지 않음(모두 '기본 정보 확인 전')

## P16 우측 인스펙터 — 완료 (2026-11-10) · 첫 시연(관문 1) 가능
지도에서 누른 사업 구역·규제 구역·필지의 사실을 근거(문서·쪽·기준일)와 함께 우측 인스펙터에 보여 준다. 새 계산 없이 사업 = `progress()`, 규제 = `load_items()`(효력 판정 `timeutil.effective`), 필지 = `parcel_by_pnu()`/`_assemble()`(→ `lookup_pnu`)을 고르고 묶기만 한다. 새로 계산하는 값은 지시된 '남은 단계 수 = 템플릿 단계 수 − 현재 단계 번호' 하나.

### 0. 정리
- **0-1 WMS 프록시** (`core/map.wms_request_error`, `core/live/vworld.wms_check`, `api/index.py`): 검사 먼저(400) → 실시간 설정(503). 허용 = 레이어 3종(`lt_c_uq111`·`lt_c_upisuq161`·`lp_pa_cbnd_bubun`) · 타일 경위도 범위가 강남구 경계 bbox(`public/data/base/gangnam.geojson`) + 2km 안 · `?size=` 256/512 · `?format=` image/png · 지적도 0.6m/px 이하(z17 + 512px). 성공만 `Cache-Control: public, max-age=86400, s-maxage=604800`, 오류(400/502/503/504)는 `no-store`. `LiveError` 메시지(원 URL·키 가능)를 응답 note에 넣던 것을 '참고 WMS 응답 오류/시간 초과'로 바꿈. 브라우저 WMS 소스에 `bounds`(강남구 bbox)를 넣어 범위 밖 타일을 요청하지 않음 — 강남구 bbox에 걸친 z14~17 타일은 모두 허용 범위 안 `[확인]`
  - `tests/test_map_wms.py` 16개: 허용 밖 레이어·대소문자·강남구 밖(부산)·줌 미만·size 300·jpeg·지적도 z16·z17/256 → 400+한국어+no-store+브이월드 호출 0 / 정상 200·image/png·캐시 값 정확히 / 업스트림 시간 초과·오류·XML 응답 → 504/502 no-store / 가짜 키·도메인이 본문·헤더에 없음
  - HUMAN_TODO 43: Vercel은 CDN에 없는 타일마다 함수 실행, Preview에서 같은 타일 두 번 요청해 `x-vercel-cache: HIT` 확인
- **0-2 지표 번호** (PLAN.md): M21 = 필지 클릭 조회 확정, 단지 매칭률 M22·거래 연결률 M23 (P17 할 일·완료 확인, P20 회귀 M1~M23, 검증 문단 '지표 5개(M19~M23)', 지표 표에 M21 행 추가). 저장소에서 다른 M22·M23 언급 없음
- **0-3 라이선스**: PLAN '먼저 정해야 할 것' ① → '서울플랜+·의제처리구역 SHP(둘 다 공공누리 4유형)'. manifest `ref_seoulplan`·`ref_uije` license 둘 다 '공공누리 4유형(출처표시·상업적 이용금지·변경금지)' — `tests/test_map.py`(기존)·ui_check_map 데이터 상태 탭 2행 확인
- **0-4 HUMAN_TODO**: 44 추가(저장소 공개·이전 전 P10(d57a54b) 이후 이력의 지오코더 응답 정리), 41에 'P20 직전 교체 + import_reference IoU 비교 다시'

### 1. API `GET /api/v1/map/feature/{kind}/{id}?as_of=` (`core/map.map_feature`)
- 공통: `kind, id, title, subtitle, kind_label, badges[{text,tone}], unverified, as_of(요청 기준일, 기본 KST 오늘), data_as_of, bbox, sections, evidence[], disclaimer`. `evidence[]` = 화면의 모든 출처 줄을 (문서, 쪽, 근거 문장)으로 한 번씩: `doc_id, short_title, title, gosi_no, published_at, pdf_page, page_label, evidence, page_image, docs_url(/docs.html?doc=&page=), label` → 원문 모달 이전/다음
- project: `sections.progress` = progress() 그대로(+ 단계별 템플릿 `what_happens`/안내·`template_status`), `stepper{total, current_seq, remaining_stages, position_label, next_title}`, `status_badges`, `boundary`(경계 근거 쪽 = GeoJSON `source_page`, D1 18쪽·D9 12쪽 결정도), `parcels`(필지마다 기존 `parcel_projects()` 판정·basis_label·review_id·source + 지번·bbox), `history`(단계 근거 + 묶인 문서 + 관련 고시, 날짜 내림차순)
- regulation (`D10` 또는 `D10-01`, 문서 종류 designation·restriction·press만): 종류·고시번호·발행·효력 기간·상태(as_of 기준)·대상 기준·요약·근거 문장·more_evidence. 지도 경계 있으면 `boundary`, D5는 `boundary_note` = '경계 확인 전, 법정동(압구정동) 단위로만 표시'(기존 상수). D6·D7·D8(서울 전역)도 열림
- parcel (19자리 PNU 또는 `사업:PNU`): `parcel_by_pnu()` 그대로. 실시간 조회가 없거나 unavailable·timeout이면 같은 `_assemble()`을 경계 없이(빌드 캐시) + `boundary_note`. 강남구 밖·없는 필지 → 404
- `_assemble`(= /map/parcel-at에도)에 `layer_items`(층별 항목, lookup 결과에서 고르기만)·`project_banner`·`evidence` 추가. 기존 키는 그대로, lookup 스냅숏 15건 바이트 동일 테스트 통과
- `map_projects`에 `status_badges` 추가(기존 `status_badge` 유지): 공람 기한 open → '공람 중', closed → '공람 마감', 단계 메모에 '승인'(확인 문서 없음) → '승인 고시 미확인'. 2026-11-10: 한양7차 [공람 마감] / 대청마을 [공람 마감, 승인 고시 미확인]
- 없는 kind·id 404(한국어), as_of 형식 오류 400. 사업·규제 p95 ≤ 300ms(pytest 20회)

### 2~6. 화면 (`web/src`)
- `inspector/Inspector.tsx`(따로 불러오는 청크): 머리 sticky(종류 배지·이름·공식 이름·기준일·자료일·상태 배지·'확인 전'·링크 복사·닫기), 탭 role=tablist(←/→/Home/End, 사업 = 개요·근거·필지·이력 / 규제 = 개요·근거·이력 / 필지 = 개요·근거), 스켈레톤·오류·빈 상태, 패널 안 스크롤. 빈 곳 클릭·URL 복원 필지(`sel=parcel:{PNU}`)는 기존 parcel-at 결과(store) 그대로
- `ProjectView`: 스테퍼 + 단계 근거 줄, 상태 배지·세부 상태·단계 메모, 지금/다음 단계(템플릿 문구 또는 '법령 대조 후 사람이 작성' 안내, '법령 대조 전 초안'), 기한 카드(D-n / 마감(YYYY.MM.DD)·기간·제출 방법·장소·출처), 남은 기간 '비교할 사례가 부족합니다' + 계산 방법 참고, 고시 수치 표(항목·값 tabular-nums·출처 줄), 구역 경계 근거 / 필지 탭(실선·점선 아이콘, '사람 확인 전 (검수 n)', 행 → 기존 검색 강조 레이어로 강조 + 그 필지로 이동, 선택은 사업 유지) / 이력 탭
- `RegulationView`: 효력 기간 막대(`inspector/period.ts`, 시작~끝 + 오늘 선, 끝 없으면 열린 막대) + API 상태 배지, 종류·고시번호·적용 범위·대상 기준·요약·근거 문장·출처 줄, '지도에서 보기'(경계 bbox로 이동) 또는 경계 안내
- `ParcelView`(P15 `ParcelLookupCard` 대체·삭제): 맨 위 사업 줄('한양7차아파트 재건축 사업 구역 필지 · 포함된 것으로 보임 · 사람 확인 전 (검수 17)'), 토지 정보 카드(출처 '브이월드… · 조회일'), 건축물 요약, 걸린 고시 층별 건수 → 펼치면 항목·효력·출처 줄, 주변 500m 사업(누르면 그 사업 선택·이동), 참고 구역(참고·비상업 배지·출처·라이선스)
- `ui/EvidenceLine`('D1 · 4쪽 · 2026-10-06', 누르면 모달), `ui/EvidenceModal`(따로 불러오는 청크, #portal-root 포털, role=dialog aria-modal, 포커스 가두기·Esc(캡처 단계, 지도 선택 해제 안 함)·포커스 복귀, 휠·핀치·끌기·+/−/원래 크기·키보드 확대 이동, 근거 문장·문서 제목·고시번호·발행일·PDF/인쇄 쪽, '문서 DB에서 보기', 근거 목록 이전/다음), `ui/Stepper`(지난 = 채움, 현재 = 브랜드 색 강조, 남은 = 빈 칸 / 단계 툴팁 = 템플릿 설명·'법령 대조 전 초안'), 사업 목록 카드도 같은 `MiniStepper` + 상태 배지
- `map/Callout.tsx` + `map/calloutPlace.ts`: 선택한 사업·규제 bbox 중심에 미니 카드(이름·단계·기한 / 효력 기간·상태)와 연결선, move마다 다시 배치, 보이는 영역 밖이면 숨김, 우측 패널과 겹치면 왼쪽. 선택한 도형의 지도 라벨은 콜아웃과 같은 내용이라 숨김
- 상단 고시 칩 팝오버에 '인스펙터에서 보기' → `sel=regulation:D6` 등
- 문구는 모두 `copy/ui.ts`(금지어 검사 통과). 파일 이름 대소문자 충돌(Windows): 콜아웃 순수 함수는 `calloutPlace.ts`

### 7. `DEMO_MAP.md` 초안
5분 6단계(고시 칩 → 레이어 패널·참고 레이어 → 대청마을 8단계 중 1번째·기한·D9 12쪽 결정도 → 한양7차 13단계 중 2번째·마감(2026.11.06)·필지 탭 528 → 역삼동 823 빈 곳 클릭 → 마무리). 단계마다 누를 곳·말할 것·안 될 때(브이월드 응답이 오래 걸리면 시연 주소 '일원동 619'·`?sel=…` 탭). 금지어 없음

### 완료 확인 (2026-11-10)
- 0단계: `pytest tests/test_map_wms.py` 16 passed. PLAN.md 지표 번호 diff는 위 0-2
- `pytest -q` **198 passed** (전 156 + WMS 16 + 인스펙터 26, 기존 P15 WMS 테스트는 강남구 안 타일 번호로 바꿈)
- `npm --prefix web run test` **72 passed** (8파일, 새 `ui/p16.test.ts`: Stepper 렌더 지난·현재·남은 / 모달 Tab 순환·키 / 확대·이동 / 효력 기간 막대 / 콜아웃 배치)
- `npm --prefix web run build`: 초기 JS `index` **95.76 kB gzip**(예산 400KB), `Inspector` 29.5 kB(7.8 kB gzip)·`EvidenceModal` 9.8 kB(3.5 kB gzip) 따로 나뉜 청크, MapView 313 kB gzip(기존과 같은 지연 청크)
- `python -m evals.run_eval`: M1~M20 직전과 같음(M10 시간만 7→6ms). `--live`: M18 20/20 p95 312ms, **M21 5/5 p95 224ms**. 커밋한 report.md는 기존처럼 비실시간 실행본
- `tests/ui_check_map.py` 개발 서버 3000 **94/94**, `--built` 8000 **94/94**, 콘솔 오류 0. P16 점검 25개(한양7차 구역 클릭 → '재건축 13단계 중 2번째 · 앞으로 11단계 · 다음: 정비구역 지정 고시'·'마감(2026.11.06)', 스테퍼 13칸, 툴팁, 고시 수치, 콜아웃·겹침 없음, 탭 키보드, 대비 ≥4.5, 원문 모달 이미지·aria-modal·포커스 가두기·확대·다음·Esc·포커스 복귀, 필지 탭 528 → 강조·이동, 대청마을 '모아타운 8단계 중 1번째'·D9 12쪽, D10 효력 막대·오늘·'지도에서 보기', `sel=parcel:1:528` 사업 줄, 역삼동 823 정식 카드, `sel=project:1` 공유, 고시 칩 → 인스펙터, 상태 배지, 4유형 2행). P14 '자리표시(P16)' 점검은 '선택 → 인스펙터에 그 사업'으로 바꿈
- 스크린샷: `docs/screens/map_04a_project_hanyang.png`, `map_04b_project_daecheong.png`, `map_04c_evidence_modal.png`, `map_04d_regulation_d10.png`, `map_04e_parcel_528.png` (기존 map_02*·03* 도 --shot으로 다시 찍힘)

### 남은 것
- Vercel Preview에서 WMS 타일 CDN 적중 확인(HUMAN_TODO 43), push 전 확인 받기
- 인스펙터의 as_of 선택(타임라인)은 P19. API는 `?as_of=` 지원
- URL `sel=parcel:1:{PNU}`로 처음 열 때는 지도가 그 필지로 이동하지 않음(카메라 `c`·`z`가 같이 공유되면 같은 화면). 필요하면 P20
- 단계 설명 문구(what_happens)·법령 근거는 여전히 비어 있음(HUMAN_TODO 2) — 툴팁은 안내 문구로 표시

## P15 공식 참고 레이어·필지 클릭 조회 — 완료 (2026-11-10)
서울시 공식 공간정보 2종과 브이월드 WMS 3종을 '참고' 레이어로 올리고, 지도 빈 곳을 누르면 그 필지의 토지 정보·걸린 고시·주변 사업·참고 구역이 나오게 했다. 카드 디자인 완성은 P16.

### 0. 지오코더 응답 저장 정리
- 찾은 곳: `tests/fixtures/vworld/getcoord_527.json`·`getcoord_1168011400106190000.json`·`getcoord_notfound.json`(커밋됨), `search_road_teheran_427.json`(브이월드 주소 검색, point 좌표, 커밋됨), `build/check_keys/vworld/getcoord_*` 3개·`search_road_teheran_427.json`, `build/p13/land_cache_before.json`(지오코더 좌표 28건)·`project_coords_before.csv`·`propedia_before.db`, `build/propedia.db.bak`, `build/propedia_before_p135.db`, 그리고 **커밋된 `db/propedia.db` 페이지 빈 공간에 옛 지오코더 좌표 바이트 3곳**(행 데이터에는 없음, P13 patch_coords가 VACUUM 없이 덮어씀). `build/vworld_raw/`에는 없음
- 처리
  - `pipeline/check_keys.py`: getcoord 3건·주소 검색 1건은 HTTP 상태·`response.status`·응답 필드 이름(키 경로)만 출력, 본문은 어디에도 저장하지 않음(`--update-fixtures`도). 이미지 API 중심은 지오코더 대신 `seed/land_cache.json`의 필지 경계 중심점. 새 옵션 `--parcel-at`(2D 데이터 필지 점 조회 저장 응답만)
  - fixtures 견본: `point` → x=127.000000·y=37.500000, 주소 문자열 → '서울특별시 강남구 견본로 1'(검색 응답은 좌표만, 결정대로), `_sample_note` 추가. PNU는 파싱 테스트 식별자라 유지. 실제 좌표에 기대던 테스트는 `tests/test_live_vworld.py:28` 하나(범위 검사) → 형식 검사(`{lat: 37.5, lon: 127.0, source}`)로 바꿈
  - `db/propedia.db`: `pipeline/vacuum_db.py`(새, 할 일 없으면 건드리지 않음) → 'vworld-geocoder' 바이트 3 → 0건, 시연 15건 lookup 응답 전후 같음. `run_all`·`patch_coords`·`patch_parcels` 끝에 `common.vacuum_db()`
  - build/ 10개 삭제(승인 받음). `build/p13/fetch_land.log`는 좌표 없이 출처 이름·이동 거리만이라 남김
- git 이력(수정·force-push 안 함): getcoord 저장 응답은 d57a54b(P10)부터 HEAD까지 커밋돼 있었음. `seed/land_cache.json`·`seed/project_coords.csv`의 지오코더 좌표는 d57a54b~e176aa3(P13에서 중심점으로 바꿈) 사이. `db/propedia.db` 바이트: d57a54b 20곳, e176aa3·723cd23·6f2e51d 2곳(빈 공간). P9 이전 커밋에는 없음
- P14 '남은 것'의 check_keys 항목 닫음

### 1. 참고 레이어 빌드 (`pipeline/import_reference.py`, 멱등)
- pyshp(CP949) → EPSG:5174 → 4326(always_xy). 좌표계 검증(반올림 전 변환값, P13과 같은 계산): **D9 '일원동 대청마을 북측구역' IoU 0.9615 (P13 0.961), D10 '대치선경' 0.9750 (P13 0.975)** — 소수 6자리 좌표로는 0.9616·0.9750
- 고르기: 강남구 경계와 겹친 면적 > 0(선만 닿는 이웃 구 도형 제외), 자르지 않음. 완전 중복 8건(의제처리구역: 압구정아파트지구·청담현대1차 소규모재건축 등) → `build/reference_dupes.csv`
- 라이선스 확인: 서울플랜+ OA-22712 '공공누리 4유형 : 출처표시+상업적 이용금지+변경금지', **의제처리구역 data.go.kr 15082965도 '공공저작물 : 출처표시, 상업적 이용금지, 변경금지 (제 4유형)'** (PLAN의 '출처표시'는 틀림 → 둘 다 '참고·비상업', PLAN 192·193·229행 고침, HUMAN_TODO 42)
- 결과 (속성은 원본 필드 이름·값 그대로 + `_source`·`_license`·`_as_of`·`_ref`·`_layer`·`_row`, 좌표만 소수 6자리)

  | 레이어 | 원본 | 강남구 | 경계 밖 걸침 | 기준일(CREATE_DAT 최대) | 크기 | sha256 |
  |---|---|---|---|---|---|---|
  | `ref_seoulplan.geojson` | 2,585행 | 109건 | 0 | 2026-01-31 | 160,100 B (0.15 MB) | `00561cbf…` |
  | `ref_uije.geojson` | 3,329행 | 75건 | 4 | 2026-08-26 | 308,402 B (0.29 MB) | `fbf99da4…` |

  둘 다 1.5MB 미만이지만 지연 로딩(켤 때 처음 한 번) 적용. `manifest.json`의 `ref_*` 항목(원천·기준일·건수·라이선스·group·badge·lazy·note '표시용 좌표 변환·반올림만, 도형 가공 없음')은 import_reference 소유, `build_map_layers`는 `propedia_*`만 바꾸도록 고침 → 두 스크립트 모두 2회 실행 sha256 같음(manifest `12fd727a…`)
- 종류별 건수 (SHP·메타데이터·데이터셋 페이지에 코드 이름표가 없음 → 코드와 대표 구역명, HUMAN_TODO 40)

  | 서울플랜+ SCLAS_CL | 건수 | 예 | | 의제처리구역 ATRB_SE | 건수 | 예 |
  |---|---|---|---|---|---|---|
  | BZ105 | 24 | 은마아파트 | | UQ1240 | 27 | 개포현대2차아파트 재건축정비사업 |
  | BZ202 | 19 | 논현세광연립 가로주택정비사업 | | UQ1206 | 9 | 개포우성4차아파트 재건축사업 |
  | BZ101 | 15 | 개포 경남·우성3·현대1 | | UQ5600 | 8 | 취락구조개선(방죽1마을) |
  | BZ302 | 10 | 강남구청역A | | UQ1812 | 5 | 역삼목화연립 가로주택정비사업 |
  | BZ602 | 10 | 서광아파트 | | UQ1700 | 4 | 청담.도곡아파트지구(삼성주구) |
  | BZ204 | 9 | 개포현대4차아파트 | | UQ1813 | 4 | 청담현대1차아파트 소규모재건축사업 |
  | BZ303 | 7 | 논현동 202-7 | | UQ1900 | 4 | 개포토지구획정리사업 |
  | BZ306 | 5 | 테헤란 아이파크 | | UQ5500 | 3 | 수서역세권 공공주택지구 |
  | BZ501 | 3 | 세곡2 | | UQ6300 | 3 | 양재동 1-26 일원 역세권 청년주택 공급촉진지 |
  | BZ603 | 3 | 논현종합시장 | | UQ6500 | 3 | 택지개발지구 |
  | BZ201·BZ203·BZ301·BZ601 | 각 1 | 대청마을 북측구역·개포동 1165-4·일원동 743·구룡마을 | | UQ1100·UQ1221·UQ1232·UQ1811·UQ6400 | 각 1 | 개포(구룡마을)도시개발구역 등 |
- 지도 모양: 회색 점선 외곽선 + 면 8%(새 토큰 `--color-layer-ref` = ink-muted 값), 종류별 색 없음, 줌 15 이상 라벨 'DGM_NM · 참고'(Propedia 라벨 다음 순위로 겹침 피하기)

### 2. 브이월드 WMS 참고 레이어
- `pipeline/check_wms.py`(새): GetCapabilities 레이어 211개. 지원 요청 GetCapabilities·GetMap·GetFeatureInfo — **LegendURL·GetLegendGraphic 없음 → 범례 생략**. 고른 이름(영현): 용도지역 `lt_c_uq111` '도시지역'(강남구 전체가 도시지역), 지구단위계획구역 `lt_c_upisuq161` '지구단위계획', 지적도 `lp_pa_cbnd_bubun` '연속지적도'. 다른 후보: uq112 관리지역·uq113 농림지역·uq114 자연환경보전지역, uq121~130 용도지구 8종, `lp_pa_cbnd_bonbun`
- **브이월드 WMS는 CORS 헤더가 없음** `[확인]`(WMTS는 `Access-Control-Allow-Origin: *`) → 브라우저 직접 요청은 콘솔 CORS 오류·타일 0장. 결정(영현): `GET /api/v1/map/wms/{layer}/{z}/{x}/{y}.png` 서버 프록시(`core/live/vworld.wms_tile`, 서버 키·`VWORLD_DOMAIN`, 4초·재시도 1회, 허용 레이어 3개만, 저장 없음·`Cache-Control: max-age=86400`). 브라우저에 키가 나가지 않음
- **연속지적도 WMS는 0.6m/px보다 거친 요청에 빈 그림(1,784B)** `[확인]`: z16 256px(2.39m/px)·512px(1.19) 빈 그림, z17 512px(0.6) 그림, z16 1024px는 525KB. 그래서 지적도는 **줌 17부터**(프록시가 z17은 512px로 받음), 행 안내 '줌 17 이상에서 표시'. 지시(16)와 다름 → HUMAN_TODO 43. 용도지역·지구단위계획은 줌 14부터
- 레이어 패널 '공식 참고' 5행(참고 배지·건수·투명도), 줌 조건 안내, 우하단 출처에 켜진 참고 레이어 출처를 이어 붙임(길면 줄 바꿈)

### 3. 필지 클릭 조회
- `core/live/vworld.parcel_at(lat, lon)`·`parcel_by_pnu(pnu)`: 2D 데이터 `LP_PA_CBND_BUBUN` 점 필터·PNU 필터 → pnu·지번·주소·경계·중심점. 상태 ok / outside(강남구 법정동 14개 밖) / not_found / unavailable / timeout. 캐시·저장 없음. `get_land(location=)`: 위치를 주면 지오코더를 부르지 않음
- `core/lookup.py` 리팩터링: `lookup()` = 정규화 + `fill_layers()`, 새 `lookup_pnu()`(+ `core/address.normalize_pnu`). 리팩터링 전에 만든 `tests/fixtures/lookup_snapshot/*.json` 15건과 **바이트 단위로 같음**
- `core/geo.py`·`core/refzones.py`(표준 라이브러리): bbox 선필터 + 짝홀 규칙(구멍·MultiPolygon). 184개 도형에서 점 판정 0.1~0.3ms
- `GET /api/v1/map/parcel-at?lat=&lon=`(강남구 주변 밖 400)·`GET /api/v1/map/parcel?pnu=`(URL 복원용): pnu·지번 주소·경계·토지 정보(지목·면적·용도지역·지역지구·공시지가)·건축물·층별 고시 수·주변 500m 사업·참고 구역(이름·종류 코드·출처·라이선스·배지). 좌표는 필지 경계 중심점(`vworld-2d:LP_PA_CBND_BUBUN centroid`)
- 화면: `map/pick.ts` 우선순위(사업 → 규제 → 사업 필지 → P17·P18 자리 → 빈 곳 = 필지 조회, 겹치면 P14 목록 유지 — 영현 결정), `api/parcel.ts` `LatestRequest`(AbortController, 이전 요청 취소), `state/parcelLookup.ts`, 브랜드 색 외곽선 강조(`click-parcel-line`), `inspector/ParcelLookupCard.tsx`, `sel=parcel:{19자리}` 복원(사업 필지 `parcel:{사업}:{pnu}`와 형식으로 구분). 상태 문구는 `web/src/copy/ui.ts`

### 완료 확인 (2026-11-10)
- `pytest -q` **156 passed** (전 132 → `tests/test_parcel_at.py` 23: 파싱·강남구 밖·필지 없음·시간 초과·오류·키 없음, 조립(지오코더·주소 검색 호출 없음), API 형식, lookup 15건 바이트 동일, `lookup_pnu` = `lookup` 층, 참고 구역 안/밖·속도, import_reference 멱등(임시 폴더 2회 + 커밋 결과와 같음), 원본 필드 유지, 지오코더 견본, check_keys 본문 저장 없음, parcel_at 저장 응답에 키·도메인 없음, WMS 프록시 3 / `test_map.py` 참고 레이어 1)
- `npm --prefix web run test` **59 passed** (전 48 → `p15.test.ts` 11: 클릭 우선순위, 요청 취소, `sel=parcel` 복원, 참고 레이어 모양·WMS 줌·출처)
- `npm --prefix web run build`: 초기 JS `index` **94.66 KB gzip**(전 92.22, ≤ 400KB), `MapView` 312.15 KB lazy
- `python -m pipeline.import_reference` 2회 sha256 같음, `python -m pipeline.build_map_layers` 뒤에도 같음
- `python -m evals.run_eval`: M1~M20 직전과 같음 (M10만 6 → 7ms)
- `python -m evals.run_eval --live`: M18 **100% (20/20) · p95 300ms**, 새 지표 **M21 필지 클릭 조회 100% (5/5) · p95 307ms** (세곡동 279 307ms·역삼동 823 159·논현동 100 203·삼성동 159 43·개포동 12 174, 토지 정보 모두 ok). 대표 좌표는 `pipeline/live_parcel_points.py`가 연속지적도 경계 중심점으로 만든 `evals/goldset/live_parcels.yaml`(2회 같음). 커밋한 `evals/report.md`는 오프라인 실행본
- `tests/ui_check_map.py --shot`(3000) **69/69**, `--built`(8000) **69/69**, 콘솔 오류 0 (P15 13항목: 참고 2종 켤 때 한 번만 요청·그려짐·점선·면 8%·출처, 참고 라벨, 줌 17 미만 안내·타일 요청 없음, 17 이상 WMS 타일 200(8000에서도 200×24), 역삼동 823 클릭 → 강조·카드·URL, 새로고침 복원, 빠른 두 번 클릭 → 마지막 것만, 대청마을 구역 안 → 사업 선택, 은마아파트 구역 안 → 참고 구역 이름)
- 스크린샷: `docs/screens/map_03a_reference.png`, `map_03b_wms_cadastral.png`(줌 17.2), `map_03c_parcel_click.png`

### 남은 것
- 인스펙터 카드 디자인(P16), 코드 이름표(HUMAN_TODO 40), 서울플랜+ 새 판(41), Preview에서 WMS 프록시 확인(43)

## P14 좌측 레이어 패널·상단 바 — 완료 (2026-11-10)
사용자가 레이어를 켜고 끄고, 겹쳐 보고, 사업을 찾아 고를 수 있게 했다. 인스펙터는 '선택 상태'까지만 만들었다 (내용은 P16).

### 0. 정리
- [x] 0-1 문서 (528 반영): `agents.md` §4 A2 '주변 66m' → 한양7차 사업 구역 필지(포함된 것으로 보임, D1 p18 결정도 대조, 사람 확인 전), A4만 '주변 293m' + §21 한 줄 / `docs/map/PLAN.md` 34·41·189·471·473행 사업 필지 18 → 19(대표 지번 2 + 지도 대조 후보 17: 대청마을 16, 한양7차 528 1). 473행 '28필지'는 그대로(528은 A2로 이미 들어 있었음) / `README.md` 지도 대조 설명에 한양7차 528번지 1필지. 다른 뜻의 18(필드 약 18개, 18px, D1 18~21쪽, P18, M18)과 PROGRESS의 과거 기록은 그대로
- [x] 0-2 `pipeline/check_keys.py`: 기본 출력 `build/check_keys/{vworld,juso}/`, `--update-fixtures`일 때만 `tests/fixtures/` (두 경로 모두 같은 키 검사 `save()`). 실행 결과 토지 3종 × 2필지 200 OK, getcoord 200 OK, image 200 png, juso E0001(키 빈 값, HUMAN_TODO 39) → `git status --short tests/fixtures` **변경 없음**

### 1. API (`core/map.py`, 표준 라이브러리·읽기 전용)
- [x] `GET /api/v1/map/manifest`: `public/data/layers/manifest.json` + `public/data/base/` → 레이어 목록(id·group·name·kind·source·license·as_of·count·status·note·available_from + unverified·doc_ids·source_pages). 준비 중: 서울플랜+·의제처리구역·용도지역 WMS·지적도 WMS(P15), 아파트 단지(P17), 학교·지하철역·편의시설(P18). D5 `not_adopted`(note는 manifest notes 그대로). 필지 `count_by_judgment {included, possible, likely}`(DB `project_parcels` + 포함 판정 표). 영향권 250·500 건수는 GeoJSON `buffer_m`으로 셈. 파일이 없으면 503 + 한국어 안내. 응답 예시 `tests/fixtures/map_manifest.json`
- [x] 포함 판정 표 `INCLUSION`·`INCLUSION_LABEL`을 `core/map.py` 한 곳으로 옮기고 `build_map_layers`가 import
- [x] `GET /api/v1/map/notices?as_of=`: `lookup.load_items` 그대로(효력 판정 `timeutil.effective` 재사용) → 서울 전역·강남구 범위, tier=applies, 효력 중, **계획 문서 제외**(영현 결정). 2026-11-10 → D6·D7·D8, 2027-01-01 → D7·D8. 형식이 틀리면 400
- [x] `GET /api/v1/map/projects?as_of=`: `progress()` 결과 그대로 (position_label·현재 단계·기한 d_day_label·sub_status), bbox(사업 구역 GeoJSON), 판정별 필지 수, 확인 전 여부, 호버 문구 `hover_line`(예: '한양7차아파트 재건축 · 2/13단계 · 정비계획(안) 주민공람 마감' — progress 값을 이어 붙이기만 함)
- [x] `/api/v1/health` 확장: `keys {vworld, juso}` = '있음'/'없음'만, `key_notes`(도로명주소 키 없음 → 브이월드 검색으로 대체). 지금: 브이월드 있음 · 도로명주소 없음

### 2. 레이어 빌드: within_impact
- [x] `build_map_layers.py`: 필지(중심점)·규제(도형 중심점)마다 `within_impact {project_id, buffer_m}` = 들어가는 가장 작은 영향권(EPSG:5186, 같으면 project_id 작은 쪽), 밖이면 null. MapLibre 식용 `impact_buffer_m`
- 결과: 필지 19개 모두 자기 사업의 250m 안(528 → {1, 250}), D10 → null(영향권에서 약 1.2km). 그래서 겹침 대상에 규제 구역을 넣음(영현 결정)
- 2회 실행 sha256 같음: projects `0c2ba018…` · impact `9a724e04…` · parcels `f7eefbde…` → **`cd3f6ee7…`** · regulations `945247ce…` → **`d06cb2ba…`** · manifest `0f8bf69d…`(그대로)

### 3~7. 화면 (`web/src`)
- [x] 상태 `state/useMapStore.ts`(zustand 하나): layers{visible, opacity}·basemap·overlap·selected{kind,id}·hovered·leftTab·camera + 화면 안 상태(palette·viewRequest·searchHit). `state/url.ts`(순수 함수)·`useUrlSync`(history.replaceState, 300ms 디바운스, 카메라는 moveend 때만, debug 등 다른 파라미터 유지). 기본값과 같은 항목은 URL에서 뺌
- [x] 좌측 패널(`panel/`, GlassPanel 320px, 스크롤은 패널 안): 탭 레이어 · 사업 목록 · 고시 피드('P19에서 채웁니다') · 데이터 상태
  - 레이어 탭: role=tree/treeitem, 그룹 접기·그룹 전체 체크(indeterminate). 배경지도 라디오(지도 위 전환 버튼에서 옮김, 3D만 남김). 행 = 실제 checkbox·색 칩(SVG, 지도 스타일과 같은 면·선·빗금·점선)·이름·건수(manifest)·'확인 전'·정보 툴팁(포털: 원천·기준일·라이선스·근거 쪽)·투명도 슬라이더. 영향권 아래 고정 문구, 필지 아래 범례 두 줄('실선 = 포함·포함될 수 있음 (대표 지번)' — 대표 지번 2건은 '포함'이 아니라서 문구를 정확히 맞춤, '점선 = 포함된 것으로 보임 (지도 대조, 사람 확인 전)') + 판정별 건수. D5·준비 중 행 비활성
  - 겹침 보기 스위치: `OVERLAP_TARGETS = ['parcels','regulations']`(설정 하나, P17·P18은 id만 추가), `opacityExpr` = `['case', ['==', ['get','impact_buffer_m'], null], 기준×0.25, 기준]` — setPaintProperty만, 다시 그리지 않음
  - 사업 목록: 카드(이름·종류·단계 스테퍼·상태 배지·기한·필지 수·확인 전) → 구역으로 이동 + sel=project:{id}
  - 데이터 상태: 레이어·원천·라이선스·기준일·건수·상태 표, DB 기준일·빌드 시각, 키 있음/없음, 운영 메모(D5 경계 확인 전, 도로명주소 키 없음)
- [x] 지도 연결: 토글은 `setLayoutProperty('visibility')`, 투명도·겹침은 `setPaintProperty`, 선택·검색 강조는 `setFilter`. 배경을 바꿔 스타일을 새로 만들 때도 지금 상태를 넣음. 영향권 250·500을 같은 소스의 두 레이어로 나눔(`propedia-impact{250,500}-{fill,line}`). 필지 호버·클릭용 투명 면 `propedia-parcel-hit`, 선택 강조 `propedia-{project,regulation,parcel}-selected`(브랜드 indigo), 검색 강조 `propedia-parcel-search`(brand sky)
- [x] 호버 툴팁: 가장 작은 도형 먼저(필지 → 규제 → 사업). 사업은 API `hover_line`, 필지 '압구정동 528 · 포함된 것으로 보임 · 사람 확인 전'. `.map-moving` 중 숨김. 클릭: 사업 → 규제 → 필지, 둘 이상 겹치면 선택 목록 → 선택하면 인스펙터 열고 'P16에서 내용 표시'
- [x] 라벨 충돌: 라벨이 HTML 마커(스타일에 글꼴 없음·CDN 금지)라 MapLibre `text-variable-anchor`를 못 씀 → 같은 규칙을 `map/labels.ts` `placeLabels`로: 줌별 표시(규제 라벨 줌 14 이상) + 가운데·위·아래·오른쪽·왼쪽 후보를 radial offset 14px로 시도해 다른 라벨·법정동 이름과 겹치지 않는 첫 자리. 전 `map_02g_labels_before.png`(대청마을·D10 라벨 겹침) → 후 `map_02g_labels_after.png`(규제 구역을 켜도 겹침 없음)
- [x] 상단 바(`app/TopBar.tsx`): 로고 · 작업 탭('선택한 사업'은 선택 없으면 비활성, 누르면 그 bbox / '강남구 전체'는 첫 화면) · 검색 버튼(Ctrl K) · 고시 칩 최대 3 + '+N'(팝오버: 종류·효력 기간·근거 쪽·원문 쪽 링크) · '오늘 YYYY.MM.DD(KST) · DB 기준 YYYY-MM-DD'
- [x] 명령 팔레트(`search/CommandPalette.tsx`, lazy 별도 청크): Ctrl/Cmd+K(기본 동작 막음)·Esc, 300ms 디바운스, 사업(`searchProjects`: 이름 앞부분 → 이름 → 별칭 → 대표 지번) / 주소(기존 `/api/v1/lookup` 그대로, ambiguous 후보, 실패 문구 그대로). 기존 lookup은 '강남구'가 없으면 찾지 못해서, 구 이름 없이 동·번지로 시작하는 검색어만 앞에 '강남구'를 붙임(`addressQuery`, API는 그대로). 주소를 고르면 필지 경계가 있으면 강조·이동, 없으면 임시 핀(좌표는 화면 메모리에만). ↑↓ Enter, 최근 검색 5개 sessionStorage(try/catch)
- [x] 키보드 L·I·T·Esc·Ctrl+K, 입력창 안에서는 L·I·T 꺼짐. 새 문구는 `web/src/copy/ui.ts`(test_wording 검사 대상). 토큰 추가 `--color-layer-regulation-line`·`--color-warn`(#8a5a00, 흰 바탕 6.2:1)

### 완료 확인 (2026-11-10)
- `pytest -q` **132 passed** (전 123 + `tests/test_map.py` 9: manifest 형식·판정별 건수·상태·503, notices 2026-11-10/2027-01-01/400, projects ↔ progress, within_impact 표(528 포함), health 키 값 없음)
- `npm --prefix web run test` **48 passed** (전 21 → url 6, search 7, labels 6, layers 겹침·점선·강조 식 등)
- `npm --prefix web run build`: 초기 JS `index` **92.22 KB gzip**(≤ 400KB), 명령 팔레트 3.02 KB 별도, 지도 `MapView` 310.64 KB lazy(전과 같음)
- `python -m pipeline.build_map_layers` 2회 sha256 같음 (위 2)
- `python -m evals.run_eval`: M1~M20 직전 결과와 같음 (M10 응답 시간만 8 → 6ms, M18은 `--live` 전용이라 전후 모두 없음)
- `tests/ui_check_map.py --shot`(3000) **56/56**, `--built`(8000) **56/56**, 콘솔 오류 0 (빌드본은 기존대로 타일 차단 제외 규칙)
- 스크린샷: `docs/screens/map_02_layers.png`, `map_02d_overlap.png`, `map_02e_search.png`, `map_02f_status.png`, `map_02g_labels_before.png`, `map_02g_labels_after.png`

### 남은 것
- 오른쪽 인스펙터 내용(P16), 고시 피드(P19), ~~빈 곳 클릭 필지 조회(P15)~~ → P15 완료
- ~~`check_keys`는 기본 출력 위치(`build/check_keys/`)에도 지오코더 응답(getcoord)을 저장한다~~ → P15 0단계에서 닫음 (본문 저장 안 함)

## P13.5 528번지 likely 반영, 키 확인 — 완료 (2026-11-10)
### A. 브이월드 키
- `.env`: `VWORLD_API_KEY` 있음 · `VWORLD_DOMAIN` 있음 · `VITE_VWORLD_KEY` 있음 · `JUSO_CONFM_KEY` **빈 값** (HUMAN_TODO 39)
- `pipeline.check_keys`: 토지 3종 × (527, 619) 6건 HTTP 200 OK(18·13·1·1·1·1건), getcoord 200 OK, image getmap 200 png 312,540B, juso 200 **E0001**(키 비어 있음). 저장 응답이 `tests/fixtures/`에 덮어써져 `git checkout -- tests/fixtures`로 되돌림
- `pipeline.fetch_land --dry-run`(새 옵션, seed를 쓰지 않고 `build/land_compare.json`): 28필지 다시 받아 지금 `seed/land_cache.json`과 비교 → **값이 다른 칸 0개** (지목·면적·용도지역 1·2·이용상황·도로·지형·공시지가·지역지구·기준연도·status). seed 그대로
- `evals.run_eval --live` M18: **100% (20/20), p95 278ms** 통과. 20건 모두 `vworld-search` 경로(juso 키 없음). 양재대로55길 14만 PNU '다름'(상태·토지 ok)

### B. 압구정동 528(A2) → 한양7차 likely (영현 결정 2026-11-10)
- 원천: `seed/map_reading_parcels.csv`(새, 열 = 대청마을 CSV + `project_key,note,decided_by,decided_at`) 1행: 528, 근거 'D1 p018 정비구역 결정도 대조(경계 겹침 99.7%)', 메모 '본문은 527번지 일대만 언급, 528 미기재'. `seed/daecheong_map_reading.csv`·527 대표 지번 행은 그대로
- `build_projects.extra_parcel_values()` → `project_parcels`(map_reading, verified 0, D1 p18, evidence = 근거 + 메모). `extra_group_reviews()` → 검수 `parcel_group 1:map_reading`을 `review_queue.py` **맨 끝**에서 넣음 (기존 검수 id 1~16 그대로, 새 행 id 17)
- 판정 값·문구는 기존 그대로: `core/lookup.py` map_reading → `likely` "…구역에 포함된 것으로 보입니다. 확인해 주세요", 지도 `INCLUSION['map_reading']='likely'`(점선)
- 결정도 경계 안이지만 사업 필지에 없는 것 (추가 안 함): 505 공(안쪽, 겹침 65.7%), 508 도(걸침, 47.4%), 529-1 도(걸침, 4.1%)
- `pipeline/patch_parcels.py`(새, 네트워크·`../data` 없음): `build/propedia.db.bak` 복사 → 시연 15건 판정 → map_reading 행·묶음 검수 행만 seed에 맞춤 → 다시 판정. seed와 상관없는 주소 판정이 바뀌거나 대상 주소가 likely가 아니면 되돌리고 종료 1
  - 1회: 추가 1 · 수정 0 · 삭제 0 / 검수 1 → sha256 `8b89e328…`, 2회: 0·0·0/0 → `8b89e328…` 같음
  - 원본 PC `run_all`도 같은 seed·같은 함수(`extra_parcel_values`·`extra_group_reviews`)로 같은 행을 만들고 검수 행이 마지막 id를 받는다. 다른 것은 `meta.build_at`·rowid 순서뿐 (HUMAN_TODO 38에 확인 추가)
- 시연 15건 전·후: **A2만 바뀜** `주변 1 66m` → `포함 1:likely`(basis map_reading, review_id 17, 원문 D1 p18). A1·A3 possible, A4 주변 293m, A5 법정동, B1 possible, B2 likely, B3 주변 275m, 나머지 사업 없음, A10 범위 밖 — 그대로. A2 사업 카드 = A1과 같은 사업 1(재건축 13단계 중 2번째, 공람 2026-11-06 마감)
- `evals/goldset/addresses.yaml` A2 `nearby` → `likely` (주석 '2026-11-10 영현 결정: D1 p018 결정도 대조, likely, 사람 확인 전 (HUMAN_TODO 35)')
- `run_eval` M1~M20 모두 통과. 전과 다른 곳: M8 주변 판정 쌍 3 → 2 (8/8 그대로), M20 25 → 26 도형, M10 6 → 8ms. 그 밖 같음
- `build_map_layers` 2회: 필지 18 → **19** (`parcel:1:1168011000105280000`, likely), manifest count 19, 5개 파일 sha256 2회 같음(parcels `f7eefbde…`, manifest `0f8bf69d…`)
- 테스트: `test_lookup.py` A2(likely·map_reading·D1 p18), `test_db_build.py`(묶음 검수 2건, 사업 1 필지 2개), `run_all.py` P3_SQL(`1 | 1 | 0 / 2 | 16 | 0`), `web/src/map/layers.test.ts` 필지 19 — 모두 같은 근거 주석
- 기록: `seed/review_drafts/D1_parcel_528.json` '반영됨' + 결정 + review_queue 행, HUMAN_TODO 36 닫음·35에 528 추가·38에 patch_parcels 확인 추가·39 juso 키
- 완료 확인: `pytest -q` 123 passed / `npm --prefix web run test` 21 passed / `tests/ui_check_map.py` 27/27

## P13 Propedia 레이어 빌드 — 완료 (2026-11-10)
고시 도면을 연속지적도와 맞춰 사업 구역 2·규제 구역 1의 경계를 만들고, 영향권·포함 판정 필지와 함께 `public/data/layers/`에 냈다. 좌표는 지오코더 결과 대신 필지 경계 중심점. 모든 도형은 사람 확인 전(`verified=0`, 지도 라벨 '확인 전').
- [x] 0단계 회색 배경: 브이월드 `white`에 `raster-saturation -1`(`web/src/map/basemaps.ts` `GRAY_PAINT`), `tests/ui_check_map.py`에 채도 검사. 레이어를 올린 스크린샷을 보고 `raster-brightness-min` 0.08 → **0.2**(진한 도로·녹지가 보라색과 겹쳐 보여 어두운 쪽을 올림)
- [x] 2 `pipeline/fetch_parcels.py`(+`pipeline/geo.py`): `project_parcels` 18 ∪ 범위 안 시연 주소 PNU(A10 서초구 제외) = **28필지**, 못 찾음 0. 528(A2) 포함. `LP_PA_CBND_BUBUN` `attrFilter=pnu:=:…` 1건씩, 원 응답 `build/vworld_raw/parcels/`. 면적·중심점(representative_point)은 EPSG:5186, 저장 4326 소수 6자리, `as_of`는 응답 `gosi_year·gosi_month`(2025-01). 2회 실행 sha256 `64a2d534…` 동일
  - 확인: 대치동 506 필지(78,634.9㎡)가 서울플랜+ '대치선경'과 IoU 0.9997·0.1m → UQ120 `.prj`(Korean 1985 Modified Central Belt, Bessel)는 **EPSG:5174**로 읽으면 맞음 `[확인]`
- [x] 3-0 `pipeline/drawing_align.py`: `daecheong_map.py`의 지적선 추출·필지선 래스터·FFT 상호상관을 함수로 옮김 + 2위 후보(1위와 위치 10m 이상 또는 배율 3% 이상 다른 것)·1위/2위 비율(<1.05 '모호함')·1위 둘레 재탐색·대조 그림(확대 인셋)·영역 추출. 기준점은 대표 필지 경계 중심점(지오코더 `CENTER` 삭제). 입력은 `data_raw/Dn.pdf`. 결과 `build/align/{doc}.json`, 필지 표 `build/align/{doc}_parcels.csv`
  - 도면 이미지: D1·D10은 쪽 안 내장 이미지가 원본(1153×747, 818×578) — 3000px 렌더링은 같은 이미지를 늘릴 뿐이라 내장 이미지를 그대로 씀. D5는 지도가 벡터(내장 이미지 2개는 제목·범례 띠)라 4200px 렌더링. D9은 꼭짓점을 읽은 2000px 렌더링 유지
  - **회귀 결과가 P10과 다름 (보고)**: P10 기록 0.79m/px는 탐색 범위(0.70~1.00)가 실제 배율을 넣지 못해 고른 틀린 봉우리였다. 0.79면 경계 면적 123,400㎡(고시 +36%). 경계 면적·둘레가 모두 서울플랜+ 구역과 **0.69m/px**를 가리켜 범위를 0.60~1.00으로 넓히고 옅은 지적선(채널 합 750)을 잡게 하자 **0.6777m/px, 상관 0.489(P10 조건 0.087), 1위/2위 2.0**으로 지적선이 블록 단위로 맞음(`build/overlay_D9.png`). P10에서 고른 16필지는 **모두 여전히 경계 안쪽**(경계 안 6m 이상 후보 324필지) → `seed/daecheong_map_reading.csv`·판정 그대로
- [x] 3-1·3-2·4 경계: `pipeline/align_drawings.py` + `seed/boundaries/{D1,D10,D5}_px.yaml`(쪽·이미지·지도 틀·축척·꼭짓점·판독 메모), D9은 `daecheong_map.py --export-boundary`
  - D1 p18: 축척 막대 0–10–25–50m = 0·28·71·141.5px → 0.3534m/px. 빨간 일점쇄선 꼭짓점 6개(동쪽 529도 옆 약 5m 꺾임 포함)
  - D10 p3: 막대 없음. 결정 D3('A3 1/1000' → 0.5134m/px ±25%)로는 맞는 값이 없었음(1위/2위 1.02 모호함, 면적 −73%). 넓혀 본 진단에서 1.24m/px·상관 0.69·IoU 0.975 → **동혁 승인으로 시작값을 면적 기준 1.254m/px(±25%)로 바꿈**(이유는 `D10_px.yaml`에 기록). 둥근 남동 모서리는 파란 선 중심을 8px 간격으로 재서 꼭짓점 10개로 근사
  - D5 p4: 막대 라벨 '0–10–250–500m'은 칸 길이(110/165/275px)상 0–**100**–250–500m의 오기로 보고 0.9091m/px. 빨간 경계·빗금 영역을 자동 추출(1/2 축소·닫힘·구멍 메움). 연속지적도 6×3 타일 **27회·3.4초·13,667필지**. 배율별 상관이 0.17~0.22로 평평해 봉우리가 없음(1위/2위 1.008 모호함, 면적 +12.08%) → **결정 D2대로 미채택**: 도형 없음, 규제 레이어에서 뺌, manifest에 'D5: 경계 확인 전, 법정동(압구정동) 단위로만 표시'. 의제처리구역 '압구정아파트지구'는 쓰지 않음
- [x] 3-3 면적표 (EPSG:5186, 사업 구역 ±5% 안 → 멈추지 않음)

  | 문서 | 계산 면적 | 고시 면적 | 차이 | 서울플랜+ 비교 (면적 · IoU · 하우스도르프) | 배율 | 상관 (1위/2위) | 판정 |
  |---|---|---|---|---|---|---|---|
  | D1 p18 한양7차 | 22,011.3㎡ | 22,123.6㎡ | −0.51% | (해당 구역 없음) | 0.3521 m/px (막대 −0.4%) | 0.459 (1.57) | 채택 |
  | D9 p12 대청마을 | 90,829.9㎡ | 90,992.0㎡ | −0.18% | 93,493.0㎡ · 0.961 · 16.7m | 0.6777 m/px | 0.489 (2.00) | 채택 |
  | D10 p3 대치동 506 | 77,423.3㎡ | 79,269.1㎡ | −2.33% | 78,634.9㎡ · 0.975 · 5.6m | 1.2394 m/px | 0.692 (1.50) | 채택 |
  | D5 p4 압구정 토허 | 1,288,345.7㎡ | 1,149,476㎡ | +12.08% | (비교 안 함) | 1.0172 m/px (막대 +11.9%) | 0.147 (1.008 모호함) | 미채택 |

  대조 그림: `build/overlay_D1.png`, `build/overlay_D9.png`, `build/overlay_D10.png`, `build/overlay_D5.png`
- [x] D1 경계 안 필지 (`build/align/D1_parcels.csv`, 중심점이 경계 안 6m 이상 = 안쪽)

  | 필지 | 판정 | 경계까지 | 겹침 |
  |---|---|---|---|
  | 528 대 | 안쪽 | 34.3m | 99.7% |
  | 527 대 | 안쪽 | 28.9m | 99.4% |
  | 505 공 | 안쪽 | 14.9m | 65.7% |
  | 508 도 | 경계 걸침(밖) | 3.3m | 47.4% |
  | 529-1 도 | 경계 걸침(밖) | 0.4m | 4.1% |
  | 504 도 | 밖 | 10.3m | 0.0% (도면의 '504 도' 글자는 경계 안이지만 연속지적도의 504는 경계 북쪽 밖 — 도면 그 띠는 연속지적도의 505에 해당) |
- [x] 5 `pipeline/build_map_layers.py` → `public/data/layers/` 사업 2·영향권 4(250·500m 면, note '표시 기준이며 영향의 크기를 뜻하지 않음')·필지 18(포함될 수 있음 2·포함된 것으로 보임 16)·규제 1(D10, 효력 2026.04.01~2028.04.01)·`manifest.json`(실행 시각 없음, 생성 기준일 = DB as_of). 합계 **24,451 B**. 2회 실행 sha256 동일. 라벨용 `short_name`(aliases 첫 값)
- [x] 6 좌표: `fetch_land.py`가 지오코더를 부르지 않고 `seed/parcels.geojson` 중심점을 `location`에 넣음(missing·status 다시 계산). 이 PC `.env`에 운영 `VWORLD_API_KEY`가 비어 있어(HUMAN_TODO 31) 토지 3종을 다시 받지 않는 **`--relocate-only`**(네트워크 없음)로 실행 → 28필지 이동 **0.0~0.2m**, 좌표 밖 토지 값 변화 0건. `seed/project_coords.csv` = 대표 필지(527·619) 중심점
  - `pipeline/patch_coords.py`: `db/propedia.db` → `build/propedia.db.bak` 후 `land_cache.payload`(load_seed와 같은 `json.dumps(land, ensure_ascii=False)`)·`projects.lat/lon/coord_source`(build_projects.project_center와 같은 float 변환)만 갱신 → 원본 PC에서 `run_all`을 돌려도 같은 seed에서 같은 값. 2회 실행 DB sha256 `f7a69960…` 동일. P13 전 DB는 `build/p13/propedia_before.db`
  - 시연 15건 판정 전·후 **모두 같음**: A1·A3 한양7차 possible, A2 주변 66m, A4 주변 293m, B1 모아타운 possible, B2 likely, B3 주변 275m, 나머지 사업 없음, A10 범위 밖
  - `tests/test_lookup.py` 좌표 출처 기대값을 `vworld-2d:LP_PA_CBND_BUBUN representative_point`로 고침 (실시간 조회 `core/live`는 지오코더를 실시간으로만 씀, 그대로)
- [x] 6-4 528번지 불일치 (보고만, 판정·정답셋·DB 그대로): D1 본문 1~17쪽 텍스트에 '528'은 **한 번도 없음**. 위치 표기는 모두 527 — p4 '재건축 정비구역 527번지 일대', p6 '527 일원', p7 '특별계획구역6-1 527 일원'·'I1-1 527 일원', p13 '527번지 일대 (한양7차APT)'. 528은 p18 결정도 그림 속 글자('528 대')뿐인데 경계가 528 전체(겹침 99.7%)를 감쌈

  | 필지 | 도면 대조(3-2) | project_parcels | A2 정답(addresses.yaml) | 지금 응답 |
  |---|---|---|---|---|
  | 압구정동 527 | 안쪽 | representative_only, verified 0 | (A1·A3) possible | possible |
  | 압구정동 528 | 안쪽 | 없음 | nearby (66m) | nearby 66m |

  검수 항목 초안 `seed/review_drafts/D1_parcel_528.json`(review_queue 열 형식, 파이프라인이 읽지 않음) + HUMAN_TODO 36
- [x] 7 `evals/goldset/boundaries.yaml`(draft, 고시 면적 쪽 출처: D1 p4, D9 p2, D10 p1, D5 p1) + `evals/run_eval.py` M19 경계 면적 일치(만든 경계만, D5는 '대상 아님')·M20 GeoJSON 유효성(is_valid·강남구 bbox+600m·필수 속성)
- [x] 8 지도: `web/src/map/layers.ts`(레이어 스펙·색 읽기·라벨·빗금 패턴, 순수 함수) + `MapView.tsx`. 사업 면 32%+선 2px / 영향권 면 8%+점선 1.5px / 규제 45° 빗금(`styleimagemissing`이면 다시 등록)+외곽선 #B07A00 / 필지 외곽선(줌 14 이상, likely 점선). 색은 `--color-layer-*`를 `getComputedStyle`로 읽음. 라벨은 HTML 마커(글리프 서버 없음), `verified=0`이면 '(확인 전)'. `window.__propediaMap`은 개발 서버 또는 `?debug=1`일 때만
- 완료 확인
  - 멱등: `fetch_parcels`(`64a2d534…`), `build_map_layers`(5파일), `patch_coords`(DB `f7a69960…`) 각 2회 sha256 동일. `shapely.ops.transform`(2.2에서 폐기 예정)을 `shapely.transform`으로 바꾼 뒤 경계·레이어 다시 만들어 바이트 동일 확인
  - `python -m evals.run_eval`: M1~M17 이전과 같음(M10 시간 제외), **M19 3/3 (D1 −0.53%, D9 −0.20%, D10 −2.32%, D5 대상 아님)**, **M20 25/25**, 오류 0. M18(`--live`)은 이 PC에 운영 juso·브이월드 키가 없어 재지 않음(이전 기록 20/20)
  - `pytest -q` 123 passed, `npm --prefix web run test` 21 passed(+layers 10), `npm --prefix web run build` 성공
  - `tests/ui_check_map.py` 개발 서버 **27/27**, 빌드본(`--built`, `?debug=1`) **27/27**, 콘솔 오류 0: 레이어 8개(마스크 위·구 경계 아래), 강남구 전체에서 사업·영향권·규제 렌더, 라벨 3개 모두 '확인 전', 빗금 등록, 한양7차(줌 17.6)·대청마을(줌 16.2) 확대 시 필지 외곽선 렌더, 회색 배경 채도 검사
  - 스크린샷 `docs/screens/map_02a_layers_preview.png`(강남구 전체), `map_02b_hanyang7.png`, `map_02c_daecheong.png`
- 남은 문제: D5 경계 없음(HUMAN_TODO 37). 강남구 전체 화면에서 대청마을·D10 라벨이 가까이 붙음(P14 라벨 충돌 처리). 만든 경계 3개(D1·D9·D10) 모두 사람 확인 전(HUMAN_TODO 35)

## P12 지도 셸 — 완료 (2026-11-09)
`/map/`에 강남구 지도: 브이월드 배경 4종, 구 밖 흐림, 법정동 경계·이름, 커서 위치, 3D 토글. `public/*.html`은 건드리지 않음.
- [x] 0단계(P11 뒷정리) 확인: `data_raw/11.공간정보/`·`.env`는 `git status --ignored`에 `!!`로만 나오고 추적 0건·이력 0건. 11-09 로컬 작업은 이미 b5cb3c1(작성자 noreply, `.env.example` 키 값 없음)로 커밋·push돼 있어 새로 만들지 않음. Preview 확인(HUMAN_TODO 32)은 Vercel 로그인이 필요해 아직 열림
- [x] 키·도메인: `core/live/vworld.py`의 고정 `DOMAIN` → `domain()` = `VWORLD_DOMAIN`, 없으면 운영 주소(`DEFAULT_DOMAIN`). `pipeline/check_keys.py`도 같은 함수. 테스트 `test_domain_from_env` 추가
  - `.env`에 `VITE_VWORLD_KEY`(개발 키 값을 출력 없이 복사)·`VWORLD_DOMAIN=http://localhost:3000` 추가(동혁 결정), `.env.example`에 빈 항목. `VWORLD_API_KEY`(운영)는 비어 있음
  - `web/vite.config.ts` `envDir: '..'`(루트 `.env`, 브라우저에는 `VITE_`만), `web/src/vite-env.d.ts`
- [x] MapLibre v6 확인 (버전 그대로 6.17.0 + react-map-gl 8.1.3): v6은 worker를 `import.meta.url` 옆 `maplibre-gl-worker.mjs`에서 찾는데(`node_modules/maplibre-gl/build/readme.md`) Vite 번들에는 그 파일이 없음 → `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'` + `setWorkerUrl(workerUrl)`, react-map-gl에는 `import * as maplibregl` 를 `mapLib`로. worker 번들은 import가 없는 단일 파일이라 그대로 동작. 개발 서버(3000)·빌드본(8000/map/) 모두 worker 오류 0 → 5.x로 내리지 않음
- [x] `pipeline/build_map_base.py`: 브이월드 2D 데이터 `LT_C_ADSIGG_INFO`(sig_cd=11680)·`LT_C_ADEMD_INFO`(emd_cd like 11680) → `public/data/base/gangnam.geojson`(31,848 B)·`bjd.geojson`(94,344 B). 키 `VWORLD_API_KEY`→없으면 `VWORLD_API_KEY_DEV`, domain `VWORLD_DOMAIN`. 원 응답 `build/vworld_raw/` 캐시(`--refresh`로 다시 받음). 응답 속성 `emd_cd`(8자리)·`emd_kor_nm`·`sig_cd`·`sig_kor_nm` `[확인]`, 법정동코드 = emd_cd + "00". 14개 코드·이름이 `seed/bjd_codes.csv`와 같음
  - 멱등: 캐시 2회 + `--refresh` 1회 sha256 동일 (gangnam `f9fbb4bf…`, bjd `ea172ccd…`). 합계 126KB라 단순화 안 함
- [x] 배경지도: WMTS Capabilities 레이어 = `Base`·`midnight`·`Hybrid`(투명 겹침)·`Satellite`(jpeg)·`white` + 해외 도시. **`gray`는 없음**(요청 시 오류 XML) → '회색'은 무채색 `white`(z15 평균 RGB 226·227·225, 채도 차 4). 하이브리드 = Satellite + Hybrid. TileMatrix 6~18 → 소스 maxzoom 18, 지도 줌 11~19. https·CORS `*` 확인. 상수 `web/src/map/basemaps.ts`, 기본값 회색
- [x] `web/src/map/MapView.tsx`(+`MapControls.tsx`, `geo.ts`, `insets.ts`): 첫 화면 fitBounds(패널을 뺀 영역), 줌 11~19, 3D(기울기 60°), 마스크(세계 사각형 − 강남구, 흰색 55%), 구 경계 1.5px, 법정동 0.75px + 이름(HTML 마커 — 외부 글리프 서버 없이 Pretendard), 커서 표시줄, 출처 '배경지도: 국토교통부 브이월드', `movestart/moveend` → `html.map-moving`
  - **maxBounds 대신 중심 제한**: MapLibre maxBounds는 화면 전체(패널 밑 포함)를 경계+2km 안에 넣으려고 줌을 ~13.5로 올려 첫 화면에 강남구 10/14동만 보였음 → `setTransformConstrain`으로 지도 중심을 경계+2km 안에 묶음 (동쪽 끝 127.1242 + 0.0226 → 끌어도 중심 127.147에서 멈춤)
  - 지도는 `lazy()`로 따로 묶음: 초기 JS gzip **81.2KB**(셸), 지도 청크 306.7KB, worker 520KB(비압축). 나누기 전 한 덩어리는 386.8KB였음
- [x] P11 보완: 선택된 작업 탭 아래 `--color-brand-indigo` 2px 막대(`.work-tab[aria-selected=true]::after`), 글자색 잉크 유지, `aria-selected`는 P11부터 있음. '투명도 줄이기' 임시 토글은 그대로, PLAN.md P12·P20에 'P20에서 설정 메뉴로' 기록
- 완료 확인
  - `python -m pipeline.build_map_base` 반복 → sha256 동일
  - `tests/ui_check_map.py`(새, Playwright 1440×900) http://localhost:3000/map/ **18/18**: 라벨 14개, 마스크·경계 레이어, 기본 회색, 첫 화면에 14동 모두 보이는 영역 안, worker 오류 0, 커서 표시줄(위도·경도·법정동), 드래그 중 `map-moving` 붙고 멈추면 떨어짐, 이동 범위, 배경 4종 전환·타일 200(취소 0), 3D, 탭 막대 `rgb(93,52,169)` 2px·글자 잉크, 콘솔 오류 0 → `docs/screens/map_01_base.png`
  - 빌드본 http://127.0.0.1:8000/map/ (`--built`) **18/18**, worker 오류 0. 타일은 127.0.0.1:8000에서도 200(브이월드가 막지 않음, 기록만)
  - `pytest -q` 123 passed (+test_domain_from_env), `npm --prefix web run test` 11 passed(geo·basemaps 6 추가), `npm --prefix web run build` 성공, `oxlint` 경고 0
  - 금지어 검사가 주석의 '늦'을 잡아 고침
- 남은 문제: Preview 확인(HUMAN_TODO 32). 배포 빌드에 `VITE_VWORLD_KEY`가 없으면 배경 없이 경계만 뜸(안내 문구 표시) → HUMAN_TODO 34. 브이월드 'white' 지도에도 지하철 노선 색은 남아 완전한 회색은 아님

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
- [x] 커밋 정리: 11-09 로컬 작업을 별도 커밋(b5cb3c1)으로. `data_raw/11.공간정보/`는 `.gitignore`(서울플랜+ SHP 공공누리 4유형 — 원격에 올리지 않음), 이력에 SHP 0건 확인. `.env.example`은 값 없는 키 + 공개 엔드포인트 URL뿐이라 커밋
- [x] `feat/map-console` push → GitHub 커밋 상태 `Vercel=success "Deployment has completed"` (buildCommand 포함 Preview 빌드 성공, Production main은 그대로: 운영 `/api/v1/health` 200, 운영 `/map/` 404)
- [ ] Preview의 `/map/`·`/api/v1/health` 200 확인 — Preview 주소(`propedia-pretotype-git-feat-map-console-hsp20.vercel.app`)가 Vercel Authentication으로 보호돼 302. 로그인한 브라우저에서 확인 필요 (HUMAN_TODO 32)

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
- 남은 문제: Preview 화면 확인(Vercel 로그인 필요), 정사각 심볼 원본 없음('p'를 잘라 임시로 씀 — 원본을 받으면 교체), 선택된 작업 탭 2px 막대는 PLAN P12 항목으로

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

