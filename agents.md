# AGENTS.md — Propedia 프리토타입 (강남구 · 압구정 한양7차 재건축)

> **이 파일 하나만 보고** Claude Code가 처음부터 끝까지 구현·검증·시연 패키지 준비까지 하도록 쓴 작업 지시서다.
> 작성 2026-10-24 (Claude, 동혁 요청) · 작업 폴더 `F:\hsp_ver2\pretotype` · 원본 문서 폴더 `F:\hsp_ver2\data` (= `../data`)
> 상위 폴더의 `../agents.md`는 다른 작업(데이터레이크)이다. 이 폴더 작업에는 이 파일만 따른다.

---

## 목차
0. 먼저 읽을 것 (작업 방식·환경·토큰 절약)
1. 배경: Propedia가 만들려는 것
2. 프리토타입 목표·성공 기준·범위
3. 입력 문서 4종 (경로·쪽 범위·확인된 사실)
4. 시연 주소 10건
5. 전체 구조와 기술 스택
6. 폴더 구조
7. 데이터 모델 (SQLite DDL)
8. 빌드 파이프라인 (스크립트별 명세)
9. 추출 명세 (Claude Code가 직접 추출)
10. 조회·판정 로직 (core/)
11. API 명세
12. 화면 명세 (public/)
13. 평가 (정답셋·지표·리포트)
14. 테스트
15. 배포(Vercel)와 로컬 실행
16. README.md · DEMO.md 내용
17. 절대 규칙
18. 단계별 작업 계획 P0~P8 (체크리스트 + 완료 확인)
19. 멈춤 조건 · 사람 확인 · 문제 해결
20. PROGRESS.md · HUMAN_TODO.md 형식
21. 변경 이력

---

## 0. 먼저 읽을 것

### 0-1. 작업 방식
1. 이 파일을 **끝까지** 읽는다. 다음으로 `PROGRESS.md`를 읽는다(없으면 §20 형식으로 만든다). 끝나지 않은 첫 단계부터 이어서 한다.
2. §18의 단계 P0 → P8을 **순서대로** 진행한다. 단계마다 체크리스트를 모두 끝내고 "완료 확인"을 실행해 통과해야 다음 단계로 간다.
3. 단계를 끝낼 때마다 `PROGRESS.md`에 날짜·한 일·확인 결과·남은 문제를 적고 `git commit` 한다. 커밋 메시지 예: `P1: 원문 발췌·텍스트화·시연 주소`.
4. 사람이 해야 하는 일이 생기면 **작업을 멈추지 말고** `HUMAN_TODO.md`에 적고 계속한다. 멈춰야 하는 경우는 §19-1에 적힌 것뿐이다.
5. 이 파일 내용과 실제 상황(쪽 번호, 코드값, 파일명 등)이 다르면 **실제를 따르고**, 이 파일의 해당 부분을 고친 뒤 §21 변경 이력에 한 줄 적는다.
6. **추출은 Claude Code(너)가 직접 한다.** 쪽별 텍스트 파일(또는 쪽 이미지)을 읽고 §9 형식의 JSON을 쓴다. 외부 LLM API는 호출하지 않는다(키 없음, 동혁 결정 2026-10-24).

### 0-2. 표기
| 표기 | 의미 |
|---|---|
| `[확인]` | 원문 PDF에서 직접 확인한 사실 (작성자가 2026-10-24에 pdftotext로 확인) |
| `[추정]` | 확인 전 추정. 작업 중 원문·API로 확인하고, 확인되면 `[확인]`으로 바꾼다 |
| `※` | 사람 확인 필요 → `HUMAN_TODO.md`에 올린다 |

### 0-3. 작업 환경
- OS: Windows. 경로에 한글이 들어간다. 명령은 Claude Code 기본 셸(Git Bash) 기준으로 적는다. PowerShell이면 `source .venv/Scripts/activate` 대신 `.venv\Scripts\Activate.ps1`.
- Python 3.11 이상 (Vercel 기본은 3.12). `python --version`으로 확인한다.
- 한글 깨짐 방지
  - 셸에서 `export PYTHONUTF8=1` 후 작업한다 (`.venv/Scripts/activate` 다음 줄에 넣어도 된다).
  - 모든 파일 읽기/쓰기에 `encoding="utf-8"`. CSV는 `encoding="utf-8-sig"`(엑셀 호환).
  - 스크립트 시작부에서 `sys.stdout.reconfigure(encoding="utf-8")`.
- 네트워크: 동혁 PC에서 실행되므로 일반 인터넷을 쓸 수 있다. 단 **빌드 스크립트만** 네트워크를 쓴다(도로명주소 API, 좌표 조회). 시연 경로(`api/`, `core/`, `public/`)는 네트워크를 쓰지 않는다.
- 비밀값: `.env`에 `JUSO_CONFM_KEY`, `JUSO_CONFM_KEY_ALT`(도로명주소 검색 API 승인키 2개, 둘 다 개발용 키)가 이미 들어 있다. **값을 화면·로그·커밋에 절대 출력하지 않는다.**

### 0-4. 토큰 절약 규칙
- PDF를 통째로 읽지 않는다. §3에 적힌 쪽만 다룬다.
- PDF는 먼저 스크립트로 쪽별 텍스트 파일(`build/text/D1/p001.txt`)과 쪽 이미지(`public/pages/D1/p001.jpg`)로 바꾸고, 필요한 쪽 파일만 연다.
- 명령 출력이 길면 `head -50` 등으로 자른다. 큰 JSON을 화면에 통째로 찍지 않는다.
- 이미지 쪽(D2)은 먼저 **저해상도 모아보기(contact sheet)** 로 볼 쪽을 고르고, 고른 쪽만 고해상도 이미지로 읽는다 (§8-4).
- 문서 하나씩 끝낸다 (D1 추출 완료 → D2 …). 여러 문서를 동시에 열지 않는다.

---

## 1. 배경: Propedia가 만들려는 것

원 계획서: 「Propedia 서울 MVP 개발 계획서 v1.0」(2026-10-23, 팀 내부·대외비). 이 프리토타입은 그 **작동 원리만** 작게 보여준다. 아래는 이 작업에 필요한 내용 전부다.

### 1-1. 서비스 한 줄
서울 주소 하나를 넣으면, 그 주소에 해당하는 공공 문서(고시·공고·계획) 정보를 **4개 층**(서울 전역·자치구·법정동·필지)에서 모아 **한 응답**으로 돌려준다. 그 필지가 정비사업(재개발·재건축 등) 구역에 속하면 **현재 단계, 다음 단계, 기한, 남은 기간**을 기준일·원문 링크와 함께 보여준다.

### 1-2. 4개 층
| 층 (API 키) | 매칭 키 | 담는 정보 |
|---|---|---|
| 서울 전역 (`city`) | 시도코드 `11` | 서울 전체에 적용되는 정책·계획 |
| 자치구 (`gu`) | 시군구코드 5자리 (강남구 `11680`) | 구 전체에 적용되는 계획·고시, 구 안 사업의 단계 분포 |
| 법정동 (`dong`) | 법정동코드 10자리. **프리토타입은 지역생활권도 이 층에 넣는다** | 동 안의 진행 사업, 진행 중 기한, 동·생활권 단위 계획 |
| 필지 (`parcel`) | PNU 19자리, 반경 500m | 용도지역, 포함 사업과 진행상황, 주변 500m 사업 |

- 같은 사업이 여러 층에 걸리면 **가장 좁은 층에만** 표시한다 (필지 > 법정동 > 자치구 > 서울 전역 순으로 좁다).
- 항목(문서 속 정책·계획·고시 단위)마다 **적용 범위(`scope_type`)** 를 추출 단계에서 정한다.
  - 지번이나 구역명이 있으면 → 법정동(`BJD`) 또는 필지(`PARCEL`)
  - "서울특별시 전역", "시 전역" 같은 표현이 있거나 서울시 조례·제도 변경이면 → 서울 전역(`SIDO`)
  - 구 문서인데 지번 없이 구 전체에 적용되면 → 자치구(`SGG`)
  - 지역생활권 단위면 → `SAENGHWAL` (프리토타입 추가 범위, 법정동 층에 표시)
  - 판단이 갈리면 → 검수 큐

### 1-3. 설계 원칙 (프리토타입에도 그대로 적용)
1. 모든 사업 문서는 **'사업 카드'로 묶인 뒤에만** 화면에 나간다.
2. 사업 단계는 **고시·공식 데이터로만** 바꾼다. LLM(=Claude Code) 추출값은 근거 문장과 함께 저장하고, 불확실하면 검수 큐로 보낸다.
3. 단계 설명·소유자 안내 문구는 **사람이 쓴 템플릿에서만** 나온다. LLM이 만들지 않는다.
4. 남은 기간은 예정일이 아니라 비교 집단의 범위·중앙값·표본 수로만 보여준다. 지연 여부·사유는 보여주지 않는다.
5. 화면의 모든 단계·기한·항목에 **기준일과 원문 링크(문서·쪽)** 를 붙인다.
6. 이용 조건이 불분명하거나 로그인이 필요한 자료는 쓰지 않는다.
7. (홈쇼퍼 공통) **사실만 보여주고 판단(점수·등급·추천·예측)은 하지 않는다.**

### 1-4. 포함 판정표 ("이 필지가 사업 구역에 포함되나?")
위에서부터 확인해 **처음 맞는 줄**을 적용한다.

| 순서 | 신호 | 판정 코드 | 화면 문구 | 프리토타입 |
|---|---|---|---|---|
| 1 | 지번 조서에 이 PNU가 있음(확인), 또는 사람 검수로 확정 | `included` | "이 필지는 {사업명} 구역에 포함되어 있습니다" + 근거 고시 링크 | 검수 승인 시 |
| 2 | 경계와 필지 면적 90% 이상 겹침 | `included` | 위와 같음 (근거: 지형도면 고시) | 구현 안 함 (경계 데이터 없음) |
| 3 | 지역지구에 정비구역 표시 + 인근 사업 후보 1개 | `likely` | "{사업명} 구역에 포함된 것으로 보입니다. 확인해 주세요" | 구현 안 함 (브이월드 없음) |
| 4 | 사업 문서에 대표 지번만 있고 이 필지가 그 대표 지번 | `possible` | "{사업명} 구역에 포함될 수 있습니다" + 원문 링크 | **D1 "527번지 일대" → 압구정동 527** |
| 5 | 사업 중심점에서 500m 이내 | `nearby` | "주변에서 진행 중인 사업" + 거리 | 좌표가 있을 때 |
| 6 | 해당 없음 | `none` | "{기준일}까지 확인된 고시 기준, 진행 중인 사업이 없습니다" | |

### 1-5. 재건축 단계
원 계획서의 재개발 13단계에서 1번만 '재건축진단'으로 바뀐다. 전체 템플릿은 §9-5.

### 1-6. 남은 기간
원 계획서는 Kaplan-Meier 생존분석(비교 집단 30건 이상)으로 계산한다. 프리토타입은 표본이 없으므로 `remaining = null`, 화면 문구는 **"비교할 사례가 부족합니다"** 로 고정한다. 계산 원리는 화면에 '참고' 상자로 설명만 한다(숫자 없이).

---

## 2. 프리토타입 목표·성공 기준·범위

### 2-1. 목표
동혁이 참석하지 않는 자리에서 **시연자가 멘토에게** "주소 하나 → 4개 층 정보 + 정비사업 진행상황"이 **어떤 원리로** 만들어지는지 보여준다. 시연 날짜는 공람 마감(2026-11-06) 전이다.

### 2-2. 성공 기준 (전부 만족해야 완료)
1. 로컬(`run_demo.bat`)과 Vercel 주소에서 화면 5개(시작·주소 조회·문서 DB·검수·평가)가 동작한다.
2. A1(`강남구 압구정동 527`) 조회 → 4개 층 모두 항목 1개 이상 + 사업 카드(재건축 13단계 중 2번째, 공람 기한 D-day 표시).
3. 모든 항목에 문서·쪽·기준일·근거 문장이 있고, "원문 보기"를 누르면 해당 쪽 이미지가 열린다.
4. 검수 화면에서 A1 포함 판정을 승인하면 주소 조회 결과가 "포함될 수 있음" → "포함"으로 바뀌고, 초기화하면 원래대로 돌아간다.
5. 평가 화면에 §13 지표가 모두 보인다.
6. `pytest -q` 전부 통과, `python -m evals.run_eval` 정상 종료.
7. 시연 중 외부 네트워크·LLM 호출 0건 (코드에 네트워크 호출이 없음을 테스트로 확인).

### 2-3. 원 계획서(MVP) 대비 축소
| 항목 | MVP 계획서 | 프리토타입 |
|---|---|---|
| 지역 | 서울 25개 구 + 서울시 | 강남구 (압구정동 중심) |
| 수집 | 수집기 26종 + 공식 데이터셋, 하루 2회 | 이미 받은 문서 4종을 로컬에서 투입 |
| 저장 | PostgreSQL 16 + PostGIS | SQLite 파일 1개 (`db/propedia.db`, 배포본은 읽기 전용) |
| 추출 | Claude API 배치 처리 | Claude Code가 작업하면서 직접 추출 → `extractions/*.json` |
| 포함 판정 | 지번 조서, 경계 90%, 브이월드, 대표 지번, 500m | 대표 지번 + 좌표 거리 + 사람 검수 |
| 진행상황 | 재개발·재건축·재정비촉진·소규모 | 재건축 1건 (한양7차) |
| 남은 기간 | 생존분석 | "비교할 사례가 부족합니다" 고정 |
| 증분 갱신 | 게시판 감시 + change_events | 문서를 1건씩 투입하는 순서를 미리 계산해 단계별로 보여줌 |
| 정답셋 | 40사업·200필지·50주소 | 사업 1, 주소 10, D1 필드 약 18개, 항목 범위 라벨 전체 |
| 화면 | Streamlit 검증 화면·검수 도구 | 정적 웹페이지 5개(HTML/JS) + FastAPI, Vercel 배포 |

### 2-4. 하지 않는 것
결제·로그인·소유 인증, 소비자용 디자인 고도화, 생존분석 수치, 브이월드·건축물대장 실시간 연동, 뉴스, 25개 구 수집기, PostgreSQL/PostGIS, 외부 LLM API.

---

## 3. 입력 문서 4종

원본은 `../data/` 아래에 있다. **수정·이동 금지.** 쪽 번호는 모두 **원본 PDF의 1부터 세는 쪽 번호(`pdf_page`)** 다. 인쇄된 쪽 번호(`page_label`)는 다르다.

### 3-1. 문서 목록
| ID | 문서 | 원본 경로 | 담당 층 | 투입 순서 |
|---|---|---|---|---|
| D1 | 강남구 공고 제2026-2347호 (구보 제1871호, 2026-10-08) — 압구정 아파트지구 개발기본계획·지구단위계획 결정(변경), 특별계획구역⑥-1 한양7차아파트 재건축 정비구역·정비계획 결정(변경)(안) 공람·공고 | `../data/7.구보/강남구 제2026-2347호*.pdf` (파일명이 길고 잘려 있음. `Path("../data/7.구보").glob("강남구 제2026-2347호*.pdf")`로 찾는다. 결과가 정확히 1개여야 한다) | 법정동 + 필지 + **사업 카드** | 4 |
| D2 | 2030 서울생활권계획 — 강남구 (2018-03) | `../data/2.생활권계획/강남구.pdf` (269쪽, 약 31MB) | 자치구 + 지역생활권 | 3 |
| D3 | 2030 서울특별시 도시·주거환경정비기본계획 (2025-06-26 변경, 서울특별시고시 제2025-348호) | `../data/3.도시주거환경정비기본계획.pdf` (396쪽) | 서울 전역 (+ 자치구 통계) | 2 |
| D4 | 2040 서울도시기본계획 (2023-02) | `../data/1.2040서울도시기본계획.pdf` (205쪽) | 서울 전역 + 동남권(자치구) | 1 |

투입 순서는 "문서 1건씩 투입" 시연(§8-10)에서 쓴다. D4 → D3 → D2 → D1 순서로 들어오며, 사업 상태가 바뀌는 건 D1뿐이다.

### 3-2. 쓰는 쪽 (pdf_page 기준) `[확인: 2026-10-24 쪽별 제목 확인]`
| ID | 쪽 | 내용 | 텍스트 상태 |
|---|---|---|---|
| D1 | 1~17 | 공고문 본문 전체 (공람 안내, 아파트지구 개발기본계획 변경, 정비계획(안)) | 텍스트 추출 가능 |
| D1 | 18~21 | 붙임 도면 (정비구역 결정도 등) | 이미지 → **원문 보기용으로만** 렌더링, 추출하지 않음 |
| D2 | 12~14 | 생활권의 구분, 지역생활권의 구분, **지역생활권 구분 결과** (강남구 6개 지역생활권: 역삼·논현, 삼성, 압구정·청담, 대치·도곡, 개포·일원, 수서·세곡) | 텍스트 추출 가능 |
| D2 | 29~31 | 강남구 개요 (일반사항, 지역생활권 현황). **p29는 장 표지, p30은 빈 쪽 → p31만 선택·전사** `[확인 2026-10-25]` | **이미지** (쪽당 30자 미만) |
| D2 | 113~151 | **압구정·청담 지역생활권계획** (113 표지, 인쇄 쪽 109~145) | **이미지** → 이 중 10~15쪽만 골라 전사 (§8-4) |
| D3 | 243~248 | 재건축사업 부문: 제도 변천(243~244), 추진현황(245), 구역해제 현황(246), 정비구역 목록·표 75 재건축 추진 중 단지 현황(247~248) | 텍스트 추출 가능 |
| D3 | 262~268 | 재건축 건축물의 밀도계획: 용적률 계획(262~264), **표 79 주거지역 용적률 체계(265)**, 역세권 용도지역 상향·공공기여(266~268) | 텍스트 추출 가능 |
| D3 | 275~277 | 표 84 허용용적률 인센티브 기준(275), 상한용적률(276~277) | 텍스트 추출 가능 |
| D4 | 73 | 표 3-2 부문별 목표와 전략 중 "주택·정비" 부문 | 텍스트 추출 가능 |
| D4 | 75~80 | 제3장 제2절 주택·정비 부문 (인쇄 67~72) | 텍스트 추출 가능 |
| D4 | 175~179 | 제5장 제3절 권역별 구상 — 6. 동남권 (인쇄 167~171) | 텍스트 추출 가능 |

- 인쇄 쪽 환산: D3 재건축 부문 `page_label = pdf_page − 13` (밀도계획 인쇄 249쪽 = PDF 262쪽) `[확인]`. D4 `page_label = pdf_page − 8` `[확인]`. D2 `page_label = pdf_page − 6` (PDF 12 = 인쇄 6, PDF 31 = 인쇄 25, PDF 115 = 인쇄 109) `[확인 2026-10-25, 처음 적은 −4는 틀림]`. D1은 공고 내부 쪽 번호(- 1 - …)를 쓴다. `page_label`은 텍스트에서 읽히면 그 값을 쓰고, 안 읽히면 위 공식으로 채운다.
- P1에서 각 쪽의 첫 줄을 뽑아 위 표의 내용과 맞는지 확인한다 (`build/page_heads.txt`). 다르면 실제를 따른다(§0-1-5).

### 3-3. 출처 정보 (화면의 "출처" 줄에 쓴다)
| ID | source_id | 출처 이름 | source_url | source_note |
|---|---|---|---|---|
| D1 | `gangnam-gubo` | 강남구 구보 | `null` ※ (정확한 게시물 주소 미확인) | "강남구 구보 제1871호(2026.10.08) 게재, 강남구 공고 제2026-2347호" |
| D2 | `seoul-urban-portal` | 서울도시공간포털 | `https://urban.seoul.go.kr/view/html/PMNU3040000001` | "2030 서울생활권계획 (2018.3)" |
| D3 | `seoul-citybuild` | 서울시 도시계획 소식 | `https://news.seoul.go.kr/citybuild/?p=528131` | "2030 정비기본계획 변경 (서울특별시고시 제2025-348호, 2025.6.26)" |
| D4 | `seoul-urban-portal` | 서울도시공간포털 | `https://urban.seoul.go.kr/view/html/PMNU2020000000` | "2040 서울도시기본계획 (2023.2)" |

### 3-4. 문서 메타데이터 (DB `documents`에 넣을 값)
| ID | title | short_title | doc_kind | issuer | gosi_no | published_at |
|---|---|---|---|---|---|---|
| D1 | (§3-1 제목 전체) | 한양7차 재건축 정비계획(안) 공람 | `gongram` | 강남구청장 | 강남구 공고 제2026-2347호 | 2026-10-06 |
| D2 | 2030 서울생활권계획 (강남구) | 2030 생활권계획 강남구 | `plan` | 서울특별시 | null | 2018-03-08 ※ (표지·공고일 확인) |
| D3 | 2030 서울특별시 도시·주거환경정비기본계획 (2025.6.26 변경) | 2030 정비기본계획 | `plan` | 서울특별시 | 서울특별시고시 제2025-348호 | 2025-06-26 |
| D4 | 2040 서울도시기본계획 | 2040 서울도시기본계획 | `plan` | 서울특별시 | null | 2023-01-05 ※ (공고일, 발간 2023-02) |

### 3-5. D1에서 확인된 사실 (정답셋 초안의 근거) `[확인: pdftotext]`
| 항목 | 값 | pdf_page |
|---|---|---|
| 공고번호 | 서울특별시 강남구 공고 제2026 - 2347호 | 1 |
| 구보 | 제1871호, 2026.10.08 (쪽 머리글) | 1~21 |
| 공고일 | 2026년 10월 6일, 강남구청장 | 1 |
| 근거 법령 | 「국토의 계획 및 이용에 관한 법률」 제28조, 「도시 및 주거환경정비법」 제15조 제1항, 같은 법 시행령 제13조 | 1 |
| 공람기간 | 2026. 10. 06. ~ 2026. 11. 06. | 1 |
| 공람장소 | 강남구청 재건축사업과 (☎02-3423-6063), 압구정동 주민센터 (☎02-3423-7606) | 1 |
| 의견 제출 | 토지등소유자 및 이해관계인은 공람기간 내에 의견서를 공람장소로 제출 | 1 |
| 관련 고시 이력 | 건설부고시 제131호(1976.8.21.) 아파트지구 최초 지정 / 서울특별시고시 제2008-202호(2008.6.12.) 개발기본계획(정비계획) 결정(변경) / 서울특별시고시 제2023-516호(2023.11.23.) 개발기본계획 결정(변경) / 서울특별시고시 제2023-517호(2023.11.23.) 지구단위계획구역 지정 및 지구단위계획 | 1 |
| 아파트지구 토지이용계획 합계 | 836,456.5㎡ (변경 없음) | 2 |
| 주택용지 | 678,983.6㎡ → 677,347.5㎡ (감 1,636.1) | 2 |
| 도로용지 | 83,625.5㎡ → 85,261.6㎡ (증 1,636.1) | 2 |
| 정비사업 명칭 | 압구정아파트지구 특별계획구역6-1 재건축 정비구역 | 4 |
| 정비구역 위치 | 강남구 압구정동 527번지 일대 | 4 |
| 정비구역 면적 | 기정 - / 증 22,123.6㎡ / 변경 22,123.6㎡ | 4 |
| 용도지역 | 제3종일반주거지역 18,034.4㎡ (81.5%), "용도지역에 관한 계획(변경없음)" | 5 |
| 획지 | I1-1, 압구정동 527번지 일대, 14,726.9㎡, 특별계획구역 6-1 (한양7차APT) | 13 |
| 주택공급계획 | 268세대 (세대수는 건축위원회 심의에서 최종 결정) | 7 |
| 용적률 | 기준(허용) 용적률 230% (허용용적률 인센티브 20%p), 정비계획 용적률 264.9%, 법정상한 용적률 300% | 7 |
| 세대수 | 현황 239 → 계획 268 (증 29) | 11~15 중 (표 위치 확인) |
| 단계 | 정비구역·정비계획 결정(변경)(**안**)의 **주민공람** 단계 → 재건축 템플릿 2번 `RB02` | 1 (제목) |

주의: D1은 **지번 조서(구역 내 지번 목록)가 없다.** 위치는 "527번지 일대"뿐이다. 그래서 압구정동 527은 판정표 4번(`possible`)이 된다.

---

## 4. 시연 주소 10건 (= 주소 정답셋 대상)

P1에서 `pipeline/resolve_addresses.py`(도로명주소 API)와 `pipeline/geocode.py`(좌표)로 확정해 `seed/demo_addresses.csv`에 저장한다.

| ID | 유형 | 입력(초안) | 고르는 방법 | 기대 결과 핵심 |
|---|---|---|---|---|
| A1 | 사업 대표 지번 | `강남구 압구정동 527` | 고정 `[확인: D1 p4]` | 필지: 한양7차 `possible` → 검수 승인 시 `included` / 법정동: D1 아파트지구 항목 + 압구정·청담 생활권 항목 / 자치구 / 서울 전역 |
| A2 | 도로명주소 입력 | `서울특별시 강남구 압구정로61길 37` (압구정동 528 한양아파트) | `[확인 2026-10-26]` 압구정동 527은 도로명주소 검색 결과가 없어(건물 주소 없는 필지) 인접 528의 도로명으로 바꿈 | 필지: 사업 없음 / 법정동: 한양7차 사업(같은 동) — 도로명 입력이 PNU로 바뀌는지 확인 |
| A3 | 입력 변형 | `서울특별시 강남구 압구정동 527번지` | 고정 | A1과 같은 결과 |
| A4 | 같은 동, 사업 500m 이내 | `강남구 압구정동 494` (갤러리아백화점, 압구정로 343) | 압구정 한양·현대아파트는 OSM에 번지가 없어 좌표를 못 얻음 → OSM에 번지가 있는 갤러리아백화점. 근사 사업 중심에서 260m `[확인 2026-10-26]` | 필지: `nearby` (거리 표시) / 법정동: 같은 동 항목 |
| A5 | 같은 동, 500m 밖 | 압구정동 안에서 500m 밖 지점 | 좌표로 확인. 압구정동 안에 500m 밖 지점이 없으면 A5를 신사동 지점으로 바꾸고 기록 | 필지: 사업 없음 / 법정동 항목 |
| A6 | 같은 생활권, 다른 동 | 청담동 1곳 | 도로명주소 API로 임의 건물 1곳 | 압구정·청담 생활권 항목 / 사업 없음 (500m 밖이면) |
| A7 | 생활권 확인용 | 신사동 1곳 | 같음 | 생활권은 §8-6 매핑 결과를 따른다 |
| A8 | 다른 생활권 | 역삼동 1곳 | 같음 | 자치구·서울 전역만, coverage_note "역삼·논현 지역생활권 장은 프리토타입 범위 밖" |
| A9 | 다른 생활권 | 대치동 1곳 | 같음 | A8과 같은 유형 (대치·도곡) |
| A10 | 범위 밖 | 서초구 1곳 (예: `서초구 방배동` 임의 건물) | 같음 | `status: out_of_scope`, "시연 범위(강남구) 밖입니다" |

- 도로명주소 API가 두 키 모두 실패하면(§19-3) 도로명주소 없이 **지번 입력만** 지원한다. 지번 → PNU는 `seed/bjd_codes.csv`로 만들 수 있으므로 작업은 계속된다. HUMAN_TODO에 기록.
- 좌표를 못 얻은 주소는 `lat/lon`을 비워 두고 500m 판정을 하지 않는다(응답에 "좌표 없음으로 주변 사업 판정 생략" 표시). HUMAN_TODO에 기록.

---

## 5. 전체 구조와 기술 스택

### 5-1. 구조
```
[빌드 단계: Claude Code 작업 세션 + 동혁 PC, 네트워크·Claude Code 직접 추출 사용]
 ../data/ 원본 PDF ──collect──▶ data_raw/D1~D4.pdf (쓰는 쪽만 발췌) + data_raw/manifest.csv (sha256)
   └▶ textify      쪽별 텍스트 build/text/Dn/p###.txt + 쪽 이미지 public/pages/Dn/p###.jpg
   └▶ (Claude Code) D2 이미지 쪽 고르기(모아보기) → 전사 → build/text/D2/p###.txt
   └▶ (Claude Code) 추출 → extractions/D1~D4.json (값 + 근거 문장 + 적용 범위)
   └▶ resolve_addresses / geocode → seed/demo_addresses.csv
   └▶ run_all: init_db → seed → load_extractions(근거 자동 검사) → build_projects(사업 카드·단계·기한·포함 판정)
               → events(투입 순서별 변화) → review_queue
   └▶ evals.run_eval → 평가 결과를 DB meta에 저장 + evals/report.md
   ▼
 db/propedia.db + public/ ──git──▶ GitHub ──▶ Vercel

[시연 단계: https://<프로젝트>.vercel.app 또는 로컬 http://127.0.0.1:8000 — 네트워크·LLM 호출 없음]
 public/*.html (화면 5개, assets/*.js가 /api/v1/* 호출)
   └▶ api/index.py (FastAPI) ─▶ core/*.py ─▶ db/propedia.db (읽기 전용)
```
- 화면은 모두 같은 API를 부른다. 화면의 "API 응답 보기"에 나오는 JSON이 실제 API 응답 그대로다.
- 로컬 실행도 같은 코드다. `python -m uvicorn api.index:app --port 8000` 하나로 API와 정적 화면(`public/`)을 함께 띄운다.

### 5-2. 기술 스택
| 구분 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.11+ (Vercel 3.12) | |
| 런타임 의존성 (`requirements.txt`) | `fastapi>=0.110`, `uvicorn>=0.29` | 런타임은 표준 라이브러리 `sqlite3`만 추가로 쓴다. **이 외 패키지를 `core/`, `api/`에서 import 금지** |
| 빌드 의존성 (`requirements-build.txt`) | `pdfplumber`, `pypdf`, `pypdfium2`, `Pillow`, `PyYAML`, `httpx`, `python-dotenv`, `pytest` | `pypdfium2`로 쪽 이미지 렌더링 (poppler 불필요) |
| DB | SQLite (`db/propedia.db`) | 배포본은 `mode=ro&immutable=1`로 연다 |
| 화면 | 정적 HTML + CSS + 바닐라 JS (빌드 도구·외부 CDN 없음) | 오프라인 로컬에서도 동작해야 함 |
| 배포 | Vercel (Hobby, 무료) | FastAPI `app` 자동 인식, `public/`은 CDN |
| 좌표 | OpenStreetMap Nominatim (빌드 때만, 초당 1회) | 실패 시 좌표 없음 처리 |
| 주소 | 도로명주소 검색 API `https://business.juso.go.kr/addrlink/addrLinkApi.do` (빌드 때만) | `.env` 키 사용 |

---

## 6. 폴더 구조

```
pretotype/
  CLAUDE.md               # "agents.md를 따른다" (이미 있음)
  agents.md               # 이 파일
  PROGRESS.md             # 진행 기록 (§20)
  HUMAN_TODO.md           # 사람 확인 목록 (§20)
  README.md               # 설치·빌드·실행·배포 (§16)
  DEMO.md                 # 시연자용 대본 (§16)
  requirements.txt        # 런타임: fastapi, uvicorn
  requirements-build.txt  # 빌드: pdfplumber, pypdf, pypdfium2, Pillow, PyYAML, httpx, python-dotenv, pytest
  .env                    # 이미 있음. JUSO_CONFM_KEY, JUSO_CONFM_KEY_ALT (커밋 금지)
  .env.example            # 이미 있음
  .gitignore              # 이미 있음 (.env, .venv/, build/, __pycache__/, *.pyc, .pytest_cache/, .vercel/)
  .vercelignore           # §15-2
  run_demo.bat            # 로컬 백업 실행 (§15-4)
  data_raw/               # 커밋함. D1~D4.pdf 발췌본 + manifest.csv
  extractions/            # 커밋함. D1~D4.json (Claude Code 작성)
  seed/                   # 커밋함
    bjd_codes.csv         # 강남구 법정동코드 + 지역생활권 (§8-6)
    demo_addresses.csv    # 시연 주소 10건 (§8-7)
    d2_selected_pages.yaml# D2 이미지 쪽 선택 결과와 이유 (§8-4)
    transcripts/D2/p###.txt # Claude Code 전사 원본 (build/는 커밋 안 하므로 여기 둔다. textify가 build/text로 합친다)
    stage_templates.yaml  # 재건축 단계 템플릿 (§9-5, 원 계획서 표 그대로)
    stage_rules.yaml      # 문서 제목 → 단계 판정 규칙 (§10-5)
  pipeline/               # 빌드 스크립트 (§8). 시연 코드에서 import 금지
    __init__.py, common.py, collect.py, textify.py, contact_sheet.py,
    resolve_addresses.py, geocode.py, init_db.py, load_seed.py, load_extractions.py,
    build_projects.py, events.py, review_queue.py, run_all.py, check.py
  db/
    schema.sql
    propedia.db           # 커밋함 (빌드 산출물, 수 MB 이하)
  core/                   # 조회·판정 로직. 표준 라이브러리만 사용
    __init__.py, db.py, address.py, lookup.py, progress.py, review.py, text.py, timeutil.py
  api/
    index.py              # FastAPI 앱 (Vercel 진입점, 로컬에서는 public/도 서빙)
  public/                 # 커밋함
    index.html, lookup.html, docs.html, review.html, eval.html
    assets/style.css, assets/app.js, assets/lookup.js, assets/docs.js, assets/review.js, assets/eval.js
    pages/D1/p001.jpg …   # 원문 쪽 이미지 (textify가 생성)
  evals/
    __init__.py
    goldset/addresses.yaml, goldset/extraction.yaml, goldset/scope_labels.yaml
    run_eval.py
    report.md             # 생성물 (커밋함)
  tests/                  # §14
  build/                  # 커밋 안 함. 중간 산출물 (text/, contact/, page_heads.txt, geocode_cache.json, juso_raw/)
```

---

## 7. 데이터 모델 (`db/schema.sql`, SQLite)

아래를 그대로 `db/schema.sql`로 만든다. 날짜는 `YYYY-MM-DD` 문자열, JSON은 문자열로 저장한다.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- keys: build_at(ISO), as_of(가장 최근 문서 날짜), schema_version('1'), eval_report(JSON), coverage_note

CREATE TABLE sources (
  id TEXT PRIMARY KEY,                 -- 'gangnam-gubo' | 'seoul-urban-portal' | 'seoul-citybuild'
  name TEXT NOT NULL,
  layer TEXT NOT NULL,                 -- 'city' | 'gu'
  url TEXT
);

CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  doc_id TEXT NOT NULL UNIQUE,         -- 'D1'..'D4'
  source_id TEXT NOT NULL REFERENCES sources(id),
  title TEXT NOT NULL,
  short_title TEXT NOT NULL,
  doc_kind TEXT NOT NULL,              -- 'gongram' | 'plan'
  issuer TEXT,
  gosi_no TEXT,
  published_at TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  supersedes_id INTEGER REFERENCES documents(id),
  source_url TEXT,
  source_note TEXT,
  original_path TEXT NOT NULL,         -- '../data/...' 상대경로
  excerpt_path TEXT NOT NULL,          -- 'data_raw/D1.pdf'
  page_ranges TEXT NOT NULL,           -- '1-21' 또는 '12-14,29-31,113-151'
  content_hash TEXT NOT NULL,          -- 원본 파일 sha256
  excerpt_hash TEXT NOT NULL,          -- 발췌본 sha256
  ingest_step INTEGER NOT NULL,        -- 투입 순서 (D4=1, D3=2, D2=3, D1=4)
  text_status TEXT NOT NULL            -- 'ok' | 'partial' | 'failed'
);

CREATE TABLE pages (
  document_id INTEGER NOT NULL REFERENCES documents(id),
  pdf_page INTEGER NOT NULL,
  page_label TEXT,
  method TEXT NOT NULL,                -- 'text' | 'vision-claude' | 'image-only'
  text TEXT NOT NULL DEFAULT '',
  char_count INTEGER NOT NULL,
  image_url TEXT NOT NULL,             -- '/pages/D1/p001.jpg'
  selected INTEGER NOT NULL DEFAULT 1, -- 추출 대상이면 1 (D1 18~21, D2 미선택 쪽은 0)
  PRIMARY KEY (document_id, pdf_page)
);

CREATE TABLE extractions (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  extractor_version TEXT NOT NULL,     -- 'claude-code-v1'
  extracted_at TEXT NOT NULL,
  payload TEXT NOT NULL,               -- extractions/Dn.json 전체
  evidence_ok_count INTEGER NOT NULL,
  evidence_total INTEGER NOT NULL
);

CREATE TABLE extracted_fields (        -- D1의 필드 단위 추출값 (평가·문서 DB 화면용)
  document_id INTEGER NOT NULL REFERENCES documents(id),
  field TEXT NOT NULL,
  value TEXT,                          -- JSON 값 문자열
  evidence TEXT,
  pdf_page INTEGER,
  confidence REAL NOT NULL,
  evidence_ok INTEGER NOT NULL,
  PRIMARY KEY (document_id, field)
);

CREATE TABLE applicability_rules (     -- 4개 층에 나가는 '항목'
  id INTEGER PRIMARY KEY,
  item_key TEXT NOT NULL UNIQUE,       -- 'D3-07'
  document_id INTEGER NOT NULL REFERENCES documents(id),
  item_type TEXT NOT NULL,             -- 'policy' | 'plan' | 'notice' | 'stat'
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  scope_type TEXT NOT NULL,            -- 'SIDO' | 'SGG' | 'SAENGHWAL' | 'BJD' | 'PARCEL'
  scope_ref TEXT NOT NULL,             -- JSON 배열: '["11"]', '["11680"]', '["압구정·청담"]', '["1168011000"]'
  scope_note TEXT,
  pdf_page INTEGER NOT NULL,
  evidence TEXT NOT NULL,
  evidence_ok INTEGER NOT NULL,
  effective_from TEXT,
  confidence REAL NOT NULL,
  needs_review INTEGER NOT NULL
);

CREATE TABLE doc_locations (
  document_id INTEGER NOT NULL REFERENCES documents(id),
  pnu TEXT, bjd_code TEXT, sgg_code TEXT,
  method TEXT NOT NULL,                -- 'representative' | 'jibun_text' | 'manual'
  jibun_text TEXT, pdf_page INTEGER, evidence TEXT, confidence REAL
);

CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  project_key TEXT NOT NULL UNIQUE,    -- 'apgujeong-6-1-hanyang7'
  name TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]',
  project_type TEXT NOT NULL,          -- 'rebuild'
  track TEXT NOT NULL DEFAULT 'unknown', -- 'general' | 'shintong' | 'public' | 'unknown'
  sgg_code TEXT NOT NULL,
  bjd_code TEXT NOT NULL,
  sub_stage_code TEXT NOT NULL,        -- 'RB02'
  stage_as_of TEXT NOT NULL,           -- 단계 근거 문서 날짜
  stage_source_doc_id INTEGER REFERENCES documents(id),
  stage_rule TEXT,                     -- 적용된 stage_rules id
  area_m2 REAL,
  location_text TEXT,                  -- '강남구 압구정동 527번지 일대'
  land_use TEXT,                       -- 문서 기재 용도지역
  land_use_page INTEGER,
  lat REAL, lon REAL, coord_source TEXT
);

CREATE TABLE project_parcels (
  project_id INTEGER NOT NULL REFERENCES projects(id),
  pnu TEXT NOT NULL,
  basis TEXT NOT NULL,                 -- 'representative_only' | 'jibun_table' | 'manual_review'
  verified INTEGER NOT NULL DEFAULT 0,
  source_doc_id INTEGER REFERENCES documents(id),
  pdf_page INTEGER, evidence TEXT,
  PRIMARY KEY (project_id, pnu)
);

CREATE TABLE project_documents (
  project_id INTEGER NOT NULL, document_id INTEGER NOT NULL,
  role TEXT NOT NULL,                  -- 'stage_basis' | 'related'
  PRIMARY KEY (project_id, document_id)
);

CREATE TABLE project_stage_history (
  project_id INTEGER NOT NULL, sub_stage_code TEXT NOT NULL,
  entered_at TEXT, source_doc_id INTEGER, basis TEXT NOT NULL,   -- 'gosi'
  pdf_page INTEGER, evidence TEXT
);

CREATE TABLE related_history (          -- 사업 카드의 '관련 고시 이력' (단계가 아님)
  project_id INTEGER NOT NULL, label TEXT NOT NULL, date TEXT, gosi_no TEXT,
  source_doc_id INTEGER, pdf_page INTEGER, evidence TEXT
);

CREATE TABLE deadlines (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL,                  -- 'public_review'
  title TEXT NOT NULL,                 -- '정비계획(안) 주민공람'
  starts_on TEXT, due_on TEXT NOT NULL,
  how_to_submit TEXT, places TEXT,     -- places: JSON 배열
  source_doc_id INTEGER, pdf_page INTEGER, evidence TEXT
);

CREATE TABLE stage_templates (
  project_type TEXT NOT NULL, seq INTEGER NOT NULL, sub_stage_code TEXT NOT NULL,
  common_stage TEXT, title TEXT NOT NULL, issuer TEXT,
  what_happens TEXT, owner_actions TEXT, legal_basis TEXT,
  source TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT,
  PRIMARY KEY (project_type, seq)
);

CREATE TABLE change_events (
  id INTEGER PRIMARY KEY,
  step INTEGER NOT NULL,               -- 투입 순서 (1~4)
  project_id INTEGER,
  event_type TEXT NOT NULL,            -- 'new_project' | 'stage_change' | 'deadline_added' | 'doc_attached'
  before TEXT, after TEXT,             -- JSON
  source_doc_id INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE review_queue (
  id INTEGER PRIMARY KEY,
  item_type TEXT NOT NULL,             -- 'parcel_inclusion' | 'evidence_mismatch' | 'vision_item' | 'scope_uncertain' | 'field_low_confidence' | 'stage_uncertain'
  ref_table TEXT NOT NULL,             -- 'project_parcels' | 'applicability_rules' | 'extracted_fields' | 'projects'
  ref_key TEXT NOT NULL,               -- 예: '1:1168011000105270000', 'D2-05', 'D1:area_m2'
  title TEXT NOT NULL,                 -- 검수 목록에 보일 제목
  reason TEXT NOT NULL,
  proposed TEXT,                       -- JSON: 현재 값/제안 값
  document_id INTEGER, pdf_page INTEGER
);

CREATE TABLE demo_addresses (
  addr_id TEXT PRIMARY KEY,            -- 'A1'..'A10'
  label TEXT NOT NULL,                 -- 화면 칩에 보일 이름
  input_text TEXT NOT NULL,
  road_address TEXT, jibun_address TEXT,
  pnu TEXT, bjd_code TEXT, sgg_code TEXT, building_name TEXT,
  lat REAL, lon REAL, coord_source TEXT,
  aliases TEXT NOT NULL DEFAULT '[]',  -- 같은 곳을 가리키는 다른 입력들
  in_scope INTEGER NOT NULL
);

CREATE TABLE bjd_codes (
  bjd_code TEXT PRIMARY KEY, sgg_code TEXT NOT NULL, dong_name TEXT NOT NULL,
  saenghwal TEXT,                      -- 지역생활권 이름 ('압구정·청담')
  code_verified INTEGER NOT NULL,      -- 도로명주소 API admCd로 확인했으면 1
  saenghwal_verified INTEGER NOT NULL  -- D2로 확인했으면 1
);
```

---

## 8. 빌드 파이프라인 (스크립트별 명세)

모든 스크립트는 `pretotype/`에서 `python -m pipeline.<이름>`으로 실행한다. 같은 입력이면 같은 출력이 나와야 한다(멱등). 실패하면 원인을 한국어로 출력하고 0이 아닌 종료 코드로 끝낸다.

### 8-1. `pipeline/common.py`
- `ROOT = Path(__file__).resolve().parents[1]`, `DATA = ROOT.parent / "data"`, `BUILD = ROOT / "build"`, `DB_PATH = ROOT / "db" / "propedia.db"`, `PUBLIC = ROOT / "public"`.
- `DOCS`: §3-1~3-4의 표를 dict로 (doc_id → 원본 glob, 쪽 범위 리스트, 투입 순서, 메타데이터, 출처, page_label 환산 함수).
- `sha256(path)`, `connect_rw()`(빌드용 쓰기 연결), `log(msg)`.
- 텍스트 정규화(§9-4와 같은 함수)는 `core/text.py`에 두고 여기서 import 해서 쓴다 (빌드·조회가 같은 규칙을 쓰도록).

### 8-2. `pipeline/collect.py` — 원본 → 발췌본
1. 각 문서의 원본 파일을 찾는다 (D1은 glob, 결과 1개 확인).
2. `pypdf`로 §3-2의 쪽만 골라 `data_raw/D1.pdf` … `data_raw/D4.pdf`로 저장한다. **원본 쪽 번호 ↔ 발췌본 쪽 번호** 대응표를 `data_raw/manifest.csv`에 쓴다.
3. `data_raw/manifest.csv` 열: `doc_id, original_path, original_sha256, original_pages, excerpt_path, excerpt_sha256, page_ranges, excerpt_page_map(JSON: {"원본쪽": 발췌쪽})`.
4. D2 발췌본에는 113~151 전체를 넣는다 (선택 전 단계이므로). D2 원본이 31MB라 발췌본도 수 MB가 될 수 있다. 10MB를 넘으면 HUMAN_TODO에 기록만 한다.

### 8-3. `pipeline/textify.py` — 쪽별 텍스트·이미지
1. 발췌본이 아니라 **원본** PDF에서 §3-2의 쪽마다:
   - `pdfplumber` `page.extract_text()` (None이면 `""`) → `build/text/{doc}/p{pdf_page:03d}.txt`
   - `pypdfium2`로 렌더링 → 가로 1200px로 줄여 JPEG(품질 75) → `public/pages/{doc}/p{pdf_page:03d}.jpg`
   - 공백을 뺀 글자 수가 30자 미만이면 `method = "image-only"`, 아니면 `"text"`.
2. `build/page_heads.txt`: 쪽마다 `{doc} p{pdf_page} chars={n} | {첫 비어 있지 않은 줄 2개}` 한 줄. 사람이 §3-2와 대조할 수 있게 한다.
3. `build/text/{doc}/pages.json`: `[{pdf_page, page_label, method, char_count, image_url, selected}]`.
   - `selected`: D1 1~17 = 1, D1 18~21 = 0, D2 12~14 = 1, D2 31 = 1 (29 표지·30 빈 쪽 = 0), D2 113~151 = 0 (§8-4 선택 후 1로 바꿈), D3·D4 = 1.
   - 텍스트는 `page.dedupe_chars(tolerance=1).extract_text()`로 뽑는다 (D1 굵은 글씨가 '공공람람'처럼 두 번 나오는 문제 `[확인]`).
   - `seed/transcripts/{doc}/p###.txt`(전사 원본)가 있으면 그 텍스트를 쓰고 `method="vision-claude"`, `selected=1`. D2 113~151은 `seed/d2_selected_pages.yaml`에 있는 쪽만 `selected=1`.
4. `page_label`: 텍스트에서 읽히면 그 값, 아니면 §3-2 공식.
5. 쪽 이미지 전체 용량을 출력한다. 40MB를 넘으면 품질을 65로 낮춰 다시 만든다.

### 8-4. D2 이미지 쪽 고르기와 전사 (Claude Code가 직접)
1. `python -m pipeline.contact_sheet D2 113 151` → `build/contact/D2_113-151_{n}.jpg`: 쪽 이미지 9장을 3×3 격자로 붙이고 칸마다 `p{pdf_page}` 라벨을 넣은 모아보기 (칸 크기 가로 400px). 29~31쪽도 한 장 만든다.
2. 모아보기 이미지를 열어 보고, **압구정동·압구정 아파트·한강변·재건축·주거지 관리·생활권 목표/공간구조**와 관련된 쪽을 10~15쪽 고른다. 생활권 범위(포함 행정동 목록)가 나온 쪽은 반드시 포함한다.
3. 고른 쪽과 이유를 `seed/d2_selected_pages.yaml`에 쓴다:
   ```yaml
   doc_id: D2
   selected:
     - {pdf_page: 115, reason: "압구정·청담 지역생활권 범위와 현황"}
     - ...
   not_selected_note: "나머지 쪽은 프리토타입 범위 밖"
   ```
4. 고른 쪽의 `public/pages/D2/p###.jpg`를 열어 보고 **보이는 글자를 그대로** `build/text/D2/p###.txt`에 옮겨 적는다.
   - 표는 행마다 한 줄, 칸은 ` | `로 구분한다.
   - 그림 속 글자는 읽을 수 있는 것만 적는다. 읽을 수 없는 부분은 `[판독 불가]`.
   - 의미를 보태거나 요약하지 않는다. 오타도 원문 그대로 적는다.
   - 쪽 이미지 글자가 작아 읽기 어려우면 `pypdfium2`로 그 쪽만 가로 2000px로 다시 렌더링해 `build/hires/`에 저장해 본다.
5. 전사한 쪽은 `pages.json`에서 `method = "vision-claude"`, `selected = 1`로 바꾼다. 29~31쪽도 같은 방법으로 전사한다.
6. 이 쪽들에서 나온 항목은 전부 `needs_review = true`가 된다 (§9-3).

### 8-5. 법정동 코드표 `seed/bjd_codes.csv`
초안 `[추정]` — P1에서 도로명주소 API로 동마다 1건씩 검색해 `admCd`로 확인하고 `code_verified=1`로 바꾼다.

| bjd_code | dong_name | saenghwal (초안) |
|---|---|---|
| 1168010100 | 역삼동 | 역삼·논현 |
| 1168010300 | 개포동 | 개포·일원 |
| 1168010400 | 청담동 | 압구정·청담 |
| 1168010500 | 삼성동 | 삼성 |
| 1168010600 | 대치동 | 대치·도곡 |
| 1168010700 | 신사동 | 압구정·청담 ※ (역삼·논현일 수도 있음) |
| 1168010800 | 논현동 | 역삼·논현 |
| 1168011000 | 압구정동 | 압구정·청담 |
| 1168011100 | 세곡동 | 수서·세곡 |
| 1168011200 | 자곡동 | 수서·세곡 |
| 1168011300 | 율현동 | 수서·세곡 |
| 1168011400 | 일원동 | 개포·일원 |
| 1168011500 | 수서동 | 수서·세곡 |
| 1168011800 | 도곡동 | 대치·도곡 |

- 열: `bjd_code,sgg_code,dong_name,saenghwal,code_verified,saenghwal_verified`. 모든 행 `sgg_code = 11680`.
- 지역생활권은 **행정동** 단위로 정해져 있다. D2 12~14쪽(텍스트)과 각 생활권 장의 첫 쪽(생활권 범위)을 보고 법정동 → 생활권을 확정한다. 한 법정동이 두 생활권에 걸치면 면적이 큰 쪽(또는 원문이 먼저 적은 쪽)으로 정하고 `HUMAN_TODO`에 적는다. 프리토타입은 압구정동·청담동·신사동만 정확하면 된다. 나머지는 초안 그대로 두되 `saenghwal_verified=0`.
- 생활권 이름의 가운뎃점은 `·`(U+00B7)로 통일한다. 원문의 `․`(U+2024)·`ㆍ`(U+318D)는 바꾼다.

### 8-6. 주소 정규화 규칙 (빌드·조회 공통, `core/address.py`)
- PNU 19자리 = 법정동코드 10 + 산 구분 1(일반 `1`, 산 `2`) + 본번 4자리 + 부번 4자리.
  ```python
  def make_pnu(bjd_code: str, main: int, sub: int = 0, san: bool = False) -> str:
      return f"{bjd_code}{'2' if san else '1'}{main:04d}{sub:04d}"
  ```
  예: 압구정동 527 → `1168011000105270000` `[추정: 코드표 확인 후 확정]`
- 지번 주소 정규식 (공백·'번지' 허용):
  ```python
  JIBUN_RE = re.compile(
      r"^\s*(?:서울(?:특별시|시)?\s*)?(?P<gu>[가-힣]+구)\s*(?P<dong>[가-힣0-9]+동)\s*"
      r"(?P<san>산\s*)?(?P<main>\d{1,4})(?:\s*-\s*(?P<sub>\d{1,4}))?\s*(?:번지)?\s*$")
  ```
  - `gu`가 `강남구`가 아니면 → `out_of_scope`.
  - `dong`이 `bjd_codes.csv`에 없으면 → `not_found`.
- 도로명주소 입력: 공백 제거·`서울특별시`→`서울`·`서울시`→`서울` 정규화 후 `demo_addresses`의 `road_address`, `jibun_address`, `aliases`와 비교. 맞으면 그 행. 문자열에 강남구가 아닌 `○○구`가 있으면 `out_of_scope`. 그 외는 `not_found` ("시연 주소 목록에서 찾을 수 없습니다. 지번 주소(예: 강남구 압구정동 527)로 입력해 주세요").
- 도로명주소 API 응답 → PNU: `admCd`(10자리 법정동코드) + (`mtYn == "1"`이면 `2`, 아니면 `1`) + `lnbrMnnm` 4자리 + `lnbrSlno` 4자리.

### 8-7. `pipeline/resolve_addresses.py` — 시연 주소 확정 (네트워크 사용)
1. `.env`를 `python-dotenv`로 읽는다. 키 값은 절대 출력하지 않는다 (`key[:3] + "***"`도 출력 금지).
2. 요청: `GET https://business.juso.go.kr/addrlink/addrLinkApi.do` 파라미터 `confmKey, currentPage=1, countPerPage=10, keyword, resultType=json`. 타임아웃 15초.
3. 응답 `results.common.errorCode`가 `"0"`이 아니면: `E0001`(승인키 오류)·`E0014`(개발승인키 기간 만료)면 `JUSO_CONFM_KEY_ALT`로 한 번 더 시도. 둘 다 실패하면 §19-3 (스크립트의 `FALLBACK` 목록으로 지번 입력만 작성, `--offline`으로 강제 가능).
4. 검색어에서 `% = > < [ ]` 같은 특수문자를 지운다.
5. 응답 원본을 `build/juso_raw/{addr_id}.json`에 저장한다 (키는 응답에 없으므로 안전).
6. §4의 방법대로 A1~A10을 확정하고 `seed/demo_addresses.csv`(열: §7 `demo_addresses`와 같음, `aliases`는 JSON 문자열)를 쓴다. A1의 aliases에 A3 입력을 넣는다.
7. 동별 1건씩 검색해 `admCd`로 `bjd_codes.csv`의 코드를 확인하고 `code_verified`를 갱신한다 (압구정동·청담동·신사동·역삼동·대치동은 시연 주소 결과로 확인 가능).
8. 실행 결과 요약을 출력: 주소 10건의 `addr_id, 입력, 도로명, 지번, PNU, in_scope`.

### 8-8. `pipeline/geocode.py` — 좌표 (네트워크 사용)
1. Nominatim `GET https://nominatim.openstreetmap.org/search` 파라미터 `q, format=jsonv2, limit=1, countrycodes=kr`, 헤더 `User-Agent: propedia-pretotype/0.1 (prototype demo)`. 요청 사이 1.1초 쉰다.
2. 시도 순서: 도로명주소 → `건물명 + 강남구`. 첫 성공을 쓴다. `coord_source = "osm-nominatim:{road|building}"`.
   - 지번 질의는 쓰지 않는다: 한국 OSM 번지는 도로명 번호라 '대치동 316'이 '선릉로 316' 건물로 잘못 맞았다 `[확인 2026-10-25]`.
   - 행정경계(`boundary`)·동네(`place`)·도로/정류장(`highway`) 결과는 필지 좌표가 아니므로 받지 않는다.
3. 결과를 `build/geocode_cache.json`에 캐시한다 (재실행 시 네트워크 안 씀).
4. 한양7차 사업 중심점 = A1(또는 A2) 좌표. `projects.lat/lon`에 쓴다 (§8-11). 둘 다 없으면 `PROJECT_ANCHORS`(도로명주소 API로 확인한 인접 필지의 OSM 좌표)로 근사해 `seed/project_coords.csv`에 쓰고, `coord_source`에 '근사: 인접 필지 …'를 남긴다. `[확인 2026-10-26]` 527·528은 OSM에 위치가 없어 526(청담고등학교) 좌표로 근사.
   - 결과 주소(`display_name`)에 해당 법정동 이름이 없으면 받지 않는다 (같은 이름의 다른 동 건물 방지: '한양아파트 강남구'가 신사동 건물로 맞았음).
5. 결과가 서울 강남구 범위(위도 37.45~37.54, 경도 127.01~127.12)를 벗어나면 실패로 본다.
6. 실패한 주소는 좌표를 비우고 HUMAN_TODO에 "지도에서 위경도 확인 필요 (A?)"로 적는다. A4·A5의 500m 판정은 좌표가 있을 때만 확정한다.

### 8-9. `pipeline/init_db.py`, `pipeline/load_seed.py`
- `init_db`: `db/propedia.db`를 지우고 `db/schema.sql`로 새로 만든다.
- `load_seed`: `sources`, `documents`(§3-3, 3-4, manifest의 해시), `pages`(`build/text/*/pages.json` + 텍스트 파일), `bjd_codes`, `demo_addresses`, `stage_templates`(§9-5 YAML)를 넣는다.
- `documents.text_status`: 선택된 쪽 중 텍스트(또는 전사)가 30자 이상인 비율이 100%면 `ok`, 50% 이상이면 `partial`, 아니면 `failed`.

### 8-10. `pipeline/load_extractions.py` — 추출 결과 적재 + 근거 자동 검사
1. `extractions/D1.json` … `D4.json`을 읽어 JSON 스키마(§9-2)를 검사한다. 필수 키가 없으면 오류로 멈춘다.
2. 모든 `evidence`를 해당 `pdf_page`의 쪽 텍스트와 비교한다 (`core.text.evidence_in(evidence, page_text)`, §9-4). 결과를 `evidence_ok`에 저장.
3. `items` → `applicability_rules`, D1 `fields` → `extracted_fields`, `extractions` 행(payload 전체, 일치 수/전체 수).
4. 근거 불일치 항목 → `review_queue(item_type='evidence_mismatch')`. 적재는 하되 화면에 "근거 확인 필요" 표시.
5. `--check` 옵션: 문서별 항목 수, 근거 일치율, `needs_review` 수를 표로 출력하고, 일치율이 100%가 아니면 불일치 목록(문서·쪽·근거 앞 40자)을 출력한다.

### 8-11. `pipeline/build_projects.py` — 사업 카드·단계·기한·포함 판정
D1 추출 JSON의 `projects` 배열로 사업 카드를 만든다 (프리토타입은 1건).
1. `projects` 행: `project_key`, `name`, `aliases`, `project_type='rebuild'`, `sgg_code='11680'`, `bjd_code`(압구정동), `area_m2`, `location_text`, `land_use`(D1 p5), `track='unknown'`(D1에 추진 방식 기재 없음), 좌표(§8-8).
2. **단계 판정**: `seed/stage_rules.yaml`(§10-5)을 D1 `title`에 적용해 단계 코드를 정한다. 추출 JSON의 `stage_candidate`와 다르면 규칙 결과를 쓰고 `review_queue(item_type='stage_uncertain')`.
3. `project_stage_history`: 현재 단계(RB02) 1행, `entered_at = 2026-10-06`(공고일), `basis='gosi'`, 근거 문장(공고 제목 문장)·쪽.
4. `related_history`: D1 p1의 관련 고시 이력 5건 (§3-5의 4건 + 건설부 건축4441-6149호(1977.3.29.) 아파트지구 개발기본계획 승인 `[확인 2026-10-25]`).
5. `deadlines`: 공람 1건 — `kind='public_review'`, `title='정비계획(안) 주민공람'`, `starts_on=2026-10-06`, `due_on=2026-11-06`, `how_to_submit`=원문 문장, `places`=공람장소 2곳.
6. `doc_locations`, `project_parcels`: 대표 지번 "527번지 일대" → 압구정동 527 PNU, `basis='representative_only'`, `verified=0`. → `review_queue(item_type='parcel_inclusion', ref_key='{project_id}:{pnu}', title='한양7차 재건축 — 압구정동 527 포함 여부', reason='고시에 지번 조서 없이 대표 지번("527번지 일대")만 있음')`.
7. `project_documents`: D1 `stage_basis`.

### 8-12. `pipeline/events.py` — 문서 1건씩 투입 순서별 변화
1. 투입 순서(step 1=D4, 2=D3, 3=D2, 4=D1)대로, "step k까지의 문서만 있을 때의 사업 상태"를 계산한다 (사업 상태 = 사업 목록, 각 사업의 단계·기한·소속 문서).
2. step k−1 상태와 step k 상태를 비교해 달라진 것만 `change_events`에 쓴다.
   - 새 사업 → `new_project` (after: 사업명·단계)
   - 단계 바뀜 → `stage_change` (before/after 단계)
   - 기한 추가 → `deadline_added`
   - 기존 사업에 문서 추가 → `doc_attached`
3. 기대 결과: step 1·2·3은 이벤트 0건, step 4는 `new_project` 1건 + `deadline_added` 1건 (`doc_attached`는 새 사업이므로 넣지 않는다).
4. `created_at`은 빌드 시각. 화면에서는 "투입 단계"로만 보여준다.

### 8-13. `pipeline/review_queue.py`
위 단계들이 넣은 것 외에 아래를 추가한다.
- `applicability_rules.needs_review = 1`인 항목 → `vision_item` (D2 전사 쪽) 또는 `scope_uncertain`(범위 판단 신뢰도 0.7 미만)
- `extracted_fields.confidence < 0.8` → `field_low_confidence`
- 같은 항목이 두 번 들어가지 않게 `(item_type, ref_key)`로 중복을 막는다.
- `proposed`에는 검수 화면이 그대로 보여줄 JSON을 넣는다: `{"current": {...}, "options": ["approve","reject","edit"], "editable_fields": ["summary","scope_type","scope_ref"]}` (parcel_inclusion은 `editable_fields: []`).

### 8-14. `pipeline/run_all.py`
`init_db → load_seed → load_extractions → build_projects → events → review_queue → meta(build_at, as_of=최근 문서 날짜 '2026-10-06', coverage_note)` 순서로 한 번에 다시 만든다. 네트워크를 쓰지 않는다 (resolve_addresses·geocode는 따로 실행해 seed에 결과를 남긴다). 끝나면 §18 P3 완료 확인 SQL의 결과를 출력한다.

`coverage_note` 기본값: "프리토타입: 강남구, 문서 4종(D1 강남구 공고 제2026-2347호, D2 2030 생활권계획 강남구 일부, D3 2030 정비기본계획 재건축 부문 일부, D4 2040 서울도시기본계획 일부)만 반영했습니다. 지역생활권 계획은 압구정·청담만 반영했습니다."

### 8-15. `pipeline/check.py`
`python -m pipeline.check P1|P2|P3` — 각 단계 완료 조건(§18)을 자동 점검하고 표로 출력한다. 통과하지 못한 항목이 있으면 종료 코드 1.

---

## 9. 추출 명세 (Claude Code가 직접 추출)

### 9-1. 원칙
- 입력은 `build/text/{doc}/p###.txt`(쪽 텍스트)뿐이다. D2 이미지 쪽은 §8-4에서 전사한 텍스트를 쓴다. **`evals/goldset/` 파일은 추출이 끝날 때까지 열지 않는다** (정답을 보고 추출하면 평가가 무의미해진다).
- 원문에 있는 것만 적는다. 원문에 없는 값은 `null`로 두고 `null_reason`을 적는다. 추정해서 채우지 않는다.
- 모든 값에 `evidence`(원문 그대로의 짧은 문장·구절)와 `pdf_page`를 붙인다. 근거는 **쪽 텍스트 파일에서 그대로 복사**한다. 공백·줄바꿈 차이는 괜찮다(§9-4).
- 숫자는 원문 그대로 옮기고 단위를 따로 적는다. 반올림·환산 금지.
- 요약(`summary`)은 원문에 있는 사실만, 1~2문장, 120자 이내. 금지어(§9-6)를 쓰지 않는다.
- 한 문서씩 끝내고 `python -m pipeline.load_extractions --check`로 근거 일치율을 확인한 뒤 다음 문서로 간다.

### 9-2. JSON 스키마 (`extractions/Dn.json`)
```json
{
  "doc_id": "D1",
  "extractor_version": "claude-code-v1",
  "extracted_at": "2026-10-25T10:00:00+09:00",
  "document": {
    "title": "…", "issuer": "강남구청장", "gosi_no": "강남구 공고 제2026-2347호",
    "published_at": "2026-10-06", "gazette": "구보 제1871호 (2026.10.08)", "doc_kind": "gongram"
  },
  "fields": {
    "<필드명>": {"value": "<값 또는 null>", "unit": "<단위 또는 null>", "evidence": "<원문 구절>",
                 "pdf_page": 1, "confidence": 0.95, "null_reason": null}
  },
  "items": [
    {
      "item_key": "D1-01",
      "item_type": "notice",
      "title": "압구정아파트지구 개발기본계획 변경(안): 토지이용계획",
      "summary": "압구정아파트지구 주택용지를 678,983.6㎡에서 677,347.5㎡로 줄이고 도로용지를 1,636.1㎡ 늘리는 안이다.",
      "scope_type": "BJD",
      "scope_ref": ["1168011000"],
      "scope_note": "아파트지구는 압구정동 일부. 경계 데이터가 없어 법정동 단위로 적용",
      "pdf_page": 2,
      "evidence": "주택용지     678,983.6",
      "effective_from": null,
      "confidence": 0.85,
      "needs_review": false
    }
  ],
  "projects": [
    {
      "project_key": "apgujeong-6-1-hanyang7",
      "name": "압구정아파트지구 특별계획구역6-1 재건축 정비구역",
      "aliases": ["한양7차아파트 재건축"],
      "project_type": "rebuild",
      "stage_candidate": "RB02",
      "stage_evidence": {"evidence": "…공람·공고", "pdf_page": 1},
      "representative_jibun": {"dong": "압구정동", "main": 527, "sub": 0, "san": false,
                               "text": "527번지 일대", "evidence": "527번지 일대", "pdf_page": 4},
      "area_m2": {"value": 22123.6, "evidence": "22,123.6", "pdf_page": 4},
      "land_use": {"value": "제3종일반주거지역", "evidence": "제3종일반주거지역", "pdf_page": 5},
      "deadlines": [
        {"kind": "public_review", "title": "정비계획(안) 주민공람",
         "starts_on": "2026-10-06", "due_on": "2026-11-06",
         "how_to_submit": "공람기간 내에 의견서를 공람장소로 제출",
         "places": ["강남구청 재건축사업과", "압구정동 주민센터"],
         "evidence": "공람기간 : 2026. 10. 06. ~ 2026. 11. 06.", "pdf_page": 1}
      ],
      "related_history": [
        {"label": "아파트지구 최초 지정", "date": "1976-08-21", "gosi_no": "건설부고시 제131호",
         "evidence": "건설부고시 제131호(1976.8.21.)", "pdf_page": 1}
      ]
    }
  ]
}
```
- 위 JSON 속 값은 **형식 예시**다. 실제 값은 쪽 텍스트에서 확인해 적는다.
- `items`는 모든 문서에 있다. `fields`·`projects`는 D1에만 있다 (D2~D4는 빈 객체·빈 배열).
- `item_key`는 `{doc_id}-{두 자리 순번}`. 한 번 정하면 바꾸지 않는다 (정답셋이 이 키를 쓴다).
- `item_type`: `policy`(정책 방향·원칙) | `plan`(구체 계획 내용) | `notice`(고시·공고 내용) | `stat`(현황 수치).
- `scope_type`·`scope_ref`
  | scope_type | scope_ref 예 | 표시 층 |
  |---|---|---|
  | `SIDO` | `["11"]` | 서울 전역 |
  | `SGG` | `["11680"]` 또는 동남권이면 `["11650","11680","11710","11740"]` | 자치구 |
  | `SAENGHWAL` | `["압구정·청담"]` | 법정동 (지역생활권) |
  | `BJD` | `["1168011000"]` | 법정동 |
  | `PARCEL` | `["1168011000105270000"]` | 필지 |
- `confidence`: 0~1. 범위 판단이 애매하면 0.7 미만으로 적는다 → 검수 큐.
- `needs_review`: D2 전사 쪽에서 나온 항목은 무조건 `true`.

### 9-3. 문서별 추출 지침
**D1 (강남구 공고, 쪽 1~17)**
- `fields` (아래 19개, 값이 없으면 null + 이유):
  `gosi_no`, `published_at`, `gazette_no`, `gazette_date`, `issuer`, `legal_basis`, `project_name`, `location_text`, `representative_jibun`(예: "압구정동 527"), `area_m2`, `public_review_start`, `public_review_end`, `review_places`(배열), `land_use`, `households_before`, `households_after`, `base_allowed_far`(%), `plan_far`(%), `legal_max_far`(%)
  (필드 이름은 바꾸지 않는다. 정답셋이 이 이름을 쓴다.)
- `items` 2~4개: 아파트지구 개발기본계획 토지이용계획 변경(p2, `BJD` 압구정동), 도로 결정 변경(p3~4·p6, `BJD`), 필요하면 지구단위계획 관련 언급(p17). **한양7차 정비계획 자체는 item이 아니라 `projects`로** 넣는다.
- `projects` 1개: §9-2 예시 구조. `related_history` 5건(D1 p1).

**D2 (생활권계획 강남구, 12~14 + 29~31 + 선택한 113~151)**
- 12~14쪽(텍스트): 강남구 지역생활권 구분 결과 → `SGG` 항목 1~2개 (`stat` 또는 `plan`).
- 29~31쪽(전사): 강남구 일반사항·지역생활권 현황 → `SGG` 항목 1~3개.
- 압구정·청담 선택 쪽(전사): 생활권 목표·공간구조·주거지 관리·한강변 등 → `SAENGHWAL ["압구정·청담"]` 항목 6~10개. 특정 동·구역 이름이 있으면 `BJD`로 좁힐 수 있는지 판단한다(지번이 없으면 `SAENGHWAL` 유지).
- 모든 D2 전사 쪽 항목 `needs_review: true`. 이 계획은 2018년판이라 `scope_note`에 "2030 생활권계획(2018) 기준"을 적는다.

**D3 (2030 정비기본계획, 243~248, 262~268, 275~277)**
- `SIDO` 항목 5~8개: 재건축 제도 변천의 핵심(구역해제 제도 등), 재건축 추진현황, 용적률 계획 기본방향, **표 79 주거지역 용적률 체계**(용도지역별 기준·허용·상한·법적상한 용적률 수치를 summary에 원문 그대로), 허용용적률 인센티브(표 84), 상한용적률.
- 표 75(재건축 추진 중 단지 현황, 248쪽)에 강남구 행이 있으면 강남구 수치만 `SGG ["11680"]` `stat` 항목으로 1개.

**D4 (2040 서울도시기본계획, 73, 75~80, 175~179)**
- `SIDO` 항목 4~6개: 주택·정비 부문 목표와 전략(73쪽 표의 주택·정비 행, 75~80쪽 전략 1-1~1-3 등).
- 동남권(175~179) 항목 2~4개: `SGG ["11650","11680","11710","11740"]` (동남권 = 서초·강남·송파·강동 `[확인: D2 p12 표 2. D4 175~179쪽 본문에는 권역 구성이 글로 없음]`). 한강변 주거지 관리 등.

### 9-4. 근거 문장 검사 규칙 (`core/text.py`)
```python
import re, unicodedata
_WS = re.compile(r"\s+")
_DOTS = str.maketrans({"ㆍ": "·", "․": "·", "‧": "·", "・": "·"})

def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").translate(_DOTS)
    return _WS.sub("", s)

def evidence_in(evidence: str, page_text: str) -> bool:
    e = norm(evidence)
    return len(e) >= 2 and e in norm(page_text)
```
- 근거는 2자 이상. 너무 흔한 근거(예: "230%")는 피하고 앞뒤 단어를 붙여 고유하게 만든다.
- 표 안 숫자는 같은 행의 이름과 숫자가 텍스트에서 이어져 있지 않을 수 있다. 그때는 숫자가 들어 있는 줄을 그대로 근거로 쓴다.

### 9-5. 재건축 단계 템플릿 `seed/stage_templates.yaml`
원 계획서의 재개발 13단계 표를 **그대로** 옮기고 1번만 재건축진단으로 바꾼 것이다. 원 계획서에 없는 칸은 `null`로 둔다. **Claude Code가 문구를 새로 쓰거나 고치지 않는다** (원칙 3). `what_happens`는 원 계획서에 문구가 없으므로 전부 `null` → 화면은 "단계 설명 문구는 법령 대조 후 사람이 작성합니다"로 표시한다.

```yaml
project_type: rebuild
project_type_label: 재건축
source: "Propedia 서울 MVP 개발 계획서 v1.0 「세부 단계 템플릿과 소유자 기한」 재개발 13단계 표 (재건축은 1번만 재건축진단으로 대체)"
reviewed_by: null          # 법령 대조 전 초안 (원 계획서: CEO + 로스쿨생 팀원이 법제처 현행본과 대조 예정)
reviewed_at: null
stages:
  - {seq: 1,  code: RB01, common_stage: "S0~S1", title: "재건축진단",              issuer: null,                       owner_actions: null}
  - {seq: 2,  code: RB02, common_stage: "S4",    title: "정비계획 입안·주민공람",  issuer: "자치구",                   owner_actions: "공람 기간 내 의견 제출"}
  - {seq: 3,  code: RB03, common_stage: "S6",    title: "정비구역 지정 고시",      issuer: "서울시보",                 owner_actions: "구역 경계와 내 필지 포함 여부"}
  - {seq: 4,  code: RB04, common_stage: "S7",    title: "추진위원회 승인",         issuer: "자치구",                   owner_actions: "동의서 요청 대응"}
  - {seq: 5,  code: RB05, common_stage: "S7",    title: "조합설립인가",            issuer: "자치구",                   owner_actions: "조합원 자격 확인"}
  - {seq: 6,  code: RB06, common_stage: "S7",    title: "시공자 선정",             issuer: "조합 총회 (정보몽땅 공지)", owner_actions: "총회 의결권"}
  - {seq: 7,  code: RB07, common_stage: "S7",    title: "사업시행계획인가",        issuer: "자치구",                   owner_actions: "사업시행계획 공람"}
  - {seq: 8,  code: RB08, common_stage: "S7",    title: "분양신청",                issuer: "조합 통지·일간지 공고",    owner_actions: "기간 내 미신청 시 현금청산 대상"}
  - {seq: 9,  code: RB09, common_stage: "S7",    title: "관리처분계획인가",        issuer: "자치구",                   owner_actions: "관리처분계획 공람·의견 제출"}
  - {seq: 10, code: RB10, common_stage: "S7",    title: "이주·철거",               issuer: "조합·자치구",              owner_actions: "이주 기한"}
  - {seq: 11, code: RB11, common_stage: "S8",    title: "착공·일반분양",           issuer: "자치구·건축HUB",           owner_actions: null}
  - {seq: 12, code: RB12, common_stage: "S8",    title: "준공인가·이전고시",       issuer: "자치구",                   owner_actions: "소유권 이전 등기 확인"}
  - {seq: 13, code: RB13, common_stage: "S8",    title: "청산·해산",               issuer: "조합",                     owner_actions: "청산금"}
```
- 각 stage의 `what_happens`, `legal_basis`는 `null`. `load_seed`가 YAML의 `source`, `reviewed_by`, `reviewed_at`을 모든 행에 복사한다.
- HUMAN_TODO: "재건축 단계 템플릿 문구(what_happens·법령 근거) 작성·검토 — CEO·로스쿨생 팀원".

### 9-6. 금지어 (우리가 만든 문장에만 적용, 원문 인용 근거는 예외)
`예상`, `예정`, `전망`, `지연`, `늦`, `위험`, `안전`, `유망`, `호재`, `추천`, `수익`, `투자`, `확실`, `보장`, `반드시`, `가능성 높`(판정표 3번 문구는 미구현이라 쓰지 않음)
- 적용 대상: `summary`, `title`, 화면 고정 문구(HTML·JS), API가 만드는 문구(라벨·메시지·coverage_note).
- 적용 제외: `evidence`(원문 그대로), 원문 제목(`documents.title`).
- `tests/test_wording.py`가 검사한다 (§14).

---

## 10. 조회·판정 로직 (`core/`)

`core/`는 표준 라이브러리만 쓴다. 함수는 모두 **순수 함수에 가깝게**(DB 연결과 `today`를 인자로 받음) 만들어 테스트하기 쉽게 한다.

### 10-1. `core/db.py`
```python
DB_PATH = Path(__file__).resolve().parents[1] / "db" / "propedia.db"
def connect_ro() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro&immutable=1", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con
```
- 요청마다 새 연결을 열고 닫아도 된다(작은 DB). 쓰기 연결 함수는 `core/`에 두지 않는다.

### 10-2. `core/timeutil.py`
```python
KST = timezone(timedelta(hours=9))   # Windows에 tzdata가 없어도 동작하도록 고정 오프셋
def today_kst() -> date: return datetime.now(KST).date()
def d_day(due: date, today: date) -> tuple[int, str]:
    n = (due - today).days
    return n, (f"D-{n}" if n > 0 else "D-day" if n == 0 else f"마감({due.isoformat()})")
```

### 10-3. `core/address.py` — `normalize(con, text) -> dict`
반환: `{"status": "ok"|"not_found"|"out_of_scope", "message": str|None, "road_address", "jibun_address", "pnu", "bjd_code", "sgg_code", "dong_name", "saenghwal", "lat", "lon", "coord_source", "addr_id"}`
1. 빈 입력 → `not_found` "주소를 입력해 주세요".
2. `demo_addresses`의 `input_text`·`road_address`·`jibun_address`·`aliases` 정규화 값과 일치하면 그 행(좌표 포함).
3. 지번 정규식(§8-6) 일치 → 구가 강남구가 아니면 `out_of_scope` "시연 범위(강남구) 밖입니다". 동이 코드표에 없으면 `not_found`. 있으면 PNU를 만든다. 같은 PNU가 `demo_addresses`에 있으면 그 좌표를 쓴다. 없으면 좌표 없음.
4. 문자열에 강남구가 아닌 `[가-힣]+구`가 있으면 `out_of_scope`.
5. 그 외 `not_found` "시연 주소 목록에서 찾을 수 없습니다. 지번 주소(예: 강남구 압구정동 527)로 입력해 주세요".

### 10-4. `core/lookup.py` — `lookup(con, text, decisions=None, today=None) -> dict`
1. `normalize`. 상태가 ok가 아니면 `layers`를 비운 응답(§11-3)을 돌려준다.
2. **항목 배치**: `applicability_rules`를 읽어
   - `SIDO` & `"11"` ∈ scope_ref → `city`
   - `SGG` & sgg_code ∈ scope_ref → `gu.items`
   - `SAENGHWAL` & saenghwal ∈ scope_ref → `dong.items` (`scope_label` = "지역생활권 압구정·청담")
   - `BJD` & bjd_code ∈ scope_ref → `dong.items` (`scope_label` = "법정동 압구정동")
   - `PARCEL` & pnu ∈ scope_ref → `parcel.items`
   - 검수 결정으로 `reject`된 항목은 뺀다. `edit`된 항목은 바뀐 값으로 배치한다(§10-7).
   - 정렬: 문서 날짜 최신 → `item_key` 순.
3. **사업 배치**: 이 PNU의 `project_parcels`가 있으면 판정표(§1-4)로 `included`(verified=1 또는 검수 승인) / `possible`(representative_only, verified=0) → `parcel.included_projects`. 좌표가 둘 다 있고 거리 ≤ 500m이며 포함 사업이 아니면 → `parcel.nearby_projects`(거리 정수 m, 하버사인).
4. **중복 제거**: `parcel`에 나온 사업은 `dong.projects`에서 뺀다. `dong.projects` = 같은 법정동의 나머지 사업. `dong.deadlines` = `dong.projects`의 진행 중 기한(`due_on ≥ today`).
5. `gu.projects_by_stage` = 같은 구 사업을 단계 코드별로 셈: `{"RB02": {"title": "정비계획 입안·주민공람", "count": 1}}`.
6. `parcel.land_use`: 포함(또는 포함될 수 있음) 사업의 `land_use`가 있으면 `{"value": "제3종일반주거지역", "basis": "사업 문서 기재 (D1 p5, 정비구역 기준)", "source": {...}}`. 없으면 `null` + `land_use_note` "필지별 용도지역은 프리토타입 범위 밖입니다 (브이월드 미연동)".
7. 좌표가 없으면 `parcel.nearby_note` = "좌표가 없어 주변 500m 사업 판정을 생략했습니다".
8. 지역생활권이 압구정·청담이 아니면 `coverage_note` 끝에 "{생활권} 지역생활권 장은 프리토타입 범위 밖입니다"를 붙인다.
9. `as_of` = `meta.as_of`. `disclaimer` 고정 문구(§11-3).

### 10-5. 단계 판정 규칙 `seed/stage_rules.yaml`
```yaml
# 문서 제목에 정규식을 위에서부터 적용, 처음 맞는 규칙의 code
- {id: R1, project_type: rebuild, pattern: "정비구역.*정비계획.*\\(안\\).*공람", code: RB02}
- {id: R2, project_type: rebuild, pattern: "정비구역\\s*지정.*고시", code: RB03}
- {id: R3, project_type: rebuild, pattern: "추진위원회.*승인", code: RB04}
- {id: R4, project_type: rebuild, pattern: "조합설립.*인가", code: RB05}
- {id: R5, project_type: rebuild, pattern: "사업시행계획.*인가", code: RB07}
- {id: R6, project_type: rebuild, pattern: "관리처분계획.*인가", code: RB09}
- {id: R7, project_type: rebuild, pattern: "준공인가|이전고시", code: RB12}
```
D1 제목에는 "정비구역·정비계획 결정(변경)(안) 공람·공고"가 있으므로 R1 → `RB02`. 규칙을 적용하기 전에 제목을 §9-4 `norm`이 아닌 **공백만 정리한 문자열**로 쓴다(가운뎃점 유지).

### 10-6. `core/progress.py` — `progress(con, project_id, decisions=None, today=None) -> dict`
- `stages`: 템플릿 13개. `seq < 현재` → `done`, `= 현재` → `current`, `> 현재` → `upcoming`. `done` 단계에 `project_stage_history` 근거가 없으면 `verified: false`, `note: "확인된 고시 없음"`.
- `current`: 현재 단계 템플릿(`what_happens`가 null이면 `what_happens_note` "단계 설명 문구는 법령 대조 후 사람이 작성합니다"), `owner_actions`, `template_status` = `reviewed_by`가 null이면 "법령 대조 전 초안".
- `next`: 다음 단계의 `code`, `title`, `owner_actions`.
- `deadlines`: 사업의 모든 기한 + `d_day`, `d_day_label`(§10-2), `status` (`open`|`closed`).
- `remaining`: `{"to_next": null, "to_completion": null, "note": "비교할 사례가 부족합니다", "method_note": "원 계획은 비슷한 사업들의 단계별 소요 기간(생존분석)으로 범위를 보여줍니다. 프리토타입에는 비교 사례가 없습니다."}`
- `related_history`, `documents`(사업에 묶인 문서와 역할), `stage_basis`(현재 단계 근거: 문서·쪽·근거 문장·규칙 id).
- `position_label`: "재건축 13단계 중 2번째".

### 10-7. `core/review.py` — 검수 결정 적용 (서버에 저장하지 않음)
- 결정 형식: `{"review_id": 3, "action": "approve"|"reject"|"edit", "edits": {"summary": "...", "scope_type": "...", "scope_ref": [...]}, "decided_at": "ISO"}`
- `apply(con, decisions) -> Overrides`
  - `parcel_inclusion` approve → 그 (project, pnu)를 `included`, basis `manual_review`. reject → 포함 목록에서 빼고(좌표로 500m 이내면 `nearby`로).
  - `vision_item`·`scope_uncertain`·`evidence_mismatch` approve → 해당 항목의 "검수 필요" 표시 제거. reject → 응답에서 제외. edit → `summary`·`scope_type`·`scope_ref`를 바꾼 값으로 배치.
  - `field_low_confidence`·`stage_uncertain` → 문서 DB 화면 표시에만 반영.
  - 없는 `review_id`, 잘못된 action은 무시하고 `review_applied`에 `{"review_id": n, "ignored": "이유"}`로 알려준다.
- 응답의 `events`에 결정마다 `{"event_type": "review_decision", "review_id", "action", "title"}`를 넣는다.

---

## 11. API 명세 (`api/index.py`)

### 11-1. 공통
- FastAPI 앱 이름은 반드시 `app`. 경로는 모두 `/api/v1/...`.
- 파일 맨 위에서 프로젝트 루트를 import 경로에 넣는다: `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`.
- Vercel이 아닐 때만(`os.environ.get("VERCEL") != "1"`) 모든 API 라우트 등록 **뒤에** `app.mount("/", StaticFiles(directory=ROOT/"public", html=True), name="public")`. (Vercel에서는 `public/`을 CDN이 서빙한다.)
- Vercel일 때는 `GET /`(그리고 `/index.html`이 CDN에서 안 잡히는 경우 대비)로 들어오면 `RedirectResponse("/index.html")`를 돌려주는 라우트를 둔다.
- 응답은 JSON, 한글 그대로 (`ensure_ascii=False` 효과는 FastAPI 기본 JSONResponse로 충분).
- 오류: 404 `{"detail": "…"}` 한국어 메시지.

### 11-2. 엔드포인트
| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/v1/health` | `{"status":"ok","build_at","as_of","schema_version"}` |
| GET | `/api/v1/demo-addresses` | 시연 주소 10건 `[{addr_id,label,input_text,road_address,jibun_address,in_scope}]` |
| GET | `/api/v1/lookup?address=` | 4개 층 통합 응답 (§11-3) |
| POST | `/api/v1/lookup` | body `{"address": "...", "decisions": [...]}` → 검수 결정을 적용한 응답 |
| GET | `/api/v1/parcels/{pnu}/projects` | `{"pnu","projects":[{project_id,name,inclusion,inclusion_label,basis,distance_m,evidence_source}]}` |
| GET | `/api/v1/projects/{project_id}/progress` | 진행상황 (§11-4) |
| POST | `/api/v1/projects/{project_id}/progress` | body `{"decisions": [...]}` |
| GET | `/api/v1/documents` | 문서 4건 요약 `[{doc_id,short_title,doc_kind,published_at,page_ranges,text_status,pages_selected,pages_text_ok,items,evidence_ok_rate,ingest_step,source}]` |
| GET | `/api/v1/documents/{doc_id}` | 문서 상세: 메타, 쪽 목록(텍스트 제외), 필드(D1), 항목, 사업, 추출 JSON 원문 |
| GET | `/api/v1/documents/{doc_id}/pages/{pdf_page}` | 쪽 텍스트, 이미지 URL, method, 그 쪽에서 나온 항목·필드와 근거 |
| GET | `/api/v1/events` | 투입 단계별 `[{step, doc_id, short_title, events:[...]}]` |
| GET | `/api/v1/review-queue` | 검수 항목 목록 (쪽 이미지 URL·근거 포함) |
| GET | `/api/v1/eval` | `meta.eval_report` JSON (§13-4) |

### 11-3. `lookup` 응답 예시 (값은 형식 예시)
```json
{
  "query": "강남구 압구정동 527",
  "status": "ok",
  "message": null,
  "normalized": {
    "addr_id": "A1", "road_address": "서울특별시 강남구 …", "jibun_address": "서울특별시 강남구 압구정동 527",
    "pnu": "1168011000105270000", "bjd_code": "1168011000", "sgg_code": "11680",
    "dong_name": "압구정동", "saenghwal": "압구정·청담", "lat": 37.53, "lon": 127.03, "coord_source": "osm-nominatim:road"
  },
  "as_of": "2026-10-06",
  "layers": {
    "city":  [ITEM],
    "gu":    {"items": [ITEM], "projects_by_stage": {"RB02": {"title": "정비계획 입안·주민공람", "count": 1}}},
    "dong":  {"items": [ITEM], "projects": [], "deadlines": []},
    "parcel": {
      "items": [],
      "land_use": {"value": "제3종일반주거지역", "basis": "사업 문서 기재 (정비구역 기준)", "source": SOURCE},
      "land_use_note": null,
      "included_projects": [{
        "project_id": 1, "name": "압구정아파트지구 특별계획구역6-1 재건축 정비구역",
        "inclusion": "possible", "inclusion_label": "포함될 수 있음",
        "message": "압구정아파트지구 특별계획구역6-1 재건축 정비구역 구역에 포함될 수 있습니다",
        "basis": "representative_only", "basis_label": "고시에 대표 지번(527번지 일대)만 있음",
        "review_id": 1, "progress_url": "/api/v1/projects/1/progress", "source": SOURCE
      }],
      "nearby_projects": [],
      "nearby_note": null
    }
  },
  "review_applied": [],
  "events": [],
  "coverage_note": "프리토타입: 강남구, 문서 4종 … ",
  "disclaimer": "공개된 고시·공식 데이터 기준 정보이며, 조합 공지와 다를 수 있습니다. 개별 권리 판단은 하지 않습니다."
}
```
- `ITEM` = `{"item_key","item_type","title","summary","scope_type","scope_label","needs_review","evidence","evidence_ok","source": SOURCE}`
- `SOURCE` = `{"doc_id","short_title","published_at","pdf_page","page_label","page_image":"/pages/D3/p265.jpg","source_url","source_note"}`
- 상태가 `not_found`/`out_of_scope`이면 `normalized`는 아는 값만, `layers`는 `null`, `message`에 안내 문구.

### 11-4. `progress` 응답 예시
```json
{
  "project_id": 1, "name": "…", "aliases": ["한양7차아파트 재건축"],
  "project_type": "rebuild", "project_type_label": "재건축", "track": "unknown", "track_label": "확인 안 됨",
  "as_of": "2026-10-06", "position_label": "재건축 13단계 중 2번째",
  "stages": [
    {"seq": 1, "code": "RB01", "title": "재건축진단", "status": "done", "verified": false, "note": "확인된 고시 없음", "source": null},
    {"seq": 2, "code": "RB02", "title": "정비계획 입안·주민공람", "status": "current", "verified": true, "entered_at": "2026-10-06", "source": SOURCE},
    {"seq": 3, "code": "RB03", "title": "정비구역 지정 고시", "status": "upcoming"}
  ],
  "current": {"code": "RB02", "title": "…", "what_happens": null,
              "what_happens_note": "단계 설명 문구는 법령 대조 후 사람이 작성합니다",
              "owner_actions": "공람 기간 내 의견 제출", "issuer": "자치구", "template_status": "법령 대조 전 초안"},
  "next": {"code": "RB03", "title": "정비구역 지정 고시", "owner_actions": "구역 경계와 내 필지 포함 여부"},
  "deadlines": [{"kind": "public_review", "title": "정비계획(안) 주민공람", "starts_on": "2026-10-06", "due_on": "2026-11-06",
                 "d_day": 12, "d_day_label": "D-12", "status": "open",
                 "how_to_submit": "공람기간 내에 의견서를 공람장소로 제출", "places": ["강남구청 재건축사업과", "압구정동 주민센터"], "source": SOURCE}],
  "remaining": {"to_next": null, "to_completion": null, "note": "비교할 사례가 부족합니다", "method_note": "…"},
  "related_history": [{"label": "아파트지구 최초 지정", "date": "1976-08-21", "gosi_no": "건설부고시 제131호", "source": SOURCE}],
  "stage_basis": {"rule_id": "R1", "evidence": "…", "source": SOURCE},
  "disclaimer": "…"
}
```

---

## 12. 화면 명세 (`public/`)

### 12-1. 공통
- 정적 HTML 5개 + `assets/style.css` + `assets/app.js`(공통) + 화면별 JS. **빌드 도구·외부 CDN·외부 글꼴 금지** (오프라인 로컬에서도 동작).
- 글꼴: `font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif;` (설치된 것만 쓰임).
- 화면 폭 1280px(노트북·프로젝터) 기준, 768px 이하에서도 한 줄로 무너지지 않게.
- 모든 화면 위쪽 공통 머리글: 로고 문자 "Propedia 프리토타입" · 메뉴(시작 / 주소 조회 / 문서 DB / 검수 / 평가) · 오른쪽에 "기준일 {as_of}" 와 검수 결정이 있으면 "검수 결정 {n}건 반영 중 [초기화]" 표시.
- 공통 띠 문구: "강남구 · 공개 문서 4종으로 만든 시연용 프리토타입입니다."
- `app.js` 공통 함수
  - `api(path, {method, body})`: 상대 경로 fetch(`/api/v1/...`), 실패 시 화면에 오류 상자.
  - `getDecisions()/setDecisions()/clearDecisions()`: `localStorage` 키 `propedia.pretotype.decisions.v1`. **모든 읽기·쓰기를 try/catch로 감싼다** (사생활 보호 모드 대비, 실패하면 메모리 변수로 대체).
  - `sourceLine(source)`: "D3 · 2030 정비기본계획 · PDF 265쪽(인쇄 252쪽) · 2025-06-26" 형식 문자열.
  - `openPage(source, evidence)`: 모달로 쪽 이미지(`source.page_image`)와 근거 문장, 출처 링크(`source_url`이 있으면 "원문 게시처 열기", 없으면 `source_note`)를 보여준다. Esc·바깥 클릭으로 닫힘.
  - `badge(text, kind)`: kind = `ok`(초록) / `warn`(주황) / `muted`(회색) / `info`(파랑).
  - 날짜는 `YYYY.MM.DD`로 표시.
- 색: CSS 변수로 정의 (`--bg #fff`, `--text #1f2328`, `--muted #6b7280`, `--line #e5e7eb`, `--ok #1a7f37`, `--warn #b45309`, `--info #1d4ed8`, `--card #f8fafc`). 다크 모드는 하지 않는다.
- 문구 규칙: §9-6 금지어 금지. 판정 문구는 §1-4 그대로.

### 12-2. `index.html` — 시작 화면
1. 제목 "주소 하나로, 그 땅에 걸린 공공 문서와 사업 진행상황을" + 2~3문장 설명 (§1-1을 쉬운 말로).
2. **시연 순서** 카드 5개 (번호, 제목, 한 줄 설명, 버튼):
   ① 주소 조회 — "압구정동 527을 조회해 4개 층과 사업 카드를 봅니다" → `lookup.html?addr=A1`
   ② 원문과 근거 — "결과의 근거 문장이 원문 어느 쪽에서 왔는지 확인합니다" → `docs.html?doc=D1`
   ③ 문서 투입 순서 — "문서가 들어올 때 사업 상태가 바뀌는 경우만 기록됩니다" → `docs.html#steps`
   ④ 사람 검수 — "애매한 판정을 사람이 확정하면 결과가 바뀝니다" → `review.html`
   ⑤ 평가 — "정답셋과 비교한 정확도" → `eval.html`
3. **반영 범위** 표: 문서 4종 (ID, 문서, 층, 쪽), `coverage_note`.
4. **원칙** 5줄: 사실만 / 근거 문장과 원문 쪽 / 단계는 고시로만 / 안내 문구는 사람이 작성 / 남은 기간은 예측하지 않음.

### 12-3. `lookup.html` — 주소 조회 (= 내부 검증 화면)
1. 입력창 + "조회" 버튼 + 시연 주소 칩 10개(`/api/v1/demo-addresses`의 `label`). URL `?addr=A1` 또는 `?q=...`로 바로 조회.
2. 정규화 결과 한 줄: 지번 · 도로명 · PNU(고정폭 글꼴) · 법정동 · 지역생활권 · 좌표 출처.
3. 상태가 `not_found`/`out_of_scope`이면 안내 상자만.
4. **4개 층 섹션**을 넓은 층부터: 서울 전역 → 자치구 → 법정동 → 필지. 섹션 제목 옆에 항목 수. 비어 있으면 "이 층에 해당하는 항목이 없습니다".
   - 항목 카드: 제목, 범위 배지(`scope_label`), 요약, 출처 줄, [원문 보기] [근거 보기(접기)], `needs_review`면 주황 배지 "검수 필요", `evidence_ok=0`이면 "근거 확인 필요".
   - 자치구 섹션 끝: "강남구 진행 사업 단계 분포" 작은 표.
5. **필지 섹션**
   - 용도지역 줄 (값 + basis, 없으면 note).
   - 포함 사업 카드: 판정 배지(`included` 초록 "포함" / `possible` 주황 "포함될 수 있음"), 메시지, 판정 근거(basis_label), 출처 줄, [검수 화면에서 확인] 링크(`review.html?id={review_id}`).
   - 그 아래 **사업 진행 카드** (`/api/v1/projects/{id}/progress`):
     - 머리: 사업명 · 유형 배지(재건축) · 추진 방식 · 기준일
     - 단계 막대: 13칸 (완료=초록, 현재=파랑 굵게, 예정=회색) + `position_label`
     - 단계 칩 목록 13개 (번호+이름, `verified=false`인 완료 단계는 "확인된 고시 없음" 툴팁)
     - "지금 단계" 상자: 이름, 발행처, 설명(없으면 note), 소유자가 챙길 것, 템플릿 상태 배지("법령 대조 전 초안")
     - "다음 단계" 상자: 이름, 소유자가 챙길 것
     - "진행 중인 기한" 표: 제목, 기간, D-day 배지, 제출 방법, 장소, 출처
     - "남은 기간" 상자: note + 접기 "계산 방법 참고"(method_note)
     - "관련 고시 이력" 목록 (날짜순)
     - 고지 문구 (회색 작은 글씨)
   - 주변 사업 목록 (이름 · 거리 m · [진행상황 보기]) 또는 nearby_note.
6. 맨 아래 `coverage_note`, `disclaimer`.
7. 접기 상자 **"API 응답 보기"**: 요청 방식·주소(예: `GET /api/v1/lookup?address=…`, 검수 결정이 있으면 `POST` + body)와 보기 좋게 들여쓴 JSON. "복사" 버튼.
8. 검수 결정이 있으면 `POST`로 조회하고, 응답의 `events`(review_decision)를 상단에 "검수 결정 반영: …" 알림으로 보여준다.

### 12-4. `docs.html` — 문서 DB
1. 문서 카드 4개 (투입 순서대로): 짧은 제목, 종류, 발행일, 쪽 범위, 텍스트화 상태, 선택 쪽 수/텍스트 확보 쪽 수, 항목 수, 근거 일치율, 출처.
2. 문서를 고르면(`?doc=D1`):
   - 쪽 목록 (쪽 번호 · method 배지 `텍스트`/`전사`/`이미지만` · 글자 수 · 선택 여부)
   - 쪽을 고르면 2단: 왼쪽 쪽 이미지, 오른쪽 쪽 텍스트. 텍스트 안에서 그 쪽 항목·필드의 근거를 `<mark>`로 표시한다 (공백 무시 매칭: 근거 글자 사이에 `\s*`를 넣은 정규식, 특수문자 escape).
   - 그 쪽에서 나온 항목·필드 목록 (값, 신뢰도, 근거 일치 여부).
   - D1이면 "필드" 표 (필드명 한국어 라벨, 값, 단위, 쪽, 신뢰도, 근거 일치), "사업" 요약 (사업 카드로 묶인 결과 → `lookup.html?addr=A1` 링크).
   - 접기 "추출 JSON 원문".
3. **문서 투입 순서** 섹션(`#steps`): 단계 버튼 1~4 (D4 → D3 → D2 → D1). 단계를 누르면 그 단계에 들어온 문서와 그때 생긴 이벤트 목록. 이벤트 0건이면 "사업 상태 변화 없음 — 이벤트를 만들지 않습니다". 위에 설명 한 줄: "문서가 들어와도 사업의 단계·기한이 바뀔 때만 변경 기록(change_events)이 생깁니다."

### 12-5. `review.html` — 검수 도구
1. 위: 설명 "시연용 검수 결정은 이 브라우저에만 저장되고, 조회할 때 서버에 함께 보내져 결과에 반영됩니다." + [시연 초기화] 버튼.
2. 검수 목록 표: 유형(한국어 라벨), 제목, 사유, 상태(미결정/승인/반려/수정). `parcel_inclusion`을 맨 위에.
3. 항목을 고르면(`?id=`): 왼쪽 쪽 이미지, 오른쪽 현재 값(`proposed.current`)·근거 문장·출처. 버튼 [승인] [반려] [수정](수정은 `editable_fields`가 있을 때만, 요약은 textarea, 범위는 select).
4. 결정 직후 안내: "결정이 저장되었습니다. 주소 조회 화면에서 확인하세요" + `lookup.html?addr=A1` 링크 (parcel_inclusion이면).
5. 유형 라벨: `parcel_inclusion` 포함 판정 / `evidence_mismatch` 근거 불일치 / `vision_item` 이미지 전사 항목 / `scope_uncertain` 적용 범위 판단 / `field_low_confidence` 낮은 신뢰도 필드 / `stage_uncertain` 단계 판정.

### 12-6. `eval.html` — 평가 리포트
1. 맨 위 안내 상자: "표본이 작아 수치 자체보다 평가 체계가 돌아가는 것을 보여주는 것이 목적입니다." + 정답셋이 초안이면 주황 배지 "정답셋 초안 — 사람 확정 전, 추출자와 같은 작성자".
2. 지표 카드(§13-2 순서): 값, 목표, 통과/미달 배지, 분자/분모.
3. 층별 재현율·정밀도 표 (층 × 재현율·정밀도·기대 수·응답 수).
4. 주소별 결과 표 (A1~A10: 상태 일치, PNU 일치, 층별 일치 수, 포함 판정 일치).
5. 오류 목록 (유형별: 정규화 / 범위 판정 / 추출 / 포함 판정 / 근거).
6. 실행 시각, 빌드 시각, 정답셋 버전.

---

## 13. 평가 (정답셋·지표·리포트)

### 13-1. 정답셋 파일 (`evals/goldset/`, 사람 소유)
Claude Code는 **초안**만 쓰고 맨 위에 `draft: true`, `author: "claude-code (초안)"`, `note`를 적는다. 사람이 확정하면 `draft: false`, `confirmed_by`를 적는다(HUMAN_TODO).

1. `extraction.yaml` — D1 필드 정답. **P1에서, 추출(P2) 전에** §3-5와 쪽 텍스트를 보고 쓴다.
   ```yaml
   draft: true
   author: "claude-code (초안)"
   note: "추출 전에 원문 텍스트만 보고 작성. 사람 확인 필요"
   doc_id: D1
   fields:
     gosi_no:            {value: "강남구 공고 제2026-2347호", match: text}
     published_at:       {value: "2026-10-06", match: date}
     area_m2:            {value: 22123.6, match: number}
     public_review_end:  {value: "2026-11-06", match: date}
     review_places:      {value: ["강남구청 재건축사업과", "압구정동 주민센터"], match: set}
     # … §9-3의 필드 전부
   stage: RB02
   representative_pnu: "1168011000105270000"
   ```
   - `match`: `text`(norm 후 같음, 또는 `accept` 목록 중 하나), `number`(float 같음), `date`(ISO 같음), `set`(norm 후 집합 같음).
2. `addresses.yaml` — 주소 정답 (P1에서 resolve 결과로 초안, 기대값은 규칙으로):
   ```yaml
   draft: true
   addresses:
     - {addr_id: A1, input: "강남구 압구정동 527", status: ok, pnu: "1168011000105270000",
        bjd_code: "1168011000", sgg_code: "11680", saenghwal: "압구정·청담",
        projects: [{project_key: apgujeong-6-1-hanyang7, inclusion: possible}]}
     - {addr_id: A10, input: "…", status: out_of_scope}
   ```
   - A4는 거리 ≤ 500m가 좌표로 확인됐을 때만 `inclusion: nearby`를 넣는다.
3. `scope_labels.yaml` — 항목별 정답 범위. **P2 추출 후**, 각 항목의 쪽 텍스트를 다시 읽고 `item_key`마다 `scope_type`, `scope_ref`를 적는다. 추출 결과와 같은 사람(Claude Code)이 쓰므로 `note`에 "추출자와 같은 작성자 — 수치가 낙관적일 수 있음"을 적는다.

### 13-2. 지표 (`evals/run_eval.py`)
| # | 지표 | 정의 | 목표 |
|---|---|---|---|
| M1 | 텍스트화 성공률 | 선택 쪽 중 텍스트(또는 전사) 공백 제외 30자 이상인 쪽 / 선택 쪽 | ≥ 95% |
| M2 | 근거 문장 일치율 | `evidence_ok=1`인 근거 / 전체 근거 (항목 + D1 필드 + 사업) | 100% |
| M3 | D1 필드 정확도 | 정답과 일치한 필드 / 정답 필드 | ≥ 90% |
| M4 | 적용 범위 정확도 | `scope_type`과 `scope_ref`가 정답과 같은 항목 / 라벨된 항목 | ≥ 95% |
| M5 | 주소 정규화 정확도 | 상태·PNU·법정동·생활권이 정답과 같은 주소 / 주소 | 100% |
| M6 | 층별 재현율 | 층마다: 응답에 나온 기대 항목 / 기대 항목 (전 주소 합) | 층마다 ≥ 90% |
| M7 | 층별 정밀도 | 층마다: 기대 항목인 응답 항목 / 응답 항목 | 층마다 ≥ 95% |
| M8 | 포함 판정 정확도 | 사업 포함 판정이 정답과 같은 (주소, 사업) / 정답 쌍 | 100% |
| M9 | 원문 링크 유효율 | `page_image` 파일이 `public/`에 있는 응답 항목 / 응답 항목 | 100% |
| M10 | 응답 시간 p95 | `TestClient`로 주소 10건 × 20회 `/api/v1/lookup`, 95번째 백분위 (ms) | ≤ 3000ms |
| M11 | 금지어 | 우리가 만든 문장(§9-6 적용 대상)의 금지어 개수 | 0 |
| M12 | 단계 판정 | 사업 단계 코드가 정답(`RB02`)과 같음 | 일치 |

- **기대 항목 계산(M6·M7)**: 주소의 정답 코드(`addresses.yaml`)와 항목의 정답 범위(`scope_labels.yaml`)로 §10-4의 배치 규칙을 **평가 스크립트 안에서 따로** 적용해 층별 기대 항목 집합을 만든다 (`core/lookup.py`를 import 해서 쓰지 않는다 — 같은 코드로 채점하면 의미가 없다). 사업은 `projects` 정답으로 필지/법정동 층 기대값을 만든다.
- 상태가 ok가 아닌 주소(A10)는 층 계산에서 빼고 M5에서만 본다.

### 13-3. 실행
`python -m evals.run_eval` → (1) 지표 계산 (2) `evals/report.md` 작성 (3) `db/propedia.db`의 `meta.eval_report`에 JSON 저장 (빌드 쓰기 연결 사용) (4) 콘솔에 지표 표 출력. 목표 미달이 있어도 종료 코드는 0, 단 스크립트 오류는 1.

### 13-4. `meta.eval_report` JSON 형식
```json
{"run_at": "…", "build_at": "…", "goldset": {"draft": true, "files": {"extraction": "…sha256 앞 8자", "addresses": "…", "scope_labels": "…"}},
 "metrics": [{"id": "M1", "name": "텍스트화 성공률", "value": 1.0, "display": "100% (52/52)", "target": "≥ 95%", "pass": true}],
 "layers": [{"layer": "city", "recall": 1.0, "precision": 1.0, "expected": 40, "returned": 40}],
 "addresses": [{"addr_id": "A1", "status_ok": true, "pnu_ok": true, "layer_hits": {"city": "5/5"}, "inclusion_ok": true}],
 "errors": [{"type": "scope", "detail": "D2-07: 정답 BJD, 응답 SAENGHWAL"}]}
```

### 13-5. 목표 미달일 때
코드 버그면 고친다. 추출값이 틀렸으면 `extractions/*.json`을 원문 기준으로 고친다(정답을 보고 맞추지 말고 원문을 다시 읽는다). 정답셋이 틀렸다고 판단되면 정답을 고치지 말고 HUMAN_TODO에 "정답셋 확인 필요: …"로 남긴다.

---

## 14. 테스트 (`tests/`, `pytest -q`)
| 파일 | 확인 내용 |
|---|---|
| `test_pnu.py` | `make_pnu` (일반·산·부번), 압구정동 527 → `1168011000105270000` |
| `test_address.py` | A1·A3 입력 변형이 같은 PNU / 서초구 → `out_of_scope` / "강남구 없는동 1" → `not_found` / 빈 입력 |
| `test_text.py` | `norm`·`evidence_in`: 공백·줄바꿈·가운뎃점 변형 무시, 2자 미만 거부 |
| `test_lookup.py` | A1: 4개 층 모두 1개 이상 / 필지에 한양7차 `possible` / 같은 사업이 법정동 층에 없음(중복 제거) / A8: 사업 없음, coverage_note에 범위 밖 문구 / 모든 ITEM에 `source.pdf_page`·`page_image` 있고 파일 존재 |
| `test_progress.py` | `today=2026-10-25` 고정: 13단계 중 2번째, 다음 RB03, 공람 `D-12`, `today=2026-11-06` → `D-day`, `2026-11-07` → `마감(2026-11-06)`, remaining.note 문구 |
| `test_review.py` | 결정 없음 → 원래 결과 / parcel_inclusion approve → `included` / reject → 포함 목록에서 빠짐 / 없는 review_id → ignored / item reject → 응답에서 빠짐 |
| `test_api.py` | `TestClient`로 모든 엔드포인트 200, lookup 응답 키 구조(§11-3), POST lookup 결정 반영 |
| `test_readonly.py` | `connect_ro()` 연결로 INSERT 시도 → 예외 |
| `test_wording.py` | `public/*.html`, `public/assets/*.js`, DB의 `summary`·`title`, API 생성 문구에 §9-6 금지어 없음 (`evidence`·`documents.title` 제외) |
| `test_no_network.py` | `core/`, `api/` 소스에 `httpx`, `requests`, `urllib.request`, `socket` import가 없음 |
| `test_db_build.py` | 사업 1건, 단계 RB02, 기한 due 2026-11-06, change_events는 step 4에만 2건, review_queue에 parcel_inclusion 1건 |

---

## 15. 배포(Vercel)와 로컬 실행

### 15-1. Vercel 동작 방식 `[확인: Vercel 문서 2026-10]`
- Vercel은 `requirements.txt`의 FastAPI를 보고 자동 인식하며, `app.py`·`index.py`·`main.py` 등(프로젝트 루트 또는 `api/`·`app/`·`src/` 아래)의 `app` 객체를 진입점으로 쓴다. 앱 전체가 함수 1개로 돌아간다. Python 기본 3.12.
- `public/` 폴더 파일은 CDN이 서빙한다 (`/pages/D1/p001.jpg`, `/lookup.html` 등).
- Python 함수는 도달 가능한 파일을 모두 묶는다(최대 500MB) → `.vercelignore`로 빌드 전용 파일을 뺀다.
- Hobby(무료) 플랜: 운영 주소는 기본 공개. 비밀번호 보호 없음. **비상업·개인 용도 조건**.

### 15-2. `.vercelignore`
```
.env
.venv/
build/
data_raw/
extractions/
pipeline/
evals/goldset/
tests/
seed/
*.bat
```
(`db/propedia.db`, `core/`, `api/`, `public/`, `requirements.txt`는 올라가야 한다. `evals/run_eval.py`는 런타임에 쓰지 않으므로 올라가도 무방.)

### 15-3. 배포 후 `/api/v1/*`가 404일 때
프로젝트 루트에 `vercel.json`을 만들고 다시 배포한다:
```json
{ "rewrites": [ { "source": "/api/(.*)", "destination": "/api/index" } ] }
```
그래도 안 되면 `api/index.py`를 루트 `index.py`로 옮기는 방법을 시도하고(§15-1 자동 인식 위치), 결과를 §21에 기록한다.

### 15-4. 로컬 실행·`run_demo.bat`
- 개발 중: `source .venv/Scripts/activate && export PYTHONUTF8=1 && python -m uvicorn api.index:app --port 8000 --reload` → `http://127.0.0.1:8000/`
- `run_demo.bat` (시연 백업용, 더블클릭으로 실행. **CRLF 줄끝, UTF-8**로 저장):
```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo [준비] 가상환경을 만듭니다...
  python -m venv .venv || (echo Python 3.11 이상이 필요합니다. & pause & exit /b 1)
)
call ".venv\Scripts\activate.bat"
python -m pip install -q -r requirements.txt
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000/"
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
pause
```

### 15-5. GitHub·Vercel 배포 순서 (P8, 사람과 함께)
1. Claude Code: `gh auth status`로 GitHub CLI 로그인 확인.
   - 로그인돼 있으면 `gh repo create propedia-pretotype --private --source . --push`.
   - 아니면 멈추고(§19-1) 사람에게 요청: "GitHub에 빈 비공개 저장소 `propedia-pretotype`를 만들고 주소를 알려 주세요" → `git remote add origin <주소>` → `git push -u origin main`.
2. 사람: vercel.com에 GitHub 계정으로 가입 → New Project → 저장소 Import → Framework는 자동(FastAPI) → Deploy.
3. 사람이 알려준 `https://….vercel.app`으로 Claude Code가 확인: `curl -s https://…/api/v1/health`, `curl -s "https://…/api/v1/lookup?address=강남구%20압구정동%20527" | head -c 600`, 브라우저 화면 5개.
4. README·DEMO.md에 주소 기록, HUMAN_TODO 해당 줄 닫기.

---

## 16. README.md · DEMO.md 내용

### 16-1. README.md (개발자·동혁용)
1. 한 줄 소개, 반영 범위(문서 4종), 원칙.
2. 폴더 구조 요약.
3. 설치: Python 3.11+, `python -m venv .venv`, `pip install -r requirements.txt -r requirements-build.txt`, `PYTHONUTF8=1`.
4. 빌드 순서: `pipeline.collect → textify → contact_sheet → (Claude Code 전사·추출) → resolve_addresses → geocode → run_all → evals.run_eval`. 네트워크가 필요한 단계 표시.
5. 실행: `run_demo.bat` 또는 uvicorn 명령. 테스트: `pytest -q`.
6. 배포: §15-5 (화면 캡처 자리 표시).
7. 알려진 한계: 경계 데이터 없음, 생활권은 2018판, 좌표는 OSM, 템플릿 문구 미검토, 정답셋 초안.

### 16-2. DEMO.md (시연자용, 개발 지식 없이 읽히게)
1. 준비 (시연 10분 전): 주소 열기, 시작 화면 확인, 검수 화면에서 [시연 초기화].
2. **5분 대본** (화면·클릭·말할 내용):
   - (30초) 시작 화면 — "주소 하나로 그 땅에 걸린 공공 문서를 4개 층으로 모읍니다. 오늘은 강남구 공개 문서 4종으로 만든 시연판입니다."
   - (1분 30초) 주소 조회 A1 — 4개 층을 위에서 아래로 훑기 → 필지의 한양7차 카드 "포함될 수 있음" → 사업 카드: 13단계 중 2번째, 공람 마감 D-day → "원문 보기"로 쪽 이미지 → "API 응답 보기".
   - (1분) 문서 DB — D1 1쪽 이미지와 텍스트에서 근거 표시 → 문서 투입 순서 1~4 (D1에서만 변경 기록).
   - (1분) 검수 — 포함 판정 항목 [승인] → 주소 조회로 돌아가 "포함"으로 바뀐 것 확인.
   - (1분) 평가 — 지표 카드와 "정답셋 초안" 배지 설명.
3. 예상 질문과 답 (각 2~3줄): 데이터는 어디서 오나 / 서울 전체로 넓히면 / 정확도는 어떻게 보장하나 / AI가 틀리면 / 남은 기간은 왜 비어 있나 / 개인정보·저작권(고시 원문은 저작권 보호 대상 아님, 이용조건 불분명 자료 미사용).
4. 문제가 생기면: 주소가 안 열림 → 백업 영상/스크린샷(`docs/screens/`가 있으면) 또는 `run_demo.bat`. 결과가 이상함 → [시연 초기화] 후 새로고침.

---

## 17. 절대 규칙
1. `../data/` 원본 파일을 수정·이동·삭제하지 않는다. 발췌본만 `data_raw/`에 만든다.
2. `.env`의 키 값을 출력·로그·커밋·Vercel 환경변수에 넣지 않는다. 키는 `pipeline/resolve_addresses.py`만 읽는다. 다른 폴더의 `.env`는 열지 않는다.
3. 사업 단계는 고시 근거(`stage_rules.yaml` + 문서 제목)로만 정한다. 추출값(`stage_candidate`)만으로 바꾸지 않는다.
4. 단계 설명·소유자 안내 문구는 `seed/stage_templates.yaml`(원 계획서 표)에서만 나온다. Claude Code가 문구를 만들거나 고치지 않는다.
5. 모든 근거 문장은 쪽 텍스트에 그대로 있어야 한다(§9-4). 없으면 검수 큐.
6. 우리가 만든 문장에 §9-6 금지어를 쓰지 않는다. 사실과 출처만 보여준다. 점수·등급·예측 금지.
7. 정답셋은 사람 소유다. Claude Code는 `draft: true` 초안만 만들고, 추출 전에 쓴 정답(extraction.yaml)을 추출 중에 열지 않는다.
8. 시연 경로(`public/`, `api/`, `core/`)는 네트워크·LLM을 호출하지 않고, DB를 읽기 전용으로 연다.
9. 가짜 고시·가짜 사업·가짜 숫자를 만들지 않는다. 예시가 필요하면 화면에 "예시"라고 쓴다.
10. 추출 JSON에 원문에 없는 값을 추정해 넣지 않는다. 없으면 `null` + `null_reason`.
11. 외부 LLM API를 호출하지 않는다. 추출·전사는 Claude Code가 직접 한다.
12. 단계 완료 = 해당 단계 "완료 확인" 통과 + `PROGRESS.md` 기록 + commit.
13. 이 파일과 실제가 다르면 실제를 따르고 이 파일을 고친 뒤 §21에 기록한다.

---

## 18. 단계별 작업 계획

> 체크박스는 `PROGRESS.md`에 복사해 진행 상황을 표시한다.

### P0 환경·뼈대
- [ ] `python --version` (3.11 이상). 없으면 §19-1.
- [ ] `python -m venv .venv && source .venv/Scripts/activate && export PYTHONUTF8=1`
- [ ] `requirements.txt`, `requirements-build.txt` 작성(§5-2) → `pip install -r requirements.txt -r requirements-build.txt`
- [ ] §6 폴더·빈 `__init__.py` 생성, `db/schema.sql`(§7), `PROGRESS.md`·`HUMAN_TODO.md`(§20)
- [ ] `.gitignore` 확인 (이미 있음) → `git init -b main` (git이 오래돼 `-b`가 안 되면 `git init && git checkout -b main`) → `git add -A` → `git commit -m "P0: 뼈대"`
- 완료 확인: `python -c "import fastapi, pdfplumber, pypdfium2, pypdf, yaml, httpx, dotenv; print('ok')"` 출력 ok / `git check-ignore .env` 가 `.env` 출력 / `git log --oneline | head -1`

### P1 원문 준비·시연 주소·정답셋 초안
- [ ] `pipeline/common.py`, `core/text.py`, `core/address.py`의 PNU·정규식 부분
- [ ] `python -m pipeline.collect` → `data_raw/` 4개 + `manifest.csv`
- [ ] `python -m pipeline.textify` → 쪽 텍스트·이미지·`build/page_heads.txt`. §3-2 표와 대조, 다르면 §0-1-5
- [ ] `python -m pipeline.contact_sheet D2 113 151` 및 `D2 29 31` → 모아보기 확인 → `seed/d2_selected_pages.yaml`
- [ ] D2 선택 쪽 + 29~31쪽 전사 (§8-4) → `pages.json` 갱신
- [ ] D2 12~14쪽과 생활권 범위 쪽으로 `seed/bjd_codes.csv` 생활권 확정(압구정동·청담동·신사동)
- [ ] `python -m pipeline.resolve_addresses` → `seed/demo_addresses.csv`, `bjd_codes.csv` 코드 확인 (실패 시 §19-3)
- [ ] `python -m pipeline.geocode` → 좌표, A4·A5 거리 확인 후 필요 시 주소 교체
- [ ] `evals/goldset/extraction.yaml`, `addresses.yaml` 초안 (`draft: true`)
- 완료 확인: `python -m pipeline.check P1` — manifest 4행 / 선택 쪽 텍스트 확보율 ≥ 95% / D2 선택 쪽 10~15 + 29~31 전사 완료 / demo_addresses 10행, in_scope 주소는 PNU 있음 / 압구정동 코드 `code_verified=1`(API 실패 시 0 허용 + HUMAN_TODO) / 정답셋 초안 2개 존재

### P2 추출
- [ ] `pipeline/init_db.py`, `load_seed.py` → `python -m pipeline.init_db && python -m pipeline.load_seed`
- [ ] D1 추출 → `extractions/D1.json` → `python -m pipeline.load_extractions --check` (근거 불일치 0이 될 때까지 원문에서 다시 복사)
- [ ] D2 → D3 → D4 같은 방법
- [ ] `evals/goldset/scope_labels.yaml` 초안 (모든 item_key)
- 완료 확인: `python -m pipeline.check P2` — 4개 JSON 스키마 통과 / 근거 일치율 100% (불일치가 남으면 전부 검수 큐에 있음) / 항목 수 D1 ≥ 2, D2 ≥ 8, D3 ≥ 5, D4 ≥ 5 / D1 필드 19개 / D2 항목 전부 needs_review

### P3 판정·DB 완성
- [ ] `seed/stage_templates.yaml`(§9-5 그대로), `seed/stage_rules.yaml`(§10-5)
- [ ] `build_projects.py`, `events.py`, `review_queue.py`, `run_all.py`
- [ ] `python -m pipeline.run_all`
- 완료 확인: `python -m pipeline.check P3` — 아래 SQL 결과가 기대와 같음
  ```sql
  SELECT project_key, sub_stage_code, stage_as_of FROM projects;          -- apgujeong-6-1-hanyang7 | RB02 | 2026-10-06
  SELECT due_on FROM deadlines;                                           -- 2026-11-06
  SELECT step, event_type FROM change_events ORDER BY step;               -- 4|new_project, 4|deadline_added
  SELECT item_type, ref_key FROM review_queue WHERE item_type='parcel_inclusion'; -- 1:1168011000105270000
  SELECT pnu, basis, verified FROM project_parcels;                       -- …105270000 | representative_only | 0
  ```

### P4 조회 로직·API
- [ ] `core/db.py`, `timeutil.py`, `address.py`, `lookup.py`, `progress.py`, `review.py`
- [ ] `api/index.py` (§11)
- [ ] `tests/` (§14, 화면 관련 test_wording은 P5에서 마무리)
- 완료 확인: `pytest -q` 통과 / `python -m uvicorn api.index:app --port 8000` 실행 후 `curl -s "http://127.0.0.1:8000/api/v1/lookup?address=%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%95%95%EA%B5%AC%EC%A0%95%EB%8F%99%20527" | python -m json.tool | head -60`

### P5 화면
- [ ] `public/` 5개 화면 + assets (§12)
- [ ] 로컬 서버에서 수동 점검: ① 시작 화면 링크 5개 ② A1 조회 4개 층·사업 카드·D-day·원문 보기 모달·API 응답 보기 ③ A8·A10 안내 ④ 문서 DB D1 1쪽 근거 하이라이트, 투입 순서 1~4 ⑤ 검수 승인 → A1 "포함" → 초기화 → "포함될 수 있음" ⑥ 평가 화면(아직 리포트 없으면 "평가 전" 안내)
- [ ] 가능하면 Playwright(Python)로 화면 5개 스크린샷을 `docs/screens/`에 저장 (설치 실패 시 건너뛰고 HUMAN_TODO에 "화면 캡처 수동"으로 기록)
- 완료 확인: `pytest -q` (test_wording 포함) 통과 + 위 수동 점검 결과를 PROGRESS.md에 항목별로 기록

### P6 평가
- [ ] `evals/run_eval.py` (§13)
- [ ] `python -m evals.run_eval` → 미달 지표 원인 분석·수정(§13-5) → 다시 실행
- 완료 확인: `python -m evals.run_eval` 종료 코드 0, `evals/report.md` 생성, 평가 화면에 지표 12개 표시

### P7 시연 패키지
- [ ] `README.md`, `DEMO.md`(§16), `run_demo.bat`(§15-4), `.vercelignore`(§15-2)
- [ ] 처음부터 다시 빌드해 같은 결과인지 확인: `python -m pipeline.run_all && python -m evals.run_eval && pytest -q`
- [ ] `db/propedia.db` 크기 확인(10MB 이하 권장), `public/pages` 크기 확인(40MB 이하)
- [ ] commit
- 완료 확인: §2-2 성공 기준 2~7을 하나씩 확인해 PROGRESS.md에 기록 (1번의 Vercel 부분은 P8)

### P8 배포 (사람과 함께)
- [ ] §15-5 순서대로. GitHub·Vercel 계정이 필요한 부분에서 멈추고 요청(§19-1).
- [ ] 배포 주소로 화면 5개·API 확인 → README·DEMO.md에 주소 기록
- 완료 확인: `curl -s https://<주소>/api/v1/health` 정상, 다른 브라우저(시크릿 창)에서 A1 조회 성공

---

## 19. 멈춤 조건 · 사람 확인 · 문제 해결

### 19-1. 멈추고 사람에게 물어야 하는 경우 (이것만)
1. Python 3.11 이상이 없고 설치할 수 없을 때.
2. 원본 PDF가 없거나 열리지 않을 때.
3. GitHub 저장소 생성·push, Vercel 가입·Import처럼 **사람 계정**이 필요할 때 (P8).
4. 이 파일의 원칙(§1-3, §17)과 충돌하는 결정을 해야 할 때.
5. 같은 오류를 서로 다른 방법으로 3번 고쳐도 해결되지 않을 때.

### 19-2. 멈추지 않고 HUMAN_TODO에 적고 계속하는 경우
- 정답셋 확정(초안 검토), 재건축 단계 템플릿 문구 작성·법령 대조, D1 게시물 URL, 좌표를 못 얻은 주소, 도로명주소 API 키 만료, 법정동·생활권 매핑 중 애매한 것, 쪽 범위가 이 파일과 다른 것, 화면 캡처 수동, 시연 리허설.

### 19-3. 도로명주소 API가 안 될 때
1. `errorCode` 확인: `E0001` 승인키 오류 → ALT 키로 재시도. `E0006` 주소 모호 → 검색어를 더 구체적으로. 기타 → 메시지 기록.
2. 두 키 모두 승인키 오류 → 개발용 키 만료 가능성. HUMAN_TODO: "business.juso.go.kr에서 검색 API 승인키 재발급 후 `.env`의 `JUSO_CONFM_KEY` 교체".
3. 그동안은 **지번 입력만** 지원한다: `demo_addresses.csv`를 지번 주소로 채우고(도로명 칸 비움), PNU는 `bjd_codes.csv`로 만든다. A2는 "도로명주소 (키 재발급 후 추가)"로 표시하고 정답셋에서 제외한다.

### 19-4. 자주 생길 문제
| 증상 | 해결 |
|---|---|
| `UnicodeEncodeError`/한글 깨짐 | `export PYTHONUTF8=1`, `sys.stdout.reconfigure(encoding="utf-8")`, 파일 `encoding="utf-8"` |
| D1 파일을 못 찾음 | 파일명에 `⑥`과 잘린 이름이 있다. `glob("강남구 제2026-2347호*.pdf")` 사용 |
| pdfplumber가 표를 섞어 출력 | 근거는 숫자가 있는 줄을 그대로 사용(§9-4). 필요하면 `page.extract_text(layout=True)`로 한 번 더 저장해 비교 |
| 쪽 이미지가 흐림 | 그 쪽만 가로 2000px로 다시 렌더링(`build/hires/`)해 읽기 |
| Nominatim 403/429 | User-Agent 확인, 1.1초 간격, 2번 실패하면 그 주소는 좌표 없음 처리 |
| SQLite가 한글 경로를 못 엶 | `Path.as_uri()`로 만든 URI 사용(§10-1) |
| `StaticFiles` 때문에 API 404 | API 라우트를 먼저 등록하고 `mount("/")`는 맨 마지막 |
| Vercel 배포 후 `/api` 404 | §15-3 |
| Vercel 주소 첫 화면(`/`)이 404 | §11-1의 `/` → `/index.html` 리다이렉트 라우트 확인 |
| Vercel 빌드 용량 오류 | `.vercelignore` 확인, `public/pages` JPEG 품질 낮추기 |
| `run_demo.bat` 한글 깨짐 | 파일을 UTF-8 + CRLF로 저장, 첫 줄 뒤 `chcp 65001` |

---

## 20. PROGRESS.md · HUMAN_TODO.md 형식

### 20-1. `PROGRESS.md`
```markdown
# 진행 기록
현재 단계: P2 (D3 추출 중)

## P0 환경·뼈대 — 완료 (2026-10-25)
- 한 일: …
- 완료 확인: (명령과 결과 요약)
- 남은 문제: 없음

## P1 … — 진행 중
- [x] collect
- [ ] …
```

### 20-2. `HUMAN_TODO.md`
```markdown
# 사람 확인 목록
| # | 할 일 | 왜 | 언제까지 | 상태 |
|---|---|---|---|---|
| 1 | 정답셋 3개 확인 후 draft:false, confirmed_by 기입 | 평가 수치를 믿을 수 있게 | 시연 전 | 열림 |
| 2 | 재건축 단계 템플릿 what_happens·법령 근거 작성 | 원칙 3 | 정식 MVP | 열림 |
| 3 | D1 게시물 URL 확인 | 출처 링크 | 시연 전 | 열림 |
| 4 | GitHub 저장소·Vercel 배포 | 계정 필요 | P8 | 열림 |
| 5 | 시연 리허설 (DEMO.md대로 5분) | | 시연 전 | 열림 |
```
P0에서 위 5줄로 만들고, 작업 중 생기는 일을 추가한다.

---

## 21. 변경 이력
| 날짜 | 작성자 | 내용 |
|---|---|---|
| 2026-10-26 | Claude Code (P8) | 새 도로명주소 키로 시연 주소 재확정: 압구정동 527은 도로명주소 없음 → A2를 인접 528 도로명 입력으로, A4를 갤러리아백화점(494)으로(§4) / 사업 중심 좌표를 인접 필지 526 근사로 허용, Nominatim 결과에 법정동 이름 확인 조건 추가(§8-8) / Vercel 배포 https://propedia-pretotype.vercel.app |
| 2026-10-25 | Claude Code (P2) | D1 관련 고시 이력은 원문대로 5건(1977 건설부 승인 포함)(§8-11, §9-3) / 동남권 구성 근거를 D2 p12로 확인(§9-3) |
| 2026-10-25 | Claude Code (P1) | 실제에 맞게 고침: D2 인쇄 쪽 환산 `−4` → `−6`(§3-2) / D2 p29 표지·p30 빈 쪽은 선택 제외, p31만 전사(§3-2, §8-3) / 텍스트 추출에 `dedupe_chars` 사용(§8-3) / 전사 원본을 커밋 대상인 `seed/transcripts/`에 두고 textify가 합침(§6, §8-3) / 도로명주소 API `E0014`도 예비 키 재시도 대상, 두 키 만료로 대체 모드(지번만) 작성(§8-7) / Nominatim 지번 질의 오매칭으로 제외, 경계·동네·정류장 결과 거부(§8-8) / D1 `title`은 공고 1쪽 제목 그대로 |
| 2026-10-24 | Claude (동혁 요청) | 폴더 이름 `pretype` → `pretotype`. Claude Code가 이 파일만 보고 끝까지 작업하도록 전면 재작성: 배경 요약, 문서별 쪽 범위 확인(D1 1~21, D2 12~14·29~31·113~151, D3 243~248·262~268·275~277, D4 73·75~80·175~179), D1 확인 사실, DDL, 스크립트 명세, 추출 JSON 스키마, 단계 템플릿, API·화면·평가·테스트·배포 명세, P0~P8 |
| 2026-10-24 | Claude (동혁 요청) | 결정 반영: 추출은 Claude Code 직접 추출(외부 LLM API 없음), 도로명주소 키 2개를 `.env`로 복사, 배포는 Vercel(정적 화면 + FastAPI), 시연은 2026-11-06 공람 마감 전 |
| 2026-10-24 | Claude (동혁 요청) | 최초 작성 (`pretype/agents.md`) |
