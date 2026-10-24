"""4개 층 통합 조회 (agents.md §10-4, §11-3)."""
import math

from core import review as review_mod
from core.address import normalize
from core.db import loads, meta, source
from core.timeutil import d_day, parse_date, today_kst

DISCLAIMER = "공개된 고시·공식 데이터 기준 정보이며, 조합 공지와 다를 수 있습니다. 개별 권리 판단은 하지 않습니다."
NEARBY_M = 500
FOCUS_SAENGHWAL = "압구정·청담"
DONGNAM = {"11650", "11680", "11710", "11740"}
SGG_NAMES = {"11650": "서초구", "11680": "강남구", "11710": "송파구", "11740": "강동구"}

INCLUSION_LABELS = {"included": "포함", "possible": "포함될 수 있음", "nearby": "주변", "none": "해당 없음"}
BASIS_LABELS = {"manual_review": "사람 검수로 확정", "jibun_table": "지번 조서에 기재"}
NOTE_NO_ADDR_COORD = "좌표가 없어 주변 500m 사업 판정을 생략했습니다"
NOTE_NO_PROJECT_COORD = "사업 중심 좌표가 없어 주변 500m 사업 판정을 생략했습니다"
LAND_USE_NOTE = "필지별 용도지역은 프리토타입 범위 밖입니다 (브이월드 미연동)"


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def scope_label(scope_type: str, refs: list, dong_names: dict) -> str:
    if scope_type == "SIDO":
        return "서울 전역"
    if scope_type == "SGG":
        if set(refs) == DONGNAM:
            return "동남권 (서초·강남·송파·강동)"
        if len(refs) == 1:
            return f"자치구 {SGG_NAMES.get(refs[0], refs[0])}"
        return f"자치구 {len(refs)}곳"
    if scope_type == "SAENGHWAL":
        return "지역생활권 " + "·".join(refs) if len(refs) == 1 else "지역생활권 " + ", ".join(refs)
    if scope_type == "BJD":
        return "법정동 " + ", ".join(dong_names.get(r, r) for r in refs)
    if scope_type == "PARCEL":
        return "필지"
    return scope_type


def load_items(con, ov) -> list[dict]:
    dong_names = {r["bjd_code"]: r["dong_name"] for r in con.execute("SELECT bjd_code, dong_name FROM bjd_codes")}
    rows = con.execute(
        """SELECT a.*, d.published_at FROM applicability_rules a JOIN documents d ON d.id = a.document_id""").fetchall()
    items = []
    for a in rows:
        key = a["item_key"]
        if key in ov.items_rejected:
            continue
        edits = ov.items_edits.get(key, {})
        scope_type = edits.get("scope_type", a["scope_type"])
        refs = edits.get("scope_ref", loads(a["scope_ref"], []))
        items.append({
            "item_key": key,
            "item_type": a["item_type"],
            "title": a["title"],
            "summary": edits.get("summary", a["summary"]),
            "scope_type": scope_type,
            "scope_ref": refs,
            "scope_label": scope_label(scope_type, refs, dong_names),
            "scope_note": a["scope_note"],
            "needs_review": bool(a["needs_review"]) and key not in ov.items_approved,
            "edited": bool(edits),
            "evidence": a["evidence"],
            "evidence_ok": bool(a["evidence_ok"]),
            "confidence": a["confidence"],
            "source": source(con, a["document_id"], a["pdf_page"]),
            "_published_at": a["published_at"] or "",
        })
    # 정렬: 문서 날짜 최신 → item_key
    items.sort(key=lambda x: x["item_key"])
    items.sort(key=lambda x: x["_published_at"], reverse=True)
    return items


def strip_private(items: list[dict]) -> list[dict]:
    return [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]


def place_items(items: list[dict], norm: dict) -> dict:
    layers = {"city": [], "gu": [], "dong": [], "parcel": []}
    for it in items:
        st, refs = it["scope_type"], it["scope_ref"]
        if st == "SIDO" and "11" in refs:
            layers["city"].append(it)
        elif st == "SGG" and norm["sgg_code"] in refs:
            layers["gu"].append(it)
        elif st == "SAENGHWAL" and norm["saenghwal"] and norm["saenghwal"] in refs:
            layers["dong"].append(it)
        elif st == "BJD" and norm["bjd_code"] in refs:
            layers["dong"].append(it)
        elif st == "PARCEL" and norm["pnu"] in refs:
            layers["parcel"].append(it)
    return {k: strip_private(v) for k, v in layers.items()}


def project_stage(con, p) -> dict:
    t = con.execute("SELECT seq, title FROM stage_templates WHERE project_type=? AND sub_stage_code=?",
                    (p["project_type"], p["sub_stage_code"])).fetchone()
    return {"code": p["sub_stage_code"], "title": t["title"] if t else None, "seq": t["seq"] if t else None}


def review_id_for(con, project_id: int, pnu: str) -> int | None:
    r = con.execute("SELECT id FROM review_queue WHERE item_type='parcel_inclusion' AND ref_key=?",
                    (f"{project_id}:{pnu}",)).fetchone()
    return r["id"] if r else None


def parcel_projects(con, norm: dict, ov) -> tuple[list, list, str | None]:
    """(포함/포함될 수 있음 사업, 주변 사업, nearby_note)"""
    included, nearby = [], []
    pnu = norm["pnu"]
    shown = set()
    for pp in con.execute(
            """SELECT pp.*, p.name, p.lat, p.lon, p.location_text FROM project_parcels pp
               JOIN projects p ON p.id = pp.project_id WHERE pp.pnu=?""", (pnu,)):
        decision = ov.parcel.get((pp["project_id"], pnu))
        if decision == "reject":
            continue
        if pp["verified"] or decision == "approve":
            inclusion = "included"
            basis = pp["basis"] if pp["verified"] else "manual_review"
            message = f"이 필지는 {pp['name']} 구역에 포함되어 있습니다"
        else:
            inclusion = "possible"
            basis = pp["basis"]
            message = f"{pp['name']} 구역에 포함될 수 있습니다"
        if basis == "representative_only":
            loc = con.execute("SELECT jibun_text FROM doc_locations WHERE pnu=? AND method='representative'",
                              (pnu,)).fetchone()
            basis_label = f"고시에 대표 지번({loc['jibun_text'] if loc else '일대'})만 있음"
        else:
            basis_label = BASIS_LABELS.get(basis, basis)
        included.append({
            "project_id": pp["project_id"], "name": pp["name"], "inclusion": inclusion,
            "inclusion_label": INCLUSION_LABELS[inclusion], "message": message, "basis": basis,
            "basis_label": basis_label, "review_id": review_id_for(con, pp["project_id"], pnu),
            "progress_url": f"/api/v1/projects/{pp['project_id']}/progress",
            "source": source(con, pp["source_doc_id"], pp["pdf_page"]),
        })
        shown.add(pp["project_id"])

    note = None
    if norm["lat"] is None or norm["lon"] is None:
        note = NOTE_NO_ADDR_COORD
    else:
        no_coord = False
        for p in con.execute("SELECT * FROM projects"):
            if p["id"] in shown:
                continue
            if p["lat"] is None or p["lon"] is None:
                no_coord = True
                continue
            dist = haversine_m(norm["lat"], norm["lon"], p["lat"], p["lon"])
            if dist <= NEARBY_M:
                stage = project_stage(con, p)
                nearby.append({"project_id": p["id"], "name": p["name"], "inclusion": "nearby",
                               "inclusion_label": "주변에서 진행 중인 사업", "distance_m": int(round(dist)),
                               "stage": stage, "progress_url": f"/api/v1/projects/{p['id']}/progress",
                               "source": source(con, p["stage_source_doc_id"], None)})
        nearby.sort(key=lambda x: x["distance_m"])
        if no_coord and not nearby:
            note = NOTE_NO_PROJECT_COORD
    return included, nearby, note


def land_use(con, included: list) -> tuple[dict | None, str | None]:
    for inc in included:
        p = con.execute("SELECT land_use, land_use_page, stage_source_doc_id FROM projects WHERE id=?",
                        (inc["project_id"],)).fetchone()
        if p and p["land_use"]:
            src = source(con, p["stage_source_doc_id"], p["land_use_page"])
            return ({"value": p["land_use"],
                     "basis": f"사업 문서 기재 ({src['doc_id']} p{p['land_use_page']}, 정비구역 기준)",
                     "source": src}, None)
    return None, LAND_USE_NOTE


def dong_projects(con, norm: dict, exclude: set, today) -> tuple[list, list]:
    projects, deadlines = [], []
    for p in con.execute("SELECT * FROM projects WHERE bjd_code=? ORDER BY id", (norm["bjd_code"],)):
        if p["id"] in exclude:
            continue
        stage = project_stage(con, p)
        projects.append({"project_id": p["id"], "name": p["name"], "stage": stage,
                         "location_text": p["location_text"],
                         "message": "같은 법정동에서 진행 중인 사업 (이 필지 포함 여부는 확인되지 않음)",
                         "progress_url": f"/api/v1/projects/{p['id']}/progress",
                         "source": source(con, p["stage_source_doc_id"], None)})
        for d in con.execute("SELECT * FROM deadlines WHERE project_id=? ORDER BY due_on", (p["id"],)):
            due = parse_date(d["due_on"])
            if due < today:
                continue
            n, label = d_day(due, today)
            deadlines.append({"project_id": p["id"], "project_name": p["name"], "kind": d["kind"],
                              "title": d["title"], "starts_on": d["starts_on"], "due_on": d["due_on"],
                              "d_day": n, "d_day_label": label, "source": source(con, d["source_doc_id"], d["pdf_page"])})
    return projects, deadlines


def projects_by_stage(con, sgg_code: str) -> dict:
    out = {}
    for p in con.execute("SELECT * FROM projects WHERE sgg_code=?", (sgg_code,)):
        s = project_stage(con, p)
        out.setdefault(s["code"], {"title": s["title"], "count": 0})["count"] += 1
    return dict(sorted(out.items()))


def lookup(con, text: str, decisions=None, today=None) -> dict:
    today = today or today_kst()
    m = meta(con)
    ov = review_mod.apply(con, decisions)
    norm = normalize(con, text)
    normalized = {k: norm[k] for k in ("addr_id", "road_address", "jibun_address", "pnu", "bjd_code", "sgg_code",
                                       "dong_name", "saenghwal", "lat", "lon", "coord_source")}
    resp = {"query": text, "status": norm["status"], "message": norm["message"], "normalized": normalized,
            "as_of": m.get("as_of"), "layers": None, "review_applied": ov.review_applied, "events": ov.events,
            "coverage_note": m.get("coverage_note"), "disclaimer": DISCLAIMER}
    if norm["status"] != "ok":
        return resp

    items = load_items(con, ov)
    placed = place_items(items, norm)
    included, nearby, nearby_note = parcel_projects(con, norm, ov)
    shown = {p["project_id"] for p in included} | {p["project_id"] for p in nearby}
    dprojects, ddeadlines = dong_projects(con, norm, shown, today)
    lu, lu_note = land_use(con, included)
    resp["layers"] = {
        "city": placed["city"],
        "gu": {"items": placed["gu"], "projects_by_stage": projects_by_stage(con, norm["sgg_code"])},
        "dong": {"items": placed["dong"], "projects": dprojects, "deadlines": ddeadlines},
        "parcel": {"items": placed["parcel"], "land_use": lu, "land_use_note": lu_note,
                   "included_projects": included, "nearby_projects": nearby, "nearby_note": nearby_note,
                   "no_project_message": None if included else
                   f"{(m.get('as_of') or '').replace('-', '.')}까지 확인된 고시 기준, 진행 중인 사업이 없습니다"},
    }
    note = m.get("coverage_note") or ""
    if norm["saenghwal"] and norm["saenghwal"] != FOCUS_SAENGHWAL:
        note = f"{note} {norm['saenghwal']} 지역생활권 장은 프리토타입 범위 밖입니다".strip()
    resp["coverage_note"] = note
    return resp


def parcel_summary(con, pnu: str) -> dict:
    """GET /parcels/{pnu}/projects 응답."""
    row = con.execute("SELECT * FROM demo_addresses WHERE pnu=? AND in_scope=1 LIMIT 1", (pnu,)).fetchone()
    b = con.execute("SELECT bjd_code, sgg_code, saenghwal FROM bjd_codes WHERE bjd_code=?", (pnu[:10],)).fetchone()
    norm = {"pnu": pnu, "bjd_code": pnu[:10], "sgg_code": b["sgg_code"] if b else pnu[:5],
            "saenghwal": b["saenghwal"] if b else None,
            "lat": row["lat"] if row else None, "lon": row["lon"] if row else None}
    included, nearby, note = parcel_projects(con, norm, review_mod.Overrides())
    out = []
    for p in included + nearby:
        out.append({"project_id": p["project_id"], "name": p["name"], "inclusion": p["inclusion"],
                    "inclusion_label": p["inclusion_label"], "basis": p.get("basis"),
                    "distance_m": p.get("distance_m"), "evidence_source": p["source"]})
    return {"pnu": pnu, "projects": out, "nearby_note": note}
