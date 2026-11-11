/**
 * 출처 줄 (P16): 'D1 · 4쪽 · 2026-10-06' — 문서 번호 · PDF 쪽 · 문서 발행일.
 * 누르면 원문 보기 모달이 그 근거(문서·쪽·근거 문장)로 열린다. 이전/다음은 인스펙터의 근거 목록을 따른다.
 */
import { FileText } from 'lucide-react'
import type { EvidenceItem, SourceRef } from '../api/feature'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'

export function sourceText(src: { doc_id: string; pdf_page: number | null; published_at: string | null }): string {
  return [src.doc_id, src.pdf_page ? UI.source.page(src.pdf_page) : UI.source.noPage, src.published_at?.slice(0, 10)]
    .filter(Boolean)
    .join(' · ')
}

/** 근거 목록에서 이 출처(문서·쪽, 근거 문장이 있으면 그것까지)와 맞는 칸 */
export function evidenceIndex(items: EvidenceItem[], src: SourceRef, evidence?: string | null): number {
  const same = (e: EvidenceItem) => e.doc_id === src.doc_id && e.pdf_page === src.pdf_page
  const exact = items.findIndex((e) => same(e) && (evidence ? e.evidence === evidence : true))
  return exact >= 0 ? exact : items.findIndex(same)
}

/** 근거 목록에 없을 때 (드묾) 이 출처 하나로 모달을 연다 */
function single(src: SourceRef, evidence: string | null | undefined, label: string): EvidenceItem {
  return {
    doc_id: src.doc_id, short_title: src.short_title, title: null, gosi_no: null, published_at: src.published_at,
    pdf_page: src.pdf_page, page_label: src.page_label, evidence: evidence ?? null, page_image: src.page_image,
    docs_url: `/docs.html?doc=${src.doc_id}${src.pdf_page ? `&page=${src.pdf_page}` : ''}`, label,
  }
}

export function EvidenceLine({ source, evidence, items, label = '', className = '', testId = 'evidence-line' }: {
  source: SourceRef | null | undefined
  evidence?: string | null
  /** 인스펙터 전체 근거 목록 (모달 이전/다음) */
  items: EvidenceItem[]
  label?: string
  className?: string
  testId?: string
}) {
  const open = useMapStore((s) => s.openEvidence)
  if (!source) return null
  const text = sourceText(source)
  const onClick = () => {
    const i = evidenceIndex(items, source, evidence)
    if (i >= 0) open(items, i)
    else open([single(source, evidence, label)], 0)
  }
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      data-doc={source.doc_id}
      data-page={source.pdf_page ?? ''}
      title={`${UI.source.open}: ${source.short_title}`}
      aria-label={`${UI.source.open}: ${source.short_title} ${text}`}
      className={`inline-flex items-center gap-1 rounded-md px-1 py-px text-caption text-ink-muted tabular-nums underline-offset-2 hover:bg-brand-indigo/8 hover:text-ink hover:underline focus-visible:outline-2 focus-visible:outline-brand-indigo ${className}`}
    >
      <FileText size={11} aria-hidden="true" />
      {text}
    </button>
  )
}
