/**
 * @file Scene3D.jsx
 * @description Core React component/service for the Project Nexus application.
 */

import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Float, MeshDistortMaterial } from '@react-three/drei'
import * as THREE from 'three'

function ParticleField() {
  const count = 2000
  const meshRef = useRef()

  const [positions, colors, sizes] = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const col = new Float32Array(count * 3)
    const siz = new Float32Array(count)
    const nexus = new THREE.Color('#22c55e')
    const blue = new THREE.Color('#3b82f6')
    const white = new THREE.Color('#ffffff')

    for (let i = 0; i < count; i++) {
      // Distribute in a sphere shape
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = 3 + Math.random() * 4

      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = r * Math.cos(phi)

      // Color mix
      const t = Math.random()
      const c = t < 0.4 ? nexus : t < 0.7 ? blue : white
      col[i * 3] = c.r
      col[i * 3 + 1] = c.g
      col[i * 3 + 2] = c.b

      siz[i] = 0.5 + Math.random() * 2.5
    }
    return [pos, col, siz]
  }, [])

  useFrame(({ clock }) => {
    if (!meshRef.current) return
    const t = clock.getElapsedTime() * 0.1
    meshRef.current.rotation.y = t
    meshRef.current.rotation.x = Math.sin(t * 0.5) * 0.1
  })

  return (
    <points ref={meshRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          count={count}
          array={colors}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-size"
          count={count}
          array={sizes}
          itemSize={1}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.025}
        vertexColors
        transparent
        opacity={0.8}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  )
}

function CenterSphere() {
  const meshRef = useRef()

  useFrame(({ clock }) => {
    if (!meshRef.current) return
    meshRef.current.rotation.y = clock.getElapsedTime() * 0.2
    meshRef.current.rotation.z = clock.getElapsedTime() * 0.1
  })

  return (
    <Float speed={1.5} rotationIntensity={0.3} floatIntensity={0.8}>
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[1.5, 20]} />
        <MeshDistortMaterial
          color="#22c55e"
          emissive="#22c55e"
          emissiveIntensity={0.15}
          roughness={0.3}
          metalness={0.8}
          distort={0.3}
          speed={2}
          transparent
          opacity={0.12}
          wireframe
        />
      </mesh>
    </Float>
  )
}

function InnerGlow() {
  return (
    <Float speed={0.8} rotationIntensity={0.1} floatIntensity={0.3}>
      <mesh>
        <sphereGeometry args={[0.6, 32, 32]} />
        <meshBasicMaterial
          color="#22c55e"
          transparent
          opacity={0.08}
        />
      </mesh>
    </Float>
  )
}

function OrbitalRings() {
  const ring1Ref = useRef()
  const ring2Ref = useRef()
  const ring3Ref = useRef()

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (ring1Ref.current) ring1Ref.current.rotation.z = t * 0.3
    if (ring2Ref.current) ring2Ref.current.rotation.z = -t * 0.2
    if (ring3Ref.current) ring3Ref.current.rotation.z = t * 0.15
  })

  return (
    <>
      <mesh ref={ring1Ref} rotation={[Math.PI * 0.3, 0, 0]}>
        <torusGeometry args={[2.2, 0.005, 16, 100]} />
        <meshBasicMaterial color="#22c55e" transparent opacity={0.15} />
      </mesh>
      <mesh ref={ring2Ref} rotation={[Math.PI * 0.6, Math.PI * 0.2, 0]}>
        <torusGeometry args={[2.8, 0.003, 16, 100]} />
        <meshBasicMaterial color="#3b82f6" transparent opacity={0.1} />
      </mesh>
      <mesh ref={ring3Ref} rotation={[Math.PI * 0.1, Math.PI * 0.5, 0]}>
        <torusGeometry args={[3.2, 0.003, 16, 100]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.05} />
      </mesh>
    </>
  )
}

export default function Scene3D({ className }) {
  return (
    <div className={`scene3d ${className || ''}`}>
      <Canvas
        camera={{ position: [0, 0, 7], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 1.5]}
      >
        <ambientLight intensity={0.2} />
        <pointLight position={[5, 5, 5]} intensity={0.5} color="#22c55e" />
        <pointLight position={[-5, -5, 5]} intensity={0.3} color="#3b82f6" />
        <ParticleField />
        <CenterSphere />
        <InnerGlow />
        <OrbitalRings />
      </Canvas>
    </div>
  )
}
