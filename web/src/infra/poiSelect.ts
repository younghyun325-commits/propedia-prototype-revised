/**
 * 편의시설 분류·하위 분류 선택 (P19-1). 순수 함수 — Vitest.
 * - 선택 상태 PoiSel: 켜진 분류 key → 켜진 하위 분류 slug 목록. 하위 분류가 없는 분류는 빈 배열. 없는 key = 꺼짐.
 * - 분류 key·하위 분류 slug는 seed/poi_categories.yaml(sub_keys)과 같다 — infra.test.ts가 manifest와 맞는지 검사한다.
 *   건수는 코드에 쓰지 않고 manifest에서 읽는다.
 * - URL: poi=supermarket,medical:dental+oriental,academy:language (하위 분류를 모두 켜면 분류만, 모두 꺼지면 파라미터 없음)
 * - 지도: 분류마다 source 하나(클러스터 + clusterProperties로 하위 분류별 건수 n_{slug}).
 *   하위 분류를 바꿀 때는 setFilter만 (낱점: sub_category 필터, 클러스터: 켜진 하위 분류 건수 합 > 0)
 */
export type PoiSub = { slug: string; label: string }
export type PoiNode = { key: string; subs: PoiSub[] }
export type PoiSel = Record<string, string[]>
export type Tri = 'on' | 'mixed' | 'off'

export const POI_TREE: PoiNode[] = [
  { key: 'supermarket', subs: [] },
  { key: 'convenience', subs: [] },
  {
    key: 'medical',
    subs: [
      { slug: 'hospital', label: '병원' }, { slug: 'clinic', label: '의원' },
      { slug: 'dental', label: '치과' }, { slug: 'oriental', label: '한방' },
    ],
  },
  { key: 'pharmacy', subs: [] },
  { key: 'cafe', subs: [] },
  {
    key: 'academy',
    subs: [{ slug: 'subject', label: '교과' }, { slug: 'language', label: '외국어' }, { slug: 'arts', label: '예체능·기타' }],
  },
]
export const POI_KEYS = POI_TREE.map((n) => n.key)
const NODE = new Map(POI_TREE.map((n) => [n.key, n]))
export const poiNode = (key: string): PoiNode | undefined => NODE.get(key)
const allSubs = (key: string) => (NODE.get(key)?.subs ?? []).map((s) => s.slug)

/** 지도 레이어·소스 id (분류마다 독립) */
export const poiSourceId = (key: string) => `infra-poi-${key}`
export const poiIconLayer = (key: string) => `poi-${key}`
export const poiClusterLayer = (key: string) => `poi-${key}-cluster`
export const poiSelectedLayer = (key: string) => `poi-${key}-selected`
export const clusterProp = (slug: string) => `n_${slug}`

/** 분류·하위 분류 순서를 POI_TREE대로 맞춘다 (같은 상태는 같은 값) */
function canon(sel: PoiSel): PoiSel {
  const out: PoiSel = {}
  for (const n of POI_TREE) {
    const v = sel[n.key]
    if (!v) continue
    if (!n.subs.length) out[n.key] = []
    else {
      const subs = n.subs.map((s) => s.slug).filter((s) => v.includes(s))
      if (subs.length) out[n.key] = subs
    }
  }
  return out
}

export const poiNone = (): PoiSel => ({})
export const poiAll = (): PoiSel => Object.fromEntries(POI_TREE.map((n) => [n.key, allSubs(n.key)]))
export const poiAny = (sel: PoiSel): boolean => Object.keys(sel).length > 0
export const catOn = (sel: PoiSel, key: string): boolean => key in sel

/** 분류 행 상태: 하위 분류가 모두 켜짐 = on, 일부 = mixed, 없음 = off */
export function triCat(sel: PoiSel, key: string): Tri {
  const v = sel[key]
  if (!v) return 'off'
  const all = allSubs(key)
  return !all.length || all.every((s) => v.includes(s)) ? 'on' : 'mixed'
}

/** 상위 '편의시설' 행: 6분류(하위 분류 포함) 모두 켜짐 = on, 일부 = mixed, 모두 꺼짐 = off */
export function triAll(sel: PoiSel): Tri {
  const ts = POI_TREE.map((n) => triCat(sel, n.key))
  if (ts.every((t) => t === 'on')) return 'on'
  return ts.every((t) => t === 'off') ? 'off' : 'mixed'
}

/** 상위 클릭: 체크 → 모두 끄기, 일부·빈칸 → 모두 켜기 */
export const clickAll = (sel: PoiSel): PoiSel => (triAll(sel) === 'on' ? poiNone() : poiAll())

/** 분류 클릭: 체크 → 끄기, 일부·빈칸 → 하위 분류 모두 켜기 */
export function clickCat(sel: PoiSel, key: string): PoiSel {
  if (!NODE.has(key)) return sel
  const out = { ...sel }
  if (triCat(sel, key) === 'on') delete out[key]
  else out[key] = allSubs(key)
  return canon(out)
}

/** 하위 분류 클릭: 하나라도 켜면 분류도 켜짐, 모두 끄면 분류도 꺼짐 */
export function clickSub(sel: PoiSel, key: string, slug: string): PoiSel {
  if (!allSubs(key).includes(slug)) return sel
  const cur = sel[key] ?? []
  const next = cur.includes(slug) ? cur.filter((s) => s !== slug) : [...cur, slug]
  const out = { ...sel }
  if (next.length) out[key] = next
  else delete out[key]
  return canon(out)
}

/** '이것만 보기': 그 분류(또는 하위 분류)만 켜고 나머지 편의시설은 끈다 */
export function solo(key: string, slug?: string): PoiSel {
  if (!NODE.has(key)) return poiNone()
  if (slug !== undefined) return allSubs(key).includes(slug) ? { [key]: [slug] } : poiNone()
  return { [key]: allSubs(key) }
}

/** 하위 분류 라벨(원자료 sub_category) → 켜져 있는지 */
export function poiShown(sel: PoiSel, p: { category: string; sub_category?: string }): boolean {
  const v = sel[p.category]
  if (!v) return false
  const n = NODE.get(p.category)
  if (!n?.subs.length || !p.sub_category) return true
  const s = n.subs.find((x) => x.label === p.sub_category)
  return !!s && v.includes(s.slug)
}

// ---------- URL ----------
export function formatPoi(sel: PoiSel): string | null {
  const c = canon(sel)
  const parts = Object.entries(c).map(([k, v]) => (triCat(c, k) === 'on' ? k : `${k}:${v.join('+')}`))
  return parts.length ? parts.join(',') : null
}

/** 잘못된 분류·하위 분류는 무시한다. '+'는 URLSearchParams가 공백으로 바꾸므로 둘 다 받는다 */
export function parsePoi(v: string | null | undefined): PoiSel {
  const out: PoiSel = {}
  for (const part of (v ?? '').split(',')) {
    const [key, rest, extra] = part.trim().split(':')
    if (!key || extra !== undefined || !NODE.has(key)) continue
    if (rest === undefined) {
      out[key] = allSubs(key)
      continue
    }
    const subs = rest.split(/[+ ]/).filter((s) => allSubs(key).includes(s))
    if (subs.length) out[key] = [...new Set([...(out[key] ?? []), ...subs])]
  }
  return canon(out)
}

// ---------- 지도 expression ----------
const HAS_COUNT = ['has', 'point_count']

/** 클러스터 소스 clusterProperties: 하위 분류마다 건수 */
export function clusterProperties(key: string): Record<string, unknown> | undefined {
  const n = NODE.get(key)
  if (!n?.subs.length) return undefined
  return Object.fromEntries(
    n.subs.map((s) => [clusterProp(s.slug), ['+', ['case', ['==', ['get', 'sub_category'], s.label], 1, 0]]]),
  )
}

/** 켜진 하위 분류가 전부면 null(필터 없음) */
function partialSubs(key: string, on: string[]): PoiSub[] | null {
  const n = NODE.get(key)
  if (!n?.subs.length) return null
  const subs = n.subs.filter((s) => on.includes(s.slug))
  return subs.length === n.subs.length ? null : subs
}

/** 클러스터 안 켜진 하위 분류 건수 합 (하위 분류가 모두 켜졌으면 point_count) */
export function clusterCountExpr(key: string, on: string[]): unknown[] {
  const subs = partialSubs(key, on)
  if (!subs) return ['get', 'point_count']
  if (subs.length === 1) return ['get', clusterProp(subs[0].slug)]
  return ['+', ...subs.map((s) => ['get', clusterProp(s.slug)])]
}

/** 낱점 아이콘 레이어 필터 */
export function iconFilter(key: string, on: string[]): unknown[] {
  const subs = partialSubs(key, on)
  if (!subs) return ['!', HAS_COUNT]
  return ['all', ['!', HAS_COUNT], ['in', ['get', 'sub_category'], ['literal', subs.map((s) => s.label)]]]
}

/** 클러스터 원 필터: 켜진 하위 분류가 하나라도 들어 있는 클러스터만 */
export function clusterFilter(key: string, on: string[]): unknown[] {
  if (!partialSubs(key, on)) return HAS_COUNT
  return ['all', HAS_COUNT, ['>', clusterCountExpr(key, on), 0]]
}

/** 클러스터 원 반지름 (개수 단계) */
export function clusterRadiusExpr(key: string, on: string[]): unknown[] {
  return ['step', clusterCountExpr(key, on), 13, 10, 15, 50, 18, 200, 21]
}

/** HTML 개수 마커: 클러스터 속성에서 켜진 하위 분류 합 */
export function clusterCount(props: Record<string, unknown>, key: string, on: string[]): number {
  const subs = partialSubs(key, on)
  if (!subs) return Number(props.point_count)
  return subs.reduce((a, s) => a + Number(props[clusterProp(s.slug)] ?? 0), 0)
}
