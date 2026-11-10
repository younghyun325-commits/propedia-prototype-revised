"""DB 좌표만 seed 값으로 갱신 (docs/map/PLAN.md P13-6-2). 네트워크·../data 없이 동작, 멱등.

원본 PDF(../data)가 없는 PC에서는 run_all(textify 결과 build/text 필요)을 돌릴 수 없으므로, seed가 바뀐 좌표만
db/propedia.db에 옮긴다. 원본 PC에서 run_all을 돌리면 같은 값이 나온다:
  - land_cache.payload ← load_seed가 seed/land_cache.json의 각 항목을 json.dumps(land, ensure_ascii=False)로 넣는다
                         (pipeline/load_seed.py). 여기서도 같은 함수로 같은 문자열을 만든다.
  - projects.lat/lon/coord_source ← build_projects.project_center()가 seed/project_coords.csv의 lat·lon(문자열 → float)·
                         coord_source를 쓴다 (pipeline/build_projects.py). 여기서도 같은 변환을 쓴다.
그 밖의 열·표는 건드리지 않는다.

순서: db/propedia.db → build/propedia.db.bak 복사 → 시연 주소 15건 판정(포함·주변 500m) 기록 → 갱신 →
     다시 판정 → 전·후 표. 판정(사업·포함 단계)이 하나라도 바뀌면 .bak으로 되돌리고 종료 코드 1.

사용: python -m pipeline.patch_coords
"""
import csv
import json
import shutil
import sqlite3

from core.lookup import lookup
from pipeline.common import BUILD, DB_PATH, SEED, log, setup_stdout, sha256, vacuum_db

BAK = BUILD / "propedia.db.bak"


def judgments(db_path) -> dict[str, dict]:
    con = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = {}
    for r in con.execute("SELECT addr_id, input_text FROM demo_addresses ORDER BY addr_id"):
        resp = lookup(con, r["input_text"])
        layers = resp.get("layers") or {}
        parcel = layers.get("parcel") or {}
        out[r["addr_id"]] = {
            "status": resp["status"],
            "included": sorted((p["project_id"], p["inclusion"]) for p in parcel.get("included_projects") or []),
            "nearby": sorted(p["project_id"] for p in parcel.get("nearby_projects") or []),
            "nearby_m": {p["project_id"]: p.get("distance_m") for p in parcel.get("nearby_projects") or []},
            "dong_projects": sorted(p["project_id"] for p in (layers.get("dong") or {}).get("projects") or []),
            "coord": (resp["normalized"].get("lat"), resp["normalized"].get("lon")),
        }
    con.close()
    return out


def apply(con) -> tuple[int, int]:
    lands = json.loads((SEED / "land_cache.json").read_text(encoding="utf-8"))
    n_land = 0
    for land in lands:
        cur = con.execute("SELECT payload FROM land_cache WHERE pnu=?", (land["pnu"],)).fetchone()
        if cur is None:
            continue
        new = json.dumps(land, ensure_ascii=False)          # load_seed.py와 같은 직렬화
        if cur[0] != new:
            con.execute("UPDATE land_cache SET payload=? WHERE pnu=?", (new, land["pnu"]))
            n_land += 1
    n_prj = 0
    with open(SEED / "project_coords.csv", encoding="utf-8-sig", newline="") as f:
        for a in csv.DictReader(f):
            if not a.get("lat"):
                continue
            lat, lon, src = float(a["lat"]), float(a["lon"]), a["coord_source"]   # build_projects.project_center와 같음
            cur = con.execute("SELECT lat, lon, coord_source FROM projects WHERE project_key=?", (a["project_key"],)).fetchone()
            if cur is not None and tuple(cur) != (lat, lon, src):
                con.execute("UPDATE projects SET lat=?, lon=?, coord_source=? WHERE project_key=?",
                            (lat, lon, src, a["project_key"]))
                n_prj += 1
    return n_land, n_prj


def main() -> int:
    setup_stdout()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_PATH, BAK)
    log(f"백업 build/propedia.db.bak (sha256 {sha256(BAK)[:16]})")
    before = judgments(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    n_land, n_prj = apply(con)
    con.commit()
    con.close()
    after = judgments(DB_PATH)
    log(f"갱신: land_cache {n_land}행, projects {n_prj}행")
    log(f"{'주소':4s} {'상태':10s} {'포함(전→후)':28s} {'주변 500m(전→후)':22s} {'거리 m(전→후)':16s} 판정")
    changed = []
    for k in before:
        b, a = before[k], after[k]
        same = (b["status"], b["included"], b["nearby"], b["dong_projects"]) == \
               (a["status"], a["included"], a["nearby"], a["dong_projects"])
        if not same:
            changed.append(k)
        inc = f"{b['included']}→{a['included']}" if b["included"] != a["included"] else str(b["included"])
        nb = f"{b['nearby']}→{a['nearby']}" if b["nearby"] != a["nearby"] else str(b["nearby"])
        dist = ", ".join(f"{pid}:{b['nearby_m'].get(pid)}→{a['nearby_m'].get(pid)}" for pid in a["nearby_m"]) or "-"
        log(f"{k:4s} {b['status']:10s} {inc:28s} {nb:22s} {dist:16s} {'같음' if same else '바뀜'}")
    if changed:
        shutil.copy2(BAK, DB_PATH)
        log(f"판정이 바뀐 주소 {changed} → db/propedia.db를 백업으로 되돌렸습니다")
        return 1
    vacuum_db()          # 덮어쓴 옛 행 바이트를 남기지 않는다 (P15 0단계)
    log(f"판정 15건 모두 같음 · db/propedia.db sha256 {sha256(DB_PATH)[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
