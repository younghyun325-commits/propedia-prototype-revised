# P22 복제본 Preview 배포 준비 (결정 7)

작성 2026-11-12 (Claude Code). 코드는 바꾸지 않았다. 아래 순서는 영현이 Vercel·브이월드 계정에서 직접 한다. 키 값은 이 문서와 채팅에 쓰지 않는다.

## 1. 원본과 섞이지 않게 먼저 확인할 것

| 확인 | 기대 | 왜 |
|---|---|---|
| Vercel 대시보드 오른쪽 위 계정 | klowyh (Hobby) | 원본 프로젝트 `propedia-prototype`와 같은 계정이다. 프로젝트 이름으로만 구분된다 |
| Import 화면의 저장소 이름 | `younghyun325-commits/propedia-prototype-revised` **전체 일치** | `propedia-prototype`(원본)이 목록 바로 옆에 있다. 이름 앞부분만 보고 고르지 않는다 |
| 새 프로젝트 이름 | 아래 2번 제안값, 원본 이름 `propedia-prototype`와 다름 | 운영 도메인 `propedia-prototype.vercel.app`은 원본 프로젝트에 붙어 있다 |
| 원본 프로젝트 Settings → Git | 연결 저장소가 여전히 `propedia-prototype` | 새 프로젝트를 만들면서 원본 연결을 바꾸지 않았는지 |
| 원본 프로젝트 Settings → Domains | `propedia-prototype.vercel.app` 그대로 | 새 프로젝트에 이 도메인을 옮기지 않는다 |
| 원본 프로젝트 환경변수 | 손대지 않음 | 새 프로젝트 환경변수는 새 프로젝트 화면에서만 넣는다 |

## 2. 새 Vercel 프로젝트 만들기

1. vercel.com → Add New… → Project.
2. Import할 저장소: `younghyun325-commits/propedia-prototype-revised` (비공개). 목록에 없으면 'Configure GitHub App'에서 이 저장소만 접근 허용에 추가한다.
3. 프로젝트 이름 제안: **`propedia-easy-map`**. 기본 주소가 `propedia-easy-map.vercel.app`이 되어 원본 주소와 헷갈리지 않는다. (다른 이름이면 아래 주소들을 그 이름으로 바꿔 읽는다)
4. Framework Preset: 자동(Other/FastAPI 인식). Root Directory `./`. Build Command·Output Directory는 비워 둔다 — `vercel.json`에 `buildCommand`가 없고 `public/map/`은 커밋된 빌드 결과다 (P20).
5. Production Branch: Settings → Git에서 **`feat/easy-map`**으로 둔다. 이 저장소의 `main`은 원본 복사본이고 pre-push 훅이 `main` push를 막으므로, `feat/easy-map`이 이 프로젝트의 기준 브랜치다. Production으로 두기 싫으면 `main` 그대로 두고 `feat/easy-map` Preview만 쓴다 (그때 주소는 4번 표의 브랜치 주소).
6. `vercel.json`은 그대로 쓴다: `regions: ["icn1"]`(서울, 미국 지역에서는 브이월드가 연결을 끊음), `excludeFiles`(web·public/pages·public/map·data_raw), `/` → `/map/` 이동, `X-Robots-Tag: noindex`.

## 3. 환경변수 (Settings → Environment Variables, 값은 영현만 다룬다)

| 이름 | 넣을 환경 | 무엇 | 없으면 |
|---|---|---|---|
| `VWORLD_API_KEY` | Production·Preview | 서버(토지 3종·필지 점 조회·참고 WMS 프록시)용 브이월드 키. 서비스 URL이 아래 `VWORLD_DOMAIN`과 같은 키 | 토지 정보·필지 클릭이 '키가 설정되지 않아' 안내로 바뀜 |
| `VWORLD_DOMAIN` | Production·Preview | 브이월드 요청의 `domain` = 키에 등록한 서비스 URL. 예 `https://propedia-easy-map.vercel.app` | **원본 운영 주소로 요청이 나감** (아래 5번) |
| `VITE_VWORLD_KEY` | Production·Preview | 브라우저 배경지도(WMTS)용 키. `/api/v1/map/config`로 실행 중에 내려감. 서비스 URL이 이 프로젝트 주소인 키 | 배경지도 없이 경계만 보임 |
| `JUSO_CONFM_KEY` | 선택 | 도로명주소 검색. 지금 로컬 `.env`도 비어 있음 | 브이월드 주소 검색으로 대신함 (HUMAN_TODO 39) |
| `JUSO_CONFM_KEY_ALT` | 선택 | 예비 도로명주소 키 | 위와 같음 |

넣지 않는 것: `VWORLD_API_KEY_DEV`·`VWORLD_DEV_DOMAIN`(로컬 개발용), `DATA_GO_KR_*`(빌드 스크립트만 씀, 런타임에서 읽지 않음), `PROPEDIA_LIVE`(테스트용).

## 4. 브이월드에 등록할 서비스 URL

브이월드 인증키는 키마다 서비스 URL 하나를 등록한다. 지금 운영 키의 서비스 URL은 원본 주소, 데스크톱 개발키는 `http://localhost:3000`이므로 둘 다 새 주소에서는 `INCORRECT_KEY`가 난다 (2026-11-12 `check_keys`로 확인한 동작과 같음).

| 쓸 주소 | 서비스 URL에 넣을 값 | 언제 |
|---|---|---|
| Production(브랜치 `feat/easy-map`) | `https://propedia-easy-map.vercel.app` | 2-5에서 Production Branch를 `feat/easy-map`으로 둔 경우 (권장) |
| 브랜치 Preview 고정 주소 | `https://propedia-easy-map-git-feat-easy-map-<팀 슬러그>.vercel.app` (Vercel이 Deployments 화면에 'Branch' 주소로 보여 줌) | Production을 `main`에 두고 Preview만 쓸 경우 |

- 배포마다 바뀌는 `…-<해시>-….vercel.app` 주소는 등록하지 않는다. 그 주소로 열면 키가 맞지 않는다.
- 새 키를 받을지, 기존 키의 서비스 URL을 바꿀지: 기존 운영 키의 URL을 바꾸면 **원본 운영 사이트의 토지 정보가 끊긴다**. 새 키를 받는다 (HUMAN_TODO 61 재발급과 함께 하면 한 번에 끝남).
- 받은 새 키 하나를 `VWORLD_API_KEY`·`VITE_VWORLD_KEY`에 같이 넣어도 동작한다. 브라우저용 키를 따로 받는 것이 더 안전하다 (HUMAN_TODO 51과 같은 권장).

## 5. 원본 운영 주소를 기본값으로 쓰는 곳 — Preview에서 문제가 되는가

| 파일:줄 | 내용 | 판단 |
|---|---|---|
| `core/live/vworld.py:35` `DEFAULT_DOMAIN` | `VWORLD_DOMAIN`이 비면 `https://propedia-prototype.vercel.app`을 `domain`으로 보냄 | **문제 됨(조건부)**. 새 프로젝트에 `VWORLD_DOMAIN`을 빠뜨리면 새 키(서비스 URL = 새 주소)와 맞지 않아 토지 정보가 모두 실패하고, 원본 주소 이름으로 요청이 나간다. 3번 표대로 `VWORLD_DOMAIN`을 넣으면 문제 없음 |
| `tests/test_live_vworld.py:107` | `DEFAULT_DOMAIN` 값을 고정 검사 | 런타임 영향 없음 |
| `tests/test_parcel_at.py:233`, `tests/test_target.py:8` | 문자열 예시 | 영향 없음 |
| `.env.example:9,14` | 설명 | 영향 없음 |
| `tests/_target.py` `is_remote()` | `vercel.app` 주소를 원격으로 판정 | 새 주소도 원격으로 판정되어 `ui_check_map --base https://propedia-easy-map.vercel.app`이 그대로 동작 |

바꾸는 방법 제안 (적용하지 않음, 영현 결정):
- (가) 그대로 두고 3번처럼 `VWORLD_DOMAIN`을 반드시 넣는다. 코드 변경 없음. 빠뜨렸을 때 조용히 실패하는 위험은 남는다.
- (나) Vercel에서는 `VWORLD_DOMAIN`이 없으면 Vercel이 넣어 주는 `VERCEL_PROJECT_PRODUCTION_URL`(또는 `VERCEL_BRANCH_URL`)로 `https://…`를 만들고, 그것도 없을 때만 `DEFAULT_DOMAIN`을 쓴다. 원본 운영에서는 Production URL이 원본 주소이므로 동작이 같다. `tests/test_live_vworld.py`에 경우별 시험을 더한다.
- (다) `/api/v1/health`의 `keys`에 '`VWORLD_DOMAIN` 없음 → 기본값 사용 중'을 함께 보여 주어 빠뜨린 것을 배포 직후 알 수 있게 한다. (가)나 (나)와 같이 쓸 수 있다.

## 6. 배포 뒤 확인 (Claude Code가 할 수 있는 것)

1. `curl -s https://propedia-easy-map.vercel.app/api/v1/health` — `status ok`, `keys.vworld` 있음.
2. `python tests/ui_check_map.py --base https://propedia-easy-map.vercel.app` — 원격 판정(배경 타일·WMS 200, 콘솔 오류 0).
3. 필지 클릭(역삼동 823) 카드 `data-status=ok`.
4. Vercel 'Deployment Protection'(Vercel Authentication)이 켜져 있으면 Preview 주소가 로그인을 요구해 2번이 401로 실패한다. Production 주소로 확인하거나, 확인하는 동안 보호를 끈다 (영현 결정).
