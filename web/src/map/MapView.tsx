/**
 * 지도 셸 (docs/map/PLAN.md P12): 브이월드 WMTS 배경 4종 + 강남구 스포트라이트 + 법정동 경계·이름.
 * P13: Propedia 검증 레이어 4종(사업 구역·영향권·규제 구역·포함 판정 필지, public/data/layers).
 * P14: 좌측 패널과 연결 — 켜기·끄기는 setLayoutProperty('visibility'), 투명도·겹침 보기는 setPaintProperty(식),
 *      선택·검색 강조는 setFilter (스타일을 다시 만들지 않음). 호버 툴팁, 클릭 선택(겹치면 선택 목록), 라벨 겹침 피하기.
 *
 * MapLibre v6은 ESM 전용이고, worker를 import.meta.url 옆의 maplibre-gl-worker.mjs에서 찾는다
 * (node_modules/maplibre-gl/build/readme.md). Vite는 라이브러리를 묶어 그 옆 파일이 없으므로
 * worker 파일을 ?url로 내보내고 setWorkerUrl()로 지정한다. react-map-gl에는 namespace import를 mapLib로 넘긴다.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Map, Marker, type MapRef, type MapLayerMouseEvent } from 'react-map-gl/maplibre'
import type { LayerSpecification, MapGeoJSONFeature, StyleSpecification } from 'maplibre-gl'
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { MapPin } from 'lucide-react'
import { useMapProjects } from '../api/map'
import { UI } from '../copy/ui'
import { useMapStore, type ParcelLookup } from '../state/useMapStore'
import { featureId, isParcelLookup, parseSelected, PANEL_LAYER_IDS, type LayerStates, type Selected } from '../state/url'
import { lookupParcelAt, lookupParcelByPnu } from '../state/parcelLookup'
import { decideClick } from './pick'
import {
  REF_GEO_IDS, REF_GEOJSON, REF_LABEL_MIN_ZOOM, REF_WMS_IDS, WMS, refAttributions, refGeoLayers, refWmsLayer,
  wmsTileUrl, type RefGeoId,
} from './reference'
import { GlassPanel } from '../ui/GlassPanel'
import { ATTRIBUTION, BASEMAPS, TILE_MAX_ZOOM, TILE_MIN_ZOOM, tileUrl } from './basemaps'
import { Callout } from './Callout'
import { bboxOf, labelPoint, outsideMask, padBounds, type Bounds } from './geo'
import { MapControls } from './MapControls'
import { estimateLabelWidth, placeLabels, REGULATION_LABEL_MIN_ZOOM, type Box, type Placement } from './labels'
import {
  HATCH_ID, LAYER_FILES, PANEL_LAYERS, PROPEDIA_SOURCES, dot, hatchImage, idFilter, labelText, paintPlan, propediaLayers,
  readHighlightColors, readLayerColors, type HighlightColors, type LayerColors, type LayerKind, type PropediaFC,
  type PropediaProps,
} from './layers'
import type { Insets } from './insets'

maplibregl.setWorkerUrl(workerUrl)

type Area = FeatureCollection<Polygon | MultiPolygon, { name: string; bjd_code?: string; sgg_code: string }>

const KEY = (import.meta.env.VITE_VWORLD_KEY ?? '').trim()
const MIN_ZOOM = 11
const MAX_ZOOM = 19
const TILT = 60
const PAD_M = 2000 // 이동 범위: 강남구 경계 + 약 2km (지도 중심 기준)
const INK = '#1f2328' // --color-ink (MapLibre 페인트는 CSS 변수를 못 읽는다)
const BG = '#e2e3e1' // 타일이 오기 전 바탕 (회색 배경 평균값과 비슷하게)
const LABEL_H = 18
const LABEL_LIFT = 14 // .map-area-label translateY(-14px)

type Propedia = Partial<Record<LayerKind, PropediaFC>>
const KINDS = Object.keys(LAYER_FILES) as LayerKind[]
// 클릭 대상은 Propedia 도형만 (참고 레이어는 클릭 대상 아님). 우선순위는 map/pick.ts
const HIT_LAYERS = ['propedia-project-fill', 'propedia-regulation-fill', 'propedia-parcel-hit'] as const
const HOVER_ORDER: Record<string, number> = { parcel: 0, regulation: 1, project: 2 } // 호버: 가장 작은 도형
const CLICK_SOURCE = 'click-parcel'
const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] }

type RefData = Partial<Record<RefGeoId, FeatureCollection<Polygon | MultiPolygon, Record<string, unknown>>>>

/** 스타일에 넣을 때와 지도에 바로 걸 때 같은 값을 쓰는 상태 묶음 */
type Snapshot = { layers: LayerStates; overlap: boolean; selected: Selected; searchPnu: string | null }

/** 클릭 필지 강조 도형: 결과가 있고 지금 선택이 그 필지일 때만 */
function clickParcelData(parcel: ParcelLookup, selected: Selected): FeatureCollection {
  if (parcel.status !== 'done' || parcel.data.status !== 'ok' || !parcel.data.boundary) return EMPTY_FC
  if (!isParcelLookup(selected) || selected.id !== parcel.data.pnu) return EMPTY_FC
  return { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { pnu: parcel.data.pnu }, geometry: parcel.data.boundary }] }
}

/** 점검 스크립트용 지도 객체 노출: 개발 서버 또는 ?debug=1일 때만 */
function exposeMap(): boolean {
  if (import.meta.env.DEV) return true
  try {
    return new URLSearchParams(window.location.search).get('debug') === '1'
  } catch {
    return false
  }
}

async function loadJson<T = Area>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`)
  return r.json()
}

/** 레이어 id → 패널 레이어 (보임 여부) */
const LAYER_OWNER: Record<string, (typeof PANEL_LAYER_IDS)[number]> = Object.fromEntries(
  PANEL_LAYER_IDS.flatMap((p) => PANEL_LAYERS[p].layers.map((l) => [l, p])),
)

function selectedFilterFor(layerId: string, sel: Selected): unknown[] {
  const kind = layerId.replace('propedia-', '').replace('-selected', '')
  return idFilter('id', sel && sel.kind === kind ? featureId(sel) : null)
}

/** 패널 상태를 레이어 정의에 넣는다 (배경 전환으로 스타일을 새로 만들 때도 상태 유지) */
function withState(specs: LayerSpecification[], snap: Snapshot): LayerSpecification[] {
  const paints: Record<string, Record<string, unknown>> = {}
  for (const id of PANEL_LAYER_IDS)
    for (const [layer, prop, v] of paintPlan(id, snap.layers[id].opacity, snap.overlap)) (paints[layer] ??= {})[prop] = v
  return specs.map((l) => {
    const owner = LAYER_OWNER[l.id]
    const out = { ...l } as LayerSpecification & { layout?: Record<string, unknown>; paint?: Record<string, unknown>; filter?: unknown }
    if (owner) out.layout = { ...(out.layout ?? {}), visibility: snap.layers[owner].visible ? 'visible' : 'none' }
    if (paints[l.id]) out.paint = { ...(out.paint ?? {}), ...paints[l.id] }
    if (l.id.endsWith('-selected')) out.filter = selectedFilterFor(l.id, snap.selected)
    if (l.id === 'propedia-parcel-search') out.filter = idFilter('pnu', snap.searchPnu)
    return out as LayerSpecification
  })
}

function buildStyle(
  basemap: keyof typeof BASEMAPS,
  gu: Area | null,
  dongs: Area | null,
  propedia: Propedia,
  colors: LayerColors,
  hl: HighlightColors,
  snap: Snapshot,
  ref: RefData = {},
  clickData: FeatureCollection = EMPTY_FC,
): StyleSpecification {
  const sources: StyleSpecification['sources'] = {}
  const layers: StyleSpecification['layers'] = [{ id: 'bg', type: 'background', paint: { 'background-color': BG } }]
  if (KEY) {
    BASEMAPS[basemap].layers.forEach((l, i) => {
      const id = `basemap-${basemap}-${i}`
      sources[id] = {
        type: 'raster',
        tiles: [tileUrl(KEY, l)],
        tileSize: 256,
        minzoom: TILE_MIN_ZOOM,
        maxzoom: TILE_MAX_ZOOM,
      }
      const paint = BASEMAPS[basemap].paint
      layers.push(paint ? { id, type: 'raster', source: id, paint } : { id, type: 'raster', source: id })
    })
  }
  if (gu) {
    sources.mask = { type: 'geojson', data: outsideMask(gu) }
    sources.gu = { type: 'geojson', data: gu }
    layers.push({ id: 'mask', type: 'fill', source: 'mask', paint: { 'fill-color': '#ffffff', 'fill-opacity': 0.55 } })
  }
  // 공식 참고 WMS (P15, API 프록시): 보이는 레이어가 있을 때만 MapLibre가 타일을 요청한다. 줌 조건은 소스·레이어 minzoom
  // bounds = 강남구 경계 bbox: 서버 허용 범위(경계 + 2km, P16 0단계) 밖 타일을 아예 요청하지 않는다
  const guBox = gu ? bboxOf(gu.features) : null
  for (const id of REF_WMS_IDS) {
    sources[id] = { type: 'raster', tiles: [wmsTileUrl(WMS[id].layer)], tileSize: 256, minzoom: WMS[id].minZoom,
      maxzoom: 19, ...(guBox ? { bounds: [guBox[0][0], guBox[0][1], guBox[1][0], guBox[1][1]] } : {}) }
  }
  layers.push(...withState(REF_WMS_IDS.map(refWmsLayer), snap))
  if (dongs) {
    sources.bjd = { type: 'geojson', data: dongs }
    // 커서 위치의 법정동을 찾기 위한 투명 면
    layers.push({ id: 'bjd-fill', type: 'fill', source: 'bjd', paint: { 'fill-color': INK, 'fill-opacity': 0 } })
    layers.push({
      id: 'bjd-line',
      type: 'line',
      source: 'bjd',
      paint: { 'line-color': INK, 'line-width': 0.75, 'line-opacity': 0.45 },
    })
  }
  // 공식 참고 GeoJSON (P15, 처음 켤 때 불러온 것만): Propedia 레이어 아래
  for (const id of REF_GEO_IDS) {
    if (!ref[id]) continue
    sources[id] = { type: 'geojson', data: ref[id]! }
    layers.push(...withState(refGeoLayers(id, colors.ref), snap))
  }
  // Propedia 검증 레이어 (스포트라이트 마스크·법정동 경계 위, 구 경계선 아래). 라벨은 HTML 마커
  const loadedKinds = KINDS.filter((k) => propedia[k])
  // 도형 id(feature.id)를 문자열 속성 id로 쓰도록 promoteId
  for (const k of loadedKinds) sources[PROPEDIA_SOURCES[k]] = { type: 'geojson', data: propedia[k]!, promoteId: 'id' }
  const specs = propediaLayers(colors, hl).filter(
    (l) => 'source' in l && loadedKinds.some((k) => PROPEDIA_SOURCES[k] === l.source),
  )
  layers.push(...withState(specs, snap))
  if (gu) {
    layers.push({ id: 'gu-line', type: 'line', source: 'gu', paint: { 'line-color': INK, 'line-width': 1.5 } })
  }
  // 빈 곳 클릭으로 조회한 필지 강조 (브랜드 색 외곽선, P15)
  sources[CLICK_SOURCE] = { type: 'geojson', data: clickData }
  layers.push({ id: 'click-parcel-line', type: 'line', source: CLICK_SOURCE,
    paint: { 'line-color': hl.selected, 'line-width': 3.5, 'line-blur': 0.5 } })
  return { version: 8, sources, layers }
}

type Hover = { x: number; y: number; text: string; id: string }
type Pick = { x: number; y: number; items: { id: string; kind: string; name: string }[] }

function propsOf(f: MapGeoJSONFeature): PropediaProps {
  return f.properties as unknown as PropediaProps
}

export default function MapView({ insets }: { insets: Insets }) {
  const mapRef = useRef<MapRef>(null)
  const basemap = useMapStore((s) => s.basemap)
  const tilt3d = useMapStore((s) => s.tilt3d)
  const layerStates = useMapStore((s) => s.layers)
  const overlap = useMapStore((s) => s.overlap)
  const selected = useMapStore((s) => s.selected)
  const searchHit = useMapStore((s) => s.searchHit)
  const viewRequest = useMapStore((s) => s.viewRequest)
  const mapMoving = useMapStore((s) => s.mapMoving)
  const setMapMoving = useMapStore((s) => s.setMapMoving)
  const projects = useMapProjects().data?.projects
  const [gu, setGu] = useState<Area | null>(null)
  const [dongs, setDongs] = useState<Area | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [propedia, setPropedia] = useState<Propedia>({})
  const colors = useMemo(() => readLayerColors(), [])
  const hl = useMemo(() => readHighlightColors(), [])
  const [cursor, setCursor] = useState<{ lat: number; lon: number; dong: string | null } | null>(null)
  const [hover, setHover] = useState<Hover | null>(null)
  const [pick, setPick] = useState<Pick | null>(null)
  const [placements, setPlacements] = useState<Record<string, Placement>>({})
  const initialCamera = useRef(useMapStore.getState().camera)
  const parcel = useMapStore((s) => s.parcel)
  const [refData, setRefData] = useState<RefData>({})
  const refLoading = useRef(new Set<RefGeoId>())

  // 공식 참고 GeoJSON: 행을 처음 켤 때만 불러온다 (켤 때 불러오기). 한 번 받은 것은 다시 받지 않는다
  useEffect(() => {
    for (const id of REF_GEO_IDS) {
      if (!layerStates[id].visible || refData[id] || refLoading.current.has(id)) continue
      refLoading.current.add(id)
      loadJson<NonNullable<RefData[RefGeoId]>>(REF_GEOJSON[id].file)
        .then((fc) => setRefData((d) => ({ ...d, [id]: fc })))
        .catch((e: Error) => {
          refLoading.current.delete(id)
          setLoadError(`${UI.reference.loadError} (${e.message})`)
        })
    }
  }, [layerStates, refData])

  useEffect(() => {
    Promise.all([loadJson('/data/base/gangnam.geojson'), loadJson('/data/base/bjd.geojson')])
      .then(([g, d]) => {
        setGu(g)
        setDongs(d)
      })
      .catch((e: Error) => setLoadError(`경계 데이터를 불러오지 못했습니다 (${e.message})`))
    // Propedia 레이어: 하나가 없어도 나머지는 그린다
    Promise.allSettled(KINDS.map((k) => loadJson<PropediaFC>(LAYER_FILES[k]))).then((rs) => {
      const got: Propedia = {}
      const failed: string[] = []
      rs.forEach((r, i) => (r.status === 'fulfilled' ? (got[KINDS[i]] = r.value) : failed.push(KINDS[i])))
      setPropedia(got)
      if (failed.length) setLoadError(`Propedia 레이어를 불러오지 못했습니다 (${failed.join(', ')})`)
    })
  }, [])

  const guBounds: Bounds | null = useMemo(() => (gu ? bboxOf(gu.features) : null), [gu])
  const panBounds = useMemo(() => (guBounds ? padBounds(guBounds, PAD_M) : null), [guBounds])
  const labels = useMemo(
    () =>
      (dongs?.features ?? []).map((f) => ({
        id: f.properties.bjd_code ?? f.properties.name,
        name: f.properties.name,
        at: labelPoint(f.geometry),
      })),
    [dongs],
  )
  // 스타일은 배경·데이터가 바뀔 때만 새로 만든다. 패널 상태는 만들 때의 값을 넣고, 이후 변경은 아래 effect가 지도에 바로 건다
  const style = useMemo(() => {
    const s = useMapStore.getState()
    return buildStyle(basemap, gu, dongs, propedia, colors, hl, {
      layers: s.layers, overlap: s.overlap, selected: s.selected, searchPnu: s.searchHit?.pnu ?? null,
    }, refData, clickParcelData(s.parcel, s.selected))
  }, [basemap, gu, dongs, propedia, colors, hl, refData])

  // 사업·규제 구역 라벨 (사람 확인 전이면 '확인 전')
  const areaLabels = useMemo(
    () =>
      (['project', 'regulation'] as const).flatMap((k) =>
        (propedia[k]?.features ?? []).map((f) => ({
          id: f.properties.id,
          kind: k,
          text: labelText(f.properties),
          at: labelPoint(f.geometry as Polygon | MultiPolygon),
        })),
      ),
    [propedia],
  )

  // 공식 참고 라벨: 줌 15 이상, DGM_NM + '참고' (Propedia 라벨 다음 순위로 겹침 피하기)
  const refVisible = REF_GEO_IDS.map((id) => (layerStates[id].visible ? '1' : '0')).join('')
  const refLabels = useMemo(
    () =>
      REF_GEO_IDS.filter((_, i) => refVisible[i] === '1').flatMap((id) =>
        (refData[id]?.features ?? []).map((f, i) => ({
          id: `ref:${id}:${i}`,
          layer: id,
          text: `${String(f.properties.DGM_NM ?? '')} · ${UI.reference.labelSuffix}`,
          at: labelPoint(f.geometry),
        })),
      ),
    [refData, refVisible],
  )

  const [loaded, setLoaded] = useState(false)
  const getMap = () => mapRef.current?.getMap()

  // ---- 패널 상태 → 지도 (setLayoutProperty·setPaintProperty·setFilter, 다시 그리지 않음)
  const applyState = useCallback(() => {
    const map = getMap()
    if (!map || !map.isStyleLoaded()) return
    const s = useMapStore.getState()
    for (const id of PANEL_LAYER_IDS) {
      const vis = s.layers[id].visible ? 'visible' : 'none'
      for (const l of PANEL_LAYERS[id].layers) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', vis)
      for (const [l, prop, v] of paintPlan(id, s.layers[id].opacity, s.overlap))
        if (map.getLayer(l)) map.setPaintProperty(l, prop as never, v as never)
    }
    for (const k of ['project', 'regulation', 'parcel']) {
      const l = `propedia-${k}-selected`
      if (map.getLayer(l)) map.setFilter(l, selectedFilterFor(l, s.selected) as never)
    }
    if (map.getLayer('propedia-parcel-search'))
      map.setFilter('propedia-parcel-search', idFilter('pnu', s.searchHit?.pnu ?? null) as never)
    const click = map.getSource(CLICK_SOURCE) as maplibregl.GeoJSONSource | undefined
    click?.setData(clickParcelData(s.parcel, s.selected) as never)
  }, [])
  useEffect(() => {
    if (loaded) applyState()
  }, [loaded, layerStates, overlap, selected, searchHit, parcel, applyState])

  // 새로고침: URL sel=parcel:{pnu}면 같은 필지를 다시 조회해 강조한다 (한 번)
  const restored = useRef(false)
  useEffect(() => {
    if (!loaded || restored.current) return
    restored.current = true
    const s = useMapStore.getState()
    if (isParcelLookup(s.selected) && s.parcel.status === 'idle') void lookupParcelByPnu(s.selected.id)
  }, [loaded])

  // 이동 범위: 지도 중심을 강남구 경계 + 약 2km 안으로 묶는다.
  // MapLibre maxBounds는 화면 전체(패널 밑 포함)를 그 안에 넣으려고 줌을 키워 버려서(1440px 화면에서 줌 ~13.5)
  // 첫 화면에 강남구 전체가 들어가지 않는다 → maxBounds 대신 중심 제한(setTransformConstrain)을 쓴다.
  useEffect(() => {
    const map = getMap()
    if (!loaded || !map || !panBounds) return
    const [[w, so], [e, n]] = panBounds
    const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
    map.setTransformConstrain((lngLat, zoom) => ({
      center: new maplibregl.LngLat(clamp(lngLat.lng, w, e), clamp(lngLat.lat, so, n)),
      zoom: clamp(zoom, MIN_ZOOM, MAX_ZOOM),
    }))
    return () => {
      map.setTransformConstrain(null)
    }
  }, [loaded, panBounds])

  const padding = useCallback(
    (extra = 24) => ({ top: insets.top + extra, bottom: insets.bottom + extra, left: insets.left + extra, right: insets.right + extra }),
    [insets],
  )

  // 첫 화면: URL에 카메라가 있으면 그대로, 없으면 패널을 뺀 영역에 강남구를 맞춘다 (한 번만)
  const fitted = useRef(initialCamera.current !== null)
  useEffect(() => {
    const map = mapRef.current
    if (!loaded || !map || !guBounds || fitted.current) return
    fitted.current = true
    map.fitBounds(guBounds, { padding: { ...insets, top: insets.top + 24, bottom: insets.bottom + 24 }, duration: 0 })
  }, [loaded, guBounds, insets])

  // 이동 요청 (작업 탭·사업 카드·검색)
  useEffect(() => {
    const map = mapRef.current
    if (!loaded || !map || !viewRequest) return
    if (viewRequest.type === 'home') {
      if (guBounds) map.fitBounds(guBounds, { padding: { ...insets, top: insets.top + 24, bottom: insets.bottom + 24 }, duration: 600 })
    } else {
      const [w, s, e, n] = viewRequest.bbox
      map.fitBounds([[w, s], [e, n]], { padding: padding(60), maxZoom: 17, duration: 600 })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, viewRequest?.nonce])

  // 검색 결과: 필지 경계가 있으면 그 경계로, 없으면 임시 핀 위치로
  useEffect(() => {
    const map = mapRef.current
    if (!loaded || !map || !searchHit) return
    const f = searchHit.pnu ? propedia.parcel?.features.find((x) => x.properties.pnu === searchHit.pnu) : undefined
    if (f) {
      const b = bboxOf([f as Feature<Polygon | MultiPolygon>])
      map.fitBounds(b, { padding: padding(80), maxZoom: 18, duration: 600 })
    } else if (searchHit.point) {
      map.flyTo({ center: searchHit.point, zoom: 17, duration: 600 })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, searchHit?.nonce])
  const searchHasParcel = !!(searchHit?.pnu && propedia.parcel?.features.some((x) => x.properties.pnu === searchHit.pnu))

  // URL로 복원한 필지 조회 결과: 그 경계로 이동 (클릭 조회는 이동하지 않음)
  const fittedReq = useRef<number | null>(null)
  useEffect(() => {
    const map = mapRef.current
    if (!loaded || !map || parcel.status !== 'done' || !parcel.fit || fittedReq.current === parcel.reqId) return
    const g = parcel.data.boundary
    if (parcel.data.status !== 'ok' || !g || (g.type !== 'Polygon' && g.type !== 'MultiPolygon')) return
    fittedReq.current = parcel.reqId
    map.fitBounds(bboxOf([{ type: 'Feature', properties: {}, geometry: g }]), { padding: padding(80), maxZoom: 18, duration: 0 })
  }, [loaded, parcel, padding])

  // 3D 기울기
  useEffect(() => {
    mapRef.current?.easeTo({ pitch: tilt3d ? TILT : 0, duration: 600 })
  }, [tilt3d])

  // ---- 라벨 배치: 이동이 끝날 때마다 (줌별 표시 + 겹침 피하기)
  const relayout = useCallback(() => {
    const map = getMap()
    if (!map) return
    const zoom = map.getZoom()
    const obstacles: Box[] = labels.map((l) => {
      const p = map.project(l.at as [number, number])
      return { x: p.x, y: p.y, w: estimateLabelWidth(l.name, 12, 7, 4), h: 16 }
    })
    const inputs = areaLabels.map((l) => {
      const p = map.project(l.at as [number, number])
      return {
        id: l.id,
        x: p.x,
        y: p.y - LABEL_LIFT,
        w: estimateLabelWidth(l.text),
        h: LABEL_H,
        keep: l.kind === 'project',
        minZoom: l.kind === 'regulation' ? REGULATION_LABEL_MIN_ZOOM : undefined,
      }
    })
    const refInputs = refLabels.map((l) => {
      const p = map.project(l.at as [number, number])
      return { id: l.id, x: p.x, y: p.y - LABEL_LIFT, w: estimateLabelWidth(l.text), h: LABEL_H, minZoom: REF_LABEL_MIN_ZOOM }
    })
    setPlacements(placeLabels([...inputs, ...refInputs], zoom, obstacles))
  }, [labels, areaLabels, refLabels])
  useEffect(() => {
    if (loaded) relayout()
  }, [loaded, relayout])

  // ---- 호버·클릭
  const hoverText = useCallback(
    (f: MapGeoJSONFeature): string => {
      const p = propsOf(f)
      const tail = p.verified ? '' : ` · ${UI.map.unverified}`
      if (p.kind === 'project') {
        const line = projects?.find((x) => x.feature_id === p.id)?.hover_line ?? p.short_name ?? p.name
        return `${line}${tail}`
      }
      if (p.kind === 'parcel') return `${p.name} · ${UI.map.inclusion[p.inclusion ?? ''] ?? ''}${tail}`
      const eff = p.effective_from && p.effective_to ? ` · ${dot(p.effective_from)}~${dot(p.effective_to)}` : ''
      return `${p.name}${eff}${tail}`
    },
    [projects],
  )

  const targetsAt = (e: MapLayerMouseEvent) => {
    const seen = new Set<string>()
    return (e.features ?? [])
      .filter((f) => (HIT_LAYERS as readonly string[]).includes(f.layer.id))
      .filter((f) => {
        const id = propsOf(f).id
        if (seen.has(id)) return false
        seen.add(id)
        return true
      })
  }

  const onMouseMove = (e: MapLayerMouseEvent) => {
    const dongF = e.features?.find((f) => f.layer.id === 'bjd-fill')
    setCursor({ lat: e.lngLat.lat, lon: e.lngLat.lng, dong: (dongF?.properties?.name as string | undefined) ?? null })
    const ts = targetsAt(e).sort((a, b) => HOVER_ORDER[propsOf(a).kind] - HOVER_ORDER[propsOf(b).kind])
    const t = ts[0]
    const st = useMapStore.getState()
    if (!t || st.mapMoving) {
      if (hover) setHover(null)
      if (st.hovered) st.setHovered(null)
      return
    }
    const id = propsOf(t).id
    setHover({ x: e.point.x, y: e.point.y, text: hoverText(t), id })
    if (st.hovered !== id) st.setHovered(id)
  }

  const onClick = (e: MapLayerMouseEvent) => {
    const feats = targetsAt(e)
    const d = decideClick(feats.map((f) => ({ id: propsOf(f).id, kind: propsOf(f).kind })))
    if (pick) {
      setPick(null) // 열린 선택 목록은 바깥을 누르면 닫기만 한다
      if (d.type === 'parcel-lookup') return
    }
    if (d.type === 'parcel-lookup') {
      // 빈 곳 = 필지 조회 (P15). 이전 요청은 취소된다
      void lookupParcelAt(e.lngLat.lat, e.lngLat.lng)
      return
    }
    if (d.type === 'select') {
      setPick(null)
      useMapStore.getState().select(parseSelected(d.id))
      return
    }
    const byId = new globalThis.Map(feats.map((f) => [propsOf(f).id, propsOf(f)]))
    setPick({
      x: e.point.x,
      y: e.point.y,
      items: d.items.map((it) => {
        const p = byId.get(it.id)!
        return { id: p.id, kind: p.kind, name: p.kind === 'project' ? (p.short_name ?? p.name) : p.name }
      }),
    })
  }

  useEffect(() => {
    if (!pick) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setPick(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pick])

  const interactive = useMemo(
    () => [...(dongs ? ['bjd-fill'] : []), ...HIT_LAYERS.filter((l) => style.layers.some((x) => x.id === l))],
    [dongs, style],
  )

  return (
    <div
      className="absolute inset-0"
      data-testid="map"
      aria-label="지도"
      data-basemap={basemap}
      data-layers={style.layers.map((l) => l.id).join(',')}
    >
      <Map
        ref={mapRef}
        mapLib={maplibregl}
        mapStyle={style}
        initialViewState={
          initialCamera.current
            ? { longitude: initialCamera.current.lon, latitude: initialCamera.current.lat, zoom: initialCamera.current.zoom }
            : { longitude: 127.06, latitude: 37.49, zoom: 12 }
        }
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
        maxPitch={TILT}
        attributionControl={false}
        interactiveLayerIds={interactive}
        cursor={hover ? 'pointer' : 'default'}
        onMouseMove={onMouseMove}
        onMouseOut={() => {
          setCursor(null)
          setHover(null)
        }}
        onClick={onClick}
        onMoveStart={() => {
          setMapMoving(true)
          setHover(null)
          setPick(null)
        }}
        onMoveEnd={(e) => {
          setMapMoving(false)
          const c = e.target.getCenter()
          useMapStore.getState().setCamera({ lon: c.lng, lat: c.lat, zoom: e.target.getZoom() })
          useMapStore.getState().setZoom(e.target.getZoom())
          relayout()
        }}
        onLoad={() => {
          const map = getMap()
          // 규제 구역 빗금: 스타일이 바뀌어도(배경 전환) 없으면 다시 넣는다
          const addHatch = () => {
            if (map && !map.hasImage(HATCH_ID)) map.addImage(HATCH_ID, hatchImage(colors.regulation))
          }
          addHatch()
          map?.on('styleimagemissing', (e: { id: string }) => e.id === HATCH_ID && addHatch())
          // 점검 스크립트(tests/ui_check_map.py)가 페인트·렌더된 도형을 확인할 수 있게: 개발 서버 또는 ?debug=1일 때만
          if (exposeMap()) (window as unknown as { __propediaMap?: unknown }).__propediaMap = map
          if (map) useMapStore.getState().setZoom(map.getZoom())
          setLoaded(true)
        }}
        style={{ position: 'absolute', inset: 0 }}
      >
        {areaLabels.map((l) => {
          const pl = placements[l.id]
          if (pl && !pl.visible) return null
          // 선택한 사업·규제는 콜아웃(P16)이 같은 내용을 보여 주므로 라벨을 숨긴다
          if (selected && featureId(selected) === l.id) return null
          return (
            <Marker key={l.id} longitude={l.at[0]} latitude={l.at[1]} anchor="center" offset={pl ? [pl.dx, pl.dy] : [0, 0]}>
              <span
                className={`map-area-label map-area-label--${l.kind}`}
                data-testid="area-label"
                data-kind={l.kind}
                data-anchor={pl?.anchor ?? 'center'}
              >
                {l.text}
              </span>
            </Marker>
          )
        })}
        {refLabels.map((l) => {
          const pl = placements[l.id]
          if (!pl || !pl.visible) return null
          return (
            <Marker key={l.id} longitude={l.at[0]} latitude={l.at[1]} anchor="center" offset={[pl.dx, pl.dy]}>
              <span className="map-area-label map-area-label--reference" data-testid="ref-label" data-layer={l.layer}>
                {l.text}
              </span>
            </Marker>
          )
        })}
        {parcel.status === 'loading' && parcel.point && (
          <Marker longitude={parcel.point[0]} latitude={parcel.point[1]} anchor="bottom">
            <span className="map-area-label" role="status" data-testid="parcel-loading-marker">{UI.parcel.loading}</span>
          </Marker>
        )}
        {labels.map((l) => (
          <Marker key={l.id} longitude={l.at[0]} latitude={l.at[1]} anchor="center">
            <span className="map-dong-label" data-testid="dong-label">
              {l.name}
            </span>
          </Marker>
        ))}
        {searchHit?.point && !searchHasParcel && (
          <Marker longitude={searchHit.point[0]} latitude={searchHit.point[1]} anchor="bottom">
            <span className="map-search-pin" data-testid="search-pin" aria-label={`${UI.map.searchPin}: ${searchHit.label}`}>
              <MapPin size={28} aria-hidden="true" />
            </span>
          </Marker>
        )}
      </Map>
      <Callout getMap={getMap} loaded={loaded} insets={insets} />

      <MapControls insets={insets} hasKey={Boolean(KEY)} />

      {/* 호버 툴팁 (이동 중 숨김) */}
      {hover && !mapMoving && (
        <GlassPanel
          role="tooltip"
          data-testid="map-tooltip"
          className="map-tooltip pointer-events-none absolute px-3 py-1.5 text-xs"
          style={{ left: hover.x + 14, top: hover.y + 14, borderRadius: 10, maxWidth: 360 }}
        >
          {hover.text}
        </GlassPanel>
      )}

      {/* 한 지점에 둘 이상 겹치면 선택 목록 */}
      {pick && (
        <GlassPanel
          role="menu"
          aria-label={UI.map.pickTitle}
          data-testid="pick-list"
          className="absolute p-1.5 text-sm"
          style={{ left: pick.x + 8, top: pick.y + 8, borderRadius: 12, minWidth: 220 }}
        >
          <p className="px-2 py-1 text-xs text-ink-muted">{UI.map.pickTitle}</p>
          {pick.items.map((it) => (
            <button
              key={it.id}
              role="menuitem"
              data-testid="pick-item"
              data-id={it.id}
              onClick={() => {
                useMapStore.getState().select(parseSelected(it.id))
                setPick(null)
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-brand-indigo/10"
            >
              <span className="text-xs text-ink-muted">{UI.map.pickKind[it.kind]}</span>
              <span className="truncate">{it.name}</span>
            </button>
          ))}
        </GlassPanel>
      )}

      {/* 커서 위치 표시줄 */}
      <div
        data-testid="cursor-bar"
        className="glass pointer-events-none absolute px-3 py-1 text-xs"
        style={{ left: insets.left, bottom: insets.bottom, borderRadius: 999 }}
      >
        {cursor
          ? `위도 ${cursor.lat.toFixed(5)} · 경도 ${cursor.lon.toFixed(5)} · ${cursor.dong ?? '강남구 밖'}`
          : '지도 위에 커서를 올리면 위치가 표시됩니다'}
      </div>

      {/* 출처 (우하단) */}
      <div
        data-testid="attribution"
        className="glass pointer-events-none absolute px-3 py-1 text-right text-xs"
        // 참고 레이어 출처가 붙으면 길어진다: 왼쪽 커서 표시줄(약 280px)과 패널을 피해 줄을 바꾼다
        style={{ right: insets.right, bottom: insets.bottom, borderRadius: 12, maxWidth: `calc(100% - ${insets.left + insets.right + 280}px)` }}
      >
        {[ATTRIBUTION, ...refAttributions((id) => layerStates[id].visible)].join(' · ')}
      </div>

      {loadError && (
        <div role="alert" className="glass absolute px-4 py-2 text-sm" style={{ left: insets.left, top: insets.top }}>
          {loadError}
        </div>
      )}
    </div>
  )
}
