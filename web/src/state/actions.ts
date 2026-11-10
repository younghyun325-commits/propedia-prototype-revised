/** 여러 화면에서 쓰는 store 동작 (P14) */
import type { MapProject } from '../api/map'
import { parseSelected } from './url'
import { useMapStore } from './useMapStore'

/** 사업을 고르고 그 구역으로 이동 (사업 목록 카드·명령 팔레트) */
export function selectProject(p: MapProject): void {
  const s = useMapStore.getState()
  s.select({ kind: 'project', id: String(p.id) })
  s.setWorkspace('project')
  if (p.bbox) s.requestView({ type: 'bbox', bbox: p.bbox })
}

/**
 * 피드·타임라인에서 대상 고르기 (P19): sel 값('project:1', 'regulation:D10')을 고르고 그 도형으로 이동.
 * date를 주면 기준일도 그날로 옮긴다. 잘못된 sel은 기준일만 옮긴다.
 */
export function focusSel(sel: string | null | undefined, date?: string | null): void {
  const s = useMapStore.getState()
  if (date !== undefined) s.setAsOf(date)
  const t = parseSelected(sel)
  if (!t) return
  s.select(t)
  if (t.kind === 'project') s.setWorkspace('project')
  if (t.kind === 'project' || t.kind === 'regulation') s.requestView({ type: 'feature', id: `${t.kind}:${t.id}` })
}

export { todayIso, todayKst } from './dates'
