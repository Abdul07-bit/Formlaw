import { AlertTriangle, BadgeCheck, CalendarDays, CheckCircle2, FileQuestion, FileText, ScanLine, Trash2, UploadCloud } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { Badge, Button } from '../ui'
import { Tilt } from '../motion'
import type { PublicLawyer } from '../../lib/types'
import { cx, label } from '../../lib/util'

export const ACCEPT = '.pdf,.docx,.txt,.png,.jpg,.jpeg'
export const inr = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n)

/** Drag-and-drop (or click / keyboard) file picker. */
export function Dropzone({ onFiles, busy, compact }: { onFiles: (f: File[]) => void; busy?: boolean; compact?: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const take = (list: FileList | null) => { const f = [...(list ?? [])]; if (f.length) onFiles(f) }
  return (
    <div role="button" tabIndex={0} aria-label="Upload case files: drop files here or press Enter to choose"
      onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), input.current?.click())}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files) }}
      className={cx('group relative flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed text-center transition-all duration-300',
        compact ? 'p-6' : 'p-10', over ? 'scale-[1.01] border-accent bg-accent-soft' : 'border-line-strong hover:border-accent hover:bg-surface-2/60')}>
      <span className={cx('flex size-14 items-center justify-center rounded-2xl bg-accent-soft text-accent transition-transform duration-300', over ? '-translate-y-1 scale-110' : 'group-hover:-translate-y-1')}>
        <UploadCloud className="size-7" />
      </span>
      <p className="mt-4 font-semibold">{busy ? 'Uploading…' : over ? 'Drop to upload' : 'Drop your case files here'}</p>
      <p className="mt-1 text-[13px] text-muted">or click to choose · PDF, Word, text, photos · up to 15 MB each, 10 at a time</p>
      <p className="mt-2 text-[12px] text-faint">Encrypted and checked for safety. Only you can see them until you choose to share.</p>
      <input ref={input} type="file" multiple hidden accept={ACCEPT} onChange={(e) => { take(e.target.files); e.target.value = '' }} />
    </div>
  )
}

export interface ReviewData {
  generatedAt: string; engine: string; disclaimer: string
  summary: { documents: number; readable: number; datedEvents: number; conflicts: number; missing: number }
  documents: { id: string; name: string; type: string; typeLabel: string; pages: number | null; status: 'read' | 'scanned' | 'unreadable'; note: string | null; datesFound: number; flagged: boolean }[]
  timeline: { date: string | null; dateText: string; event: string; source: string; page: number | null }[]
  conflicts: { event: string; note: string; sides: { date: string; dateText: string; source: string; page: number | null; quote: string }[] }[]
  missing: { key: string; title: string; why: string; basis: 'mentioned' | 'usually_needed'; mentionedIn: string[] }[]
}

function Stat({ n, label: l, tone }: { n: number; label: string; tone?: 'warn' | 'ok' }) {
  return (
    <div className="glass rounded-2xl p-4">
      <p className={cx('font-serif text-3xl', tone === 'warn' && n ? 'text-warn' : tone === 'ok' ? 'text-ok' : '')}>{n}</p>
      <p className="text-[13px] text-muted">{l}</p>
    </div>
  )
}

function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-muted">{icon}{title}</h3>
      {children}
    </section>
  )
}

const where = (source: string, page: number | null) => (page ? `${source} · page ${page}` : source)

export function ReviewPanel({ r }: { r: ReviewData }) {
  const [showAll, setShowAll] = useState(false)
  const mentioned = r.missing.filter((m) => m.basis === 'mentioned')
  const usual = r.missing.filter((m) => m.basis === 'usually_needed')
  const timeline = showAll ? r.timeline : r.timeline.slice(0, 8)
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat n={r.summary.readable} label={`of ${r.summary.documents} files read`} tone="ok" />
        <Stat n={r.summary.datedEvents} label="dated events" />
        <Stat n={r.summary.conflicts} label="conflicting dates" tone="warn" />
        <Stat n={r.summary.missing} label="documents to find" tone="warn" />
      </div>

      <Section icon={<FileText className="size-4" />} title="Your documents">
        <ul className="grid gap-2 sm:grid-cols-2">
          {r.documents.map((d) => (
            <li key={d.id} className="glass rounded-2xl p-3.5">
              <div className="flex items-center gap-2">
                {d.status === 'scanned' ? <ScanLine className="size-4 text-warn" /> : d.status === 'read' ? <CheckCircle2 className="size-4 text-ok" /> : <AlertTriangle className="size-4 text-bad" />}
                <span className="flex-1 truncate font-medium">{d.name}</span>
                <Badge tone={d.type === 'template' ? 'warn' : 'accent'}>{d.typeLabel}</Badge>
              </div>
              <p className="mt-1 text-[12.5px] text-muted">
                {d.status === 'read' ? `${d.pages ?? '?'} page(s) · ${d.datesFound} date(s) found` : d.note}
              </p>
              {d.status === 'read' && d.note && <p className="mt-1 text-[12.5px] text-warn">{d.note}</p>}
            </li>
          ))}
        </ul>
      </Section>

      {!!r.conflicts.length && (
        <Section icon={<AlertTriangle className="size-4 text-warn" />} title="Dates that don't match">
          {r.conflicts.map((c) => (
            <div key={c.event} className="rounded-2xl border border-warn/40 bg-warn-soft/40 p-4">
              <p className="font-semibold">{c.event}</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {c.sides.map((s) => (
                  <Tilt key={s.date + s.source} className="glass rounded-xl p-3" max={4}>
                    <p className="font-serif text-xl">{s.dateText}</p>
                    <p className="text-[12px] text-faint">{where(s.source, s.page)}</p>
                    <p className="mt-2 text-[13px] text-muted">“{s.quote}”</p>
                  </Tilt>
                ))}
              </div>
              <p className="mt-3 text-[13px] text-muted">{c.note}</p>
            </div>
          ))}
        </Section>
      )}

      {!!r.missing.length && (
        <Section icon={<FileQuestion className="size-4" />} title="Documents to look for">
          <ul className="space-y-2">
            {[...mentioned, ...usual].map((m) => (
              <li key={m.key} className="flex gap-3 rounded-2xl border border-line bg-surface p-3.5">
                <span className={cx('mt-1 size-2.5 shrink-0 rounded-full', m.basis === 'mentioned' ? 'bg-warn' : 'bg-faint')} />
                <div>
                  <p className="font-medium">{m.title} <span className="ml-1 text-[12px] font-normal text-faint">{m.basis === 'mentioned' ? `mentioned in ${m.mentionedIn.join(', ')}` : 'usually needed for this kind of matter'}</span></p>
                  {m.why && <p className="text-[13px] text-muted">{m.why}</p>}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {!!r.timeline.length && (
        <Section icon={<CalendarDays className="size-4" />} title="Timeline from your files">
          <ol className="relative space-y-4 border-l-2 border-line pl-6">
            {timeline.map((t, i) => (
              <li key={i} className="relative">
                <span className="absolute -left-[31px] top-1.5 size-3 rounded-full border-2 border-accent bg-bg" />
                <p className="font-medium">{t.dateText}</p>
                <p className="text-[13.5px] text-muted">{t.event}</p>
                <p className="text-[12px] text-faint">{where(t.source, t.page)}</p>
              </li>
            ))}
          </ol>
          {r.timeline.length > 8 && <Button size="sm" variant="ghost" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show less' : `Show all ${r.timeline.length}`}</Button>}
        </Section>
      )}
      <p className="text-[12px] text-faint">{r.disclaimer} · {r.engine}</p>
    </div>
  )
}

export function FileList({ files, onDelete }: { files: { id: string; filename: string; size: number }[]; onDelete?: (id: string) => void }) {
  if (!files.length) return null
  return (
    <ul className="space-y-1.5">
      {files.map((f) => (
        <li key={f.id} className="flex items-center gap-3 rounded-xl border border-line bg-surface px-3 py-2 text-[14px]">
          <FileText className="size-4 text-muted" /><span className="flex-1 truncate">{f.filename}</span>
          {f.size > 0 && <span className="text-[12px] text-faint">{Math.max(1, Math.round(f.size / 1024))} KB</span>}
          {onDelete && <button type="button" aria-label={`Remove ${f.filename}`} onClick={() => onDelete(f.id)} className="rounded-lg p-1 text-faint hover:bg-bad-soft hover:text-bad"><Trash2 className="size-4" /></button>}
        </li>
      ))}
    </ul>
  )
}

const FIT: Record<string, { tone: 'ok' | 'warn' | 'bad' | 'neutral'; text: string }> = {
  within: { tone: 'ok', text: 'Within your budget' }, partly: { tone: 'warn', text: 'Partly within your budget' },
  above: { tone: 'bad', text: 'Above your budget' }, not_declared: { tone: 'neutral', text: 'Fees not declared' },
}

export function AdvocateCard({ lawyer, reasons, considerations, fit, action }: {
  lawyer: PublicLawyer; reasons: string[]; considerations: string[]; fit: string | null; action: ReactNode
}) {
  const f = fit ? FIT[fit] : null
  return (
    <Tilt className="glass flex h-full flex-col rounded-3xl p-5 shadow-card" max={5}>
      <div className="flex items-start gap-3">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-accent-soft font-serif text-lg text-accent">
          {lawyer.name.replace(/^Adv\.\s*/, '').split(' ').map((p) => p[0]).slice(0, 2).join('')}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{lawyer.name}</p>
          <p className="text-[13px] text-muted">{[lawyer.city, lawyer.languages?.join(', ')].filter(Boolean).join(' · ')}</p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            <Badge tone="ok"><BadgeCheck className="size-3" />verified</Badge>
            {lawyer.isDemo && <Badge>demo profile</Badge>}
            {lawyer.verifiedAreas?.map((a) => <Badge key={a}>{label(a)}</Badge>)}
          </div>
        </div>
      </div>
      {(lawyer.feeRange || lawyer.consultationFee != null) && (
        <div className="mt-4 rounded-2xl bg-surface-2/70 p-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-[13px] text-muted">Typical fee for a matter</p>
            {f && <Badge tone={f.tone}>{f.text}</Badge>}
          </div>
          <p className="font-serif text-xl">{lawyer.feeRange ? `${inr(lawyer.feeRange.min)} – ${inr(lawyer.feeRange.max)}` : '—'}</p>
          {lawyer.consultationFee != null && <p className="text-[13px] text-muted">First consultation {inr(lawyer.consultationFee)}</p>}
          <p className="mt-1 text-[11.5px] text-faint">Declared by the advocate, not verified by FormLaw. Agree fees in writing.</p>
        </div>
      )}
      <p className="mt-4 text-[13px] font-medium">Why suggested</p>
      <ul className="text-[13px] text-muted">{reasons.map((r) => <li key={r}>• {r}</li>)}</ul>
      {considerations.length > 0 && <ul className="mt-1 text-[12px] text-faint">{considerations.map((r) => <li key={r}>Note: {r}</li>)}</ul>}
      <div className="mt-auto pt-4">{action}</div>
    </Tilt>
  )
}
