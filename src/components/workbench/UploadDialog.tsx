import { CheckCircle2, FileUp, ShieldAlert, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { api, errorMessage } from '../../lib/api'
import type { CaseDocument } from '../../lib/types'
import { bytes } from '../../lib/util'
import { Button, Dialog } from '../ui'

interface Item { name: string; size: number; state: 'uploading' | 'done' | 'error'; doc?: CaseDocument; error?: string }

/** Upload → validate → hash → extract → scan → chunk → index happens server-side; this shows what came back. */
export function UploadDialog({ open, onClose, caseId, onUploaded, path }: { open: boolean; onClose: () => void; caseId: string; onUploaded: () => void; path?: string }) {
  const [items, setItems] = useState<Item[]>([])
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const upload = async (files: File[]) => {
    for (const f of files) {
      setItems((xs) => [...xs, { name: f.name, size: f.size, state: 'uploading' }])
      const fd = new FormData()
      fd.append('files', f)
      try {
        const [doc] = await api.post<CaseDocument[]>(path ?? `/cases/${caseId}/documents`, fd)
        setItems((xs) => xs.map((x) => (x.name === f.name && x.state === 'uploading' ? { ...x, state: 'done', doc } : x)))
        onUploaded()
      } catch (e) {
        setItems((xs) => xs.map((x) => (x.name === f.name && x.state === 'uploading' ? { ...x, state: 'error', error: errorMessage(e) } : x)))
      }
    }
  }

  return (
    <Dialog open={open} onClose={() => { setItems([]); onClose() }} title="Add documents">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload([...e.dataTransfer.files]) }}
        className={`flex flex-col items-center rounded-xl border-2 border-dashed px-6 py-8 text-center ${drag ? 'border-accent bg-accent-soft' : 'border-line'}`}
      >
        <FileUp className="mb-2 size-6 text-muted" />
        <p className="font-medium">Drop PDF, DOCX or text files</p>
        <p className="mt-1 text-[13px] text-muted">Files are validated, hashed, encrypted at rest and scanned for embedded instructions. Up to 15 MB each.</p>
        <Button className="mt-3" onClick={() => input.current?.click()}>Choose files</Button>
        <input ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
          onChange={(e) => { upload([...(e.target.files ?? [])]); e.target.value = '' }} />
      </div>
      {items.length > 0 && (
        <ul className="mt-4 space-y-2">
          {items.map((it, i) => (
            <li key={i} className="flex items-start gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
              {it.state === 'done' ? (it.doc?.securityFlags?.length ? <ShieldAlert className="mt-0.5 size-4 text-warn" /> : <CheckCircle2 className="mt-0.5 size-4 text-ok" />)
                : it.state === 'error' ? <XCircle className="mt-0.5 size-4 text-bad" /> : <span className="mt-1 size-3 animate-pulse-dot rounded-full bg-accent" />}
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{it.name} <span className="font-normal text-faint">{bytes(it.size)}</span></p>
                {it.state === 'uploading' && <p className="text-muted">Validating, extracting and indexing…</p>}
                {it.error && <p className="text-bad">{it.error}</p>}
                {it.doc && (
                  <p className="text-muted">
                    {it.doc.status === 'indexed' ? `Indexed · ${it.doc.pages ?? '?'} page(s) · detected as ${it.doc.docType?.replace('_', ' ')}` : it.doc.statusNote ?? it.doc.status}
                    {it.doc.securityFlags?.length ? <span className="block text-warn">Contains instructions aimed at AI — those passages will never be sent to a model. The document stays available as evidence.</span> : null}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  )
}
