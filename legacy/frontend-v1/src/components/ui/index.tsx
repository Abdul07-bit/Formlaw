import { motion, AnimatePresence } from 'framer-motion'
import { X, Loader2 } from 'lucide-react'
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { ClaimStatus, KycStatus } from '../../types'

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')
export { cx }

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'dark'
const variants: Record<Variant, string> = {
  primary: 'bg-sky-500 text-white hover:bg-sky-600 shadow-[0_8px_24px_-8px_rgb(14_165_233/0.7)]',
  secondary: 'bg-white text-ink border border-sky-200 hover:border-sky-400 hover:bg-sky-50',
  ghost: 'text-ink-soft hover:bg-sky-50 hover:text-ink',
  danger: 'bg-rose-500 text-white hover:bg-rose-600',
  dark: 'bg-ink text-white hover:bg-[#13285a]',
}

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: ReactNode
  to?: string
}

export function Button({ variant = 'primary', size = 'md', loading, icon, to, className, children, ...rest }: BtnProps) {
  const cls = cx(
    'inline-flex items-center justify-center gap-2 rounded-2xl font-bold transition-all duration-200 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap',
    size === 'sm' && 'h-9 px-3.5 text-sm', size === 'md' && 'h-11 px-5 text-[15px]', size === 'lg' && 'h-14 px-7 text-base',
    variants[variant], className,
  )
  const inner = <>{loading ? <Loader2 className="size-4 animate-spin" /> : icon}{children}</>
  if (to) return <Link to={to} className={cls}>{inner}</Link>
  return <button className={cls} disabled={loading || rest.disabled} {...rest}>{inner}</button>
}

type Tone = 'sky' | 'green' | 'amber' | 'red' | 'slate' | 'violet'
const tones: Record<Tone, string> = {
  sky: 'bg-sky-50 text-sky-700 ring-sky-200',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  red: 'bg-rose-50 text-rose-700 ring-rose-200',
  slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200',
}
export function Badge({ tone = 'sky', children, className, icon }: { tone?: Tone; children: ReactNode; className?: string; icon?: ReactNode }) {
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset', tones[tone], className)}>
      {icon}{children}
    </span>
  )
}

export function DemoTag({ live }: { live?: boolean }) {
  return live
    ? <Badge tone="green" className="uppercase tracking-wider !text-[10px]">● Live</Badge>
    : <Badge tone="violet" className="uppercase tracking-wider !text-[10px]">Demo / Simulated</Badge>
}

export const claimTone: Record<ClaimStatus, Tone> = { supported: 'green', partial: 'amber', conflicted: 'red', unsupported: 'slate' }
export const claimLabel: Record<ClaimStatus, string> = { supported: 'Evidence-backed', partial: 'Partially supported', conflicted: 'Conflicting evidence', unsupported: 'Insufficient evidence' }

export function KycBadge({ status }: { status: KycStatus }) {
  const map: Record<KycStatus, [Tone, string]> = { verified: ['green', 'KYC Verified'], pending: ['amber', 'Verification pending'], rejected: ['red', 'KYC rejected'], not_started: ['slate', 'Not verified'] }
  const [tone, label] = map[status]
  return <Badge tone={tone}>{status === 'verified' && '✓ '}{label}</Badge>
}

export function Avatar({ initials, hue = 199, size = 48, verified }: { initials: string; hue?: number; size?: number; verified?: boolean }) {
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <div
        className="grid size-full place-items-center rounded-2xl font-extrabold text-white"
        style={{ background: `linear-gradient(135deg, hsl(${hue} 90% 58%), hsl(${hue + 20} 85% 40%))`, fontSize: size * 0.36 }}
        aria-hidden
      >
        {initials}
      </div>
      {verified && (
        <span className="absolute -bottom-1 -right-1 grid size-5 place-items-center rounded-full bg-emerald-500 text-[10px] font-black text-white ring-2 ring-white" title="KYC verified">✓</span>
      )}
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            role="dialog" aria-modal="true" aria-label={title}
            className={cx('relative max-h-[90vh] w-full overflow-auto rounded-3xl bg-white p-6 shadow-2xl scrollbar-thin', wide ? 'max-w-4xl' : 'max-w-lg')}
            initial={{ y: 30, scale: 0.96, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: 20, scale: 0.97, opacity: 0 }}
            transition={{ type: 'spring', damping: 26, stiffness: 320 }}
          >
            <div className="mb-4 flex items-start justify-between gap-4">
              <h3 className="text-xl">{title}</h3>
              <button onClick={onClose} className="rounded-xl p-1.5 text-ink-soft hover:bg-sky-50" aria-label="Close dialog"><X className="size-5" /></button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.18em] text-sky-600">{eyebrow}</p>}
        <h1 className="text-3xl md:text-4xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-2xl text-ink-soft">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-3">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-14 text-center">
      <div className="grid size-14 place-items-center rounded-2xl bg-sky-50 text-sky-500">{icon}</div>
      <h3 className="text-lg">{title}</h3>
      <p className="max-w-sm text-sm text-ink-soft">{body}</p>
      {action}
    </div>
  )
}

export function Stat({ label, value, icon, hint, tone = 'sky' }: { label: string; value: ReactNode; icon: ReactNode; hint?: string; tone?: Tone }) {
  return (
    <motion.div className="card card-hover p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-ink-soft">{label}</span>
        <span className={cx('grid size-9 place-items-center rounded-xl ring-1 ring-inset', tones[tone])}>{icon}</span>
      </div>
      <div className="mt-3 text-3xl font-extrabold">{value}</div>
      {hint && <div className="mt-1 text-xs font-semibold text-ink-soft">{hint}</div>}
    </motion.div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-bold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>}
    </label>
  )
}

export const inputCls =
  'w-full rounded-2xl border border-sky-200 bg-white px-4 py-3 text-[15px] font-semibold text-ink placeholder:text-slate-400 placeholder:font-medium outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100'
