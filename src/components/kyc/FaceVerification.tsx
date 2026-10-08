import { motion } from 'framer-motion'
import { Camera, CameraOff, Check, RefreshCw, ScanFace } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Badge, Button, cx, DemoTag } from '../ui'

const CHECKS = ['Face detected in frame', 'Blink detected', 'Turn head left', 'Turn head right', 'Matching with ID photo']

export interface FaceResult { livenessPassed: boolean; faceMatchScore: number; thumbnail?: string }

/**
 * Captures a live camera frame and walks through a liveness script.
 * Prototype: liveness/face-match scores are SIMULATED — the backend will run a certified
 * liveness + 1:1 face-match provider and only return a score (no biometric stored in browser).
 */
export function FaceVerification({ onComplete }: { onComplete: (r: FaceResult) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const [state, setState] = useState<'idle' | 'starting' | 'live' | 'denied' | 'checking' | 'done'>('idle')
  const [step, setStep] = useState(0)
  const [thumb, setThumb] = useState<string>()
  const [score, setScore] = useState(0)

  const stop = () => { stream.current?.getTracks().forEach((t) => t.stop()); stream.current = null }
  useEffect(() => stop, [])
  useEffect(() => {
    if (state === 'live' && video.current && stream.current && video.current.srcObject !== stream.current) {
      video.current.srcObject = stream.current
      video.current.play().catch(() => {})
    }
  }, [state])

  const start = async () => {
    setState('starting')
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 }, audio: false })
      stream.current = s
      setState('live')
    } catch {
      setState('denied')
    }
  }

  const capture = () => {
    let dataUrl: string | undefined
    const v = video.current
    if (v && v.videoWidth) {
      const c = document.createElement('canvas')
      c.width = 160; c.height = 120
      c.getContext('2d')!.drawImage(v, 0, 0, 160, 120)
      dataUrl = c.toDataURL('image/jpeg', 0.6)
    }
    setThumb(dataUrl)
    setState('checking')
    setStep(0)
    let i = 0
    const t = setInterval(() => {
      i++
      setStep(i)
      if (i >= CHECKS.length) {
        clearInterval(t)
        const s = Math.round(91 + Math.random() * 7)
        setScore(s)
        setState('done')
        stop()
        onComplete({ livenessPassed: true, faceMatchScore: s / 100, thumbnail: dataUrl })
      }
    }, 750)
  }

  // Fallback path when no camera is available (e.g. desktop without webcam during a demo).
  const simulate = () => { setState('checking'); setStep(0); let i = 0; const t = setInterval(() => { i++; setStep(i); if (i >= CHECKS.length) { clearInterval(t); setScore(93); setState('done'); onComplete({ livenessPassed: true, faceMatchScore: 0.93 }) } }, 600) }

  return (
    <div className="grid gap-6 md:grid-cols-[1.1fr_1fr]">
      <div className="relative aspect-[4/3] overflow-hidden rounded-3xl bg-ink">
        {(state === 'live' || state === 'checking') && <video ref={video} muted playsInline className="size-full -scale-x-100 object-cover" aria-label="Camera preview" />}
        {state === 'done' && thumb && <img src={thumb} alt="Captured selfie" className="size-full -scale-x-100 object-cover opacity-80" />}
        {(state === 'idle' || state === 'starting' || state === 'denied' || (state === 'done' && !thumb)) && (
          <div className="grid size-full place-items-center p-6 text-center text-sky-100">
            <div>
              {state === 'denied' ? <CameraOff className="mx-auto size-12 text-amber-300" /> : <ScanFace className="mx-auto size-12 text-sky-300" />}
              <p className="mt-3 font-extrabold">{state === 'denied' ? 'Camera unavailable or permission denied' : state === 'done' ? 'Liveness verified' : 'Live facial verification'}</p>
              <p className="mt-1 text-sm text-sky-200/80">{state === 'denied' ? 'You can retry, or use demo verification for this prototype.' : 'We match your live face with the photo on your ID card.'}</p>
            </div>
          </div>
        )}
        {/* face guide */}
        {(state === 'live' || state === 'checking') && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <motion.div animate={{ scale: [1, 1.03, 1] }} transition={{ repeat: Infinity, duration: 2 }} className={cx('h-[70%] aspect-[3/4] rounded-[50%] border-4', state === 'checking' ? 'border-emerald-400' : 'border-sky-400 border-dashed')} />
            {state === 'checking' && <motion.div className="absolute inset-x-[20%] h-1 rounded-full bg-sky-400 shadow-[0_0_20px_#38bdf8]" initial={{ top: '15%' }} animate={{ top: ['15%', '85%', '15%'] }} transition={{ repeat: Infinity, duration: 2.2 }} />}
          </div>
        )}
        <div className="absolute left-3 top-3"><DemoTag /></div>
      </div>

      <div className="flex flex-col">
        <ol className="space-y-2">
          {CHECKS.map((c, i) => {
            const done = (state === 'checking' && i < step) || state === 'done'
            const active = state === 'checking' && i === step
            return (
              <li key={c} className={cx('flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-bold transition', done ? 'bg-emerald-50 text-emerald-800' : active ? 'bg-sky-50 text-sky-800 ring-1 ring-sky-200' : 'bg-white text-ink-soft ring-1 ring-sky-100')}>
                <span className={cx('grid size-6 place-items-center rounded-full text-white', done ? 'bg-emerald-500' : active ? 'bg-sky-500 animate-pulse' : 'bg-slate-200')}>{done ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}</span>{c}
              </li>
            )
          })}
        </ol>
        <div className="mt-auto pt-5">
          {state === 'done' ? (
            <div className="flex items-center justify-between rounded-2xl bg-emerald-50 p-4">
              <div><p className="font-extrabold text-emerald-800">Face match {score}%</p><p className="text-xs font-bold text-emerald-700">Liveness passed · selfie discarded after match</p></div>
              <Badge tone="green">Passed</Badge>
            </div>
          ) : state === 'live' ? (
            <Button className="w-full" size="lg" icon={<Camera className="size-5" />} onClick={capture}>Capture & verify</Button>
          ) : state === 'checking' ? (
            <Button className="w-full" size="lg" loading>Verifying…</Button>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button className="flex-1" size="lg" icon={state === 'denied' ? <RefreshCw className="size-5" /> : <Camera className="size-5" />} loading={state === 'starting'} onClick={start}>{state === 'denied' ? 'Retry camera' : 'Start camera'}</Button>
              <Button variant="secondary" size="lg" onClick={simulate}>Demo verify</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
