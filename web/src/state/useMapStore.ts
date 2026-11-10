import { create } from 'zustand'
import type { BasemapId } from '../map/basemaps'
import {
  defaultUrlState, parseUrl, type Camera, type LayerStates, type LeftTab, type PanelLayerId, type Selected,
} from './url'

export type Workspace = 'gangnam' | 'project'

/** 지도에 보내는 이동 요청 (nonce가 바뀔 때마다 한 번 실행) */
export type ViewTarget = { type: 'home' } | { type: 'bbox'; bbox: [number, number, number, number] }
export type ViewRequest = ViewTarget & { nonce: number }

/** 검색으로 찾은 곳: 필지 경계가 있으면 pnu로 강조, 없으면 임시 핀 (좌표는 화면 메모리에만, 저장하지 않음) */
export type SearchHit = { label: string; pnu: string | null; point: [number, number] | null; nonce: number } | null

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
  // ---- 화면 안 상태
  hovered: string | null
  paletteOpen: boolean
  viewRequest: ViewRequest | null
  searchHit: SearchHit

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
}

function initialUrlState() {
  try {
    return typeof window === 'undefined' ? defaultUrlState() : parseUrl(window.location.search)
  } catch {
    return defaultUrlState()
  }
}

let nonce = 0

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

    toggleLeft: () => set((s) => ({ leftOpen: !s.leftOpen })),
    toggleRight: () => set((s) => ({ rightOpen: !s.rightOpen })),
    toggleTimeline: () => set((s) => ({ timelineOpen: !s.timelineOpen })),
    // 고르면 인스펙터를 연다 (내용은 P16)
    select: (selected) => set(selected ? { selected, rightOpen: true } : { selected: null }),
    clearSelection: () => set({ selected: null }),
    setWorkspace: (workspace) => set({ workspace }),
    toggleReduceTransparency: () => set((s) => ({ reduceTransparency: !s.reduceTransparency })),
    setMapMoving: (mapMoving) => set(mapMoving ? { mapMoving, hovered: null } : { mapMoving }),
    setBasemap: (basemap) => set({ basemap }),
    toggleTilt3d: () => set((s) => ({ tilt3d: !s.tilt3d })),
    setLayerVisible: (id, v) => set((s) => ({ layers: { ...s.layers, [id]: { ...s.layers[id], visible: v } } })),
    setLayersVisible: (ids, v) =>
      set((s) => {
        const layers = { ...s.layers }
        for (const id of ids) layers[id] = { ...layers[id], visible: v }
        return { layers }
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
  }
})
