"""P22-2: 너비별 배치 구간이 CSS 토큰(web/src/styles/tokens.css)과 TS(web/src/ui/panelLayout.ts)에서 같은 값인지, 글씨 크기 토큰이 12px 이상인지."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web" / "src"


def _css() -> str:
    return (WEB / "styles" / "tokens.css").read_text(encoding="utf-8")


def _rem(name: str) -> float:
    m = re.search(rf"--{name}:\s*([\d.]+)rem", _css())
    assert m, name
    return float(m.group(1)) * 16


def test_panel_tiers_match():
    ts = (WEB / "ui" / "panelLayout.ts").read_text(encoding="utf-8")
    md = int(re.search(r"PANEL_MD = (\d+)", ts).group(1))
    lg = int(re.search(r"PANEL_LG = (\d+)", ts).group(1))
    assert (md, lg) == (380, 520)
    assert _rem("container-panel-md") == md
    assert _rem("container-panel-lg") == lg


def test_text_tokens():
    sizes = {n: _rem(f"text-{n}") for n in ("caption", "meta", "body", "title")}
    assert sizes == {"caption": 12, "meta": 14, "body": 16, "title": 18}


def test_no_fixed_font_sizes_in_components():
    bad = []
    for p in WEB.rglob("*"):
        if p.suffix not in {".ts", ".tsx", ".css"} or ".test." in p.name:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"text-\[\d+px\]|font-size:\s*\d+px|\btext-(xs|sm|base|lg)\b", line):
                bad.append(f"{p.relative_to(WEB)}:{i}")
    assert not bad, bad
