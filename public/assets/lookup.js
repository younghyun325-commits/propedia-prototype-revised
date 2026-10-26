/* 주소 조회 화면 (agents.md §12-3) */
'use strict';

let demoList = [];

const EFFECTIVE_KIND = { in_force: 'ok', not_started: 'info', ended: 'muted' };

function effectiveBadge(it) {
  if (!it.effective_status) return '';
  return `<span class="effective">${badge(it.effective_status_label, EFFECTIVE_KIND[it.effective_status] || 'muted')}
    <span class="small muted">${esc(it.effective_label)}</span></span>`;
}

function itemCard(it, extraBadge) {
  const more = (it.more_evidence || []).map((m) => `<div class="evidence"><b>${esc(m.label)}</b> · ${esc(m.evidence)}
      ${m.evidence_ok ? '' : badge('근거 확인 필요', 'warn')} ${pageButton(m.source, m.evidence, `원문 p${m.source ? m.source.pdf_page : ''}`)}</div>`).join('');
  return `<div class="item">
    <div class="row">
      <span class="item-title">${esc(it.title)}</span>
      ${it.scope_type === 'SAENGHWAL' ? '' : badge(it.scope_label, 'info')}
      ${extraBadge || ''}
      ${it.needs_review ? badge('검수 필요', 'warn') : ''}
      ${it.evidence_ok ? '' : badge('근거 확인 필요', 'warn')}
      ${it.edited ? badge('검수에서 수정됨', 'muted') : ''}
    </div>
    ${effectiveBadge(it)}
    <p>${esc(it.summary)}</p>
    ${it.target_note ? `<div class="target-note small">${esc(it.target_note)}</div>` : ''}
    <div class="src">출처 · ${esc(sourceLine(it.source))}</div>
    <div class="actions">
      ${pageButton(it.source, it.evidence)}
      <details><summary>근거 보기</summary>
        <div class="evidence">${esc(it.evidence)}</div>
        ${more}
        ${it.scope_note ? `<div class="small muted">적용 범위 메모: ${esc(it.scope_note)}</div>` : ''}
      </details>
    </div>
  </div>`;
}

const LAYER_SHORT = { city: '서울 전역', gu: '자치구', dong: '법정동', parcel: '필지' };

function referenceHtml(ref) {
  if (!ref) return '';
  const items = ref.items || [];
  return `<details class="card soft reference" id="reference">
    <summary><b>참고: 배경 설명과 참고 계획 (${items.length})</b></summary>
    <p class="small muted">${esc(ref.note)}</p>
    ${items.length ? items.map((it) => itemCard(it, badge(`${LAYER_SHORT[it.layer] || it.layer} · ${it.reference_reason}`, 'muted'))
      + (it.tier_reason ? `<div class="small muted" style="margin:-4px 0 8px 4px">분류 이유: ${esc(it.tier_reason)}</div>` : '')).join('')
      : '<div class="empty">참고로 보여줄 항목이 없습니다</div>'}
  </details>`;
}

function buildingHtml(P) {
  const b = P.building;
  if (!b) return `<div class="item"><b>건축물 요약</b> <span class="muted">${esc(P.building_note || '')}</span></div>`;
  return `<div class="item building">
    <div class="row"><b>건축물 요약</b><span class="small muted">주건축물 ${b.main_count}동 기준</span></div>
    <div class="table-wrap"><table><thead><tr><th>건물명</th><th>주용도</th><th>구조</th><th>최고 층수</th><th>세대수</th><th>연면적</th><th>사용승인일</th></tr></thead>
    <tbody><tr><td>${esc((b.bld_names || []).join(', ') || '—')}</td><td>${esc(b.main_purpose || '—')}</td><td>${esc(b.structure || '—')}</td>
      <td>지상 ${b.max_grnd_flr ?? '—'}층${b.max_ugrnd_flr ? ` · 지하 ${b.max_ugrnd_flr}층` : ''}</td>
      <td>${b.total_hhld ? fmtNum(b.total_hhld) : '—'}</td><td>${b.total_area ? `${fmtNum(b.total_area)}㎡` : '—'}</td>
      <td>${b.use_apr_day ? fmtDate(b.use_apr_day) : '—'}</td></tr></tbody></table></div>
    <div class="src">출처 · ${esc(b.source)} · ${esc(b.fetched_label)}</div>
  </div>`;
}

function itemsHtml(items) {
  if (!items || !items.length) return '<div class="empty">이 층에 해당하는 항목이 없습니다</div>';
  return items.map((it) => itemCard(it)).join('');
}

function layer(title, code, count, body, id) {
  return `<section class="layer" id="${id}">
    <div class="layer-head"><h2>${esc(title)}</h2>${badge(`${count}건`, count ? 'info' : 'muted')}
      <span class="layer-code">${esc(code)}</span></div>
    <div class="layer-body">${body}</div>
  </section>`;
}

function stageTable(byStage) {
  const rows = Object.entries(byStage || {});
  if (!rows.length) return '';
  return `<h3 style="margin-top:14px">강남구 진행 사업 단계 분포</h3>
    <table><thead><tr><th>단계 코드</th><th>단계</th><th>사업 수</th></tr></thead><tbody>
    ${rows.map(([code, v]) => `<tr><td class="mono">${esc(code)}</td><td>${esc(v.title)}</td><td>${v.count}</td></tr>`).join('')}
    </tbody></table>
    <p class="small muted">프리토타입에 반영된 사업(고시 기준)만 셉니다.</p>`;
}

function deadlineTable(rows, withProject) {
  if (!rows || !rows.length) return '<div class="empty">진행 중인 기한이 없습니다</div>';
  return `<div class="table-wrap"><table><thead><tr>
      ${withProject ? '<th>사업</th>' : ''}<th>기한</th><th>기간</th><th>남은 날</th><th>제출 방법</th><th>장소</th><th>출처</th>
    </tr></thead><tbody>
    ${rows.map((d) => `<tr>
      ${withProject ? `<td>${esc(d.project_name)}</td>` : ''}
      <td><b>${esc(d.title)}</b></td>
      <td>${fmtDate(d.starts_on)} ~ ${fmtDate(d.due_on)}</td>
      <td class="dday">${badge(d.d_day_label, d.status === 'closed' ? 'muted' : (d.d_day <= 7 ? 'warn' : 'info'))}</td>
      <td>${esc(d.how_to_submit || '')}</td>
      <td>${esc((d.places || []).join(', '))}</td>
      <td class="small">${esc(sourceLine(d.source))}<br>${pageButton(d.source, null)}</td>
    </tr>`).join('')}
    </tbody></table></div>`;
}

function progressCard(p) {
  const stagebar = p.stages.map((s) => `<div class="${s.status}" title="${esc(`${s.seq}. ${s.title}`)}"></div>`).join('');
  const chips = p.stages.map((s) => {
    const cls = `stage-chip ${s.status}${s.status === 'done' && !s.verified ? ' unverified' : ''}`;
    const tip = s.status === 'done' && !s.verified ? (s.note || '확인된 고시 없음') : s.title;
    return `<span class="${cls}" title="${esc(tip)}">${s.seq}. ${esc(s.title)}</span>`;
  }).join('');
  const c = p.current;
  const facts = (p.facts || []).length ? `
    <h3 style="margin-top:16px">고시에 적힌 수치</h3>
    <table><thead><tr><th>항목</th><th>값</th><th>근거</th></tr></thead><tbody>
    ${p.facts.map((f) => `<tr><td>${esc(f.label)}</td>
      <td><b>${Array.isArray(f.value) ? esc(f.value.join(', ')) : fmtNum(f.value)}</b> ${esc(f.unit || '')}</td>
      <td class="small">${esc(sourceLine(f.source))} ${pageButton(f.source, f.evidence, '원문')}</td></tr>`).join('')}
    </tbody></table>
    <p class="small muted">${esc(p.facts_note || '')}</p>` : '';
  const hist = (p.related_history || []).map((h) => `<li>${fmtDate(h.date)} · ${esc(h.label)}
      <span class="muted">(${esc(h.gosi_no || '')})</span> ${pageButton(h.source, null, '원문')}</li>`).join('');
  return `<div class="project-card">
    <div class="project-head">
      <h3>${esc(p.name)}</h3>${badge(p.project_type_label, 'info')}
      <span class="small muted">추진 방식 ${esc(p.track_label)} · 기준일 ${fmtDate(p.as_of)}</span>
    </div>
    ${(p.aliases || []).length ? `<div class="small muted">다른 이름: ${esc(p.aliases.join(', '))}</div>` : ''}
    <div class="small muted">위치: ${esc(p.location_text || '')}${p.center ? ` · 중심 좌표 ${p.center.lat.toFixed(5)}, ${p.center.lon.toFixed(5)} (${esc(p.center.coord_source)})` : ' · 중심 좌표 없음'}</div>
    <div class="stagebar" aria-label="단계 막대" style="grid-template-columns:repeat(${p.stages.length}, 1fr)">${stagebar}</div>
    <div class="row"><b>${esc(p.position_label)}</b><span class="small muted">초록=지난 단계(점선=확인된 고시 없음), 파랑=지금 단계, 회색=다음 단계들</span></div>
    ${p.sub_status ? `<div class="row" style="margin-top:4px">${badge('세부 상태', 'info')}<span>${esc(p.sub_status)}</span></div>` : ''}
    ${p.stage_note ? `<div class="box warn small" style="margin-top:6px">${esc(p.stage_note)}</div>` : ''}
    <div class="stage-chips">${chips}</div>

    <div class="grid cols-2">
      <div class="card soft">
        <div class="row"><h3 style="margin:0">지금 단계 · ${esc(c.title)}</h3>${badge(c.template_status, 'warn')}</div>
        <dl class="kv" style="margin-top:8px">
          <dt>발행처</dt><dd>${esc(c.issuer || '—')}</dd>
          <dt>설명</dt><dd>${c.what_happens ? esc(c.what_happens) : `<span class="muted">${esc(c.what_happens_note)}</span>`}</dd>
          <dt>소유자가 챙길 것</dt><dd>${c.owner_actions ? esc(c.owner_actions) : `<span class="muted">${esc(c.owner_actions_note || '—')}</span>`}</dd>
          <dt>단계 근거</dt><dd class="small">${esc(sourceLine(p.stage_basis.source))} (규칙 ${esc(p.stage_basis.rule_id)})
            ${pageButton(p.stage_basis.source, p.stage_basis.evidence, '원문')}</dd>
        </dl>
      </div>
      <div class="card soft">
        <h3>다음 단계${p.next ? ` · ${esc(p.next.title)}` : ''}</h3>
        ${p.next ? `<dl class="kv"><dt>소유자가 챙길 것</dt><dd>${p.next.owner_actions ? esc(p.next.owner_actions) : `<span class="muted">${esc(p.next.owner_actions_note || '—')}</span>`}</dd></dl>` : '<div class="empty">마지막 단계입니다</div>'}
        <h3 style="margin-top:12px">남은 기간</h3>
        <div>${esc(p.remaining.note)}</div>
        <details><summary>계산 방법 참고</summary><div class="small">${esc(p.remaining.method_note)}</div></details>
      </div>
    </div>

    <h3 style="margin-top:16px">진행 중인 기한</h3>
    ${deadlineTable(p.deadlines, false)}
    ${facts}
    <h3 style="margin-top:16px">관련 고시 이력</h3>
    <ul class="small">${hist || '<li class="muted">없음</li>'}</ul>
    <p class="small muted">${esc(p.disclaimer)}</p>
    ${apiViewer(p._method, p._url, p._body, Object.fromEntries(Object.entries(p).filter(([k]) => !k.startsWith('_'))))}
  </div>`;
}

async function loadProgress(projectId) {
  // 검수 화면을 메뉴에서 뺐으므로 조회 화면은 검수 결정을 보내지 않는다 (API의 POST는 남아 있음)
  const url = `/api/v1/projects/${projectId}/progress`;
  const p = await api(url);
  Object.assign(p, { _method: 'GET', _url: url, _body: null });
  return p;
}

const LAND_STATUS = { ok: ['토지 정보', 'ok'], partial: ['일부만 불러옴', 'warn'], unavailable: ['불러오지 못함', 'muted'] };
const RELATION_KIND = { '포함': 'info', '저촉': 'warn', '접함': 'muted' };

function fmtStamp(iso) {
  if (!iso) return '';
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  return m ? `${m[1]}.${m[2]}.${m[3]} ${m[4]}:${m[5]}` : fmtDate(iso);
}

function landCard(land, documented) {
  const [st, kind] = LAND_STATUS[land.status] || [land.status, 'muted'];
  const miss = '<span class="muted">불러오지 못함</span>';
  const v = (x, unit) => (x === null || x === undefined || x === '' ? miss : `${fmtNum(x)}${unit || ''}`);
  const price = land.official_price;
  const zones = (land.zones || []).map((z) => badge(`${z.name}${z.relation ? ` · ${z.relation}` : ''}`, RELATION_KIND[z.relation] || 'muted')).join(' ');
  const cache = land.cache === 'build' ? '미리 받아 둔 값(캐시)' : land.cache === 'memory' ? '최근 조회 값(캐시)' : '실시간 조회';
  if (land.status === 'unavailable') {
    return `<div class="card land-card"><div class="row"><h3 style="margin:0">토지 정보</h3>${badge(st, kind)}</div>
      <p>${esc(land.note || '토지 정보를 지금 불러오지 못했습니다')}</p></div>`;
  }
  return `<div class="card land-card">
    <div class="row"><h3 style="margin:0">토지 정보</h3>${badge(st, kind)}<span class="small muted">${esc(land.source || '')} · 조회 ${esc(fmtStamp(land.fetched_at))} · ${esc(cache)}</span></div>
    <dl class="kv land-kv">
      <dt>지목</dt><dd>${v(land.jimok)}</dd>
      <dt>면적</dt><dd>${v(land.area_m2, '㎡')}</dd>
      <dt>용도지역</dt><dd>${v(land.land_use_zone)}${land.land_use_zone2 ? ` · ${esc(land.land_use_zone2)}` : ''}
        ${documented ? `<div class="small muted">고시 기재: ${esc(documented.value)} — ${esc(documented.basis)} ${pageButton(documented.source, null, '원문')}</div>` : ''}</dd>
      <dt>공시지가</dt><dd>${price && price.won_per_m2 ? `${fmtNum(price.won_per_m2)}원/㎡ <span class="small muted">(${esc(price.year)}년 기준${price.announced_on ? ` · 공시 ${fmtDate(price.announced_on)}` : ''})</span>` : miss}</dd>
      <dt>이용상황</dt><dd>${v(land.use_situation)}</dd>
      <dt>도로접면</dt><dd>${v(land.road_side)}</dd>
      <dt>지형</dt><dd>${v(land.terrain)}</dd>
      <dt>지역·지구 등</dt><dd>${zones || miss}</dd>
    </dl>
    ${(land.missing || []).length ? `<div class="small muted">불러오지 못한 항목: ${esc(land.missing.join(', '))}</div>` : ''}
    <p class="small muted">${esc(land.note || '')}</p>
  </div>`;
}

function parcelHtml(P, normalized) {
  let html = landCard(P.land, P.land_use_documented);
  html += buildingHtml(P);
  html += itemsHtml(P.items).replace('<div class="empty">이 층에 해당하는 항목이 없습니다</div>', '');
  if (P.included_projects.length) {
    P.included_projects.forEach((p) => {
      const kind = p.inclusion === 'included' ? 'ok' : p.inclusion === 'likely' ? 'info' : 'warn';
      html += `<div class="item">
        <div class="row">${badge(p.inclusion_label, kind)}<span class="item-title">${esc(p.message)}</span></div>
        <p class="small">판정 근거: ${esc(p.basis_label)}</p>
        <div class="src">출처 · ${esc(sourceLine(p.source))}</div>
        <div class="actions">${pageButton(p.source, null)}</div>
      </div>
      <div id="progress-${p.project_id}"><div class="empty">사업 진행 카드를 불러오는 중…</div></div>`;
    });
  } else if (P.no_project_message) {
    html += `<div class="box info">${esc(P.no_project_message)}</div>`;
  }
  html += '<h3 style="margin-top:14px">주변 500m 사업</h3>';
  if (P.nearby_projects.length) {
    html += P.nearby_projects.map((n) => `<div class="item"><div class="row">${badge(n.inclusion_label, 'info')}
      <b>${esc(n.name)}</b><span><b>${n.distance_m}m</b></span>
      <button class="btn small" type="button" data-progress="${n.project_id}">진행상황 보기</button></div>
      <div class="small muted distance-basis">거리 기준: ${esc(n.distance_basis || '')}</div>
      <div id="progress-${n.project_id}" style="width:100%"></div></div>`).join('');
  } else {
    html += `<div class="empty">${esc(P.nearby_note || '주변 500m 안에서 진행 중인 사업이 없습니다')}</div>`;
  }
  return html;
}

function dongExtras(D) {
  let html = '';
  if (D.projects.length) {
    html += '<h3 style="margin-top:14px">같은 법정동의 사업</h3>';
    html += D.projects.map((p) => `<div class="item">
      <div class="row"><span class="item-title">${esc(p.name)}</span>${badge(`${p.stage.code} ${p.stage.title}`, 'info')}</div>
      <p class="small">${esc(p.message)}${p.location_text ? ` · 위치: ${esc(p.location_text)}` : ''}</p>
      <div class="src">출처 · ${esc(sourceLine(p.source))}</div>
      <div class="actions"><button class="btn small" type="button" data-progress="${p.project_id}">진행상황 보기</button></div>
      <div id="progress-${p.project_id}"></div></div>`).join('');
    html += '<h3 style="margin-top:14px">진행 중인 기한</h3>' + deadlineTable(D.deadlines, true);
  }
  return html;
}

function normLine(n) {
  const parts = [
    ['지번', n.jibun_address || '—'],
    ['도로명', n.road_address || '— (이 필지에 부여된 도로명주소 없음)'],
    ['PNU', n.pnu ? `<span class="mono">${esc(n.pnu)}</span>` : '—'],
    ['법정동', n.dong_name ? `${esc(n.dong_name)} <span class="mono small">${esc(n.bjd_code)}</span>` : '—'],
    ['지역생활권(참고)', n.saenghwal || '—'],
    ['좌표', n.coord_source ? `${n.lat.toFixed(5)}, ${n.lon.toFixed(5)} (${esc(n.coord_source)})` : '없음'],
  ];
  return `<div class="card soft norm-line">${parts.map(([k, v]) =>
    `<span><b>${k}</b>${k === 'PNU' || k === '법정동' || k === '좌표' ? v : esc(v)}</span>`).join('')}</div>`;
}

async function run(text) {
  // 검수 결정 없이 GET으로만 조회한다 (검수 화면은 메뉴에서 뺐음)
  const url = `/api/v1/lookup?address=${encodeURIComponent(text)}`;
  const r = await api(url);
  const method = 'GET';
  const body = null;
  const shownUrl = url;
  el('notices').innerHTML = '';

  document.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c.dataset.text === text));
  let html = normLine(r.normalized);
  if (r.status === 'ambiguous') {
    html += `<div class="box info"><b>${esc(r.message)}</b>
      <div class="candidates">${(r.candidates || []).map((c) => `<button class="btn small candidate" type="button"
        data-cand="${esc(c.jibun_address || c.road_address)}">${esc(c.road_address || '')}
        <span class="small muted">${esc(c.jibun_address || '')}${c.bld_name ? ` · ${esc(c.bld_name)}` : ''}</span></button>`).join('')}</div></div>`;
  } else if (r.status !== 'ok') {
    html += `<div class="box info"><b>${esc(r.message)}</b></div>`;
  } else {
    const L = r.layers;
    const n = r.normalized;
    const counts = {
      city: L.city.length,
      gu: L.gu.items.length,
      dong: L.dong.items.length + L.dong.projects.length,
      parcel: L.parcel.items.length + L.parcel.included_projects.length + L.parcel.nearby_projects.length,
    };
    // 화면 순서: 이 땅(필지) → 법정동 → 자치구 → 서울 전역 → 참고 (feedback2.md §3-4). 가장 좁은 층에만 표시하는 규칙은 그대로
    html += `<div class="row small" style="margin:8px 0">바로가기
      <a href="#layer-parcel">이 땅 (토지 정보${L.parcel.included_projects.length ? '·사업 카드' : ''})</a> ·
      <a href="#layer-dong">법정동 ${counts.dong}</a> · <a href="#layer-gu">자치구 ${counts.gu}</a> ·
      <a href="#layer-city">서울 전역 ${counts.city}</a> · <a href="#reference">참고 ${(r.reference && r.reference.items.length) || 0}</a></div>`;
    html += layer('필지 · 이 땅', `PNU ${n.pnu}`, counts.parcel, parcelHtml(L.parcel, n), 'layer-parcel');
    html += layer(`법정동 · ${n.dong_name}`, `법정동 ${n.bjd_code}`, counts.dong,
      (L.dong.items.length || L.dong.projects.length ? itemsHtml(L.dong.items) : `<div class="empty">${esc(L.dong.empty_note || '이 층에 해당하는 항목이 없습니다')}</div>`)
      + dongExtras(L.dong), 'layer-dong');
    html += layer(`자치구 · 강남구`, `시군구 ${n.sgg_code}`, counts.gu, itemsHtml(L.gu.items) + stageTable(L.gu.projects_by_stage), 'layer-gu');
    html += layer('서울 전역', '시도 11', counts.city, itemsHtml(L.city), 'layer-city');
    html += referenceHtml(r.reference);
  }
  html += `<p class="small muted">${esc(r.coverage_note || '')}</p><p class="small muted">${esc(r.disclaimer)}</p>`;
  html += apiViewer(method, shownUrl, body, r);
  el('result').innerHTML = html;

  if (r.status === 'ok') {
    for (const p of r.layers.parcel.included_projects) {
      const box = el(`progress-${p.project_id}`);
      try { box.innerHTML = progressCard(await loadProgress(p.project_id)); } catch (e) { box.innerHTML = ''; }
    }
  }
}

document.addEventListener('click', async (e) => {
  const cand = e.target.closest('[data-cand]');
  if (cand) { search(cand.dataset.cand, null); return; }
  const b = e.target.closest('[data-progress]');
  if (!b) return;
  const box = el(`progress-${b.dataset.progress}`);
  if (box.innerHTML.trim()) { box.innerHTML = ''; return; }
  box.innerHTML = progressCard(await loadProgress(Number(b.dataset.progress)));
});

function search(text, addrId) {
  el('q').value = text;
  const params = addrId ? `?addr=${encodeURIComponent(addrId)}` : `?q=${encodeURIComponent(text)}`;
  window.history.replaceState(null, '', `lookup.html${params}`);
  run(text);
}

(async () => {
  await initShell('lookup');
  demoList = await api('/api/v1/demo-addresses');
  const groups = [];
  demoList.forEach((d) => {
    const g = groups.find((x) => x.name === d.group) || (groups.push({ name: d.group, items: [] }), groups[groups.length - 1]);
    g.items.push(d);
  });
  el('chips').innerHTML = groups.map((g) => `<div class="chip-group"><span class="chip-group-name">${esc(g.name)}</span>
    ${g.items.map((d) => `<button class="chip${g.name === '대표 시연' ? ' featured' : ''}" type="button" data-addr="${esc(d.addr_id)}"
      data-text="${esc(d.input_text)}" ${d.available ? '' : 'disabled title="주소 확정 전"'}>${esc(d.label)}</button>`).join('')}</div>`).join('');
  el('chips').addEventListener('click', (e) => {
    const c = e.target.closest('.chip');
    if (c && !c.disabled) search(c.dataset.text, c.dataset.addr);
  });
  el('search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const t = el('q').value.trim();
    const hit = demoList.find((d) => d.input_text === t);
    search(t, hit ? hit.addr_id : null);
  });
  const addr = qs('addr');
  const q = qs('q');
  if (addr) {
    const d = demoList.find((x) => x.addr_id === addr && x.available);
    if (d) search(d.input_text, d.addr_id);
  } else if (q) {
    search(q, null);
  }
})();
