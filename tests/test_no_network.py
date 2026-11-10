"""시연 경로의 네트워크 호출은 core/live/ 안에서만 한다 (feedback2.md §2-1·§2-2, agents.md §2-2-7 수정).

- core/ 나머지와 api/: 네트워크 라이브러리 import 금지
- core/live/: 표준 라이브러리 urllib만 쓴다 (httpx·requests 등 외부 패키지 금지, LLM 호출 없음)
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = re.compile(r"^\s*(?:import|from)\s+(httpx|requests|urllib\.request|urllib3|socket|http\.client|aiohttp)\b",
                    re.M)
BANNED_ATTR = re.compile(r"\burllib\.request\b|\bsocket\.")
ALLOWED_TOP = {"__future__", "json", "math", "re", "sqlite3", "sys", "os", "pathlib", "dataclasses", "datetime",
               "unicodedata", "statistics", "fastapi", "core"}
LIVE_ALLOWED_TOP = ALLOWED_TOP | {"urllib", "time"}
LLM = re.compile(r"anthropic|openai|generativelanguage|api\.claude", re.I)


def offline_sources():
    yield from (ROOT / "core").glob("*.py")
    yield from (ROOT / "api").glob("*.py")


def live_sources():
    yield from (ROOT / "core" / "live").glob("*.py")


def test_no_network_outside_live():
    bad = []
    for f in offline_sources():
        text = f.read_text(encoding="utf-8")
        for m in BANNED.finditer(text):
            bad.append(f"{f.name}: {m.group(0).strip()}")
        if BANNED_ATTR.search(text):
            bad.append(f"{f.name}: urllib.request/socket 사용")
    assert not bad, bad


def test_only_stdlib_and_fastapi_imports():
    imp = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M)
    bad = []
    for files, allowed in ((offline_sources(), ALLOWED_TOP), (live_sources(), LIVE_ALLOWED_TOP)):
        for f in files:
            for m in imp.finditer(f.read_text(encoding="utf-8")):
                top = (m.group(1) or m.group(2)).split(".")[0]
                if top not in allowed:
                    bad.append(f"{f.relative_to(ROOT)}: {top}")
    assert not bad, bad


def test_live_has_no_llm_calls():
    for f in live_sources():
        assert not LLM.search(f.read_text(encoding="utf-8")), f.name


def test_live_modules_exist():
    names = {f.name for f in live_sources()}
    assert {"juso.py", "vworld.py", "http.py"} <= names
