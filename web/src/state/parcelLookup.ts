/**
 * 지도 클릭 필지 조회 흐름 (P15-3-3). 빈 곳 클릭 → 로딩 → 결과(필지 강조 + 인스펙터 카드) / 실패 문구.
 * 빠르게 여러 번 누르면 이전 요청은 취소한다. 결과는 화면 메모리에만 둔다.
 */
import { getParcelAt, getParcelByPnu, LatestRequest, type ParcelAt } from '../api/parcel'
import { UI } from '../copy/ui'
import { useMapStore } from './useMapStore'

const latest = new LatestRequest()

async function run(fetcher: (signal: AbortSignal) => Promise<ParcelAt>, point: [number, number] | null,
  pnu: string | null, fit: boolean): Promise<void> {
  const st = useMapStore.getState()
  const reqId = st.parcel.reqId + 1
  // 다른 선택을 내리고 로딩 표시 (URL sel은 결과가 오면 parcel:{pnu})
  useMapStore.setState({ parcel: { status: 'loading', reqId, point, pnu }, rightOpen: true,
    ...(pnu ? {} : { selected: null }) })
  const res = await latest.run(fetcher)
  if (!res || useMapStore.getState().parcel.reqId !== reqId) return // 취소됐거나 다른 선택으로 바뀜
  if (!res.ok) {
    useMapStore.setState({ parcel: { status: 'error', reqId, message: UI.parcel.failed } })
    return
  }
  const data = res.value
  useMapStore.setState({
    parcel: { status: 'done', reqId, data, fit },
    ...(data.status === 'ok' && data.pnu ? { selected: { kind: 'parcel' as const, id: data.pnu } } : {}),
  })
}

export function lookupParcelAt(lat: number, lon: number): Promise<void> {
  return run((signal) => getParcelAt(lat, lon, signal), [lon, lat], null, false)
}

/** 새로고침으로 sel=parcel:{pnu}가 있을 때 같은 필지를 다시 조회하고 그 경계로 이동 */
export function lookupParcelByPnu(pnu: string): Promise<void> {
  return run((signal) => getParcelByPnu(pnu, signal), null, pnu, true)
}

export function cancelParcelLookup(): void {
  latest.cancel()
}
