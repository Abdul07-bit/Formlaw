import { ArrowUp, Paperclip } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from '../../lib/util'

export function Composer({ onSend, onAttach, disabled, placeholder, autoFocus, footer, initial = '' }:
  { onSend: (text: string) => void; onAttach?: () => void; disabled?: boolean; placeholder?: string; autoFocus?: boolean; footer?: ReactNode; initial?: string }) {
  const [text, setText] = useState(initial)
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`
  }, [text])
  const send = () => {
    const t = text.trim()
    if (!t || disabled) return
    onSend(t)
    setText('')
  }
  return (
    <div className="rounded-2xl border border-line bg-surface shadow-card focus-within:border-line-strong">
      <textarea
        ref={ref}
        rows={1}
        value={text}
        autoFocus={autoFocus}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            send()
          }
        }}
        placeholder={placeholder ?? 'Ask FormLaw about this case…'}
        aria-label="Message"
        className="block max-h-60 w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[15px] placeholder:text-faint focus:outline-none focus-visible:outline-none"
      />
      <div className="flex items-center gap-2 px-2.5 pb-2.5">
        {onAttach && (
          <button type="button" onClick={onAttach} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[13px] text-muted hover:bg-surface-2 hover:text-fg">
            <Paperclip className="size-4" /> Add documents
          </button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {footer}
          <button type="button" onClick={send} disabled={disabled || !text.trim()} aria-label="Send"
            className={cx('inline-flex size-8 items-center justify-center rounded-lg bg-accent text-on-accent transition-opacity', (disabled || !text.trim()) && 'opacity-40')}>
            <ArrowUp className="size-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
