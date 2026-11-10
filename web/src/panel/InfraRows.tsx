/**
 * 레이어 탭의 생활 인프라 부분 (P18, P19-1): 칩 모양 색 칩, 편의시설 분류 6행(켜기·끄기·건수)과
 * 병원·의원·학원의 하위 분류 행. 체크박스는 3단(켜짐·일부·꺼짐) — 실제 input + indeterminate + aria-checked="mixed".
 * '이것만 보기': 행에 마우스를 올리거나 포커스하면 나오는 버튼, 또는 Alt+클릭. 건수·안내는 manifest(pipeline/fetch_pois.py) 값 그대로.
 */
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { ChevronDown, ChevronRight, Info } from 'lucide-react'
import { UI } from '../copy/ui'
import type { InfraLayer, PoiCategory } from '../infra/data'
import { ICON_OF, INK } from '../infra/icons'
import { clickCat, clickSub, poiNode, solo, triCat, type PoiSel, type Tri } from '../infra/poiSelect'
import { useMapStore } from '../state/useMapStore'
import { Tooltip } from '../ui/Floating'

const ICON_FOR_LAYER: Record<string, string> = { schools: 'school', stations: 'station', bus_stops: 'bus' }

/** 흰 원형 칩 + 아이콘 (지도와 같은 모양) */
export function ChipSwatch({ icon, small = false }: { icon: string; small?: boolean }) {
  const Icon = ICON_OF[icon]
  const s = small ? 16 : 20
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-white"
      style={{ width: s, height: s, border: `1.5px solid ${INK}` }}
    >
      {Icon && <Icon size={Math.round(s * 0.6)} color={INK} strokeWidth={2} />}
    </span>
  )
}

export const infraSwatchIcon = (id: string) => ICON_FOR_LAYER[id] ?? (id === 'pois' ? 'convenience' : null)

/** 3단 체크박스 (실제 input). 클릭은 onToggle(altKey)로만 받는다 — Alt+클릭은 '이것만 보기' */
export function TriCheckbox({
  id, tri, onToggle, testId, label, disabled = false, className = 'h-3.5 w-3.5',
}: {
  id?: string
  tri: Tri
  onToggle: (alt: boolean) => void
  testId?: string
  label?: string
  disabled?: boolean
  className?: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = tri === 'mixed'
  }, [tri])
  return (
    <input
      ref={ref}
      id={id}
      type="checkbox"
      checked={tri === 'on'}
      aria-checked={tri === 'mixed' ? 'mixed' : tri === 'on'}
      aria-label={label}
      disabled={disabled}
      data-testid={testId}
      data-state={tri}
      // 클릭에서 preventDefault를 하면 브라우저가 렌더 뒤 checked를 되돌린다 → onChange에서 받고 Alt는 원래 클릭 이벤트에서 읽는다
      onChange={(e: ChangeEvent<HTMLInputElement>) => onToggle(!!(e.nativeEvent as globalThis.MouseEvent).altKey)}
      onKeyDown={(e) => {
        // Space는 브라우저가 click으로 바꿔 준다. Enter도 같은 동작으로 받는다
        if (e.key === 'Enter') {
          e.preventDefault()
          onToggle(e.altKey)
        }
      }}
      className={`${className} shrink-0 accent-brand-indigo`}
    />
  )
}

function OnlyButton({ name, onClick, testId }: { name: string; onClick: () => void; testId: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={UI.infra.onlyLabel(name)}
      title={UI.infra.onlyHelp}
      data-testid={testId}
      className="rounded px-1 text-[11px] text-ink-muted opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 hover:text-ink focus:opacity-100"
    >
      {UI.infra.only}
    </button>
  )
}

/** 하위 분류 라벨 → slug (manifest sub_keys, 없으면 POI_TREE) */
function subSlug(c: PoiCategory, label: string): string | undefined {
  return c.sub_keys?.[label] ?? poiNode(c.key)?.subs.find((s) => s.label === label)?.slug
}

/** 분류 행 건수: 하위 분류가 일부만 켜졌으면 켜진 하위 분류의 합, 아니면 분류 전체 (manifest 값) */
export function categoryCount(c: PoiCategory, sel: PoiSel): number {
  const on = sel[c.key]
  if (!on || !c.sub_categories.length || triCat(sel, c.key) === 'on') return c.count
  return c.sub_categories.reduce((a, s) => a + (on.includes(subSlug(c, s) ?? '') ? (c.sub_counts[s] ?? 0) : 0), 0)
}

function CategoryRow({ c }: { c: PoiCategory }) {
  const sel = useMapStore((s) => s.poi)
  const setPoi = useMapStore((s) => s.setPoi)
  const [open, setOpen] = useState(false)
  const id = `poi-cat-${c.key}`
  const tri = triCat(sel, c.key)
  const subs = c.sub_categories
    .map((label) => ({ label, slug: subSlug(c, label) }))
    .filter((x): x is { label: string; slug: string } => !!x.slug)
  return (
    <li data-testid={`poi-cat-row-${c.key}`} data-state={tri} className="py-0.5">
      <div className="group flex items-center gap-1.5">
        <TriCheckbox id={id} tri={tri} testId={`poi-cat-toggle-${c.key}`}
          onToggle={(alt) => setPoi(alt ? solo(c.key) : clickCat(sel, c.key))} />
        <label htmlFor={id} className="flex min-w-0 flex-1 items-center gap-1.5">
          <ChipSwatch icon={c.key} small />
          <span className="break-keep">{c.label}</span>
        </label>
        <OnlyButton name={c.label} testId={`poi-only-${c.key}`} onClick={() => setPoi(solo(c.key))} />
        <span className="tabular-nums" data-testid={`poi-cat-count-${c.key}`}>{UI.layers.count(categoryCount(c, sel))}</span>
        {c.note && (
          <Tooltip testId={`poi-cat-note-${c.key}`} content={<span>{c.note}</span>}>
            {(p) => (
              <button type="button" {...p} aria-label={`${c.label} ${UI.layers.info}`} className="rounded p-0.5 hover:text-ink">
                <Info size={12} aria-hidden="true" />
              </button>
            )}
          </Tooltip>
        )}
        {subs.length > 0 && (
          <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
            aria-controls={`${id}-subs`}
            aria-label={`${c.label} ${open ? UI.infra.collapseSubs : UI.infra.expandSubs}`}
            data-testid={`poi-cat-expand-${c.key}`} className="rounded p-0.5 hover:text-ink">
            {open ? <ChevronDown size={12} aria-hidden="true" /> : <ChevronRight size={12} aria-hidden="true" />}
          </button>
        )}
      </div>
      {open && subs.length > 0 && (
        <ul id={`${id}-subs`} className="mt-0.5 ml-6 space-y-0.5" aria-label={c.label}>
          {subs.map(({ label, slug }) => {
            const sid = `poi-sub-${c.key}-${slug}`
            const on = !!sel[c.key]?.includes(slug)
            return (
              <li key={slug} className="group flex items-center gap-1.5" data-testid="poi-sub-row" data-key={`${c.key}:${slug}`}
                data-state={on ? 'on' : 'off'}>
                <TriCheckbox id={sid} tri={on ? 'on' : 'off'} testId="poi-sub-toggle"
                  onToggle={(alt) => setPoi(alt ? solo(c.key, slug) : clickSub(sel, c.key, slug))} />
                <label htmlFor={sid} className="flex-1 break-keep">{label}</label>
                <OnlyButton name={label} testId="poi-sub-only" onClick={() => setPoi(solo(c.key, slug))} />
                <span className="tabular-nums">{UI.layers.count(c.sub_counts[label] ?? 0)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </li>
  )
}

/** 편의시설 분류 행 (상위 '편의시설' 행이 꺼져 있어도 분류부터 켤 수 있다) */
export function PoiCategoryRows({ l }: { l: InfraLayer }) {
  if (!l.categories?.length) return null
  return (
    <div className="mt-1 ml-6 text-xs text-ink-muted">
      <ul className="space-y-0.5" data-testid="poi-categories" aria-label={UI.infra.poiCats}>
        {l.categories.map((c) => <CategoryRow key={c.key} c={c} />)}
      </ul>
      <p className="mt-1">{UI.infra.poiNote}</p>
    </div>
  )
}

/** 줌 조건 안내 (정류장: 줌 15 이상) — P15 지적도 안내와 같은 방식 */
export function InfraZoomHint({ l }: { l: InfraLayer }) {
  const zoom = useMapStore((s) => s.zoom)
  const visible = useMapStore((s) => (l.id === 'bus_stops' ? s.layers.bus_stops.visible : false))
  if (!l.min_zoom || !visible || zoom === null || zoom >= l.min_zoom) return null
  return (
    <p className="mt-1 ml-6 text-xs text-ink-muted" data-testid={`layer-zoomhint-${l.id}`}>
      {UI.infra.zoomHint(l.min_zoom)}
    </p>
  )
}
