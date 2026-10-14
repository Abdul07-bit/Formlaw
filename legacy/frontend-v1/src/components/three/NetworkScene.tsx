import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

const N = 90

/** Rotating globe of agent nodes with links between neighbours — background for the dark pipeline section. */
function Globe() {
  const ref = useRef<THREE.Group>(null)
  const pulse = useRef<THREE.InstancedMesh>(null)
  const { points, lines } = useMemo(() => {
    // Fibonacci sphere for even node spacing
    const pts: THREE.Vector3[] = []
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2
      const r = Math.sqrt(1 - y * y)
      const t = i * Math.PI * (3 - Math.sqrt(5))
      pts.push(new THREE.Vector3(Math.cos(t) * r, y, Math.sin(t) * r).multiplyScalar(2.4))
    }
    const seg: number[] = []
    pts.forEach((a, i) => pts.forEach((b, j) => { if (j > i && a.distanceTo(b) < 0.95) seg.push(a.x, a.y, a.z, b.x, b.y, b.z) }))
    return { points: pts, lines: new Float32Array(seg) }
  }, [])

  const dummy = useMemo(() => new THREE.Object3D(), [])
  useFrame(({ clock, pointer }, d) => {
    if (!ref.current) return
    ref.current.rotation.y += d * 0.12
    ref.current.rotation.x = THREE.MathUtils.lerp(ref.current.rotation.x, 0.25 - pointer.y * 0.2, 0.04)
    if (!pulse.current) return
    points.forEach((p, i) => {
      const s = 0.045 + Math.max(0, Math.sin(clock.elapsedTime * 1.4 + i * 0.7)) * 0.05
      dummy.position.copy(p); dummy.scale.setScalar(s / 0.05); dummy.updateMatrix()
      pulse.current!.setMatrixAt(i, dummy.matrix)
    })
    pulse.current.instanceMatrix.needsUpdate = true
  })

  return (
    <group ref={ref}>
      <lineSegments>
        <bufferGeometry><bufferAttribute attach="attributes-position" args={[lines, 3]} /></bufferGeometry>
        <lineBasicMaterial color="#38bdf8" transparent opacity={0.28} />
      </lineSegments>
      <instancedMesh ref={pulse} args={[undefined, undefined, N]}>
        <sphereGeometry args={[0.05, 12, 12]} />
        <meshBasicMaterial color="#7dd3fc" />
      </instancedMesh>
      <mesh><sphereGeometry args={[2.35, 48, 48]} /><meshBasicMaterial color="#0ea5e9" transparent opacity={0.05} /></mesh>
      <mesh><icosahedronGeometry args={[0.55, 1]} /><meshBasicMaterial color="#22c55e" wireframe transparent opacity={0.7} /></mesh>
    </group>
  )
}

export default function NetworkScene() {
  const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  return (
    <Canvas dpr={[1, 1.5]} camera={{ position: [0, 0, 6.5], fov: 45 }} frameloop={reduce ? 'demand' : 'always'} gl={{ antialias: true, alpha: true }}>
      <Globe />
    </Canvas>
  )
}
