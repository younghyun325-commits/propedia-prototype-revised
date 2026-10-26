"""평가 (agents.md §13). 정답셋과 비교해 지표 12개를 계산하고 evals/report.md 와 meta.eval_report 에 저장한다.

사용: python -m evals.run_eval
- 층별 기대 항목(M6·M7)은 core/lookup.py 를 쓰지 않고 정답셋(addresses.yaml + scope_labels.yaml)으로 따로 배치해 만든다.
- 목표 미달이 있어도 종료 코드 0, 스크립트 오류는 1.
"""
import hashlib
import json
import math
import sqlite3
import sys
import time
import traceback
import warnings
from datetime import datetime
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
SKIP_KEYS = {"evidence", "how_to_submit", "places", "source_note", "payload", "text", "evidences", "query"}
TIMING_ROUNDS = 20


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


# ── 정답셋으로 따로 만드는 층별 기대값 ─────────────────────────
def expected_layers(addr: dict, labels: dict) -> dict[str, set]:
    exp = {k: set() for k in LAYERS}
    for key, lab in labels.items():
        st, refs = lab["scope_type"], lab["scope_ref"]
        if st == "SIDO" and "11" in refs:
            exp["city"].add(key)
        elif st == "SGG" and addr["sgg_code"] in refs:
            exp["gu"].add(key)
        elif st == "SAENGHWAL" and addr.get("saenghwal") in refs:
            exp["dong"].add(key)
        elif st == "BJD" and addr["bjd_code"] in refs:
            exp["dong"].add(key)
        elif st == "PARCEL" and addr["pnu"] in refs:
            exp["parcel"].add(key)
    for p in addr.get("projects", []):
        tag = f"project:{p['project_key']}"
        if p["inclusion"] in ("possible", "included", "nearby"):
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


def evaluate() -> dict:
    g_ext = load_yaml("extraction.yaml")
    g_addr = load_yaml("addresses.yaml")
    g_scope = load_yaml("scope_labels.yaml")
    labels = g_scope.get("labels", {})
    errors: list[dict] = []
    metrics: list[dict] = []

    con = connect_ro()
    m = meta(con)
    keymap = {r["id"]: r["project_key"] for r in con.execute("SELECT id, project_key FROM projects")}

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

    # M4 적용 범위 정확도
    db_items = {r["item_key"]: (r["scope_type"], set(json.loads(r["scope_ref"]))) for r in
                con.execute("SELECT item_key, scope_type, scope_ref FROM applicability_rules")}
    hit = 0
    for key, lab in labels.items():
        got = db_items.get(key)
        if got and got[0] == lab["scope_type"] and got[1] == set(lab["scope_ref"]):
            hit += 1
        else:
            errors.append({"type": "scope", "detail": f"{key}: 정답 {lab['scope_type']} {lab['scope_ref']}, "
                                                      f"응답 {got[0] + ' ' + str(sorted(got[1])) if got else '(항목 없음)'}"})
    for key in sorted(set(db_items) - set(labels)):
        errors.append({"type": "scope", "detail": f"{key}: 정답 라벨 없음"})
    metrics.append({"id": "M4", "name": "적용 범위 정확도", "value": pct(hit, len(labels)),
                    "display": disp(hit, len(labels)), "target": "≥ 95%",
                    "pass": len(labels) > 0 and hit / len(labels) >= 0.95})

    # M5 주소 정규화, M6·M7 층별, M8 포함 판정, M9 원문 링크
    addresses = g_addr.get("addresses", [])
    n_ok = 0
    layer_exp = {k: 0 for k in LAYERS}
    layer_ret = {k: 0 for k in LAYERS}
    layer_hit = {k: 0 for k in LAYERS}
    pair_ok = pair_n = 0
    img_ok = img_n = 0
    addr_rows = []
    responses = []
    for a in addresses:
        n = normalize(con, a["input"])
        row = {"addr_id": a["addr_id"], "input": a["input"], "status_ok": n["status"] == a["status"],
               "pnu_ok": None, "layer_hits": {}, "inclusion_ok": None}
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
            exp = expected_layers(a, labels)
            ret = returned_layers(resp, keymap)
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
            L = resp["layers"]
            for it in L["city"] + L["gu"]["items"] + L["dong"]["items"] + L["parcel"]["items"]:
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
                    "target": "100%", "pass": img_n > 0 and img_ok == img_n})

    # M11 금지어 (우리가 만든 문장)
    hits = []
    for r in con.execute("SELECT item_key, title, summary FROM applicability_rules"):
        hits += [f"{r['item_key']}: {w}" for w in banned_hits(r["title"] + " " + r["summary"])]
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
    gold_stage = g_ext.get("stage")
    got_stage = stages.get("apgujeong-6-1-hanyang7")
    if got_stage != gold_stage:
        errors.append({"type": "other", "detail": f"단계: 정답 {gold_stage}, 응답 {got_stage}"})
    metrics.append({"id": "M12", "name": "단계 판정", "value": got_stage == gold_stage,
                    "display": f"{got_stage} (정답 {gold_stage})", "target": "일치", "pass": got_stage == gold_stage})
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

    drafts = [g_ext.get("draft"), g_addr.get("draft"), g_scope.get("draft")]
    return {
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "build_at": m.get("build_at"),
        "goldset": {"draft": any(d is not False for d in drafts),
                    "files": {"extraction": sha8(GOLD / "extraction.yaml"), "addresses": sha8(GOLD / "addresses.yaml"),
                              "scope_labels": sha8(GOLD / "scope_labels.yaml")}},
        "metrics": metrics,
        "layers": layer_rows,
        "addresses": addr_rows,
        "excluded_addresses": g_addr.get("excluded", []),
        "errors": errors,
    }


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
    lines += ["", "## 주소별 결과", "", "| 주소 | 입력 | 상태 | PNU | 서울 전역 | 자치구 | 법정동 | 필지 | 포함 판정 |",
              "|---|---|---|---|---|---|---|---|---|"]
    o = lambda v: "—" if v is None else ("일치" if v else "불일치")  # noqa: E731
    for a in rep["addresses"]:
        h = a["layer_hits"]
        lines.append(f"| {a['addr_id']} | {a['input']} | {o(a['status_ok'])} | {o(a['pnu_ok'])} | "
                     + " | ".join(h.get(k, "—") for k in LAYERS) + f" | {o(a['inclusion_ok'])} |")
    if rep["excluded_addresses"]:
        lines.append(f"\n정답셋에서 뺀 주소: {', '.join(rep['excluded_addresses'])} (도로명주소 API 키 재발급 후 확정)")
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
    try:
        rep = evaluate()
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
