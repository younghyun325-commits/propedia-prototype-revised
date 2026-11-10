"""평가 (agents.md §13, feedback.md §6-2, feedback2.md §8-2). 정답셋과 비교해 지표를 계산하고 evals/report.md 와
meta.eval_report 에 저장한다.

사용: python -m evals.run_eval          # 네트워크 없이 M1~M17, M19·M20
      python -m evals.run_eval --live   # M18(실시간 조회 성공률·p95)·M21(필지 클릭 조회)을 더 잰다 (외부 서비스 상태에 좌우됨)
- 층별 기대 항목(M6·M7)은 core/lookup.py 를 쓰지 않고 정답셋(addresses.yaml + scope_labels.yaml)으로 따로 배치해 만든다.
  P9부터 기대 집합 = tier 'applies' + 효력 중 + 층별 5개 상한 적용 후 (정렬: tier_class → rank → 문서 날짜 최신).
- 목표 미달이 있어도 종료 코드 0, 스크립트 오류는 1.
"""
import argparse
import hashlib
import json
import os
import math
import sqlite3
import sys
import time
import traceback
import warnings
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.address import normalize  # noqa: E402
from core.db import DB_PATH, connect_ro, meta  # noqa: E402
from core.lookup import lookup  # noqa: E402
from core.progress import progress  # noqa: E402
from core.text import norm  # noqa: E402

GOLD = ROOT / "evals" / "goldset"
LAYERS = ["city", "gu", "dong", "parcel"]
LAYER_KO = {"city": "서울 전역", "gu": "자치구", "dong": "법정동", "parcel": "필지"}
BANNED = ["예상", "예정", "전망", "지연", "늦", "위험", "안전", "유망", "호재", "추천", "수익", "투자", "확실", "보장",
          "반드시", "가능성 높"]
ALLOW = ["정비예정구역"]
SKIP_KEYS = {"evidence", "how_to_submit", "places", "source_note", "payload", "text", "evidences", "query",
             # 브이월드 원 자료 값 (예: '비행안전제2구역') — 원문 인용과 같이 검사하지 않는다
             "zones", "jimok", "land_use_zone", "land_use_zone2", "use_situation", "road_side", "terrain"}
TIMING_ROUNDS = 20
LAYER_CAP = 5                      # feedback.md §3-3: 서울 전역·자치구·법정동 층별 상한
CAPPED = ("city", "gu", "dong")
CLASS_ORDER = {"a": 0, "b": 1, "c": 2}
BUILDING_NOT_FOUND = "조회되지 않았습니다"


def sha8(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def load_yaml(name: str) -> dict:
    return yaml.safe_load((GOLD / name).read_text(encoding="utf-8")) or {}


def tnorm(s) -> str:
    return norm(str(s)).replace("「", "").replace("」", "")


def pct(n, d) -> float | None:
    return None if d == 0 else n / d


def disp(n, d) -> str:
    return "—" if d == 0 else f"{n / d:.0%} ({n}/{d})"


def gold_in_force(lab: dict, today: date) -> bool:
    """정답 라벨의 효력 기간이 끝나지 않았는지 (기간이 없으면 효력 중으로 본다)."""
    end = lab.get("effective_to")
    return not end or today <= date.fromisoformat(str(end))


# ── 정답셋으로 따로 만드는 층별 기대값 ─────────────────────────
def expected_layers(addr: dict, labels: dict, doc_dates: dict, today: date) -> dict[str, set]:
    cand = {k: [] for k in LAYERS}
    for key, lab in labels.items():
        if lab.get("tier") != "applies" or not gold_in_force(lab, today):
            continue
        st, refs = lab["scope_type"], lab["scope_ref"]
        if st == "SIDO" and "11" in refs:
            cand["city"].append(key)
        elif st == "SGG" and addr["sgg_code"] in refs:
            cand["gu"].append(key)
        elif st == "BJD" and addr["bjd_code"] in refs:
            cand["dong"].append(key)
        elif st == "PARCEL" and addr["pnu"] in refs:
            cand["parcel"].append(key)
        # SAENGHWAL은 층에 두지 않는다 (feedback.md §4)
    exp = {}
    for k, keys in cand.items():
        keys.sort()
        keys.sort(key=lambda x: doc_dates.get(x.split("-")[0], ""), reverse=True)
        keys.sort(key=lambda x: (CLASS_ORDER.get(labels[x].get("tier_class"), 3), labels[x].get("rank") or 999))
        exp[k] = set(keys[:LAYER_CAP] if k in CAPPED else keys)
    for p in addr.get("projects", []):
        tag = f"project:{p['project_key']}"
        if p["inclusion"] in ("possible", "likely", "included", "nearby"):
            exp["parcel"].add(tag)
        elif p["inclusion"] == "same_dong":
            exp["dong"].add(tag)
    return exp


def returned_layers(resp: dict, keymap: dict) -> dict[str, set]:
    L = resp["layers"]
    ret = {
        "city": {i["item_key"] for i in L["city"]},
        "gu": {i["item_key"] for i in L["gu"]["items"]},
        "dong": {i["item_key"] for i in L["dong"]["items"]} |
                {f"project:{keymap[p['project_id']]}" for p in L["dong"]["projects"]},
        "parcel": {i["item_key"] for i in L["parcel"]["items"]} |
                  {f"project:{keymap[p['project_id']]}" for p in
                   L["parcel"]["included_projects"] + L["parcel"]["nearby_projects"]},
    }
    return ret


def response_inclusions(resp: dict, keymap: dict) -> dict[str, str]:
    out = {}
    if resp["status"] != "ok":
        return out
    L = resp["layers"]
    for p in L["parcel"]["included_projects"]:
        out[keymap[p["project_id"]]] = p["inclusion"]
    for p in L["parcel"]["nearby_projects"]:
        out[keymap[p["project_id"]]] = "nearby"
    for p in L["dong"]["projects"]:
        out.setdefault(keymap[p["project_id"]], "same_dong")
    return out


def field_match(spec: dict, value) -> bool:
    gold, how = spec["value"], spec["match"]
    if value is None:
        return gold is None
    if how == "text":
        return tnorm(value) in {tnorm(gold)} | {tnorm(a) for a in spec.get("accept", [])}
    if how == "number":
        try:
            return math.isclose(float(value), float(gold), rel_tol=0, abs_tol=1e-9)
        except (TypeError, ValueError):
            return False
    if how == "date":
        return str(value)[:10] == str(gold)[:10]
    if how == "set":
        if not isinstance(value, list):
            return False
        return {tnorm(x) for x in value} == {tnorm(x) for x in gold}
    raise ValueError(f"알 수 없는 match: {how}")


def banned_hits(text: str) -> list[str]:
    for a in ALLOW:
        text = text.replace(a, "")
    return [w for w in BANNED if w in text]


def walk_strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in SKIP_KEYS:
                yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)
    elif isinstance(obj, str):
        yield obj


def land_match(gold: dict, land: dict) -> list[tuple[str, bool]]:
    """land.yaml 정답과 토지 정보 비교: 지목·면적·용도지역·공시지가(원/㎡·기준연도)."""
    price, gp = land.get("official_price") or {}, gold.get("official_price") or {}
    area_ok = land.get("area_m2") is not None and math.isclose(float(land["area_m2"]), float(gold["area_m2"]),
                                                                 abs_tol=0.01)
    return [("지목", land.get("jimok") == gold["jimok"]), ("면적", area_ok),
            ("용도지역", land.get("land_use_zone") == gold["land_use_zone"]),
            ("공시지가", price.get("won_per_m2") == gp.get("won_per_m2") and price.get("year") == gp.get("year"))]


def evaluate(live: bool = False) -> dict:
    g_ext = load_yaml("extraction.yaml")
    g_addr = load_yaml("addresses.yaml")
    g_scope = load_yaml("scope_labels.yaml")
    g_land = load_yaml("land.yaml")
    gold_land = {x["addr_id"]: x for x in g_land.get("parcels", [])}
    labels = g_scope.get("labels", {})
    errors: list[dict] = []
    metrics: list[dict] = []

    con = connect_ro()
    m = meta(con)
    keymap = {r["id"]: r["project_key"] for r in con.execute("SELECT id, project_key FROM projects")}
    doc_dates = {r["doc_id"]: r["published_at"] or "" for r in con.execute("SELECT doc_id, published_at FROM documents")}
    today = datetime.now(timezone(timedelta(hours=9))).date()

    # M1 텍스트화 성공률
    sel, ok = con.execute("SELECT count(*), sum(char_count >= 30) FROM pages WHERE selected=1").fetchone()
    ok = ok or 0
    for r in con.execute("""SELECT d.doc_id, p.pdf_page FROM pages p JOIN documents d ON d.id=p.document_id
                            WHERE p.selected=1 AND p.char_count < 30"""):
        errors.append({"type": "extraction", "detail": f"{r['doc_id']} p{r['pdf_page']}: 텍스트 30자 미만"})
    metrics.append({"id": "M1", "name": "텍스트화 성공률", "value": pct(ok, sel), "display": disp(ok, sel),
                    "target": "≥ 95%", "pass": sel > 0 and ok / sel >= 0.95})

    # M2 근거 문장 일치율
    eok, etot = con.execute("SELECT sum(evidence_ok_count), sum(evidence_total) FROM extractions").fetchone()
    eok, etot = eok or 0, etot or 0
    for r in con.execute("SELECT ref_key, title FROM review_queue WHERE item_type='evidence_mismatch'"):
        errors.append({"type": "evidence", "detail": f"{r['ref_key']}: {r['title']}"})
    metrics.append({"id": "M2", "name": "근거 문장 일치율", "value": pct(eok, etot), "display": disp(eok, etot),
                    "target": "100%", "pass": etot > 0 and eok == etot,
                    "note": "항목 + D1 필드 + 사업 카드 근거"})

    # M3 D1 필드 정확도
    rows = {r["field"]: json.loads(r["value"]) if r["value"] is not None else None for r in con.execute(
        "SELECT f.field, f.value FROM extracted_fields f JOIN documents d ON d.id=f.document_id WHERE d.doc_id='D1'")}
    gf = g_ext.get("fields", {})
    hit = 0
    for name, spec in gf.items():
        if name in rows and field_match(spec, rows[name]):
            hit += 1
        else:
            errors.append({"type": "extraction",
                           "detail": f"D1 {name}: 정답 {spec['value']!r}, 추출 {rows.get(name, '(없음)')!r}"})
    metrics.append({"id": "M3", "name": "D1 필드 정확도", "value": pct(hit, len(gf)), "display": disp(hit, len(gf)),
                    "target": "≥ 90%", "pass": len(gf) > 0 and hit / len(gf) >= 0.9})

    # M4 적용 범위 정확도 (+ 층 분류 tier 일치는 참고로 note에)
    db_items = {r["item_key"]: (r["scope_type"], set(json.loads(r["scope_ref"])), r["tier"]) for r in
                con.execute("SELECT item_key, scope_type, scope_ref, tier FROM applicability_rules")}
    hit = tier_hit = 0
    for key, lab in labels.items():
        got = db_items.get(key)
        if got and got[0] == lab["scope_type"] and got[1] == set(lab["scope_ref"]):
            hit += 1
        else:
            errors.append({"type": "scope", "detail": f"{key}: 정답 {lab['scope_type']} {lab['scope_ref']}, "
                                                      f"응답 {got[0] + ' ' + str(sorted(got[1])) if got else '(항목 없음)'}"})
        if got and got[2] == lab.get("tier"):
            tier_hit += 1
        else:
            errors.append({"type": "scope", "detail": f"{key}: 층 분류 정답 {lab.get('tier')}, "
                                                      f"응답 {got[2] if got else '(항목 없음)'}"})
    for key in sorted(set(db_items) - set(labels)):
        errors.append({"type": "scope", "detail": f"{key}: 정답 라벨 없음"})
    metrics.append({"id": "M4", "name": "적용 범위 정확도", "value": pct(hit, len(labels)),
                    "display": disp(hit, len(labels)), "target": "≥ 95%",
                    "pass": len(labels) > 0 and hit / len(labels) >= 0.95,
                    "note": f"층 분류(적용/배경) 일치 {tier_hit}/{len(labels)}"})

    # M5 주소 정규화, M6·M7 층별, M8 포함 판정, M9 원문 링크
    addresses = g_addr.get("addresses", [])
    n_ok = 0
    layer_exp = {k: 0 for k in LAYERS}
    layer_ret = {k: 0 for k in LAYERS}
    layer_hit = {k: 0 for k in LAYERS}
    pair_ok = pair_n = 0
    img_ok = img_n = 0
    cap_ok = cap_n = 0                 # M13
    reg_ok = reg_n = 0                 # M14
    bld_ok = bld_n = bld_found = 0     # M15
    land_ok = land_n = 0               # M16
    lf_ok = lf_n = 0                   # M17
    addr_rows = []
    responses = []
    for a in addresses:
        n = normalize(con, a["input"])
        row = {"addr_id": a["addr_id"], "input": a["input"], "status_ok": n["status"] == a["status"],
               "pnu_ok": None, "layer_hits": {}, "inclusion_ok": None, "regulations": None, "building": None,
               "land": None}
        good = row["status_ok"]
        if a["status"] == "ok":
            row["pnu_ok"] = n["pnu"] == a["pnu"]
            good = good and row["pnu_ok"] and n["bjd_code"] == a["bjd_code"] and n["saenghwal"] == a["saenghwal"]
        if not good:
            errors.append({"type": "normalize", "detail": f"{a['addr_id']} '{a['input']}': 정답 {a['status']} "
                                                          f"{a.get('pnu', '')} {a.get('saenghwal', '')}, 응답 {n['status']} "
                                                          f"{n['pnu'] or ''} {n['saenghwal'] or ''}"})
        n_ok += good
        if a["status"] == "ok" and n["status"] == "ok":
            resp = lookup(con, a["input"])
            responses.append(resp)
            exp = expected_layers(a, labels, doc_dates, today)
            ret = returned_layers(resp, keymap)
            L = resp["layers"]
            # M13 층별 상한
            sizes = {"city": len(L["city"]), "gu": len(L["gu"]["items"]), "dong": len(L["dong"]["items"])}
            cap_n += 1
            if all(v <= LAYER_CAP for v in sizes.values()):
                cap_ok += 1
            else:
                errors.append({"type": "other", "detail": f"{a['addr_id']} 층별 상한 초과: {sizes}"})
            # M14 효력 중 고시 표시
            got_by_layer = {"city": {i["item_key"] for i in L["city"]}, "gu": {i["item_key"] for i in L["gu"]["items"]},
                            "dong": {i["item_key"] for i in L["dong"]["items"]},
                            "parcel": {i["item_key"] for i in L["parcel"]["items"]}}
            r_hit = r_tot = 0
            for layer, keys in (a.get("expect_regulations") or {}).items():
                for key in keys:
                    r_tot += 1
                    if key in got_by_layer.get(layer, set()):
                        r_hit += 1
                    else:
                        errors.append({"type": "scope", "detail": f"{a['addr_id']} {LAYER_KO[layer]}: 효력 중 고시 {key} 없음"})
            reg_ok += r_hit
            reg_n += r_tot
            row["regulations"] = f"{r_hit}/{r_tot}" if r_tot else None
            # M16 토지 정보 확보 (빌드 캐시, 네트워크 없음) · M17 토지 정보 정확도
            land = L["parcel"]["land"]
            land_n += 1
            land_ok += land["status"] in ("ok", "partial")
            row["land"] = land["status"]
            gl = gold_land.get(a["addr_id"]) or next((x for x in gold_land.values() if x["pnu"] == a.get("pnu")), None)
            if gl:
                for fname, okf in land_match(gl, land):
                    lf_n += 1
                    lf_ok += okf
                    if not okf:
                        errors.append({"type": "extraction", "detail": f"{a['addr_id']} 토지 정보 {fname} 정답과 다름"})
            # M15 건축물 정보 처리
            P = L["parcel"]
            bld_n += 1
            if P.get("building"):
                bld_ok += 1
                bld_found += 1
                row["building"] = "있음"
            elif BUILDING_NOT_FOUND in (P.get("building_note") or ""):
                bld_ok += 1
                row["building"] = "미조회 안내"
            else:
                row["building"] = "처리 안 됨"
                errors.append({"type": "other", "detail": f"{a['addr_id']} 건축물: {P.get('building_note')}"})
            for k in LAYERS:
                h = len(exp[k] & ret[k])
                layer_exp[k] += len(exp[k])
                layer_ret[k] += len(ret[k])
                layer_hit[k] += h
                row["layer_hits"][k] = f"{h}/{len(exp[k])}" + (f" (+{len(ret[k] - exp[k])})" if ret[k] - exp[k] else "")
                for miss in sorted(exp[k] - ret[k]):
                    errors.append({"type": "scope", "detail": f"{a['addr_id']} {LAYER_KO[k]}: 기대 {miss} 누락"})
                for extra in sorted(ret[k] - exp[k]):
                    errors.append({"type": "scope", "detail": f"{a['addr_id']} {LAYER_KO[k]}: 기대 밖 {extra}"})
            gold_inc = {p["project_key"]: p["inclusion"] for p in a.get("projects", [])}
            got_inc = response_inclusions(resp, keymap)
            keys = set(gold_inc) | set(got_inc)
            this_ok = True
            for key in keys:
                pair_n += 1
                if gold_inc.get(key) == got_inc.get(key):
                    pair_ok += 1
                else:
                    this_ok = False
                    errors.append({"type": "inclusion", "detail": f"{a['addr_id']} {key}: 정답 {gold_inc.get(key)}, "
                                                                  f"응답 {got_inc.get(key)}"})
            row["inclusion_ok"] = this_ok if keys else None
            for it in L["city"] + L["gu"]["items"] + L["dong"]["items"] + L["parcel"]["items"] + \
                    resp["reference"]["items"]:
                img_n += 1
                pi = (it.get("source") or {}).get("page_image")
                if pi and (ROOT / "public" / pi.lstrip("/")).exists():
                    img_ok += 1
                else:
                    errors.append({"type": "evidence", "detail": f"{a['addr_id']} {it['item_key']}: 원문 쪽 이미지 없음"})
        addr_rows.append(row)
    metrics.append({"id": "M5", "name": "주소 정규화 정확도", "value": pct(n_ok, len(addresses)),
                    "display": disp(n_ok, len(addresses)), "target": "100%",
                    "pass": len(addresses) > 0 and n_ok == len(addresses),
                    "note": f"정답셋 제외: {', '.join(g_addr.get('excluded', [])) or '없음'}"})
    layer_rows = [{"layer": k, "recall": pct(layer_hit[k], layer_exp[k]), "precision": pct(layer_hit[k], layer_ret[k]),
                   "expected": layer_exp[k], "returned": layer_ret[k]} for k in LAYERS]
    rec_ok = all(r["recall"] is None or r["recall"] >= 0.9 for r in layer_rows)
    pre_ok = all(r["precision"] is None or r["precision"] >= 0.95 for r in layer_rows)
    fmt = lambda v: "—" if v is None else f"{v:.0%}"  # noqa: E731
    metrics.append({"id": "M6", "name": "층별 재현율", "value": min((r["recall"] for r in layer_rows
                                                                   if r["recall"] is not None), default=None),
                    "display": " / ".join(f"{LAYER_KO[r['layer']]} {fmt(r['recall'])}" for r in layer_rows),
                    "target": "층마다 ≥ 90%", "pass": rec_ok})
    metrics.append({"id": "M7", "name": "층별 정밀도", "value": min((r["precision"] for r in layer_rows
                                                                   if r["precision"] is not None), default=None),
                    "display": " / ".join(f"{LAYER_KO[r['layer']]} {fmt(r['precision'])}" for r in layer_rows),
                    "target": "층마다 ≥ 95%", "pass": pre_ok})
    metrics.append({"id": "M8", "name": "포함 판정 정확도", "value": pct(pair_ok, pair_n), "display": disp(pair_ok, pair_n),
                    "target": "100%", "pass": pair_n > 0 and pair_ok == pair_n,
                    "note": f"주변(500m) 판정 쌍 {sum(p['inclusion'] == 'nearby' for a in addresses for p in a.get('projects', []))}개 "
                            "— 사업 중심은 인접 필지 좌표 근사"})
    metrics.append({"id": "M9", "name": "원문 링크 유효율", "value": pct(img_ok, img_n), "display": disp(img_ok, img_n),
                    "target": "100%", "pass": img_n > 0 and img_ok == img_n, "note": "4개 층 + 참고 섹션 항목"})

    # M11 금지어 (우리가 만든 문장)
    hits = []
    for r in con.execute("SELECT item_key, title, summary, target_note, tier_reason FROM applicability_rules"):
        text = " ".join(x or "" for x in (r["title"], r["summary"], r["target_note"], r["tier_reason"]))
        hits += [f"{r['item_key']}: {w}" for w in banned_hits(text)]
    for r in con.execute("SELECT label FROM related_history"):
        hits += [f"관련 이력: {w}" for w in banned_hits(r["label"])]
    for r in con.execute("SELECT title, reason FROM review_queue"):
        hits += [f"검수 큐: {w}" for w in banned_hits(r["title"] + " " + r["reason"])]
    hits += [f"coverage_note: {w}" for w in banned_hits(m.get("coverage_note", ""))]
    for f in list((ROOT / "public").glob("*.html")) + list((ROOT / "public" / "assets").glob("*.js")):
        hits += [f"{f.name}: {w}" for w in banned_hits(f.read_text(encoding="utf-8"))]
    extra = [lookup(con, t) for t in ("", "강남구 없는동 1", "서초구 방배동 818-14")]
    for resp in responses + extra + [progress(con, pid) for pid in keymap]:
        for s in walk_strings(resp):
            hits += [f"API 문구: {w} ({s[:30]})" for w in banned_hits(s)]
    for h in hits:
        errors.append({"type": "other", "detail": f"금지어 {h}"})
    metrics.append({"id": "M11", "name": "금지어", "value": len(hits), "display": f"{len(hits)}개", "target": "0",
                    "pass": len(hits) == 0})

    # M12 단계 판정
    stages = {r["project_key"]: r["sub_stage_code"] for r in con.execute("SELECT project_key, sub_stage_code FROM projects")}
    # 한양7차는 정답셋(extraction.yaml stage), 모아타운은 승인 고시를 확인하기 전까지 MT01 (feedback2.md §11)
    gold_stages = {"apgujeong-6-1-hanyang7": g_ext.get("stage"), "ilwon-daecheong-north-moatown": "MT01"}
    stage_ok = all(stages.get(k) == v for k, v in gold_stages.items())
    for k, v in gold_stages.items():
        if stages.get(k) != v:
            errors.append({"type": "other", "detail": f"단계 {k}: 정답 {v}, 응답 {stages.get(k)}"})
    metrics.append({"id": "M12", "name": "단계 판정", "value": stage_ok,
                    "display": " / ".join(f"{stages.get(k)} (정답 {v})" for k, v in gold_stages.items()),
                    "target": "일치", "pass": stage_ok})

    # M13~M15 (feedback.md §6-2)
    metrics.append({"id": "M13", "name": "층별 상한 준수", "value": pct(cap_ok, cap_n), "display": disp(cap_ok, cap_n),
                    "target": "100%", "pass": cap_n > 0 and cap_ok == cap_n,
                    "note": f"서울 전역·자치구·법정동 층 항목 {LAYER_CAP}개 이하인 주소 비율"})
    metrics.append({"id": "M14", "name": "효력 중 고시 표시", "value": pct(reg_ok, reg_n), "display": disp(reg_ok, reg_n),
                    "target": "100%", "pass": reg_n > 0 and reg_ok == reg_n,
                    "note": "정답셋 expect_regulations의 고시가 해당 층에 나온 비율"})
    metrics.append({"id": "M15", "name": "건축물 정보 처리율", "value": pct(bld_ok, bld_n), "display": disp(bld_ok, bld_n),
                    "target": "100%", "pass": bld_n > 0 and bld_ok == bld_n,
                    "note": f"건축물대장 표제부가 조회된 주소(참고 값) {disp(bld_found, bld_n)}"})
    # M16·M17 (feedback2.md §8-2)
    metrics.append({"id": "M16", "name": "토지 정보 확보율 (캐시)", "value": pct(land_ok, land_n),
                    "display": disp(land_ok, land_n), "target": "100%", "pass": land_n > 0 and land_ok == land_n,
                    "note": "범위 안 시연 주소 중 토지 정보 status가 ok·partial인 비율 (빌드 캐시, 네트워크 없음)"})
    metrics.append({"id": "M17", "name": "토지 정보 정확도", "value": pct(lf_ok, lf_n), "display": disp(lf_ok, lf_n),
                    "target": "≥ 95%", "pass": lf_n > 0 and lf_ok / lf_n >= 0.95,
                    "note": "land.yaml 정답과 지목·면적·용도지역·공시지가 일치 (정답셋은 fetch_land 결과 초안 — 토지이음 대조 전)"})
    demo_inputs = [r["input_text"] for r in con.execute("SELECT input_text FROM demo_addresses") if r["input_text"]]
    con.close()

    # M10 응답 시간 p95 (TestClient, 주소 × 20회)
    warnings.filterwarnings("ignore", message="Using .httpx. with .starlette.testclient.")
    from fastapi.testclient import TestClient
    from api.index import app
    client = TestClient(app)
    times = []
    for _ in range(TIMING_ROUNDS):
        for t in demo_inputs:
            t0 = time.perf_counter()
            r = client.get("/api/v1/lookup", params={"address": t})
            times.append((time.perf_counter() - t0) * 1000)
            if r.status_code != 200:
                errors.append({"type": "other", "detail": f"lookup HTTP {r.status_code} ({t})"})
    times.sort()
    p95 = times[max(0, math.ceil(len(times) * 0.95) - 1)] if times else None
    metrics.insert(9, {"id": "M10", "name": "응답 시간 p95", "value": p95,
                       "display": f"{p95:.0f}ms" if p95 is not None else "—", "target": "≤ 3000ms",
                       "pass": p95 is not None and p95 <= 3000,
                       "note": f"시연 주소 {len(demo_inputs)}건 × {TIMING_ROUNDS}회 = {len(times)}회 (로컬 TestClient)"})

    # M18 실시간 조회 (--live): 시연 목록 밖 강남구 도로명주소 → 도로명 검색·토지 정보 실시간
    live_rows, parcel_rows = [], []
    if live:
        from core import live as live_mod
        g_live = load_yaml("live_addresses.yaml")
        con = connect_ro()
        lt, ok_n = [], 0
        for x in g_live.get("addresses", []):
            t0 = time.perf_counter()
            r = lookup(con, x["input"], live=live_mod.Live())
            ms = (time.perf_counter() - t0) * 1000
            lt.append(ms)
            good = r["status"] == "ok" and r["layers"]["parcel"]["land"]["status"] in ("ok", "partial")
            ok_n += good
            live_rows.append({"input": x["input"], "status": r["status"],
                              "land": r["layers"]["parcel"]["land"]["status"] if r["layers"] else None,
                              "pnu_ok": (r["normalized"].get("pnu") == x.get("pnu")) if r["status"] == "ok" else None,
                              "via": r["normalized"].get("match_via"), "ms": round(ms)})
            if not good:
                errors.append({"type": "other", "detail": f"실시간 {x['input']}: {r['status']} "
                                                          f"{r.get('message') or ''}"})
        con.close()
        lt.sort()
        lp95 = lt[max(0, math.ceil(len(lt) * 0.95) - 1)] if lt else None
        n = len(lt)
        metrics.append({"id": "M18", "name": "실시간 조회 성공률", "value": pct(ok_n, n),
                        "display": f"{disp(ok_n, n)} · p95 {lp95:.0f}ms" if lp95 is not None else "—",
                        "target": "≥ 90%, p95 ≤ 3000ms",
                        "pass": n > 0 and ok_n / n >= 0.9 and lp95 is not None and lp95 <= 3000,
                        "note": "실시간 항목은 실행 시점의 외부 서비스(도로명주소·브이월드) 상태에 좌우됨"})

        # M21 필지 클릭 조회 (--live, P15): 지번 5건의 필지 경계 중심점 → /map/parcel-at과 같은 조립 → PNU 일치, p95
        from core import map as map_mod
        g_parcels = load_yaml("live_parcels.yaml")
        con = connect_ro()
        ct, c_ok = [], 0
        for x in g_parcels.get("parcels", []):
            t0 = time.perf_counter()
            r = map_mod.parcel_at(con, x["lat"], x["lon"], live_mod.Live())
            ms = (time.perf_counter() - t0) * 1000
            ct.append(ms)
            good = r["status"] == "ok" and r["pnu"] == x["pnu"]
            c_ok += good
            parcel_rows.append({"label": x["label"], "pnu": x["pnu"], "got": r["pnu"], "status": r["status"],
                                "land": (r["land"] or {}).get("status"), "ms": round(ms)})
            if not good:
                errors.append({"type": "other", "detail": f"필지 클릭 {x['label']}: {r['status']} {r['pnu']} "
                                                          f"{r.get('message') or ''}"})
        con.close()
        ct.sort()
        cp95 = ct[max(0, math.ceil(len(ct) * 0.95) - 1)] if ct else None
        n = len(ct)
        metrics.append({"id": "M21", "name": "필지 클릭 조회", "value": pct(c_ok, n),
                        "display": f"{disp(c_ok, n)} · p95 {cp95:.0f}ms" if cp95 is not None else "—",
                        "target": "PNU 100%, p95 ≤ 2000ms",
                        "pass": n > 0 and c_ok == n and cp95 is not None and cp95 <= 2000,
                        "note": "지번 5건의 연속지적도 경계 중심점(evals/goldset/live_parcels.yaml)에서 실시간 조회"})

    # M19·M20 지도 경계·레이어 (docs/map/PLAN.md P13)
    g_bnd = load_yaml("boundaries.yaml")
    metrics += map_metrics(g_bnd, errors)
    # M22·M23 실거래 단지 (docs/map/PLAN.md P17)
    mk_metrics, market = market_metrics(errors)
    metrics += mk_metrics
    # M24 생활 인프라 건수 일치 (docs/map/PLAN.md P18)
    inf_metrics, infra = infra_metrics(errors)
    metrics += inf_metrics

    drafts = [g_ext.get("draft"), g_addr.get("draft"), g_scope.get("draft"), g_land.get("draft"), g_bnd.get("draft")]
    return {
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "build_at": m.get("build_at"),
        "goldset": {"draft": any(d is not False for d in drafts),
                    "files": {"extraction": sha8(GOLD / "extraction.yaml"), "addresses": sha8(GOLD / "addresses.yaml"),
                              "scope_labels": sha8(GOLD / "scope_labels.yaml"), "land": sha8(GOLD / "land.yaml"),
                              "live_addresses": sha8(GOLD / "live_addresses.yaml"),
                              "boundaries": sha8(GOLD / "boundaries.yaml"),
                              "live_parcels": sha8(GOLD / "live_parcels.yaml")}},
        "live": live,
        "live_rows": live_rows,
        "parcel_rows": parcel_rows,
        "metrics": sorted(metrics, key=lambda x: int(x["id"][1:])),
        "layers": layer_rows,
        "addresses": addr_rows,
        "excluded_addresses": g_addr.get("excluded", []),
        "market": market,
        "infra": infra,
        "errors": errors,
    }


LAYER_DIR = ROOT / "public" / "data" / "layers"
BOUNDARY_DIR = ROOT / "seed" / "boundaries"
COMMON_PROPS = ("id", "kind", "name", "basis", "verified", "doc_ids", "source_page", "as_of", "area_m2_geom")
KIND_PROPS = {"project": ("stage_code", "stage_label", "area_m2_doc", "align_score"),
              "impact": ("project_id", "buffer_m", "note"),
              "parcel": ("pnu", "jibun", "inclusion"),
              "regulation": ("area_m2_doc", "align_score", "effective_from", "effective_to")}
BBOX_PAD_M = 600       # 영향권 500m가 구 경계를 조금 넘을 수 있어 여유


def map_metrics(g_bnd: dict, errors: list) -> list[dict]:
    """M19 경계 면적 일치, M20 GeoJSON 유효성. shapely·pyproj는 빌드 의존성 (평가는 빌드 PC에서 돈다)."""
    from pyproj import Transformer
    import shapely
    from shapely.geometry import shape
    tr = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
    tol = g_bnd.get("tolerance_pct", 5) / 100
    rows, skipped = [], []
    for b in g_bnd.get("boundaries", []):
        path = BOUNDARY_DIR / f"{b['doc_id']}.geojson"
        if not path.exists():
            skipped.append(b["doc_id"])
            continue
        f = json.loads(path.read_text(encoding="utf-8"))["features"][0]
        area = shapely.transform(shape(f["geometry"]), lambda x, y: tr.transform(x, y), interleaved=False).area
        diff = area / b["area_m2"] - 1
        rows.append((b["doc_id"], diff))
        if abs(diff) > tol:
            errors.append({"type": "boundary", "detail": f"{b['doc_id']} 경계 면적 {area:,.1f}㎡ / 고시 {b['area_m2']:,.1f}㎡ "
                                                          f"= {diff * 100:+.2f}%"})
    ok = sum(abs(d) <= tol for _, d in rows)
    detail = ", ".join(f"{d} {v * 100:+.2f}%" for d, v in rows)
    if skipped:
        detail += " · 대상 아님(경계 미채택): " + ", ".join(skipped)
    out = [{"id": "M19", "name": "경계 면적 일치", "value": pct(ok, len(rows)), "display": f"{disp(ok, len(rows))} — {detail}",
            "target": f"고시 면적 ±{tol:.0%}", "pass": bool(rows) and ok == len(rows),
            "note": "도면 정합으로 만든 경계만 셈 (evals/goldset/boundaries.yaml)"}]

    gb = json.loads((ROOT / "public" / "data" / "base" / "gangnam.geojson").read_text(encoding="utf-8"))
    x0, y0, x1, y1 = shape(gb["features"][0]["geometry"]).bounds
    lat0 = (y0 + y1) / 2
    dx, dy = BBOX_PAD_M / (111320 * math.cos(math.radians(lat0))), BBOX_PAD_M / 110540
    n = good = 0
    for path in sorted(LAYER_DIR.glob("propedia_*.geojson")):
        for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
            n += 1
            g = shape(f["geometry"])
            p = f["properties"]
            need = COMMON_PROPS + KIND_PROPS.get(p.get("kind"), ())
            lack = [k for k in need if k not in p]
            bx = g.bounds
            inside = bx[0] >= x0 - dx and bx[1] >= y0 - dy and bx[2] <= x1 + dx and bx[3] <= y1 + dy
            if g.is_valid and inside and not lack:
                good += 1
            else:
                errors.append({"type": "geojson", "detail": f"{path.name} {p.get('id')}: valid={g.is_valid} "
                                                            f"강남구 범위 안={inside} 빠진 속성={lack}"})
    out.append({"id": "M20", "name": "GeoJSON 유효성", "value": pct(good, n), "display": disp(good, n), "target": "100%",
                "pass": n > 0 and good == n,
                "note": "public/data/layers 도형마다 is_valid · 강남구 경계 bbox(+600m) 안 · 필수 속성 보유"})
    return out


APT_SEED = ROOT / "seed" / "apartments.geojson"
MARKET_DB = ROOT / "db" / "market.db"
APT_UNMATCHED = ROOT / "build" / "apartments_unmatched.csv"


def market_metrics(errors: list) -> tuple[list[dict], dict | None]:
    """M22 단지 위치 매칭률 = 필지 경계를 찾은 실거래 단지 ÷ 실거래 단지 (seed/apartments.geojson)
    M23 거래 연결률 = 위치가 있는 단지에 연결된 거래 ÷ 강남구 아파트 거래 (db/market.db apt_trades, 해제 포함)
    참고(목표 없음): 기본 정보가 연결된 단지 수 / 단지 목록 수. 자료가 없으면 '자료 없음'(미달 아님 표시)."""
    if not APT_SEED.exists() or not MARKET_DB.exists():
        none = {"value": None, "display": "자료 없음 (pipeline.build_trade_complexes·build_market_db 실행 전)", "pass": False}
        return [{"id": "M22", "name": "단지 위치 매칭률", "target": "≥ 90%", **none},
                {"id": "M23", "name": "거래 연결률", "target": "≥ 95%", **none}], None
    feats = json.loads(APT_SEED.read_text(encoding="utf-8"))["features"]
    located = {f["properties"]["id"] for f in feats if f.get("geometry")}
    reasons = {}
    if APT_UNMATCHED.exists():
        import csv
        with open(APT_UNMATCHED, encoding="utf-8-sig", newline="") as fh:
            reasons = {r["id"]: r["reason"] for r in csv.DictReader(fh)}
    unmatched = Counter(reasons.get(f["properties"]["id"]) or ("PNU 없음" if not f["properties"]["pnus"] else "필지 없음")
                        for f in feats if not f.get("geometry"))
    con = sqlite3.connect(MARKET_DB.as_uri() + "?mode=ro", uri=True)
    try:
        total = con.execute("SELECT COUNT(*) FROM apt_trades").fetchone()[0]
        rows = con.execute("SELECT complex_id, COUNT(*) FROM apt_trades GROUP BY complex_id").fetchall()
        mm = dict(con.execute("SELECT key, value FROM meta").fetchall())
        linked = con.execute("SELECT COUNT(*) FROM apt_complexes WHERE basis_info_status='linked'").fetchone()[0]
    finally:
        con.close()
    ok = sum(n for cid, n in rows if cid in located)
    unlinked = Counter()
    for cid, n in rows:
        if cid is None:
            unlinked["단지에 연결 못 함"] += n
        elif cid not in located:
            unlinked["연결된 단지의 위치 없음 (필지 경계 못 찾음)"] += n
    missing = [f"{f['properties']['id']} {f['properties']['name']} ({', '.join(f['properties']['pnus']) or 'PNU 없음'})"
               for f in feats if not f.get("geometry")]
    lt = mm.get("list_total")
    basis = (f"{linked} / {lt}" if lt else f"{linked}") + (" (기본 정보 API 미등록으로 건너뜀)"
                                                           if mm.get("basis_info_check") == "not_registered" else "")
    out = [{"id": "M22", "name": "단지 위치 매칭률", "value": pct(len(located), len(feats)),
            "display": disp(len(located), len(feats)), "target": "≥ 90%",
            "pass": bool(feats) and len(located) / len(feats) >= 0.9,
            "note": "필지 경계를 찾은 실거래 단지 ÷ 실거래 단지 (aptSeq·PNU 기준)"},
           {"id": "M23", "name": "거래 연결률", "value": pct(ok, total), "display": disp(ok, total), "target": "≥ 95%",
            "pass": total > 0 and ok / total >= 0.95,
            "note": f"위치가 있는 단지에 연결된 거래 ÷ 강남구 아파트 거래(해제 포함) · 참고: 기본 정보 연결 단지 {basis}"}]
    market = {"complexes": len(feats), "located": len(located), "trades": total, "trades_linked_located": ok,
              "unmatched_reasons": dict(unmatched.most_common()), "unlinked_reasons": dict(unlinked.most_common()),
              "basis_linked": linked, "list_total": int(lt) if lt else None, "basis_check": mm.get("basis_info_check"),
              "unmatched": missing}
    return out, market


INFRA_RAW = ROOT / "data_raw" / "12.생활인프라"
POIS_RAW = ROOT / "build" / "pois_raw"


def _csv_rows(path: Path) -> list[dict] | None:
    import csv
    if not path.exists():
        return None
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return list(csv.DictReader(raw.decode(enc).splitlines()))
        except UnicodeDecodeError:
            continue
    return None


def _pct_s(n: int, d: int) -> str:
    return f"{n / d * 100:.1f}%" if d else "—"


def infra_metrics(errors: list) -> tuple[list[dict], dict | None]:
    """M24 생활 인프라 건수 일치 = 레이어 건수 ÷ (원자료 강남구 건수 − 사유가 기록된 제외 건수), 원천 4종 각각 100%.
    원자료 건수는 여기서 원본(data_raw/12.생활인프라 CSV, build/pois_raw 상가 응답)으로 따로 센다. 제외 사유·건수는 manifest.
    참고(목표 없음): 버스 노선 연결률 2가지 (노선-정류장 행 중 서울 정류장 마스터에 있는 정류장, 노선이 연결된 강남구 정류장)."""
    man = (json.loads((LAYER_DIR / "manifest.json").read_text(encoding="utf-8")).get("layers") or {}) if (LAYER_DIR / "manifest.json").exists() else {}
    if not all(k in man for k in ("schools", "stations", "bus_stops", "pois")):
        return [{"id": "M24", "name": "생활 인프라 건수 일치", "value": None, "display": "레이어 없음", "target": "원천 4종 100%",
                 "pass": False, "note": "pipeline.fetch_pois 실행 전"}], None
    from pyproj import Transformer
    from shapely.geometry import Point, shape
    from shapely.prepared import prep
    t = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
    gfc = json.loads((ROOT / "public" / "data" / "base" / "gangnam.geojson").read_text(encoding="utf-8"))
    gg = shape(gfc["features"][0]["geometry"])
    import shapely
    g5 = shapely.transform(gg, lambda x, y: t.transform(x, y), interleaved=False)
    bufs = {m: prep(g5.buffer(m)) for m in (100, 500)}

    def near(lon, lat, m) -> bool:
        try:
            lon, lat = float(lon), float(lat)
        except (TypeError, ValueError):
            return False
        return lon != 0 and lat != 0 and bufs[m].covers(Point(*t.transform(lon, lat)))

    def layer_count(name: str) -> int:
        e = man[name]
        files = [c["file"] for c in e.get("categories") or [] if c.get("file")] or [e["file"]]
        return sum(len(json.loads((LAYER_DIR / f).read_text(encoding="utf-8"))["features"]) for f in files)

    rows = []
    school = _csv_rows(INFRA_RAW / "학교" / "전국초중등학교위치표준데이터.csv")
    rows.append(("학교", "schools", None if school is None else
                 sum(1 for r in school if "서울특별시 강남구" in (r.get("소재지도로명주소", "") + r.get("소재지지번주소", ""))), "학교 (강남구 주소)"))
    st = _csv_rows(INFRA_RAW / "지하철역" / "서울시 역사마스터 정보.csv")
    rows.append(("지하철역", "stations", None if st is None else sum(1 for r in st if near(r["경도"], r["위도"], 500)), "역사 행 (경계 + 500m)"))
    stops = _csv_rows(INFRA_RAW / "버스정류장" / "서울시 정류장마스터 정보.csv")
    rows.append(("버스정류장", "bus_stops", None if stops is None else sum(1 for r in stops if near(r["경도"], r["위도"], 100)), "정류장 (경계 + 100m)"))
    pages = sorted(POIS_RAW.glob("p*.json")) if POIS_RAW.exists() else []
    raw_pois = sum(len(((json.loads(p.read_text(encoding="utf-8")).get("body") or {}).get("items") or [])) for p in pages) if pages else None
    rows.append(("편의시설", "pois", raw_pois, "상가 (강남구 전체)"))

    out_rows, ok_all = [], True
    for name, key, raw, basis in rows:
        excl = man[key].get("excluded") or {}
        n = layer_count(key)
        ok = None if raw is None else (raw - sum(excl.values()) == n)
        if ok is False:
            ok_all = False
            errors.append({"type": "infra", "detail": f"{name}: 레이어 {n} ≠ 원자료 {raw} − 제외 {sum(excl.values())}"})
        out_rows.append({"name": name, "key": key, "basis": basis, "raw": raw, "excluded": excl, "layer": n, "ok": ok})
    checked = [r for r in out_rows if r["ok"] is not None]

    bus_links = None
    rstop = _csv_rows(INFRA_RAW / "버스정류장" / "서울시 노선 정류장마스터 정보.csv")
    if stops is not None and rstop is not None:
        sid = {r["정류장_ID"].strip() for r in stops}
        num = sum(1 for r in rstop if r["정류장_ID"].strip() in sid)
        bus = json.loads((LAYER_DIR / man["bus_stops"]["file"]).read_text(encoding="utf-8"))["features"]
        linked = sum(1 for f in bus if f["properties"].get("route_count"))
        bus_links = {"all": {"num": num, "den": len(rstop), "pct": _pct_s(num, len(rstop))},
                     "gangnam": {"num": linked, "den": len(bus), "pct": _pct_s(linked, len(bus))}}
    disp_s = " · ".join(f"{r['name']} {'—' if r['raw'] is None else ('100%' if r['ok'] else '다름')}" for r in out_rows)
    note = "분모 = 원자료 강남구 건수 − 사유가 기록된 제외(manifest excluded)"
    if bus_links:
        note += (f" · 참고: 버스 노선 연결률 전체 {bus_links['all']['pct']} ({bus_links['all']['num']:,}/{bus_links['all']['den']:,}), "
                 f"강남구 정류장 {bus_links['gangnam']['pct']} ({bus_links['gangnam']['num']}/{bus_links['gangnam']['den']}) — 목표 없음")
    metric = {"id": "M24", "name": "생활 인프라 건수 일치", "value": (len([r for r in checked if r["ok"]]) / len(out_rows)) if out_rows else None,
              "display": disp_s, "target": "원천 4종 각각 100%", "pass": ok_all and len(checked) == len(out_rows), "note": note}
    return [metric], {"sources": out_rows, "bus_links": bus_links}


def write_report_md(rep: dict) -> None:
    lines = ["# 평가 리포트", "",
             f"- 실행: {rep['run_at']} · DB 빌드: {rep['build_at']}",
             f"- 정답셋: {'**초안** (사람 확정 전, 추출자와 같은 작성자)' if rep['goldset']['draft'] else '확정'} · "
             + " · ".join(f"{k} `{v}`" for k, v in rep["goldset"]["files"].items()),
             "- 표본이 작아 수치 자체보다 평가 체계가 돌아가는 것을 보여주는 것이 목적입니다.", "",
             "## 지표", "", "| # | 지표 | 값 | 목표 | 결과 |", "|---|---|---|---|---|"]
    for mt in rep["metrics"]:
        res = "통과" if mt["pass"] else "미달"
        note = f" ({mt['note']})" if mt.get("note") else ""
        lines.append(f"| {mt['id']} | {mt['name']} | {mt['display']}{note} | {mt['target']} | {res} |")
    lines += ["", "## 층별 재현율·정밀도", "", "| 층 | 재현율 | 정밀도 | 기대 | 응답 |", "|---|---|---|---|---|"]
    for r in rep["layers"]:
        f = lambda v: "—" if v is None else f"{v:.0%}"  # noqa: E731
        lines.append(f"| {LAYER_KO[r['layer']]} | {f(r['recall'])} | {f(r['precision'])} | {r['expected']} | {r['returned']} |")
    lines += ["", "## 주소별 결과", "",
              "| 주소 | 입력 | 상태 | PNU | 서울 전역 | 자치구 | 법정동 | 필지 | 포함 판정 | 효력 중 고시 | 건축물 | 토지 정보 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    o = lambda v: "—" if v is None else ("일치" if v else "불일치")  # noqa: E731
    for a in rep["addresses"]:
        h = a["layer_hits"]
        lines.append(f"| {a['addr_id']} | {a['input']} | {o(a['status_ok'])} | {o(a['pnu_ok'])} | "
                     + " | ".join(h.get(k, "—") for k in LAYERS) + f" | {o(a['inclusion_ok'])} | "
                     f"{a.get('regulations') or '—'} | {a.get('building') or '—'} | {a.get('land') or '—'} |")
    if rep["excluded_addresses"]:
        lines.append(f"\n정답셋에서 뺀 주소: {', '.join(rep['excluded_addresses'])} (도로명주소 API 키 재발급 후 확정)")
    if rep.get("live"):
        lines += ["", "## 실시간 조회 (M18)", "", f"- 실행 {rep['run_at']} · 실시간 항목은 실행 시점의 외부 서비스 상태에 좌우됨", "",
                  "| 입력 | 상태 | 토지 정보 | PNU 일치 | 검색 경로 | 응답(ms) |", "|---|---|---|---|---|---|"]
        o2 = lambda v: "—" if v is None else ("일치" if v else "다름")  # noqa: E731
        for x in rep.get("live_rows", []):
            lines.append(f"| {x['input']} | {x['status']} | {x['land'] or '—'} | {o2(x['pnu_ok'])} | {x['via'] or '—'} | {x['ms']} |")
        if rep.get("parcel_rows"):
            lines += ["", "## 필지 클릭 조회 (M21)", "", "| 지번 | PNU 정답 | 응답 PNU | 상태 | 토지 정보 | 응답(ms) |",
                      "|---|---|---|---|---|---|"]
            for x in rep["parcel_rows"]:
                lines.append(f"| {x['label']} | `{x['pnu']}` | `{x['got']}` | {x['status']} | {x['land'] or '—'} | {x['ms']} |")
    else:
        lines += ["", "실시간 조회(M18)는 `python -m evals.run_eval --live`로 잽니다 (이번 실행에는 없음)."]
    mk = rep.get("market")
    if mk:
        lines += ["", "## 실거래 단지 (M22·M23)", "",
                  f"- 실거래 단지 {mk['complexes']} · 위치 찾음 {mk['located']} · 거래 {mk['trades']} · "
                  f"위치 있는 단지에 연결 {mk['trades_linked_located']}",
                  f"- 참고(목표 없음): 기본 정보 연결 단지 {mk['basis_linked']} / 단지 목록 {mk['list_total'] or '—'}"
                  + (" — 기본 정보 API 미등록으로 건너뜀" if mk.get("basis_check") == "not_registered" else ""), "",
                  "| 구분 | 사유 | 수 |", "|---|---|---|"]
        lines += [f"| 단지 위치 못 찾음 | {k} | {v} |" for k, v in mk["unmatched_reasons"].items()]
        lines += [f"| 거래 연결 안 됨 | {k} | {v} |" for k, v in mk["unlinked_reasons"].items()]
        if mk.get("unmatched"):
            lines += ["", "위치를 못 찾은 단지 (신고 지번의 필지가 지금 연속지적도에 없음 — 재건축 뒤 지번이 바뀐 단지 등일 수 있음, "
                      "build/apartments_unmatched.csv):", ""] + [f"- {x}" for x in mk["unmatched"]]
    inf = rep.get("infra")
    if inf:
        lines += ["", "## 생활 인프라 (M24)", "",
                  "레이어 건수 ÷ (원자료 강남구 건수 − 사유가 기록된 제외 건수). 원자료 건수는 평가 스크립트가 원본 CSV·상가 원 응답에서 따로 셉니다.", "",
                  "| 원천 | 원자료 강남구 | 사유 기록 제외 | 레이어 | 일치 |", "|---|---|---|---|---|"]
        for x in inf["sources"]:
            ex = ", ".join(f"{k} {v}" for k, v in x["excluded"].items()) or "—"
            lines.append(f"| {x['name']} | {x['raw'] if x['raw'] is not None else '원자료 없음'} | {ex} | {x['layer']} | "
                         f"{'—' if x['ok'] is None else ('일치' if x['ok'] else '다름')} |")
        b = inf.get("bus_links")
        if b:
            lines += ["", f"- 참고(목표 없음): 노선-정류장 행 중 서울 정류장 마스터에 있는 정류장 {b['all']['num']:,}/{b['all']['den']:,} "
                      f"({b['all']['pct']}) · 노선이 연결된 강남구 정류장 {b['gangnam']['num']}/{b['gangnam']['den']} ({b['gangnam']['pct']})"]
    lines += ["", "## 오류 목록", ""]
    if rep["errors"]:
        lines += [f"- [{e['type']}] {e['detail']}" for e in rep["errors"]]
    else:
        lines.append("없음")
    (ROOT / "evals" / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_meta(rep: dict) -> None:
    con = sqlite3.connect(str(DB_PATH))
    try:
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('eval_report', ?)",
                    (json.dumps(rep, ensure_ascii=False),))
        con.commit()
    finally:
        con.close()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="M18 실시간 조회·M21 필지 클릭 조회까지 잰다 (네트워크 사용)")
    args = ap.parse_args()
    if not args.live:
        os.environ["PROPEDIA_LIVE"] = "0"     # 네트워크 없이 (feedback2.md §8-2)
    try:
        rep = evaluate(live=args.live)
        write_report_md(rep)
        save_meta(rep)
    except Exception:
        traceback.print_exc()
        print("[오류] 평가 스크립트 실행 실패", file=sys.stderr)
        return 1
    print("지표 | 값 | 목표 | 결과")
    for mt in rep["metrics"]:
        print(f"{mt['id']} {mt['name']} | {mt['display']} | {mt['target']} | {'통과' if mt['pass'] else '미달'}")
    print(f"오류 {len(rep['errors'])}건 · evals/report.md, meta.eval_report 저장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
