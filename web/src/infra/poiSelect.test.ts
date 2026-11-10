import { describe, expect, it } from 'vitest'
import manifestRaw from '../../../public/data/layers/manifest.json?raw'
import type { PoiCategory } from './data'
import {
  POI_TREE, clickAll, clickCat, clickSub, clusterCount, clusterCountExpr, clusterFilter, clusterProperties, formatPoi, iconFilter,
  parsePoi, poiAll, poiShown, solo, triAll, triCat,
} from './poiSelect'
import { mergeSearch, parseUrl, toSearch } from '../state/url'

const HAS = ['has', 'point_count']

describe('편의시설 분류표 (P19-1): POI_TREE = manifest (seed/poi_categories.yaml)', () => {
  it('분류 key·하위 분류 라벨·slug가 같다', () => {
    const cats: PoiCategory[] = JSON.parse(manifestRaw).layers.pois.categories
    expect(POI_TREE.map((n) => n.key)).toEqual(cats.map((c) => c.key))
    for (const c of cats) {
      const n = POI_TREE.find((x) => x.key === c.key)!
      expect(n.subs.map((s) => s.label)).toEqual(c.sub_categories)
      expect(Object.fromEntries(n.subs.map((s) => [s.label, s.slug]))).toEqual(c.sub_keys ?? {})
      expect(c.file).toBe(`pois_${c.key}.geojson`)
    }
  })
})

describe('3단 상태', () => {
  it('상위: 모두 = on, 일부 = mixed, 없음 = off', () => {
    expect(triAll({})).toBe('off')
    expect(triAll(poiAll())).toBe('on')
    expect(triAll({ convenience: [] })).toBe('mixed')
    // 하위 분류 하나만 빠져도 일부
    expect(triAll({ ...poiAll(), medical: ['hospital', 'clinic', 'dental'] })).toBe('mixed')
  })
  it('분류: 하위 분류 모두 = on, 일부 = mixed, 없음 = off / 하위 분류 없는 분류는 on·off', () => {
    expect(triCat({ medical: ['hospital', 'clinic', 'dental', 'oriental'] }, 'medical')).toBe('on')
    expect(triCat({ medical: ['dental'] }, 'medical')).toBe('mixed')
    expect(triCat({}, 'medical')).toBe('off')
    expect(triCat({ cafe: [] }, 'cafe')).toBe('on')
  })
})

describe('클릭', () => {
  it('상위: 일부·빈칸 → 모두 켜기, 체크 → 모두 끄기', () => {
    expect(clickAll({})).toEqual(poiAll())
    expect(clickAll({ cafe: [] })).toEqual(poiAll())
    expect(clickAll(poiAll())).toEqual({})
  })
  it('분류: 일부 → 모두, 체크 → 끄기', () => {
    expect(clickCat({ medical: ['dental'] }, 'medical')).toEqual({ medical: ['hospital', 'clinic', 'dental', 'oriental'] })
    expect(clickCat({ medical: ['hospital', 'clinic', 'dental', 'oriental'] }, 'medical')).toEqual({})
    expect(clickCat({}, 'pharmacy')).toEqual({ pharmacy: [] })
    expect(clickCat({}, 'nope')).toEqual({})
  })
  it('하위 분류: 하나라도 켜면 분류 켜짐, 모두 끄면 분류 꺼짐 (순서는 분류표대로)', () => {
    const a = clickSub({}, 'academy', 'arts')
    expect(a).toEqual({ academy: ['arts'] })
    const b = clickSub(a, 'academy', 'language')
    expect(b).toEqual({ academy: ['language', 'arts'] })
    expect(clickSub({ academy: ['arts'] }, 'academy', 'arts')).toEqual({})
    expect(clickSub({}, 'academy', 'nope')).toEqual({})
  })
  it("'이것만 보기': 그 분류·하위 분류만", () => {
    expect(solo('pharmacy')).toEqual({ pharmacy: [] })
    expect(solo('medical')).toEqual({ medical: ['hospital', 'clinic', 'dental', 'oriental'] })
    expect(solo('medical', 'dental')).toEqual({ medical: ['dental'] })
    expect(solo('medical', 'x')).toEqual({})
  })
  it('점 표시 여부 (원자료 sub_category 라벨)', () => {
    const s = { medical: ['dental'], cafe: [] }
    expect(poiShown(s, { category: 'medical', sub_category: '치과' })).toBe(true)
    expect(poiShown(s, { category: 'medical', sub_category: '의원' })).toBe(false)
    expect(poiShown(s, { category: 'cafe' })).toBe(true)
    expect(poiShown(s, { category: 'pharmacy' })).toBe(false)
  })
})

describe('URL poi 왕복', () => {
  it('분류만 = 하위 분류 전체, 콜론 뒤 = 켠 하위 분류만', () => {
    const s = parsePoi('supermarket,medical:dental+oriental,academy:language')
    expect(s).toEqual({ supermarket: [], medical: ['dental', 'oriental'], academy: ['language'] })
    expect(formatPoi(s)).toBe('supermarket,medical:dental+oriental,academy:language')
    expect(formatPoi({ medical: ['oriental', 'hospital', 'clinic', 'dental'] })).toBe('medical')
    expect(formatPoi({})).toBeNull()
  })
  it("URLSearchParams가 '+'를 공백으로 바꿔도 같은 값", () => {
    expect(parsePoi('academy:language arts')).toEqual({ academy: ['language', 'arts'] })
  })
  it('잘못된 값은 무시', () => {
    expect(parsePoi('cafe:x,unknown,medical:dental:extra,academy:nope+arts,,')).toEqual({ academy: ['arts'] })
    expect(parsePoi(null)).toEqual({})
  })
  it('주소창 왕복: layers와 겹치지 않음, 모두 꺼지면 파라미터 없음', () => {
    const s = parseUrl('?poi=academy:language+arts&layers=projects,pois')
    expect(s.poi).toEqual({ academy: ['language', 'arts'] })
    expect(s.layers.pois.visible).toBe(true)
    expect(s.layers.impact250.visible).toBe(false)
    const q = toSearch(s)
    expect(q).toContain('poi=academy%3Alanguage%2Barts')
    expect(q).toContain('layers=projects')
    expect(q).not.toContain('pois')
    expect(mergeSearch('', q)).toContain('poi=academy:language+arts')
    expect(parseUrl(mergeSearch('', q))).toEqual(s)
    // poi 없이 layers에 pois만 있으면 꺼짐
    expect(parseUrl('?layers=projects,pois').layers.pois.visible).toBe(false)
    expect(toSearch(parseUrl('?poi=,,'))).toBe('')
  })
})

describe('지도 expression (setFilter만)', () => {
  it('하위 분류가 모두 켜졌으면 필터 없음', () => {
    expect(iconFilter('medical', ['hospital', 'clinic', 'dental', 'oriental'])).toEqual(['!', HAS])
    expect(clusterFilter('medical', ['hospital', 'clinic', 'dental', 'oriental'])).toEqual(HAS)
    expect(iconFilter('cafe', [])).toEqual(['!', HAS])
  })
  it('일부: 낱점은 sub_category, 클러스터는 켠 하위 분류 건수 합 > 0', () => {
    expect(iconFilter('medical', ['dental'])).toEqual(['all', ['!', HAS], ['in', ['get', 'sub_category'], ['literal', ['치과']]]])
    expect(clusterCountExpr('academy', ['language', 'arts'])).toEqual(['+', ['get', 'n_language'], ['get', 'n_arts']])
    expect(clusterFilter('medical', ['dental'])).toEqual(['all', HAS, ['>', ['get', 'n_dental'], 0]])
  })
  it('clusterProperties: 하위 분류마다 건수, 하위 분류 없는 분류는 없음', () => {
    expect(clusterProperties('cafe')).toBeUndefined()
    expect(clusterProperties('medical')!.n_dental).toEqual(['+', ['case', ['==', ['get', 'sub_category'], '치과'], 1, 0]])
  })
  it('개수 마커: 켠 하위 분류 합만', () => {
    const p = { point_count: 10, n_hospital: 1, n_clinic: 5, n_dental: 3, n_oriental: 1 }
    expect(clusterCount(p, 'medical', ['dental'])).toBe(3)
    expect(clusterCount(p, 'medical', ['hospital', 'clinic', 'dental', 'oriental'])).toBe(10)
  })
})
