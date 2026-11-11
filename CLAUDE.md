# CLAUDE.md

## 이 저장소는 propedia-prototype-revised (복제본) — 2026-11-12 추가
원본(`propedia-prototype`, 운영 https://propedia-prototype.vercel.app)을 복제해 P22 '쉬운 지도'를 만드는 저장소다.

| 구분 | 경로 | 다루는 방법 |
|---|---|---|
| 작업 폴더(복제본) | Windows `C:\dev\propedia-prototype-revised` (Git Bash `/c/dev/propedia-prototype-revised`) · macOS `~/dev/propedia-prototype-revised` (아직 만들지 않음) | 여기서만 작업한다 |
| 복제본 GitHub | `younghyun325-commits/propedia-prototype-revised` (비공개) | 원격 `origin`, push 대상 |
| 원본 GitHub | `younghyun325-commits/propedia-prototype` | 원격 `upstream`, **fetch 전용** (push URL `PUSH_DISABLED_original_repo`) |
| 원본 Vercel 프로젝트 | klowyh/`propedia-prototype` | 건드리지 않는다. 이 저장소는 어느 Vercel 프로젝트에도 연결돼 있지 않다 |
| 데스크톱 옛 원본 폴더 | `C:\dev\propedia-pretotype` | 읽기 전용. git에 없는 파일(원본 데이터 등)의 출처로만. 코드 기준으로 쓰지 않는다. git도 status·log·ls-files 같은 읽기 명령만 |
| OneDrive 옛 복사본 | `C:\Users\young\OneDrive\Desktop\Anti Gravity\propedia-prototype-main(revised)` | 손대지 않는다 (사람이 삭제 예정) |

- 원본 폴더·원본 저장소·원본 Vercel 프로젝트를 건드리지 않는다. upstream으로 push하는 명령은 쓰지도 출력하지도 않는다.
- 원본 판별은 저장소 이름 **전체 일치**로 한다 (`propedia-prototype-revised` 안에 `propedia-prototype`이 들어 있으므로 부분 문자열 검사 금지).
- clone 직후 `sh scripts/install_hooks.sh`로 pre-push 훅을 설치한다 (원본·upstream·이름 불일치 push 거부, noreply가 아닌 작성자 거부, main 직접 push 거부).
- 커밋 작성자는 `git config --local user.email`(저장소 주인 noreply). 전역 설정은 학교 주소이므로 커밋 전 local 값을 확인한다.
- push는 사람이 한다 (Claude Code는 명령만 출력). 원본에 반영할지는 P22-8 뒤 영현이 결정한다.
- 아래 agents.md의 폴더 경로·원격·배포 설명은 원본 기준이다. 이 저장소에서는 위 표가 우선한다.

이 폴더(`pretotype`)의 작업 지시서는 `agents.md`다. 작업을 시작하기 전에 끝까지 읽고 그대로 따른다.
진행 상황은 `PROGRESS.md`, 사람이 확인할 일은 `HUMAN_TODO.md`에 기록한다.

## 절대 규칙 (키 출력, 2026-11-11 추가)
- 개발 서버 응답, 빌드 산출물, 네트워크 응답, 로그를 화면에 출력할 때는 반드시 `python -m pipeline.peek`을 거친다 (직접 `cat`·`curl`·`head` 출력 금지). Vite 개발 서버(3000) 모듈 응답에는 `.env`의 `VITE_*` 값이 그대로 들어 있다.
- 키가 있는지 확인할 때는 값을 보지 말고 `python -m pipeline.check_secrets`처럼 '변수 이름별 건수'만 본다.

@agents.md
