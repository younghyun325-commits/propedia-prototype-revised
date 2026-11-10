/** 명령 팔레트 검색 (P14). 순수 함수 — Vitest. 사업은 화면에 있는 /api/v1/map/projects 결과에서 부분 일치로 찾는다. */
import type { MapProject } from '../api/map'

/** 공백·'번지'·'서울특별시'·'서울' 접두어를 떼고 소문자로 */
export function normQuery(s: string): string {
  return s
    .normalize('NFC')
    .replace(/서울특별시|서울시/g, '')
    .replace(/번지/g, '')
    .replace(/\s+/g, '')
    .toLowerCase()
}

export type ProjectHit = { project: MapProject; field: 'name' | 'alias' | 'jibun'; rank: number }

/**
 * 정렬: 이름 앞부분 일치(0) → 이름 포함(1) → 별칭 포함(2) → 대표 지번 포함(3), 같으면 사업 id 순.
 * 2글자 미만이면 결과 없음.
 */
export function searchProjects(list: MapProject[], q: string): ProjectHit[] {
  const n = normQuery(q)
  if (n.length < 2) return []
  const hits: ProjectHit[] = []
  for (const p of list) {
    const name = normQuery(p.name)
    const short = normQuery(p.short_name)
    let hit: ProjectHit | null = null
    if (name.startsWith(n) || short.startsWith(n)) hit = { project: p, field: 'name', rank: 0 }
    else if (name.includes(n) || short.includes(n)) hit = { project: p, field: 'name', rank: 1 }
    else if (p.aliases.some((a) => normQuery(a).includes(n))) hit = { project: p, field: 'alias', rank: 2 }
    else if (p.representative_jibun && normQuery(p.representative_jibun).includes(n))
      hit = { project: p, field: 'jibun', rank: 3 }
    if (hit) hits.push(hit)
  }
  return hits.sort((a, b) => a.rank - b.rank || a.project.id - b.project.id)
}

/**
 * 주소 그룹에 보낼 검색어. 지도는 강남구만 다루므로 구 이름 없이 동·번지로 시작하면('압구정동 528') 앞에 '강남구'를 붙인다.
 * 그 밖에는 입력 그대로 기존 /api/v1/lookup에 보낸다.
 */
export function addressQuery(q: string): string {
  const t = q.trim()
  if (/[가-힣]+구(\s|$)/.test(t) || /^(서울|서울시|서울특별시)/.test(t)) return t
  if (/^[가-힣0-9]+동\s*(산\s*)?\d/.test(t)) return `강남구 ${t}`
  return t
}

/** 최근 검색 (sessionStorage, 실패해도 화면은 그대로) */
const RECENT_KEY = 'propedia.map.recent.v1'
export const RECENT_MAX = 5

export function pushRecent(list: string[], q: string, max = RECENT_MAX): string[] {
  const t = q.trim()
  if (!t) return list
  return [t, ...list.filter((x) => x !== t)].slice(0, max)
}

export function loadRecent(): string[] {
  try {
    const v = JSON.parse(window.sessionStorage.getItem(RECENT_KEY) ?? '[]')
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string').slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}

export function saveRecent(list: string[]): void {
  try {
    window.sessionStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX)))
  } catch {
    /* 저장소를 못 써도 검색은 그대로 */
  }
}
