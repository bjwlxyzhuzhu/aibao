// 实践教学：学生端（手机）提交保教实践记录、看对抗评价与五维评分、写反思、看成长档案；
// 导师端（高校导师桌面 / 园所导师手机）评阅：问题条目确认、五维评分调整、评语；成效数据导出。
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { api, fileUrl, getToken, streamRun, upload, type AgentMsg } from '../../api'
import ChatFlow from '../../components/ChatFlow'
import { Brand } from '../../components/Layout'
import { ICamera, IChevron, IClip, IFile, ISend, IX } from '../../components/icons'
import { SEGMENTS, SegIcon } from '../../components/segments'
import { Badge, Button, Card, Empty, Modal, SEV_TONE, Spinner, Tabs, VerdictBadge, cx, fmtTime, useToast } from '../../components/ui'
import { useApp } from '../../store'
import { ChunkList } from '../principal/Inspect'
import { compress } from '../staff/Staff'

const DIMS = ['一日生活', '环境创设', '游戏支持', '激励评价', '反思发展']
const DIM_FULL: Record<string, string> = { 一日生活: '一日生活的组织与保育', 环境创设: '环境的创设与利用', 游戏支持: '游戏活动的支持与引导', 激励评价: '激励与评价', 反思发展: '反思与发展' }
const DIM_COLOR = ['#D46A47', '#3E9B5B', '#2F7BE0', '#E59A0B', '#8A5CC2']
const SRC_CN: Record<string, string> = { ai: 'AI 草稿', mentor_u: '高校导师', mentor_k: '园所导师' }

// ---------------- 成长曲线（五维周均分） ----------------
export function GrowthChart({ series, height = 220 }: { series: any[]; height?: number }) {
  const W = 560, H = height, pl = 34, pr = 14, pt = 14, pb = 28
  if (!series.length) return <div className="py-8 text-center text-sm text-ink-3">还没有记录</div>
  const xs = (i: number) => pl + (series.length === 1 ? (W - pl - pr) / 2 : (i * (W - pl - pr)) / (series.length - 1))
  const ys = (v: number) => pt + ((5 - v) / 4) * (H - pt - pb)
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {[1, 2, 3, 4, 5].map((v) => (
          <g key={v}><line x1={pl} x2={W - pr} y1={ys(v)} y2={ys(v)} stroke="#EFE3D7" /><text x={pl - 8} y={ys(v) + 4} fontSize="11" textAnchor="end" fill="#958A82">{v}</text></g>
        ))}
        {series.map((s, i) => <text key={i} x={xs(i)} y={H - 8} fontSize="11" textAnchor="middle" fill="#958A82">第{s.week}周</text>)}
        {DIMS.map((d, k) => {
          const pts = series.map((s, i) => (s[d] != null ? `${xs(i)},${ys(s[d])}` : null)).filter(Boolean).join(' ')
          return (
            <g key={d}>
              <polyline points={pts} fill="none" stroke={DIM_COLOR[k]} strokeWidth="2.5" strokeLinejoin="round" />
              {series.map((s, i) => s[d] != null && <circle key={i} cx={xs(i)} cy={ys(s[d])} r="3.5" fill={DIM_COLOR[k]} />)}
            </g>
          )
        })}
      </svg>
      <div className="mt-1 flex flex-wrap justify-center gap-3 text-xs">{DIMS.map((d, k) => <span key={d} className="flex items-center gap-1"><i className="h-2 w-3 rounded" style={{ background: DIM_COLOR[k] }} />{DIM_FULL[d]}</span>)}</div>
    </div>
  )
}

function ScoreDots({ v }: { v: number }) {
  return <span className="inline-flex gap-0.5">{[1, 2, 3, 4, 5].map((i) => <i key={i} className={cx('h-2.5 w-2.5 rounded-full', i <= v ? 'bg-terra-500' : 'bg-cream-3')} />)}</span>
}

// ---------------- 学生端 ----------------
export function StudentShell() {
  const { me, logout } = useApp()
  const [info, setInfo] = useState<any>(null)
  useEffect(() => { api('/practice/me').then(setInfo).catch(() => {}) }, [])
  const tabs = [{ to: '/student', label: '记录', icon: <ICamera />, end: true }, { to: '/student/list', label: '反馈', icon: <IClip /> }, { to: '/student/growth', label: '成长', icon: <IFile /> }]
  return (
    <div className="mx-auto min-h-screen max-w-[520px] bg-cream pb-24">
      <header className="sticky top-0 z-30 flex items-center justify-between bg-cream/95 px-4 pb-2 pt-[max(env(safe-area-inset-top),10px)] backdrop-blur">
        <Brand compact />
        <div className="flex items-center gap-2 text-right text-xs leading-tight">
          <div><div className="text-sm font-bold">{info?.code || me?.name}</div><div className="text-ink-3">{info?.class_name ? `见习：${info.class_name}班` : '见习学生'}</div></div>
          <button onClick={logout} className="rounded-full bg-white px-2 py-1 text-ink-3">退出</button>
        </div>
      </header>
      <Outlet />
      <nav className="fixed bottom-0 left-1/2 z-30 flex w-full max-w-[520px] -translate-x-1/2 justify-around border-t border-[#EFE2D6] bg-white/95 pb-[max(env(safe-area-inset-bottom),6px)] pt-1.5 backdrop-blur">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => cx('flex min-w-[64px] flex-col items-center gap-0.5 rounded-xl px-2 py-1 text-[11px]', isActive ? 'font-bold text-terra-600' : 'text-ink-3')}>{t.icon}{t.label}</NavLink>
        ))}
      </nav>
    </div>
  )
}

export function StudentNew() {
  const [segment, setSegment] = useState('午睡')
  const [text, setText] = useState('')
  const [photos, setPhotos] = useState<{ id: number; url: string; faces: number }[]>([])
  const [busy, setBusy] = useState('')
  const ref = useRef<HTMLInputElement>(null)
  const toast = useToast()
  const nav = useNavigate()
  const add = async (fs: FileList | null) => {
    if (!fs) return
    setBusy('正在本地打码人脸…')
    try {
      for (const f of Array.from(fs).slice(0, 3 - photos.length)) {
        const fd = new FormData(); fd.append('file', await compress(f), 'p.jpg'); fd.append('kind', 'image')
        const r = await upload('/media', fd); setPhotos((p) => [...p, { id: r.id, url: r.preview_url, faces: r.faces }])
      }
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const submit = async () => {
    setBusy('提交中…')
    try {
      const r = await api('/practice/records', { method: 'POST', json: { segment, text, media_ids: photos.map((p) => p.id) } })
      nav(`/student/r/${r.record_id}?run=${r.run_id}`)
    } catch (e: any) { toast(e.message, 'err'); setBusy('') }
  }
  return (
    <div className="space-y-4 px-4 pt-2">
      <div className="flex items-center gap-3 rounded-3xl bg-gradient-to-r from-[#FFF1E6] to-white p-4">
        <img src="/mascot/aibao-mini.png" className="h-16 w-16 object-contain" alt="爱宝" />
        <div><div className="text-lg font-black">今天的保教实践，记下来</div><div className="text-sm text-ink-2">写清你做了什么、幼儿怎么反应、你怎么调整</div></div>
      </div>
      <Card className="p-4">
        <div className="font-bold">① 哪个一日生活环节</div>
        <div className="mt-3 grid grid-cols-4 gap-2">
          {SEGMENTS.map((s) => <button key={s} onClick={() => setSegment(s)} className={cx('flex flex-col items-center gap-1 rounded-2xl py-2.5 text-sm', segment === s ? 'bg-terra-500 text-white shadow-pill' : 'bg-cream text-ink-2')}><SegIcon seg={s} />{s}</button>)}
        </div>
      </Card>
      <Card className="p-4">
        <div className="font-bold">② 实践记录与反思</div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} placeholder="例如：13:00 我负责看午睡，每 15 分钟巡视一次……发现一名幼儿蒙头睡，我轻声提醒并帮他整理被子。反思：……"
          className="mt-3 w-full rounded-2xl border border-[#E9DCD0] bg-white p-3 text-[15px] outline-none focus:border-terra-300" />
        <div className="mt-2 flex gap-2">
          {photos.map((p) => (
            <div key={p.id} className="relative"><img src={fileUrl(p.url)} className="h-20 w-20 rounded-xl object-cover" alt="打码预览" />
              <button onClick={() => setPhotos(photos.filter((x) => x.id !== p.id))} className="absolute right-1 top-1 rounded-full bg-white/90 p-0.5"><IX size={12} /></button></div>
          ))}
          {photos.length < 3 && <button onClick={() => ref.current?.click()} className="flex h-20 w-20 flex-col items-center justify-center rounded-xl border-2 border-dashed border-terra-200 text-xs text-terra-500"><ICamera />环境照片</button>}
        </div>
        <input ref={ref} type="file" accept="image/*" multiple hidden onChange={(e) => add(e.target.files)} />
        <div className="mt-1 text-[11px] text-ink-3">照片中的人脸在服务器上自动模糊；请勿拍摄幼儿正脸</div>
      </Card>
      <Button size="lg" className="w-full" disabled={!!busy || text.trim().length < 10} onClick={submit}>{busy ? <><Spinner />{busy}</> : <>③ 提交，请爱宝智囊团评一评 <ISend /></>}</Button>
    </div>
  )
}

export function StudentList() {
  const [rows, setRows] = useState<any[] | null>(null)
  const nav = useNavigate()
  useEffect(() => { api('/practice/records').then(setRows) }, [])
  if (!rows) return <div className="p-6"><Spinner /></div>
  return (
    <div className="space-y-2 px-4 pt-2">
      <div className="text-lg font-black">我的实践记录</div>
      {!rows.length && <Empty text="还没有提交记录" />}
      {rows.map((r) => (
        <button key={r.id} onClick={() => nav(`/student/r/${r.id}`)} className="flex w-full items-center gap-3 rounded-2xl bg-white p-3 text-left shadow-sm">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cream text-terra-500"><SegIcon seg={r.segment} /></div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">第{r.week_no}周 · {r.segment} · {r.text}</div>
            <div className="text-xs text-ink-3">{fmtTime(r.created_at)}</div>
          </div>
          <div className="flex flex-col items-end gap-1">
            {r.mentor_u_done ? <Badge tone="green">导师已评</Badge> : <Badge tone="amber">待导师评阅</Badge>}
            {!r.reflection && r.status === 'done' && <Badge tone="terra">待反思</Badge>}
          </div>
          <IChevron size={16} className="text-ink-3" />
        </button>
      ))}
    </div>
  )
}

function RecordBody({ d, onChunk }: { d: any; onChunk: (id: number) => void }) {
  return (
    <>
      <Card className="p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="font-bold">五维保教实践能力</div>
          <span className="text-xs text-ink-3">依据《幼儿园教师专业标准（试行）》</span>
        </div>
        <div className="space-y-2.5">
          {DIMS.map((k) => {
            const ai = d.ai_scores[k]; const fin = d.final_scores[k]
            if (!ai && !fin) return null
            return (
              <div key={k} className="rounded-xl bg-cream p-2.5">
                <div className="flex items-center gap-2 text-sm"><b className="flex-1">{DIM_FULL[k]}</b><ScoreDots v={fin?.score ?? ai?.score} /><Badge tone={fin?.source === 'ai' ? 'gray' : 'green'}>{SRC_CN[fin?.source || 'ai']}</Badge></div>
                {ai && <div className="mt-1 text-xs leading-5 text-ink-2">{ai.evidence}{ai.cited?.map((c: number) => <button key={c} onClick={() => onChunk(c)} className="ml-1 rounded-full bg-[#FFF5DC] px-1.5 text-[11px] text-[#A86400]">📖#{c}</button>)}</div>}
              </div>
            )
          })}
        </div>
      </Card>
      {d.suggestions?.length > 0 && <Card className="p-4"><div className="font-bold">改进建议（AI 草稿）</div><ul className="mt-1 list-disc pl-5 text-sm leading-6">{d.suggestions.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></Card>}
      {(d.mentor_u_comment || d.mentor_k_comment) && (
        <Card className="space-y-2 p-4">
          {d.mentor_u_comment && <div className="rounded-xl bg-[#E6F6EA] p-2.5 text-sm"><b className="text-[#0E7A2F]">高校导师：</b>{d.mentor_u_comment}</div>}
          {d.mentor_k_comment && <div className="rounded-xl bg-[#E7F0FC] p-2.5 text-sm"><b className="text-[#2160B8]">园所导师：</b>{d.mentor_k_comment}</div>}
        </Card>
      )}
    </>
  )
}

export function StudentRecord() {
  const { id } = useParams()
  const [d, setD] = useState<any>(null)
  const [msgs, setMsgs] = useState<AgentMsg[]>([])
  const [agents, setAgents] = useState<any>({})
  const [live, setLive] = useState(false)
  const [chunk, setChunk] = useState<any>(null)
  const [refl, setRefl] = useState('')
  const toast = useToast()
  const load = () => api(`/practice/records/${id}`).then((x) => { setD(x); setRefl(x.reflection || ''); return x })
  useEffect(() => {
    let stop = () => {}
    load().then(async (x) => {
      if (!x.run_id) return
      const r = await api(`/runs/${x.run_id}`); setAgents(r.agents)
      if (r.status !== 'running') { setMsgs(r.messages); return }
      setLive(true)
      stop = streamRun(x.run_id, (m) => setMsgs((s) => (s.some((y) => y.id === m.id) ? s : [...s, m])), () => { setLive(false); load() })
    })
    return () => stop()
  }, [id])
  if (!d) return <div className="p-6"><Spinner /></div>
  return (
    <div className="space-y-4 px-4 pt-2">
      <Card className="p-4">
        <div className="flex items-center gap-2"><SegIcon seg={d.segment} /><b>第{d.week_no}周 · {d.segment}</b><span className="ml-auto text-xs text-ink-3">{fmtTime(d.created_at)}</span></div>
        <div className="mt-2 text-sm leading-6 text-ink-2">{d.inspection.text}</div>
      </Card>
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between"><div className="font-bold">智囊团评一评</div>{live ? <Badge tone="amber"><Spinner className="h-3 w-3" /> 进行中</Badge> : <Badge tone="green">已完成</Badge>}</div>
        <ChatFlow messages={msgs} agents={agents} compact onChunk={(c) => api(`/chunks/${c}`).then(setChunk)} />
      </Card>
      {!live && <RecordBody d={d} onChunk={(c) => api(`/chunks/${c}`).then(setChunk)} />}
      {!live && (
        <Card className="p-4">
          <div className="font-bold">我的反思</div>
          <textarea rows={3} value={refl} onChange={(e) => setRefl(e.target.value)} placeholder="看完反馈，我准备怎么改？对评分有不同意见也可以写在这里，导师会看到。" className="mt-2 w-full rounded-2xl border border-[#E9DCD0] p-3 text-sm" />
          <Button className="mt-2 w-full" onClick={async () => { await api(`/practice/records/${id}/reflection`, { method: 'POST', json: { text: refl } }); toast('反思已保存'); load() }}>保存反思</Button>
        </Card>
      )}
      <Modal open={!!chunk} onClose={() => setChunk(null)} title="引用条款原文">{chunk && <ChunkList chunks={[chunk]} />}</Modal>
    </div>
  )
}

export function StudentGrowth() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api('/practice/me').then(setD) }, [])
  if (!d) return <div className="p-6"><Spinner /></div>
  const g = d.growth
  return (
    <div className="space-y-4 px-4 pt-2">
      <div className="text-lg font-black">我的成长档案</div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Card className="p-3"><div className="text-2xl font-black">{g.records}</div><div className="text-xs text-ink-3">实践记录</div></Card>
        <Card className="p-3"><div className="text-2xl font-black">{g.reflections}</div><div className="text-xs text-ink-3">完成反思</div></Card>
        <Card className="p-3"><div className="text-2xl font-black">{g.recent_avg ?? '—'}</div><div className="text-xs text-ink-3">近两周均分</div></Card>
      </div>
      <Card className="p-4"><div className="mb-2 font-bold">五维周均分变化</div><GrowthChart series={g.series} /></Card>
      {g.value_added && (
        <Card className="p-4">
          <div className="font-bold">增值（近两周 − 起始两周）</div>
          <div className="mt-2 space-y-1.5">{DIMS.map((k) => <div key={k} className="flex justify-between text-sm"><span>{DIM_FULL[k]}</span><b className={g.value_added[k] >= 0 ? 'text-[#0E7A2F]' : 'text-[#B83227]'}>{g.value_added[k] >= 0 ? '+' : ''}{g.value_added[k].toFixed(2)}</b></div>)}</div>
        </Card>
      )}
    </div>
  )
}

// ---------------- 导师端 ----------------
export function MentorOverview() {
  const [rows, setRows] = useState<any[] | null>(null)
  const nav = useNavigate()
  useEffect(() => { api('/practice/students').then(setRows) }, [])
  return (
    <div className="mx-auto max-w-[1200px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
      <h1 className="text-4xl font-black">见习学生总览</h1>
      <div className="mt-1 text-ink-2">每位学生的五维保教实践能力变化 · 待评阅记录 · 增值</div>
      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {!rows ? <Spinner /> : rows.map((s) => (
          <Card key={s.id} className="cursor-pointer p-4 transition hover:-translate-y-0.5" onClick={() => nav(`/mentor/review?student=${s.id}`)}>
            <div className="flex items-center gap-2"><b className="text-lg">{s.code}</b><span className="text-xs text-ink-3">见习 {s.class_name}班</span>{s.is_demo && <Badge tone="gray">演示</Badge>}
              {s.pending > 0 && <Badge tone="amber" className="ml-auto">待评 {s.pending}</Badge>}</div>
            <GrowthChart series={s.series} height={150} />
            <div className="mt-1 flex justify-between text-xs text-ink-2"><span>{s.records} 条记录</span><span>起始 {s.start_avg ?? '—'} → 近期 {s.recent_avg ?? '—'}</span></div>
          </Card>
        ))}
      </div>
    </div>
  )
}

export function MentorReview({ mobile }: { mobile?: boolean }) {
  const qs = new URLSearchParams(location.search)
  const [rows, setRows] = useState<any[] | null>(null)
  const [sel, setSel] = useState<number | null>(null)
  const [d, setD] = useState<any>(null)
  const [msgs, setMsgs] = useState<AgentMsg[]>([])
  const [agents, setAgents] = useState<any>({})
  const [scores, setScores] = useState<Record<string, number>>({})
  const [fdec, setFdec] = useState<Record<number, string>>({})
  const [comment, setComment] = useState('')
  const [chunk, setChunk] = useState<any>(null)
  const [filter, setFilter] = useState<'pending' | 'all'>('pending')
  const toast = useToast()
  const loadList = () => api(`/practice/records${qs.get('student') ? `?student_id=${qs.get('student')}` : ''}`).then((r) => { setRows(r); return r })
  useEffect(() => { loadList() }, [])
  useEffect(() => {
    if (!sel) return
    api(`/practice/records/${sel}`).then(async (x) => {
      setD(x)
      const mine = x.mentor_kind
      const fin = x.final_scores
      setScores(Object.fromEntries(DIMS.map((k) => [k, (fin[k]?.source === mine ? fin[k].score : x.ai_scores[k]?.score) ?? 3])))
      setFdec(Object.fromEntries(x.inspection.findings.map((f: any) => [f.id, f.review?.decision || (f.final_verdict === 'invalid' ? 'invalid' : 'valid')])))
      setComment(mine === 'mentor_u' ? x.mentor_u_comment : x.mentor_k_comment)
      if (x.run_id) { const r = await api(`/runs/${x.run_id}`); setMsgs(r.messages); setAgents(r.agents) }
    })
  }, [sel])
  const shown = (rows || []).filter((r) => filter === 'all' || !(d?.mentor_kind === 'mentor_k' ? r.mentor_k_done : r.mentor_u_done))
  const submit = async () => {
    const r = await api(`/practice/records/${sel}/review`, { method: 'POST', json: { scores, comment, findings: fdec } })
    toast(`已提交（${SRC_CN[r.as]}评阅）`)
    const list = await loadList()
    const next = list.find((x: any) => x.id !== sel && !(r.as === 'mentor_k' ? x.mentor_k_done : x.mentor_u_done))
    if (next) setSel(next.id)
  }
  return (
    <div className={cx(mobile ? 'space-y-3 px-4 pt-2' : 'mx-auto max-w-[1400px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10')}>
      {!mobile && <><h1 className="text-4xl font-black">记录评阅</h1><div className="mt-1 text-ink-2">AI 只给草稿：确认问题条目、调整五维评分、写评语，以导师评阅为最终结果</div></>}
      {mobile && <div className="text-lg font-black">见习学生记录评阅（园所导师）</div>}
      <div className={cx('grid gap-4', !mobile && 'mt-5 lg:grid-cols-[340px_1fr]')}>
        <Card className={cx('p-3', mobile && !!sel && 'hidden')}>
          <Tabs value={filter} onChange={setFilter} items={[{ value: 'pending', label: '待评阅' }, { value: 'all', label: '全部' }]} />
          <div className="mt-2 max-h-[70vh] space-y-1 overflow-auto">
            {!rows ? <Spinner /> : shown.length === 0 ? <Empty text="都评完了" emotion="happy" /> : shown.map((r) => (
              <button key={r.id} onClick={() => setSel(r.id)} className={cx('w-full rounded-xl p-2.5 text-left text-sm', sel === r.id ? 'bg-terra-50 ring-1 ring-terra-200' : 'hover:bg-cream')}>
                <div className="flex items-center gap-1.5"><b>{r.student}</b><span className="text-ink-3">第{r.week_no}周 · {r.segment}</span>{r.reflection && <Badge tone="blue">有反思</Badge>}</div>
                <div className="truncate text-xs text-ink-3">{r.text}</div>
              </button>
            ))}
          </div>
        </Card>
        {!d || !sel ? (!mobile && <Card className="p-10"><Empty text="从左侧选择一条记录开始评阅" /></Card>) : (
          <div className="space-y-4">
            {mobile && <button onClick={() => { setSel(null); setD(null) }} className="text-sm text-ink-2">← 返回列表</button>}
            <Card className="p-4">
              <div className="flex flex-wrap items-center gap-2"><b className="text-lg">{d.student}</b><span className="text-sm text-ink-3">第{d.week_no}周 · {d.class_name}班 · {d.segment} · {fmtTime(d.created_at)}</span><Badge tone="gray" className="ml-auto">你的身份：{SRC_CN[d.mentor_kind]}</Badge></div>
              <div className="mt-2 leading-7">{d.inspection.text}</div>
              {d.inspection.media?.length > 0 && <div className="mt-2 flex gap-2">{d.inspection.media.map((m: any) => <img key={m.id} src={fileUrl(m.url)} className="h-20 rounded-lg" alt="已打码" />)}</div>}
              {d.reflection && <div className="mt-2 rounded-xl bg-[#E7F0FC] p-2.5 text-sm"><b className="text-[#2160B8]">学生反思：</b>{d.reflection}</div>}
            </Card>
            <div className={cx('grid gap-4', !mobile && 'xl:grid-cols-2')}>
              <Card className="max-h-[560px] overflow-auto p-4"><div className="mb-2 font-bold">对抗评价过程</div><ChatFlow messages={msgs} agents={agents} compact onChunk={(c) => api(`/chunks/${c}`).then(setChunk)} /></Card>
              <div className="space-y-4">
                <Card className="p-4">
                  <div className="mb-2 font-bold">问题条目确认</div>
                  {d.inspection.findings.length === 0 && <div className="text-sm text-ink-3">本条记录未诊断出问题</div>}
                  {d.inspection.findings.map((f: any) => (
                    <div key={f.id} className="mb-2 rounded-xl bg-cream p-2.5 text-sm">
                      <div className="flex flex-wrap items-center gap-1.5"><b>{f.item}</b><Badge tone={SEV_TONE[f.severity]}>{f.category}</Badge><VerdictBadge v={f.final_verdict} /><span className="text-xs text-ink-3">置信度 {f.confidence.toFixed(2)}</span></div>
                      <div className="mt-1 text-xs text-ink-2">{f.verdict_reason}</div>
                      <div className="mt-1.5 flex gap-1.5">{(['valid', 'invalid'] as const).map((v) => <button key={v} onClick={() => setFdec({ ...fdec, [f.id]: v })} className={cx('rounded-full px-3 py-1 text-xs', fdec[f.id] === v ? (v === 'valid' ? 'bg-[#D9483B] text-white' : 'bg-[#2F7BE0] text-white') : 'bg-white')}>{v === 'valid' ? '成立' : '不成立'}</button>)}</div>
                    </div>
                  ))}
                </Card>
                <Card className="p-4">
                  <div className="mb-2 flex items-center justify-between"><div className="font-bold">五维评分</div><span className="text-xs text-ink-3">灰点 = AI 草稿</span></div>
                  {DIMS.map((k) => (
                    <div key={k} className="mb-2">
                      <div className="flex items-center gap-2 text-sm"><span className="flex-1">{DIM_FULL[k]}</span>
                        {[1, 2, 3, 4, 5].map((v) => <button key={v} onClick={() => setScores({ ...scores, [k]: v })} className={cx('h-8 w-8 rounded-full text-sm font-bold', scores[k] === v ? 'bg-terra-500 text-white' : d.ai_scores[k]?.score === v ? 'bg-cream-3 text-ink' : 'bg-cream text-ink-3')}>{v}</button>)}
                      </div>
                      {d.ai_scores[k] && <div className="mt-0.5 text-xs text-ink-3">AI 依据：{d.ai_scores[k].evidence}{d.ai_scores[k].cited?.map((c: number) => <button key={c} onClick={() => api(`/chunks/${c}`).then(setChunk)} className="ml-1 text-[#A86400] hover:underline">📖#{c}</button>)}</div>}
                    </div>
                  ))}
                  <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="评语：肯定做得好的地方，指出一个最需要改进的点" className="mt-1 w-full rounded-xl border border-[#E9DCD0] p-2.5 text-sm" />
                  <Button className="mt-2 w-full" onClick={submit}>提交评阅</Button>
                </Card>
              </div>
            </div>
          </div>
        )}
      </div>
      <Modal open={!!chunk} onClose={() => setChunk(null)} title="引用条款原文">{chunk && <ChunkList chunks={[chunk]} />}</Modal>
    </div>
  )
}

export function MentorMetrics() {
  const [src, setSrc] = useState<'real' | 'demo'>('real')
  const [m, setM] = useState<any>(null)
  const [md, setMd] = useState('')
  useEffect(() => { api(`/practice/metrics?source=${src}`).then(setM); api(`/practice/metrics.md?source=${src}`).then(setMd) }, [src])
  const pct = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)
  return (
    <div className="mx-auto max-w-[1200px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
      <h1 className="text-4xl font-black">应用成效数据</h1>
      <div className="mt-1 text-ink-2">全部数字由系统记录直接计算；一致性与误判率以导师评阅为标准答案</div>
      <div className="mt-4 flex gap-2">
        <Tabs value={src} onChange={setSrc} items={[{ value: 'real', label: '真实使用数据' }, { value: 'demo', label: '演示数据' }]} />
        <Button variant="ghost" size="sm" onClick={() => { const b = new Blob([md], { type: 'text/markdown' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `成效数据_${src}.md`; a.click() }}>导出 Markdown</Button>
      </div>
      {!m ? <Spinner /> : (
        <div className="mt-5 grid gap-4 md:grid-cols-4">
          {[[m.students, '参与学生'], [m.records, '实践记录'], [pct(m.reflection_rate), '提交反思比例'], [m.feedback_seconds_median == null ? '—' : `${Math.round(m.feedback_seconds_median)} 秒`, '提交到 AI 反馈（中位数）'],
            [pct(m.rubric_within1_rate), `AI 与导师评分相差≤1（${m.rubric_pairs} 项）`], [pct(m.rubric_exact_rate), 'AI 与导师评分完全一致'], [pct(m.solo_error_rate), '诊断员单独误判率'], [pct(m.adversarial_error_rate), '对抗后裁定误判率']].map(([v, l], i) => (
            <Card key={i} className="p-4"><div className="text-3xl font-black">{v}</div><div className="mt-1 text-sm text-ink-2">{l}</div></Card>
          ))}
          {m.value_added_avg && <Card className="p-4 md:col-span-4"><div className="font-bold">五维增值（{m.students_with_growth} 名学生平均，后两周 − 前两周）</div>
            <div className="mt-2 grid gap-2 md:grid-cols-5">{DIMS.map((k) => <div key={k} className="rounded-xl bg-cream p-3 text-center"><div className="text-2xl font-black text-[#0E7A2F]">{m.value_added_avg[k] >= 0 ? '+' : ''}{m.value_added_avg[k].toFixed(2)}</div><div className="text-xs text-ink-2">{DIM_FULL[k]}</div></div>)}</div></Card>}
        </div>
      )}
    </div>
  )
}
