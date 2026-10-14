import { useEffect, useState } from 'react'
import { streamEvents } from './api'
import type { PlanStep, RunEvent } from './types'

export interface LiveRun {
  steps: PlanStep[]
  notes: { kind: string; text: string }[]
  intent: string | null
  rationale: string
  done: boolean
  failed: boolean
}

/** Follow a run's events. Steps are inserted where the orchestrator adapted the plan. */
export function useRunStream(runId: string | null, onDone: () => void): LiveRun {
  const [s, setS] = useState<LiveRun>({ steps: [], notes: [], intent: null, rationale: '', done: false, failed: false })
  useEffect(() => {
    if (!runId) return
    const ctl = new AbortController()
    let lastDone: string | null = null
    let finished = false
    setS({ steps: [], notes: [], intent: null, rationale: '', done: false, failed: false })
    const apply = (type: string, raw: unknown) => {
      const e = raw as RunEvent
      setS((prev) => {
        const steps = [...prev.steps]
        const at = (id: string | null) => steps.findIndex((x) => x.id === id)
        switch (type) {
          case 'intent':
            return { ...prev, intent: String(e.data.intent ?? '') }
          case 'plan': {
            const planned = (e.data.steps as PlanStep[]) ?? []
            const have = new Set(steps.map((x) => x.id))
            return { ...prev, rationale: e.summary, steps: [...steps, ...planned.filter((x) => !have.has(x.id))] }
          }
          case 'step.started': {
            const i = at(e.stepId)
            if (i >= 0) steps[i] = { ...steps[i], status: 'running' }
            else steps.push({ id: e.stepId ?? String(e.seq), agent: e.agent ?? '', action: String(e.data.action ?? ''), label: e.summary, status: 'running', origin: String(e.data.origin ?? 'gate'), reason: '', summary: '' })
            return { ...prev, steps }
          }
          case 'step.completed':
          case 'step.failed': {
            const i = at(e.stepId)
            const status = type === 'step.failed' ? 'failed' : (e.data.status === 'skipped' ? 'skipped' : 'done')
            if (i >= 0) steps[i] = { ...steps[i], status, summary: e.summary }
            lastDone = e.stepId
            return { ...prev, steps }
          }
          case 'adapt':
          case 'replan': {
            const inserted = (e.data.inserted as PlanStep[] | undefined) ?? []
            const i = at(lastDone)
            steps.splice(i >= 0 ? i + 1 : steps.length, 0, ...inserted.filter((x) => at(x.id) < 0))
            return { ...prev, steps, notes: [...prev.notes, { kind: type, text: e.summary }] }
          }
          case 'run.completed':
          case 'run.failed':
            return { ...prev, done: true, failed: type === 'run.failed' }
          default:
            return prev
        }
      })
      if (type === 'run.completed' || type === 'run.failed') {
        finished = true
        onDone()
      }
    }
    // The stream can also end without a terminal event (connection dropped, proxy timeout, server restart). Never keep
    // waiting on it: fall back to fetching the conversation, which shows the run's answer or failure message.
    const fallback = () => {
      if (!finished && !ctl.signal.aborted) onDone()
    }
    streamEvents(`/runs/${runId}/events`, apply, ctl.signal).then(fallback, fallback)
    return () => ctl.abort()
  }, [runId])
  return s
}
