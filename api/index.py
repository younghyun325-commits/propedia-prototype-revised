"""Propedia 프리토타입 API (agents.md §11). Vercel 진입점이며, 로컬에서는 public/ 정적 화면도 함께 서빙한다.

시연 경로: LLM 호출 없음, DB는 읽기 전용. 외부 호출은 core/live/(도로명주소·브이월드)만 한다 (feedback2.md §2).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import Body, FastAPI, HTTPException  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from core import catalog  # noqa: E402
from core import live as live_mod  # noqa: E402
from core.db import connect_ro, meta  # noqa: E402
from core.lookup import lookup, parcel_summary  # noqa: E402
from core.progress import progress  # noqa: E402

app = FastAPI(title="Propedia 프리토타입 API", version="0.1")


def _con():
    return connect_ro()


@app.get("/api/v1/health")
def health():
    con = _con()
    try:
        m = meta(con)
        return {"status": "ok", "build_at": m.get("build_at"), "as_of": m.get("as_of"),
                "schema_version": m.get("schema_version"), "coverage_note": m.get("coverage_note")}
    finally:
        con.close()


@app.get("/api/v1/demo-addresses")
def demo_addresses():
    con = _con()
    try:
        return catalog.demo_addresses(con)
    finally:
        con.close()


@app.get("/api/v1/lookup")
def lookup_get(address: str = ""):
    con = _con()
    try:
        return lookup(con, address, live=live_mod.default())
    finally:
        con.close()


@app.post("/api/v1/lookup")
def lookup_post(body: dict = Body(default_factory=dict)):
    con = _con()
    try:
        return lookup(con, str(body.get("address") or ""), body.get("decisions"), live=live_mod.default())
    finally:
        con.close()


@app.get("/api/v1/parcels/{pnu}/projects")
def parcel_projects(pnu: str):
    if not (pnu.isdigit() and len(pnu) == 19):
        raise HTTPException(status_code=404, detail="PNU는 숫자 19자리입니다")
    con = _con()
    try:
        return parcel_summary(con, pnu)
    finally:
        con.close()


def _progress(project_id: int, decisions=None):
    con = _con()
    try:
        res = progress(con, project_id, decisions)
    finally:
        con.close()
    if res is None:
        raise HTTPException(status_code=404, detail=f"사업 {project_id}을(를) 찾을 수 없습니다")
    return res


@app.get("/api/v1/projects/{project_id}/progress")
def progress_get(project_id: int):
    return _progress(project_id)


@app.post("/api/v1/projects/{project_id}/progress")
def progress_post(project_id: int, body: dict = Body(default_factory=dict)):
    return _progress(project_id, body.get("decisions"))


@app.get("/api/v1/documents")
def documents():
    con = _con()
    try:
        return catalog.list_documents(con)
    finally:
        con.close()


@app.get("/api/v1/documents/{doc_id}")
def document(doc_id: str):
    con = _con()
    try:
        res = catalog.document_detail(con, doc_id)
    finally:
        con.close()
    if res is None:
        raise HTTPException(status_code=404, detail=f"문서 {doc_id}을(를) 찾을 수 없습니다")
    return res


@app.get("/api/v1/documents/{doc_id}/pages/{pdf_page}")
def document_page(doc_id: str, pdf_page: int):
    con = _con()
    try:
        res = catalog.page_detail(con, doc_id, pdf_page)
    finally:
        con.close()
    if res is None:
        raise HTTPException(status_code=404, detail=f"{doc_id} {pdf_page}쪽을 찾을 수 없습니다")
    return res


@app.get("/api/v1/events")
def events():
    con = _con()
    try:
        return catalog.list_events(con)
    finally:
        con.close()


@app.get("/api/v1/review-queue")
def review_queue():
    con = _con()
    try:
        return catalog.list_review_queue(con)
    finally:
        con.close()


@app.get("/api/v1/eval")
def eval_report():
    con = _con()
    try:
        return catalog.eval_report(con)
    finally:
        con.close()


if os.environ.get("VERCEL") == "1":
    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/index.html")
else:
    # API 라우트를 모두 등록한 뒤 마지막에 정적 화면을 붙인다 (순서가 바뀌면 API가 404)
    app.mount("/", StaticFiles(directory=str(ROOT / "public"), html=True), name="public")
