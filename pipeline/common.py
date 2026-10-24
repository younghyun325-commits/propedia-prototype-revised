"""빌드 스크립트 공통 설정 (agents.md §8-1). 시연 코드(core/, api/)에서 import 하지 않는다."""
import hashlib
import logging
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "data"
BUILD = ROOT / "build"
DB_PATH = ROOT / "db" / "propedia.db"
PUBLIC = ROOT / "public"
SEED = ROOT / "seed"
DATA_RAW = ROOT / "data_raw"
EXTRACTIONS = ROOT / "extractions"
TEXT_DIR = BUILD / "text"
PAGES_DIR = PUBLIC / "pages"
TRANSCRIPTS = SEED / "transcripts"   # Claude Code 전사 원본 (커밋함, §21 참고)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def setup_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1) -> None:
    print(f"[오류] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def connect_rw() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def expand_ranges(ranges: list[tuple[int, int]]) -> list[int]:
    out: list[int] = []
    for a, b in ranges:
        out.extend(range(a, b + 1))
    return out


def ranges_str(ranges: list[tuple[int, int]]) -> str:
    return ",".join(f"{a}-{b}" if a != b else f"{a}" for a, b in ranges)


# ── 출처 (§3-3) ────────────────────────────────────────────
SOURCES = {
    "gangnam-gubo": {"name": "강남구 구보", "layer": "gu", "url": None},
    "seoul-urban-portal": {"name": "서울도시공간포털", "layer": "city", "url": "https://urban.seoul.go.kr"},
    "seoul-citybuild": {"name": "서울시 도시계획 소식", "layer": "city", "url": "https://news.seoul.go.kr/citybuild/"},
}


# ── page_label 환산 공식 (§3-2). 텍스트에서 읽히지 않을 때만 쓴다 ──
def _label_d1(p: int) -> str | None:
    return None


def _label_d2(p: int) -> str | None:
    return str(p - 6)   # [확인] PDF 12 = 인쇄 6, PDF 31 = 인쇄 25, PDF 115 = 인쇄 109


def _label_d3(p: int) -> str | None:
    return str(p - 13)


def _label_d4(p: int) -> str | None:
    return str(p - 8)


# ── 문서 4종 (§3-1 ~ §3-4) ─────────────────────────────────
# D1 p1 공고 제목 그대로 [확인]
D1_TITLE = (
    "도시관리계획(압구정 아파트지구 개발기본계획, 지구단위계획구역 및 지구단위계획) 결정(변경), "
    "압구정 아파트지구 특별계획구역⑥-1 한양7차아파트 재건축 정비구역·정비계획 결정(변경)(안) 공람·공고"
)

DOCS = {
    "D1": {
        "glob": ("7.구보", "강남구 제2026-2347호*.pdf"),
        "ranges": [(1, 21)],
        "selected_ranges": [(1, 17)],
        "ingest_step": 4,
        "label_fn": _label_d1,
        "source_id": "gangnam-gubo",
        "source_url": None,
        "source_note": "강남구 구보 제1871호(2026.10.08) 게재, 강남구 공고 제2026-2347호",
        "title": D1_TITLE,
        "short_title": "한양7차 재건축 정비계획(안) 공람",
        "doc_kind": "gongram",
        "issuer": "강남구청장",
        "gosi_no": "강남구 공고 제2026-2347호",
        "published_at": "2026-10-06",
    },
    "D2": {
        "path": ("2.생활권계획", "강남구.pdf"),
        "ranges": [(12, 14), (29, 31), (113, 151)],
        # p29는 장 표지, p30은 빈 쪽이라 추출 대상에서 뺀다 [확인]. 113~151은 seed/d2_selected_pages.yaml
        "selected_ranges": [(12, 14), (31, 31)],
        "ingest_step": 3,
        "label_fn": _label_d2,
        "source_id": "seoul-urban-portal",
        "source_url": "https://urban.seoul.go.kr/view/html/PMNU3040000001",
        "source_note": "2030 서울생활권계획 (2018.3)",
        "title": "2030 서울생활권계획 (강남구)",
        "short_title": "2030 생활권계획 강남구",
        "doc_kind": "plan",
        "issuer": "서울특별시",
        "gosi_no": None,
        "published_at": "2018-03-08",
    },
    "D3": {
        "path": ("3.도시주거환경정비기본계획.pdf",),
        "ranges": [(243, 248), (262, 268), (275, 277)],
        "selected_ranges": [(243, 248), (262, 268), (275, 277)],
        "ingest_step": 2,
        "label_fn": _label_d3,
        "source_id": "seoul-citybuild",
        "source_url": "https://news.seoul.go.kr/citybuild/?p=528131",
        "source_note": "2030 정비기본계획 변경 (서울특별시고시 제2025-348호, 2025.6.26)",
        "title": "2030 서울특별시 도시·주거환경정비기본계획 (2025.6.26 변경)",
        "short_title": "2030 정비기본계획",
        "doc_kind": "plan",
        "issuer": "서울특별시",
        "gosi_no": "서울특별시고시 제2025-348호",
        "published_at": "2025-06-26",
    },
    "D4": {
        "path": ("1.2040서울도시기본계획.pdf",),
        "ranges": [(73, 73), (75, 80), (175, 179)],
        "selected_ranges": [(73, 73), (75, 80), (175, 179)],
        "ingest_step": 1,
        "label_fn": _label_d4,
        "source_id": "seoul-urban-portal",
        "source_url": "https://urban.seoul.go.kr/view/html/PMNU2020000000",
        "source_note": "2040 서울도시기본계획 (2023.2)",
        "title": "2040 서울도시기본계획",
        "short_title": "2040 서울도시기본계획",
        "doc_kind": "plan",
        "issuer": "서울특별시",
        "gosi_no": None,
        "published_at": "2023-01-05",
    },
}

DOC_ORDER = ["D1", "D2", "D3", "D4"]


def original_path(doc_id: str) -> Path:
    """원본 PDF 경로. D1은 glob 결과가 정확히 1개여야 한다."""
    d = DOCS[doc_id]
    if "glob" in d:
        folder, pattern = d["glob"]
        hits = sorted((DATA / folder).glob(pattern))
        if len(hits) != 1:
            fail(f"{doc_id} 원본을 찾을 때 glob 결과가 {len(hits)}개입니다 ({folder}/{pattern}). 정확히 1개여야 합니다.")
        return hits[0]
    p = DATA.joinpath(*d["path"])
    if not p.exists():
        fail(f"{doc_id} 원본 파일이 없습니다: {p}")
    return p


def original_rel(doc_id: str) -> str:
    """'../data/...' 형식의 상대 경로 (DB·manifest 기록용)."""
    p = original_path(doc_id)
    return "../" + p.relative_to(ROOT.parent).as_posix()


def doc_pages(doc_id: str) -> list[int]:
    return expand_ranges(DOCS[doc_id]["ranges"])


def default_selected(doc_id: str, pdf_page: int) -> int:
    return int(pdf_page in expand_ranges(DOCS[doc_id]["selected_ranges"]))


def image_url(doc_id: str, pdf_page: int) -> str:
    return f"/pages/{doc_id}/p{pdf_page:03d}.jpg"
