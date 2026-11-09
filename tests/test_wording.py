"""우리가 만든 문장에 금지어가 없는지 확인한다 (agents.md §9-6).

적용: public/*.html, public/assets/*.js, DB의 summary·title·target_note·tier_reason, API가 만드는 문구
(effective_status_label·reference_reason·building_note 포함).
제외: evidence(원문 인용), documents.title(원문 제목), 원문 문구 그대로인 how_to_submit·places·source_note.
법정 용어 '정비예정구역'은 예측 표현이 아니므로 허용한다.
"""
import json
from datetime import date
from pathlib import Path

from core.lookup import lookup
from core.progress import progress

ROOT = Path(__file__).resolve().parents[1]
BANNED = ["예상", "예정", "전망", "지연", "늦", "위험", "안전", "유망", "호재", "추천", "수익", "투자", "확실", "보장",
          "반드시", "가능성 높"]
ALLOW = ["정비예정구역"]
SKIP_KEYS = {"evidence", "how_to_submit", "places", "source_note", "payload", "text", "evidences", "query",
             # 브이월드 원 자료 값 (예: '비행안전제2구역') — 원문 인용과 같이 검사하지 않는다
             "zones", "jimok", "land_use_zone", "land_use_zone2", "use_situation", "road_side", "terrain"}


def hits(text: str) -> list[str]:
    for a in ALLOW:
        text = text.replace(a, "")
    return [w for w in BANNED if w in text]


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP_KEYS:
                continue
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def test_public_files():
    bad = []
    files = list((ROOT / "public").glob("*.html")) + list((ROOT / "public" / "assets").glob("*.js"))
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for w in hits(line):
                bad.append(f"{f.name}:{i} '{w}'")
    assert not bad, bad


# 지도 화면(web/src): §9-6 금지어 + '시세' (docs/map/PLAN.md '먼저 정해야 할 것'). 브랜드 문구 파일만 예외.
WEB_BANNED = BANNED + ["시세"]
WEB_SRC = ROOT / "web" / "src"
WEB_EXEMPT = {WEB_SRC / "copy" / "brand.ts"}


def web_hits(text: str) -> list[str]:
    for a in ALLOW:
        text = text.replace(a, "")
    return [w for w in WEB_BANNED if w in text]


def test_web_src():
    files = [f for pat in ("*.ts", "*.tsx") for f in WEB_SRC.rglob(pat) if f not in WEB_EXEMPT]
    assert files, "web/src 에 검사할 파일이 없습니다"
    bad = []
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for w in web_hits(line):
                bad.append(f"{f.relative_to(ROOT).as_posix()}:{i} '{w}'")
    assert not bad, bad


def test_db_summary_title(con):
    bad = []
    for r in con.execute("SELECT item_key, title, summary, target_note, tier_reason FROM applicability_rules"):
        for w in hits(" ".join(x or "" for x in (r["title"], r["summary"], r["target_note"], r["tier_reason"]))):
            bad.append(f"{r['item_key']} '{w}'")
    for r in con.execute("SELECT label FROM related_history"):
        bad += [f"related_history '{w}'" for w in hits(r["label"])]
    for r in con.execute("SELECT value FROM meta WHERE key='coverage_note'"):
        bad += [f"coverage_note '{w}'" for w in hits(r["value"])]
    assert not bad, bad


def test_api_generated_text(con):
    bad = []
    texts = [r["input_text"] for r in con.execute("SELECT input_text FROM demo_addresses") if r["input_text"]]
    texts += ["", "강남구 없는동 1", "아무 데나"]
    rid = con.execute("SELECT id FROM review_queue WHERE item_type='parcel_inclusion'").fetchone()["id"]
    responses = [lookup(con, t) for t in texts]
    responses.append(lookup(con, texts[0], decisions=[{"review_id": rid, "action": "approve"}]))
    responses.append(progress(con, 1))
    # 효력 상태 문구(기간 중·끝남·시작 전)가 모두 나오도록 날짜를 바꿔 본다
    responses += [lookup(con, texts[0], today=date(2027, 5, 1)), lookup(con, texts[0], today=date(2026, 4, 20))]
    for resp in responses:
        for path, s in walk(resp):
            for w in hits(s):
                bad.append(f"{path} '{w}': {s[:40]}")
    assert not bad, bad


def test_review_queue_labels(con):
    bad = []
    for r in con.execute("SELECT title, reason FROM review_queue"):
        bad += [f"'{w}' in {r['title']}" for w in hits(r["title"] + " " + r["reason"])]
    assert not bad, bad
