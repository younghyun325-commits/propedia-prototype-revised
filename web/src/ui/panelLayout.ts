export const PANEL_MD = 380
export const PANEL_LG = 520

export type PanelTier = 'narrow' | 'normal' | 'wide'

export function panelTier(width: number): PanelTier {
  return width < PANEL_MD ? 'narrow' : width < PANEL_LG ? 'normal' : 'wide'
}

export const KV_GRID = 'grid grid-cols-1 @panel-md:grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 @panel-md:gap-y-1'
export const ONLY_NARROW = '@panel-md:hidden'
export const ONLY_WIDE = 'hidden @panel-lg:block'
export const ONLY_WIDE_INLINE = 'hidden @panel-lg:inline'
export const UNTIL_WIDE_INLINE = '@panel-lg:hidden'
export const WIDE_CELL = 'hidden @panel-lg:table-cell'
