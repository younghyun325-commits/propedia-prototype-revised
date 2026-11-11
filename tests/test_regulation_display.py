"""P22-1 요청 13: 조정대상지역·투기과열지구 화면 문구가 칩·필지 패널·규제 인스펙터에서 같고, 원문 제목은 그대로다."""
import json
from datetime import date

from core import map as map_mod
from core.regulation_display import DISPLAY, SEOUL_25, SEOUL_25_DETAIL

TODAY = date(2026, 11, 10)
PNU_YEOKSAM_823 = "1168010100108230000"


def test_original_titles_untouched():
    for doc, key in (("D7", "D7-01"), ("D8", "D8-01")):
        items = json.loads((map_mod.ROOT / "extractions" / f"{doc}.json").read_text(encoding="utf-8"))["items"]
        orig = next(it for it in items if it["item_key"] == key)
        assert orig["title"] != DISPLAY[key]["title"]


def test_chip_and_inspector_same_source(client, con):
    notices = {n["item_key"]: n for n in client.get("/api/v1/map/notices", params={"as_of": TODAY.isoformat()}).json()["items"]}
    for key, doc in (("D7-01", "D7"), ("D8-01", "D8")):
        n = notices[key]
        assert n["chip_label"] == DISPLAY[key]["chip"] and n["chip_label"].endswith(SEOUL_25)
        assert "(" not in n["chip_label"]
        assert n["display_title"] == DISPLAY[key]["title"] and n["display_title"].endswith(SEOUL_25_DETAIL)
        assert "21개 구" not in n["chip_label"]
        f = map_mod.map_feature(con, "regulation", doc, None, TODAY)
        assert f["title"] == n["chip_label"]
        assert f["subtitle"] == n["display_title"]
        assert f["sections"]["regulation"]["display_title"] == n["display_title"]
        assert f["sections"]["regulation"]["display_basis"]
    d6 = notices["D6-01"]
    assert d6["chip_label"] == d6["short_title"] and d6["display_title"] == d6["title"]


def test_parcel_panel_uses_same_title(con):
    f = map_mod.map_feature(con, "parcel", f"parcel:{PNU_YEOKSAM_823}", None, TODAY)
    by = {it["item_key"]: it for it in f["sections"]["parcel"]["layer_items"]["city"]}
    for key in ("D7-01", "D8-01"):
        assert by[key]["display_title"] == DISPLAY[key]["title"]
        assert by[key]["title"] != DISPLAY[key]["title"]
