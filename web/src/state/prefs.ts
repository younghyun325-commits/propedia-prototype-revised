/**
 * 보는 사람 한 명의 화면 설정 (P20): 브라우저 localStorage에만 둔다. 사생활 보호 모드·저장 차단이면 기본값으로 동작.
 * 모든 읽기·쓰기를 try/catch로 감싼다.
 */
export const REDUCE_TRANSPARENCY_KEY = 'propedia.map.reduceTransparency.v1'

export function readBool(key: string, fallback = false): boolean {
  try {
    const v = window.localStorage.getItem(key)
    return v === null ? fallback : v === '1'
  } catch {
    return fallback
  }
}

export function writeBool(key: string, v: boolean): void {
  try {
    window.localStorage.setItem(key, v ? '1' : '0')
  } catch {
    /* 저장 안 됨: 이번 방문 동안만 유지 */
  }
}
