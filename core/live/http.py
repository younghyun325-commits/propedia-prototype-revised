"""실시간 조회 공통: 환경변수 키, JSON GET(타임아웃 4초·재시도 1회), 메모리 캐시. 표준 라이브러리만 쓴다."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TIMEOUT = 4
RETRIES = 1
CACHE_TTL = 3600          # 1시간 (feedback2.md §3-3)
KST = timezone(timedelta(hours=9))
_ENV_LOADED = False


class LiveError(Exception):
    """외부 호출 실패. 메시지에 URL·키를 넣지 않는다."""


def _load_dotenv() -> None:
    """로컬 실행용: 프로젝트 루트 .env에서 비어 있는 환경변수만 채운다 (Vercel에는 .env가 올라가지 않는다)."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    p = Path(__file__).resolve().parents[2] / ".env"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for ln in lines:
        if "=" not in ln or ln.lstrip().startswith("#"):
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v


def env_key(name: str) -> str:
    _load_dotenv()
    return (os.environ.get(name) or "").strip()


def get_json(url: str, params: dict, timeout: float = TIMEOUT, retries: int = RETRIES) -> dict:
    """GET → JSON. 실패하면 LiveError(오류 종류만)."""
    full = f"{url}?{urllib.parse.urlencode(params)}"
    last = "unknown"
    for _ in range(retries + 1):
        try:
            with urllib.request.urlopen(full, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = type(e).__name__
        except ValueError:
            last = "JSON 아님"
    raise LiveError(last)


def now_kst() -> datetime:
    return datetime.now(KST)


class TTLCache:
    """함수 인스턴스 메모리 캐시 {키: (값, 저장 시각)}."""

    def __init__(self, ttl: float = CACHE_TTL):
        self.ttl = ttl
        self._d: dict = {}

    def get(self, key):
        hit = self._d.get(key)
        if hit and time.monotonic() - hit[1] < self.ttl:
            return hit[0]
        return None

    def put(self, key, value) -> None:
        self._d[key] = (value, time.monotonic())

    def clear(self) -> None:
        self._d.clear()
