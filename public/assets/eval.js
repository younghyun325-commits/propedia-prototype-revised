/* 평가 리포트 화면 (agents.md §12-6) */
'use strict';

const LAYER_NAMES = { city: '서울 전역', gu: '자치구', dong: '법정동', parcel: '필지' };
const ERROR_TYPES = { normalize: '정규화', scope: '범위 판정', extraction: '추출', inclusion: '포함 판정', evidence: '근거', other: '기타' };

function okBadge(v) {
  if (v === null || v === undefined) return badge('해당 없음', 'muted');
  return v ? badge('일치', 'ok') : badge('불일치', 'warn');
}

function pctText(v) { return v === null || v === undefined ? '—' : `${Math.round(v * 1000) / 10}%`; }

function render(rep) {
  if (rep.status === 'not_run') {
    el('eval-body').innerHTML = `<div class="box warn">${esc(rep.message)}</div>`;
    return;
  }
  const g = rep.goldset || {};
  el('draft-badge').innerHTML = g.draft ? badge('정답셋 초안 — 사람 확정 전, 추출자와 같은 작성자', 'warn') : badge('정답셋 확정', 'ok');
  const metrics = rep.metrics.map((m) => `<div class="card metric">
      <div class="row"><span class="mono small muted">${esc(m.id)}</span>${m.pass === null ? badge('참고', 'muted') : (m.pass ? badge('통과', 'ok') : badge('미달', 'warn'))}</div>
      <div class="name">${esc(m.name)}</div>
      <div class="val">${esc(m.display)}</div>
      <div class="small muted">목표 ${esc(m.target)}</div>
      ${m.note ? `<div class="small muted">${esc(m.note)}</div>` : ''}
    </div>`).join('');
  const layers = `<table><thead><tr><th>층</th><th>재현율</th><th>정밀도</th><th>기대 항목 수</th><th>응답 항목 수</th></tr></thead><tbody>
    ${rep.layers.map((l) => `<tr><td>${esc(LAYER_NAMES[l.layer] || l.layer)}</td><td>${pctText(l.recall)}</td><td>${pctText(l.precision)}</td>
      <td>${l.expected}</td><td>${l.returned}</td></tr>`).join('')}</tbody></table>`;
  const addrs = `<table><thead><tr><th>주소</th><th>입력</th><th>상태</th><th>PNU</th><th>서울 전역</th><th>자치구</th><th>법정동</th><th>필지</th><th>포함 판정</th><th>효력 중 고시</th><th>건축물</th></tr></thead><tbody>
    ${rep.addresses.map((a) => `<tr><td><b>${esc(a.addr_id)}</b></td><td class="small">${esc(a.input || '')}</td>
      <td>${okBadge(a.status_ok)}</td><td>${okBadge(a.pnu_ok)}</td>
      ${['city', 'gu', 'dong', 'parcel'].map((k) => `<td class="small">${esc((a.layer_hits || {})[k] || '—')}</td>`).join('')}
      <td>${okBadge(a.inclusion_ok)}</td><td class="small">${esc(a.regulations || '—')}</td>
      <td class="small">${esc(a.building || '—')}</td></tr>`).join('')}</tbody></table>`;
  const errGroups = {};
  (rep.errors || []).forEach((e) => { (errGroups[e.type] = errGroups[e.type] || []).push(e.detail); });
  const errs = Object.keys(errGroups).length
    ? Object.entries(errGroups).map(([t, list]) => `<h3>${esc(ERROR_TYPES[t] || t)} (${list.length})</h3>
        <ul class="small">${list.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>`).join('')
    : '<div class="empty">오류 없음</div>';
  const files = Object.entries(g.files || {}).map(([k, v]) => `${k} ${v}`).join(' · ');
  el('eval-body').innerHTML = `
    <h2>지표</h2><div class="grid cols-4">${metrics}</div>
    <h2>층별 재현율·정밀도</h2><div class="table-wrap">${layers}</div>
    <h2>주소별 결과</h2><div class="table-wrap">${addrs}</div>
    ${(rep.excluded_addresses || []).length ? `<p class="small muted">정답셋에서 뺀 주소: ${esc(rep.excluded_addresses.join(', '))} (도로명주소 API 키 재발급 후 확정)</p>` : ''}
    <h2>오류 목록</h2>${errs}
    <h2>실행 정보</h2>
    <dl class="kv"><dt>평가 실행</dt><dd>${esc(rep.run_at)}</dd><dt>DB 빌드</dt><dd>${esc(rep.build_at)}</dd>
      <dt>정답셋 버전</dt><dd class="mono small">${esc(files)}</dd></dl>`;
}

(async () => {
  await initShell('eval');
  render(await api('/api/v1/eval'));
})();
