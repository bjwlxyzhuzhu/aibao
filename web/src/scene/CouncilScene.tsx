// 3D 议事桌：暖色木质圆桌 + 纸片人角色（Billboard）+ 发言气泡 + 关系光束 + 裁定特效 + 置信度环 + 导演镜头
import { Billboard, Html, OrbitControls, QuadraticBezierLine, RoundedBox } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { AgentMsg } from '../api'

export type SceneState = {
  speaking: string | null
  thinking: Set<string>
  emotions: Record<string, string>
  bubble: { agent: string; text: string; action: string } | null
  beam: { from: string; to: string; kind: 'challenge' | 'support' | 'cite' } | null
  verdicts: { id: string; result: string; label: string }[]
  confidence: number | null
  redShield: boolean
}

export const emptyState = (): SceneState => ({ speaking: null, thinking: new Set(), emotions: {}, bubble: null, beam: null, verdicts: [], confidence: null, redShield: false })

// 由一条消息推进场景状态（PRD 6.3 状态 → 表情 → 动作）
export function reduceScene(s: SceneState, m: AgentMsg): SceneState {
  const n: SceneState = { ...s, thinking: new Set(s.thinking), emotions: { ...s.emotions }, verdicts: [...s.verdicts] }
  if (m.action === 'think') {
    n.thinking.add(m.agent)
    n.emotions[m.agent] = 'doubt'
    return n
  }
  n.thinking.delete(m.agent)
  n.speaking = m.agent
  n.emotions[m.agent] = m.emotion || 'cheer'
  n.bubble = { agent: m.agent, text: m.text, action: m.action }
  n.beam = null
  n.redShield = false
  if (m.action === 'challenge' && m.target) {
    n.beam = { from: m.agent, to: m.target, kind: 'challenge' }
    n.emotions[m.target] = n.emotions[m.target] === 'sad' ? 'sad' : n.emotions[m.target]
  } else if (m.action === 'support' && m.target) {
    n.beam = { from: m.agent, to: m.target, kind: 'support' }
    if (m.text.startsWith('撤回')) n.emotions[m.agent] = 'sad'
  } else if (m.action === 'verdict') {
    n.beam = { from: '__book', to: m.agent, kind: 'cite' }
    n.confidence = m.confidence
    const r = m.content?.result || 'needs_review'
    n.verdicts.push({ id: `${m.id}`, result: r, label: (m.finding_id || '') + ' ' + (m.content?.result === 'valid' ? '成立' : m.content?.result === 'invalid' ? '不成立' : '转园长') })
    if (m.target && r === 'invalid') n.emotions[m.target] = 'sad'
  } else if (m.action === 'redteam') {
    n.beam = { from: m.agent, to: m.target || 'aibao', kind: m.content?.risk_level === 'low' ? 'support' : 'challenge' }
    n.redShield = m.content?.risk_level === 'high'
  }
  return n
}

const BEAM_COLOR = { challenge: '#F07A2A', support: '#3FB45A', cite: '#E9B53B' }

function useTex(url: string) {
  const [tex, setTex] = useState<THREE.Texture | null>(null)
  useEffect(() => {
    let alive = true
    new THREE.TextureLoader().load(url, (t) => {
      if (!alive) return
      t.colorSpace = THREE.SRGBColorSpace
      t.anisotropy = 4
      setTex(t)
    })
    return () => { alive = false }
  }, [url])
  return tex
}

function seatPos(i: number, n: number, r = 3.1): [number, number, number] {
  const a = Math.PI / 2 + (i / n) * Math.PI * 2 + (n === 2 ? Math.PI / 2 : 0)
  return [Math.cos(a) * r, 0, Math.sin(a) * r]
}

function Agent({ id, name, role, color, url, pos, speaking, thinking, isJudge, confidence, threshold, shield }: {
  id: string; name: string; role: string; color: string; url: string; pos: [number, number, number]; speaking: boolean; thinking: boolean
  isJudge: boolean; confidence: number | null; threshold: number; shield: boolean
}) {
  const tex = useTex(url)
  const g = useRef<THREE.Group>(null)
  const halo = useRef<THREE.Mesh>(null)
  const t0 = useMemo(() => Math.random() * 10, [])
  useFrame(({ clock }) => {
    const t = clock.elapsedTime + t0
    if (!g.current) return
    const breathe = Math.sin(t * 1.6) * 0.03
    const bounce = speaking ? Math.abs(Math.sin(t * 6)) * 0.18 : 0
    g.current.position.y = 1.15 + breathe + bounce
    g.current.scale.setScalar(1 + (speaking ? 0.06 : 0) + breathe * 0.4)
    if (halo.current) {
      const m = halo.current.material as THREE.MeshBasicMaterial
      m.opacity = speaking ? 0.55 + Math.sin(t * 5) * 0.25 : 0
    }
  })
  const aspect = tex?.image ? (tex.image as HTMLImageElement).width / (tex.image as HTMLImageElement).height : 1
  const h = 1.45
  const low = confidence != null && confidence < threshold
  return (
    <group position={pos}>
      {/* 椅子 */}
      <mesh position={[0, 0.28, 0]} castShadow>
        <cylinderGeometry args={[0.48, 0.52, 0.56, 28]} />
        <meshStandardMaterial color="#E9CDB2" roughness={0.8} />
      </mesh>
      {/* 发言光圈 */}
      <mesh ref={halo} position={[0, 0.58, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.55, 0.78, 48]} />
        <meshBasicMaterial color={color} transparent opacity={0} side={THREE.DoubleSide} />
      </mesh>
      {/* 置信度环（裁判脚下） */}
      {isJudge && confidence != null && (
        <ConfRing value={confidence} low={low} />
      )}
      <Billboard>
        <group ref={g}>
          <mesh>
            <planeGeometry args={[h * aspect, h]} />
            {tex ? <meshBasicMaterial key={tex.uuid} map={tex} transparent alphaTest={0.02} toneMapped={false} side={THREE.DoubleSide} />
              : <meshBasicMaterial color="#ffffff" transparent opacity={0.4} side={THREE.DoubleSide} />}
          </mesh>
          {shield && (
            <mesh position={[0.75, 0.1, 0.05]}>
              <circleGeometry args={[0.32, 6]} />
              <meshBasicMaterial color="#E5483B" transparent opacity={0.9} />
            </mesh>
          )}
        </group>
        <Html position={[0, 0.25, 0]} center distanceFactor={9} zIndexRange={[10, 0]}>
          <div className="pointer-events-none select-none whitespace-nowrap rounded-full bg-white/90 px-2.5 py-0.5 text-center text-[13px] font-bold shadow" style={{ color }}>
            {name}<span className="ml-1 text-[10px] font-normal text-ink-3">{role}</span>
          </div>
        </Html>
        {thinking && (
          <Html position={[0, 2.25, 0]} center distanceFactor={9}>
            <div className="flex gap-1 rounded-full bg-white px-3 py-1.5 shadow">
              {[0, 1, 2].map((i) => <span key={i} className="h-2 w-2 animate-bounce rounded-full bg-terra-400" style={{ animationDelay: `${i * 0.15}s` }} />)}
            </div>
          </Html>
        )}
      </Billboard>
    </group>
  )
}

function ConfRing({ value, low }: { value: number; low: boolean }) {
  const ref = useRef<THREE.Mesh>(null)
  useFrame(({ clock }) => {
    if (ref.current && low) (ref.current.material as THREE.MeshBasicMaterial).opacity = 0.5 + Math.sin(clock.elapsedTime * 8) * 0.4
  })
  return (
    <group position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh><ringGeometry args={[0.85, 1.0, 64]} /><meshBasicMaterial color="#000" transparent opacity={0.08} /></mesh>
      <mesh ref={ref}><ringGeometry args={[0.85, 1.0, 64, 1, Math.PI / 2, Math.PI * 2 * value]} /><meshBasicMaterial color={low ? '#F2A516' : '#3FB45A'} transparent opacity={0.95} /></mesh>
    </group>
  )
}

function Beam({ from, to, kind }: { from: THREE.Vector3; to: THREE.Vector3; kind: 'challenge' | 'support' | 'cite' }) {
  const ref = useRef<any>(null)
  useFrame((_, dt) => { if (ref.current?.material) ref.current.material.dashOffset -= dt * 2.4 })
  const mid = from.clone().add(to).multiplyScalar(0.5).add(new THREE.Vector3(0, 1.6, 0))
  return <QuadraticBezierLine ref={ref} start={from} end={to} mid={mid} color={BEAM_COLOR[kind]} lineWidth={5} dashed dashScale={6} dashSize={0.6} gapSize={0.25} />
}

function Ripple({ trigger }: { trigger: number }) {
  const ref = useRef<THREE.Mesh>(null)
  const start = useRef(0)
  useEffect(() => { start.current = performance.now() }, [trigger])
  useFrame(() => {
    if (!ref.current) return
    const t = (performance.now() - start.current) / 1400
    const s = 0.2 + t * 2.4
    ref.current.scale.set(s, s, s)
    ;(ref.current.material as THREE.MeshBasicMaterial).opacity = trigger ? Math.max(0, 0.6 - t * 0.6) : 0
  })
  return (
    <mesh ref={ref} position={[0, 0.83, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[0.9, 1, 64]} />
      <meshBasicMaterial color="#E9B53B" transparent opacity={0} />
    </mesh>
  )
}

const TRAYS: Record<string, { pos: [number, number, number]; label: string; color: string }> = {
  valid: { pos: [-1.05, 0.88, -0.55], label: '成立', color: '#D9483B' },
  invalid: { pos: [1.05, 0.88, -0.55], label: '不成立', color: '#2F7BE0' },
  needs_review: { pos: [4.7, 0.6, -1.4], label: '转园长', color: '#F2A516' },
}

function VerdictCard({ result, index, label }: { result: string; index: number; label: string }) {
  const ref = useRef<THREE.Group>(null)
  const t0 = useRef(performance.now())
  const tray = TRAYS[result] || TRAYS.needs_review
  const target = new THREE.Vector3(tray.pos[0], tray.pos[1] + 0.06 + index * 0.05, tray.pos[2])
  useFrame(() => {
    if (!ref.current) return
    const t = Math.min(1, (performance.now() - t0.current) / 1300)
    const e = 1 - Math.pow(1 - t, 3)
    const p = new THREE.Vector3(0, 2.2, 0).lerp(target, e)
    p.y += Math.sin(e * Math.PI) * 1.2
    ref.current.position.copy(p)
    ref.current.rotation.z = (1 - e) * Math.PI * 2
  })
  return (
    <group ref={ref}>
      <RoundedBox args={[0.55, 0.04, 0.38]} radius={0.02}>
        <meshStandardMaterial color={tray.color} />
      </RoundedBox>
    </group>
  )
}

function Table({ subject, media, trays }: { subject: string; media?: string; trays: boolean }) {
  const card = useRef<THREE.Group>(null)
  useFrame(({ clock }) => { if (card.current) card.current.position.y = 2.25 + Math.sin(clock.elapsedTime * 1.2) * 0.08 })
  return (
    <group>
      {/* 地面：幼儿园绿色调 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[9, 64]} />
        <meshStandardMaterial color="#A9BE97" roughness={1} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 0]}>
        <ringGeometry args={[5.2, 5.5, 64]} />
        <meshStandardMaterial color="#93AB80" />
      </mesh>
      {/* 木质圆桌 */}
      <mesh position={[0, 0.8, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[2.25, 2.25, 0.12, 64]} />
        <meshStandardMaterial color="#C98B57" roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.81, 0]}>
        <cylinderGeometry args={[1.9, 1.9, 0.122, 64]} />
        <meshStandardMaterial color="#D59A66" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.4, 0]}>
        <cylinderGeometry args={[0.25, 0.45, 0.8, 24]} />
        <meshStandardMaterial color="#A86F44" />
      </mesh>
      {/* 桌心条款书 */}
      <group position={[0, 0.95, 0]} rotation={[0, 0.5, 0]}>
        <RoundedBox args={[0.7, 0.14, 0.5]} radius={0.03}><meshStandardMaterial color="#5E8D63" /></RoundedBox>
        <mesh position={[0, 0.075, 0]}><boxGeometry args={[0.64, 0.02, 0.46]} /><meshStandardMaterial color="#FFF8EA" /></mesh>
      </group>
      {/* 托盘 */}
      {Object.entries(TRAYS).filter(([k]) => trays || k === 'needs_review').map(([k, t]) => (
        <group key={k} position={t.pos}>
          {k === 'needs_review' ? (
            <group>
              <mesh position={[0, -0.32, 0]}><cylinderGeometry args={[0.6, 0.65, 0.56, 28]} /><meshStandardMaterial color="#F3D9A4" /></mesh>
              <Html position={[0, 0.9, 0]} center distanceFactor={9}><div className="whitespace-nowrap rounded-full bg-[#FFF2DB] px-3 py-1 text-xs font-bold text-[#A86400] shadow">园长座位 · 人在回路</div></Html>
            </group>
          ) : (
            <>
              <mesh><cylinderGeometry args={[0.42, 0.38, 0.05, 32]} /><meshStandardMaterial color="#FFF6EC" /></mesh>
              <Html position={[0, 0.1, 0.42]} center distanceFactor={9}><div className="whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-bold text-white" style={{ background: t.color }}>{t.label}</div></Html>
            </>
          )}
        </group>
      ))}
      {/* 悬浮议题卡 */}
      <group ref={card} position={[0, 2.25, 0]}>
        <Html center distanceFactor={8} transform={false} zIndexRange={[5, 0]}>
          <div className="pointer-events-none w-[230px] rounded-2xl bg-white/95 p-3 shadow-xl ring-1 ring-terra-100">
            <div className="text-[11px] font-semibold text-terra-500">◎ 议题 · 对抗进行中</div>
            {media && <img src={media} className="mt-1.5 h-20 w-full rounded-lg object-cover" alt="已打码" />}
            <div className="mt-1 text-[15px] font-bold leading-snug text-ink">{subject}</div>
          </div>
        </Html>
      </group>
    </group>
  )
}

function Director({ target, enabled }: { target: THREE.Vector3 | null; enabled: boolean }) {
  const { camera } = useThree()
  const home = useMemo(() => new THREE.Vector3(0, 7.4, 10.2), [])
  useFrame(() => {
    if (!enabled) return
    const goal = target ? target.clone().multiplyScalar(0.3).add(new THREE.Vector3(0, 6.4, 9.2)) : home
    camera.position.lerp(goal, 0.03)
    camera.lookAt(0, 1.2, 0)
  })
  return null
}

function Bubble({ pos, text: full, color, speed }: { pos: THREE.Vector3; text: string; color: string; speed: number }) {
  // 3D 气泡只显示前 80 字，完整发言在右侧记录里
  const text = full.length > 80 ? full.slice(0, 78) + '…' : full
  const [shown, setShown] = useState('')
  useEffect(() => {
    setShown('')
    let i = 0
    const step = Math.max(8, 28 / speed)
    const t = setInterval(() => { i += 1; setShown(text.slice(0, i)); if (i >= text.length) clearInterval(t) }, step)
    return () => clearInterval(t)
  }, [text, speed])
  return (
    <Html position={[pos.x, 3.15, pos.z]} center distanceFactor={9} zIndexRange={[20, 10]}>
      <div className="pointer-events-none relative w-[250px] rounded-2xl bg-white p-3 text-[13px] leading-5 text-ink shadow-xl" style={{ borderTop: `3px solid ${color}` }}>
        {shown}<span className="animate-pulse">{shown.length < text.length ? '▍' : ''}</span>
        <div className="absolute -bottom-2 left-1/2 h-4 w-4 -translate-x-1/2 rotate-45 bg-white" />
      </div>
    </Html>
  )
}

export function CouncilScene({ seats, agents, avatarFor, state, subject, media, director, speed, threshold = 0.7, chain = 'inspect' }: {
  seats: string[]
  agents: Record<string, { name: string; role: string; color: string }>
  avatarFor: (agent: string, emotion: string) => string
  state: SceneState
  subject: string
  media?: string
  director: boolean
  speed: number
  threshold?: number
  chain?: string
}) {
  const positions = useMemo(() => {
    const m: Record<string, THREE.Vector3> = { __book: new THREE.Vector3(0, 1.0, 0) }
    seats.forEach((a, i) => { m[a] = new THREE.Vector3(...seatPos(i, seats.length)).setY(1.3) })
    return m
  }, [seats])
  const speakerPos = state.speaking ? positions[state.speaking] : null
  const [ripple, setRipple] = useState(0)
  useEffect(() => { if (state.verdicts.length) setRipple(state.verdicts.length) }, [state.verdicts.length])
  return (
    <Canvas shadows camera={{ position: [0, 7.4, 10.2], fov: 42 }} dpr={[1, 2]} gl={{ antialias: true }}>
      <color attach="background" args={['#F6EDE3']} />
      <fog attach="fog" args={['#F6EDE3', 16, 30]} />
      <ambientLight intensity={0.85} />
      <directionalLight position={[5, 10, 6]} intensity={1.3} castShadow shadow-mapSize={[1024, 1024]} />
      <hemisphereLight args={['#FFF4E6', '#9CB487', 0.5]} />
      <Table subject={subject} media={media} trays={chain === 'inspect'} />
      {seats.map((a, i) => (
        <Agent key={a} id={a} name={agents[a]?.name || a} role={(agents[a]?.role || '').split(' ')[0]} color={agents[a]?.color || '#D46A47'}
          url={avatarFor(a, state.emotions[a] || 'sleep')} pos={seatPos(i, seats.length)} speaking={state.speaking === a}
          thinking={state.thinking.has(a)} isJudge={a === 'mingli'} confidence={a === 'mingli' ? state.confidence : null} threshold={threshold}
          shield={a === 'weishi' && state.redShield} />
      ))}
      {state.beam && positions[state.beam.from] && positions[state.beam.to] && (
        <Beam key={`${state.beam.from}-${state.beam.to}-${state.bubble?.text}`} from={positions[state.beam.from]} to={positions[state.beam.to]} kind={state.beam.kind} />
      )}
      {state.bubble && positions[state.bubble.agent] && (
        <Bubble pos={positions[state.bubble.agent]} text={state.bubble.text} color={agents[state.bubble.agent]?.color || '#D46A47'} speed={speed} />
      )}
      {state.verdicts.map((v, i) => <VerdictCard key={v.id} result={v.result} label={v.label} index={state.verdicts.slice(0, i).filter((x) => x.result === v.result).length} />)}
      <Ripple trigger={ripple} />
      <Director target={speakerPos} enabled={director} />
      {!director && <OrbitControls target={[0, 1.2, 0]} maxPolarAngle={Math.PI / 2.15} minDistance={6} maxDistance={18} />}
    </Canvas>
  )
}

export function webglOK(): boolean {
  try {
    const c = document.createElement('canvas')
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')))
  } catch { return false }
}
