import type { ElementType, ReactNode } from 'react'

type Props = {
  as?: ElementType
  /** 리퀴드 글래스 굴절 (크롬 계열 + 작은 요소에만) */
  liquid?: boolean
  className?: string
  children?: ReactNode
  [key: string]: unknown
}

/** 기본 blur 글래스 카드. '투명도 줄이기'(html.reduce-transparency)면 glass.css가 불투명으로 바꾼다. */
export function GlassPanel({ as: Tag = 'div', liquid = false, className = '', children, ...rest }: Props) {
  const cls = ['glass', liquid ? 'glass-liquid' : '', className].filter(Boolean).join(' ')
  return (
    <Tag className={cls} {...rest}>
      {children}
    </Tag>
  )
}
