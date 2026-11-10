"""단지명 정규화 (seed/apt_name_rules.yaml). 순수 함수 — tests/test_market_build.py."""
import re
import unicodedata
from functools import lru_cache

import yaml

from pipeline.common import SEED

RULES = SEED / "apt_name_rules.yaml"


@lru_cache(maxsize=1)
def _steps() -> tuple:
    d = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    out = []
    for s in d["steps"]:
        if s["kind"] == "regex":
            out.append(("regex", re.compile(s["pattern"]), s.get("repl", "")))
        else:
            out.append((s["kind"], None, None))
    return tuple(out)


def norm_name(name: str | None) -> str:
    s = name or ""
    for kind, pat, repl in _steps():
        if kind == "unicode_nfkc":
            s = unicodedata.normalize("NFKC", s)
        elif kind == "lower":
            s = s.lower()
        else:
            s = pat.sub(repl, s)
    return s
