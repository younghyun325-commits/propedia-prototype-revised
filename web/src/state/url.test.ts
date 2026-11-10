import { describe, expect, it } from 'vitest'
import { DEFAULT_VISIBLE, defaultUrlState, mergeSearch, parseSelected, parseUrl, toSearch } from './url'

describe('URL ↔ 상태 (P14)', () => {
  it('기본값: 사업 구역·영향권 250·500·필지·학교·지하철역 켜짐, 규제·버스정류장·편의시설 꺼짐, 회색 배경, 레이어 탭', () => {
    const s = parseUrl('')
    expect(DEFAULT_VISIBLE).toEqual(['projects', 'impact250', 'impact500', 'parcels', 'schools', 'stations'])
    expect([s.layers.bus_stops.visible, s.layers.pois.visible]).toEqual([false, false])
    expect([s.poi, s.route, s.radius]).toEqual([{}, null, null])
    expect(s.layers.regulations.visible).toBe(false)
    expect(s.layers.projects).toEqual({ visible: true, opacity: 100 })
    expect([s.basemap, s.leftTab, s.overlap, s.selected, s.camera]).toEqual(['gray', 'layers', false, null, null])
    expect(toSearch(s)).toBe('')
  })

  it('예시 주소 그대로 읽고 다시 씀 (왕복)', () => {
    const q = '?layers=projects,impact250,parcels,regulations&op=projects:80&base=satellite&ov=1&sel=project:1&tab=status&c=127.05,37.50&z=13'
    const s = parseUrl(q)
    expect(s.layers.impact500.visible).toBe(false)
    expect(s.layers.regulations.visible).toBe(true)
    expect(s.layers.projects.opacity).toBe(80)
    expect(s.basemap).toBe('satellite')
    expect(s.overlap).toBe(true)
    expect(s.selected).toEqual({ kind: 'project', id: '1' })
    expect(s.leftTab).toBe('status')
    expect(s.camera).toEqual({ lon: 127.05, lat: 37.5, zoom: 13 })
    expect(parseUrl(toSearch(s))).toEqual(s)
  })

  it('필지 선택 id에 PNU가 들어가도 왕복', () => {
    const s = { ...defaultUrlState(), selected: parseSelected('parcel:1:1168011000105280000') }
    expect(s.selected).toEqual({ kind: 'parcel', id: '1:1168011000105280000' })
    expect(parseUrl(toSearch(s)).selected).toEqual(s.selected)
  })

  it('잘못된 값은 무시하고 기본값', () => {
    const s = parseUrl('?layers=foo,bar&op=projects:150,parcels:x,nope:10&base=gray2&ov=yes&sel=user:1&tab=xx&c=0,0&z=30')
    expect(s).toEqual(defaultUrlState())
    expect(parseUrl('?sel=project:').selected).toBeNull()
    expect(parseUrl('?sel=project:<script>').selected).toBeNull()
    expect(parseUrl('?c=127.05,37.5').camera).toBeNull() // 줌 없음
  })

  it('layers= (빈 값)은 모두 끔, 모르는 이름이 섞이면 아는 것만', () => {
    expect(Object.values(parseUrl('?layers=').layers).every((l) => !l.visible)).toBe(true)
    const s = parseUrl('?layers=projects,zzz')
    expect(s.layers.projects.visible).toBe(true)
    expect(s.layers.parcels.visible).toBe(false)
    expect(parseUrl(toSearch(parseUrl('?layers='))).layers.projects.visible).toBe(false)
  })

  it('다른 파라미터(debug)는 두고 우리 키만 바꿈', () => {
    expect(mergeSearch('?debug=1&sel=project:2', 'sel=project:1&ov=1')).toBe('?debug=1&sel=project:1&ov=1')
    expect(mergeSearch('?sel=project:2', '')).toBe('')
  })
})
