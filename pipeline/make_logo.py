"""로고 원본(logo/, 수정 금지)에서 지도 화면용 브랜드 이미지를 만든다 (docs/map/PLAN.md P11).

- 원본 배경의 반투명 잡점(알파 48 미만)을 지운다.
- web/public/brand/
    logo-wordmark.png        ← propedia_logo_transparent.png (그라디언트 글자, 흰 바탕용), 가로 480px
    logo-wordmark-white.png  ← propedia_logo_white.png (흰 글자, 어두운 바탕용), 가로 480px
    logo-mark.png            ← 첫 글자 'p'를 잘라 512×512 투명 정사각 가운데에
    favicon.png              ← logo-mark 64×64
- 같은 입력이면 같은 결과 (멱등). 실행: python -m pipeline.make_logo
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "logo"
OUT = ROOT / "web" / "public" / "brand"
ALPHA_MIN = 48
WORDMARK_W = 480
MARK = 512
MARK_PAD = 0.12  # 정사각 안 여백 비율
FAVICON = 64


def clean(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    r, g, b, a = im.split()
    a = a.point(lambda v: 0 if v < ALPHA_MIN else v)
    im = Image.merge("RGBA", (r, g, b, a))
    return im.crop(a.getbbox())


def wordmark(im: Image.Image) -> Image.Image:
    h = round(im.height * WORDMARK_W / im.width)
    return im.resize((WORDMARK_W, h), Image.LANCZOS)


def first_glyph(im: Image.Image) -> Image.Image:
    """왼쪽부터 첫 번째 빈 열(알파 0만 있는 열)까지 = 첫 글자 'p'."""
    a = im.getchannel("A")
    w, h = a.size
    px = a.load()
    x = 0
    while x < w and any(px[x, y] for y in range(h)):
        x += 1
    if x >= w:
        raise SystemExit("첫 글자 뒤 빈 열을 찾지 못했습니다")
    glyph = im.crop((0, 0, x, h))
    return glyph.crop(glyph.getchannel("A").getbbox())


def square(glyph: Image.Image, size: int) -> Image.Image:
    inner = round(size * (1 - 2 * MARK_PAD))
    scale = inner / max(glyph.size)
    g = glyph.resize((max(1, round(glyph.width * scale)), max(1, round(glyph.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2))
    return canvas


def save(im: Image.Image, name: str) -> None:
    path = OUT / name
    im.save(path, optimize=True)
    a = im.getchannel("A").getextrema()
    print(f"{name:26s} {im.width}x{im.height}  {path.stat().st_size:>7,} B  투명={'예' if a[0] == 0 else '아니오'}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    color = clean(SRC / "propedia_logo_transparent.png")
    white = clean(SRC / "propedia_logo_white.png")
    save(wordmark(color), "logo-wordmark.png")
    save(wordmark(white), "logo-wordmark-white.png")
    mark = square(first_glyph(color), MARK)
    save(mark, "logo-mark.png")
    save(mark.resize((FAVICON, FAVICON), Image.LANCZOS), "favicon.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
