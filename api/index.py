"""Propedia 프리토타입 API (agents.md §11). Vercel 진입점이며, 로컬에서는 public/ 정적 화면도 함께 서빙한다.

시연 경로: LLM 호출 없음, DB는 읽기 전용. 외부 호출은 core/live/(도로명주소·브이월드)만 한다 (feedback2.md §2).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datetime import date  # noqa: E402

from fastapi import Body, FastAPI, HTTPException, Query  # noqa: E402
from fastapi.responses import RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from core import catalog  # noqa: E402
from core import live as live_mod  # noqa: E402
from core import map as map_mod  # noqa: E402
from core import market as market_mod  # noqa: E402
from core.db import connect_market_ro, connect_ro, meta  # noqa: E402
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


def _date_param(v: str | None, name: str, default: date) -> date:
    if not v:
        return default
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name}은(는) YYYY-MM-DD 형식입니다") from None


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


WMS_CACHE = "public, max-age=86400, s-maxage=604800"   # 성공 타일만 (브라우저 1일, CDN 7일)
NO_STORE = {"Cache-Control": "no-store"}                # 오류는 캐시하지 않는다


@app.get("/api/v1/map/wms/{layer}/{z}/{x}/{y}.png")
def map_wms_tile(layer: str, z: int, x: int, y: int, size: int | None = None, format: str | None = None):
    """공식 참고 WMS 타일 (P15·P16 0단계). 브이월드 WMS는 CORS 헤더가 없어 서버 키로 받아 그대로 돌려준다. 저장하지 않는다.
    허용 목록(레이어 3종·강남구 경계 + 2km·크기 256/512·image/png·지적도 0.6m/px 이하) 밖이면 400. 응답에 키·원 URL을 넣지 않는다."""
    bad = map_mod.wms_request_error(layer, z, x, y, size, format)
    if bad:
        raise HTTPException(status_code=400, detail=bad, headers=NO_STORE)
    live = live_mod.default()
    if live is None:
        raise HTTPException(status_code=503, detail="실시간 조회를 쓰지 않는 설정입니다", headers=NO_STORE)
    r = live.wms_tile(layer, z, x, y, size=size)
    if r["status"] == "bad_request":
        raise HTTPException(status_code=400, detail=r["note"], headers=NO_STORE)
    if r["status"] != "ok":
        raise HTTPException(status_code=504 if r["status"] == "timeout" else 502,
                            detail="참고 WMS 타일을 받지 못했습니다", headers=NO_STORE)
    return Response(content=r["content"], media_type=r["content_type"], headers={"Cache-Control": WMS_CACHE})


@app.get("/api/v1/map/feature/{kind}/{fid}")
def map_feature(kind: str, fid: str, as_of: str | None = None):
    """인스펙터 내용 (P16). 사업 = progress(), 규제 = applicability_rules 항목, 필지 = /map/parcel과 같은 조립.
    as_of(YYYY-MM-DD)를 주면 그날 기준 기한·효력 상태 (P19 타임라인)."""
    day = _as_of(as_of)
    if kind == "apartment":
        return _market(lambda mcon, con: market_mod.feature_apartment(mcon, con, fid, day))
    con = _con()
    try:
        return map_mod.map_feature(con, kind, fid, live_mod.default() if kind == "parcel" else None, day)
    except map_mod.FeatureNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    finally:
        con.close()


def _market(fn):
    """market.db(실거래)를 쓰는 응답. 파일이 없으면 503 + 한국어 안내 (다른 기능은 그대로)."""
    try:
        mcon = connect_market_ro()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail=market_mod.UNAVAILABLE) from None
    con = _con()
    try:
        return fn(mcon, con)
    except market_mod.ApartmentNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e) if "면적대" in str(e) else
                            "from은 YYYY-MM 또는 YYYY-MM-DD 형식입니다") from None
    finally:
        mcon.close()
        con.close()


@app.get("/api/v1/apartments/{cid}")
def apartment(cid: str):
    """아파트 단지 (P17): 기본 정보(없으면 상태 문구), 준공연도(실거래 신고 기준), 면적대별 거래 요약, 걸친 영향권, 출처"""
    return _market(lambda mcon, con: market_mod.apartment(mcon, con, cid, today_kst()))


@app.get("/api/v1/apartments/{cid}/trades")
def apartment_trades(cid: str, band: str | None = None, from_: str | None = Query(None, alias="from"),
                     as_of: str | None = None):
    """월별 중위 거래가·건수(해제 제외), 개별 거래 점, 최근 거래 20건(해제 표시). as_of(P19): 계약일 ≤ 기준일만"""
    day = _as_of(as_of)
    return _market(lambda mcon, con: market_mod.trades(mcon, cid, band or None, from_ or None, as_of=day))


@app.get("/api/v1/timeline")
def timeline(from_: str | None = Query(None, alias="from"), to: str | None = None):
    """시간축 계열 (P19): 고시 발행·공람·효력·사업 단계·자료 기준일. from·to가 없으면 전체"""
    frm = _date_param(from_, "from", date(1900, 1, 1))
    end = _date_param(to, "to", date(2100, 12, 31))
    if frm > end:
        raise HTTPException(status_code=400, detail="from은 to보다 앞선 날짜여야 합니다")
    con = _con()
    try:
        return map_mod.timeline(con, frm, end)
    finally:
        con.close()


@app.get("/api/v1/feed")
def feed(limit: int = Query(50, ge=1, le=200), as_of: str | None = None):
    """고시 피드 (P19): 발행일 ≤ 기준일 문서, 최신순, 기한은 그날 D-day"""
    day = _as_of(as_of)
    con = _con()
    try:
        return map_mod.feed(con, day, limit)
    finally:
        con.close()


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
