"""읽기 전용 DB 연결과 출처(SOURCE) 조립 (agents.md §10-1, §11-3)."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "propedia.db"


def connect_ro() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro&immutable=1", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def meta(con) -> dict:
    return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}


def source(con, document_id: int, pdf_page: int | None) -> dict | None:
    """SOURCE = {doc_id, short_title, published_at, pdf_page, page_label, page_image, source_url, source_note}"""
    d = con.execute("SELECT doc_id, short_title, published_at, source_url, source_note FROM documents WHERE id=?",
                    (document_id,)).fetchone()
    if d is None:
        return None
    p = None
    if pdf_page is not None:
        p = con.execute("SELECT page_label, image_url FROM pages WHERE document_id=? AND pdf_page=?",
                        (document_id, pdf_page)).fetchone()
    return {
        "doc_id": d["doc_id"],
        "short_title": d["short_title"],
        "published_at": d["published_at"],
        "pdf_page": pdf_page,
        "page_label": p["page_label"] if p else None,
        "page_image": p["image_url"] if p else None,
        "source_url": d["source_url"],
        "source_note": d["source_note"],
    }


def loads(s, default=None):
    if s is None:
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default
