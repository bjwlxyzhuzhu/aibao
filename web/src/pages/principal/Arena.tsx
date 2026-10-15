import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, fileUrl } from '../../api'
import ChatFlow from '../../components/ChatFlow'
import { IPause, IPlay, IStep } from '../../components/icons'
import { Badge, Card, Modal, Spinner, cx, fmtTime } from '../../components/ui'
import { CouncilScene, webglOK } from '../../scene/CouncilScene'
import { SEATS, usePlayer } from '../../scene/usePlayer'
import { avatarUrl, useApp } from '../../store'
import { ChunkList } from './Inspect'

export function ArenaPlayer({ runId, height = 560, showFlow = true }: { runId: number; height?: number; showFlow?: boolean }) {
  const p = usePlayer(runId)
  const { avatars } = useApp()
  const [director, setDirector] = useState(true)
  const [chunk, setChunk] = useState<any>(null)
  const [gl] = useState(webglOK())
  const openChunk = (id: number) => api(`/chunks/${id}`).then(setChunk)
  if (!p.run) return <div className="flex items-center justify-center text-ink-3" style={{ height }}><Spinner /> 加载对抗过程…</div>
  const seats = SEATS[p.run.chain] || SEATS.inspect
  const avatarFor = (a: string, e: string) => {
    const imgs = avatars?.images?.[a]
    if ((e === 'sleep' || !e) && imgs?.front && (a === 'aibao' || a === 'xingbao')) return imgs.front
    return avatarUrl(avatars, a, e)
  }
  const progress = p.all.length ? p.idx / p.all.length : 0
  return (
    <div className={cx('grid gap-4', showFlow && 'xl:grid-cols-[1fr_360px]')}>
      <div className="overflow-hidden rounded-3xl bg-[#F6EDE3] shadow-card ring-1 ring-[#EFE0D2]">
        <div className="relative" style={{ height }}>
          {gl ? (
            <Suspense fallback={<div className="flex h-full items-center justify-center"><Spinner /></div>}>
              <CouncilScene seats={seats} agents={p.run.agents} avatarFor={avatarFor} state={p.state} director={director} speed={p.speed}
                subject={p.run.subject || ''} chain={p.run.chain} media={p.run.media?.[0] ? fileUrl(p.run.media[0]) : undefined} />
            </Suspense>
          ) : (
            <div className="h-full overflow-auto p-4"><ChatFlow messages={p.shown} agents={p.run.agents} onChunk={openChunk} /></div>
          )}
          <div className="absolute left-4 top-4 flex flex-wrap gap-2">
            {p.live && <Badge tone="red">● 实时</Badge>}
            <Badge tone={p.run.engine === 'llm' ? 'blue' : 'gray'}>{p.run.engine === 'llm' ? '通义千问' : '离线规则引擎'}</Badge>
            <Badge tone="gray">{{ inspect: '① 保教巡查链', parent: '② 家园沟通链', council: '③ 园务议事链' }[p.run.chain] || p.run.chain}</Badge>
          </div>
          <div className="absolute right-4 top-4 hidden gap-3 rounded-full bg-white/80 px-3 py-1 text-xs md:flex">
            <span className="flex items-center gap-1"><i className="h-2 w-4 rounded bg-[#F07A2A]" />质询</span>
            <span className="flex items-center gap-1"><i className="h-2 w-4 rounded bg-[#3FB45A]" />支持</span>
            <span className="flex items-center gap-1"><i className="h-2 w-4 rounded bg-[#E9B53B]" />引用条款</span>
          </div>
        </div>
        {/* 回放控制条（与设计稿"讨论回放"一致） */}
        <div className="flex flex-wrap items-center gap-4 border-t border-[#EFE0D2] bg-white/80 px-5 py-3">
          <div className="font-bold">{p.live ? '实时对抗' : '讨论回放'}</div>
          <button onClick={() => (p.done ? p.restart() : p.setPlaying(!p.playing))}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-terra-500 text-white shadow-pill" aria-label="播放/暂停">
            {p.playing && !p.done ? <IPause /> : <IPlay />}
          </button>
          <button onClick={p.step} className="rounded-full p-2 text-ink-2 hover:bg-cream-2" title="逐步前进"><IStep /></button>
          <div className="text-sm tabular-nums text-ink-2">{p.idx} / {p.all.length}</div>
          <div className="relative h-2 min-w-[160px] flex-1 cursor-pointer rounded-full bg-cream-2"
            onClick={(e) => { const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect(); p.setIdx(Math.round(((e.clientX - r.left) / r.width) * p.all.length)) }}>
            <div className="h-full rounded-full bg-terra-400" style={{ width: `${progress * 100}%` }} />
            {[1, 2, 3].map((r) => {
              const first = p.all.findIndex((m) => m.round === r)
              if (first < 0) return null
              return <span key={r} className="absolute -top-5 -translate-x-1/2 text-[10px] text-ink-3" style={{ left: `${(first / p.all.length) * 100}%` }}>
                {p.run!.chain === 'council' ? ['陈述', '交叉质询', '综合'][r - 1] : ['陈述', '质询答辩', '整改'][r - 1]}</span>
            })}
          </div>
          <div className="flex rounded-full bg-cream-2 p-1 text-sm">
            {[0.5, 1, 2].map((s) => <button key={s} onClick={() => p.setSpeed(s)} className={cx('rounded-full px-2.5 py-0.5', p.speed === s && 'bg-white font-bold shadow')}>{s}×</button>)}
          </div>
          {gl && <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={director} onChange={(e) => setDirector(e.target.checked)} />导演镜头</label>}
        </div>
      </div>
      {showFlow && (
        <Card className="max-h-[680px] overflow-auto p-4">
          <div className="mb-3 font-bold">发言记录</div>
          <ChatFlow messages={p.shown} agents={p.run.agents} compact onChunk={openChunk} />
        </Card>
      )}
      <Modal open={!!chunk} onClose={() => setChunk(null)} title="引用条款原文">{chunk && <ChunkList chunks={[chunk]} />}</Modal>
    </div>
  )
}

export default function Arena() {
  const [sp, setSp] = useSearchParams()
  const [runs, setRuns] = useState<any[]>([])
  const runId = Number(sp.get('run')) || null
  useEffect(() => {
    api('/runs?limit=60').then((r: any[]) => {
      const rs = r.filter((x) => ['inspect', 'parent', 'council'].includes(x.chain))
      setRuns(rs)
      if (!runId && rs.length) setSp({ run: String(rs[0].id) }, { replace: true })
    })
  }, [])
  return (
    <div className="mx-auto max-w-[1400px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-4xl font-black">3D 对抗回放</h1>
          <div className="mt-1 text-ink-2">任选一次巡查、家长问答或议事，在议事桌里实时观看或回放对抗过程</div>
        </div>
        <select value={runId || ''} onChange={(e) => setSp({ run: e.target.value })} className="h-10 max-w-full rounded-full border border-[#E9DCD0] bg-white px-4 text-sm">
          {runs.map((r) => <option key={r.id} value={r.id}>#{r.id} · {{ inspect: '巡查', parent: '家园', council: '议事' }[r.chain as string]} · {r.title} · {fmtTime(r.started_at)}</option>)}
        </select>
      </div>
      <div className="mt-5">{runId ? <ArenaPlayer key={runId} runId={runId} /> : <Spinner />}</div>
    </div>
  )
}
