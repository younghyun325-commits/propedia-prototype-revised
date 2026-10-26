"""검수 결정 적용 — 서버에 저장하지 않고 요청마다 받은 결정을 반영한다 (agents.md §10-7).

결정 형식: {"review_id": 3, "action": "approve"|"reject"|"edit",
           "edits": {"summary": "...", "scope_type": "...", "scope_ref": [...], "tier": "applies"|"background"},
           "decided_at": "ISO"}
"""
from dataclasses import dataclass, field

from core.db import loads

ACTIONS = {"approve", "reject", "edit"}
SCOPE_TYPES = {"SIDO", "SGG", "SAENGHWAL", "BJD", "PARCEL"}
TIERS = {"applies", "background"}
ITEM_TYPES = {"vision_item", "scope_uncertain", "evidence_mismatch"}
ACTION_LABELS = {"approve": "승인", "reject": "반려", "edit": "수정"}


@dataclass
class Overrides:
    parcel: dict = field(default_factory=dict)          # (project_id, pnu) -> 'approve' | 'reject'
    items_rejected: set = field(default_factory=set)    # item_key
    items_approved: set = field(default_factory=set)    # item_key (검수 필요 표시 제거)
    items_edits: dict = field(default_factory=dict)     # item_key -> {summary, scope_type, scope_ref, tier}
    display: dict = field(default_factory=dict)         # 'D1:area_m2' / project_id -> action (문서 DB 화면용)
    review_applied: list = field(default_factory=list)
    events: list = field(default_factory=list)


def _clean_edits(edits, editable: list) -> tuple[dict, str | None]:
    if not isinstance(edits, dict):
        return {}, "edits가 객체가 아님"
    out = {}
    for k, v in edits.items():
        if k not in editable:
            continue
        if k == "summary":
            if not isinstance(v, str) or not v.strip():
                return {}, "summary가 비어 있음"
            out[k] = v.strip()
        elif k == "scope_type":
            if v not in SCOPE_TYPES:
                return {}, f"scope_type 값이 올바르지 않음: {v}"
            out[k] = v
        elif k == "scope_ref":
            if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
                return {}, "scope_ref는 문자열 배열이어야 함"
            out[k] = v
        elif k == "tier":
            if v not in TIERS:
                return {}, f"tier 값이 올바르지 않음: {v}"
            out[k] = v
    if not out:
        return {}, "수정할 수 있는 값이 없음"
    return out, None


def apply(con, decisions) -> Overrides:
    ov = Overrides()
    if not decisions:
        return ov
    if not isinstance(decisions, list):
        ov.review_applied.append({"review_id": None, "ignored": "decisions는 배열이어야 함"})
        return ov
    rows = {r["id"]: r for r in con.execute("SELECT * FROM review_queue")}
    for d in decisions:
        rid = d.get("review_id") if isinstance(d, dict) else None
        action = d.get("action") if isinstance(d, dict) else None
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            ov.review_applied.append({"review_id": rid, "ignored": "review_id가 숫자가 아님"})
            continue
        row = rows.get(rid)
        if row is None:
            ov.review_applied.append({"review_id": rid, "ignored": "없는 검수 항목"})
            continue
        if action not in ACTIONS:
            ov.review_applied.append({"review_id": rid, "ignored": f"잘못된 action: {action}"})
            continue
        proposed = loads(row["proposed"], {}) or {}
        editable = proposed.get("editable_fields") or []
        options = proposed.get("options") or list(ACTIONS)
        if action not in options:
            ov.review_applied.append({"review_id": rid, "ignored": f"이 항목에서 쓸 수 없는 action: {action}"})
            continue
        it, ref = row["item_type"], row["ref_key"]
        if it == "parcel_inclusion":
            pid, _, pnu = ref.partition(":")
            ov.parcel[(int(pid), pnu)] = action
        elif it == "parcel_group":
            # 지도 대조 후보 묶음 (feedback2.md §5-4): 승인하면 전부 포함, edits.exclude_pnus의 필지는 반려
            pid = int(ref.partition(":")[0])
            pnus = [p["pnu"] for p in (proposed.get("current") or {}).get("parcels", [])]
            excl = (d.get("edits") or {}).get("exclude_pnus") or []
            if not isinstance(excl, list) or not all(isinstance(x, str) for x in excl):
                ov.review_applied.append({"review_id": rid, "ignored": "exclude_pnus는 문자열 배열이어야 함"})
                continue
            for pnu in pnus:
                ov.parcel[(pid, pnu)] = "reject" if action == "reject" or pnu in excl else "approve"
        elif it in ITEM_TYPES and row["ref_table"] == "applicability_rules":
            ov.items_rejected.discard(ref)
            ov.items_approved.discard(ref)
            ov.items_edits.pop(ref, None)
            if action == "approve":
                ov.items_approved.add(ref)
            elif action == "reject":
                ov.items_rejected.add(ref)
            else:
                edits, err = _clean_edits(d.get("edits"), editable)
                if err:
                    ov.review_applied.append({"review_id": rid, "ignored": err})
                    continue
                ov.items_edits[ref] = edits
                ov.items_approved.add(ref)
        else:
            ov.display[ref] = action
        ov.review_applied.append({"review_id": rid, "action": action, "status": "applied"})
        ov.events.append({"event_type": "review_decision", "review_id": rid, "action": action,
                          "action_label": ACTION_LABELS[action], "title": row["title"]})
    return ov
