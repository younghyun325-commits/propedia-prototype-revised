import { create } from 'zustand'
import type { EvidenceItem } from '../api/feature'
import type { ParcelAt } from '../api/parcel'
import type { BasemapId } from '../map/basemaps'
import type { Radius } from '../infra/radius'
import { poiAll, poiAny, poiNone, type PoiSel } from '../infra/poiSelect'
import {
  defaultUrlState, isParcelLookup, parseUrl, type Camera, type LayerStates, type LeftTab, type PanelLayerId, type Selected,
} from './url'

export type Workspace = 'gangnam' | 'project'

/** 지도에 보내는 이동 요청 (nonce가 바뀔 때마다 한 번 실행) */
export type ViewTarget = { type: 'home' } | { type: 'bbox'; bbox: [number, number, number, number] }
export type ViewRequest = ViewTarget & { nonce: number }

/** 검색으로 찾은 곳: 필지 경계가 있으면 pnu로 강조, 없으면 임시 핀 (좌표는 화면 메모리에만, 저장하지 않음) */
export type SearchHit = { label: string; pnu: string | null; point: [number, number] | null; nonce: number } | null

/** 지도 클릭 필지 조회 (P15). 화면 메모리에만 (저장하지 않음). reqId가 다른 (이전) 응답은 버린다 */
export type ParcelLookup =
  | { status: 'idle'; reqId: number }
  | { status: 'loading'; reqId: number; point: [number, number] | null; pnu: string | null }
  | { status: 'done'; reqId: number; data: ParcelAt; fit: boolean }
  | { status: 'error'; reqId: number; message: string }

export type MapState = {
  leftOpen: boolean
  rightOpen: boolean
  timelineOpen: boolean
  workspace: Workspace
  /** '투명도 줄이기' — html.reduce-transparency */
  reduceTransparency: boolean
  /** 지도 이동 중 — html.map-moving (MapLibre movestart/moveend) */
  mapMoving: boolean
  /** 3D 기울기 */
  tilt3d: boolean
  // ---- URL과 동기화하는 상태 (state/url.ts)
  layers: LayerStates
  basemap: BasemapId
  overlap: boolean
  selected: Selected
  leftTab: LeftTab
  camera: Camera
  poi: PoiSel
  route: string | null
  radius: Radius | null
  // ---- 화면 안 상태
  /** 반경 보기 도구가 켜져 있음 (지도를 누르면 원을 그린다) */
  radiusTool: boolean
  hovered: string | null
  paletteOpen: boolean
  viewRequest: ViewRequest | null
  searchHit: SearchHit
  /** 현재 줌 (이동이 끝날 때) — 줌 조건이 있는 레이어 안내용 */
  zoom: number | null
  parcel: ParcelLookup
  /** 원문 보기 모달 (P16): 근거 목록과 지금 보는 칸. 열린 동안 지도 단축키는 쉰다 */
  evidence: { items: EvidenceItem[]; index: number } | null

  toggleLeft: () => void
  toggleRight: () => void
  toggleTimeline: () => void
  select: (s: Selected) => void
  clearSelection: () => void
  setWorkspace: (w: Workspace) => void
  toggleReduceTransparency: () => void
  setMapMoving: (v: boolean) => void
  setBasemap: (b: BasemapId) => void
  toggleTilt3d: () => void
  setLayerVisible: (id: PanelLayerId, v: boolean) => void
  setLayersVisible: (ids: PanelLayerId[], v: boolean) => void
  setLayerOpacity: (id: PanelLayerId, pct: number) => void
  setOverlap: (v: boolean) => void
  setLeftTab: (t: LeftTab) => void
  setCamera: (c: Camera) => void
  setHovered: (id: string | null) => void
  setPaletteOpen: (v: boolean) => void
  requestView: (r: ViewTarget) => void
  setSearchHit: (h: Omit<NonNullable<SearchHit>, 'nonce'> | null) => void
  setZoom: (z: number) => void
  setParcel: (p: ParcelLookup) => void
  openEvidence: (items: EvidenceItem[], index: number) => void
  setEvidenceIndex: (index: number) => void
  closeEvidence: () => void
  /** 편의시설 선택 (P19-1): layers.pois.visible도 함께 맞춘다 */
  setPoi: (sel: PoiSel) => void
  setRoute: (id: string | null) => void
  setRadius: (r: Radius | null) => void
  setRadiusTool: (v: boolean) => void
}

function initialUrlState() {
  try {
    return typeof window === 'undefined' ? defaultUrlState() : parseUrl(window.location.search)
  } catch {
    return defaultUrlState()
  }
}

let nonce = 0

function withPoi(layers: LayerStates, poi: PoiSel): { layers: LayerStates; poi: PoiSel } {
  return { poi, layers: { ...layers, pois: { ...layers.pois, visible: poiAny(poi) } } }
}

export const useMapStore = create<MapState>()((set) => {
  const u = initialUrlState()
  return {
    leftOpen: true,
    rightOpen: true,
    timelineOpen: false,
    workspace: u.selected?.kind === 'project' ? 'project' : 'gangnam',
    reduceTransparency: false,
    mapMoving: false,
    tilt3d: false,
    ...u,
    hovered: null,
    paletteOpen: false,
    viewRequest: null,
    searchHit: null,
    zoom: u.camera?.zoom ?? null,
    parcel: { status: 'idle', reqId: 0 },
    evidence: null,
    radiusTool: u.radius !== null,

    toggleLeft: () => set((s) => ({ leftOpen: !s.leftOpen })),
    toggleRight: () => set((s) => ({ rightOpen: !s.rightOpen })),
    toggleTimeline: () => set((s) => ({ timelineOpen: !s.timelineOpen })),
    // 고르면 인스펙터를 연다 (내용은 P16)
    // 필지 조회가 아닌 대상을 고르면 필지 조회 결과를 내린다
    select: (selected) =>
      set((s) => ({
        ...(selected ? { selected, rightOpen: true } : { selected: null }),
        ...(isParcelLookup(selected) ? {} : { parcel: { status: 'idle' as const, reqId: s.parcel.reqId + 1 } }),
      })),
    clearSelection: () => set((s) => ({ selected: null, parcel: { status: 'idle', reqId: s.parcel.reqId + 1 } })),
    setWorkspace: (workspace) => set({ workspace }),
    toggleReduceTransparency: () => set((s) => ({ reduceTransparency: !s.reduceTransparency })),
    setMapMoving: (mapMoving) => set(mapMoving ? { mapMoving, hovered: null } : { mapMoving }),
    setBasemap: (basemap) => set({ basemap }),
    toggleTilt3d: () => set((s) => ({ tilt3d: !s.tilt3d })),
    // 편의시설 행·그룹 켜기는 '6분류 모두 켜기·끄기'와 같다 (P19-1)
    setLayerVisible: (id, v) =>
      set((s) =>
        id === 'pois'
          ? withPoi(s.layers, v ? poiAll() : poiNone())
          : { layers: { ...s.layers, [id]: { ...s.layers[id], visible: v } } },
      ),
    setLayersVisible: (ids, v) =>
      set((s) => {
        const layers = { ...s.layers }
        for (const id of ids) if (id !== 'pois') layers[id] = { ...layers[id], visible: v }
        return ids.includes('pois') ? withPoi(layers, v ? poiAll() : poiNone()) : { layers }
      }),
    setLayerOpacity: (id, pct) =>
      set((s) => ({
        layers: { ...s.layers, [id]: { ...s.layers[id], opacity: Math.max(0, Math.min(100, Math.round(pct))) } },
      })),
    setOverlap: (overlap) => set({ overlap }),
    setLeftTab: (leftTab) => set({ leftTab }),
    setCamera: (camera) => set({ camera }),
    setHovered: (hovered) => set({ hovered }),
    setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
    requestView: (r) => set({ viewRequest: { ...r, nonce: ++nonce } }),
    setSearchHit: (h) => set({ searchHit: h ? { ...h, nonce: ++nonce } : null }),
    setZoom: (zoom) => set({ zoom }),
    setParcel: (parcel) => set({ parcel }),
    openEvidence: (items, index) =>
      set(items.length ? { evidence: { items, index: Math.max(0, Math.min(items.length - 1, index)) } } : {}),
    setEvidenceIndex: (index) =>
      set((s) => (s.evidence ? { evidence: { ...s.evidence, index: Math.max(0, Math.min(s.evidence.items.length - 1, index)) } } : {})),
    closeEvidence: () => set({ evidence: null }),
    setPoi: (sel) => set((s) => withPoi(s.layers, sel)),
    // 노선을 고르면 정류장 레이어를 켠다 (강조할 정류장이 보이게)
    setRoute: (route) =>
      set((s) => (route ? { route, layers: { ...s.layers, bus_stops: { ...s.layers.bus_stops, visible: true } } } : { route: null })),
    setRadius: (radius) => set({ radius }),
    setRadiusTool: (radiusTool) => set(radiusTool ? { radiusTool } : { radiusTool, radius: null }),
  }
})
