# Propedia 강남구 지도 대시보드 — Claude Code 단계별 개발 계획

> 원본: Claude Docs 문서 https://claude.ai/artifact/Q4WwJbBNkfUM7GSG3fQj1p (2026-11-09 기준 내보내기)

Nov 9, 2026 · @영현2

## 한눈에 보기

지금의 FastAPI·SQLite 백엔드와 강남구 고시 DB(문서 10건·항목 41개·사업 2건)는 그대로 두고, 그 위에 강남구 지도를 가운데 둔 새 화면을 React로 얹습니다. 작업은 10단계(P11\~P20)로 나누고, 단계마다 Claude Code에 붙여 넣을 프롬프트와 완료 확인 방법을 적었습니다.

| 항목 | 추천 | 이유 |
| --- | --- | --- |
| 화면 구조 | 상단 검색 바 · 좌측 레이어 패널 · 가운데 지도 · 우측 인스펙터 · 하단 타임라인 | 참고 이미지의 팔란티어 구조를 흰색 글래스 톤으로 옮김 |
| 프론트엔드 | Vite + React + TypeScript, Tailwind CSS, Zustand, TanStack Query | 서버 렌더링이 필요 없는 지도 콘솔이라 Next.js보다 단순 |
| 지도 | MapLibre GL JS + 브이월드 배경지도·용도지역·지적도 | 이미 쓰는 브이월드 키 재사용, 레이어를 자유롭게 겹칠 수 있음 |
| 데이터 | 고시 DB → 빌드 때 GeoJSON 생성, 공공데이터(학교·상가·아파트·실거래) 추가 | 모든 표시에 근거·기준일을 붙이는 원칙 유지 |
| 백엔드 | 기존 FastAPI에 지도용 API 몇 개 추가, `core/`는 표준 라이브러리만 | pytest 121개와 평가 지표 M1\~M18을 그대로 회귀 검사로 씀 |
| 배포 | 같은 Vercel 프로젝트, 새 화면은 `/map/`에서 시작해 마지막에 첫 화면으로 | 기존 시연 경로를 깨지 않음 |
| 일정 | 약 4\~5주 (하루 3\~4시간 작업 가정, 추정) | P16이 끝나면 시연 가능한 첫 버전 |

1. P11 작업 기반: 새 브랜치, `web/` 프로젝트, 디자인 토큰, 규칙 갱신
2. P12 지도 셸: 배경지도, 강남구 경계·법정동, 카메라
3. P13 Propedia 레이어 빌드: 사업 구역·영향권·규제 구역 GeoJSON
4. P14 좌측 레이어 패널: 켜기/끄기, 투명도, 겹침 보기, 범례
5. P15 공식 참고 레이어와 지도 아무 곳 클릭 → 필지 조회
6. P16 우측 인스펙터: 사업 단계·남은 단계·기한·원문 보기 (첫 시연 가능)
7. P17 아파트 단지와 실거래가 이력
8. P18 학교·지하철역·편의시설 레이어
9. P19 하단 타임라인과 고시 피드
10. P20 다듬기·테스트·배포

## 지금 프리토타입에서 가져갈 것과 바꿀 것

지도에 바로 올릴 수 있는 것은 사업 2건의 중심 좌표, 사업 필지 18개(PNU), 토지 정보 28필지입니다. 없는 것은 사업·규제 구역의 **경계선**, 생활 인프라, 아파트와 실거래 데이터입니다. (`db/propedia.db` 2026-10-26 빌드 기준)

| 자산 | 지금 상태 | 지도에서 쓰는 곳 | 해야 할 일 |
| --- | --- | --- | --- |
| 고시·계획 문서 | 10건(D1\~D10), 쓰는 쪽 133개, 쪽 이미지 `public/pages/` | 인스펙터 ‘원문 보기’, 타임라인, 고시 피드 | 그대로 |
| 항목(`applicability_rules`) | 41개 (적용 16 · 배경 25) | 법정동·구·서울 전역 칩, 필지 인스펙터 | 그대로 |
| 사업(`projects`) | 2건: 한양7차 재건축(압구정동 527, 13단계 중 2번째, 공람 2026.10.06\~11.06) · 대청마을 북측 모아타운(일원동 619, 8단계 중 1번째, 공람 2026.04.17\~05.01 마감) | 사업 구역 폴리곤·영향권·인스펙터 | 구역 경계가 없음 → P13에서 도면 대조로 만듦 |
| 사업 필지(`project_parcels`) | 18개: 대표 지번 2 + 대청마을 지도 대조 후보 16, 모두 사람 확인 전(`verified=0`) | 포함 판정 색을 입힌 필지 | 연속지적도에서 필지 경계를 받음 |
| 사업 사실(`project_facts`) | 16개 (면적·세대수·용적률·종상향, 근거 쪽 포함) | 인스펙터 ‘고시에 적힌 수치’ | 그대로 |
| 단계 템플릿 | 21행 (재건축 13 + 모아타운 8) | 진행 단계 바, ‘앞으로 N단계’ | 그대로 (문구는 법령 대조 전 초안) |
| 토지 정보 캐시·건축물 요약 | 각 28필지 (지목·면적·용도지역·지역지구·공시지가·좌표) | 필지 인스펙터 | 지도 클릭 조회는 실시간으로 |
| 실시간 조회 `core/live/` | 브이월드 토지 3종·지오코더, 도로명주소 (4초·재시도 1회) | 검색 바, 필지 클릭 | 연속지적도 점 조회 1개 추가 |
| 시연 주소 | 15건 (A1\~A10, B1\~B5) | 검색 바 바로가기 | 그대로 |
| 테스트·평가 | pytest 121개, `tests/ui_check.py` 50항목, 지표 M1\~M18 | 회귀 방지 | 지도용 테스트 추가 |

지도화에 비어 있는 데이터:

- 사업 구역 경계: D1·D9 모두 지번 조서가 없고 도면(쪽 이미지)만 있음. D9는 `pipeline/daecheong_map.py`에 경계 꼭짓점 10개를 이미 읽어 둔 상태
- 규제 구역 경계: D5 압구정 아파트지구 1,149,476㎡, D10 대치동 506 일대 79,269.1㎡ (지형도면은 이미지뿐)
- 강남구·법정동 경계, 학교·지하철역·편의시설·공원
- 아파트 단지 목록·경계, 실거래가 이력
- 공식 도시계획 레이어: 토지 정보에는 필지별 이름만 있음 (예: 28필지 중 27필지가 지구단위계획구역)

바꿀 규칙 (자세한 결정은 ‘먼저 정해야 할 것’):

- ‘화면은 빌드 도구·외부 CDN 없이’(agents.md §12-1) → 지도 화면은 Vite로 묶어 배포. 외부 CDN은 계속 쓰지 않고, 외부 호출은 지도 타일만 허용
- 대상 사용자: 토지 소유자 → 개인 투자자. ‘판단하지 않고 사실만’ 원칙을 어디까지 유지할지 팀 결정 필요
- 첫 화면: 주소 입력창 → 지도

## 목표 화면

한 화면을 다섯 영역으로 나눕니다: 상단 바(56px), 좌측 레이어 패널(320px), 가운데 지도, 우측 인스펙터(400px), 하단 타임라인(접힘 44px / 펼침 200px). 패널은 지도 위에 떠 있는 글래스 카드이고, 지도는 화면 전체를 채웁니다.

> 그림: 화면 배치 · 5개 영역 (원본 문서에 있음)

선택한 사업은 지도·콜아웃·인스펙터에 같은 강조색으로 이어지고, 하단 타임라인은 44px로 접혀 있다가 200px로 펼쳐집니다.

참고 이미지(2\~6번)에서는 배치와 상호작용 방식만 가져옵니다. 팔란티어의 이름·로고·색은 쓰지 않습니다.

| 참고 이미지의 요소 | Propedia에서 | 단계 |
| --- | --- | --- |
| 하단 Timeline (재생·스크러버, 계열별 막대) — 2번 | 고시 발행일·공람 기간·효력 기간·사업 단계 이력을 계열별 막대로. 날짜를 옮기면 ‘그날 기준’ 지도 | P19 |
| 좌측 패널의 탭 (Unmanned / Planes / Satellite) — 2번 | 좌측 패널 탭: 레이어 · 사업 목록 · 고시 피드 | P14 |
| 상단 작업 탭과 검색(Ctrl+Space) — 2·5번 | 상단 작업 탭(강남구 전체 / 선택한 사업), 명령 팔레트 Ctrl+K | P14 |
| LAYER STACK 체크박스 — 6번 | 레이어 켜기/끄기 + 투명도 + 건수 | P14 |
| SYSTEM HEALTH — 6번 | 데이터 상태: 레이어별 기준일·원천·건수 | P14 |
| 자산 목록과 상태 배지(READY / ERROR / IN USE) — 5번 | 사업 목록과 상태 배지(공람 중 / 공람 마감 / 승인 고시 미확인) | P16 |
| Request Status 단계 표시(sent → received → approved) — 5번 | 사업 진행 단계 스테퍼(현재 단계, 다음 단계, 남은 단계 수) | P16 |
| AI ASSESSMENT + HUMAN AUTHORIZATION REQUIRED — 6번 | ‘지도 대조 후보 · 사람 확인 전’ 배지 (기존 `likely`·검수 큐) | P16 |
| 지도 위 콜아웃 카드(선으로 연결) — 6번 | 선택한 대상 옆 미니 카드(이름·단계·D-day) | P16 |
| 지도 위 심볼(School, Church, Roadblock)·경로 — 5번 | 학교·역·편의시설 심볼, 거리·반경 측정 도구 | P18 |
| 이벤트 피드·다중 패널 — 3·4번 | 고시 피드(최신순, D-day), 상단 기준일 표시 | P19 |

상호작용 규칙:

- **클릭 우선순위**: 사업 구역 → 규제 구역 → 아파트 단지 → 학교·역·편의시설 → 빈 곳(필지 조회). 겹친 곳을 누르면 작은 선택 목록을 띄움
- **호버**: 이름 + 한 줄 상태 툴팁 (예: ‘한양7차 재건축 · 2/13단계 · 공람 마감’)
- **선택**: 외곽선 강조 + 우측 인스펙터 열림 + 주소창 URL 갱신(`?sel=project:1`) → 링크로 같은 화면 공유
- **겹침 보기**: ‘영향권’과 ‘아파트 단지’를 함께 켜면 영향권 안 단지만 진하게, 나머지는 흐리게. 학교·편의시설도 같은 방식
- **검색 바**: 주소·지번·사업명·단지명 → 후보 목록 → 지도 이동 + 인스펙터. 기존 `/api/v1/lookup`을 재사용
- **키보드**: Ctrl+K 검색, L 레이어 패널, I 인스펙터, T 타임라인, Esc 선택 해제

인스펙터에 보여 줄 내용 (대상별):

| 누른 대상 | 보여 줄 것 | 데이터 |
| --- | --- | --- |
| 사업 구역 | 사업 종류 · 단계 스테퍼(예: 재건축 13단계 중 2번째, 앞으로 11단계, 다음 ‘정비구역 지정 고시’) · 기한 D-day · 고시 수치 · 포함 필지 · 원문 보기 | 기존 `/api/v1/projects/{id}/progress` |
| 규제 구역 | 효력 기간·상태 배지, 대상 기준, 근거 문장, 원문 쪽 | `applicability_rules` |
| 빈 곳(필지) | 토지 정보, 건축물 요약, 이 필지에 걸린 고시(4개 층), 주변 500m 사업 | 기존 `/api/v1/lookup` |
| 아파트 단지 | 세대수·사용승인일, 전용면적대별 실거래가 차트, 최근 거래 표(해제 건 표시), 영향권 안 사업 | 새 `market.db` (P17) |
| 학교·역·편의시설 | 이름·분류·주소·원천·기준일 | 새 GeoJSON (P18) |

‘남은 단계 수’는 템플릿에서 세는 사실이라 보여 주고, ‘남은 기간’은 지금처럼 ‘비교할 사례가 부족합니다’로 둡니다.

## 디자인 시스템

로고 글자의 그라디언트는 하늘색 #4AB2E6 → 인디고 #5D34A9 → 플럼 #7A2690입니다(프로젝트의 `로고.jpg`에서 픽셀을 재어 측정). 화면은 흰 바탕 지도 위에 반투명 흰 유리 패널을 띄우고, 브랜드 색은 선택·강조·사업 레이어에만 씁니다.

### 브랜드 색 (측정값)

| 로고 위치 | 색 | OKLCH | 흰 바탕 대비 | 쓰는 곳 |
| --- | --- | --- | --- | --- |
| 시작 (p) | #4AB2E6 | 0.725 0.121 234 | 2.39:1 | 그라디언트 시작·장식. 글자에는 쓰지 않음 |
| 28% | #5171C5 | 0.565 0.135 266 | 4.65:1 | 보조 링크·아이콘 |
| 52% | #5D34A9 | 0.444 0.177 294 | 8.30:1 | 주 색: 주 버튼, 선택 상태, 사업 구역 |
| 76% | #6E289E | 0.441 0.182 308 | 8.54:1 | 그라디언트 |
| 끝 (a) | #7A2690 | 0.445 0.175 318 | 8.37:1 | 그라디언트 끝 |

로고 파일이 204×102px JPG라 압축 오차가 있습니다. 원본(SVG·AI·고해상도 PNG)을 받으면 같은 방법으로 다시 재고 토큰만 바꿉니다.

> 2026-11-09 P11 재측정 (`logo/propedia_logo_transparent.png` 2348×586): 0% #49BFFA(ΔE2000 3.7) · 28% #4064B8(5.1) · 52% #592298(4.5) · 76% #5C1A7B(6.5) · 100% #75105E(10.2). 모두 ΔE 3 이상이지만 **토큰은 위 값 유지**로 결정(지도 3색 검사를 통과한 값). 측정 방법·표는 PROGRESS.md P11.

```css
/* web/src/styles/tokens.css — Tailwind v4 */
@import "tailwindcss";

@theme {
  --color-brand-sky: #4ab2e6;
  --color-brand-blue: #5171c5;
  --color-brand-indigo: #5d34a9;   /* primary */
  --color-brand-purple: #6e289e;
  --color-brand-plum: #7a2690;
  --color-ink: #1f2328;
  --color-ink-muted: #5b6270;
  --color-layer-project: #5d34a9;    /* 사업 구역·영향권 */
  --color-layer-apartment: #e0567a;  /* 아파트 단지 */
  --color-layer-regulation: #eda100; /* 규제 구역 (빗금과 함께) */
  --font-sans: "Pretendard Variable", "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
}

:root {
  --brand-gradient: linear-gradient(90deg, #4ab2e6 0%, #5171c5 28%, #5d34a9 52%, #6e289e 76%, #7a2690 100%);
  --glass-bg: rgb(255 255 255 / 0.62);
  --glass-border: rgb(255 255 255 / 0.72);
  --glass-blur: 18px;
  --glass-radius: 20px;
  --glass-shadow: 0 8px 32px rgb(31 35 40 / 0.12), inset 0 1px 0 rgb(255 255 255 / 0.85);
}
```

### 글래스와 리퀴드 글래스 규칙

1. **기본 글래스(모든 브라우저)**: `backdrop-filter: blur(18px) saturate(160%)`에 `-webkit-` 접두어를 함께 씁니다. 배경 흰색 62%, 테두리 1px 흰색 72%, 위쪽 안쪽 하이라이트, 모서리 20px.
2. **리퀴드 글래스(크롬 계열에서만)**: SVG `feDisplacementMap`을 `backdrop-filter: url(#lg)`로 걸어 가장자리 굴절을 넣습니다. Safari·Firefox는 이 필터를 아예 그리지 않고 `@supports`로도 걸러지지 않으므로, JS로 크롬 계열을 확인해 클래스를 붙입니다. 버튼·토글 칩·선택된 카드 같은 작은 요소에만 씁니다.
3. **지도 위 성능**: 지도는 매 프레임 다시 그려져 패널의 blur도 매번 계산됩니다. 드래그·확대 중에는 `.map-moving` 클래스로 blur를 8px로 낮추고 굴절을 끕니다. 동시에 띄우는 글래스 패널은 4개 이하.
4. **읽힘**: 패널 안 글자는 잉크 #1F2328만 쓰고 본문 대비 4.5:1 이상. 배경지도를 회색·밝게 두어 유리 뒤 대비가 들쭉날쭉하지 않게 합니다.
5. **투명도 줄이기**: `prefers-reduced-transparency`는 Safari가 지원하지 않고 Firefox는 꺼져 있어, 설정 메뉴에 ‘투명도 줄이기’(불투명 패널) 스위치를 둡니다. `prefers-reduced-motion`이면 애니메이션을 끕니다.
6. **구현 함정**: `backdrop-filter`는 포함 블록을 만들어 안쪽의 `position: fixed`가 어긋납니다. 툴팁·모달은 포털로 `body`에 띄웁니다.

### 지도 레이어 모양

| 레이어 | 모양 | 색 | 색 외 표시 |
| --- | --- | --- | --- |
| 사업 구역 (고시 근거) | 면 32% + 외곽선 2px | #5D34A9 | 사업명·단계 라벨, 선택 시 그라디언트 글로우 |
| 영향권 250m·500m | 면 8% + 점선 1.5px | #5D34A9 | 범례에 ‘표시 기준’ 문구 |
| 포함 판정 필지 | 외곽선만: 포함 실선, 포함된 것으로 보임 점선, 대표 지번 핀 | #5D34A9 | 판정 배지 |
| 규제 구역 (토허제·개발행위허가 제한) | 45° 빗금 + 외곽선 | #EDA100 (외곽선 #B07A00) | 라벨 + 효력 기간 |
| 아파트 단지 | 면 28% + 외곽선 1px | #E0567A | 단지명 라벨(줌 15 이상) |
| 학교·역·편의시설 | 흰 원형 칩 + 아이콘 | 잉크 #1F2328 | 아이콘 모양 + 이름(줌 16 이상) |
| 공식 참고 (서울플랜+ 사업, 용도지역) | 원본 색 또는 회색 점선 | 원본 | ‘참고’ 배지 |

지도 3색(#5D34A9·#E0567A·#EDA100)은 색 조합 검사 스크립트로 모든 쌍을 비교해 통과했습니다(색각 이상 ΔE 최저 17.3, 일반 시각 최저 22.3). 앰버는 흰 바탕 대비가 2.11:1이라 빗금·진한 외곽선·라벨을 반드시 같이 씁니다. 학교·역·편의시설은 색을 늘리지 않고 아이콘 모양으로 구분합니다.

글꼴은 Pretendard를 npm 패키지로 앱에 묶어 외부 CDN 없이 씁니다. 숫자는 `tabular-nums`, PNU는 고정폭 글꼴. 로고는 P11에서 `로고.jpg`의 흰 배경을 투명하게 바꿔 임시로 쓰고, 원본을 받으면 교체합니다.

## 데이터 레이어 카탈로그

지도 레이어는 세 등급으로 나눕니다. ① **Propedia 검증 레이어**: 우리 고시 DB에서 나오고 근거 쪽이 붙음. ② **공식 참고 레이어**: 공공기관 공간정보를 그대로 보여 줌(‘참고’ 배지). ③ **시장·생활 레이어**: 아파트·실거래·학교·역·편의시설.

| 등급 | 레이어 | 원천 | 수집 | 형태 | 지금 | 단계 |
| --- | --- | --- | --- | --- | --- | --- |
| 기본 | 배경지도 (기본·회색·위성·하이브리드) | 브이월드 WMTS, 공공누리 1유형(출처표시) | 실시간 타일 | 래스터 | 없음 | P12 |
| 기본 | 강남구 경계·법정동 14개 | 브이월드 2D 데이터 `lt_c_adsigg_info`·`lt_c_ademd_info` | 빌드 1회 | GeoJSON | 없음 | P12 |
| ① | 사업 구역 2건 | 고시 도면(D1 18\~21쪽, D9 12쪽) × 연속지적도 대조 | 빌드 | GeoJSON | 경계 없음(D9 꼭짓점 10개만 있음) | P13 |
| ① | 영향권 250m·500m | 사업 구역에서 계산 | 빌드 | GeoJSON | 없음 | P13 |
| ① | 포함 판정 필지 18개 | `project_parcels` + 연속지적도 `LP_PA_CBND_BUBUN` | 빌드 | GeoJSON | PNU만 | P13 |
| ① | 규제 구역: D5 압구정 아파트지구(1,149,476㎡), D10 대치동 506 일대(79,269.1㎡) | 고시 지형도면 대조, 안 되면 공식 참고 경계 | 빌드 | GeoJSON | 없음 | P13 |
| ① | 서울 전역·구 단위 고시 (D6·D7·D8 등) | `applicability_rules` | 앱 실행 때 API | 상단 바 칩 | 있음 | P14 |
| ② | 서울시 도시계획사업 현황(재개발·재건축·신속통합기획·모아타운 등) | [서울 열린데이터광장 OA-22712](https://data.seoul.go.kr/dataList/OA-22712/F/1/datasetView.do) SHP, 반기 갱신, 공공누리 4유형 | 빌드(사람이 내려받음) | GeoJSON | 없음 | P15 |
| ② | 의제처리구역(정비구역·아파트지구·택지개발지구 등 16종) | [서울특별시 의제처리구역 위치정보](https://www.data.go.kr/dcat/metadata/15082965), 출처표시 | 빌드 | GeoJSON | 없음 | P15 |
| ② | 용도지역·지구단위계획구역 등 | 브이월드 WMS (레이어명은 P15에서 확인) | 실시간 타일 | 래스터 | 없음 | P15 |
| ② | 지적도(필지 경계) | 브이월드 WMS `lp_pa_cbnd_bubun` (줌 16 이상) | 실시간 타일 | 래스터 | 없음 | P15 |
| ② | 클릭한 필지의 토지 정보 | 2D 데이터 점 조회 → 기존 `core/live` 토지 3종 | 실시간 API | JSON | 토지 3종 있음 | P15 |
| ③ | 아파트 단지(목록·세대수·사용승인일) | 국토부 공동주택 단지 목록 · [기본 정보(AptBasisInfoServiceV5)](https://www.data.go.kr/en/data/15058453/openapi.do) | 빌드(월 1회) | GeoJSON + DB | 없음 | P17 |
| ③ | 아파트 매매 실거래가 | [국토부 아파트 매매 실거래가 상세 자료](https://www.data.go.kr/en/data/15126468/openapi.do): 지역코드 5자리(11680)·계약년월 6자리, 개발계정 10,000건, 이용허락 제한 없음 | 빌드(주 1회) | `db/market.db` | 없음 | P17 |
| ③ | 학교(초·중·고) | [전국초중등학교위치표준데이터](https://www.data.go.kr/data/15021148/standard.do) (위도·경도 포함) | 빌드 | GeoJSON | 없음 | P18 |
| ③ | 초등학교 통학구역(선택) | 한국교육시설안전원 학구도 SHP (매년 3월·9월 배포) | 빌드 | GeoJSON | 없음 | P18 |
| ③ | 편의시설(마트·편의점·병원·약국·카페 등) | [소상공인시장진흥공단 상가(상권)정보](https://www.data.go.kr/catalog/15083033/fileData.json): 분기 갱신, 경도·위도·업종 포함, 이용허락 제한 없음 | 빌드 | GeoJSON | 없음 | P18 |
| ③ | 지하철역 | 서울시 역사마스터 정보(좌표) | 빌드 | GeoJSON | 없음 | P18 |

모든 빌드 산출 GeoJSON은 `public/data/layers/`에 두고, 같은 폴더의 `manifest.json`에 레이어별 원천·기준일·건수·라이선스를 적습니다. Propedia 레이어의 도형 속성은 아래 형식을 지킵니다.

```json
{
  "type": "Feature",
  "properties": {
    "id": "project:1",
    "kind": "project",
    "name": "압구정아파트지구 특별계획구역6-1 재건축 정비구역",
    "stage_code": "RB02",
    "stage_label": "재건축 13단계 중 2번째",
    "basis": "map_reading",
    "verified": 0,
    "doc_ids": ["D1"],
    "as_of": "2026-10-06",
    "area_m2_doc": 22123.6,
    "area_m2_geom": null
  },
  "geometry": { "type": "Polygon", "coordinates": [] }
}
```

꼭 지켜야 할 데이터 조건:

- **브이월드 지오코더 결과는 저장 금지**: 공공데이터포털 안내에 따르면 하루 최대 40,000건이고 실시간으로만 써야 하며 별도 저장장치나 DB에 저장할 수 없습니다 ([지오코더 API](https://www.data.go.kr/data/15101106/openapi.do)). 그래서 지도에 저장하는 좌표는 필지 경계(2D 데이터)의 중심점이나 좌표가 들어 있는 공개 데이터에서 가져옵니다. 지금 `seed/land_cache.json`에 저장된 `location`(지오코더 결과)도 P13에서 필지 중심점으로 바꿉니다.
- **서울플랜+ 사업 현황 SHP는 공공누리 4유형(비상업·변경금지)**: 프로토타입 시연에만 쓰고 도형을 단순화·재가공하지 않습니다. 유료화 전에는 서울시에 이용을 문의하거나 출처표시 조건인 의제처리구역 데이터로 바꿉니다.
- **실거래가는 공공데이터포털 API로만**: 실거래가 공개시스템(rt.molit.go.kr)은 스크래핑·크롤링을 금지하고, 대량 이용은 공공데이터포털을 쓰라고 안내합니다. KB·포털 시세는 쓰지 않습니다.
- **소유자 정보 없음**: 브이월드 토지소유정보 API는 계속 쓰지 않습니다(feedback2 §2-5).

## 기술 스택·구조

백엔드(FastAPI + SQLite 읽기 전용 + `core/live`)는 그대로 두고, 지도 화면만 `web/` 폴더의 Vite + React 앱으로 더합니다. 빌드 결과는 `public/map/`으로 나가고, Vercel은 `public/**`를 CDN으로 서빙하므로 배포 구조가 바뀌지 않습니다.

> 그림: 구조 · 실행 중 호출과 빌드 흐름 (원본 문서에 있음)

브라우저는 CDN·FastAPI·브이월드 타일 세 곳만 부르고, 공공데이터 수집과 도형 계산은 개발 PC에서 빌드 때 끝내 커밋합니다.

| 구분 | 선택 | 비고 |
| --- | --- | --- |
| 빌드 도구 | Vite 8 + React + TypeScript (`react-ts` 템플릿) | Node.js 20.19+ 또는 22.12+ 필요 |
| 스타일 | Tailwind CSS v4 (`@tailwindcss/vite`, CSS의 `@theme`에 토큰) | tailwind.config.js 없음 |
| 지도 | MapLibre GL JS + `react-map-gl/maplibre` (v8) | MapLibre v6(2026.7)부터 WebGL2 필수·ESM 전용. react-map-gl 8.1 계열이 MapLibre v4·v5·v6을 지원(v6은 named/namespace import와 번들러용 worker 설정 필요). P12에서 확인하고, 안 되면 5.x로 고정 |
| 상태 | Zustand(레이어·선택·날짜) + TanStack Query(API 캐시) | URL에 상태 동기화 |
| 차트 | d3-scale + d3-shape로 직접 그린 SVG | 실거래 선·막대 2종만 필요 |
| 아이콘·글꼴 | lucide-react, Pretendard(npm) | 외부 CDN 없음 |
| 도형 계산(빌드) | shapely + pyproj (`requirements-build.txt`) | 영향권 버퍼는 EPSG:5186(미터)에서 계산 |
| 백엔드 | 기존 FastAPI, `core/`는 표준 라이브러리만 | 외부 호출은 `core/live/`만 |
| 테스트 | pytest(기존) + Vitest(프론트 로직) + Playwright Python(`tests/ui_check_map.py`) | 기존 `ui_check.py` 방식 그대로 |

폴더 구조 (새로 생기거나 바뀌는 것만):

```text
propedia-pretotype/
  docs/map/PLAN.md              # 이 문서의 내보내기 (Claude Code 작업 지시서)
  .claude/settings.json         # 권한 규칙
  .claude/rules/web.md          # web/** 를 만질 때만 읽히는 프론트 규칙
  .claude/rules/pipeline.md     # pipeline/** 규칙 (키 출력 금지, 원본 수정 금지, 멱등)
  web/
    vite.config.ts              # base '/map/', outDir '../public/map', /api·/pages·/data 프록시
    src/app/App.tsx
    src/map/MapView.tsx         # MapLibre, 배경지도, 마스크
    src/map/layers/*.ts         # 레이어별 스타일 정의
    src/panels/                 # TopBar, LayerPanel, Inspector, Timeline, Feed
    src/inspector/              # ProjectView, RegulationView, ParcelView, ApartmentView, PoiView
    src/ui/                     # GlassPanel, Badge, Stepper, EvidenceModal
    src/state/useMapStore.ts
    src/api/client.ts
    src/styles/tokens.css, glass.css
  core/map.py                   # 레이어 목록·인스펙터 조립 (표준 라이브러리)
  core/live/vworld.py           # parcel_at(lat, lon) 추가
  pipeline/build_map_base.py    # 강남구·법정동 경계
  pipeline/fetch_parcels.py     # PNU → 필지 경계
  pipeline/build_map_layers.py  # 사업·영향권·규제·manifest
  pipeline/fetch_apartments.py, fetch_trades.py, fetch_pois.py
  public/map/                   # 빌드 산출 (직접 수정 금지)
  public/data/base/*.geojson, public/data/layers/*.geojson, manifest.json
  db/market.db                  # 실거래 (읽기 전용)
  tests/test_map_*.py, tests/ui_check_map.py, web/src/**/*.test.ts
```

추가 API (기존 13개는 그대로):

| 메서드·경로 | 돌려주는 것 | 단계 |
| --- | --- | --- |
| `GET /api/v1/map/manifest` | 레이어 목록, 원천, 기준일, 건수, 라이선스 | P14 |
| `GET /api/v1/map/feature/{kind}/{id}` | 인스펙터 내용 (사업은 기존 progress 재사용) | P16 |
| `GET /api/v1/map/parcel-at?lat=&lon=` | 클릭 지점 필지의 PNU·경계·토지 정보 | P15 |
| `GET /api/v1/apartments/{id}` | 단지 기본정보·거래 요약 | P17 |
| `GET /api/v1/apartments/{id}/trades?band=&from=` | 면적대별 월별 중위 거래가·건수, 최근 거래 | P17 |
| `GET /api/v1/timeline?from=&to=` | 고시 발행·공람·효력·단계 이벤트 | P19 |
| `GET /api/v1/feed?limit=` | 최신 고시 목록과 D-day | P19 |

개발·배포 설정:

```ts
// web/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/map/',
  plugins: [react(), tailwindcss()],
  build: { outDir: '../public/map', emptyOutDir: true },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/pages': 'http://127.0.0.1:8000',
      '/data': 'http://127.0.0.1:8000',
    },
  },
})
```

```json
{
  "regions": ["icn1"],
  "buildCommand": "npm --prefix web ci && npm --prefix web run build"
}
```

- 개발 중에는 터미널 2개: `python -m uvicorn api.index:app --port 8000 --reload`와 `npm --prefix web run dev`(http://localhost:5173/map/).
- Vercel은 FastAPI 프로젝트에서도 `public/**`를 CDN으로 서빙하고, `vercel.json`의 Build Command가 우선합니다. P11에서 Preview 배포로 `/map/`이 열리는지 먼저 확인하고, 빌드가 막히면 `public/map/`을 커밋하는 방식(지금 `db/propedia.db`를 커밋하는 것과 같은 방식)으로 돌아갑니다.
- 브이월드 키: 토지·2D 데이터 호출은 서버(`core/live`)에서만. 배경지도·WMS 타일 주소에는 키가 브라우저에 드러나므로 서비스 URL 제한에 기대고, 가능하면 브라우저용 키를 따로 발급합니다(`VITE_VWORLD_KEY`).
- 성능 예산: 초기 JS(gzip) 400KB 이하, 레이어 GeoJSON 합계 2MB 이하, DB API p95 300ms 이하, 실시간 필지 조회 p95 2초 이하.

## 먼저 정해야 할 것

개발을 시작하기 전에 아래 6가지를 팀에서 정해 `docs/map/PLAN.md`에 적어 두면, Claude Code가 단계마다 같은 기준으로 작업합니다. 추천안을 기본값으로 두었습니다.

| 결정 | 추천안 | 이유 |
| --- | --- | --- |
| ‘사실만 보여주고 판단하지 않는다’ 원칙 | 투자자용으로 바뀌어도 유지. 점수·등급·추천·예측은 만들지 않고, 모든 표시에 근거 쪽·기준일을 붙임 | 팔란티어처럼 ‘보여주되 판단은 사용자가’. 기존 테스트·평가 체계를 그대로 쓸 수 있음 |
| 금지어와 ‘투자’라는 말 | 시스템이 만드는 문장은 기존 금지어 유지 + ‘시세’ 추가. 브랜드 소개 문구는 별도 파일(`web/src/copy/brand.ts`)에 두고 검사 예외로 | agents.md §9-6 금지어에 ‘투자’가 들어 있어 테스트가 깨짐 |
| ‘영향권’의 정의 | 사업 구역 경계에서 250m·500m. 범례에 ‘Propedia 표시 기준이며 영향의 크기를 뜻하지 않음’ | 기존 ‘주변 500m 사업’ 규칙과 같은 숫자 |
| ‘과거 시세’의 범위 | 국토부 신고 실거래가만(계약일 기준, 해제 거래 표시). 시세 추정치는 쓰지 않음 | 라이선스가 분명하고 원자료 그대로 보여 줄 수 있음 |
| 라이선스와 상용화 | 지금은 비상업 프로토타입으로 진행. 유료화 전에 ① 서울플랜+ SHP(4유형) 대체·문의 ② Vercel Hobby→Pro 전환 ③ 브이월드 이용 조건 재확인 | Vercel Hobby는 비상업·개인 용도 조건(README 기록) |
| 첫 화면 | P16까지는 `/map/`에서 따로, P20에서 `/`를 지도로 바꿈. 기존 주소 조회·문서 DB 화면은 ‘근거 상세’로 유지 | 시연 경로·ui\_check 50항목을 깨지 않음 |

사람이 준비할 것 (`HUMAN_TODO.md`에 추가):

- [ ] 로고 원본 파일(SVG·AI·고해상도 PNG) 전달
- [ ] 공공데이터포털 활용신청: 아파트 매매 실거래가 상세, 공동주택 단지 목록·기본 정보, 상가(상권)정보 (기존 `DATA_GO_KR_SERVICE_KEY`에 서비스 추가)
- [ ] 브이월드: 개발용 서비스 URL(localhost) 등록 가능 여부 확인, 브라우저용 키 분리 발급
- [ ] 서울 열린데이터광장에서 서울플랜+ SHP·의제처리구역 SHP를 내려받아 `../data/11.공간정보/`에 두기 (파일 수정 금지)
- [ ] 위 결정 6개 확정 (영현·동혁)

## Claude Code 작업 환경 (VS Code)

지금 저장소가 쓰는 ‘지시서 → 단계 → 완료 확인 → PROGRESS 기록 → 커밋’ 방식을 그대로 잇고, 지시서만 가볍게 다시 짜는 것이 핵심입니다.

1. **설치**: VS Code Extensions에서 ‘Claude Code’를 검색해 설치하고 로그인합니다. Node.js 22 LTS(Vite 8은 20.19+ 또는 22.12+ 필요), Python 3.11+, 터미널은 기존처럼 Git Bash.
2. **브랜치**: `git switch -c feat/map-console`. main은 지금 배포본으로 둡니다.
3. **지시서 정리**: 공식 문서는 CLAUDE.md를 200줄 이하로 권하고, `@` 임포트한 파일도 매 세션 통째로 컨텍스트에 들어갑니다. 지금 CLAUDE.md는 긴 `agents.md`를 `@agents.md`로 통째로 불러오므로, 아래처럼 짧게 바꾸고 agents.md는 필요할 때만 읽게 합니다. CLAUDE.md가 있으면 AGENTS.md는 기본 설정에서 따로 읽히지 않으므로 @agents.md 줄만 빼면 됩니다.
4. **이 문서를 저장소에**: 이 문서를 Markdown으로 내보내 `docs/map/PLAN.md`로 둡니다.
5. **권한 규칙**: `.claude/settings.json`을 커밋합니다. 규칙은 deny → ask → allow 순서로 판정되어 allow로 deny를 뚫을 수 없습니다. 다만 Read deny는 Claude의 파일 도구와 cat 같은 명령에만 걸리고, 파일을 직접 여는 Python 스크립트에는 걸리지 않습니다.

```markdown
# CLAUDE.md — Propedia 프리토타입

## 지금 하는 일
- 지도 대시보드 P11~P20: docs/map/PLAN.md를 따른다. 단계 순서대로, 단계마다 '완료 확인'을 통과해야 다음으로 간다.
- 진행 기록은 PROGRESS.md, 사람 확인은 HUMAN_TODO.md.
- 데이터·추출·조회 규칙의 원문은 agents.md다. 필요한 절만 찾아 읽는다.

## 절대 규칙
1. 사실만 보여 준다. 점수·등급·추천·예측 금지. 모든 표시에 문서·쪽·기준일.
2. 시스템 문장에 금지어(agents.md §9-6 + '시세') 금지. tests/test_wording.py가 web/src도 검사한다.
3. .env 키 값을 출력·로그·커밋하지 않는다.
4. ../data/ 원본은 수정·이동·삭제 금지.
5. core/는 표준 라이브러리만. 외부 호출은 core/live/에서만.
6. 브이월드 지오코더 결과는 저장하지 않는다. 지도 좌표는 필지 경계 중심점.
7. 디자인 값은 web/src/styles/tokens.css 토큰만 쓴다.

## 명령
- API: python -m uvicorn api.index:app --port 8000 --reload
- 화면: npm --prefix web run dev  (http://localhost:5173/map/)
- 테스트: pytest -q / npm --prefix web run test / python tests/ui_check_map.py
- 평가: python -m evals.run_eval
- 빌드: npm --prefix web run build  (→ public/map)
```

```markdown
---
paths:
  - "web/**"
---
# .claude/rules/web.md — 프론트엔드 규칙
- 색·간격·반경은 tokens.css만. 글래스는 ui/GlassPanel만 쓴다.
- 리퀴드 글래스(SVG 굴절)는 크롬 계열에서만, 작은 요소에만.
- 레이어 스타일은 src/map/layers/에만 정의한다.
- 사실을 보여 주는 곳에는 출처 줄(문서·쪽·기준일) 컴포넌트를 붙인다.
- 툴팁·모달은 포털로 body에 띄운다. 모든 조작은 키보드로도 가능해야 한다.
```

```json
{
  "permissions": {
    "allow": ["Bash(npm --prefix web run *)", "Bash(pytest *)", "Bash(python -m pipeline.*)", "Bash(python -m evals.*)"],
    "ask": ["Bash(git push *)"],
    "deny": ["Read(./.env)", "Read(./.env.*)"]
  }
}
```

한 단계를 진행하는 루틴:

1. 단계마다 **새 대화**를 엽니다. 이전 단계의 긴 대화가 컨텍스트를 차지하지 않게 합니다.
2. 프롬프트 상자 아래 모드를 **Plan**으로 두고(또는 `/plan`) 아래 단계별 프롬프트를 붙여 넣습니다. VS Code는 계획을 Markdown 문서로 열어 주고, 줄마다 코멘트를 달아 고칠 수 있습니다.
3. 계획을 승인한 뒤 **Edit automatically** 모드로 구현을 맡깁니다. `git push`는 ask 규칙이 매번 묻습니다.
4. 단계의 ‘완료 확인’ 명령을 실행하고, 화면 단계는 `docs/screens/map_*.png` 스크린샷을 `@`로 첨부해 디자인 피드백을 줍니다. 팔란티어 참고 이미지는 `docs/design/refs/`에 두고 같은 방식으로 비교하게 합니다.
5. PROGRESS.md에 기록하고 커밋합니다. Vercel 배포가 막히지 않도록 커밋은 기존처럼 저장소 주인 계정의 noreply 이메일로 합니다.

## 단계별 계획 ① P11\~P15: 기반·지도·레이어

단계마다 ‘할 일’을 PROGRESS.md에 복사해 체크하고, ‘완료 확인’을 통과해야 다음 단계로 갑니다. 일수는 하루 3\~4시간 작업 기준 추정입니다.

### P11 작업 기반 (0.5\~1일)

기존 기능을 그대로 둔 채 새 브랜치·`web/` 프로젝트·규칙·디자인 토큰을 갖추고, 빈 화면 틀을 띄웁니다.

- [ ] `feat/map-console` 브랜치, `docs/map/PLAN.md`, 새 CLAUDE.md, `.claude/rules/web.md`·`pipeline.md`, `.claude/settings.json`
- [ ] `npm create vite@latest web -- --template react-ts` → maplibre-gl, react-map-gl, zustand, @tanstack/react-query, tailwindcss, @tailwindcss/vite, lucide-react, pretendard, d3-scale, d3-shape / 개발용 vitest
- [ ] `web/vite.config.ts` (‘기술 스택·구조’의 설정 그대로)
- [ ] `tokens.css`·`glass.css`, `GlassPanel` 컴포넌트, 크롬 계열에서만 굴절을 켜는 `useLiquidGlass` 훅
- [ ] 로고: `pipeline/make_logo.py`로 `로고.jpg`의 흰 배경을 투명하게 → `web/public/brand/logo.png`
- [ ] 빈 틀: 상단 바(로고·탭·검색·기준일 자리), 좌 320px, 우 400px, 하단 44px, 가운데 회색 상자
- [ ] `tests/test_wording.py`가 `web/src/**/*.ts(x)`도 검사(브랜드 문구 파일은 예외)
- [ ] `vercel.json`에 buildCommand 추가 → Preview 배포

```text
@docs/map/PLAN.md 의 P11 '작업 기반'을 진행해 줘.
1) 바꿀 파일 목록과 순서를 계획으로 먼저 보여 주고, 내가 승인하면 구현해.
2) web/은 Vite react-ts 템플릿, vite.config.ts는 PLAN.md '기술 스택·구조'의 설정을 그대로.
3) 색·글꼴·글래스 값은 PLAN.md '디자인 시스템'의 토큰만 써. 새 색을 만들지 마.
4) public/*.html, api/, core/는 이번 단계에서 건드리지 마.
5) 끝나면 '완료 확인' 명령을 모두 실행해 결과를 보여 주고 PROGRESS.md에 P11 섹션을 써.
```

완료 확인: `npm --prefix web run build` 성공·`public/map/index.html` 생성 / http://127.0.0.1:8000/map/ 에 빈 틀 표시(스크린샷 `docs/screens/map_00_shell.png`) / `pytest -q` 기존 121개 통과 / Preview 주소의 `/map/`·`/api/v1/health` 모두 200

### P12 지도 셸 (1\~2일)

화면 가운데 강남구가 떠 있는 지도를 만듭니다. 강남구 밖은 흐리게, 법정동은 얇은 경계와 이름으로.

- [x] `pipeline/build_map_base.py`: 2D 데이터 `lt_c_adsigg_info`(11680)·`lt_c_ademd_info`(강남구) → `public/data/base/gangnam.geojson`, `bjd.geojson`. 법정동 코드 14개가 `seed/bjd_codes.csv`와 같은지 검사
- [x] `MapView`: MapLibre + 브이월드 WMTS(기본·회색·위성·하이브리드) 전환. 레이어 이름은 Capabilities 응답으로 확인해 상수로 — Capabilities에 `gray`가 없어 회색은 무채색 `white` 레이어 (2026-11-09 확인)
- [x] 첫 화면 fitBounds(강남구), maxBounds(경계 + 약 2km), 줌 11\~19, 3D 기울기 토글 — maxBounds는 패널 밑까지 화면 전체를 묶어 줌이 커져서, 지도 **중심**을 경계 + 2km 안으로 묶는 `setTransformConstrain`으로 구현
- [x] 스포트라이트 마스크: 강남구 밖 흰색 55%, 구 경계선 1.5px
- [x] 커서 위치 표시줄(위도·경도·법정동), 우하단 출처 ‘배경지도: 국토교통부 브이월드’
- [x] localhost에서 타일이 막히면 브이월드에 개발용 URL을 등록하거나 Vite 프록시로 우회하고 PROGRESS에 기록 — 개발 키(서비스 URL localhost:3000)로 막히지 않음, 프록시 안 씀
- [x] maplibre-gl v6 + react-map-gl 8.1 이상으로 시작: named/namespace import와 worker 설정이 개발 서버·빌드 모두에서 도는지 확인, 안 되면 maplibre-gl 5.x 고정
- [x] 상단 바 선택된 작업 탭: 글자색은 잉크 그대로(규칙 4), 탭 아래 브랜드색 2px 막대 추가 (P11에서는 굵기로만 구분돼 약했음)
- [x] 상단 바 ‘투명도 줄이기’ 임시 토글은 그대로 두고, P20에서 설정 메뉴로 옮긴다

```text
@docs/map/PLAN.md 의 P12 '지도 셸'을 진행해 줘. Plan 모드로 계획부터.
- 경계 데이터는 pipeline/build_map_base.py로 빌드 때 한 번 받아 public/data/base/에 저장해. 키는 .env의 VWORLD_API_KEY, 출력 금지.
- 브이월드 WMTS 레이어 이름은 추측하지 말고 Capabilities 응답으로 확인해 상수로 둬.
- 첫 작업으로 maplibre-gl v6과 react-map-gl 8.1 이상 조합(named import·worker 설정)이 개발 서버와 빌드에서 모두 도는지 확인하고 결과를 PROGRESS.md에 적어.
- 완료 확인 뒤 docs/screens/map_01_base.png를 저장해.
```

완료 확인: `python -m pipeline.build_map_base` 두 번 실행 결과 동일(멱등) / 법정동 라벨 14개·구 밖 흐림·배경 4종 전환 / 콘솔 오류 0 / 스크린샷

### P13 Propedia 레이어 빌드 (2\~3일)

DB의 사업·규제 고시를 지도 도형으로 바꿉니다: 사업 구역 2, 영향권 4(250m·500m × 2), 포함 판정 필지 18, 규제 구역 2.

- [ ] `pipeline/fetch_parcels.py`: PNU 목록(사업 필지 18 + 시연 주소 15) → 2D 데이터 `LP_PA_CBND_BUBUN` → `seed/parcels.geojson` (원 응답은 `build/` 캐시)
- [ ] 대청마을 경계: `daecheong_map.py`에 `--export-boundary` 옵션 — 이미 읽은 꼭짓점 10개를 경위도로 바꿔 `seed/boundaries/D9.geojson`
- [ ] 한양7차 경계: D1 18\~21쪽 정비구역 결정도에 같은 정합 방법 → `seed/boundaries/D1.geojson`
- [ ] 규제 구역: D10(2\~3쪽)·D5(4\~9쪽) 지형도면 정합. 안 되면 의제처리구역·서울플랜+ 경계로 대체하고 `basis`에 기록
- [ ] 영향권: shapely로 EPSG:5186에서 250m·500m 버퍼 → EPSG:4326
- [ ] `pipeline/build_map_layers.py` → `public/data/layers/propedia_*.geojson` + `manifest.json`
- [ ] 좌표 정리: 지도·500m 판정 좌표를 필지 경계 중심점으로 바꾸고(`land_cache.location` 포함) `run_all` → `run_eval`로 판정 변화 확인
- [ ] 새 지표: M19 경계 면적 일치(고시 면적 ±5%), M20 GeoJSON 유효성
- [ ] HUMAN\_TODO: 도면 대조로 만든 경계 4개 사람 확인(그전까지 지도에 ‘확인 전’ 배지)

```text
@docs/map/PLAN.md 의 P13 'Propedia 레이어 빌드'를 진행해 줘. Plan 모드로 계획부터.
- 도면 정합은 pipeline/daecheong_map.py의 방법(연속지적도와 FFT 상호상관)을 재사용해. 결정도 축척 막대는 실제와 다를 수 있으니 지적선으로 맞춘 배율을 써(D9에서 0.947 → 0.79m/px였음).
- 각 경계의 계산 면적을 고시 면적(D1 22,123.6㎡, D9 90,992.0㎡, D10 79,269.1㎡, D5 1,149,476㎡)과 비교한 표를 보여 줘. ±5%를 넘으면 멈추고 대조 그림(build/overlay_*.png)을 보여 줘.
- 지오코더 좌표는 저장하지 마. 좌표는 필지 경계 중심점으로.
- 끝나면 python -m evals.run_eval과 pytest 결과를 보여 줘.
```

완료 확인: 경계 4개의 면적 비교표(±5% 이내 또는 사유 기록) / `build_map_layers` 멱등 / M1\~M20 통과 / pytest 통과 / geojson.io나 QGIS로 겹쳐 본 스크린샷

### P14 좌측 레이어 패널·상단 바 (1\~2일)

레이어를 그룹별로 켜고 끄고, 겹침 보기·검색·데이터 상태를 넣습니다.

- [ ] `GET /api/v1/map/manifest` (`core/map.py`)
- [ ] 레이어 트리 4그룹: Propedia 고시·사업 / 공식 참고 / 시장 / 생활 인프라. 행마다 켜기, 색 칩·아이콘, 건수, 기준일 툴팁, 투명도
- [ ] 겹침 보기 ‘영향권 안만 강조’: 빌드 때 계산한 `within_impact` 속성으로 필터
- [ ] 상단 바: 로고, 작업 탭, 검색(Ctrl+K → 기존 `/api/v1/lookup` + 사업·단지 이름), 기준일, 지도에 영역이 없는 서울 전역·구 단위 고시 칩(D6·D7·D8 등)
- [ ] 좌측 탭: 레이어 · 사업 목록 · 고시 피드(P19에서 채움) · 데이터 상태(원천·기준일·건수)
- [ ] URL 상태 `?layers=&sel=&c=&z=`, 키보드 Ctrl+K·L·I·T·Esc

```text
@docs/map/PLAN.md 의 P14 '좌측 레이어 패널'을 진행해 줘. Plan 모드로 계획부터.
- 레이어 상태는 web/src/state/useMapStore.ts(zustand) 하나에서 관리하고 URL과 동기화해.
- 검색은 기존 /api/v1/lookup을 그대로 쓰고, ambiguous면 후보 목록을 보여 줘.
- @docs/design/refs/ 의 팔란티어 참고 이미지에서 LAYER STACK의 밀도만 참고하고, 색은 흰 글래스 톤 토큰으로.
- tests/ui_check_map.py에 레이어 토글·URL 복원·검색 점검을 추가해.
```

완료 확인: `ui_check_map` — 레이어를 끄면 지도에서 사라짐, 새로고침 뒤 같은 화면 복원, Ctrl+K로 ‘일원동 619’ 검색 → 지도 이동 / 스크린샷 `map_02_layers.png`

### P15 공식 참고 레이어·필지 클릭 조회 (1\~2일)

서울시 사업 현황·용도지역·지적도를 참고로 올리고, 지도 아무 곳이나 누르면 그 필지의 토지 정보가 나오게 합니다.

- [ ] `pipeline/import_reference.py`: 서울플랜+·의제처리구역 SHP(사람이 받아 둔 파일) → 강남구만 → `public/data/layers/ref_*.geojson` (도형 원본 그대로, 출처·라이선스 속성)
- [ ] 브이월드 WMS: 용도지역·지구단위계획구역·지적도(줌 16 이상). 레이어명은 브이월드 데이터 목록에서 확인
- [ ] `core/live/vworld.py`에 `parcel_at(lat, lon)`: 2D 데이터 `LP_PA_CBND_BUBUN` 점 필터 조회 → PNU·지번·경계 (타임아웃 4초·재시도 1회)
- [ ] `GET /api/v1/map/parcel-at` → 지번 주소로 기존 `lookup()` 호출 → 토지 정보·4개 층 요약
- [ ] 빈 곳 클릭 → 필지 하이라이트 + 인스펙터
- [ ] 테스트: 저장 응답(`tests/fixtures/vworld/parcel_at_*.json`)으로 파싱, `test_no_network` 규칙 유지

```text
@docs/map/PLAN.md 의 P15를 진행해 줘. Plan 모드로 계획부터.
- 브이월드 2D 데이터 점 조회는 core/live/vworld.py에만 넣고, 기존 get_land와 같은 실패 처리(unavailable·안내 문구)를 따라.
- 첫 호출 응답을 tests/fixtures/vworld/에 저장하되 키가 들어가지 않았는지 검사해.
- 서울플랜+ SHP는 공공누리 4유형이라 도형을 단순화하지 말고, 레이어에 '참고·비상업' 배지와 출처를 달아.
```

완료 확인: 지번 5건(세곡동 279·역삼동 823·논현동 100·삼성동 159·개포동 12)을 지도에서 누르면 토지 정보 표시 / parcel-at p95 2초 이하(`run_eval --live`에 추가) / pytest 통과(네트워크 없음)

## 단계별 계획 ② P16\~P20: 인스펙터·실거래·타임라인·배포

P16이 끝나면 ‘지도에서 사업을 눌러 단계·기한·근거를 본다’는 핵심 시연이 가능합니다. 그 뒤 단계는 투자자용 데이터를 더하는 순서입니다.

### P16 우측 인스펙터 (2\~3일) — 첫 시연 가능

지도에서 누른 대상의 사실을 근거와 함께 보여 줍니다. 데이터는 기존 API를 재사용하고 새 계산은 만들지 않습니다.

- [ ] `GET /api/v1/map/feature/{kind}/{id}` (`core/map.py`): 사업은 기존 `progress()`, 규제는 `applicability_rules` 항목, 필지는 기존 `lookup()` 재사용
- [ ] 공통 틀: 머리(이름·종류 배지·기준일), 탭, 출처 줄, ‘원문 보기’ 모달(기존 `/pages/Dn/pNNN.jpg` + 근거 문장, ‘문서 DB에서 보기’는 기존 `docs.html` 링크)
- [ ] 사업: 단계 스테퍼(예: 재건축 13단계 중 2번째 · 앞으로 11단계 · 다음 ‘정비구역 지정 고시’), 세부 상태·단계 메모, 기한(D-day 또는 ‘마감(2026.11.06)’), 고시 수치 표, 포함 필지 목록(누르면 지도에서 강조), 관련 고시 이력, ‘남은 기간: 비교할 사례가 부족합니다’
- [ ] 규제: 효력 기간 막대(오늘 표시), 대상 기준, 근거 문장, 원문
- [ ] 필지: 토지 정보 카드, 건축물 요약, 이 필지에 걸린 고시(층별 항목 수와 펼치기), 주변 500m 사업
- [ ] 지도 콜아웃(선택 대상 옆 미니 카드)과 사업 목록 탭의 상태 배지(공람 중 / 공람 마감 / 승인 고시 미확인)

```text
@docs/map/PLAN.md 의 P16 '우측 인스펙터'를 진행해 줘. Plan 모드로 계획부터.
- 사업 데이터는 기존 core/progress.py와 /api/v1/projects/{id}/progress를 재사용하고 새 계산을 만들지 마.
- '남은 단계 수'는 템플릿 단계 수에서 현재 단계 번호를 뺀 값으로만 보여 주고, 남은 기간은 기존 문구('비교할 사례가 부족합니다')를 그대로 써.
- 모든 수치 옆에 출처 줄과 '원문 보기'를 붙여. 원문 모달은 기존 public/pages 이미지를 써.
- B1(일원동 619)과 A1(압구정동 527)에서 기존 lookup.html과 같은 사실이 나오는지 비교하는 테스트를 추가해.
```

완료 확인: A1·B1의 단계·기한·수치·근거 쪽이 기존 응답과 같음(pytest) / `ui_check_map`: 한양7차 구역 클릭 → ‘13단계 중 2번째’·‘마감(2026.11.06)’, 대청마을 ‘8단계 중 1번째’ / 스크린샷 `map_03_inspector.png` / 시연 대본 초안 `DEMO_MAP.md`

### P17 아파트 단지·실거래 (3\~4일)

강남구 아파트 단지를 지도에 올리고, 누르면 실거래가 이력을 봅니다.

- [ ] (사람) 공공데이터포털 활용신청: 실거래가 상세·단지 목록·기본 정보
- [ ] `pipeline/fetch_apartments.py`: 강남구 단지 목록 → 기본 정보(세대수·동수·사용승인일·주소) → PNU → 필지 경계 → `apartments.geojson`. 매칭 실패는 `build/apartments_unmatched.csv`
- [ ] `pipeline/fetch_trades.py`: 2016-01부터 이번 달까지 월별 호출(지역코드 11680), 이어받기 체크포인트, 응답 샘플은 `tests/fixtures/rtms/` → `db/market.db`의 `apt_trades`(원자료), `apt_trade_monthly`(단지 × 전용면적대 × 월의 중위값·건수, 해제 거래 제외)
- [ ] 거래와 단지 연결: PNU 일치 → 안 되면 단지명 정규화 일치 → 연결률 리포트
- [ ] API `/api/v1/apartments/{id}`, `/api/v1/apartments/{id}/trades`
- [ ] 인스펙터: 전용면적대 칩(거래 많은 면적대가 기본) → 월별 중위 거래가 선 + 개별 거래 점, 그 아래 별도 거래량 막대, 최근 거래 20건 표(계약일·전용면적·층·금액·거래유형·해제 여부)
- [ ] 문구는 ‘실거래가(국토교통부 신고 자료, 계약일 기준)’. ‘시세’는 쓰지 않음
- [ ] 지표: M21 단지 매칭률 90% 이상, M22 거래 연결률 95% 이상, 월별 건수 합 = 원자료 건수

```text
@docs/map/PLAN.md 의 P17 '아파트 단지·실거래'를 진행해 줘. Plan 모드로 계획부터.
- 실거래 API 응답 필드 이름은 공공데이터포털 기술문서와 실제 응답 샘플로 확인하고, 확인 전에는 코드에 쓰지 마.
- 일일 호출 한도에 걸려도 이어받을 수 있게 체크포인트를 남겨. 키는 출력하지 마.
- 지도 좌표는 지오코더가 아니라 필지 경계 중심점으로.
- 차트는 두 축 겹치기 금지: 가격 선 차트와 거래량 막대 차트를 위아래로 분리해.
- 은마(대치동 316)·청담자이(청담동 134-38)·현대(압구정동 426)의 최근 거래 10건을 표로 뽑아 줘. 사람이 실거래가 공개시스템 화면과 대조할 거야.
```

완료 확인: M21·M22 목표 달성 / 단지 3곳 대조표(HUMAN\_TODO) / `db/market.db` 크기 기록(20MB를 넘으면 원자료 기간 축소 검토) / 스크린샷 `map_04_apartment.png`

### P18 생활 인프라 (1\~2일)

학교·지하철역·편의시설을 올리고, 영향권과 겹쳐 볼 수 있게 합니다.

- [ ] `pipeline/fetch_pois.py`: 학교(표준데이터, 강남구 주소만), 지하철역(역사마스터), 편의시설(상가정보 강남구) → `schools.geojson`, `stations.geojson`, `pois.geojson`
- [ ] 편의시설 분류표 `seed/poi_categories.yaml`(대형마트·편의점·병원·약국·카페·학원 등 업종 코드 → 표시 이름·아이콘). 표에 없는 업종은 싣지 않음
- [ ] (선택) 초등학교 통학구역 SHP → `school_zones.geojson`
- [ ] 줌 15 미만은 클러스터, 16 이상은 이름 표시
- [ ] 반경 측정 도구: 점을 찍으면 500m 원과 원 안 분류별 개수(사실만, 점수 없음)
- [ ] 겹침 보기 연동: `within_impact` 속성을 빌드 때 계산

```text
@docs/map/PLAN.md 의 P18 '생활 인프라'를 진행해 줘. Plan 모드로 계획부터.
- 좌표는 원자료의 위도·경도를 그대로 쓰고 지오코딩은 하지 마.
- 편의시설 분류표(seed/poi_categories.yaml) 초안을 먼저 보여 주고 내 확인을 받은 뒤 진행해.
- 레이어마다 manifest.json에 원천·기준일·건수·라이선스를 적어.
```

완료 확인: 레이어 건수 = 원자료의 강남구 건수 / 줌·이동 중 끊김 없음(Chrome 성능 패널) / 스크린샷 `map_05_poi.png`

### P19 하단 타임라인·고시 피드 (2일)

고시·공람·효력·사업 단계를 시간축에 올리고, 날짜를 옮기면 ‘그날 기준’ 지도를 보여 줍니다.

- [ ] `GET /api/v1/timeline`: 문서 발행일 10건, 공람 기간 2건, 효력 기간(D5 2026.04.27\~2027.04.26, D6 2025.10.20\~2026.12.31, D10 2026.04.01\~2028.04.01 등), 사업 단계 이력 2건
- [ ] 하단 타임라인: 계열(고시 발행·공람·효력·사업 단계·선택 단지 거래량), 확대·이동, 오늘 선, 재생
- [ ] 날짜 스크러버: 그 날짜까지 나온 문서의 사업만, 효력 중인 규제만 표시
- [ ] 고시 피드: 최신순, 종류 배지, 기한 D-day, 누르면 지도 이동 + 인스펙터

```text
@docs/map/PLAN.md 의 P19 '타임라인·고시 피드'를 진행해 줘. Plan 모드로 계획부터.
- 날짜 계산은 core/timeutil.py(KST 고정)를 재사용해.
- 스크러버의 '그날 기준' 판정은 core/map.py의 순수 함수로 두고 pytest로 날짜별 기대값을 검사해.
- 참고 이미지 2번의 하단 Timeline 배치를 참고하되 흰 글래스 톤으로.
```

완료 확인: 2026-05-01 기준 한양7차 숨김(D1 공고 전)·대청마을 ‘공람 중(D-day)’ / 2026-11-09 기준 한양7차 ‘마감(2026.11.06)’·대청마을 ‘마감(2026.05.01)’ (pytest) / 스크린샷 `map_06_timeline.png`

### P20 다듬기·테스트·배포 (1\~2일)

성능·접근성·반응형을 마무리하고 배포합니다.

- [ ] 성능: 인스펙터 차트 지연 로딩, GeoJSON 좌표 6자리·gzip, 레이어별 줌 범위 제한
- [ ] 접근성: 키보드 탐색·포커스 링, 대비 검사, ‘투명도 줄이기’ 설정(P11 상단 바 임시 토글을 설정 메뉴로 옮김), `prefers-reduced-motion`
- [ ] 반응형: 1280px 이상 기본, 1024\~1279px는 인스펙터를 지도 위에 겹침, 1024px 미만은 하단 시트(보기 전용)
- [ ] 회귀: `pytest -q`, `python -m evals.run_eval`(M1\~M22), `tests/ui_check.py`(기존 50항목), `tests/ui_check_map.py`
- [ ] 문서: README(지도 빌드 순서·환경변수), `DEMO_MAP.md` 5분 대본(강남구 전체 → 대청마을 사업 → 영향권 안 단지 → 실거래 → 타임라인 → 원문 근거), HUMAN\_TODO
- [ ] 배포: Preview 확인 → main 병합 → Production, `/`를 `/map/`으로(결정 후), 브이월드 서비스 URL에 배포 주소 확인

```text
@docs/map/PLAN.md 의 P20 '다듬기·배포'를 진행해 줘. Plan 모드로 계획부터.
- 성능·접근성 점검 결과를 표로 보여 주고, 목표에 못 미치는 항목부터 고쳐.
- main에 병합하기 전에 Preview 배포에서 ui_check_map을 --base로 돌려 결과를 보여 줘.
- git push 전에는 항상 나에게 물어봐.
```

완료 확인: 배포 주소에서 `ui_check_map` 전부 통과·콘솔 오류 0 / Lighthouse 데스크톱 성능 80 이상 / `DEMO_MAP.md` 리허설 1회

## 검증·일정·리스크

기존 테스트 121개와 평가 지표 M1\~M18은 모든 단계에서 회귀 검사로 계속 돌리고, 지도용 검사와 지표 4개(M19\~M22)를 더합니다. 일정은 약 5주이고, 3주차 끝(P16)에 첫 시연, 5주차 끝(P20)에 배포가 관문입니다.

> 그림: 일정 · 10단계와 관문 2개 (원본 문서에 있음)

칸 안 일수를 더하면 관문 1까지 7.5\~13일, 관문 2까지 14.5\~23일입니다. 관문 1 뒤 네 단계는 투자자용 데이터와 배포 순서입니다.

| 무엇을 | 도구 | 확인 내용 | 단계 |
| --- | --- | --- | --- |
| 레이어 빌드 | pytest + `pipeline.check` | GeoJSON 유효성, 멱등, 고시 면적 ±5%, 응답에 키 없음 | P12\~P18 |
| 새 API | pytest + TestClient | 응답 형식, 기존 조회와 사실 일치, 날짜별 ‘그날 기준’ 값 | P14\~P19 |
| 실시간 조회 | `run_eval --live` | 필지 조회 성공률·p95 | P15 |
| 프론트 로직 | Vitest | URL 상태, D-day 표기, 면적대 분류, 겹침 필터 | P14\~ |
| 화면 | Playwright Python `ui_check_map.py` | 레이어 토글, 인스펙터 내용, 타임라인, 스크린샷 | P12\~P20 |
| 문구 | `test_wording.py` | `web/src`의 금지어 | P11\~ |
| 사람 확인 | HUMAN\_TODO | 경계 4개, 단지 3곳 실거래 대조, 편의시설 분류표 | P13·P17·P18 |

| 지표 | 정의 | 목표 |
| --- | --- | --- |
| M19 경계 면적 일치 | 계산 면적 ÷ 고시 면적 (D1·D5·D9·D10) | 4개 모두 ±5% |
| M20 GeoJSON 유효성 | 유효 폴리곤·EPSG:4326·필수 속성을 갖춘 도형 비율 | 100% |
| M21 단지 매칭률 | 필지 경계를 찾은 단지 ÷ 강남구 단지 | 90% 이상 |
| M22 거래 연결률 | 단지에 연결된 거래 ÷ 강남구 아파트 거래 | 95% 이상 |

| 리스크 | 나타나는 신호 | 대응 |
| --- | --- | --- |
| 브이월드 타일이 localhost에서 막힘 | 빈 타일·인증 오류 | 개발용 서비스 URL 등록, 안 되면 Vite 프록시로 우회 |
| MapLibre v6와 react-map-gl 호환 | 빌드·런타임 오류 | react-map-gl 8.1 이상과 v6 worker 설정 확인, 안 되면 maplibre-gl 5.x 고정 |
| 고시 도면 정합 실패 | 면적 ±5% 초과 (D9는 축척 막대가 이미 틀렸음) | 의제처리구역·서울플랜+ 경계로 대체, ‘확인 전’ 배지 |
| 실거래와 단지 매칭 실패 | 매칭률 90% 미만 | 단지명 정규화 표, 미매칭 목록 사람 확인 |
| 글래스 때문에 지도가 버벅임 | 드래그 중 프레임 하락 | 이동 중 blur 축소, 굴절은 작은 요소에만 |
| Safari·Firefox에서 리퀴드 효과 없음 | 굴절이 안 보임 | 크롬 계열에서만 적용, 나머지는 blur 글래스 |
| 라이선스·저장 제한 | 상용화 논의 | 서울플랜+ 대체·문의, 지오코더 좌표 미저장 |
| 공공데이터 호출 한도 | 한도 초과 오류 | 체크포인트로 이어받기, 운영계정 전환 |

## 출처

이 문서의 데이터 조건·기술 선택은 아래 공개 페이지 19곳(2026-11-09에 열어 확인)과 첨부 프로젝트 파일에 근거합니다.

**데이터·라이선스**

- [서울 열린데이터광장 OA-22712 · 서울시 도시계획사업 현황(서울플랜+)](https://data.seoul.go.kr/dataList/OA-22712/F/1/datasetView.do) — 사업 현황 SHP, 반기 갱신, 공공누리 4유형
- [공공데이터포털 · 서울특별시 의제처리구역 위치정보](https://www.data.go.kr/dcat/metadata/15082965) — 정비구역·아파트지구 등 경계
- [공공데이터포털 · 국토교통부 2D 데이터 API](https://www.data.go.kr/en/data/15140372/openapi.do) — 행정경계·연속지적도
- [공공데이터포털 · 국토교통부 WMTS/TMS API](https://www.data.go.kr/en/data/3046388/openapi.do) — 배경지도(기본·회색·위성·하이브리드)
- [공공데이터포털 · 브이월드 지오코더 API](https://www.data.go.kr/data/15101106/openapi.do) — 하루 40,000건, 결과 저장 금지
- [국토교통부 아파트 매매 실거래가 상세 자료](https://www.data.go.kr/en/data/15126468/openapi.do) — 지역코드·계약년월 요청, 개발계정 10,000건
- [국토교통부 공동주택 기본 정보제공 서비스(AptBasisInfoServiceV5)](https://www.data.go.kr/en/data/15058453/openapi.do) — 단지 세대수·사용승인일
- [전국초중등학교위치표준데이터](https://www.data.go.kr/data/15021148/standard.do) — 학교 위도·경도
- [소상공인시장진흥공단 상가(상권)정보](https://www.data.go.kr/catalog/15083033/fileData.json) — 분기 갱신, 업종·좌표
- [실거래가 공개시스템 이용안내](https://rt.molit.go.kr/pt/info/info.do) — 스크래핑 금지, 대량 이용은 공공데이터포털

**기술 스택**

- [Vercel · FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi) — `public/**` CDN 서빙, Build Command
- [Vite · 시작하기](https://main.vite.dev/guide/) — Node.js 20.19+ 또는 22.12+
- [MapLibre GL JS v6: WebGL2 필수·ESM 전용 (malagis)](https://geo.malagis.com/maplibre-gl-js-v6-mandatory-webgl-and-esm-only.html)
- [MapLibre 뉴스레터 2026년 7월](https://maplibre.org/news/2026-08-02-maplibre-newsletter-jul-2026/)
- [react-map-gl · What's new](https://visgl.github.io/react-map-gl/docs/whats-new) — 8.1 계열의 MapLibre v4·v5·v6 지원

**Claude Code**

- [Claude Code · VS Code 확장](https://code.claude.com/docs/en/vs-code) — Plan 모드, 계획 문서 코멘트
- [Claude Code · CLAUDE.md와 규칙 파일](https://code.claude.com/docs/en/claude-md) — 200줄 이하 권장, `@` 임포트, `paths` 규칙
- [Claude Code · 권한 규칙](https://code.claude.com/docs/en/permissions) — deny → ask → allow 순서

**디자인**

- [Liquid Glass on the web: 6 ways to build it with CSS and SVG (dev.to)](https://dev.to/devyatov/liquid-glass-on-the-web-6-ways-to-build-it-with-css-and-svg-3m07) — SVG 굴절은 크롬 계열에서만

**프로젝트 자료** (첨부 `propedia-pretotype-main`): `agents.md`, `PROGRESS.md`, `HUMAN_TODO.md`, `feedback.md`·`feedback2.md`, `db/schema.sql`, `db/propedia.db`(2026-10-26 빌드), `pipeline/daecheong_map.py`, `core/live/vworld.py`, `로고.jpg`, 대화에 첨부된 참고 이미지 6장
