"""배포 재현: Vercel 함수가 `public/`을 읽지 못하는 조건에서도 API가 정상인지 (P20-B). 네트워크 없음.

Vercel은 프로젝트 루트 `public/`을 CDN이 플랫폼 수준에서 서빙하고 Python 함수 묶음에는 넣지 않는다
(근거·관찰은 `core/paths.py` 머리말). 운영에서 이 때문에 `/api/v1/map/manifest` 503, 참고 WMS 타일 400,
필지 응답 `ref_zones` 0건, 타임라인 `data_as_of`에 레이어 기준일 누락이 한꺼번에 생겼다.

그래서 환경변수 `PROPEDIA_PUBLIC_DIR`를 **없는 경로**로 두어 같은 조건을 만들고, 서버가 읽는 파일을
`public/` 밖 `data/server/`에서 읽는지 확인한다. 이 테스트는 고치기 전 코드에서 실패한다.
"""
import json
from datetime import date

import pytest

from core import live as live_mod
from core import map as map_mod
from core import refzones
from core.paths import PUBLIC_ENV, SERVER_DATA, base_dir, layers_dir, public_dir
from tests.live_fixtures import FixtureFetch

YEOKSAM = (37.498701, 127.031577)          # 역삼동 823 경계 중심점 (tests/test_parcel_at.py와 같은 값)
PNU_YEOKSAM = "1168010100108230000"
REF_ZONE_YEOKSAM = "영동1토지구획정리사업"       # 역삼동 823이 들어 있는 의제처리구역 (ref_uije)
GANGNAM_Z14 = (14, 13974, 6348)            # 대치동 부근 — 운영 점검 목록과 같은 타일
TODAY = date(2026, 11, 10)

# 서버가 실행 중에 읽는 파일 (pipeline/sync_server_data.py가 복사하는 것과 같은 목록)
SERVER_FILES = [
    ("layers", "manifest.json"),
    ("layers", "propedia_projects.geojson"),
    ("layers", "propedia_impact.geojson"),
    ("layers", "propedia_parcels.geojson"),
    ("layers", "propedia_regulations.geojson"),
    ("layers", "ref_seoulplan.geojson"),
    ("layers", "ref_uije.geojson"),
    ("base", "gangnam.geojson"),
    ("base", "bjd.geojson"),
]


@pytest.fixture()
def no_public(monkeypatch, tmp_path):
    """배포본과 같은 조건: `public/`이 없다. 한 번 읽어 둔 캐시도 비운다."""
    monkeypatch.setenv(PUBLIC_ENV, str(tmp_path / "없는-public"))
    monkeypatch.setenv("VWORLD_API_KEY", "test-key")
    monkeypatch.setattr(map_mod, "_gangnam_bbox", None)
    refzones._CACHE.clear()
    yield
    monkeypatch.setattr(map_mod, "_gangnam_bbox", None)
    refzones._CACHE.clear()


def test_public_dir_env_takes_effect(no_public):
    assert not public_dir().exists()


def test_manifest_without_public(client, no_public):
    r = client.get("/api/v1/map/manifest")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["layers"] and d["generated_as_of"]
    boundaries = {L["id"]: L for L in d["layers"] if L["group"] == "base"}
    assert {"boundary-gangnam", "boundary-bjd"} <= set(boundaries)
    for L in boundaries.values():
        assert L["status"] == "ready" and L["count"], L
    # 도형 속성에서 읽는 근거 쪽 (propedia_*.geojson)
    projects = next(L for L in d["layers"] if L["id"] == "projects")
    assert projects["status"] == "ready" and projects["source_pages"]


def test_parcel_ref_zones_without_public(client, monkeypatch, no_public):
    """필지 조회의 '참고 구역'은 ref_*.geojson을 읽어야 나온다."""
    import api.index as api
    monkeypatch.setattr(api.live_mod, "default", lambda: live_mod.Live(FixtureFetch()))
    d = client.get("/api/v1/map/parcel-at", params={"lat": YEOKSAM[0], "lon": YEOKSAM[1]}).json()
    assert d["status"] == "ok" and d["pnu"] == PNU_YEOKSAM
    assert REF_ZONE_YEOKSAM in [z["name"] for z in d["ref_zones"]]


def test_refzones_loaded_without_public(no_public):
    assert refzones.loaded_count() > 0
    assert REF_ZONE_YEOKSAM in [z["name"] for z in refzones.zones_at(*YEOKSAM)]


def test_feature_project_without_public(client, no_public):
    d = client.get("/api/v1/map/feature/project/1").json()
    assert d["kind"] == "project" and d["title"] and d["as_of"]


def test_wms_bbox_without_public(client, no_public):
    """강남구 경계(base/gangnam.geojson)를 못 읽으면 모든 타일이 '강남구 밖'으로 막힌다."""
    w, s, e, n = map_mod.gangnam_bbox()
    assert 127.0 < w < e < 127.2 and 37.4 < s < n < 37.6
    z, x, y = GANGNAM_Z14
    assert map_mod.wms_request_error("lt_c_uq111", z, x, y) is None
    r = client.get(f"/api/v1/map/wms/lt_c_uq111/{z}/{x}/{y}.png")
    assert r.status_code != 400, r.text          # pytest는 PROPEDIA_LIVE=0이라 503이 정상


def test_timeline_layer_as_of_without_public(client, no_public):
    """타임라인 '자료 기준일' 레인의 layer:* 항목은 manifest.json에서 온다."""
    d = client.get("/api/v1/timeline", params={"from": "2018-01-01", "to": "2026-12-31"}).json()
    assert [e for e in d["lanes"]["data_as_of"] if e["id"].startswith("layer:")]


def test_runtime_reads_no_public():
    """`core/`는 실행 중에 `public/`을 쳐다보지 않는다 (`api/index.py`의 로컬 전용 mount만 예외).

    `public_dir()`을 쓰는 곳과 `public` 경로를 적은 문자열(설명·오류 문구 포함)을 함께 막는다 —
    배포본에서 읽히지 않는 경로를 안내 문구에 적으면 사람이 엉뚱한 곳을 보게 된다.
    """
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    bad = []
    for p in sorted((root / "core").rglob("*.py")):
        if p.name == "paths.py":                 # public_dir() 정의와 근거를 적어 두는 곳
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            where = f"{p.relative_to(root)}:{getattr(node, 'lineno', 0)}"
            if isinstance(node, ast.Name) and node.id == "public_dir":
                bad.append(f"{where} public_dir() 사용")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "public/data" in node.value:
                bad.append(f"{where} {node.value[:60]!r}")       # 설명·오류 문구까지 (사람이 엉뚱한 곳을 보지 않게)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                # Path 결합: ROOT / "public" / … ('public'을 추진 방식 코드로 쓰는 곳과 구분)
                for side in (node.left, node.right):
                    if isinstance(side, ast.Constant) and side.value == "public":
                        bad.append(f"{where} 경로에 'public'")
    assert not bad, "public/을 가리키는 곳: " + " / ".join(bad)


def test_server_data_in_sync():
    """`data/server/`가 `public/data/`와 바이트까지 같다 (pipeline.sync_server_data --check와 같은 규칙)."""
    pub = public_dir() / "data"
    diff = [f"{sub}/{name}" for sub, name in SERVER_FILES
            if (SERVER_DATA / sub / name).read_bytes() != (pub / sub / name).read_bytes()]
    assert not diff, "다른 파일: " + ", ".join(diff) + " → python -m pipeline.sync_server_data"


def test_server_data_dirs():
    assert layers_dir() == SERVER_DATA / "layers" and base_dir() == SERVER_DATA / "base"
    man = json.loads((layers_dir() / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(man.get("layers"), dict) and man["layers"]
