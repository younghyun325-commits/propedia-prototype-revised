"""키를 가린 채로 파일·로컬 서버 응답·표준입력을 보여 준다 (P20, 표준 라이브러리만).

개발 서버(Vite 3000) 모듈 응답에는 .env의 VITE_* 값이 그대로 들어 있고, 빌드 산출물·네트워크 응답·로그에도 키가 섞일 수 있다.
그런 내용을 화면에 낼 때는 직접 cat·curl·head 하지 말고 이 도구를 거친다 (CLAUDE.md 절대 규칙).

- .env에서 값이 8자 이상인 변수를 모두 읽어(값은 메모리에서만), 출력 전에 '[변수 이름 가림]'으로 바꾼다.
  URL 인코딩 형태(quote·quote_plus)도 가린다. 같은 값을 가진 변수는 이름을 '='로 이어 붙인다.
- 가리기는 전체 내용에 먼저 하고, 그 뒤에 --grep·--head를 적용한다 (잘라서 키 앞부분이 남지 않게).
- 마지막 줄에 변수 이름별 가린 개수를 보여 준다 (값은 출력하지 않음).
- URL은 로컬 3000·8000번만 허용한다 (localhost·127.0.0.1).

사용:
  python -m pipeline.peek public/map/index.html --head 20
  python -m pipeline.peek http://localhost:3000/map/src/api/map.ts --grep useMapConfig
  some_command | python -m pipeline.peek - --head 50
"""
import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_LEN = 8
ALLOWED_HOSTS = {"localhost", "127.0.0.1"}
ALLOWED_PORTS = {3000, 8000}


def read_env(path: Path) -> dict[str, str]:
    """KEY=VALUE 줄만 읽는다 (따옴표·앞뒤 공백 제거, 주석 무시). 값이 MIN_LEN자 미만이면 뺀다."""
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        if s.startswith("export "):
            s = s[7:]
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'").strip()
        if k and len(v) >= MIN_LEN:
            out[k] = v
    return out


def secret_forms(env: dict[str, str]) -> list[tuple[str, str]]:
    """(가릴 문자열, 표시 이름) 목록. 긴 것부터 바꿔야 짧은 형태가 긴 형태 일부를 먼저 먹지 않는다."""
    names_by_value: dict[str, list[str]] = {}
    for k, v in env.items():
        names_by_value.setdefault(v, []).append(k)
    forms: dict[str, str] = {}
    for v, names in names_by_value.items():
        label = "=".join(sorted(names))
        for f in {v, urllib.parse.quote(v, safe=""), urllib.parse.quote_plus(v), urllib.parse.quote(v)}:
            forms.setdefault(f, label)
    return sorted(forms.items(), key=lambda kv: -len(kv[0]))


def mask(text: str, env: dict[str, str]) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for form, label in secret_forms(env):
        n = text.count(form)
        if n:
            text = text.replace(form, f"[{label} 가림]")
            counts[label] = counts.get(label, 0) + n
    return text, counts


def fetch_local(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    if u.scheme != "http" or u.hostname not in ALLOWED_HOSTS or u.port not in ALLOWED_PORTS:
        raise SystemExit("허용하지 않는 주소입니다: 로컬 http://localhost:3000·8000 (127.0.0.1)만 됩니다")
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def read_input(src: str) -> str:
    if src == "-":
        return sys.stdin.buffer.read().decode("utf-8", "replace")
    if src.startswith(("http://", "https://")):
        return fetch_local(src)
    return Path(src).read_bytes().decode("utf-8", "replace")


def render(text: str, env: dict[str, str], head: int | None = None, grep: str | None = None) -> str:
    masked, counts = mask(text, env)
    lines = masked.splitlines()
    if grep:
        rx = re.compile(grep)
        lines = [ln for ln in lines if rx.search(ln)]
    if head is not None:
        lines = lines[:head]
    summary = ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "없음"
    return "\n".join(lines + [f"[peek] 가림: {summary}"])


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="키를 가리고 보여 준다")
    ap.add_argument("src", help="파일 경로, 로컬 URL(3000·8000), 또는 - (표준입력)")
    ap.add_argument("--head", type=int, help="앞 N줄만 (가린 뒤)")
    ap.add_argument("--grep", help="정규식에 맞는 줄만 (가린 뒤)")
    ap.add_argument("--env", default=str(ROOT / ".env"), help=argparse.SUPPRESS)  # 테스트용
    a = ap.parse_args(argv)
    print(render(read_input(a.src), read_env(Path(a.env)), a.head, a.grep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
