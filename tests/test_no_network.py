"""시연 경로(core/, api/)에 네트워크 호출 코드가 없음을 확인한다 (agents.md §2-2-7)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = re.compile(r"^\s*(?:import|from)\s+(httpx|requests|urllib\.request|urllib3|socket|http\.client|aiohttp)\b",
                    re.M)
BANNED_ATTR = re.compile(r"\burllib\.request\b|\bsocket\.")
ALLOWED_TOP = {"__future__", "json", "math", "re", "sqlite3", "sys", "os", "pathlib", "dataclasses", "datetime",
               "unicodedata", "fastapi", "core"}


def sources():
    for d in ("core", "api"):
        yield from (ROOT / d).glob("*.py")


def test_no_network_imports():
    bad = []
    for f in sources():
        text = f.read_text(encoding="utf-8")
        for m in BANNED.finditer(text):
            bad.append(f"{f.name}: {m.group(0).strip()}")
        if BANNED_ATTR.search(text):
            bad.append(f"{f.name}: urllib.request/socket 사용")
    assert not bad, bad


def test_only_stdlib_and_fastapi_imports():
    imp = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M)
    bad = []
    for f in sources():
        for m in imp.finditer(f.read_text(encoding="utf-8")):
            top = (m.group(1) or m.group(2)).split(".")[0]
            if top not in ALLOWED_TOP:
                bad.append(f"{f.name}: {top}")
    assert not bad, bad
