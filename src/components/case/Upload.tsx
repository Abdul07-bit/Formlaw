import { AnimatePresence, motion } from 'framer-motion'
import { Check, FileText, FileWarning, Loader2, ShieldAlert, UploadCloud, X } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import type { CaseDocument } from '../../types'
import { ACCEPT_ATTR, ALLOWED_LABELS, formatBytes, ingestFile, validateFile } from '../../services/ingest'
import { Badge, cx } from '../ui'

const STAGES = ['Uploading', 'Reading document', 'Extracting text', 'Detecting structure', 'Indexing evidence', 'Ready for review']

interface Item { key: string; name: string; size: number; stage: number; error?: string; doc?: CaseDocument }

export function DocumentUpload({ onDocuments, compact }: { onDocuments: (docs: CaseDocument[]) => void; compact?: boolean }) {
  const [drag, setDrag] = useState(false)
  const [items, setItems] = useState<Item[]>([])
  const input = useRef<HTMLInputElement>(null)

  const process = useCallback(async (files: FileList | File[]) => {
    const list = [...files].slice(0, 20)
    const fresh: Item[] = list.map((f, i) => {
      const v = validateFile(f)
      return { key: `${Date.now()}-${i}`, name: f.name, size: f.size, stage: v.ok ? 0 : -1, error: v.ok ? undefined : v.reason }
    })
    setItems((prev) => [...fresh, ...prev])
    const ready: CaseDocument[] = []
    await Promise.all(list.map(async (f, i) => {
      const it = fresh[i]
      if (it.error) return
      try {
        const doc = await ingestFile(f)
        for (let s = 1; s < STAGES.length; s++) {
          await new Promise((r) => setTimeout(r, 260 + Math.random() * 260))
          setItems((prev) => prev.map((p) => (p.key === it.key ? { ...p, stage: s, doc } : p)))
        }
        ready.push(doc)
      } catch (e) {
        setItems((prev) => prev.map((p) => (p.key === it.key ? { ...p, stage: -1, error: (e as Error).message } : p)))
      }
    }))
    if (ready.length) onDocuments(ready)
  }, [onDocuments])

  return (
    <div className="space-y-4">
      <motion.div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) process(e.dataTransfer.files) }}
        animate={{ scale: drag ? 1.015 : 1 }}
        className={cx('relative overflow-hidden rounded-3xl border-2 border-dashed text-center transition-colors', compact ? 'p-6' : 'p-10 md:p-14', drag ? 'border-sky-500 bg-sky-50' : 'border-sky-200 bg-white hover:border-sky-400')}
      >
        <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" />
        <div className="relative">
          <motion.div animate={{ y: drag ? -6 : 0 }} className="mx-auto grid size-16 place-items-center rounded-3xl bg-sky-500 text-white shadow-[var(--shadow-glow)]"><UploadCloud className="size-8" /></motion.div>
          <h3 className="mt-5 text-xl">{drag ? 'Drop to add evidence' : 'Add evidence to your case'}</h3>
          <p className="mt-1 text-sm font-semibold text-ink-soft">Drag files here or</p>
          <button type="button" onClick={() => input.current?.click()} className="mt-3 rounded-2xl bg-ink px-5 py-2.5 text-sm font-extrabold text-white transition hover:bg-[#13285a]">Browse files</button>
          <input ref={input} type="file" multiple accept={ACCEPT_ATTR} className="sr-only" aria-label="Upload case documents" onChange={(e) => { if (e.target.files) process(e.target.files); e.target.value = '' }} />
          <div className="mt-5 flex flex-wrap justify-center gap-1.5">{ALLOWED_LABELS.map((l) => <Badge key={l} tone="slate">{l}</Badge>)}</div>
          <p className="mx-auto mt-4 flex max-w-md items-center justify-center gap-1.5 text-xs font-bold text-amber-700">
            <ShieldAlert className="size-3.5 shrink-0" />Uploaded documents are treated as untrusted content. Embedded instructions are never executed.
          </p>
        </div>
      </motion.div>

      <AnimatePresence initial={false}>
        {items.map((it) => (
          <motion.div key={it.key} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="card p-4">
            <div className="flex items-center gap-3">
              <span className={cx('grid size-10 place-items-center rounded-xl', it.error ? 'bg-rose-50 text-rose-500' : 'bg-sky-50 text-sky-600')}>{it.error ? <FileWarning className="size-5" /> : <FileText className="size-5" />}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-extrabold">{it.name}</p>
                  {it.doc && <Badge tone={it.doc.extraction === 'live' ? 'green' : 'violet'}>{it.doc.extraction === 'live' ? 'Text extracted' : 'Queued for server OCR'}</Badge>}
                </div>
                <p className={cx('text-xs font-bold', it.error ? 'text-rose-600' : 'text-ink-soft')}>{it.error ?? `${formatBytes(it.size)} · ${STAGES[Math.max(0, it.stage)]}`}</p>
              </div>
              {it.error ? <button onClick={() => setItems((p) => p.filter((x) => x.key !== it.key))} aria-label="Dismiss" className="rounded-lg p-1 text-ink-soft hover:bg-sky-50"><X className="size-4" /></button>
                : it.stage === STAGES.length - 1 ? <span className="grid size-7 place-items-center rounded-full bg-emerald-500 text-white"><Check className="size-4" strokeWidth={3} /></span>
                  : <Loader2 className="size-5 animate-spin text-sky-500" />}
            </div>
            {!it.error && (
              <div className="mt-3 grid grid-cols-6 gap-1">
                {STAGES.map((s, i) => <motion.div key={s} className="h-1.5 rounded-full" animate={{ backgroundColor: i <= it.stage ? '#0ea5e9' : '#e0f2fe' }} title={s} />)}
              </div>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
