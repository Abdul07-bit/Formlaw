import { AlertTriangle, CheckCircle2, CircleDashed, CircleHelp, Loader2, X, XCircle } from 'lucide-react'
import { forwardRef, useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cx } from '../lib/util'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:opacity-90',
  secondary: 'bg-surface border border-line hover:bg-surface-2 text-fg',
  ghost: 'text-muted hover:text-fg hover:bg-surface-2',
  danger: 'bg-bad text-white hover:opacity-90',
}

export function Button({ variant = 'secondary', size = 'md', loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md'; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx('inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        size === 'sm' ? 'h-8 px-2.5 text-[13px]' : 'h-9 px-3.5 text-sm', VARIANTS[variant], className)}
    >
      {loading && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button {...rest} aria-label={label} title={label}
      className={cx('inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-40', className)}>
      {children}
    </button>
  )
}

const field = 'rounded-lg border border-line bg-surface px-3 text-sm text-fg placeholder:text-faint focus:border-accent focus:outline-none focus-visible:outline-none'
const width = (c?: string) => (c && /(^|\s)w-/.test(c) ? '' : 'w-full')
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...rest }, ref) => (
  <input ref={ref} {...rest} className={cx(field, width(className), 'h-9', className)} />
))
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...rest }, ref) => (
  <textarea ref={ref} {...rest} className={cx(field, width(className), 'py-2', className)} />
))
export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={cx(field, width(className), 'h-9', className)}>{children}</select>
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[13px] font-medium text-fg">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  )
}

type Tone = 'neutral' | 'ok' | 'warn' | 'bad' | 'info' | 'accent'
const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-muted border-line',
  ok: 'bg-ok-soft text-ok border-transparent',
  warn: 'bg-warn-soft text-warn border-transparent',
  bad: 'bg-bad-soft text-bad border-transparent',
  info: 'bg-info-soft text-accent border-transparent',
  accent: 'bg-accent-soft text-accent border-transparent',
}
export function Badge({ tone = 'neutral', children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  return <span title={title} className={cx('inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide', TONES[tone], className)}>{children}</span>
}

// Verification checks a statement against the passage it cites. "Matches source" means the document says it — not that it is true.
const STATUS: Record<string, { tone: Tone; label: string; icon: ReactNode }> = {
  SUPPORTED: { tone: 'ok', label: 'Matches source', icon: <CheckCircle2 className="size-3" /> },
  PARTIALLY_SUPPORTED: { tone: 'warn', label: 'Partly in source', icon: <CircleDashed className="size-3" /> },
  UNSUPPORTED: { tone: 'bad', label: 'Not in source', icon: <XCircle className="size-3" /> },
  CONTRADICTED: { tone: 'bad', label: 'Source contradicts', icon: <AlertTriangle className="size-3" /> },
  UNVERIFIED: { tone: 'neutral', label: 'Unverified', icon: <CircleHelp className="size-3" /> },
}
const SCOPE = 'Checked against the cited document: it shows what the document says, not that it is true.'
export function StatusBadge({ status, reason }: { status: string; reason?: string }) {
  const s = STATUS[status] ?? STATUS.UNVERIFIED
  return <Badge tone={s.tone} title={reason ? `${reason}. ${SCOPE}` : SCOPE}>{s.icon}{s.label}</Badge>
}

/** How clearly two sources disagree (not a probability). */
export function ConflictPill({ level }: { level: string }) {
  const [tone, text]: [Tone, string] = level === 'high' ? ['warn', 'clear conflict'] : level === 'medium' ? ['warn', 'likely conflict'] : ['neutral', 'possible conflict']
  return <Badge tone={tone} title="How directly the two sources disagree on the same point">{text}</Badge>
}

const ASSESSMENT_TONE: Record<string, Tone> = { strong: 'ok', partial: 'warn', conflicting: 'warn', insufficient: 'bad', not_assessed: 'neutral' }
/** Documentary-support assessment of an answer, with its basis. Describes the reviewed documents only. */
export function AssessmentPill({ level, label, reason }: { level: string; label: string; reason: string }) {
  return <Badge tone={ASSESSMENT_TONE[level] ?? 'neutral'} title={reason}>{label}</Badge>
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx('size-4 animate-spin text-muted', className)} aria-label="Loading" />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('animate-pulse rounded-lg bg-surface-2', className)} />
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-12 text-center">
      {icon && <div className="mb-3 text-faint">{icon}</div>}
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null
  return <p role="alert" className="rounded-lg bg-bad-soft px-3 py-2 text-sm text-bad">{children}</p>
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('rounded-xl border border-line bg-surface', className)}>{children}</div>
}

export function Dialog({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={cx('w-full rounded-2xl border border-line bg-surface shadow-card', wide ? 'max-w-3xl' : 'max-w-lg')}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="font-semibold">{title}</h2>
          <IconButton label="Close" onClick={onClose}><X className="size-4" /></IconButton>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: string; count?: number }[] }) {
  return (
    <div role="tablist" className="flex gap-0.5 overflow-x-auto [scrollbar-width:none]">
      {items.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cx('whitespace-nowrap rounded-md px-2 py-1 text-[13px] font-medium',
            value === t.id ? 'bg-surface-3 text-fg' : 'text-muted hover:text-fg')}>
          {t.label}{t.count ? <span className="ml-1 text-faint">{t.count}</span> : null}
        </button>
      ))}
    </div>
  )
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h3 className="text-[12px] font-semibold uppercase tracking-wider text-muted">{children}</h3>
      {right}
    </div>
  )
}
