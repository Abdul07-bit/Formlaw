import { FileText } from 'lucide-react'
import type { Citation as C } from '../../lib/types'
import { useViewer } from './viewer'

/** Clickable source reference: opens the document at the exact page/paragraph with the quote highlighted. */
export function Citation({ c, compact }: { c: C; compact?: boolean }) {
  const open = useViewer()
  const name = c.documentName.replace(/\.(pdf|txt|docx|md)$/i, '')
  return (
    <button
      type="button"
      onClick={() => open({ documentId: c.documentId, chunkId: c.chunkId, quote: c.quote, documentName: c.documentName })}
      title={`“${c.quote}”`}
      className="inline-flex max-w-full items-center gap-1 rounded-md border border-line bg-surface-2 px-1.5 py-0.5 align-baseline text-[12px] font-medium text-accent hover:border-accent"
    >
      <FileText className="size-3 shrink-0" aria-hidden />
      <span className="truncate">{name}</span>
      <span className="shrink-0 text-muted">· p.{c.page}{compact ? '' : ` ¶${c.paragraph}`}</span>
    </button>
  )
}

export function Quote({ c }: { c: C }) {
  return (
    <figure className="rounded-lg border-l-2 border-gold bg-surface-2 px-3 py-2">
      <blockquote className="font-serif text-[14.5px] leading-relaxed">“{c.quote}”</blockquote>
      <figcaption className="mt-1"><Citation c={c} /></figcaption>
    </figure>
  )
}
