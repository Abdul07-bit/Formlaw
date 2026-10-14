import { FileText, ShieldAlert, X } from 'lucide-react'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useDocPages } from '../../lib/queries'
import { cx, label } from '../../lib/util'
import { Badge, IconButton, Skeleton } from '../ui'

export interface ViewTarget { documentId: string; chunkId?: string; quote?: string; documentName?: string; page?: number }
const Ctx = createContext<(t: ViewTarget) => void>(() => {})
export const useViewer = () => useContext(Ctx)

export function ViewerProvider({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<ViewTarget | null>(null)
  return (
    <Ctx.Provider value={setTarget}>
      {children}
      {target && <DocumentViewer target={target} onClose={() => setTarget(null)} />}
    </Ctx.Provider>
  )
}

function highlight(text: string, quote?: string): ReactNode {
  if (!quote) return text
  // Quotes are taken from the stored chunk text, so a case-insensitive substring match locates them.
  const q = quote.trim().replace(/[.\s"']+$/, '')
  const i = text.toLowerCase().indexOf(q.toLowerCase())
  if (i < 0 || !q) return text
  return <>{text.slice(0, i)}<mark>{text.slice(i, i + q.length)}</mark>{text.slice(i + q.length)}</>
}

function DocumentViewer({ target, onClose }: { target: ViewTarget; onClose: () => void }) {
  const { data, isLoading, error } = useDocPages(target.documentId)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  useEffect(() => {
    if (!data || !target.chunkId) return
    ref.current?.querySelector(`[data-chunk="${target.chunkId}"]`)?.scrollIntoView({ block: 'center' })
  }, [data, target.chunkId])
  const doc = data?.document
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside aria-label="Document viewer" className="flex h-full w-full max-w-2xl flex-col border-l border-line bg-surface shadow-card">
        <header className="flex items-start gap-3 border-b border-line px-5 py-3">
          <FileText className="mt-0.5 size-5 text-muted" />
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{doc?.filename ?? target.documentName ?? 'Document'}</p>
            {doc && (
              <p className="text-xs text-muted">
                {label(doc.docType ?? 'document')} · {doc.pages ?? '?'} page(s) · SHA-256 <span className="font-mono">{doc.contentHash?.slice(0, 12)}…</span>
              </p>
            )}
          </div>
          <IconButton label="Close viewer" onClick={onClose}><X className="size-4" /></IconButton>
        </header>
        {doc?.securityFlags?.length ? (
          <div className="flex gap-2 border-b border-line bg-warn-soft px-5 py-2 text-[13px] text-warn">
            <ShieldAlert className="mt-0.5 size-4 shrink-0" />
            This document contains text that tries to instruct the AI. Those passages are shown here as evidence but are never sent to a model.
          </div>
        ) : null}
        <div ref={ref} className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading && <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-24" /></div>}
          {error && <p className="text-sm text-bad">This document could not be opened.</p>}
          {data?.pages.map((p) => (
            <section key={p.page} className="mb-6">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-faint">Page {p.page}</p>
              <div className="space-y-2 rounded-lg border border-line bg-bg p-4 font-serif text-[15px] leading-relaxed">
                {p.chunks.map((c, i) => {
                  const active = c.chunkId === target.chunkId
                  const newSection = c.section && c.section !== (i > 0 ? p.chunks[i - 1].section : null)
                  return (
                    <div key={c.chunkId} data-chunk={c.chunkId}
                      className={cx('rounded-md px-2 py-1', active && 'bg-accent-soft ring-1 ring-accent', c.securityFlags.length > 0 && 'bg-bad-soft/60')}>
                      {newSection && <p className="mt-2 font-sans text-[11px] font-semibold uppercase tracking-wide text-muted">{c.section}</p>}
                      <span className="mr-2 font-sans text-[11px] text-faint">¶{c.paragraph}</span>
                      {active ? highlight(c.text, target.quote) : c.text}
                      {c.securityFlags.length > 0 && <Badge tone="bad" className="ml-2 align-middle">instruction text · excluded from AI</Badge>}
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
      </aside>
    </div>
  )
}
