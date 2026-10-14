import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Float, RoundedBox, ContactShadows } from '@react-three/drei'
import { useEffect, useMemo, useRef, type ReactNode, type RefObject } from 'react'
import * as THREE from 'three'

const SKY = '#0ea5e9'
const SKY_LIGHT = '#7dd3fc'
const GOLD = '#f59e0b'
const EMERALD = '#10b981'

function Scales() {
  const beam = useRef<THREE.Group>(null)
  const left = useRef<THREE.Group>(null)
  const right = useRef<THREE.Group>(null)
  useFrame(({ clock }) => {
    const a = Math.sin(clock.elapsedTime * 0.8) * 0.12
    if (beam.current) beam.current.rotation.z = a
    // pans hang vertically regardless of beam tilt
    if (left.current) { left.current.position.y = Math.sin(a) * -1.25; left.current.rotation.z = -a }
    if (right.current) { right.current.position.y = Math.sin(a) * 1.25; right.current.rotation.z = -a }
  })
  const metal = <meshStandardMaterial color={SKY} metalness={0.55} roughness={0.25} />
  return (
    <group position={[0, -0.4, 0]}>
      {/* base */}
      <mesh position={[0, -1.55, 0]} castShadow><cylinderGeometry args={[0.9, 1.1, 0.25, 48]} /><meshStandardMaterial color="#ffffff" roughness={0.3} /></mesh>
      <mesh position={[0, -1.35, 0]}><cylinderGeometry args={[0.55, 0.75, 0.2, 48]} />{metal}</mesh>
      {/* pillar */}
      <mesh position={[0, 0, 0]} castShadow><cylinderGeometry args={[0.08, 0.12, 2.6, 24]} />{metal}</mesh>
      <mesh position={[0, 1.42, 0]}><sphereGeometry args={[0.16, 32, 32]} /><meshStandardMaterial color={GOLD} metalness={0.7} roughness={0.2} /></mesh>
      <group position={[0, 1.15, 0]}>
        <group ref={beam}>
          <mesh rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.05, 0.05, 2.6, 16]} />{metal}</mesh>
        </group>
        {[[-1.25, left], [1.25, right]].map(([x, ref]) => (
          <group key={x as number} position={[x as number, 0, 0]} ref={ref as RefObject<THREE.Group>}>
            {[-0.32, 0.32].map((dx) => (
              <mesh key={dx} position={[dx / 2, -0.45, 0]} rotation={[0, 0, dx > 0 ? 0.33 : -0.33]}>
                <cylinderGeometry args={[0.012, 0.012, 0.95, 6]} /><meshStandardMaterial color="#94a3b8" />
              </mesh>
            ))}
            <mesh position={[0, -0.92, 0]} castShadow>
              <cylinderGeometry args={[0.48, 0.3, 0.12, 48]} /><meshStandardMaterial color={SKY_LIGHT} metalness={0.4} roughness={0.25} />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  )
}

function ChakraRing() {
  const ref = useRef<THREE.Group>(null)
  useFrame((_, d) => { if (ref.current) ref.current.rotation.z -= d * 0.15 })
  return (
    <group ref={ref} position={[0, 0.2, -2.2]}>
      <mesh><torusGeometry args={[2.6, 0.035, 16, 120]} /><meshStandardMaterial color={SKY} emissive={SKY} emissiveIntensity={0.25} /></mesh>
      <mesh><torusGeometry args={[0.28, 0.03, 16, 48]} /><meshStandardMaterial color={SKY} /></mesh>
      {Array.from({ length: 24 }, (_, i) => (
        <mesh key={i} rotation={[0, 0, (i * Math.PI) / 12]} position={[Math.cos((i * Math.PI) / 12 + Math.PI / 2) * 1.43, Math.sin((i * Math.PI) / 12 + Math.PI / 2) * 1.43, 0]}>
          <boxGeometry args={[0.025, 2.3, 0.02]} />
          <meshStandardMaterial color={SKY_LIGHT} transparent opacity={0.55} />
        </mesh>
      ))}
    </group>
  )
}

function DocCard({ position, rotation, accent }: { position: [number, number, number]; rotation: [number, number, number]; accent: string }) {
  return (
    <Float speed={1.6} rotationIntensity={0.5} floatIntensity={1.2}>
      <group position={position} rotation={rotation}>
        <RoundedBox args={[0.9, 1.15, 0.04]} radius={0.06} smoothness={4} castShadow>
          <meshStandardMaterial color="#ffffff" roughness={0.35} />
        </RoundedBox>
        <mesh position={[0, 0.42, 0.025]}><planeGeometry args={[0.9, 0.1]} /><meshBasicMaterial color={accent} /></mesh>
        {[0.2, 0.06, -0.08, -0.22].map((y, i) => (
          <mesh key={y} position={[i % 2 ? -0.08 : -0.03, y, 0.025]}><planeGeometry args={[i % 2 ? 0.5 : 0.62, 0.05]} /><meshBasicMaterial color="#bae6fd" /></mesh>
        ))}
        <mesh position={[0.26, -0.4, 0.026]}><circleGeometry args={[0.09, 24]} /><meshBasicMaterial color="#22c55e" /></mesh>
      </group>
    </Float>
  )
}

function Particles() {
  const ref = useRef<THREE.Points>(null)
  const positions = useMemo(() => {
    const arr = new Float32Array(420 * 3)
    for (let i = 0; i < 420; i++) {
      const r = 3 + Math.random() * 4
      const t = Math.random() * Math.PI * 2
      arr.set([Math.cos(t) * r, (Math.random() - 0.5) * 6, Math.sin(t) * r - 2], i * 3)
    }
    return arr
  }, [])
  useFrame((_, d) => { if (ref.current) ref.current.rotation.y += d * 0.03 })
  return (
    <points ref={ref}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[positions, 3]} /></bufferGeometry>
      <pointsMaterial size={0.035} color={SKY} transparent opacity={0.7} sizeAttenuation />
    </points>
  )
}

/** The green check-shield from the FormLaw logo, extruded in 3D. */
function Shield(props: { position: [number, number, number] }) {
  const ref = useRef<THREE.Group>(null)
  const [shield, check] = useMemo(() => {
    const s = new THREE.Shape()
    s.moveTo(0, 0.62)
    s.bezierCurveTo(0.2, 0.5, 0.38, 0.48, 0.5, 0.48)
    s.bezierCurveTo(0.5, 0.05, 0.42, -0.35, 0, -0.62)
    s.bezierCurveTo(-0.42, -0.35, -0.5, 0.05, -0.5, 0.48)
    s.bezierCurveTo(-0.38, 0.48, -0.2, 0.5, 0, 0.62)
    const shieldGeo = new THREE.ExtrudeGeometry(s, { depth: 0.16, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.04, bevelSegments: 6, curveSegments: 32 })
    shieldGeo.center()
    const path = new THREE.CatmullRomCurve3([new THREE.Vector3(-0.2, 0.02, 0), new THREE.Vector3(-0.05, -0.14, 0), new THREE.Vector3(0.24, 0.2, 0)], false, 'catmullrom', 0)
    return [shieldGeo, new THREE.TubeGeometry(path, 32, 0.045, 12, false)]
  }, [])
  useFrame(({ clock }) => { if (ref.current) ref.current.rotation.y = Math.sin(clock.elapsedTime * 0.7) * 0.5 })
  return (
    <Float speed={2} floatIntensity={0.8} rotationIntensity={0.2}>
      <group ref={ref} position={props.position} scale={0.85}>
        <mesh geometry={shield} castShadow><meshPhysicalMaterial color={EMERALD} metalness={0.3} roughness={0.18} clearcoat={1} clearcoatRoughness={0.1} /></mesh>
        <mesh geometry={check} position={[0, 0, 0.14]}><meshStandardMaterial color="#ffffff" roughness={0.2} /></mesh>
      </group>
    </Float>
  )
}

/** Tilts the scene toward the pointer. Reads window events so it works while the canvas sits behind page content. */
function Rig({ children }: { children: ReactNode }) {
  const ref = useRef<THREE.Group>(null)
  const p = useRef({ x: 0, y: 0 })
  useEffect(() => {
    const on = (e: PointerEvent) => { p.current = { x: (e.clientX / window.innerWidth) * 2 - 1, y: -(e.clientY / window.innerHeight) * 2 + 1 } }
    window.addEventListener('pointermove', on, { passive: true })
    return () => window.removeEventListener('pointermove', on)
  }, [])
  useFrame(() => {
    if (!ref.current) return
    ref.current.rotation.y = THREE.MathUtils.lerp(ref.current.rotation.y, p.current.x * 0.35, 0.05)
    ref.current.rotation.x = THREE.MathUtils.lerp(ref.current.rotation.x, -p.current.y * 0.15, 0.05)
  })
  return <group ref={ref}>{children}</group>
}

/** Full-bleed: push the scene to the right half so the hero copy stays readable. Contained: fit to the canvas. */
function Stage({ full, children }: { full: boolean; children: ReactNode }) {
  const width = useThree((s) => s.viewport.width)
  const offset = full ? width * 0.25 : 0
  const scale = full ? THREE.MathUtils.clamp((width / 2 - offset) / 2.7, 0.7, 1.15) : Math.min(1, width / 7)
  return <group position={[offset, 0, 0]} scale={scale}>{children}</group>
}

export default function HeroScene({ full = false }: { full?: boolean }) {
  const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  return (
    <Canvas shadows dpr={[1, 1.75]} camera={{ position: [0, 0.4, 6.2], fov: 42 }} frameloop={reduce ? 'demand' : 'always'} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.85} />
      <directionalLight position={[4, 6, 5]} intensity={1.6} castShadow shadow-mapSize={[1024, 1024]} />
      <pointLight position={[-4, 2, 3]} intensity={18} color={SKY_LIGHT} />
      <Stage full={full}>
      <Rig>
        <ChakraRing />
        <Float speed={1.2} floatIntensity={0.4} rotationIntensity={0.15}><Scales /></Float>
        <DocCard position={[-2.5, 1.0, 0.4]} rotation={[0.1, 0.5, -0.12]} accent="#ff9933" />
        <DocCard position={[2.55, 0.7, 0.2]} rotation={[-0.05, -0.5, 0.1]} accent={SKY} />
        <DocCard position={[2.1, -1.3, 1]} rotation={[0.15, -0.3, 0.2]} accent="#138808" />
        <DocCard position={[-2.2, -1.25, 0.9]} rotation={[-0.1, 0.4, -0.18]} accent={SKY} />
        <Shield position={[1.15, -1.45, 1.4]} />
        <Particles />
      </Rig>
      <ContactShadows position={[0, -2.1, 0]} opacity={0.3} scale={10} blur={2.6} far={4} color="#0369a1" />
      </Stage>
    </Canvas>
  )
}
