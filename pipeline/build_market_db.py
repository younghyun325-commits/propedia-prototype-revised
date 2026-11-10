"""db/market.db 만들기 (docs/map/PLAN.md P17 4단계). 네트워크 안 씀. 멱등, 끝나면 VACUUM.

입력: build/rtms_raw/*.xml (pipeline.fetch_trades), seed/apartments.geojson (pipeline.build_trade_complexes)
- apt_complexes: 실거래 단지. 기본 정보 열(kapt_code·households·buildings·approval_date·road_addr·jibun_addr·
  basis_info_status)은 이미 있는 market.db에서 그대로 옮긴다 (pipeline.fetch_apt_basis만 채운다).
- apt_trades: 거래 → 단지 연결 ① aptSeq ② PNU ③ 법정동 + 정규화 단지명(seed/apt_name_rules.yaml) ④ 안 되면 NULL
  → build/trades_unlinked.csv (사유별 건수)
- apt_trade_monthly: 단지 × 면적대 × 계약월 중위 거래가·건수 (해제 거래 제외)
- 검사(어긋나면 종료 코드 1): 월별 count 합 = 해제 제외·연결된 원자료 건수, raw_hash 중복 0,
  해제 건수 = 원자료 cdealType 'O' 건수. 20MB를 넘으면 종료 코드 3 (기간 축소 검토).
- M22·M23은 meta에 JSON으로 남긴다 (evals/run_eval.py가 같은 정의로 다시 센다).
- 사람 대조용: build/market_check_table.md (은마·청담자이·압구정동 426 최근 거래 10건)

사용: python -m pipeline.build_market_db
"""
import csv
import json
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from core.market import AREA_BANDS, area_band
from pipeline.apt_names import norm_name
from pipeline.build_trade_complexes import OUT as APT_SEED, fetched_on, load_trades
from pipeline.common import BUILD, ROOT, log, setup_stdout, sha256
from pipeline.rtms_parse import DROP_FIELDS

DB = ROOT / "db" / "market.db"
SCHEMA = ROOT / "db" / "market_schema.sql"
UNLINKED = BUILD / "trades_unlinked.csv"
CHECK_TABLE = BUILD / "market_check_table.md"
MAX_BYTES = 20 * 1024 * 1024
BASIS_COLS = ("kapt_code", "households", "buildings", "approval_date", "road_addr", "jibun_addr", "basis_info_status")
# 사람 대조용 (HUMAN_TODO): 지번으로 고른다 (압구정동 426의 실거래 단지명은 '신현대9차')
CHECK_JIBUNS = [("대치동", "316", "은마"), ("청담동", "134-38", "청담자이"), ("압구정동", "426", "현대")]
TRADE_COLS = ("complex_id", "apt_seq", "pnu", "apt_name_raw", "umd_name", "jibun", "apt_dong", "exclusive_area_m2",
              "area_band", "contract_date", "amount_10k_won", "floor", "build_year", "deal_type", "land_leasehold",
              "is_cancelled", "cancelled_date", "registered_date", "link_method", "raw_hash")


def old_basis(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        return {r["id"]: {k: r[k] for k in BASIS_COLS} for r in con.execute(
            f"SELECT id, {', '.join(BASIS_COLS)} FROM apt_complexes")}
    except sqlite3.Error:
        return {}
    finally:
        con.close()


def old_meta(path: Path) -> dict:
    if not path.is_file():
        return {}
    con = sqlite3.connect(path)
    try:
        return {k: v for k, v in con.execute("SELECT key, value FROM meta")}
    except sqlite3.Error:
        return {}
    finally:
        con.close()


class Linker:
    """거래 → 단지 id. ① aptSeq ② PNU ③ 법정동 + 정규화 단지명"""

    def __init__(self, complexes: list[dict]):
        self.by_seq = {c["apt_seq"]: c["id"] for c in complexes if c["apt_seq"]}
        self.by_pnu: dict[str, str] = {}
        self.by_name: dict[tuple, set] = defaultdict(set)
        for c in complexes:
            for p in c["pnus"]:
                self.by_pnu.setdefault(p, c["id"])
            for nm in [c["name"], *c["aliases"]]:
                if c["bjd_code"]:
                    self.by_name[(c["bjd_code"], norm_name(nm))].add(c["id"])

    def link(self, r: dict) -> tuple[str | None, str | None, str | None]:
        """→ (단지 id, 방법, 실패 사유)"""
        if r["apt_seq"] and r["apt_seq"] in self.by_seq:
            return self.by_seq[r["apt_seq"]], "apt_seq", None
        if r["pnu"] and r["pnu"] in self.by_pnu:
            return self.by_pnu[r["pnu"]], "pnu", None
        bjd = r["pnu"][:10] if r["pnu"] else (f"{r['sgg_cd']}{r['umd_cd']}" if r["sgg_cd"] and r["umd_cd"] else None)
        hits = self.by_name.get((bjd, norm_name(r["apt_name_raw"]))) if bjd else None
        if hits and len(hits) == 1:
            return next(iter(hits)), "name", None
        if hits:
            return None, None, "단지명이 여러 단지와 같음"
        if not r["apt_seq"] and not r["pnu"]:
            return None, None, "aptSeq·PNU 없음, 단지명 불일치"
        return None, None, "aptSeq·PNU·단지명 모두 불일치"


def m22_m23(complexes: list[dict], trades: list[dict]) -> tuple[dict, dict]:
    located = {c["id"] for c in complexes if c["lat"] is not None}
    m22 = {"num": len(located), "den": len(complexes)}
    m23 = {"num": sum(1 for t in trades if t["complex_id"] in located), "den": len(trades)}
    return m22, m23


def check_table(con) -> str:
    out = ["| 단지(지번) | 계약일 | 전용면적(㎡) | 층 | 금액(만원) | 거래 유형 | 해제 | 동 |", "|---|---|---|---|---|---|---|---|"]
    for dong, jibun, label in CHECK_JIBUNS:
        rows = con.execute("""SELECT t.*, c.name cname FROM apt_trades t LEFT JOIN apt_complexes c ON c.id=t.complex_id
                              WHERE t.umd_name=? AND t.jibun=? ORDER BY t.contract_date DESC, t.id DESC LIMIT 10""",
                           (dong, jibun)).fetchall()
        for r in rows:
            out.append(f"| {label}({dong} {jibun}, 신고명 {r['apt_name_raw']}) | {r['contract_date']} | "
                       f"{r['exclusive_area_m2']} | {r['floor']} | {r['amount_10k_won']:,} | {r['deal_type'] or '-'} | "
                       f"{'해제 ' + (r['cancelled_date'] or '') if r['is_cancelled'] else '-'} | {r['apt_dong'] or '-'} |")
    return "\n".join(out) + "\n"


def main() -> int:
    setup_stdout()
    trades_raw, same = load_trades()
    fc = json.loads(APT_SEED.read_text(encoding="utf-8"))
    as_of = fetched_on()
    keep = old_basis(DB)
    keep_meta = old_meta(DB)
    complexes = []
    for f in fc["features"]:
        p = f["properties"]
        complexes.append({"id": p["id"], "apt_seq": p["apt_seq"], "name": p["name"], "aliases": p["aliases"],
                          "pnus": p["pnus"], "bjd_code": p["bjd_code"], "lat": p["lat"], "lon": p["lon"],
                          "build_year": p["build_year"], "as_of": as_of,
                          **(keep.get(p["id"]) or {k: None for k in BASIS_COLS} | {"basis_info_status": "pending"})})
    linker = Linker(complexes)
    unlinked = Counter()
    rows = []
    for r in trades_raw:
        cid, how, why = linker.link(r)
        if cid is None:
            unlinked[why] += 1
        rows.append({**{k: r.get(k) for k in TRADE_COLS}, "complex_id": cid, "link_method": how,
                     "area_band": area_band(r["exclusive_area_m2"])})
    for row in rows:      # 저장 필드에 개인 정보 성격 필드가 섞이지 않았는지 (rtms_parse가 이미 버림)
        assert not (DROP_FIELDS & set(row)), "개인 정보 성격 필드"

    tmp = DB.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    ccols = ("id", "apt_seq", "name", "aliases", "pnus", "bjd_code", "lat", "lon", "build_year", *BASIS_COLS, "as_of")
    con.executemany(f"INSERT INTO apt_complexes ({', '.join(ccols)}) VALUES ({', '.join('?' * len(ccols))})",
                    [tuple(json.dumps(c[k], ensure_ascii=False) if k in ("aliases", "pnus") else c[k] for k in ccols)
                     for c in sorted(complexes, key=lambda c: c["id"])])
    rows.sort(key=lambda r: (r["contract_date"] or "", r["raw_hash"]))
    try:
        con.executemany(f"INSERT INTO apt_trades ({', '.join(TRADE_COLS)}) VALUES ({', '.join('?' * len(TRADE_COLS))})",
                        [tuple(r[k] for k in TRADE_COLS) for r in rows])
        dup = 0
    except sqlite3.IntegrityError:
        dup = len(rows) - len({r["raw_hash"] for r in rows})
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if r["complex_id"] and not r["is_cancelled"] and r["area_band"]:
            groups[(r["complex_id"], r["area_band"], r["contract_date"][:7])].append(r["amount_10k_won"])
    con.executemany("INSERT INTO apt_trade_monthly VALUES (?,?,?,?,?)",
                    [(k[0], k[1], k[2], float(statistics.median(v)), len(v)) for k, v in sorted(groups.items())])

    m22, m23 = m22_m23(complexes, rows)
    dates = sorted(r["contract_date"] for r in rows if r["contract_date"])
    meta = {"schema_version": "1", "fetched_on": as_of or "", "trade_from": dates[0] if dates else "",
            "trade_to": dates[-1] if dates else "", "raw_count": str(len(rows)),
            "raw_cancelled": str(sum(r["is_cancelled"] for r in rows)),
            "area_bands": json.dumps([b[0] for b in AREA_BANDS], ensure_ascii=False),
            "m22": json.dumps(m22), "m23": json.dumps(m23),
            "unlinked": json.dumps(dict(unlinked), ensure_ascii=False, sort_keys=True),
            "source_note": "국토교통부 아파트 매매 실거래가 상세 자료 (공공데이터포털 RTMSDataSvcAptTradeDev, 지역코드 11680)"}
    for k in ("basis_fetched_on", "list_total", "basis_info_check", "basis_list_unlinked"):
        if keep_meta.get(k):                        # 기본 정보 단계가 남긴 값은 그대로
            meta[k] = keep_meta[k]
    con.executemany("INSERT INTO meta VALUES (?,?)", sorted(meta.items()))
    con.commit()

    # 검사
    errs = []
    monthly_sum = con.execute("SELECT COALESCE(SUM(count),0) FROM apt_trade_monthly").fetchone()[0]
    expect = sum(1 for r in rows if r["complex_id"] and not r["is_cancelled"] and r["area_band"])
    live_all = sum(1 for r in rows if not r["is_cancelled"])
    if monthly_sum != expect:
        errs.append(f"월별 count 합 {monthly_sum} ≠ 해제 제외·연결 원자료 {expect}")
    if dup:
        errs.append(f"raw_hash 중복 {dup}")
    raw_cancel = sum(1 for r in trades_raw if r["is_cancelled"])
    db_cancel = con.execute("SELECT COUNT(*) FROM apt_trades WHERE is_cancelled=1").fetchone()[0]
    if raw_cancel != db_cancel:
        errs.append(f"해제 건수 DB {db_cancel} ≠ 원자료 {raw_cancel}")
    tbl = check_table(con)
    con.close()
    if errs:
        tmp.unlink(missing_ok=True)
        for e in errs:
            log(f"[검사 실패] {e}")
        return 1
    c2 = sqlite3.connect(tmp)
    c2.execute("VACUUM")
    c2.close()
    tmp.replace(DB)

    BUILD.mkdir(exist_ok=True)
    with open(UNLINKED, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["reason", "count"])
        w.writerows(sorted(unlinked.items(), key=lambda x: -x[1]))
    CHECK_TABLE.write_text(tbl, encoding="utf-8", newline="\n")
    by_how = Counter(r["link_method"] for r in rows)
    size = DB.stat().st_size
    log(f"거래 {len(rows)}건 (해제 {db_cancel} · 같은 달 같은 레코드 순번 {same}) · 단지 {len(complexes)}")
    log(f"연결: aptSeq {by_how['apt_seq']} · PNU {by_how['pnu']} · 단지명 {by_how['name']} · 못 이음 {by_how[None]} "
        f"{dict(unlinked)} → {UNLINKED.name}")
    log(f"월별 행 {len(groups)} · count 합 {monthly_sum} = 해제 제외·연결 {expect} (해제 제외 전체 {live_all}) · raw_hash 중복 0 · "
        f"해제 {db_cancel} = 원자료 {raw_cancel}")
    log(f"M22 {m22['num']}/{m22['den']} = {m22['num'] / m22['den']:.1%} · M23 {m23['num']}/{m23['den']} = "
        f"{m23['num'] / m23['den']:.1%}")
    log(f"db/market.db {size / 1024 / 1024:.2f} MB sha256 {sha256(DB)[:16]} · 대조표 → build/{CHECK_TABLE.name}")
    if size > MAX_BYTES:
        log("db/market.db가 20MB를 넘었습니다 — 기간 축소 방안을 정해야 합니다")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
