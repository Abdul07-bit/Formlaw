import { Check, ChevronDown, ChevronRight, Circle, CornerDownRight, Loader2, Minus, RefreshCw, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { PlanStep } from '../../lib/types'
import { cx } from '../../lib/util'

const ICON: Record<string, ReactNode> = {
  pending: <Circle className="size-3.5 text-faint" />,
  running: <Loader2 className="size-3.5 animate-spin text-accent" />,
  done: <Check className="size-3.5 text-ok" />,
  failed: <X className="size-3.5 text-bad" />,
  skipped: <Minus className="size-3.5 text-faint" />,
}

/** The agent plan, shown live while agents work and collapsed afterwards. Summaries are reasoning summaries, not chain-of-thought. */
export function AgentPlan({ steps, live, notes = [], stats }: { steps: PlanStep[]; live?: boolean; notes?: { kind: string; text: string }[]; stats?: string }) {
  const [open, setOpen] = useState(false)
  const expanded = live || open
  const visible = steps.filter((s) => s.action !== 'security.scan_request' || s.status === 'failed')
  const doneN = visible.filter((s) => s.status === 'done').length
  const adapted = steps.filter((s) => s.origin === 'adapt' || s.origin === 'replan').length
  return (
    <div className="rounded-xl border border-line bg-surface-2/60">
      <button type="button" onClick={() => setOpen(!open)} disabled={live}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-muted">
        {live ? <Loader2 className="size-3.5 animate-spin text-accent" /> : expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        <span className="font-medium text-fg">{live ? 'Working' : 'Plan'}</span>
        <span>{doneN}/{visible.length} steps</span>
        {adapted > 0 && <span className="inline-flex items-center gap-1 text-gold"><RefreshCw className="size-3" />adapted {adapted}×</span>}
        {stats && !live && <span className="ml-auto text-faint">{stats}</span>}
      </button>
      {expanded && (
        <ol className="space-y-1.5 border-t border-line px-3 py-2.5">
          {visible.map((s) => (
            <li key={s.id} className="flex gap-2.5">
              <span className="mt-1 shrink-0">{ICON[s.status] ?? ICON.pending}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] leading-snug">
                  <span className={cx(s.status === 'pending' ? 'text-muted' : 'text-fg')}>{s.label}</span>
                  <span className="ml-2 text-[11px] text-faint">{s.agent}</span>
                  {(s.origin === 'adapt' || s.origin === 'replan') && (
                    <span className="ml-2 rounded bg-warn-soft px-1 text-[10px] font-semibold uppercase tracking-wide text-warn">{s.origin === 'replan' ? 'replanned' : 'adapted'}</span>
                  )}
                </p>
                {s.reason && (s.origin === 'adapt' || s.origin === 'replan') && (
                  <p className="flex items-center gap-1 text-[12px] text-gold"><CornerDownRight className="size-3" />{s.reason}</p>
                )}
                {s.summary && s.status !== 'pending' && <p className="text-[12px] text-muted">{s.summary}</p>}
              </div>
            </li>
          ))}
          {live && notes.length > 0 && (
            <li className="pt-1 text-[12px] text-gold">↻ {notes[notes.length - 1].text}</li>
          )}
        </ol>
      )}
    </div>
  )
}
