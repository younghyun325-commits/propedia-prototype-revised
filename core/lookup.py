"""4개 층 통합 조회 (agents.md §10-4, §11-3, feedback.md §3-3).

층에는 tier='applies'이면서 효력이 끝나지 않은 항목만 놓고(층별 5개 상한), 넘친 항목·효력이 끝난 항목·
reference_rank가 있는 배경 항목은 '참고(reference)' 섹션으로 보낸다.
"""
import math

from core import review as review_mod
from core.address import jibun_text, normalize
from core.db import loads, meta, source
from core.timeutil import d_day, dot, effective, parse_date, today_kst

DISCLAIMER = "공개된 고시·공식 데이터 기준 정보이며, 조합 공지와 다를 수 있습니다. 개별 권리 판단은 하지 않습니다."
NEARBY_M = 500
LAYER_CAP = 5            # 서울 전역·자치구·법정동 층별 상한 (필지 층은 상한 없음)
REFERENCE_CAP = 5
CLASS_ORDER = {"a": 0, "b": 1, "c": 2}
REFERENCE_NOTE = "배경 설명과 참고 계획입니다. 이 땅에 바로 적용되는 결정은 위 4개 층에 있습니다."
DONGNAM = {"11650", "11680", "11710", "11740"}
SGG_NAMES = {"11650": "서초구", "11680": "강남구", "11710": "송파구", "11740": "강동구"}

INCLUSION_LABELS = {"included": "포함", "likely": "포함된 것으로 보임", "possible": "포함될 수 있음", "nearby": "주변",
                    "none": "해당 없음"}
BASIS_LABELS = {"manual_review": "사람 검수로 확정", "jibun_table": "지번 조서에 기재",
                "map_reading": "지도 대조 후보 (고시 결정도와 지적도를 맞대 본 결과, 사람 확인 전)"}
NOTE_NO_ADDR_COORD = "좌표가 없어 주변 500m 사업 판정을 생략했습니다"
NOTE_NO_PROJECT_COORD = "사업 중심 좌표가 없어 주변 500m 사업 판정을 생략했습니다"
LAND_OFFLINE_NOTE = "이 필지는 미리 받아 둔 토지 정보가 없고, 실시간 조회를 쓰지 않았습니다"
BUILDING_NOT_FETCHED = "이 필지는 건축물대장을 조회하지 않았습니다 (빌드 때 시연 주소만 조회)"
BUILDING_SOURCE = "건축HUB 건축물대장 표제부(getBrTitleInfo)"


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
        return "생활권계획 참고 (" + ", ".join(refs) + ")"
    if scope_type == "BJD":
        return "법정동 " + ", ".join(dong_names.get(r, r) for r in refs)
    if scope_type == "PARCEL":
        return "필지"
    return scope_type


def load_items(con, ov, today) -> list[dict]:
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
        tier = edits.get("tier", a["tier"])
        more = [{"label": m["label"], "evidence": m["evidence"], "evidence_ok": bool(m.get("evidence_ok")),
                 "source": source(con, a["document_id"], m["pdf_page"])} for m in loads(a["more_evidence"], [])]
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
            "more_evidence": more,
            "confidence": a["confidence"],
            "effective_from": a["effective_from"],
            "effective_to": a["effective_to"],
            **effective(a["effective_from"], a["effective_to"], today),
            "target_note": a["target_note"],
            "tier": tier,
            "tier_class": a["tier_class"],
            "tier_reason": a["tier_reason"],
            "source": source(con, a["document_id"], a["pdf_page"]),
            "_published_at": a["published_at"] or "",
            "_applies_rank": a["applies_rank"],
            "_reference_rank": a["reference_rank"],
            "_tier_edited": tier != a["tier"],
        })
    # 층 안 정렬: tier_class a → b → c → 없음, applies_rank, 문서 날짜 최신, item_key (feedback.md §3-3)
    items.sort(key=lambda x: x["item_key"])
    items.sort(key=lambda x: x["_published_at"], reverse=True)
    items.sort(key=lambda x: (CLASS_ORDER.get(x["tier_class"], 3),
                              x["_applies_rank"] if x["_applies_rank"] is not None else 999))
    return items


def strip_private(items: list[dict]) -> list[dict]:
    return [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]


def scope_layer(it: dict, norm: dict) -> str | None:
    """이 주소의 범위에 맞는 항목이면 그 층 이름. 지역생활권은 층이 없어 'saenghwal'(참고 전용)."""
    st, refs = it["scope_type"], it["scope_ref"]
    if st == "SIDO" and "11" in refs:
        return "city"
    if st == "SGG" and norm["sgg_code"] in refs:
        return "gu"
    if st == "BJD" and norm["bjd_code"] in refs:
        return "dong"
    if st == "PARCEL" and norm["pnu"] in refs:
        return "parcel"
    if st == "SAENGHWAL" and norm["saenghwal"] and norm["saenghwal"] in refs:
        return "saenghwal"
    return None


def place_items(items: list[dict], norm: dict) -> tuple[dict, list[dict]]:
    """(층별 항목, 참고 항목). items는 load_items 정렬 순서."""
    layers = {"city": [], "gu": [], "dong": [], "parcel": []}
    spill, ranked = [], []     # 참고: 층에서 빠진 항목(넘침·효력 끝남·검수에서 배경으로) → reference_rank 순
    for it in items:
        layer = scope_layer(it, norm)
        if layer is None:
            continue
        if it["tier"] == "applies" and layer in layers:
            if it["effective_status"] == "ended":
                spill.append(it | {"layer": layer, "reference_reason": "효력 기간 끝남"})
            elif layer != "parcel" and len(layers[layer]) >= LAYER_CAP:
                spill.append(it | {"layer": layer, "reference_reason": f"층별 {LAYER_CAP}개 초과"})
            else:
                layers[layer].append(it)
        elif it["tier"] == "applies":      # 지역생활권 범위 항목을 검수에서 '적용'으로 바꾼 경우
            spill.append(it | {"layer": "dong", "reference_reason": "지역생활권 항목은 참고로만 표시"})
        elif it["tier"] == "background":
            ref_layer = "dong" if layer == "saenghwal" else layer
            if it["_tier_edited"]:
                spill.append(it | {"layer": ref_layer, "reference_reason": "검수에서 배경으로 바꿈"})
            elif it["_reference_rank"] is not None:
                ranked.append(it | {"layer": ref_layer, "reference_reason": "참고 계획"})
    ranked.sort(key=lambda x: x["_reference_rank"])
    reference = (spill + ranked)[:REFERENCE_CAP]
    return {k: strip_private(v) for k, v in layers.items()}, strip_private(reference)


def project_stage(con, p) -> dict:
    t = con.execute("SELECT seq, title FROM stage_templates WHERE project_type=? AND sub_stage_code=?",
                    (p["project_type"], p["sub_stage_code"])).fetchone()
    return {"code": p["sub_stage_code"], "title": t["title"] if t else None, "seq": t["seq"] if t else None}


def review_id_for(con, project_id: int, pnu: str, basis: str | None = None) -> int | None:
    if basis == "map_reading":          # 지도 대조 후보는 사업마다 한 건으로 묶어 검수한다
        r = con.execute("SELECT id FROM review_queue WHERE item_type='parcel_group' AND ref_key=?",
                        (f"{project_id}:map_reading",)).fetchone()
    else:
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
        elif pp["basis"] == "map_reading":      # 판정표 3번과 같은 강도 (feedback2.md §5-4)
            inclusion = "likely"
            basis = pp["basis"]
            message = f"{pp['name']} 구역에 포함된 것으로 보입니다. 확인해 주세요"
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
            "basis_label": basis_label, "review_id": review_id_for(con, pp["project_id"], pnu, pp["basis"]),
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
                               "distance_basis": distance_basis(norm.get("coord_source"), p["coord_source"]),
                               "stage": stage, "progress_url": f"/api/v1/projects/{p['id']}/progress",
                               "source": source(con, p["stage_source_doc_id"], None)})
        nearby.sort(key=lambda x: x["distance_m"])
        if no_coord and not nearby:
            note = NOTE_NO_PROJECT_COORD
    return included, nearby, note


def distance_basis(addr_coord: str | None, project_coord: str | None) -> str:
    """거리 옆에 작게 붙이는 기준 (feedback.md §5-3)."""
    proj = project_coord or ""
    if proj.startswith("근사"):
        where = proj.split("인접 필지", 1)[1].split("OSM", 1)[0].strip() if "인접 필지" in proj else ""
        proj = "사업 중심 근사값: 인접 필지 OSM 좌표" + (f" ({where})" if where else "")
    else:
        proj = f"사업 중심 좌표 ({proj})"
    return f"{proj} · 주소 좌표 ({addr_coord})"


def building(con, pnu: str) -> tuple[dict | None, str | None]:
    """건축물대장 표제부 요약 (feedback.md §5-1). 빌드 때 조회한 필지만 있다."""
    r = con.execute("SELECT payload FROM buildings WHERE pnu=?", (pnu,)).fetchone()
    if r is None:
        return None, BUILDING_NOT_FETCHED
    b = loads(r["payload"], {}) or {}
    if not b.get("found"):
        return None, b.get("note") or "이 지번에 건축물대장 표제부가 조회되지 않았습니다"
    return b | {"source": BUILDING_SOURCE, "fetched_label": f"{dot(b['fetched_at'])} 조회"}, None


def land_use_documented(con, included: list) -> dict | None:
    """고시에 적힌 용도지역 (사업 구역 기준). 토지 정보(브이월드) 아래 보조 줄로 보인다 (feedback2.md §3-4)."""
    for inc in included:
        p = con.execute("SELECT land_use, land_use_page, stage_source_doc_id FROM projects WHERE id=?",
                        (inc["project_id"],)).fetchone()
        if p and p["land_use"]:
            src = source(con, p["stage_source_doc_id"], p["land_use_page"])
            return {"value": p["land_use"],
                    "basis": f"고시 기재 ({src['doc_id']} p{p['land_use_page']}, 정비구역 기준)", "source": src}
    return None


def land_for(con, norm: dict, live) -> dict:
    """토지 정보: ① 빌드 캐시(seed/land_cache.json) ② 실시간(메모리 캐시 1시간 포함) ③ 없음 안내."""
    r = con.execute("SELECT payload FROM land_cache WHERE pnu=?", (norm["pnu"],)).fetchone()
    if r:
        return dict(loads(r["payload"], {}) or {}, from_cache=True, cache="build")
    if live is not None:
        land = live.get_land(norm["pnu"], norm["jibun_address"] or jibun_text(con, norm["pnu"]))
        return dict(land, cache="memory" if land.get("from_cache") else None)
    return {"status": "unavailable", "pnu": norm["pnu"], "zones": [], "missing": [], "location": None,
            "official_price": None, "from_cache": False, "cache": None, "found": None, "source": None,
            "fetched_at": None, "note": LAND_OFFLINE_NOTE}


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


NORM_KEYS = ("addr_id", "road_address", "jibun_address", "pnu", "bjd_code", "sgg_code", "dong_name", "saenghwal",
             "lat", "lon", "coord_source", "match_via")


def lookup(con, text: str, decisions=None, today=None, live=None) -> dict:
    """live: 실시간 조회 객체(core.live.Live). None이면 네트워크 없이 시연 주소·지번·빌드 캐시만 쓴다."""
    today = today or today_kst()
    m = meta(con)
    ov = review_mod.apply(con, decisions)
    norm = normalize(con, text, search=live.search if live is not None else None)
    normalized = {k: norm[k] for k in NORM_KEYS}
    resp = {"query": text, "status": norm["status"], "message": norm["message"], "normalized": normalized,
            "candidates": norm.get("candidates"),
            "as_of": m.get("as_of"), "layers": None, "reference": None, "review_applied": ov.review_applied,
            "events": ov.events, "coverage_note": m.get("coverage_note"), "disclaimer": DISCLAIMER}
    if norm["status"] != "ok":
        return resp

    land = land_for(con, norm, live)
    loc = land.get("location")
    if loc:                               # 좌표는 토지 정보(지오코더)를 쓰고, 주변 500m 판정을 모든 주소에 적용
        norm.update(lat=loc["lat"], lon=loc["lon"], coord_source=loc["source"])
        normalized.update(lat=loc["lat"], lon=loc["lon"], coord_source=loc["source"])
    if not normalized["jibun_address"]:
        normalized["jibun_address"] = jibun_text(con, norm["pnu"])
    items = load_items(con, ov, today)
    placed, reference = place_items(items, norm)
    included, nearby, nearby_note = parcel_projects(con, norm, ov)
    shown = {p["project_id"] for p in included} | {p["project_id"] for p in nearby}
    dprojects, ddeadlines = dong_projects(con, norm, shown, today)
    bld, bld_note = building(con, norm["pnu"])
    resp["layers"] = {
        "city": placed["city"],
        "gu": {"items": placed["gu"], "projects_by_stage": projects_by_stage(con, norm["sgg_code"])},
        "dong": {"items": placed["dong"], "projects": dprojects, "deadlines": ddeadlines,
                 "empty_note": None if (placed["dong"] or dprojects) else
                 f"{norm['dong_name'] or '이 법정동'}에 대해 확인된 고시가 없습니다 (프리토타입에 모은 문서 기준)"},
        "parcel": {"items": placed["parcel"], "land": land,
                   "land_use_documented": land_use_documented(con, included),
                   "building": bld, "building_note": bld_note,
                   "included_projects": included, "nearby_projects": nearby, "nearby_note": nearby_note,
                   "no_project_message": None if included else
                   f"{(m.get('as_of') or '').replace('-', '.')}까지 확인된 고시 기준, 진행 중인 사업이 없습니다"},
    }
    resp["reference"] = {"items": reference, "note": REFERENCE_NOTE}
    return resp


def parcel_summary(con, pnu: str) -> dict:
    """GET /parcels/{pnu}/projects 응답."""
    row = con.execute("SELECT * FROM demo_addresses WHERE pnu=? AND in_scope=1 LIMIT 1", (pnu,)).fetchone()
    b = con.execute("SELECT bjd_code, sgg_code, saenghwal FROM bjd_codes WHERE bjd_code=?", (pnu[:10],)).fetchone()
    norm = {"pnu": pnu, "bjd_code": pnu[:10], "sgg_code": b["sgg_code"] if b else pnu[:5],
            "saenghwal": b["saenghwal"] if b else None,
            "lat": row["lat"] if row else None, "lon": row["lon"] if row else None,
            "coord_source": row["coord_source"] if row else None}
    included, nearby, note = parcel_projects(con, norm, review_mod.Overrides())
    out = []
    for p in included + nearby:
        out.append({"project_id": p["project_id"], "name": p["name"], "inclusion": p["inclusion"],
                    "inclusion_label": p["inclusion_label"], "basis": p.get("basis"),
                    "distance_m": p.get("distance_m"), "evidence_source": p["source"]})
    return {"pnu": pnu, "projects": out, "nearby_note": note}
