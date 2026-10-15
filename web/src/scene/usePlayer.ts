// 实时（SSE）与回放（0.5× / 1× / 2× / 逐步）共用的播放器
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, streamRun, type AgentMsg } from '../api'
import { emptyState, reduceScene, type SceneState } from './CouncilScene'

export type RunData = {
  id: number; chain: string; status: string; engine: string; subject?: string; text?: string; media?: string[]
  agents: Record<string, { name: string; role: string; color: string }>; messages: AgentMsg[]
}

export const SEATS: Record<string, string[]> = {
  inspect: ['aibao', 'xingbao', 'humiao', 'mingli', 'xiaobu'],
  parent: ['aibao', 'weishi'],
  council: ['aibao', 'xiaoyi', 'xiaoshi', 'xiaojia', 'xiaodun'],
}

export function usePlayer(runId: number | null) {
  const [run, setRun] = useState<RunData | null>(null)
  const [all, setAll] = useState<AgentMsg[]>([])
  const [idx, setIdx] = useState(0) // 已播放条数
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [live, setLive] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (!runId) return
    let stop: (() => void) | null = null
    setRun(null); setAll([]); setIdx(0); setPlaying(true)
    api<RunData>(`/runs/${runId}`).then((r) => {
      setRun(r)
      if (r.status === 'running') {
        setLive(true)
        setAll([])
        stop = streamRun(runId, (m) => setAll((x) => (x.some((y) => y.id === m.id) ? x : [...x, m])), () => {
          setLive(false)
          api<RunData>(`/runs/${runId}`).then((rr) => setRun(rr))
        })
      } else {
        setLive(false)
        setAll(r.messages)
      }
    })
    return () => { stop?.() }
  }, [runId])

  // 推进：每条消息停留时长与文字长度、倍速相关
  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current)
    if (!playing || idx >= all.length) return
    const cur = all[idx - 1]
    const base = !cur ? 300 : cur.action === 'think' ? 650 : 900 + Math.min(cur.text.length, 120) * 32
    timer.current = window.setTimeout(() => setIdx((i) => Math.min(all.length, i + 1)), base / speed)
    return () => { if (timer.current) window.clearTimeout(timer.current) }
  }, [playing, idx, all, speed])

  const shown = useMemo(() => all.slice(0, idx), [all, idx])
  const state: SceneState = useMemo(() => shown.reduce(reduceScene, emptyState()), [shown])
  const step = useCallback(() => { setPlaying(false); setIdx((i) => Math.min(all.length, i + 1)) }, [all.length])
  const restart = useCallback(() => { setIdx(0); setPlaying(true) }, [])
  const done = !live && idx >= all.length && all.length > 0
  return { run, all, shown, state, idx, setIdx, playing, setPlaying, speed, setSpeed, step, restart, live, done }
}
