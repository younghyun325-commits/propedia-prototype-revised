export type Brand = { brand: string; version?: string }

/**
 * 크롬 계열(Chrome·Edge·Whale·Opera 등 Blink) 판별.
 * SVG 굴절 backdrop-filter(url(#lg))는 Blink만 그린다. Safari(iOS의 CriOS·EdgiOS 포함, 모두 WebKit)와 Firefox는 제외.
 */
export function isChromium(ua: string, brands?: Brand[] | null): boolean {
  if (brands && brands.some((b) => b.brand === 'Chromium')) return true
  if (/Firefox\/|FxiOS\//.test(ua)) return false
  if (/CriOS\/|EdgiOS\/|iPhone|iPad/.test(ua)) return false
  return /Chrome\/|Chromium\/|Edg\//.test(ua)
}
