/**
 * 사업 진행 단계 스테퍼 (P16). 템플릿 전체 단계를 가로 칸으로: 지난 단계 = 채움, 현재 = 브랜드 색 강조, 남은 단계 = 빈 칸.
 * 아래 한 줄 '재건축 13단계 중 2번째 · 앞으로 11단계 · 다음: 정비구역 지정 고시'.
 * 남은 단계 수는 API 값(템플릿 단계 수 − 현재 단계 번호)을 그대로 쓴다. 기간 예측은 하지 않는다.
 * 단계 툴팁: 템플릿의 단계 설명(사람이 쓴 문구, 없으면 안내)과 템플릿 상태('법령 대조 전 초안').
 */
import { UI } from '../copy/ui'
import { Tooltip } from './Floating'

export type StepState = 'done' | 'current' | 'upcoming'
export type StepInput = {
  seq: number
  title?: string
  status?: StepState
  what_happens?: string | null
  what_happens_note?: string | null
  template_status?: string
  note?: string | null
}

/** 칸마다 상태. status가 있으면 그대로(API), 없으면 현재 번호로 나눈다 (사업 목록 카드: 번호만 있음) */
export function stepCells(steps: StepInput[], currentSeq: number): { seq: number; state: StepState }[] {
  return steps.map((s) => ({
    seq: s.seq,
    state: s.status ?? (s.seq < currentSeq ? 'done' : s.seq === currentSeq ? 'current' : 'upcoming'),
  }))
}

const CELL: Record<StepState, string> = {
  done: 'bg-brand-indigo/45',
  current: 'bg-brand-indigo ring-2 ring-brand-indigo/30',
  upcoming: 'bg-white/70 ring-1 ring-inset ring-ink/20',
}

/** 사업 목록 카드용 작은 막대 (툴팁 없음) */
export function MiniStepper({ seq, total }: { seq: number; total: number }) {
  const cells = stepCells(Array.from({ length: total }, (_, i) => ({ seq: i + 1 })), seq)
  return (
    <div className="flex items-center gap-0.5" role="img" aria-label={UI.projects.stage(seq, total)} data-testid="mini-stepper">
      {cells.map((c) => (
        <span key={c.seq} data-state={c.state} className={`h-1.5 flex-1 rounded-full ${CELL[c.state]}`} />
      ))}
    </div>
  )
}

export function Stepper({ stages, currentSeq, positionLabel, remaining, nextTitle }: {
  stages: StepInput[]
  currentSeq: number
  positionLabel: string
  remaining: number
  nextTitle: string | null
}) {
  const cells = stepCells(stages, currentSeq)
  const stateLabel = { done: UI.stepper.done, current: UI.stepper.current, upcoming: UI.stepper.upcoming }
  return (
    <div data-testid="stepper">
      <ol className="flex items-center gap-1" aria-label={UI.stepper.label}>
        {stages.map((s, i) => {
          const st = cells[i].state
          return (
            <li key={s.seq} className="flex-1">
              <Tooltip
                width={240}
                testId="stepper-tooltip"
                content={
                  <div className="space-y-1">
                    <p className="font-semibold">
                      {s.seq}. {s.title} <span className="font-normal text-ink-muted">({stateLabel[st]})</span>
                    </p>
                    <p>{s.what_happens ?? s.what_happens_note}</p>
                    {s.note && <p className="text-ink-muted">{s.note}</p>}
                    {s.template_status && <p className="text-warn">{s.template_status}</p>}
                  </div>
                }
              >
                {(p) => (
                  <span
                    {...p}
                    tabIndex={0}
                    role="img"
                    aria-label={`${s.seq}. ${s.title} — ${stateLabel[st]}`}
                    aria-current={st === 'current' ? 'step' : undefined}
                    data-state={st}
                    data-testid="stepper-cell"
                    className={`block rounded-full outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand-indigo ${st === 'current' ? 'h-3' : 'h-2'} ${CELL[st]}`}
                  />
                )}
              </Tooltip>
            </li>
          )
        })}
      </ol>
      <p className="mt-2 text-meta" data-testid="stepper-line">
        {UI.stepper.line(positionLabel, remaining, nextTitle)}
      </p>
    </div>
  )
}
