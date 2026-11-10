/**
 * P15 공식 참고 레이어·필지 클릭 조회 (docs/map/PLAN.md): 클릭 우선순위, 요청 취소, URL sel=parcel 복원, 참고 레이어 모양.
 */
import { describe, expect, it } from 'vitest'
import manifestRaw from '../../../public/data/layers/manifest.json?raw'
import { LatestRequest, parcelAtUrl, parcelByPnuUrl } from '../api/parcel'
import { defaultUrlState, isParcelLookup, parseSelected, parseUrl, toSearch } from '../state/url'
import { DEFAULT_COLORS, PANEL_LAYERS, paintPlan } from './layers'
import { decideClick } from './pick'
import {
  REF_GEO_IDS, REF_OPACITY, WMS, refAttributions, refGeoLayers, refWmsLayer, wmsTileUrl, zoomBlocked,
} from './reference'

describe('클릭 우선순위 (사업 → 규제 → 사업 필지 → 빈 곳 = 필지 조회)', () => {
  it('Propedia 도형이 없으면 필지 조회', () => {
    expect(decideClick([])).toEqual({ type: 'parcel-lookup' })
    expect(decideClick([{ id: 'ref:1', kind: 'reference' }])).toEqual({ type: 'parcel-lookup' }) // 참고는 대상 아님
  })
  it('하나면 바로 선택', () => {
    expect(decideClick([{ id: 'project:2', kind: 'project' }])).toEqual({ type: 'select', id: 'project:2' })
  })
  it('겹치면 우선순위 순서의 목록 (중복 제거)', () => {
    const d = decideClick([
      { id: 'parcel:2:1168011400106330002', kind: 'parcel' },
      { id: 'regulation:D10', kind: 'regulation' },
      { id: 'project:2', kind: 'project' },
      { id: 'project:2', kind: 'project' },
    ])
    expect(d.type).toBe('choose')
    if (d.type === 'choose') expect(d.items.map((x) => x.kind)).toEqual(['project', 'regulation', 'parcel'])
  })
})

describe('요청 취소 (빠르게 여러 번 누르면 이전 요청 취소)', () => {
  const deferred = <T,>() => {
    let resolve!: (v: T) => void
    const p = new Promise<T>((r) => (resolve = r))
    return { p, resolve }
  }
  it('새 요청이 오면 이전 요청은 abort되고 결과를 버린다', async () => {
    const lr = new LatestRequest()
    const signals: AbortSignal[] = []
    const a = deferred<string>()
    const b = deferred<string>()
    const ra = lr.run((s) => (signals.push(s), a.p))
    const rb = lr.run((s) => (signals.push(s), b.p))
    expect(signals[0].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)
    a.resolve('old')
    b.resolve('new')
    expect(await ra).toBeUndefined()
    expect(await rb).toEqual({ ok: true, value: 'new' })
  })
  it('실패는 오류로, 취소된 실패는 버린다', async () => {
    const lr = new LatestRequest()
    expect(await lr.run(() => Promise.reject(new Error('x')))).toEqual({ ok: false, error: new Error('x') })
    const p = lr.run((s) => new Promise((_, rej) => s.addEventListener('abort', () => rej(new Error('abort')))))
    lr.cancel()
    expect(await p).toBeUndefined()
  })
  it('요청 주소', () => {
    expect(parcelAtUrl(37.4987011, 127.0315774)).toBe('/api/v1/map/parcel-at?lat=37.498701&lon=127.031577')
    expect(parcelByPnuUrl('1168010100108230000')).toBe('/api/v1/map/parcel?pnu=1168010100108230000')
  })
})

describe('URL sel=parcel:{pnu} 복원', () => {
  it('19자리 PNU는 필지 조회, 사업:PNU는 Propedia 사업 필지', () => {
    const s = parseUrl('?sel=parcel:1168010100108230000')
    expect(s.selected).toEqual({ kind: 'parcel', id: '1168010100108230000' })
    expect(isParcelLookup(s.selected)).toBe(true)
    expect(isParcelLookup(parseSelected('parcel:1:1168011000105280000'))).toBe(false)
    expect(isParcelLookup(parseSelected('parcel:12345'))).toBe(false)
    expect(parseUrl(toSearch(s)).selected).toEqual(s.selected)
  })
  it('참고 레이어 id도 layers=에서 왕복, 기본은 꺼짐', () => {
    const d = defaultUrlState()
    expect(d.layers['ref-seoulplan'].visible).toBe(false)
    const s = parseUrl('?layers=projects,ref-seoulplan,ref-cadastral')
    expect([s.layers['ref-seoulplan'].visible, s.layers['ref-cadastral'].visible, s.layers['ref-uije'].visible])
      .toEqual([true, true, false])
    expect(parseUrl(toSearch(s)).layers).toEqual(s.layers)
  })
})

describe('공식 참고 레이어 모양 (회색 점선 + 면 8%, 종류별 색 없음)', () => {
  const man = JSON.parse(manifestRaw).layers
  it('빌드 GeoJSON 2종: 점선·면 8%, 색 하나', () => {
    for (const id of REF_GEO_IDS) {
      const [fill, line] = refGeoLayers(id, DEFAULT_COLORS.ref) as { paint: Record<string, unknown> }[]
      expect(fill.paint['fill-opacity']).toBe(0.08)
      expect(fill.paint['fill-color']).toBe(DEFAULT_COLORS.ref)
      expect(line.paint['line-dasharray']).toBeTruthy()
      expect(line.paint['line-color']).toBe(DEFAULT_COLORS.ref)
    }
    expect(man.ref_seoulplan.lazy && man.ref_uije.lazy).toBe(true)
  })
  it('WMS: 이름·줌 조건 (지적도 17 — 0.6m/px보다 거칠면 빈 그림, 나머지 14), 투명도 슬라이더 연결', () => {
    expect(WMS['ref-cadastral']).toMatchObject({ layer: 'lp_pa_cbnd_bubun', minZoom: 17 })
    expect(refWmsLayer('ref-zoning')).toMatchObject({ minzoom: 14, source: 'ref-zoning' })
    expect(zoomBlocked('ref-cadastral', 16.5)).toBe(17)
    expect(zoomBlocked('ref-cadastral', 17)).toBeNull()
    expect(zoomBlocked('ref-seoulplan', 10)).toBeNull()
    expect(PANEL_LAYERS['ref-zoning'].layers).toEqual(['ref-zoning-raster'])
    expect(paintPlan('ref-zoning', 50, false)).toEqual([['ref-zoning-raster', 'raster-opacity', REF_OPACITY.raster / 2]])
    // 브이월드 WMS는 CORS 헤더가 없어 API 프록시로 받는다 (브라우저에 키 없음)
    const url = wmsTileUrl('lp_pa_cbnd_bubun', 'http://localhost:3000')
    expect(url).toBe('http://localhost:3000/api/v1/map/wms/lp_pa_cbnd_bubun/{z}/{x}/{y}.png')
    expect(url).not.toMatch(/key=/i)
  })
  it('켜진 참고 레이어 출처를 이어 붙인다', () => {
    expect(refAttributions(() => false)).toEqual([])
    const on = refAttributions((id) => id === 'ref-uije' || id === 'ref-cadastral')
    expect(on).toHaveLength(2)
    expect(on[0]).toContain('의제처리구역')
  })
})
