/* 문서 DB 화면 (agents.md §12-4) */
'use strict';

const STATUS_LABELS = { ok: ['텍스트 확보', 'ok'], partial: ['일부 확보', 'warn'], failed: ['실패', 'warn'] };
const METHOD_KIND = { text: 'info', 'vision-claude': 'warn', 'image-only': 'muted' };
let docs = [];
let current = null;   // 문서 상세
let steps = [];

function pct(v) { return v === null || v === undefined ? '—' : `${Math.round(v * 1000) / 10}%`; }

function docCard(d) {
  const [st, kind] = STATUS_LABELS[d.text_status] || [d.text_status, 'muted'];
  return `<div class="card doc-card ${current && current.document.doc_id === d.doc_id ? 'active' : ''}" data-doc="${esc(d.doc_id)}">
    <div class="row"><b>${esc(d.doc_id)}</b>${badge(`투입 ${d.ingest_step}단계`, 'muted')}${badge(d.doc_kind_label, 'info')}</div>
    <h3 style="margin:6px 0">${esc(d.short_title)}</h3>
    <div class="meta">발행 ${fmtDate(d.published_at)} · 쪽 ${esc(d.page_ranges)}</div>
    <div class="meta">${badge(st, kind)} 선택 쪽 ${d.pages_text_ok}/${d.pages_selected} 텍스트 확보</div>
    <div class="meta">항목 ${d.items}개 · 근거 일치 ${d.evidence_ok}/${d.evidence_total} (${pct(d.evidence_ok_rate)})</div>
    <div class="meta">출처 · ${esc(d.source.name || '')} ${d.source.source_url ? `<a href="${esc(d.source.source_url)}" target="_blank" rel="noopener">게시처</a>` : ''}</div>
  </div>`;
}

function renderCards() {
  el('doc-cards').innerHTML = docs.map(docCard).join('');
}

function fieldsTable(fields) {
  if (!fields.length) return '';
  return `<h3 style="margin-top:16px">필드 (D1 공고문에서 추출)</h3>
    <div class="table-wrap"><table><thead><tr><th>필드</th><th>값</th><th>단위</th><th>쪽</th><th>신뢰도</th><th>근거 일치</th><th></th></tr></thead><tbody>
    ${fields.map((f) => `<tr>
      <td>${esc(f.label)} <span class="small muted mono">${esc(f.field)}</span></td>
      <td>${f.value === null ? `<span class="muted">없음 (${esc(f.null_reason || '')})</span>` :
        Array.isArray(f.value) ? esc(f.value.join(', ')) : fmtNum(f.value)}</td>
      <td>${esc(f.unit || '')}</td>
      <td><button class="linkbtn" type="button" data-goto-page="${f.pdf_page}">p${f.pdf_page}</button></td>
      <td>${f.confidence}</td>
      <td>${f.evidence_ok ? badge('일치', 'ok') : badge('불일치', 'warn')}</td>
      <td>${pageButton(f.source, f.evidence, '원문')}</td>
    </tr>`).join('')}
    </tbody></table></div>`;
}

function projectsBox(projects) {
  if (!projects.length) return '';
  return `<h3 style="margin-top:16px">사업 카드로 묶인 결과</h3>
    ${projects.map((p) => `<div class="item"><div class="row"><b>${esc(p.name)}</b>
      ${badge(`${p.stage.code} ${p.stage.title}`, 'info')}<span class="small muted">단계 규칙 ${esc(p.stage_rule)} (문서 제목 기준)</span></div>
      <div class="small">${esc(p.location_text || '')}</div>
      <div class="actions">${p.project_key === 'ilwon-daecheong-north-moatown'
        ? '<a class="btn small primary" href="lookup.html?addr=B1">주소 조회에서 보기 (대청마을 일원동 619)</a>'
        : '<a class="btn small primary" href="lookup.html?addr=A1">주소 조회에서 보기 (압구정동 527)</a>'}</div></div>`).join('')}`;
}

function itemsList(items, title) {
  if (!items.length) return '';
  return `<h3 style="margin-top:16px">${esc(title)}</h3>
    <p class="small muted">적용 = 주소 조회의 4개 층에 표시 · 배경 = 4개 층에서 빼고 문서 DB(일부는 참고 섹션)에서만 표시</p>
    ${items.map((it) => `<div class="item">
      <div class="row"><span class="mono small">${esc(it.item_key)}</span><span class="item-title">${esc(it.title)}</span>
        ${badge(it.tier_label, it.tier === 'applies' ? 'ok' : 'muted')}
        ${badge(it.item_type_label, 'muted')}${badge(it.scope_type, 'info')}${it.needs_review ? badge('검수 필요', 'warn') : ''}
        ${it.evidence_ok ? badge('근거 일치', 'ok') : badge('근거 불일치', 'warn')}
        ${it.effective_status ? badge(`${it.effective_status_label} · ${it.effective_label}`, it.effective_status === 'in_force' ? 'ok' : 'muted') : ''}</div>
      <p class="small">${esc(it.summary)}</p>
      ${it.target_note ? `<div class="target-note small">${esc(it.target_note)}</div>` : ''}
      <div class="small muted">분류 이유: ${esc(it.tier_reason || '—')}${it.tier_class ? ` (구분 ${esc(it.tier_class)}${it.applies_rank ? `·${it.applies_rank}` : ''})` : ''}${it.reference_rank ? ` · 참고 순서 ${it.reference_rank}` : ''}</div>
      <div class="small muted">신뢰도 ${it.confidence} · <button class="linkbtn" type="button" data-goto-page="${it.pdf_page}">p${it.pdf_page}</button>
        ${(it.more_evidence || []).map((m) => `· ${esc(m.label)} <button class="linkbtn" type="button" data-goto-page="${m.pdf_page}">p${m.pdf_page}</button>`).join(' ')}</div>
    </div>`).join('')}`;
}

async function showDoc(docId, page) {
  current = await api(`/api/v1/documents/${encodeURIComponent(docId)}`);
  renderCards();
  const d = current.document;
  const pages = current.pages.map((p) => `<button type="button" class="page-btn ${p.selected ? '' : 'unsel'} ${p.method === 'vision-claude' ? 'vision' : ''}"
      data-page="${p.pdf_page}" title="${esc(`${p.method_label} · ${p.char_count}자${p.selected ? '' : ' · 추출 대상 아님'}`)}">p${p.pdf_page}</button>`).join('');
  el('doc-detail').innerHTML = `
    <div class="card">
      <div class="row"><h2 style="margin:0">${esc(d.doc_id)} · ${esc(d.short_title)}</h2></div>
      <p class="small muted">${esc(d.title)}</p>
      <div class="small">발행 ${fmtDate(d.published_at)} · ${esc(d.issuer || '')} ${d.gosi_no ? `· ${esc(d.gosi_no)}` : ''} · 원본 <span class="mono">${esc(d.original_path)}</span>
        · 발췌본 <span class="mono">${esc(d.excerpt_path)}</span> · sha256 <span class="mono">${esc(d.content_hash.slice(0, 12))}…</span></div>
      <h3 style="margin-top:14px">쪽 목록 <span class="small muted">(테두리 주황 = 이미지 쪽 전사, 회색 = 추출 대상 아님)</span></h3>
      <div class="page-list" id="page-list">${pages}</div>
      <div id="page-view" style="margin-top:12px"></div>
      ${fieldsTable(current.fields)}
      ${projectsBox(current.projects)}
      ${itemsList(current.items, '항목 (4개 층에 나가는 단위)')}
      ${current.extraction ? `<details class="card soft" style="margin-top:14px"><summary>추출 JSON 원문 (${esc(current.extraction.extractor_version)}, ${esc(current.extraction.extracted_at)})</summary>
        <pre>${esc(JSON.stringify(current.extraction.payload, null, 2))}</pre></details>` : ''}
    </div>`;
  const first = page || (current.pages.find((p) => p.selected) || current.pages[0]).pdf_page;
  showPage(first);
}

async function showPage(pdfPage) {
  if (!current) return;
  const d = current.document;
  document.querySelectorAll('.page-btn').forEach((b) => b.classList.toggle('active', Number(b.dataset.page) === pdfPage));
  const p = await api(`/api/v1/documents/${encodeURIComponent(d.doc_id)}/pages/${pdfPage}`);
  window.history.replaceState(null, '', `docs.html?doc=${encodeURIComponent(d.doc_id)}&page=${pdfPage}${window.location.hash}`);
  const onPage = [...p.items.map((i) => `<li><span class="mono small">${esc(i.item_key)}</span> ${esc(i.title)}
      ${i.evidence_ok ? badge('근거 일치', 'ok') : badge('근거 불일치', 'warn')} <span class="small muted">신뢰도 ${i.confidence}</span></li>`),
    ...p.fields.map((f) => `<li>필드 <b>${esc(f.label)}</b> = ${Array.isArray(f.value) ? esc(f.value.join(', ')) : fmtNum(f.value)} ${esc(f.unit || '')}
      ${f.evidence_ok ? badge('근거 일치', 'ok') : badge('근거 불일치', 'warn')} <span class="small muted">신뢰도 ${f.confidence}</span></li>`),
    ...p.project_evidences.map((e) => `<li>사업 카드 근거 <span class="small muted">(${esc(e.what)})</span></li>`)];
  el('page-view').innerHTML = `
    <div class="row"><b>p${p.pdf_page}</b>${p.page_label ? `<span class="small muted">인쇄 ${esc(p.page_label)}쪽</span>` : ''}
      ${badge(p.method_label, METHOD_KIND[p.method] || 'muted')}<span class="small muted">${p.char_count}자</span>
      ${p.selected ? '' : badge('추출 대상 아님', 'muted')}
      ${p.method === 'vision-claude' ? '<span class="small muted">이미지 쪽을 Claude Code가 보이는 그대로 옮겨 적은 텍스트입니다 (검수 대상)</span>' : ''}</div>
    <div class="split" style="margin-top:8px">
      <div><img class="page-img" src="${esc(p.image_url)}" alt="${esc(`${d.doc_id} ${p.pdf_page}쪽 이미지`)}"></div>
      <div><pre class="page-text">${p.text ? highlight(p.text, p.evidences) : '<span class="muted">(텍스트 없음)</span>'}</pre>
        <h3 style="margin-top:10px">이 쪽에서 나온 것 <span class="small muted">(노란색 = 근거 문장 위치)</span></h3>
        <ul class="small">${onPage.join('') || '<li class="muted">없음</li>'}</ul></div>
    </div>`;
}

function stepDetail(k) {
  document.querySelectorAll('.step-btn').forEach((b) => b.classList.toggle('active', Number(b.dataset.step) === k));
  const s = steps.find((x) => x.step === k);
  if (!s) return;
  const evs = s.events.length
    ? `<table><thead><tr><th>변경 기록</th><th>사업</th><th>이전</th><th>이후</th></tr></thead><tbody>
       ${s.events.map((e) => `<tr><td>${badge(e.event_label, 'info')}</td><td>${esc(e.project_name || '')}</td>
         <td class="small mono">${esc(e.before ? JSON.stringify(e.before) : '—')}</td>
         <td class="small mono">${esc(JSON.stringify(e.after))}</td></tr>`).join('')}
       </tbody></table>`
    : '<div class="box info">사업 상태 변화 없음 — 이벤트를 만들지 않습니다</div>';
  el('step-detail').innerHTML = `<div class="card"><div class="row"><b>${k}단계 투입: ${esc(s.doc_id)} · ${esc(s.short_title)}</b>
    <span class="small muted">발행 ${fmtDate(s.published_at)}</span></div>${evs}</div>`;
}

document.addEventListener('click', (e) => {
  const card = e.target.closest('[data-doc]');
  if (card) { showDoc(card.dataset.doc); return; }
  const pb = e.target.closest('[data-page]');
  if (pb) { showPage(Number(pb.dataset.page)); return; }
  const gp = e.target.closest('[data-goto-page]');
  if (gp) { showPage(Number(gp.dataset.gotoPage)); el('page-view').scrollIntoView({ behavior: 'smooth' }); return; }
  const sb = e.target.closest('[data-step]');
  if (sb) stepDetail(Number(sb.dataset.step));
});

(async () => {
  await initShell('docs');
  docs = await api('/api/v1/documents');
  renderCards();
  steps = await api('/api/v1/events');
  el('step-buttons').innerHTML = steps.map((s) => `<button class="step-btn" type="button" data-step="${s.step}">
    <b>${s.step}단계 · ${esc(s.doc_id)}</b><small>${esc(s.short_title)} · 변경 ${s.events.length}건</small></button>`).join('');
  // 처음에는 변경 기록이 생긴 마지막 단계(D1 투입)를 보여준다. 5~8단계 규제 고시는 사업 상태를 바꾸지 않는다
  const withEvents = steps.filter((s) => s.events.length);
  stepDetail((withEvents[withEvents.length - 1] || steps[steps.length - 1] || { step: 1 }).step);
  const doc = qs('doc');
  if (doc) {
    await showDoc(doc, Number(qs('page')) || null);
  }
  if (window.location.hash === '#steps') el('steps').scrollIntoView();
})();
