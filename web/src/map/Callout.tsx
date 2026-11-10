/**
 * 지도 콜아웃 (P16, 참고 이미지 6번): 선택한 사업·규제 옆 미니 카드(이름·단계·기한)를 선으로 잇는다.
 * 지도를 움직이면 따라가고(move 이벤트), 기준점이 화면(패널을 뺀 영역) 밖이면 숨긴다. 우측 패널과 겹치면 왼쪽에 둔다.
 * 내용은 인스펙터와 같은 /api/v1/map/feature 응답(TanStack Query 캐시 공유)에서 고르기만 한다.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Map as MlMap } from 'maplibre-gl'
import { useFeature } from '../api/feature'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { GlassPanel } from '../ui/GlassPanel'
import { bboxCenter, placeCallout, type CalloutPlacement } from './calloutPlace'
import type { Insets } from './insets'

export function Callout({ getMap, loaded, insets }: { getMap: () => MlMap | undefined; loaded: boolean; insets: Insets }) {
  const selected = useMapStore((s) => s.selected)
  const kind = selected && (selected.kind === 'project' || selected.kind === 'regulation') ? selected.kind : null
  const q = useFeature(kind, kind ? selected!.id : null)
  const f = kind ? q.data : undefined
  const cardRef = useRef<HTMLDivElement>(null)
  const [place, setPlace] = useState<CalloutPlacement>({ visible: false })
  const bbox = f?.bbox ?? null

  const relayout = useRef<() => void>(() => {})
  relayout.current = () => {
    const map = getMap()
    if (!map || !bbox) return setPlace({ visible: false })
    const p = map.project(bboxCenter(bbox))
    const c = map.getContainer()
    const card = cardRef.current?.getBoundingClientRect()
    setPlace(placeCallout({ x: p.x, y: p.y }, { w: card?.width ?? 220, h: card?.height ?? 64 },
      { width: c.clientWidth, height: c.clientHeight }, insets))
  }
  useEffect(() => {
    const map = getMap()
    if (!loaded || !map) return
    const on = () => relayout.current()
    map.on('move', on)
    map.on('resize', on)
    return () => {
      map.off('move', on)
      map.off('resize', on)
    }
    // getMap은 MapView가 렌더마다 새로 만드는 함수라 의존성에 넣지 않는다 (지도 객체는 load 뒤 바뀌지 않음)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded])
  useLayoutEffect(() => relayout.current(), [bbox, insets, f])

  if (!f || !bbox) return null
  let line2: string | null = null
  let line3: string | null = null
  if (f.kind === 'project') {
    line2 = f.sections.stepper.position_label
    const d = f.sections.progress.deadlines[0]
    line3 = d ? `${d.title} · ${d.d_day_label}` : null
  } else if (f.kind === 'regulation') {
    const r = f.sections.regulation
    line2 = r.effective_label
    line3 = r.effective_status_label
  }
  const hidden = !place.visible
  return (
    <div className="pointer-events-none absolute inset-0 z-[5]" aria-hidden={hidden} data-testid="callout-layer">
      {place.visible && (
        <svg className="absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
          <line x1={place.line[0].x} y1={place.line[0].y} x2={place.line[1].x} y2={place.line[1].y}
            className="stroke-brand-indigo" strokeWidth={1.5} />
          <circle cx={place.line[0].x} cy={place.line[0].y} r={3.5} className="fill-brand-indigo" />
        </svg>
      )}
      <div
        ref={cardRef}
        className="absolute"
        style={{ left: place.visible ? place.left : -9999, top: place.visible ? place.top : -9999, visibility: hidden ? 'hidden' : 'visible' }}
        data-testid="callout"
        data-side={place.visible ? place.side : ''}
        role="note"
        aria-label={UI.callout.label}
      >
        <GlassPanel liquid className="max-w-[240px] px-3 py-2 text-xs leading-snug" style={{ borderRadius: 12 }}>
          <p className="font-semibold">{f.title}</p>
          {line2 && <p className="text-ink-muted">{line2}</p>}
          {line3 && <p className="tabular-nums">{line3}</p>}
        </GlassPanel>
      </div>
    </div>
  )
}
