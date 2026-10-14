import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Check, ChevronDown, GitBranch, Loader2, ShieldAlert, Terminal } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { TraceStep } from '../../types'
import { cx } from '../ui'

const kindStyle: Record<TraceStep['kind'], { ring: string; text: string; icon: ReactNode }> = {
  info: { ring: 'bg-sky-500', text: 'text-ink', icon: <Check className="size-3.5" strokeWidth={3} /> },
  ok: { ring: 'bg-emerald-500', text: 'text-ink', icon: <Check className="size-3.5" strokeWidth={3} /> },
  warn: { ring: 'bg-amber-500', text: 'text-amber-800', icon: <AlertTriangle className="size-3.5" strokeWidth={3} /> },
  danger: { ring: 'bg-rose-500', text: 'text-rose-700', icon: <ShieldAlert className="size-3.5" strokeWidth={3} /> },
  adapt: { ring: 'bg-violet-500', text: 'text-violet-800', icon: <GitBranch className="size-3.5" strokeWidth={3} /> },
}

/** Replays agent steps one at a time so the user sees the system plan, act, observe and adapt. */
export function AgentPipeline({ steps, onDone, speed = 520, title = 'Agents at work' }: { steps: TraceStep[]; onDone?: () => void; speed?: number; title?: string }) {
  const [shown, setShown] = useState(0)
  const doneRef = useRef(onDone)
  doneRef.current = onDone
  useEffect(() => {
    setShown(0)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) { setShown(steps.length); const t = setTimeout(() => doneRef.current?.(), 200); return () => clearTimeout(t) }
    let i = 0
    const tick = () => {
      i++
      setShown(i)
      if (i < steps.length) {
        const s = steps[i - 1]
        timer = setTimeout(tick, s.kind === 'adapt' || s.kind === 'danger' || s.kind === 'warn' ? speed * 2 : speed)
      } else timer = setTimeout(() => doneRef.current?.(), 700)
    }
    let timer = setTimeout(tick, 350)
    return () => clearTimeout(timer)
  }, [steps, speed])

  const progress = steps.length ? Math.round((shown / steps.length) * 100) : 0
  const active = steps[shown]
  return (
    <div className="card overflow-hidden" role="status" aria-live="polite">
      <div className="flex items-center justify-between border-b border-sky-100 bg-gradient-to-r from-sky-50 to-white px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="relative grid size-10 place-items-center rounded-2xl bg-sky-500 text-white animate-pulse-ring"><Loader2 className={cx('size-5', shown < steps.length && 'animate-spin')} /></span>
          <div>
            <p className="font-extrabold">{shown < steps.length ? title : 'Analysis complete'}</p>
            <p className="text-sm font-semibold text-ink-soft">{active ? `${active.agent} working…` : 'Evidence verified · results ready'}</p>
          </div>
        </div>
        <span className="font-mono text-sm font-bold text-sky-600">{progress}%</span>
      </div>
      <div className="h-1 bg-sky-100"><motion.div className="h-full bg-sky-500" animate={{ width: `${progress}%` }} transition={{ ease: 'easeOut' }} /></div>
      <ol className="max-h-[420px] space-y-1 overflow-auto p-4 scrollbar-thin">
        <AnimatePresence initial={false}>
          {steps.slice(0, shown + 1).map((s, i) => {
            const done = i < shown
            const st = kindStyle[s.kind]
            return (
              <motion.li key={i} layout initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} className={cx('flex items-start gap-3 rounded-2xl px-3 py-2.5 transition', !done && 'bg-sky-50 ring-1 ring-sky-200', s.kind === 'danger' && done && 'bg-rose-50', s.kind === 'adapt' && done && 'bg-violet-50')}>
                <span className={cx('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-white', done ? st.ring : 'bg-sky-200')}>
                  {done ? st.icon : <span className="size-2 rounded-full bg-sky-500 animate-ping" />}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-extrabold">{s.agent}</p>
                  <p className={cx('text-sm font-semibold', done ? st.text : 'text-ink-soft')}>{done ? s.message : 'working…'}</p>
                </div>
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ol>
    </div>
  )
}

export function AgentTrace({ taskId, steps }: { taskId: string; steps: TraceStep[] }) {
  const [open, setOpen] = useState(true)
  const color: Record<TraceStep['kind'], string> = { info: 'text-sky-300', ok: 'text-emerald-300', warn: 'text-amber-300', danger: 'text-rose-300', adapt: 'text-violet-300' }
  return (
    <div className="overflow-hidden rounded-3xl bg-ink text-sky-50 shadow-[var(--shadow-lift)]">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-5 py-4" aria-expanded={open}>
        <span className="flex items-center gap-2 font-extrabold"><Terminal className="size-4 text-sky-400" />Agent trace <span className="font-mono text-xs text-sky-300/80">{taskId}</span></span>
        <ChevronDown className={cx('size-5 transition', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ol initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden border-t border-white/10 font-mono text-[13px]">
            {steps.map((s, i) => (
              <li key={i} className="flex gap-4 px-5 py-1.5 hover:bg-white/5">
                <span className="w-12 shrink-0 text-sky-300/60">{`00:${s.t.toFixed(1).padStart(4, '0')}`}</span>
                <span className={cx('w-40 shrink-0 font-bold', color[s.kind])}>{s.agent}</span>
                <span className="text-sky-100/90">{s.message}</span>
              </li>
            ))}
            <li className="h-3" />
          </motion.ol>
        )}
      </AnimatePresence>
    </div>
  )
}

/** Animated horizontal/vertical flow used on landing + architecture pages. */
export function FlowGraph({ nodes, vertical }: { nodes: { label: string; sub?: string; icon: ReactNode }[]; vertical?: boolean }) {
  return (
    <div className={cx('flex gap-3', vertical ? 'flex-col items-stretch' : 'flex-col items-stretch md:flex-row md:items-center')}>
      {nodes.map((n, i) => (
        <div key={n.label} className={cx('flex items-center gap-3', vertical ? 'flex-col' : 'flex-col md:flex-row', 'md:flex-1')}>
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }} whileInView={{ opacity: 1, y: 0, scale: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.12, type: 'spring', damping: 18 }}
            className="card card-hover relative flex w-full items-center gap-3 p-4"
          >
            <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-sky-500 text-white">{n.icon}</span>
            <div><p className="font-extrabold leading-tight">{n.label}</p>{n.sub && <p className="text-xs font-semibold text-ink-soft">{n.sub}</p>}</div>
          </motion.div>
          {i < nodes.length - 1 && (
            <svg className={cx('shrink-0 text-sky-400', vertical ? 'h-6 w-4' : 'h-6 w-4 md:h-4 md:w-8')} viewBox={vertical ? '0 0 4 24' : '0 0 32 4'} aria-hidden>
              {vertical ? <line x1="2" y1="0" x2="2" y2="24" stroke="currentColor" strokeWidth="2.5" className="flow-line" /> : <>
                <line x1="0" y1="2" x2="32" y2="2" stroke="currentColor" strokeWidth="2.5" className="flow-line hidden md:block" />
              </>}
            </svg>
          )}
        </div>
      ))}
    </div>
  )
}
