import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { cx } from '../lib/util'

const Scene3D = lazy(() => import('./three/Scene3D'))

const hasWebGL = (() => {
  let cached: boolean | null = null
  return () => {
    if (cached === null) {
      try { cached = !!document.createElement('canvas').getContext('webgl2') } catch { cached = false }
    }
    return cached
  }
})()

/** Full-bleed 3D background with a gradient fallback (no WebGL, or while three.js loads). */
export function Hero3D({ variant = 'hero' }: { variant?: 'hero' | 'portal' }) {
  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden>
      <div className="aurora absolute inset-0" />
      {hasWebGL() && <Suspense fallback={null}><Scene3D variant={variant} /></Suspense>}
      {/* keeps the text legible over the scene */}
      <div className="absolute inset-y-0 left-0 w-full bg-gradient-to-r from-bg/85 via-bg/40 to-transparent md:w-3/5" />
      <div className="absolute inset-0 bg-bg/50 md:hidden" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-bg" />
    </div>
  )
}

/** Fades and lifts content into place (with a slight 3D tilt) when it scrolls into view. */
export function Reveal({ children, delay = 0, className, as: Tag = 'div' }: { children: ReactNode; delay?: number; className?: string; as?: 'div' | 'section' | 'li' }) {
  const ref = useRef<HTMLElement>(null)
  const [shown, setShown] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setShown(true); io.disconnect() } }, { rootMargin: '0px 0px -10% 0px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return <Tag ref={ref as never} className={cx('reveal', shown && 'is-shown', className)} style={{ '--reveal-delay': `${delay}ms` } as CSSProperties}>{children}</Tag>
}

/** A card that tilts toward the pointer in 3D. Static for keyboard users and reduced motion. */
export function Tilt({ children, className, max = 8 }: { children: ReactNode; className?: string; max?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const move = (e: React.PointerEvent) => {
    const el = ref.current
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5
    el.style.setProperty('--rx', `${-y * max}deg`)
    el.style.setProperty('--ry', `${x * max}deg`)
    el.style.setProperty('--gx', `${(x + 0.5) * 100}%`)
    el.style.setProperty('--gy', `${(y + 0.5) * 100}%`)
  }
  const leave = () => { ref.current?.style.setProperty('--rx', '0deg'); ref.current?.style.setProperty('--ry', '0deg') }
  return <div ref={ref} onPointerMove={move} onPointerLeave={leave} className={cx('tilt', className)}>{children}</div>
}

/** Counts up to a number once visible (instant for reduced motion). */
export function CountUp({ to, suffix = '' }: { to: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [v, setV] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setV(to); return }
    let raf = 0
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return
      io.disconnect()
      const t0 = performance.now()
      const step = (t: number) => { const p = Math.min(1, (t - t0) / 1200); setV(Math.round(to * (1 - (1 - p) ** 3))); if (p < 1) raf = requestAnimationFrame(step) }
      raf = requestAnimationFrame(step)
    })
    io.observe(el)
    return () => { io.disconnect(); cancelAnimationFrame(raf) }
  }, [to])
  return <span ref={ref}>{v.toLocaleString('en-IN')}{suffix}</span>
}
