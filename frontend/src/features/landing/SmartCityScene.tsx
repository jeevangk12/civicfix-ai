import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { Color, Object3D, OrthographicCamera } from 'three'
import type { Group, InstancedMesh, Mesh } from 'three'
import { createCityModel, type CityInstance } from './cityModel'
import { gsap, useGSAP } from './motion'
import { sceneIssues, type SceneIssue } from './sceneIssues'

export type SmartCitySceneProps = {
  compact: boolean
  animate: boolean
  onReady: () => void
  onUnavailable: () => void
}

function InstanceBatch({ items, kind }: { items: CityInstance[]; kind: 'surface' | 'light' | 'tree' }) {
  const batch = useRef<InstancedMesh>(null)

  useLayoutEffect(() => {
    const mesh = batch.current
    if (!mesh) return
    const transform = new Object3D()
    const color = new Color()
    items.forEach((item, index) => {
      transform.position.set(...item.position)
      transform.scale.set(...item.scale)
      transform.updateMatrix()
      mesh.setMatrixAt(index, transform.matrix)
      mesh.setColorAt(index, color.set(item.color))
    })
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [items])

  return (
    <instancedMesh ref={batch} args={[undefined, undefined, items.length]} frustumCulled={false}>
      {kind === 'tree' ? <dodecahedronGeometry /> : <boxGeometry />}
      {kind === 'light'
        ? <meshBasicMaterial toneMapped={false} />
        : <meshStandardMaterial roughness={0.72} metalness={kind === 'tree' ? 0 : 0.16} />}
    </instancedMesh>
  )
}

function IssueMarker({ issue, onRing }: { issue: SceneIssue; onRing: (mesh: Mesh | null) => void }) {
  return (
    <group position={issue.position}>
      <mesh ref={onRing} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.34, 0.37, 30]} />
        <meshBasicMaterial color={issue.color} transparent opacity={0.66} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.43, 0]}>
        <cylinderGeometry args={[0.026, 0.022, 0.84, 6]} />
        <meshBasicMaterial color={issue.color} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.98, 0]}>
        <octahedronGeometry args={[0.24]} />
        <meshStandardMaterial color={issue.color} emissive={issue.color} emissiveIntensity={0.47} />
      </mesh>
      <mesh position={[0, 0.98, 0]} scale={1.35}>
        <octahedronGeometry args={[0.24]} />
        <meshBasicMaterial color={issue.color} opacity={0.16} transparent depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  )
}

function CityWorld({ compact, animate, onReady, onUnavailable }: SmartCitySceneProps) {
  const city = useRef<Group>(null)
  const rings = useRef<(Mesh | null)[]>([])
  const animation = useRef<gsap.core.Timeline | null>(null)
  const signalled = useRef(false)
  const { gl, invalidate, set, size } = useThree()
  const model = useMemo(() => createCityModel(compact), [compact])

  const camera = useMemo(() => {
    const view = new OrthographicCamera(-size.width / 2, size.width / 2, size.height / 2, -size.height / 2, 0.1, 80)
    view.position.set(16, 13.3, 18)
    view.lookAt(0, 1.42, 0)
    view.zoom = Math.min(size.width / 20.1, size.height / 17.5)
    view.updateProjectionMatrix()
    return view
  }, [size.width, size.height])

  useLayoutEffect(() => {
    set({ camera })
    invalidate()
  }, [camera, set, invalidate])

  useEffect(() => {
    const canvas = gl.domElement
    canvas.addEventListener('webglcontextlost', onUnavailable)
    return () => canvas.removeEventListener('webglcontextlost', onUnavailable)
  }, [gl, onUnavailable])

  useFrame(() => {
    if (!signalled.current) {
      signalled.current = true
      onReady()
    }
  })

  useGSAP(() => {
    if (!city.current) return
    const timeline = gsap.timeline({ paused: true, onUpdate: invalidate })
    timeline.to(city.current.position, { y: compact ? 0.12 : 0.22, duration: 2.7, ease: 'sine.inOut', yoyo: true, repeat: -1 }, 0)
    rings.current.forEach((ring, index) => {
      if (!ring) return
      timeline.to(ring.scale, { x: 1.58, y: 1.58, duration: 1.55, ease: 'sine.inOut', yoyo: true, repeat: -1 }, index * 0.33)
    })
    animation.current = timeline
    return () => { animation.current = null }
  }, { dependencies: [compact, invalidate], revertOnUpdate: true })

  useEffect(() => {
    animation.current?.paused(!animate)
    invalidate()
  }, [animate, compact, invalidate])

  return (
    <>
      <hemisphereLight args={['#f9f1e9', '#342e2b', 2.15]} />
      <directionalLight position={[2, 11, 6]} color="#fff8ef" intensity={2.3} />
      <directionalLight position={[-8, 6, -6]} color="#bd6538" intensity={0.72} />
      <group ref={city}>
        <InstanceBatch items={model.surfaces} kind="surface" />
        <InstanceBatch items={model.lights} kind="light" />
        <InstanceBatch items={model.trees} kind="tree" />
        {sceneIssues.map((issue, index) => (
          <IssueMarker key={issue.icon} issue={issue} onRing={(ring) => { rings.current[index] = ring }} />
        ))}
      </group>
    </>
  )
}

export default function SmartCityScene(props: SmartCitySceneProps) {
  return (
    <Canvas className="city-canvas" orthographic frameloop="demand" dpr={props.compact ? 1 : [1, 1.5]}
      camera={{ near: 0.1, far: 80, position: [16, 13.3, 18] }} gl={{ alpha: true, antialias: true }}>
      <CityWorld {...props} />
    </Canvas>
  )
}
