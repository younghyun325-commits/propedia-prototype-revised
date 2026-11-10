"""Propedia 프리토타입 API (agents.md §11). Vercel 진입점이며, 로컬에서는 public/ 정적 화면도 함께 서빙한다.

시연 경로: LLM 호출 없음, DB는 읽기 전용. 외부 호출은 core/live/(도로명주소·브이월드)만 한다 (feedback2.md §2).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datetime import date  # noqa: E402

from fastapi import Body, FastAPI, HTTPException  # noqa: E402
from fastapi.responses import RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from core import catalog  # noqa: E402
from core import live as live_mod  # noqa: E402
from core import map as map_mod  # noqa: E402
from core.db import connect_ro, meta  # noqa: E402
from core.lookup import lookup, parcel_summary  # noqa: E402
from core.progress import progress  # noqa: E402
from core.timeutil import today_kst  # noqa: E402

app = FastAPI(title="Propedia 프리토타입 API", version="0.1")


def _con():
    return connect_ro()


@app.get("/api/v1/health")
def health():
    con = _con()
    try:
        m = meta(con)
        return {"status": "ok", "build_at": m.get("build_at"), "as_of": m.get("as_of"),
                "schema_version": m.get("schema_version"), "coverage_note": m.get("coverage_note"),
                **map_mod.key_status()}
    finally:
        con.close()


def _as_of(as_of: str | None) -> date:
    if not as_of:
        return today_kst()
    try:
        return date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(status_code=400, detail="기준일(as_of)은 YYYY-MM-DD 형식입니다") from None


@app.get("/api/v1/map/manifest")
def map_manifest():
    con = _con()
    try:
        return map_mod.map_manifest(con)
    except map_mod.MapDataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    finally:
        con.close()


@app.get("/api/v1/map/notices")
def map_notices(as_of: str | None = None):
    day = _as_of(as_of)
    con = _con()
    try:
        return map_mod.map_notices(con, day)
    finally:
        con.close()


@app.get("/api/v1/map/projects")
def map_projects(as_of: str | None = None):
    day = _as_of(as_of)
    con = _con()
    try:
        return map_mod.map_projects(con, day)
    finally:
        con.close()


@app.get("/api/v1/map/parcel-at")
def map_parcel_at(lat: float, lon: float):
    if not map_mod.in_click_range(lat, lon):
        raise HTTPException(status_code=400, detail="강남구 주변 좌표(위도 37.40~37.60, 경도 126.90~127.25)만 조회합니다")
    con = _con()
    try:
        return map_mod.parcel_at(con, lat, lon, live_mod.default())
    finally:
        con.close()


@app.get("/api/v1/map/wms/{layer}/{z}/{x}/{y}.png")
def map_wms_tile(layer: str, z: int, x: int, y: int):
    """공식 참고 WMS 타일 (P15). 브이월드 WMS는 CORS 헤더가 없어 서버 키로 받아 그대로 돌려준다. 저장하지 않는다."""
    live = live_mod.default()
    if live is None:
        raise HTTPException(status_code=503, detail="실시간 조회를 쓰지 않는 설정입니다")
    r = live.wms_tile(layer, z, x, y)
    if r["status"] == "bad_request":
        raise HTTPException(status_code=400, detail=r["note"])
    if r["status"] != "ok":
        raise HTTPException(status_code=504 if r["status"] == "timeout" else 502, detail="참고 WMS 타일을 받지 못했습니다")
    return Response(content=r["content"], media_type=r["content_type"],
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/v1/map/parcel")
def map_parcel(pnu: str):
    if not (pnu.isdigit() and len(pnu) == 19):
        raise HTTPException(status_code=400, detail="PNU는 숫자 19자리입니다")
    con = _con()
    try:
        return map_mod.parcel_by_pnu(con, pnu, live_mod.default())
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
