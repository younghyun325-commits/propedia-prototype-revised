/**
 * 하단 타임라인 (docs/map/PLAN.md P19). 따로 불러오는 청크 (App.tsx lazy) — d3-scale은 여기와 실거래 차트에서만.
 * - 접힘 44px: 기준일 · 이전·다음 이벤트(◀ ▶) · 펼치기 (T)
 * - 펼침 200px: 계열별 줄(고시 발행·공람·효력·사업 단계·자료 기준일) + 아파트 단지를 고르면 '거래량' 줄
 *   휠 확대·끌어서 이동·전체 보기, 오늘 선(실선)·기준일 스크러버(브랜드 색, 끌어서 이동), 이벤트 호버·클릭, 재생(1·2·4배)
 * - 키보드(타임라인 포커스): ←/→ 하루 · Shift+←/→ 한 달 · Home 오늘. 기준일 변경은 aria-live로 알린다
 * 값(이벤트·날짜)은 /api/v1/timeline 그대로. 화면은 위치만 계산한다 (timeline/scale.ts).
 */
import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Maximize2, Pause, Play } from 'lucide-react'
import { useTimeline, type LaneId, type TlBar, type TlPoint } from '../api/map'
import { useApartmentMonthly } from '../api/market'
import { UI } from '../copy/ui'
import { focusSel } from '../state/actions'
import { todayIso } from '../state/dates'
import { featureId } from '../state/url'
import { useMapStore } from '../state/useMapStore'
import {
  DEFAULT_DOMAIN, PLAY_SPEEDS, dateAtX, eventDates, fullDomain, keyStep, makeX, monthSpan, nextEvent, panDomain, playInterval,
  playStep, prevEvent, spanDays, stackRows, ticks, xOf, zoomDomain, type Domain, type PlaySpeed,
} from './scale'

const LANES: LaneId[] = ['publish', 'review', 'effective', 'stage', 'data_as_of']
const LABEL_W = 76
const PAD_R = 12
const AXIS_H = 18
const ROW_DY = 6
const COLORS: Record<LaneId | 'trades', string> = {
  publish: 'var(--color-brand-indigo)',
  review: 'var(--color-brand-sky)',
  effective: 'var(--color-layer-regulation)',
  stage: 'var(--color-brand-plum)',
  data_as_of: 'var(--color-ink-muted)',
  trades: 'var(--color-layer-apartment)',
}

const dot = (iso: string) => iso.replaceAll('-', '.')

function useReducedMotion(): boolean {
  const [v, setV] = useState(() => {
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches
    } catch {
      return false
    }
  })
  useEffect(() => {
    let mq: MediaQueryList
    try {
      mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    } catch {
      return
    }
    const on = () => setV(mq.matches)
    mq.addEventListener?.('change', on)
    return () => mq.removeEventListener?.('change', on)
  }, [])
  return v
}

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(() => setW(el.clientWidth))
    ro.observe(el)
    setW(el.clientWidth)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

type Tip = { x: number; y: number; title: string; lines: string[] }
type Item = { lane: LaneId | 'trades'; id: string; x1: number; x2: number; kind: 'point' | 'bar'; date: string; end: string | null;
  title: string; sel: string | null; tip: string[]; small?: boolean; value?: number }

/** 이벤트 → 화면 칸 (점은 반지름만큼, 끝 없는 막대는 오른쪽 끝까지) */
function toItems(lane: LaneId, list: (TlPoint | TlBar)[], x: (iso: string) => number, right: number): Item[] {
  return list.map((e) => {
    const src = e.source
    const ev = src ? UI.time.tipEvidence(src.doc_id, src.pdf_page) : null
    if ('date' in e) {
      const cx = x(e.date)
      const small = lane === 'data_as_of'
      const r = small ? 3 : 4.5
      return { lane, id: e.id, x1: cx - r, x2: cx + r, kind: 'point', date: e.date, end: null, title: e.title, sel: e.sel ?? null,
        small, tip: [dot(e.date), e.kind_label ?? e.as_of_label ?? null, ev].filter((v): v is string => !!v) }
    }
    const x1 = x(e.start)
    const x2 = e.end ? x(e.end) : right
    return { lane, id: e.id, x1, x2: Math.max(x2, x1 + 3), kind: 'bar', date: e.start, end: e.end, title: e.title,
      sel: e.sel ?? null, tip: [UI.time.tipPeriod(dot(e.start), e.end ? dot(e.end) : null), ev].filter((v): v is string => !!v) }
  })
}

function Chart({ domain, setDomain, cur, today, setTip }: {
  domain: Domain; setDomain: (d: Domain) => void; cur: string; today: string; setTip: (t: Tip | null) => void
}) {
  const [wrapRef, width] = useWidth<HTMLDivElement>()
  const svgRef = useRef<SVGSVGElement>(null)
  const { data } = useTimeline()
  const setAsOf = useMapStore((s) => s.setAsOf)
  const selected = useMapStore((s) => s.selected)
  const aptId = selected?.kind === 'apt' ? featureId(selected) : null
  const monthly = useApartmentMonthly(aptId).data
  const aptName = useMapStore((s) => (s.selected?.kind === 'apt' ? s.selected.id : null))
  const [draft, setDraft] = useState<string | null>(null)
  const height = 148
  const lanes: (LaneId | 'trades')[] = aptId ? [...LANES, 'trades'] : LANES
  const laneH = (height - AXIS_H) / lanes.length
  const right = Math.max(LABEL_W + 40, width - PAD_R)
  const x = useMemo(() => makeX(domain, LABEL_W, right), [domain, right])
  const xi = (iso: string) => xOf(x, iso)

  const items = useMemo(() => {
    if (!data) return [] as Item[]
    const out: Item[] = []
    for (const lane of LANES) out.push(...toItems(lane, data.lanes[lane] as (TlPoint | TlBar)[], (d) => xOf(x, d), right))
    return out
  }, [data, x, right])
  const rows = useMemo(() => {
    const r: Record<string, number> = {}
    for (const lane of LANES) Object.assign(r, stackRows(items.filter((i) => i.lane === lane), 2))
    return r
  }, [items])
  const maxRows = Math.max(1, Math.floor((laneH - 8) / ROW_DY))
  const trades = useMemo(() => {
    if (!monthly) return []
    const counts = monthly.monthly.filter((m) => m.count > 0)
    const max = Math.max(1, ...counts.map((m) => m.count))
    return counts.map((m) => {
      const [s, e] = monthSpan(m.ym)
      return { ym: m.ym, x1: xOf(x, s), x2: xOf(x, e), h: (m.count / max) * (laneH - 6), count: m.count, date: s }
    })
  }, [monthly, x, laneH])

  // 휠 확대·축소 (가리킨 날짜 고정). passive가 아니어야 페이지 스크롤을 막을 수 있다
  const domainRef = useRef(domain)
  domainRef.current = domain
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const px = Math.max(LABEL_W, Math.min(right, e.clientX - r.left))
      const anchor = dateAtX(makeX(domainRef.current, LABEL_W, right), px)
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        setDomain(panDomain(domainRef.current, (e.deltaX / (right - LABEL_W)) * spanDays(domainRef.current)))
      } else setDomain(zoomDomain(domainRef.current, anchor, e.deltaY > 0 ? 1.2 : 1 / 1.2))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [right, setDomain])

  // 끌기: 배경 = 시간축 이동(누르기만 하면 그 날짜로), 스크러버 = 기준일 (놓을 때 반영)
  const drag = useRef<{ mode: 'pan' | 'scrub'; x0: number; d0: Domain; moved: boolean } | null>(null)
  const localX = (e: RPointerEvent) => e.clientX - (svgRef.current?.getBoundingClientRect().left ?? 0)
  const onDown = (mode: 'pan' | 'scrub') => (e: RPointerEvent<SVGElement>) => {
    if (e.button !== 0) return
    e.stopPropagation()
    ;(e.currentTarget as Element).setPointerCapture?.(e.pointerId)
    drag.current = { mode, x0: e.clientX, d0: domain, moved: false }
    if (mode === 'scrub') setDraft(dateAtX(x, localX(e)))
  }
  const onMove = (e: RPointerEvent<SVGElement>) => {
    const d = drag.current
    if (!d) return
    if (Math.abs(e.clientX - d.x0) > 3) d.moved = true
    if (d.mode === 'scrub') setDraft(dateAtX(x, Math.max(LABEL_W, Math.min(right, localX(e)))))
    else if (d.moved) setDomain(panDomain(d.d0, (-(e.clientX - d.x0) / (right - LABEL_W)) * spanDays(d.d0)))
  }
  const onUp = (e: RPointerEvent<SVGElement>) => {
    const d = drag.current
    drag.current = null
    if (!d) return
    if (d.mode === 'scrub') {
      const v = draft ?? dateAtX(x, localX(e))
      setDraft(null)
      setAsOf(v)
    } else if (!d.moved && localX(e) >= LABEL_W) setAsOf(dateAtX(x, localX(e)))
  }

  const showTip = (e: React.MouseEvent, title: string, lines: string[]) => {
    const r = wrapRef.current?.getBoundingClientRect()
    if (!r) return
    setTip({ x: e.clientX - r.left, y: e.clientY - r.top, title, lines })
  }
  const clickItem = (it: Item) => {
    setTip(null)
    if (it.sel) focusSel(it.sel, it.date)
    else setAsOf(it.date)
  }

  const scrubDate = draft ?? cur
  const sx = xi(scrubDate)
  const tx = xi(today)
  const inView = (px: number) => px >= LABEL_W - 1 && px <= right + 1
  return (
    <div ref={wrapRef} className="relative" style={{ height }}>
      {width > 0 && (
        <svg
          ref={svgRef}
          width={width}
          height={height}
          className="tl-svg block"
          data-testid="tl-svg"
          data-domain={domain.join('~')}
          onPointerDown={onDown('pan')}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={() => {
            drag.current = null
            setDraft(null)
          }}
          role="group"
          aria-label={UI.time.axisLabel}
        >
          <defs>
            <clipPath id="tl-clip">
              <rect x={LABEL_W} y={0} width={Math.max(0, right - LABEL_W)} height={height} />
            </clipPath>
          </defs>
          {/* 눈금 */}
          <g aria-hidden="true" className="text-ink-muted">
            {ticks(x, right - LABEL_W).map((t) => (
              <g key={t.iso} transform={`translate(${xi(t.iso)},0)`}>
                <line y1={AXIS_H - 4} y2={height} stroke="currentColor" strokeOpacity={t.major ? 0.25 : 0.1} />
                <text y={11} x={2} fontSize={10} fill="currentColor" fontWeight={t.major ? 600 : 400}>{t.label}</text>
              </g>
            ))}
          </g>
          {/* 줄 이름·구분선 */}
          {lanes.map((lane, i) => (
            <g key={lane} aria-hidden="true">
              <line x1={0} x2={right} y1={AXIS_H + i * laneH} y2={AXIS_H + i * laneH} stroke="var(--color-ink)" strokeOpacity={0.06} />
              <text x={4} y={AXIS_H + i * laneH + laneH / 2 + 3.5} fontSize={10.5} fill="var(--color-ink-muted)" data-testid={`tl-lane-${lane}`}>
                {lane === 'trades' ? UI.time.lanes.trades : UI.time.lanes[lane]}
              </text>
            </g>
          ))}
          <g clipPath="url(#tl-clip)">
            {/* 거래량 (선택한 단지, 해제 제외 월별 건수) */}
            {aptId && (
              <g data-testid="tl-trades" data-apt={aptName ?? ''}>
                {trades.map((t) => {
                  const base = AXIS_H + lanes.indexOf('trades') * laneH + laneH - 2
                  return (
                    <rect key={t.ym} x={t.x1} y={base - t.h} width={Math.max(1, t.x2 - t.x1 - 0.5)} height={t.h}
                      fill={COLORS.trades} fillOpacity={0.7} data-testid="tl-trade-bar"
                      onMouseMove={(e) => showTip(e, UI.time.lanes.trades, [UI.time.tradesTip(t.ym, t.count)])}
                      onMouseLeave={() => setTip(null)} />
                  )
                })}
              </g>
            )}
            {items.map((it) => {
              const li = lanes.indexOf(it.lane)
              const row = Math.min(rows[it.id] ?? 0, maxRows - 1)
              const cy = AXIS_H + li * laneH + 6 + row * ROW_DY + (maxRows === 1 ? laneH / 2 - 6 : 0)
              const common = {
                className: 'tl-event',
                'data-testid': 'tl-event',
                'data-lane': it.lane,
                'data-id': it.id,
                'data-date': it.date,
                'data-sel': it.sel ?? '',
                onPointerDown: (e: RPointerEvent) => e.stopPropagation(),
                onClick: () => clickItem(it),
                onMouseMove: (e: React.MouseEvent) => showTip(e, it.title, it.tip),
                onMouseLeave: () => setTip(null),
              }
              return it.kind === 'point' ? (
                <circle key={it.id} {...common} cx={(it.x1 + it.x2) / 2} cy={cy} r={it.small ? 3 : 4.5} fill={COLORS[it.lane]}
                  fillOpacity={it.small ? 0.7 : 1} stroke="white" strokeWidth={1} />
              ) : (
                <rect key={it.id} {...common} x={it.x1} y={cy - 2.5} width={it.x2 - it.x1} height={5} rx={2.5} fill={COLORS[it.lane]}
                  fillOpacity={0.85} />
              )
            })}
            {/* 오늘 선 (실선) */}
            {inView(tx) && (
              <g data-testid="tl-today" data-date={today} aria-hidden="true">
                <line x1={tx} x2={tx} y1={AXIS_H - 2} y2={height} stroke="var(--color-ink)" strokeWidth={1.25} />
                <text x={tx + 3} y={AXIS_H + 8} fontSize={9.5} fill="var(--color-ink)">{UI.time.today}</text>
              </g>
            )}
          </g>
          {/* 기준일 스크러버 (브랜드 색, 끌어서 이동) */}
          {inView(sx) && (
            <g className="tl-scrubber" data-testid="tl-scrubber" data-date={scrubDate} onPointerDown={onDown('scrub')}
              aria-label={`${UI.time.scrubber} ${scrubDate}`}>
              <line x1={sx} x2={sx} y1={0} y2={height} stroke="var(--color-brand-indigo)" strokeWidth={2} />
              <rect x={sx - 6} y={0} width={12} height={AXIS_H - 2} rx={3} fill="var(--color-brand-indigo)" />
              <rect x={sx - 6} y={0} width={12} height={height} fill="transparent" />
            </g>
          )}
        </svg>
      )}
    </div>
  )
}

export default function Timeline() {
  const open = useMapStore((s) => s.timelineOpen)
  const toggle = useMapStore((s) => s.toggleTimeline)
  const asOf = useMapStore((s) => s.asOf)
  const setAsOf = useMapStore((s) => s.setAsOf)
  const today = todayIso()
  const cur = asOf ?? today
  const q = useTimeline()
  const dates = useMemo(() => eventDates(q.data), [q.data])
  const [domain, setDomain] = useState<Domain>(() => {
    const c = useMapStore.getState().asOf
    return c && (c < DEFAULT_DOMAIN[0] || c > DEFAULT_DOMAIN[1]) ? fullDomain([c, ...DEFAULT_DOMAIN], todayIso()) : DEFAULT_DOMAIN
  })
  const [tip, setTip] = useState<Tip | null>(null)
  const reduced = useReducedMotion()
  const [playingRaw, setPlaying] = useState(false)
  // 접으면 재생도 멈춘다
  const playing = playingRaw && open
  const [speed, setSpeed] = useState<PlaySpeed>(1)
  const prev = prevEvent(dates, cur)
  const next = nextEvent(dates, cur)

  // 기준일이 보이는 범위 밖으로 나가면 범위를 그쪽으로 옮긴다 (키보드·이벤트 버튼·재생)
  useEffect(() => {
    if (cur >= domain[0] && cur <= domain[1]) return
    const half = Math.round(spanDays(domain) / 2)
    const days = Math.round((Date.parse(cur) - Date.parse(domain[0])) / 86_400_000) - half
    setDomain(panDomain(domain, days))
  }, [cur, domain])

  // 재생: 한 주씩 앞으로 (보이는 범위 끝에서 멈춤). 움직임 줄이기 설정이면 재생하지 않는다
  useEffect(() => {
    if (!playing || reduced) return
    const t = window.setInterval(() => {
      const c = useMapStore.getState().asOf ?? todayIso()
      const n = playStep(c, domain[1])
      if (!n) setPlaying(false)
      else useMapStore.getState().setAsOf(n)
    }, playInterval(speed))
    return () => window.clearInterval(t)
  }, [playing, speed, reduced, domain])

  const onKey = (e: React.KeyboardEvent) => {
    const n = keyStep(e.key, e.shiftKey, cur, today)
    if (!n) return
    e.preventDefault()
    setAsOf(n)
  }
  const btn = 'inline-flex h-7 items-center gap-1 rounded-lg px-1.5 text-meta hover:bg-white/80 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-brand-indigo'
  return (
    <div className="flex h-full flex-col" data-testid="tl-root" data-as-of={cur}>
      <div className="flex h-[44px] shrink-0 items-center gap-2">
        <button type="button" onClick={toggle} aria-expanded={open} data-testid="tl-toggle" title={open ? UI.time.collapse : UI.time.expand}
          className="flex items-center gap-1.5 font-semibold">
          {open ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronUp size={16} aria-hidden="true" />}
          {UI.time.title}
        </button>
        <span className="text-meta tabular-nums" data-testid="tl-current">
          <span className="text-ink-muted">{UI.time.asOf}</span>{' '}
          <span className={asOf ? 'font-semibold text-brand-indigo' : ''}>{cur}</span>
          {!asOf && <span className="text-ink-muted"> ({UI.time.today})</span>}
        </span>
        <button type="button" className={btn} disabled={!prev} onClick={() => prev && setAsOf(prev)} aria-label={UI.time.prevEvent}
          title={prev ? `${UI.time.prevEvent} (${prev})` : UI.time.prevEvent} data-testid="tl-prev">
          <ChevronLeft size={14} aria-hidden="true" />
        </button>
        <button type="button" className={btn} disabled={!next} onClick={() => next && setAsOf(next)} aria-label={UI.time.nextEvent}
          title={next ? `${UI.time.nextEvent} (${next})` : UI.time.nextEvent} data-testid="tl-next">
          <ChevronRight size={14} aria-hidden="true" />
        </button>
        {open && (
          <>
            {!reduced && (
              <>
                <button type="button" className={btn} onClick={() => setPlaying((v) => !v)} aria-pressed={playing} data-testid="tl-play">
                  {playing ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
                  {playing ? UI.time.pause : UI.time.play}
                </button>
                <span role="group" aria-label={UI.time.speedLabel} className="flex gap-0.5">
                  {PLAY_SPEEDS.map((v) => (
                    <button key={v} type="button" className={`${btn} ${speed === v ? 'bg-white/90 font-semibold' : ''}`}
                      aria-pressed={speed === v} onClick={() => setSpeed(v)} data-testid={`tl-speed-${v}`}>
                      {UI.time.speed(v)}
                    </button>
                  ))}
                </span>
              </>
            )}
            <button type="button" className={btn} onClick={() => setDomain(fullDomain(dates, today))} data-testid="tl-fit">
              <Maximize2 size={13} aria-hidden="true" />
              {UI.time.fitAll}
            </button>
            <button type="button" className={btn} onClick={() => setDomain(DEFAULT_DOMAIN)} data-testid="tl-default">
              {UI.time.fitDefault}
            </button>
          </>
        )}
        <span className="ml-auto truncate text-caption text-ink-muted">
          {open ? UI.time.keysHelp : UI.time.expand}
          {q.isError ? ` · ${UI.time.error}` : ''}
        </span>
      </div>
      {open && (
        <div tabIndex={0} onKeyDown={onKey} className="tl-svg relative min-h-0 flex-1 rounded-xl" data-testid="tl-focus"
          aria-label={`${UI.time.axisLabel} · ${UI.time.keysHelp}`} aria-describedby="tl-live">
          {q.data ? (
            <Chart domain={domain} setDomain={setDomain} cur={cur} today={today} setTip={setTip} />
          ) : (
            <p role="status" className="pt-4 text-meta text-ink-muted">{q.isError ? UI.time.error : UI.time.loading}</p>
          )}
          {tip && (
            <div className="pointer-events-none absolute z-10 max-w-[260px] rounded-lg bg-white/95 px-2 py-1 text-caption shadow"
              style={{ left: tip.x > 600 ? undefined : tip.x + 12, right: tip.x > 600 ? `calc(100% - ${tip.x - 12}px)` : undefined,
                top: tip.y < 64 ? tip.y + 14 : tip.y - 58 }} data-testid="tl-tip" role="tooltip">
              <p className="font-semibold">{tip.title}</p>
              {tip.lines.map((l) => <p key={l} className="text-ink-muted">{l}</p>)}
            </div>
          )}
        </div>
      )}
      <p id="tl-live" className="sr-only" aria-live="polite" data-testid="tl-live">{UI.time.announce(cur)}</p>
    </div>
  )
}
