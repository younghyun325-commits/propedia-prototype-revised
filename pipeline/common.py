"""빌드 스크립트 공통 설정 (agents.md §8-1). 시연 코드(core/, api/)에서 import 하지 않는다."""
import hashlib
import logging
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "data"
BUILD = ROOT / "build"
DB_PATH = ROOT / "db" / "propedia.db"
PUBLIC = ROOT / "public"
SEED = ROOT / "seed"
DATA_RAW = ROOT / "data_raw"
# 공간정보 SHP 원본 (동혁이 직접 둔 파일, 수정·이동 금지 — agents.md §3-6)
SPATIAL = DATA_RAW / "11.공간정보"
SHP_SEOULPLAN = SPATIAL / "서울플랜_사업현황" / "UPIS_C_UQ120.shp"   # 서울플랜+ 사업현황
SHP_UIJE = SPATIAL / "의제처리구역" / "UPIS_C_UQ181.shp"            # 의제처리구역
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


def vacuum_db(path: Path | None = None) -> None:
    """DB 파일을 다시 써서 지운·덮어쓴 행의 옛 바이트를 없앤다 (P15 0단계: 예전 지오코더 좌표가 페이지 빈 공간에 남았음).
    행 내용은 바뀌지 않는다."""
    con = sqlite3.connect(str(path or DB_PATH))
    try:
        con.execute("VACUUM")
    finally:
        con.close()


def mark_patched(by: str, at: str | None = None, path: Path | None = None) -> str:
    """DB를 고친 스크립트가 meta에 마지막 갱신 시각·주체를 남긴다 (P20). as_of(가장 최근 문서 날짜)·build_at(run_all)은 건드리지 않는다.
    실제로 행을 바꿨을 때만 부른다 — 바뀐 것이 없으면 DB 바이트를 그대로 둬야 멱등이다."""
    from datetime import datetime, timedelta, timezone
    at = at or datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    con = sqlite3.connect(str(path or DB_PATH))
    try:
        con.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", [("patched_at", at), ("patched_by", by)])
        con.commit()
    finally:
        con.close()
    return at


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
    # P9 규제 고시 (feedback.md §2-2)
    "gangnam-gongo": {"name": "강남구청 고시공고", "layer": "gu", "url": "https://www.gangnam.go.kr"},
    "sdm-gongji": {"name": "서대문구청 공지", "layer": "gu", "url": "https://www.sdm.go.kr"},
    "law-go-kr": {"name": "국가법령정보센터 행정규칙", "layer": "national", "url": "https://law.go.kr"},
    "molit-press": {"name": "국토교통부 보도자료", "layer": "national", "url": None},
    # P10 강남구 구보 ZIP (feedback2.md §5-1)
    "gangnam-gubo-zip": {"name": "강남구 구보", "layer": "gu", "url": None},
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


def _label_none(p: int) -> str | None:
    return None   # 공고문: 쪽 아래 '- n -'이 읽히면 그 값을 쓴다


# ── 문서 (§3-1 ~ §3-4, D5~D8은 P9) ─────────────────────────
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
    # ── P9: 지금 효력이 있는 규제 고시 (feedback.md §2). 사업 상태를 바꾸지 않는다 ──
    "D5": {
        "glob": ("8.규제고시", "토지거래허가구역재지정및조정공고*.pdf"),
        "ranges": [(1, 9)],
        "selected_ranges": [(1, 2)],          # 3쪽은 안내 한 줄, 4~9쪽은 지형도면 (원문 보기용)
        "ingest_step": 5,
        "label_fn": _label_none,
        "source_id": "gangnam-gongo",
        "source_url": "https://www.gangnam.go.kr/board/B_000046/1075080/view.do?mid=ID05_0410",
        "source_note": "강남구청 고시공고 게시물 붙임 공고문 (서울특별시 공고 제2026-1141호, 2026.4.9)",
        "title": "토지거래허가구역 재지정 및 조정 공고",
        "short_title": "압구정 아파트지구 토지거래허가구역 재지정",
        "doc_kind": "designation",
        "issuer": "서울특별시장",
        "gosi_no": "서울특별시 공고 제2026-1141호",
        "published_at": "2026-04-09",
    },
    "D6": {
        "glob": ("8.규제고시", "토지거래허가구역지정공고*.pdf"),
        "ranges": [(1, 4)],
        "selected_ranges": [(1, 2)],          # 3쪽 지형도면, 4쪽 붙임2 단지 목록(강남구 없음)
        "ingest_step": 6,
        "label_fn": _label_none,
        "source_id": "sdm-gongji",
        "source_url": "https://www.sdm.go.kr/news/notice/notice.do?mode=view&sdmBoardSeq=305997",
        "source_note": "서대문구청 공지 게시물 첨부 공고문 (국토교통부공고 제2025-1219호, 2025.10.15)",
        "title": "토지거래허가구역 지정 공고문",
        "short_title": "서울 전역 아파트 토지거래허가구역 지정",
        "doc_kind": "designation",
        "issuer": "국토교통부장관",
        "gosi_no": "국토교통부공고 제2025-1219호",
        "published_at": "2025-10-15",
    },
    "D7": {
        "glob": ("8.규제고시", "*제2025-1223호*조정대상지역*.pdf"),
        "ranges": [(1, 2)],
        "selected_ranges": [(1, 2)],
        "ingest_step": 7,
        "label_fn": _label_none,
        "source_id": "law-go-kr",
        "source_url": "https://law.go.kr/LSW/admRulInfoP.do?admRulSeq=2100000265026&chrClsCd=010201",
        "source_note": "국가법령정보센터 행정규칙 (국토교통부공고 제2025-1223호, 2025.10.16)",
        "title": "조정대상지역 지정",
        "short_title": "조정대상지역 지정 (서울 21개 구 신규)",
        "doc_kind": "designation",
        "issuer": "국토교통부장관",
        "gosi_no": "국토교통부공고 제2025-1223호",
        "published_at": "2025-10-16",
    },
    "D8": {
        # 투기과열지구 지정 공고문을 구하지 못해 국토교통부 보도참고자료의 현황표를 쓴다 (HUMAN_TODO)
        "glob": ("8.규제고시", "*보도참고*투기과열지구*.pdf"),
        "ranges": [(1, 5)],
        "selected_ranges": [(1, 1), (5, 5)],  # 2쪽 향후 계획, 3~4쪽 규제 효과 표는 추출 대상 아님
        "ingest_step": 8,
        "label_fn": _label_none,
        "source_id": "molit-press",
        "source_url": None,
        "source_note": "국토교통부 보도참고자료 (2026.6.30, 주택정책과) — 지정 공고문이 아님",
        "title": "투기과열지구 및 조정대상지역 추가 지정 (보도참고자료)",
        "short_title": "투기과열지구 현황 (국토부 보도참고자료)",
        "doc_kind": "press",
        "issuer": "국토교통부",
        "gosi_no": None,
        "published_at": "2026-06-30",
    },
}

# ── P10: 강남구 토지 고시 (feedback2.md §5). 구보 ZIP 안의 PDF를 꺼내 쓴다 (ZIP은 수정하지 않음) ──
DOCS["D9"] = {
    "zip": ("10.강남구_토지고시", "69e57c91b3d816.58748850.zip", "강남구 제2026-1034호"),
    "ranges": [(1, 16)],
    "selected_ranges": [(1, 11)],          # 12~16쪽은 도면(관리지역 결정도 등) — 원문 보기·지도 대조용
    "ingest_step": 9,
    "label_fn": _label_none,
    "source_id": "gangnam-gubo-zip",
    "source_url": None,
    "source_note": "강남구 구보 제1846호(2026.04.17) 게재, 강남구 공고 제2026-1034호",
    "title": "대청마을 북측구역(일원동 619번지 일원) 소규모주택정비 관리계획(모아타운 관리계획) 수립(안) 주민공람 공고",
    "short_title": "대청마을 북측 모아타운 관리계획(안) 공람",
    "doc_kind": "gongram",
    "issuer": "강남구청장",
    "gosi_no": "강남구 공고 제2026-1034호",
    "published_at": "2026-04-17",
}
DOCS["D10"] = {
    "zip": ("10.강남구_토지고시", "69dd8efc1d5cb9.48809192.zip", "강남구 제2026-69호"),
    "ranges": [(1, 3)],
    "selected_ranges": [(1, 3)],
    "ingest_step": 10,
    "label_fn": _label_none,
    "source_id": "gangnam-gubo-zip",
    "source_url": None,
    "source_note": "강남구 구보 제1845호(2026.04.10) 게재, 강남구 고시 제2026-69호",
    "title": "개발행위허가 제한 연장 및 지형도면 고시",
    "short_title": "대치동 506 일대 개발행위허가 제한 연장",
    "doc_kind": "restriction",
    "issuer": "강남구청장",
    "gosi_no": "강남구 고시 제2026-69호",
    "published_at": "2026-04-10",
}

DOC_ORDER = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10"]
ZIP_SRC = BUILD / "zip_src"


def zip_member_name(info: zipfile.ZipInfo) -> str:
    """ZIP 안 파일명: UTF-8 플래그가 없으면 CP949로 저장된 이름이다 (feedback2.md §5-1)."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def _zip_member(doc_id: str) -> tuple[Path, zipfile.ZipInfo, str]:
    folder, zname, needle = DOCS[doc_id]["zip"]
    zpath = DATA / folder / zname
    if not zpath.exists():
        fail(f"{doc_id} ZIP이 없습니다: {zpath}")
    with zipfile.ZipFile(zpath) as zf:
        hits = [(i, zip_member_name(i)) for i in zf.infolist()
                if needle in zip_member_name(i) and zip_member_name(i).lower().endswith(".pdf")]
    if len(hits) != 1:
        fail(f"{doc_id}: ZIP 안에서 '{needle}' PDF가 {len(hits)}개입니다. 정확히 1개여야 합니다.")
    return zpath, hits[0][0], hits[0][1]


def original_path(doc_id: str) -> Path:
    """원본 PDF 경로. glob으로 찾는 문서(D1, D5~D8)는 결과가 정확히 1개여야 한다.
    ZIP 안 문서(D9·D10)는 build/zip_src/{doc}.pdf로 꺼내 그 경로를 돌려준다 (ZIP은 읽기만 한다)."""
    d = DOCS[doc_id]
    if "zip" in d:
        out = ZIP_SRC / f"{doc_id}.pdf"
        if not out.exists():
            zpath, info, _ = _zip_member(doc_id)
            ZIP_SRC.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zpath) as zf:
                out.write_bytes(zf.read(info))
        return out
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
    """'../data/...' 형식의 상대 경로 (DB·manifest 기록용). ZIP 안 문서는 '../data/…/x.zip!/파일명.pdf'."""
    if "zip" in DOCS[doc_id]:
        zpath, _, member = _zip_member(doc_id)
        return "../" + zpath.relative_to(ROOT.parent).as_posix() + "!/" + member
    p = original_path(doc_id)
    return "../" + p.relative_to(ROOT.parent).as_posix()


def doc_pages(doc_id: str) -> list[int]:
    return expand_ranges(DOCS[doc_id]["ranges"])


def default_selected(doc_id: str, pdf_page: int) -> int:
    return int(pdf_page in expand_ranges(DOCS[doc_id]["selected_ranges"]))


def image_url(doc_id: str, pdf_page: int) -> str:
    return f"/pages/{doc_id}/p{pdf_page:03d}.jpg"
