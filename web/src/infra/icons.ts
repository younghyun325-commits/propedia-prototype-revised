/**
 * 생활 인프라 칩 이미지 (P18): 흰 원형 칩 + lucide 아이콘, 잉크 한 가지 색 (docs/map/PLAN.md '지도 레이어 모양').
 * 색을 늘리지 않고 아이콘 모양으로 구분한다. 스타일에 글꼴이 없으므로 이름·개수는 HTML 마커로 그린다.
 * lucide-react 아이콘을 떨어진 DOM에 그려 SVG를 얻고, 캔버스에 칩과 함께 그려 map.addImage로 넣는다.
 */
import { createElement, type ComponentType } from 'react'
import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { BookOpen, Bus, Coffee, Hospital, Pill, School, ShoppingCart, Store, TrainFront } from 'lucide-react'

export const INK = '#1f2328'
type IconC = ComponentType<{ size?: number; color?: string; strokeWidth?: number }>

/** 칩 id → 아이콘 (편의시설 분류 key는 seed/poi_categories.yaml과 같다) */
export const ICON_OF: Record<string, IconC> = {
  school: School, station: TrainFront, bus: Bus,
  supermarket: ShoppingCart, convenience: Store, clinic: Hospital, pharmacy: Pill, cafe: Coffee, academy: BookOpen,
}

export type Chip = { id: string; icon: string; size: number; border: number }
/** 학교·역·편의시설 26px, 버스정류장은 작게 18px. 중앙차로 정류장은 테두리만 굵게, 노선 선택 정류장은 크게 + 굵은 테두리 */
export const CHIPS: Chip[] = [
  ...['school', 'station', 'supermarket', 'convenience', 'clinic', 'pharmacy', 'cafe', 'academy'].map((k) => ({
    id: `chip-${k}`, icon: k, size: 26, border: 1.5,
  })),
  { id: 'chip-bus', icon: 'bus', size: 18, border: 1.25 },
  { id: 'chip-bus-central', icon: 'bus', size: 18, border: 2.75 },
  { id: 'chip-bus-route', icon: 'bus', size: 26, border: 3 },
]
export const CHIP_IDS = new Set(CHIPS.map((c) => c.id))
const RATIO = 2

function svgOf(Icon: IconC, px: number): string {
  const host = document.createElement('div')
  const root = createRoot(host)
  flushSync(() => root.render(createElement(Icon, { size: px, color: INK, strokeWidth: 2 })))
  const svg = host.innerHTML
  root.unmount()
  return svg
}

function loadImage(svg: string): Promise<HTMLImageElement> {
  return new Promise((ok, fail) => {
    const img = new Image()
    img.onload = () => ok(img)
    img.onerror = () => fail(new Error('아이콘 그림을 만들지 못했습니다'))
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  })
}

/** 칩 하나 → ImageData (pixelRatio 2) */
export async function chipImage(c: Chip): Promise<ImageData> {
  const S = Math.round(c.size * RATIO)
  const canvas = document.createElement('canvas')
  canvas.width = S
  canvas.height = S
  const g = canvas.getContext('2d')!
  const b = c.border * RATIO
  g.beginPath()
  g.arc(S / 2, S / 2, S / 2 - b / 2 - 0.5, 0, Math.PI * 2)
  g.fillStyle = '#ffffff'
  g.fill()
  g.lineWidth = b
  g.strokeStyle = INK
  g.stroke()
  const iconPx = Math.round(S * 0.56)
  const img = await loadImage(svgOf(ICON_OF[c.icon], iconPx))
  g.drawImage(img, (S - iconPx) / 2, (S - iconPx) / 2, iconPx, iconPx)
  return g.getImageData(0, 0, S, S)
}

let cache: Promise<Map<string, ImageData>> | null = null
/** 모든 칩 (한 번만 만든다) */
export function chipImages(): Promise<Map<string, ImageData>> {
  cache ??= Promise.all(CHIPS.map(async (c) => [c.id, await chipImage(c)] as const)).then((xs) => new Map(xs))
  return cache
}

type MapLike = { hasImage(id: string): boolean; addImage(id: string, img: ImageData, o: { pixelRatio: number }): void }
/** 지도에 칩을 넣는다 (스타일이 바뀌어 빠진 것만) */
export function addChips(map: MapLike, imgs: Map<string, ImageData>, only?: string): void {
  for (const [id, img] of imgs) if ((!only || only === id) && !map.hasImage(id)) map.addImage(id, img, { pixelRatio: RATIO })
}
