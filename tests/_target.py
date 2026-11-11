"""화면 점검 도구(ui_check·ui_check_map·demo_map_run) 공통: 점검 대상 주소, 키 가림, 스크린샷 이름 (P20).

- 대상이 localhost·127.0.0.1이면 로컬, 아니면 원격(운영·Preview).
- 출력 가림: 로컬 .env 값(pipeline.peek 규칙) + 브이월드 타일 주소의 키 자리(WMTS 경로·KEY=).
  운영 키는 로컬 .env에 없으므로 주소 모양으로 가리는 정규식이 실제로 가린다.
- 원격 점검 스크린샷은 prod_ 접두를 붙여 로컬 스크린샷을 덮어쓰지 않는다.
"""
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import peek  # noqa: E402

LOCAL_HOSTS = {"localhost", "127.0.0.1"}
KEY_RE = re.compile(r"(/req/wmts/1\.0\.0/)[^/]+/")
WMS_KEY_RE = re.compile(r"((?:KEY|apikey|key)=)[^&\s\"']+", re.I)
_ENV = None


def is_remote(base: str) -> bool:
    return (urllib.parse.urlsplit(base).hostname or "") not in LOCAL_HOSTS


def mask_text(s: str) -> str:
    global _ENV
    if _ENV is None:
        _ENV = peek.read_env(ROOT / ".env")
    s = WMS_KEY_RE.sub(r"\1***", KEY_RE.sub(r"\1***/", s or ""))
    return peek.mask(s, _ENV)[0]


def shot_name(name: str, remote: bool) -> str:
    return f"prod_{name}" if remote else name
