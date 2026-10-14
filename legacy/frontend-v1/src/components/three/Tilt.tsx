import { motion, useMotionTemplate, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useRef, type ReactNode } from 'react'
import { cx } from '../ui'

const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Card that tilts toward the pointer in 3D with a moving glare. Children can pop out with `[transform:translateZ(40px)]`. */
export function Tilt({ children, className, max = 10 }: { children: ReactNode; className?: string; max?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const spring = { stiffness: 220, damping: 20 }
  const rx = useSpring(0, spring)
  const ry = useSpring(0, spring)
  const gx = useMotionValue(50)
  const gy = useMotionValue(50)
  const hover = useSpring(0, spring)
  const glare = useMotionTemplate`radial-gradient(circle at ${gx}% ${gy}%, rgba(255,255,255,0.55), transparent 55%)`
  const shadow = useTransform(hover, (h) => `0 ${12 + h * 18}px ${30 + h * 30}px -12px rgba(3,105,161,${0.18 + h * 0.17})`)

  const move = (e: React.PointerEvent) => {
    if (reduce || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    ry.set((px - 0.5) * max * 2)
    rx.set(-(py - 0.5) * max * 2)
    gx.set(px * 100); gy.set(py * 100); hover.set(1)
  }
  const leave = () => { rx.set(0); ry.set(0); hover.set(0) }

  return (
    <div className="h-full [perspective:900px]">
      <motion.div
        ref={ref}
        onPointerMove={move}
        onPointerLeave={leave}
        style={{ rotateX: rx, rotateY: ry, boxShadow: shadow, transformStyle: 'preserve-3d' }}
        className={cx('relative h-full', className)}
      >
        {children}
        <motion.div aria-hidden className="pointer-events-none absolute inset-0 rounded-[inherit] mix-blend-overlay" style={{ background: glare, opacity: hover }} />
      </motion.div>
    </div>
  )
}
