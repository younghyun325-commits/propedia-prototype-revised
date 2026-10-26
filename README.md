# Propedia 프리토타입 — 강남구 · 압구정 한양7차 재건축

서울 주소 하나를 넣으면 그 주소에 해당하는 공공 문서(고시·공고·계획) 정보를 **4개 층**(서울 전역·자치구·법정동·필지)으로 모아 한 응답으로 돌려주고, 필지가 정비사업 구역에 걸리면 **현재 단계·다음 단계·기한·남은 기간**을 기준일·원문 쪽과 함께 보여주는 원리를 작게 보여주는 시연판입니다.

- 작업 지시서: [agents.md](agents.md) · 진행 기록: [PROGRESS.md](PROGRESS.md) · 사람 확인 목록: [HUMAN_TODO.md](HUMAN_TODO.md) · 시연 대본: [DEMO.md](DEMO.md)
- GitHub(비공개): https://github.com/greekyogurt02/propedia-pretotype
- 배포 주소: https://propedia-pretotype.vercel.app (Vercel Hobby, GitHub `main` push 시 자동 배포)

## 반영 범위

| ID | 문서 | 층 | 쓴 쪽(PDF) |
|---|---|---|---|
| D1 | 강남구 공고 제2026-2347호 (구보 제1871호) 한양7차 재건축 정비계획(안) 공람·공고 | 법정동·필지·사업 카드 | 1~21 (18~21 도면은 원문 보기용) |
| D2 | 2030 서울생활권계획 강남구 (2018) | 자치구·지역생활권(압구정·청담) | 12~14, 31, 압구정·청담 장 12쪽 전사 |
| D3 | 2030 도시·주거환경정비기본계획 (2025.6.26 변경) | 서울 전역(+자치구 통계) | 243~248, 262~268, 275~277 |
| D4 | 2040 서울도시기본계획 (2023) | 서울 전역·동남권 | 73, 75~80, 175~179 |

원칙: 사실만 보여준다 / 모든 항목에 근거 문장·원문 쪽·기준일 / 사업 단계는 고시 문서 제목 + 규칙으로만 / 단계 설명·안내 문구는 사람이 쓴 템플릿에서만 / 남은 기간은 비교 사례가 부족하면 비워 둔다.

## 폴더

```
api/index.py        FastAPI 앱 (Vercel 진입점, 로컬은 public/도 서빙)
core/               조회·판정 로직 (표준 라이브러리만, 네트워크 없음, DB 읽기 전용)
public/             화면 5개 + assets + 원문 쪽 이미지(pages/)
db/                 schema.sql, propedia.db (빌드 산출물, 커밋함)
pipeline/           빌드 스크립트 (시연 코드에서 import 금지)
seed/               법정동 코드·시연 주소·단계 템플릿/규칙·D2 쪽 선택·전사 원본(transcripts/)
extractions/        Claude Code가 직접 추출한 D1~D4.json
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
| 7 | `python -m pipeline.run_all` | – | DB 전체 재빌드 + P3 확인 SQL 출력 |
| 8 | `python -m evals.run_eval` | – | 지표 12개 → `evals/report.md`, `meta.eval_report` |

단계별 점검: `python -m pipeline.check P1|P2|P3`

## 실행·테스트

- 로컬 실행: `run_demo.bat` 더블클릭 (가상환경이 없으면 만들고 `http://127.0.0.1:8000/`을 엽니다)
- 개발 중: `python -m uvicorn api.index:app --port 8000 --reload`
- 테스트: `pytest -q`
- 화면 점검 + 캡처: `python tests/ui_check.py` (배포본은 `--base https://….vercel.app`)

## 배포 (Vercel)

1. GitHub 비공개 저장소에 push (`gh repo create propedia-pretotype --private --source . --push`, 완료).
   - 이후 `git push`가 "Repository not found"로 실패하면 Windows 자격 증명 관리자에 다른 GitHub 계정이 저장된 것입니다. 전역 설정을 바꾸지 않고 `git -c credential.helper= -c "credential.helper=!gh auth git-credential" push`로 올립니다.
2. vercel.com → New Project → 저장소 Import → Framework 자동(FastAPI) → Deploy.
3. 확인: `curl -s https://<주소>/api/v1/health`, 화면 5개.
4. `/api/*`가 404면 루트에 `vercel.json` `{ "rewrites": [ { "source": "/api/(.*)", "destination": "/api/index" } ] }` 추가 후 재배포 (agents.md §15-3).

`.vercelignore`가 빌드 전용 파일(pipeline, seed, extractions, data_raw, tests, docs 등)을 뺍니다. `db/propedia.db`, `core/`, `api/`, `public/`, `requirements.txt`는 올라갑니다. Hobby 플랜은 운영 주소가 기본 공개이며 비상업·개인 용도 조건입니다.

화면 캡처: [docs/screens/](docs/screens/) (`python tests/ui_check.py`가 다시 만듭니다)

## 알려진 한계

- **압구정동 527은 도로명주소가 없는 필지**입니다(도로명주소 API 검색 결과 없음, 2026-10-26). 그래서 A2는 인접 528(한양아파트, 압구정로61길 37)의 도로명 입력으로 바꿨습니다.
- **사업 중심 좌표는 근사값**입니다: 527·528 모두 OSM에 위치가 없어, 인접 필지 526(청담고등학교, 도로명주소 API로 확인)의 OSM 좌표를 씁니다. 주변 500m 판정(A4 갤러리아 260m)은 이 근사 중심 기준이며 화면에 거리 기준을 함께 표시합니다(HUMAN_TODO 7).
- 좌표는 OSM Nominatim에서 도로명·건물명으로만 찾습니다(한국 OSM 번지는 도로명 번호라 지번 질의는 오매칭). 결과 주소에 해당 법정동 이름이 있을 때만 받습니다.
- 경계 데이터가 없어 포함 판정은 대표 지번(`possible`)과 사람 검수(`included`)만 씁니다.
- 지역생활권 계획은 2018년판이며 압구정·청담 장만 반영했습니다. 이미지 쪽은 Claude Code가 전사했고 모두 검수 대상입니다.
- 재건축 단계 템플릿 문구(설명·법령 근거)는 법령 대조 전 초안이라 비어 있습니다(HUMAN_TODO 2).
- 정답셋 3개는 추출자와 같은 작성자의 초안이라 평가 수치가 낙관적입니다(HUMAN_TODO 1).
