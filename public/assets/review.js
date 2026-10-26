/* 검수 화면 (agents.md §12-5) */
'use strict';

const STATUS = { approve: ['승인', 'ok'], reject: ['반려', 'warn'], edit: ['수정', 'info'] };
const CURRENT_LABELS = {
  project: '사업', jibun: '지번', pnu: 'PNU', inclusion: '현재 판정', basis: '판정 근거', item_key: '항목 키',
  title: '제목', summary: '요약', scope_type: '적용 범위', scope_ref: '범위 값', scope_note: '범위 메모',
  confidence: '신뢰도', field: '필드', value: '값', rule: '단계 규칙', code: '단계', candidate: '추출 후보',
  tier: '층 분류',
};
const TIER_TEXT = { applies: '적용 (4개 층에 표시)', background: '배경 (참고·문서 DB에만)' };
const INCLUSION_TEXT = { possible: '포함될 수 있음', included: '포함' };
const SCOPE_TYPES = ['SIDO', 'SGG', 'SAENGHWAL', 'BJD', 'PARCEL'];
let queue = [];
let selectedId = null;

function statusBadge(id) {
  const d = decisionFor(id);
  if (!d) return badge('미결정', 'muted');
  const [t, k] = STATUS[d.action] || [d.action, 'muted'];
  return badge(t, k);
}

function renderList() {
  el('queue-body').innerHTML = queue.map((q) => `<tr class="clickable ${q.id === selectedId ? 'selected' : ''}" data-id="${q.id}">
      <td>${q.id}</td><td>${badge(q.item_type_label, q.item_type === 'parcel_inclusion' ? 'warn' : 'muted')}</td>
      <td>${esc(q.title)}</td><td class="small">${esc(q.reason)}</td><td>${statusBadge(q.id)}</td></tr>`).join('');
}

function currentTable(cur) {
  const rows = Object.entries(cur || {}).filter(([k]) => !['evidence', 'pdf_page'].includes(k));
  return `<table>${rows.map(([k, v]) => {
    let val = Array.isArray(v) ? v.join(', ') : v;
    if (k === 'inclusion') val = INCLUSION_TEXT[v] || v;
    if (k === 'tier') val = TIER_TEXT[v] || v;
    if (k === 'basis' && v === 'representative_only') val = '대표 지번만 있음 (representative_only)';
    return `<tr><th>${esc(CURRENT_LABELS[k] || k)}</th><td>${esc(val)}</td></tr>`;
  }).join('')}</table>`;
}

function editForm(q) {
  const cur = q.proposed.current || {};
  const prev = decisionFor(q.id);
  const e = (prev && prev.action === 'edit' && prev.edits) || {};
  return `<details class="card soft" ${prev && prev.action === 'edit' ? 'open' : ''}><summary>수정해서 확정</summary>
    <label class="small muted">요약</label>
    <textarea id="edit-summary">${esc(e.summary || cur.summary || '')}</textarea>
    <div class="row" style="margin-top:8px">
      <label class="small muted">적용 범위</label>
      <select id="edit-scope-type">${SCOPE_TYPES.map((t) =>
        `<option value="${t}" ${(e.scope_type || cur.scope_type) === t ? 'selected' : ''}>${t}</option>`).join('')}</select>
      <label class="small muted">범위 값 (쉼표로 구분)</label>
      <input type="text" id="edit-scope-ref" value="${esc((e.scope_ref || cur.scope_ref || []).join(', '))}" style="min-width:260px">
    </div>
    ${(q.proposed.editable_fields || []).includes('tier') ? `<div class="row" style="margin-top:8px">
      <label class="small muted">층 분류</label>
      <select id="edit-tier">${Object.entries(TIER_TEXT).map(([t, label]) =>
        `<option value="${t}" ${(e.tier || cur.tier) === t ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select>
    </div>` : ''}
    <p class="small muted">범위 값 예: SIDO → 11 / SGG → 11680 / SAENGHWAL → 압구정·청담 / BJD → 1168011000 / PARCEL → PNU 19자리</p>
    <button class="btn primary" type="button" data-act="edit">수정 내용으로 확정</button>
  </details>`;
}

function renderDetail() {
  const q = queue.find((x) => x.id === selectedId);
  if (!q) { el('detail').innerHTML = '<p class="muted">목록에서 검수할 항목을 고르세요.</p>'; return; }
  const cur = q.proposed.current || {};
  const options = q.proposed.options || ['approve', 'reject'];
  const editable = (q.proposed.editable_fields || []).length > 0;
  const ev = cur.evidence;
  el('detail').innerHTML = `<div class="card">
    <div class="row"><h2 style="margin:0">#${q.id} ${esc(q.title)}</h2>${badge(q.item_type_label, 'warn')}${statusBadge(q.id)}</div>
    <p class="small">${esc(q.reason)}</p>
    <div class="split">
      <div>${q.source && q.source.page_image ? `<img class="page-img" src="${esc(q.source.page_image)}" alt="원문 쪽 이미지">` : ''}</div>
      <div>
        <h3>현재 값</h3>
        ${currentTable(cur)}
        ${ev ? `<div class="evidence" style="margin-top:10px"><b>근거 문장</b> · ${esc(ev)}</div>` : ''}
        <div class="src">출처 · ${esc(sourceLine(q.source))} ${pageButton(q.source, ev, '크게 보기')}</div>
        <div class="actions" style="margin-top:12px">
          ${options.includes('approve') ? '<button class="btn ok" type="button" data-act="approve">승인</button>' : ''}
          ${options.includes('reject') ? '<button class="btn warn" type="button" data-act="reject">반려</button>' : ''}
          ${decisionFor(q.id) ? '<button class="btn small" type="button" data-act="undo">이 결정 취소</button>' : ''}
        </div>
        ${q.item_type === 'parcel_inclusion'
          ? '<p class="small muted">승인하면 이 필지는 "포함"(근거: 사람 검수), 반려하면 포함 목록에서 빠집니다.</p>'
          : '<p class="small muted">승인하면 "검수 필요" 표시가 사라지고, 반려하면 조회 결과에서 빠집니다.</p>'}
        ${editable && options.includes('edit') ? editForm(q) : ''}
      </div>
    </div>
  </div>`;
}

function decide(action) {
  const q = queue.find((x) => x.id === selectedId);
  if (!q) return;
  if (action === 'undo') {
    setDecisions(getDecisions().filter((d) => d.review_id !== q.id));
    el('decided').innerHTML = '<div class="box info">결정을 취소했습니다.</div>';
  } else {
    const d = { review_id: q.id, action };
    if (action === 'edit') {
      const refs = el('edit-scope-ref').value.split(',').map((s) => s.trim()).filter(Boolean);
      d.edits = { summary: el('edit-summary').value.trim(), scope_type: el('edit-scope-type').value, scope_ref: refs };
      if (el('edit-tier')) d.edits.tier = el('edit-tier').value;
      if (!d.edits.summary || !refs.length) { toast('요약과 범위 값을 채워 주세요'); return; }
    }
    upsertDecision(d);
    const link = '<a class="btn small primary" href="lookup.html?addr=A1">주소 조회에서 확인 (압구정동 527)</a>';
    el('decided').innerHTML = `<div class="box ok row"><span>결정이 저장되었습니다. 주소 조회 화면에서 확인하세요.</span>${link}</div>`;
  }
  renderDecisionStatus();
  renderList();
  renderDetail();
}

function select(id) {
  selectedId = id;
  window.history.replaceState(null, '', `review.html?id=${id}`);
  renderList();
  renderDetail();
}

document.addEventListener('click', (e) => {
  const row = e.target.closest('tr[data-id]');
  if (row) { select(Number(row.dataset.id)); return; }
  const act = e.target.closest('[data-act]');
  if (act) decide(act.dataset.act);
});

(async () => {
  await initShell('review');
  el('reset-all').addEventListener('click', () => {
    clearDecisions();
    renderDecisionStatus();
    renderList();
    renderDetail();
    el('decided').innerHTML = '<div class="box info">시연을 초기화했습니다. 모든 검수 결정을 지웠습니다.</div>';
  });
  queue = await api('/api/v1/review-queue');
  const id = Number(qs('id'));
  selectedId = queue.some((q) => q.id === id) ? id : (queue[0] ? queue[0].id : null);
  renderList();
  renderDetail();
})();
