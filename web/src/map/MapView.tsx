/**
 * 지도 셸 (docs/map/PLAN.md P12): 브이월드 WMTS 배경 4종 + 강남구 스포트라이트 + 법정동 경계·이름.
 * P13: Propedia 검증 레이어 4종(사업 구역·영향권·규제 구역·포함 판정 필지, public/data/layers) — 패널 없이 표시만.
 *
 * MapLibre v6은 ESM 전용이고, worker를 import.meta.url 옆의 maplibre-gl-worker.mjs에서 찾는다
 * (node_modules/maplibre-gl/build/readme.md). Vite는 라이브러리를 묶어 그 옆 파일이 없으므로
 * worker 파일을 ?url로 내보내고 setWorkerUrl()로 지정한다. react-map-gl에는 namespace import를 mapLib로 넘긴다.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Map, Marker, type MapRef, type MapLayerMouseEvent } from 'react-map-gl/maplibre'
import type { StyleSpecification } from 'maplibre-gl'
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { useMapStore } from '../state/useMapStore'
import { ATTRIBUTION, BASEMAPS, TILE_MAX_ZOOM, TILE_MIN_ZOOM, tileUrl } from './basemaps'
import { bboxOf, labelPoint, outsideMask, padBounds, type Bounds } from './geo'
import { MapControls } from './MapControls'
import {
  HATCH_ID, LAYER_FILES, PROPEDIA_SOURCES, hatchImage, labelText, propediaLayers, readLayerColors,
  type LayerColors, type LayerKind, type PropediaFC,
} from './layers'

maplibregl.setWorkerUrl(workerUrl)

type Area = FeatureCollection<Polygon | MultiPolygon, { name: string; bjd_code?: string; sgg_code: string }>

import type { Insets } from './insets'

const KEY = (import.meta.env.VITE_VWORLD_KEY ?? '').trim()
const MIN_ZOOM = 11
const MAX_ZOOM = 19
const TILT = 60
const PAD_M = 2000 // 이동 범위: 강남구 경계 + 약 2km (지도 중심 기준)
const INK = '#1f2328' // --color-ink (MapLibre 페인트는 CSS 변수를 못 읽는다)
const BG = '#e2e3e1' // 타일이 오기 전 바탕 (회색 배경 평균값과 비슷하게)

type Propedia = Partial<Record<LayerKind, PropediaFC>>
const KINDS = Object.keys(LAYER_FILES) as LayerKind[]

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

function buildStyle(
  basemap: keyof typeof BASEMAPS,
  gu: Area | null,
  dongs: Area | null,
  propedia: Propedia,
  colors: LayerColors,
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
  // Propedia 검증 레이어 (스포트라이트 마스크·법정동 경계 위, 구 경계선 아래). 라벨은 HTML 마커
  const loadedKinds = KINDS.filter((k) => propedia[k])
  for (const k of loadedKinds) sources[PROPEDIA_SOURCES[k]] = { type: 'geojson', data: propedia[k]! }
  layers.push(...propediaLayers(colors).filter((l) => 'source' in l && loadedKinds.some((k) => PROPEDIA_SOURCES[k] === l.source)))
  if (gu) {
    layers.push({ id: 'gu-line', type: 'line', source: 'gu', paint: { 'line-color': INK, 'line-width': 1.5 } })
  }
  return { version: 8, sources, layers }
}

export default function MapView({ insets }: { insets: Insets }) {
  const mapRef = useRef<MapRef>(null)
  const basemap = useMapStore((s) => s.basemap)
  const tilt3d = useMapStore((s) => s.tilt3d)
  const setMapMoving = useMapStore((s) => s.setMapMoving)
  const [gu, setGu] = useState<Area | null>(null)
  const [dongs, setDongs] = useState<Area | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [propedia, setPropedia] = useState<Propedia>({})
  const colors = useMemo(() => readLayerColors(), [])
  const [cursor, setCursor] = useState<{ lat: number; lon: number; dong: string | null } | null>(null)

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
  const style = useMemo(() => buildStyle(basemap, gu, dongs, propedia, colors), [basemap, gu, dongs, propedia, colors])
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

  // 이동 범위: 지도 중심을 강남구 경계 + 약 2km 안으로 묶는다.
  // MapLibre maxBounds는 화면 전체(패널 밑 포함)를 그 안에 넣으려고 줌을 키워 버려서(1440px 화면에서 줌 ~13.5)
  // 첫 화면에 강남구 전체가 들어가지 않는다 → maxBounds 대신 중심 제한(setTransformConstrain)을 쓴다.
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    const map = mapRef.current?.getMap()
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

  // 첫 화면: 패널을 뺀 영역에 강남구를 맞춘다 (한 번만)
  const fitted = useRef(false)
  useEffect(() => {
    const map = mapRef.current
    if (!loaded || !map || !guBounds || fitted.current) return
    fitted.current = true
    map.fitBounds(guBounds, { padding: { ...insets, top: insets.top + 24, bottom: insets.bottom + 24 }, duration: 0 })
  }, [loaded, guBounds, insets])

  // 3D 기울기
  useEffect(() => {
    mapRef.current?.easeTo({ pitch: tilt3d ? TILT : 0, duration: 600 })
  }, [tilt3d])

  const onMouseMove = (e: MapLayerMouseEvent) => {
    const dong = (e.features?.[0]?.properties?.name as string | undefined) ?? null
    setCursor({ lat: e.lngLat.lat, lon: e.lngLat.lng, dong })
  }

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
        initialViewState={{ longitude: 127.06, latitude: 37.49, zoom: 12 }}
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
        maxPitch={TILT}
        attributionControl={false}
        interactiveLayerIds={dongs ? ['bjd-fill'] : []}
        cursor="default"
        onMouseMove={onMouseMove}
        onMouseOut={() => setCursor(null)}
        onMoveStart={() => setMapMoving(true)}
        onMoveEnd={() => setMapMoving(false)}
        onLoad={() => {
          const map = mapRef.current?.getMap()
          // 규제 구역 빗금: 스타일이 바뀌어도(배경 전환) 없으면 다시 넣는다
          const addHatch = () => {
            if (map && !map.hasImage(HATCH_ID)) map.addImage(HATCH_ID, hatchImage(colors.regulation))
          }
          addHatch()
          map?.on('styleimagemissing', (e: { id: string }) => e.id === HATCH_ID && addHatch())
          // 점검 스크립트(tests/ui_check_map.py)가 페인트·렌더된 도형을 확인할 수 있게: 개발 서버 또는 ?debug=1일 때만
          if (exposeMap()) (window as unknown as { __propediaMap?: unknown }).__propediaMap = map
          setLoaded(true)
        }}
        style={{ position: 'absolute', inset: 0 }}
      >
        {areaLabels.map((l) => (
          <Marker key={l.id} longitude={l.at[0]} latitude={l.at[1]} anchor="center">
            <span className={`map-area-label map-area-label--${l.kind}`} data-testid="area-label" data-kind={l.kind}>
              {l.text}
            </span>
          </Marker>
        ))}
        {labels.map((l) => (
          <Marker key={l.id} longitude={l.at[0]} latitude={l.at[1]} anchor="center">
            <span className="map-dong-label" data-testid="dong-label">
              {l.name}
            </span>
          </Marker>
        ))}
      </Map>

      <MapControls insets={insets} hasKey={Boolean(KEY)} />

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
        className="glass pointer-events-none absolute px-3 py-1 text-xs"
        style={{ right: insets.right, bottom: insets.bottom, borderRadius: 999 }}
      >
        {ATTRIBUTION}
      </div>

      {loadError && (
        <div role="alert" className="glass absolute px-4 py-2 text-sm" style={{ left: insets.left, top: insets.top }}>
          {loadError}
        </div>
      )}
    </div>
  )
}
