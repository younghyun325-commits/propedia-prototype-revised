"""쪽 이미지 모아보기 (3×3 격자, 칸 가로 400px, 칸마다 p### 라벨) (agents.md §8-4).

사용: python -m pipeline.contact_sheet D2 113 151
출력: build/contact/D2_113-151_{n}.jpg
"""
import argparse

from PIL import Image, ImageDraw, ImageFont

from pipeline.common import BUILD, PAGES_DIR, fail, log, setup_stdout

CELL_W = 400
COLS = ROWS = 3


def load_font(size: int):
    for name in ("arialbd.ttf", "arial.ttf", "C:/Windows/Fonts/malgunbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    args = ap.parse_args()

    pages = []
    for p in range(args.start, args.end + 1):
        f = PAGES_DIR / args.doc / f"p{p:03d}.jpg"
        if not f.exists():
            fail(f"쪽 이미지가 없습니다: {f} (먼저 python -m pipeline.textify)")
        pages.append((p, f))

    out_dir = BUILD / "contact"
    out_dir.mkdir(parents=True, exist_ok=True)
    font = load_font(30)
    per = COLS * ROWS
    for n, i in enumerate(range(0, len(pages), per), start=1):
        chunk = pages[i:i + per]
        thumbs = []
        for p, f in chunk:
            im = Image.open(f).convert("RGB")
            im = im.resize((CELL_W, round(im.height * CELL_W / im.width)), Image.LANCZOS)
            thumbs.append((p, im))
        cell_h = max(im.height for _, im in thumbs)
        sheet = Image.new("RGB", (CELL_W * COLS, cell_h * ROWS), "white")
        draw = ImageDraw.Draw(sheet)
        for k, (p, im) in enumerate(thumbs):
            x, y = (k % COLS) * CELL_W, (k // COLS) * cell_h
            sheet.paste(im, (x, y))
            draw.rectangle([x, y, x + CELL_W - 1, y + cell_h - 1], outline="gray")
            draw.rectangle([x, y, x + 100, y + 40], fill="yellow")
            draw.text((x + 6, y + 4), f"p{p}", fill="red", font=font)
        out = out_dir / f"{args.doc}_{args.start}-{args.end}_{n}.jpg"
        sheet.save(out, "JPEG", quality=80)
        log(f"{out.relative_to(BUILD.parent)}  ({chunk[0][0]}~{chunk[-1][0]})")


if __name__ == "__main__":
    main()
