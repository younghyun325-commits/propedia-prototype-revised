"""원본 PDF → 쪽별 텍스트(build/text)·쪽 이미지(public/pages)·page_heads.txt·pages.json (agents.md §8-3).

- 전사본(seed/transcripts/{doc}/p###.txt)이 있는 쪽은 그 텍스트를 쓰고 method='vision-claude', selected=1.
- D2 113~151은 seed/d2_selected_pages.yaml에 있는 쪽만 selected=1.
- 이미지가 이미 있으면 다시 렌더링하지 않는다 (--force 로 강제).
"""
import argparse
import json
import re

import pdfplumber
import pypdfium2 as pdfium
import yaml
from PIL import Image

from pipeline.common import (BUILD, DOC_ORDER, DOCS, PAGES_DIR, SEED, TEXT_DIR, TRANSCRIPTS, default_selected,
                             doc_pages, image_url, log, original_path, setup_stdout)

WIDTH = 1200
IMAGE_LIMIT_MB = 40
MIN_CHARS = 30

_DASH_LABEL = re.compile(r"^-\s*(\d{1,3})\s*-$")      # '- 109 -'
_NUM_LINE = re.compile(r"^(\d{1,3})$")
_HEAD_NUM = re.compile(r"^(?:(\d{1,3})\s+\S.*|.*\S\s+(\d{1,3}))$")   # D4 머리글 '제1절 개요 65' / '68 제3장 …'


def nonspace_len(s: str) -> int:
    return len(re.sub(r"\s+", "", s or ""))


def read_label(doc_id: str, pdf_page: int, text: str) -> str | None:
    """텍스트에서 인쇄 쪽 번호를 읽는다. 못 읽으면 None.

    공식(§3-2)이 있으면 공식과 같은 숫자만 받는다 (표 안 숫자를 쪽 번호로 오인하지 않도록).
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None
    formula = DOCS[doc_id]["label_fn"](pdf_page)
    edges = lines[:3] + lines[-3:]
    cands = []
    for ln in edges:
        for rx in (_DASH_LABEL, _NUM_LINE):
            m = rx.match(ln)
            if m:
                cands.append(int(m.group(1)))
    if doc_id == "D4":
        m = _HEAD_NUM.match(lines[0])
        if m:
            cands.append(int(m.group(1) or m.group(2)))
    for n in cands:
        if formula is None or n == int(formula):
            return str(n)
    return None


def load_d2_selection() -> set[int]:
    p = SEED / "d2_selected_pages.yaml"
    if not p.exists():
        return set()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {int(x["pdf_page"]) for x in data.get("selected", [])}


def render(pdf: pdfium.PdfDocument, pdf_page: int, out, quality: int, width: int = WIDTH) -> None:
    page = pdf[pdf_page - 1]
    w, _ = page.get_size()
    img = page.render(scale=width / w).to_pil()
    if img.width != width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.convert("RGB").save(out, "JPEG", quality=quality, optimize=True)
    page.close()


def process_doc(doc_id: str, force: bool, quality: int, d2_sel: set[int], heads: list[str]) -> list[dict]:
    src = original_path(doc_id)
    tdir = TEXT_DIR / doc_id
    idir = PAGES_DIR / doc_id
    tdir.mkdir(parents=True, exist_ok=True)
    idir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(src))
    rows = []
    with pdfplumber.open(str(src)) as plumb:
        for p in doc_pages(doc_id):
            # dedupe_chars: 굵은 글씨를 두 번 찍은 PDF에서 글자가 겹쳐 나오는 것을 없앤다 (D1 '공공람람')
            raw = plumb.pages[p - 1].dedupe_chars(tolerance=1).extract_text() or ""
            transcript = TRANSCRIPTS / doc_id / f"p{p:03d}.txt"
            if transcript.exists():
                text = transcript.read_text(encoding="utf-8")
                method = "vision-claude"
                selected = 1
            else:
                text = raw
                method = "text" if nonspace_len(raw) >= MIN_CHARS else "image-only"
                selected = default_selected(doc_id, p)
                if doc_id == "D2" and p in d2_sel:
                    selected = 1
            (tdir / f"p{p:03d}.txt").write_text(text, encoding="utf-8")
            img_path = idir / f"p{p:03d}.jpg"
            if force or not img_path.exists():
                render(pdf, p, img_path, quality)
            label = read_label(doc_id, p, raw) or DOCS[doc_id]["label_fn"](p)
            n = nonspace_len(text)
            rows.append({"pdf_page": p, "page_label": label, "method": method, "char_count": n,
                         "image_url": image_url(doc_id, p), "selected": selected})
            first = [ln.strip() for ln in raw.splitlines() if ln.strip()][:2]
            heads.append(f"{doc_id} p{p} chars={nonspace_len(raw)} label={label} | " + " / ".join(first))
    pdf.close()
    (tdir / "pages.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def images_mb() -> float:
    return sum(f.stat().st_size for f in PAGES_DIR.rglob("*.jpg")) / 1e6


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="쪽 이미지를 다시 렌더링")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("docs", nargs="*", default=DOC_ORDER)
    args = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    d2_sel = load_d2_selection()
    heads: list[str] = []
    summary = []
    for d in args.docs:
        rows = process_doc(d, args.force, args.quality, d2_sel, heads)
        sel = [r for r in rows if r["selected"]]
        ok = [r for r in sel if r["char_count"] >= MIN_CHARS]
        summary.append((d, len(rows), len(sel), len(ok), sum(r["method"] == "vision-claude" for r in rows)))
    if set(args.docs) == set(DOC_ORDER):
        (BUILD / "page_heads.txt").write_text("\n".join(heads) + "\n", encoding="utf-8")

    total = images_mb()
    if total > IMAGE_LIMIT_MB and args.quality > 65:
        log(f"쪽 이미지 합계 {total:.1f}MB > {IMAGE_LIMIT_MB}MB → 품질 65로 다시 만듭니다")
        heads.clear()
        for d in args.docs:
            process_doc(d, True, 65, d2_sel, heads)
        total = images_mb()

    log("doc | 쪽 | 선택 | 선택 중 텍스트 확보 | 전사")
    for s in summary:
        log(" | ".join(map(str, s)))
    log(f"쪽 이미지 합계 {total:.1f}MB")


if __name__ == "__main__":
    main()
