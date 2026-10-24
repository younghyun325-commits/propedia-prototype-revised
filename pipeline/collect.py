"""원본 PDF → 쓰는 쪽만 발췌한 data_raw/Dn.pdf + manifest.csv (agents.md §8-2)."""
import csv
import json

from pypdf import PdfReader, PdfWriter

from pipeline.common import (DATA_RAW, DOC_ORDER, DOCS, doc_pages, log, original_path, original_rel,
                             ranges_str, setup_stdout, sha256)

MANIFEST_COLS = ["doc_id", "original_path", "original_sha256", "original_pages", "excerpt_path",
                 "excerpt_sha256", "page_ranges", "excerpt_page_map"]


def build_excerpt(doc_id: str) -> dict:
    src = original_path(doc_id)
    reader = PdfReader(str(src))
    pages = doc_pages(doc_id)
    writer = PdfWriter()
    page_map = {}
    for i, p in enumerate(pages, start=1):
        writer.add_page(reader.pages[p - 1])
        page_map[str(p)] = i
    # 같은 입력이면 같은 파일이 나오도록 메타데이터·ID를 고정한다
    writer.add_metadata({"/Producer": "propedia-pretotype collect", "/Title": f"{doc_id} excerpt"})
    out = DATA_RAW / f"{doc_id}.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    size_mb = out.stat().st_size / 1e6
    return {
        "doc_id": doc_id,
        "original_path": original_rel(doc_id),
        "original_sha256": sha256(src),
        "original_pages": len(reader.pages),
        "excerpt_path": f"data_raw/{doc_id}.pdf",
        "excerpt_sha256": sha256(out),
        "page_ranges": ranges_str(DOCS[doc_id]["ranges"]),
        "excerpt_page_map": json.dumps(page_map, ensure_ascii=False),
        "_size_mb": size_mb,
        "_n": len(pages),
    }


def main() -> None:
    setup_stdout()
    DATA_RAW.mkdir(exist_ok=True)
    rows = [build_excerpt(d) for d in DOC_ORDER]
    with open(DATA_RAW / "manifest.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log("doc | 원본쪽수 | 발췌쪽수 | 발췌 MB | 쪽 범위")
    for r in rows:
        log(f"{r['doc_id']} | {r['original_pages']} | {r['_n']} | {r['_size_mb']:.1f} | {r['page_ranges']}")
        if r["_size_mb"] > 10:
            log(f"  ※ {r['doc_id']} 발췌본이 10MB를 넘습니다 → HUMAN_TODO 기록 대상")
    log("manifest.csv 작성 완료")


if __name__ == "__main__":
    main()
