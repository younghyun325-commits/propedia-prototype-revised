# CLAUDE.md

이 폴더(`pretotype`)의 작업 지시서는 `agents.md`다. 작업을 시작하기 전에 끝까지 읽고 그대로 따른다.
진행 상황은 `PROGRESS.md`, 사람이 확인할 일은 `HUMAN_TODO.md`에 기록한다.

## 절대 규칙 (키 출력, 2026-11-11 추가)
- 개발 서버 응답, 빌드 산출물, 네트워크 응답, 로그를 화면에 출력할 때는 반드시 `python -m pipeline.peek`을 거친다 (직접 `cat`·`curl`·`head` 출력 금지). Vite 개발 서버(3000) 모듈 응답에는 `.env`의 `VITE_*` 값이 그대로 들어 있다.
- 키가 있는지 확인할 때는 값을 보지 말고 `python -m pipeline.check_secrets`처럼 '변수 이름별 건수'만 본다.

@agents.md
