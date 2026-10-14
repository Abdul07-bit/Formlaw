import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

/**
 * "Justice constellation": a faceted core, translucent case-file panels in orbit and a drifting particle network.
 * Follows the pointer and page scroll with eased motion. Pauses when off-screen or the tab is hidden; renders a single
 * still frame for people who prefer reduced motion. Colours come from the theme's CSS variables.
 * Loaded lazily (default export) so three.js never weighs on pages that don't show it.
 */
export default function Scene3D({ variant = 'hero', className = '' }: { variant?: 'hero' | 'portal'; className?: string }) {
  const host = useRef<HTMLDivElement>(null)
  const [theme, setTheme] = useState(() => document.documentElement.className)

  useEffect(() => {  // rebuild with the new palette when the user switches light/dark
    const mo = new MutationObserver(() => setTheme(document.documentElement.className))
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => mo.disconnect()
  }, [])

  useEffect(() => {
    const el = host.current
    if (!el) return
    const css = getComputedStyle(document.documentElement)
    const color = (v: string, fallback: string) => new THREE.Color((css.getPropertyValue(v) || fallback).trim())
    const accent = color('--accent', '#8fb0ef')
    const gold = color('--gold', '#d5b56a')
    const dark = document.documentElement.classList.contains('dark')
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const compact = variant === 'portal'

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x000000, 0)
    renderer.domElement.setAttribute('aria-hidden', 'true')
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(dark ? 0x111318 : 0xfbfaf7, 9, 22)
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
    const distance = compact ? 12 : 11
    camera.position.set(0, 0, distance)

    scene.add(new THREE.AmbientLight(0xffffff, dark ? 0.35 : 0.8))
    const keyLight = new THREE.PointLight(accent, 40, 30)
    keyLight.position.set(4, 3, 6)
    const rimLight = new THREE.PointLight(gold, 30, 30)
    rimLight.position.set(-5, -2, 4)
    scene.add(keyLight, rimLight)

    const world = new THREE.Group()
    world.position.x = compact ? 2.4 : 2.2
    scene.add(world)

    // Core: faceted crystal with a soft inner glow.
    const coreGeo = new THREE.IcosahedronGeometry(1.35, 1)
    const core = new THREE.Mesh(coreGeo, new THREE.MeshStandardMaterial({ color: accent, metalness: 0.35, roughness: 0.25, flatShading: true,
      transparent: true, opacity: 0.92, emissive: accent, emissiveIntensity: dark ? 0.25 : 0.12 }))
    const shell = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.9, 1)),
      new THREE.LineBasicMaterial({ color: gold, transparent: true, opacity: 0.45 }))
    world.add(core, shell)

    // Case files: thin glassy panels on tilted orbits.
    const panelGeo = new THREE.BoxGeometry(0.9, 1.2, 0.025)
    const panelEdges = new THREE.EdgesGeometry(panelGeo)
    const panelMat = new THREE.MeshStandardMaterial({ color: dark ? 0x1f2b44 : 0xffffff, metalness: 0.1, roughness: 0.3, transparent: true, opacity: dark ? 0.55 : 0.75 })
    const edgeMat = new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.8 })
    const lineMat = new THREE.LineBasicMaterial({ color: gold, transparent: true, opacity: 0.3 })
    const panels: { g: THREE.Group; r: number; speed: number; phase: number; tilt: number; y: number }[] = []
    const count = compact ? 7 : 11
    for (let i = 0; i < count; i++) {
      const g = new THREE.Group()
      g.add(new THREE.Mesh(panelGeo, panelMat), new THREE.LineSegments(panelEdges, edgeMat))
      for (let k = 0; k < 3; k++) {  // "lines of text" on the panel
        const w = 0.6 - k * 0.12
        const line = new THREE.Mesh(new THREE.PlaneGeometry(w, 0.035), new THREE.MeshBasicMaterial({ color: k ? accent : gold, transparent: true, opacity: 0.7 }))
        line.position.set(-(0.6 - w) / 2, 0.32 - k * 0.14, 0.016)  // left-aligned, like text
        g.add(line)
      }
      panels.push({ g, r: 2.5 + (i % 3) * 0.55, speed: 0.12 + (i % 4) * 0.03, phase: (i / count) * Math.PI * 2, tilt: ((i % 5) - 2) * 0.22, y: ((i % 3) - 1) * 0.8 })
      world.add(g)
    }

    // Particle network.
    const n = compact ? 160 : 320
    const pos = new Float32Array(n * 3)
    const seeds: number[] = []
    for (let i = 0; i < n; i++) {
      const r = 3 + Math.random() * 6, a = Math.random() * Math.PI * 2, b = (Math.random() - 0.5) * Math.PI
      pos.set([Math.cos(a) * Math.cos(b) * r, Math.sin(b) * r * 0.6, Math.sin(a) * Math.cos(b) * r - 2], i * 3)
      seeds.push(Math.random() * 10)
    }
    const pGeo = new THREE.BufferGeometry()
    pGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    const points = new THREE.Points(pGeo, new THREE.PointsMaterial({ color: accent, size: 0.045, transparent: true, opacity: dark ? 0.8 : 0.6, depthWrite: false }))
    world.add(points)
    const links = new THREE.LineSegments(new THREE.BufferGeometry(), lineMat)
    world.add(links)
    const base = pos.slice()

    const pointer = { x: 0, y: 0, tx: 0, ty: 0 }
    let scroll = 0
    const onPointer = (e: PointerEvent) => { pointer.tx = (e.clientX / window.innerWidth) * 2 - 1; pointer.ty = (e.clientY / window.innerHeight) * 2 - 1 }
    const onScroll = () => { scroll = Math.min(1, window.scrollY / Math.max(1, window.innerHeight)) }
    window.addEventListener('pointermove', onPointer, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = el
      if (!w || !h) return
      renderer.setSize(w, h, false)
      camera.aspect = w / h
      // Right of the text on wide screens (never across it); centred and smaller behind the text on phones.
      world.position.x = w < 768 ? 0 : compact ? 3.6 : Math.min(4.2, 2.6 + (w - 768) / 600)
      world.scale.setScalar(w < 768 ? 0.75 : 1)
      camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()

    const clock = new THREE.Clock()
    const frame = () => {
      const t = reduced ? 2 : clock.getElapsedTime()
      pointer.x += (pointer.tx - pointer.x) * 0.04
      pointer.y += (pointer.ty - pointer.y) * 0.04
      core.rotation.set(t * 0.18, t * 0.25, 0)
      shell.rotation.set(-t * 0.08, -t * 0.12, t * 0.05)
      for (const p of panels) {
        const a = p.phase + t * p.speed
        p.g.position.set(Math.cos(a) * p.r, p.y + Math.sin(a * 2 + p.phase) * 0.25, Math.sin(a) * p.r * 0.55)
        p.g.rotation.set(p.tilt, -a + Math.PI / 2, p.tilt * 0.5)
      }
      for (let i = 0; i < n; i++) {
        pos[i * 3 + 1] = base[i * 3 + 1] + Math.sin(t * 0.4 + seeds[i]) * 0.15
      }
      pGeo.attributes.position.needsUpdate = true
      // Link nearby particles (a sparse, shifting "network").
      const seg: number[] = []
      for (let i = 0; i < n && seg.length < 1200; i += 2) {
        for (let j = i + 1; j < Math.min(n, i + 14); j++) {
          const dx = pos[i * 3] - pos[j * 3], dy = pos[i * 3 + 1] - pos[j * 3 + 1], dz = pos[i * 3 + 2] - pos[j * 3 + 2]
          if (dx * dx + dy * dy + dz * dz < 0.9) seg.push(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2], pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2])
        }
      }
      links.geometry.setAttribute('position', new THREE.Float32BufferAttribute(seg, 3))
      world.rotation.y = pointer.x * 0.35 + scroll * 0.6
      world.rotation.x = pointer.y * 0.18
      camera.position.z = distance + scroll * 3
      camera.position.y = -scroll * 1.5
      camera.lookAt(world.position.x * 0.4, 0, 0)
      renderer.render(scene, camera)
    }

    let raf = 0
    let visible = true
    const loop = () => { frame(); raf = requestAnimationFrame(loop) }
    const start = () => { if (!raf && visible && !document.hidden && !reduced) { clock.start(); loop() } }
    const stop = () => { cancelAnimationFrame(raf); raf = 0 }
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) start(); else stop() })
    io.observe(el)
    const onVis = () => (document.hidden ? stop() : start())
    document.addEventListener('visibilitychange', onVis)
    frame()
    start()

    return () => {
      stop()
      io.disconnect()
      ro.disconnect()
      window.removeEventListener('pointermove', onPointer)
      window.removeEventListener('scroll', onScroll)
      document.removeEventListener('visibilitychange', onVis)
      scene.traverse((o) => {
        const m = o as THREE.Mesh
        m.geometry?.dispose()
        const mat = m.material as THREE.Material | THREE.Material[] | undefined
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose()); else mat?.dispose()
      })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [variant, theme])

  return <div ref={host} className={`pointer-events-none absolute inset-0 [&>canvas]:h-full [&>canvas]:w-full ${className}`} />
}
