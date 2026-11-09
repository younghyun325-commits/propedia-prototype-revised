/* Propedia 프리토타입 공통 스크립트 (agents.md §12-1). 외부 라이브러리 없음. */
'use strict';

const DECISION_KEY = 'propedia.pretotype.decisions.v1';
let memoryDecisions = [];

/* ── 검수 결정 저장 (이 브라우저에만, 사생활 보호 모드면 메모리로 대체) ── */
function getDecisions() {
  try {
    const s = window.localStorage.getItem(DECISION_KEY);
    if (s === null) return memoryDecisions.slice();
    const v = JSON.parse(s);
    return Array.isArray(v) ? v : [];
  } catch (e) {
    return memoryDecisions.slice();
  }
}

function setDecisions(list) {
  memoryDecisions = list.slice();
  try { window.localStorage.setItem(DECISION_KEY, JSON.stringify(list)); } catch (e) { /* 메모리만 사용 */ }
}

function clearDecisions() {
  memoryDecisions = [];
  try { window.localStorage.removeItem(DECISION_KEY); } catch (e) { /* 무시 */ }
}

function upsertDecision(decision) {
  const list = getDecisions().filter((d) => d.review_id !== decision.review_id);
  list.push(Object.assign({}, decision, { decided_at: new Date().toISOString() }));
  setDecisions(list);
}

function decisionFor(reviewId) {
  return getDecisions().find((d) => d.review_id === reviewId) || null;
}

/* ── 기본 도우미 ── */
function esc(v) {
  if (v === null || v === undefined) return '';
  return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function fmtDate(s) {
  if (!s) return '';
  return String(s).slice(0, 10).replace(/-/g, '.');
}

function fmtNum(v) {
  if (typeof v !== 'number') return esc(v);
  return v.toLocaleString('ko-KR', { maximumFractionDigits: 2 });
}

function badge(text, kind) {
  return `<span class="badge ${kind || 'muted'}">${esc(text)}</span>`;
}

function qs(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function el(id) { return document.getElementById(id); }

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

/* ── API ── */
function showError(msg) {
  const main = document.querySelector('main');
  if (!main) return;
  let box = el('error-box');
  if (!box) {
    box = document.createElement('div');
    box.id = 'error-box';
    box.className = 'box error';
    main.prepend(box);
  }
  box.textContent = msg;
}

async function api(path, opts) {
  const o = opts || {};
  const init = { method: o.method || 'GET', headers: {} };
  if (o.body !== undefined) {
    init.method = o.method || 'POST';
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(o.body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch (e) {
    showError(`서버에 연결할 수 없습니다 (${path}). 로컬이면 run_demo.bat이 켜져 있는지 확인하세요.`);
    throw e;
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); msg = j.detail || msg; } catch (e) { /* 무시 */ }
    showError(`요청 실패: ${msg}`);
    throw new Error(msg);
  }
  return res.json();
}

/* ── 출처 줄: "D3 · 2030 정비기본계획 · PDF 265쪽(인쇄 252쪽) · 2025.06.26" ── */
function sourceLine(s) {
  if (!s) return '';
  const parts = [s.doc_id, s.short_title];
  if (s.pdf_page) {
    const label = s.page_label && String(s.page_label) !== String(s.pdf_page) ? `(인쇄 ${s.page_label}쪽)` : '';
    parts.push(`PDF ${s.pdf_page}쪽${label}`);
  }
  if (s.published_at) parts.push(fmtDate(s.published_at));
  return parts.filter(Boolean).join(' · ');
}

/* ── 원문 보기 모달 ── */
let modalSource = null;

function ensureModal() {
  if (el('page-modal')) return;
  const back = document.createElement('div');
  back.id = 'page-modal';
  back.className = 'modal-back';
  back.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="page-modal-title">
      <div class="modal-head">
        <h3 id="page-modal-title"></h3>
        <a class="btn small" id="page-modal-doc" href="#">문서 DB에서 보기</a>
        <button class="btn small" id="page-modal-close" type="button">닫기 (Esc)</button>
      </div>
      <div id="page-modal-evidence"></div>
      <div id="page-modal-link" class="small" style="margin:6px 0 10px"></div>
      <img id="page-modal-img" alt="원문 쪽 이미지">
    </div>`;
  document.body.appendChild(back);
  back.addEventListener('click', (e) => { if (e.target === back) closePage(); });
  el('page-modal-close').addEventListener('click', closePage);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePage(); });
}

function openPage(source, evidence) {
  if (!source || !source.page_image) { toast('원문 쪽 정보가 없습니다'); return; }
  ensureModal();
  modalSource = source;
  el('page-modal-title').textContent = sourceLine(source);
  el('page-modal-evidence').innerHTML = evidence
    ? `<div class="evidence"><b>근거 문장</b> · ${esc(evidence)}</div>` : '';
  el('page-modal-link').innerHTML = source.source_url
    ? `<a href="${esc(source.source_url)}" target="_blank" rel="noopener">원문 게시처 열기</a> · ${esc(source.source_note || '')}`
    : `출처: ${esc(source.source_note || '')}`;
  el('page-modal-doc').href = `docs.html?doc=${encodeURIComponent(source.doc_id)}&page=${source.pdf_page}`;
  el('page-modal-img').src = source.page_image;
  el('page-modal').classList.add('open');
}

function closePage() {
  const m = el('page-modal');
  if (m) m.classList.remove('open');
}

/* 버튼에 출처를 실어 두고 클릭 시 모달을 연다 */
const pageRefs = [];
function pageButton(source, evidence, label) {
  if (!source || !source.page_image) return '';
  const i = pageRefs.push({ source, evidence }) - 1;
  return `<button class="btn small" type="button" data-page-ref="${i}">${esc(label || '원문 보기')}</button>`;
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-page-ref]');
  if (!b) return;
  const r = pageRefs[Number(b.dataset.pageRef)];
  if (r) openPage(r.source, r.evidence);
});

/* ── 근거 하이라이트: 공백 무시, 가운뎃점 변형 허용 ── */
const DOT_CLASS = '[·ㆍ․‧・]';
function evidenceRegex(ev) {
  const chars = Array.from(String(ev).replace(/\s+/g, ''));
  if (chars.length < 2) return null;
  const parts = chars.map((c) => ('·ㆍ․‧・'.includes(c) ? DOT_CLASS : c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  return new RegExp(parts.join('\\s*'), 'g');
}

function highlight(text, evidences) {
  const ranges = [];
  (evidences || []).forEach((ev) => {
    const rx = evidenceRegex(ev);
    if (!rx) return;
    let m;
    while ((m = rx.exec(text)) !== null) {
      ranges.push([m.index, m.index + m[0].length]);
      if (m[0].length === 0) rx.lastIndex += 1;
    }
  });
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  ranges.forEach((r) => {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push(r.slice());
  });
  let out = '';
  let pos = 0;
  merged.forEach(([a, b]) => {
    out += esc(text.slice(pos, a)) + '<mark>' + esc(text.slice(a, b)) + '</mark>';
    pos = b;
  });
  return out + esc(text.slice(pos));
}

/* ── API 응답 보기 ── */
function apiViewer(method, url, body, data) {
  const req = `${method} ${url}` + (body ? `\n${JSON.stringify(body, null, 2)}` : '');
  const json = JSON.stringify(data, null, 2);
  const id = `api-json-${Math.random().toString(36).slice(2, 8)}`;
  return `<details class="card soft"><summary>API 응답 보기</summary>
    <p class="small muted">화면은 아래 API 응답을 그대로 그립니다.</p>
    <pre>${esc(req)}</pre>
    <div class="row"><b>응답</b><span class="spacer"></span><button class="btn small" type="button" data-copy="${id}">복사</button></div>
    <pre id="${id}">${esc(json)}</pre></details>`;
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-copy]');
  if (!b) return;
  const text = el(b.dataset.copy).textContent;
  const done = () => toast('복사했습니다');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, () => toast('복사하지 못했습니다'));
  } else {
    toast('이 브라우저에서는 직접 선택해 복사해 주세요');
  }
});

/* ── 공통 머리글 ──
   검수·평가 화면은 메뉴에서 뺐다 (2026-10-26 동혁 결정). 파일과 API(/api/v1/review-queue, /api/v1/eval)는 남아 있다 */
const NAV = [
  ['index', 'index.html', '시작'],
  ['lookup', 'lookup.html', '주소 조회'],
  ['docs', 'docs.html', '문서 DB'],
];

let healthCache = null;
async function health() {
  if (!healthCache) healthCache = await api('/api/v1/health');
  return healthCache;
}

function renderDecisionStatus() {
  const box = el('decision-status');
  if (!box) return;
  const n = getDecisions().length;
  box.innerHTML = n
    ? `${badge(`검수 결정 ${n}건 반영 중`, 'warn')} <button class="btn small" type="button" id="reset-decisions">초기화</button>`
    : '';
  const b = el('reset-decisions');
  if (b) b.addEventListener('click', () => { clearDecisions(); window.location.reload(); });
}

async function initShell(active) {
  const header = el('site-header');
  if (header) {
    header.className = 'site-header';
    header.innerHTML = `
      <a class="logo" href="index.html"><img src="assets/logo.png" alt="Propedia" width="96" height="23"><span>프리토타입</span></a>
      <nav class="nav">${NAV.map(([k, href, label]) =>
        `<a href="${href}" class="${k === active ? 'active' : ''}">${label}</a>`).join('')}</nav>
      <div class="header-right"><span id="as-of"></span><span id="decision-status"></span></div>`;
  }
  if (active === 'review') renderDecisionStatus();   // 검수 결정 표시는 (메뉴에서 뺀) 검수 화면에서만
  try {
    const h = await health();
    el('as-of').textContent = `기준일 ${fmtDate(h.as_of)}`;
  } catch (e) { /* 오류 상자는 api()가 표시 */ }
}

window.addEventListener('storage', () => { if (el('decision-status') && el('queue-body')) renderDecisionStatus(); });
