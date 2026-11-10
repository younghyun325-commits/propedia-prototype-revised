/** 여러 화면에서 쓰는 store 동작 (P14) */
import type { MapProject } from '../api/map'
import { useMapStore } from './useMapStore'

/** 사업을 고르고 그 구역으로 이동 (사업 목록 카드·명령 팔레트) */
export function selectProject(p: MapProject): void {
  const s = useMapStore.getState()
  s.select({ kind: 'project', id: String(p.id) })
  s.setWorkspace('project')
  if (p.bbox) s.requestView({ type: 'bbox', bbox: p.bbox })
}

/** 오늘 (KST) 'YYYY.MM.DD' */
export function todayKst(now = new Date()): string {
  const s = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
  return s.replaceAll('-', '.')
}
