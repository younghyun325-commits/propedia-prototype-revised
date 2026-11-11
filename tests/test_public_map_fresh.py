"""P20: 커밋된 지도 빌드(public/map)가 지금 web/ 소스로 만든 것인지 확인한다 (빌드는 돌리지 않고 소스 해시만 비교).

Vercel은 빌드 중에 만든 public/ 파일을 서빙하지 않아(관찰: Preview ee79ea4) public/map을 커밋한다.
해시 규칙은 web/scripts/build-info.mjs와 같다 — 둘을 함께 고칠 것.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MAP = ROOT / "public" / "map"
DIRS = ["src", "public", "scripts"]
FILES = ["index.html", "package.json", "package-lock.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json",
         "tsconfig.node.json"]
HINT = "web/를 고쳤으면 `npm --prefix web run build` 후 public/map을 함께 커밋하세요"


def _normalized(b: bytes) -> bytes:
    return b if b"\0" in b else b.replace(b"\r\n", b"\n")


def source_sha256() -> tuple[str, int]:
    paths = [p for d in DIRS for p in (WEB / d).rglob("*") if p.is_file()] + [WEB / f for f in FILES]
    rels = sorted(r for r in (p.relative_to(WEB).as_posix() for p in paths) if not r.endswith(".test.ts"))
    h = hashlib.sha256()
    for r in rels:
        h.update(f"{r}\n{hashlib.sha256(_normalized((WEB / r).read_bytes())).hexdigest()}\n".encode("utf-8"))
    return h.hexdigest(), len(rels)


def test_build_info_matches_web_sources():
    info = json.loads((MAP / "build-info.json").read_text(encoding="utf-8"))
    sha, n = source_sha256()
    assert info["source_files"] == n, HINT
    assert info["source_sha256"] == sha, HINT


def test_index_assets_exist():
    html = (MAP / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="/map/([^"]+)"', html)
    assert any(r.startswith("assets/") and r.endswith(".js") for r in refs)
    missing = [r for r in refs if not (MAP / r).is_file()]
    assert not missing, f"public/map/index.html이 가리키는 파일이 없음: {missing} — {HINT}"
