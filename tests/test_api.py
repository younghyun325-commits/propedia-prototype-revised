from conftest import parcel_review_id

A1 = "강남구 압구정동 527"
ITEM_KEYS = {"item_key", "item_type", "title", "summary", "scope_type", "scope_label", "needs_review", "evidence",
             "evidence_ok", "source",
             # P9 (feedback.md §2-2-5)
             "effective_from", "effective_to", "effective_label", "effective_status", "effective_status_label",
             "target_note", "tier"}
SOURCE_KEYS = {"doc_id", "short_title", "published_at", "pdf_page", "page_label", "page_image", "source_url",
               "source_note"}


def test_all_get_endpoints_200(client):
    for url in ["/api/v1/health", "/api/v1/demo-addresses", f"/api/v1/lookup?address={A1}",
                "/api/v1/parcels/1168011000105270000/projects", "/api/v1/projects/1/progress", "/api/v1/documents",
                "/api/v1/documents/D1", "/api/v1/documents/D2/pages/115", "/api/v1/events", "/api/v1/review-queue",
                "/api/v1/eval"]:
        r = client.get(url)
        assert r.status_code == 200, url


def test_404s(client):
    assert client.get("/api/v1/projects/999/progress").status_code == 404
    assert client.get("/api/v1/documents/D9").status_code == 404
    assert client.get("/api/v1/documents/D1/pages/999").status_code == 404
    assert client.get("/api/v1/parcels/123/projects").status_code == 404
    assert "detail" in client.get("/api/v1/documents/D9").json()


def test_health(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["as_of"] == "2026-10-06" and h["schema_version"] == "2"


def test_lookup_structure(client):
    d = client.get("/api/v1/lookup", params={"address": A1}).json()
    assert set(d) >= {"query", "status", "message", "normalized", "as_of", "layers", "reference", "review_applied",
                      "events", "coverage_note", "disclaimer"}
    L = d["layers"]
    assert set(L) == {"city", "gu", "dong", "parcel"}
    assert set(L["gu"]) >= {"items", "projects_by_stage"}
    assert set(L["dong"]) >= {"items", "projects", "deadlines"}
    assert set(L["parcel"]) >= {"items", "land_use", "land_use_note", "building", "building_note",
                                "included_projects", "nearby_projects", "nearby_note"}
    for it in L["city"] + L["gu"]["items"] + L["dong"]["items"]:
        assert set(it) >= ITEM_KEYS
        assert set(it["source"]) >= SOURCE_KEYS
    assert set(d["reference"]) == {"items", "note"}
    for it in d["reference"]["items"]:
        assert set(it) >= ITEM_KEYS | {"layer", "reference_reason"}


def test_lookup_not_ok_has_no_reference(client):
    d = client.get("/api/v1/lookup", params={"address": "서초구 방배동 818-14"}).json()
    assert d["status"] == "out_of_scope" and d["layers"] is None and d["reference"] is None


def test_post_lookup_applies_decisions(client):
    from core.db import connect_ro
    con = connect_ro()
    rid = parcel_review_id(con)
    con.close()
    d = client.post("/api/v1/lookup", json={"address": A1, "decisions": [{"review_id": rid, "action": "approve"}]})
    assert d.status_code == 200
    j = d.json()
    assert j["layers"]["parcel"]["included_projects"][0]["inclusion"] == "included"
    assert j["events"][0]["review_id"] == rid


def test_progress_structure(client):
    p = client.get("/api/v1/projects/1/progress").json()
    assert set(p) >= {"project_id", "name", "aliases", "project_type", "project_type_label", "track", "track_label",
                      "as_of", "position_label", "stages", "current", "next", "deadlines", "remaining",
                      "related_history", "stage_basis", "disclaimer"}


def test_events_steps(client):
    ev = client.get("/api/v1/events").json()
    assert [e["step"] for e in ev] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [e["doc_id"] for e in ev] == ["D4", "D3", "D2", "D1", "D5", "D6", "D7", "D8"]
    assert [len(e["events"]) for e in ev] == [0, 0, 0, 2, 0, 0, 0, 0]   # 규제 고시는 사업 상태를 바꾸지 않는다


def test_review_queue_parcel_first(client):
    q = client.get("/api/v1/review-queue").json()
    assert q[0]["item_type"] == "parcel_inclusion"
    assert q[0]["source"]["page_image"]


def test_documents_list(client):
    docs = client.get("/api/v1/documents").json()
    assert [d["doc_id"] for d in docs] == ["D4", "D3", "D2", "D1", "D5", "D6", "D7", "D8"]
    assert all(d["evidence_ok_rate"] == 1.0 for d in docs)
    kinds = {d["doc_id"]: d["doc_kind"] for d in docs}
    assert [kinds[k] for k in ("D5", "D6", "D7", "D8")] == ["designation"] * 3 + ["press"]


def test_document_items_have_tier(client):
    items = client.get("/api/v1/documents/D3").json()["items"]
    assert {i["item_key"]: i["tier"] for i in items}["D3-07"] == "applies"
    assert all(i["tier_label"] in ("적용", "배경") and i["tier_reason"] for i in items)


def test_page_detail_evidences(client):
    p = client.get("/api/v1/documents/D1/pages/1").json()
    assert p["text"] and p["image_url"] == "/pages/D1/p001.jpg"
    assert p["evidences"]
