import { AnimatePresence, motion } from 'framer-motion'
import { Check, FileText, FileWarning, Loader2, ShieldAlert, UploadCloud, X } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import { ACCEPT_ATTR, ALLOWED_LABELS, formatBytes, validateFile } from '../../services/ingest'
import { Badge, cx } from '../ui'

export interface UploadItem { key: string; file: File; status: 'ready' | 'uploading' | 'done' | 'error'; error?: string; note?: string }

/**
 * Drop zone. Files are pre-checked here for quick feedback, then handed to the parent which uploads
 * them; the server re-validates content, extracts text and scans for embedded instructions.
 */
export function DocumentUpload({ onFiles, items, onRemove, compact }: {
  onFiles: (files: File[]) => void; items: UploadItem[]; onRemove?: (key: string) => void; compact?: boolean
}) {
  const [drag, setDrag] = useState(false)
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([])
  const input = useRef<HTMLInputElement>(null)

  const take = useCallback((files: FileList | File[]) => {
    const ok: File[] = []
    const bad: { name: string; reason: string }[] = []
    for (const f of [...files].slice(0, 20)) {
      const v = validateFile(f)
      if (v.ok) ok.push(f)
      else bad.push({ name: f.name, reason: v.reason })
    }
    setRejected(bad)
    if (ok.length) onFiles(ok)
  }, [onFiles])

  return (
    <div className="space-y-4">
      <motion.div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) take(e.dataTransfer.files) }}
        animate={{ scale: drag ? 1.015 : 1 }}
        className={cx('relative overflow-hidden rounded-3xl border-2 border-dashed text-center transition-colors', compact ? 'p-6' : 'p-10 md:p-14', drag ? 'border-sky-500 bg-sky-50' : 'border-sky-200 bg-white hover:border-sky-400')}
      >
        <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" />
        <div className="relative">
          <motion.div animate={{ y: drag ? -6 : 0 }} className="mx-auto grid size-16 place-items-center rounded-3xl bg-sky-500 text-white shadow-[var(--shadow-glow)]"><UploadCloud className="size-8" /></motion.div>
          <h3 className="mt-5 text-xl">{drag ? 'Drop to add evidence' : 'Add evidence to your case'}</h3>
          <p className="mt-1 text-sm font-semibold text-ink-soft">Drag files here or</p>
          <button type="button" onClick={() => input.current?.click()} className="mt-3 rounded-2xl bg-ink px-5 py-2.5 text-sm font-extrabold text-white transition hover:bg-[#13285a]">Browse files</button>
          <input ref={input} type="file" multiple accept={ACCEPT_ATTR} className="sr-only" aria-label="Upload case documents" onChange={(e) => { if (e.target.files) take(e.target.files); e.target.value = '' }} />
          <div className="mt-5 flex flex-wrap justify-center gap-1.5">{ALLOWED_LABELS.map((l) => <Badge key={l} tone="slate">{l}</Badge>)}</div>
          <p className="mx-auto mt-4 flex max-w-md items-center justify-center gap-1.5 text-xs font-bold text-amber-700">
            <ShieldAlert className="size-3.5 shrink-0" />Uploaded documents are treated as untrusted content. Embedded instructions are never executed.
          </p>
        </div>
      </motion.div>

      {rejected.map((r) => (
        <p key={r.name} className="flex items-center gap-2 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-bold text-rose-700" role="alert"><FileWarning className="size-4 shrink-0" />{r.name}: {r.reason}</p>
      ))}

      <AnimatePresence initial={false}>
        {items.map((it) => (
          <motion.div key={it.key} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="card flex items-center gap-3 p-4">
            <span className={cx('grid size-10 place-items-center rounded-xl', it.status === 'error' ? 'bg-rose-50 text-rose-500' : 'bg-sky-50 text-sky-600')}>{it.status === 'error' ? <FileWarning className="size-5" /> : <FileText className="size-5" />}</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-extrabold">{it.file.name}</p>
                {it.note && <Badge tone={it.note === 'Text extracted' ? 'green' : 'violet'}>{it.note}</Badge>}
              </div>
              <p className={cx('text-xs font-bold', it.status === 'error' ? 'text-rose-600' : 'text-ink-soft')}>
                {it.error ?? `${formatBytes(it.file.size)} · ${{ ready: 'Ready to upload', uploading: 'Uploading & extracting on the server…', done: 'Stored encrypted', error: '' }[it.status]}`}
              </p>
            </div>
            {it.status === 'uploading' ? <Loader2 className="size-5 animate-spin text-sky-500" />
              : it.status === 'done' ? <span className="grid size-7 place-items-center rounded-full bg-emerald-500 text-white"><Check className="size-4" strokeWidth={3} /></span>
                : onRemove && <button onClick={() => onRemove(it.key)} aria-label={`Remove ${it.file.name}`} className="rounded-lg p-1 text-ink-soft hover:bg-sky-50"><X className="size-4" /></button>}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

const NOTE: Record<string, string> = { extracted: 'Text extracted', needs_ocr: 'Awaiting OCR', failed: 'Unreadable', quarantined: 'Quarantined' }
export const processingNote = (status: string) => NOTE[status] ?? status

let n = 0
export const toItems = (files: File[]): UploadItem[] => files.map((file) => ({ key: `u${++n}`, file, status: 'ready' }))
