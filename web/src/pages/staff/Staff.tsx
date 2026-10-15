import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { api, fileUrl, streamRun, upload, type AgentMsg } from '../../api'
import ChatFlow from '../../components/ChatFlow'
import { Brand } from '../../components/Layout'
import { IBack, ICamera, IChevron, IClip, IFile, IMic, ISearch, ISend, IUsers, IX } from '../../components/icons'
import { SEGMENTS, SegIcon } from '../../components/segments'
import { Badge, Button, Card, Empty, Mascot, Modal, SEV_TONE, Spinner, VerdictBadge, cx, fmtTime, useToast } from '../../components/ui'
import { useApp } from '../../store'
import { ChunkList } from '../principal/Inspect'

export function StaffShell() {
  const { me, logout } = useApp()
  const [badge, setBadge] = useState<Record<string, number>>({})
  useEffect(() => {
    const load = () => Promise.all([api('/rectifications?mine=true'), api('/staff/parent-queue')]).then(([r, q]) =>
      setBadge({ '/staff/rect': r.filter((x: any) => x.status === 'issued').length, '/staff/parents': q.filter((x: any) => !x.reply).length })).catch(() => {})
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])
  const tabs = [
    { to: '/staff', label: '巡查', icon: <ICamera />, end: true },
    { to: '/staff/mine', label: '记录', icon: <IClip /> },
    { to: '/staff/rect', label: '整改', icon: <IFile /> },
    { to: '/staff/parents', label: '家长', icon: <IUsers /> },
    { to: '/staff/ask', label: '助手', icon: <ISearch /> },
  ]
  return (
    <div className="mx-auto min-h-screen max-w-[520px] bg-cream pb-24">
      <header className="sticky top-0 z-30 flex items-center justify-between bg-cream/95 px-4 pb-2 pt-[max(env(safe-area-inset-top),10px)] backdrop-blur">
        <Brand compact />
        <div className="flex items-center gap-2 text-right text-xs leading-tight">
          <div><div className="font-bold text-sm">{me?.name}</div><div className="text-ink-3">{me?.classes?.length ? `${me.classes.join('、')}班` : me?.positions?.join('、')}</div></div>
          {me?.role === 'principal' && <NavLink to="/principal" className="rounded-full bg-white px-2 py-1 text-ink-2">驾驶舱</NavLink>}
          <button onClick={logout} className="rounded-full bg-white px-2 py-1 text-ink-3">退出</button>
        </div>
      </header>
      <Outlet />
      <nav className="fixed bottom-0 left-1/2 z-30 flex w-full max-w-[520px] -translate-x-1/2 justify-around border-t border-[#EFE2D6] bg-white/95 pb-[max(env(safe-area-inset-bottom),6px)] pt-1.5 backdrop-blur">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => cx('relative flex min-w-[56px] flex-col items-center gap-0.5 rounded-xl px-2 py-1 text-[11px]', isActive ? 'text-terra-600 font-bold' : 'text-ink-3')}>
            {t.icon}{t.label}
            {badge[t.to] > 0 && <span className="absolute right-2 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#E5483B] px-1 text-[10px] font-bold text-white">{badge[t.to]}</span>}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

// 前端压缩：长边 1600px
async function compress(file: File): Promise<Blob> {
  const bmp = await createImageBitmap(file)
  const s = Math.min(1, 1600 / Math.max(bmp.width, bmp.height))
  const c = document.createElement('canvas')
  c.width = Math.round(bmp.width * s); c.height = Math.round(bmp.height * s)
  c.getContext('2d')!.drawImage(bmp, 0, 0, c.width, c.height)
  return new Promise((res) => c.toBlob((b) => res(b || file), 'image/jpeg', 0.86))
}

export function NewInspection() {
  const { me } = useApp()
  const [classes, setClasses] = useState<any[]>([])
  const [classId, setClassId] = useState<number | null>(null)
  const [sched, setSched] = useState<any>(null)
  const [segment, setSegment] = useState('')
  const [text, setText] = useState('')
  const [photos, setPhotos] = useState<{ id: number; url: string; faces: number }[]>([])
  const [audio, setAudio] = useState<{ id: number; transcript: string | null } | null>(null)
  const [busy, setBusy] = useState('')
  const [rec, setRec] = useState<MediaRecorder | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLInputElement>(null)
  const toast = useToast()
  const nav = useNavigate()
  useEffect(() => {
    api('/classes').then((cs) => {
      setClasses(cs)
      const mine = cs.find((c: any) => c.mine)
      setClassId((mine || cs[0])?.id ?? null)
    })
  }, [])
  useEffect(() => {
    if (!classId) return
    api(`/schedule/now?class_id=${classId}`).then((s) => { setSched(s); setSegment(s.segment) })
  }, [classId])
  const addPhotos = async (files: FileList | null) => {
    if (!files) return
    const list = Array.from(files).slice(0, 6 - photos.length)
    setBusy('正在本地打码人脸…')
    try {
      for (const f of list) {
        const fd = new FormData()
        fd.append('file', await compress(f), 'photo.jpg'); fd.append('kind', 'image')
        const r = await upload('/media', fd)
        setPhotos((p) => [...p, { id: r.id, url: r.preview_url, faces: r.faces }])
      }
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const sendAudio = async (blob: Blob, name: string) => {
    setBusy('正在本地转写（音频不出园）…')
    try {
      const fd = new FormData(); fd.append('file', blob, name); fd.append('kind', 'audio')
      const r = await upload('/media', fd)
      setAudio({ id: r.id, transcript: r.transcript })
      if (r.transcript) setText((t) => (t ? t + '\n' : '') + r.transcript)
      else toast('本地语音识别服务未启动，请直接输入文字', 'err')
    } finally { setBusy('') }
  }
  const startRec = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true })
      const r = new MediaRecorder(s)
      const chunks: Blob[] = []
      r.ondataavailable = (e) => chunks.push(e.data)
      r.onstop = () => { s.getTracks().forEach((t) => t.stop()); sendAudio(new Blob(chunks, { type: r.mimeType }), 'voice.webm') }
      r.start(); setRec(r)
    } catch { toast('无法使用麦克风，请改用上传音频或文字', 'err') }
  }
  const submit = async () => {
    if (!classId || !segment) return
    setBusy('提交中…')
    try {
      const r = await api('/inspections', { method: 'POST', json: { class_id: classId, segment, text, media_ids: [...photos.map((p) => p.id), ...(audio ? [audio.id] : [])] } })
      nav(`/staff/result/${r.inspection_id}?run=${r.run_id}`)
    } catch (e: any) { toast(e.message, 'err'); setBusy('') }
  }
  return (
    <div className="space-y-4 px-4 pt-2">
      <div className="flex items-center gap-3 rounded-3xl bg-gradient-to-r from-[#EAF3FD] to-white p-4">
        <img src="/mascot/xingbao.png" className="h-20 w-20 object-contain" alt="星宝" />
        <div><div className="text-lg font-black">星宝来帮你看一看</div><div className="text-sm text-ink-2">三步提交，照片在本地自动打码</div></div>
      </div>
      {/* 第 1 步 */}
      <Card className="p-4">
        <div className="flex items-center gap-2 font-bold"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-terra-500 text-xs text-white">1</span>班级与环节</div>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {classes.map((c) => (
            <button key={c.id} onClick={() => setClassId(c.id)} className={cx('shrink-0 rounded-full px-3 py-1.5 text-sm', classId === c.id ? 'bg-terra-500 text-white' : c.mine ? 'bg-terra-50 text-terra-600' : 'bg-cream-2 text-ink-2')}>{c.name}{c.mine ? '★' : ''}</button>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-4 gap-2">
          {SEGMENTS.map((s) => (
            <button key={s} onClick={() => setSegment(s)} className={cx('flex flex-col items-center gap-1 rounded-2xl py-2.5 text-sm', segment === s ? 'bg-terra-500 text-white shadow-pill' : 'bg-cream text-ink-2')}>
              <SegIcon seg={s} />{s}
            </button>
          ))}
        </div>
        {sched && (
          <div className="mt-3 rounded-2xl bg-cream p-3 text-xs text-ink-2">
            <div>⏱ 当前：{sched.segment_text || '—'}{sched.start ? `（${sched.start}–${sched.end}）` : ''} {sched.confirmed === false && <Badge tone="amber">作息待确认</Badge>}</div>
            <div className="mt-1">👥 在岗：{sched.on_duty.map((d: any) => `${d.name}（${d.role}）`).join('、') || '—'}</div>
            {sched.week_no && <div className="mt-1">📅 第 {sched.week_no} 周 · {sched.parity === 'single' ? '单周' : '双周'}课表</div>}
          </div>
        )}
      </Card>
      {/* 第 2 步 */}
      <Card className="p-4">
        <div className="flex items-center gap-2 font-bold"><span className="flex h-6 w-6 items-center justify-center rounded-full bg-terra-500 text-xs text-white">2</span>照片 / 语音 / 文字</div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {photos.map((p) => (
            <div key={p.id} className="relative">
              <img src={fileUrl(p.url)} className="aspect-square w-full rounded-xl object-cover" alt="打码预览" />
              <span className="absolute bottom-1 left-1 rounded-full bg-black/60 px-1.5 text-[10px] text-white">{p.faces ? `已模糊 ${p.faces} 张脸` : '未检出人脸'}</span>
              <button onClick={() => setPhotos(photos.filter((x) => x.id !== p.id))} className="absolute right-1 top-1 rounded-full bg-white/90 p-0.5"><IX size={14} /></button>
            </div>
          ))}
          {photos.length < 6 && (
            <button onClick={() => fileRef.current?.click()} className="flex aspect-square flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-terra-200 text-terra-500">
              <ICamera size={26} /><span className="text-xs">拍照 / 相册</span>
            </button>
          )}
        </div>
        <input ref={fileRef} type="file" accept="image/*" capture="environment" multiple hidden onChange={(e) => addPhotos(e.target.files)} />
        <div className="mt-3 flex gap-2">
          <button onPointerDown={startRec} onPointerUp={() => { rec?.stop(); setRec(null) }} onPointerLeave={() => { if (rec) { rec.stop(); setRec(null) } }}
            className={cx('flex flex-1 items-center justify-center gap-2 rounded-full py-2.5 text-sm select-none', rec ? 'bg-[#D9483B] text-white' : 'bg-cream-2 text-ink-2')}>
            <IMic size={18} />{rec ? '松开结束' : '按住说话'}
          </button>
          <button onClick={() => audioRef.current?.click()} className="rounded-full bg-cream-2 px-4 text-sm text-ink-2">上传音频</button>
          <input ref={audioRef} type="file" accept=".m4a,.mp3,.wav,audio/*" hidden onChange={(e) => e.target.files?.[0] && sendAudio(e.target.files[0], e.target.files[0].name)} />
        </div>
        <div className="mt-1 text-[11px] text-ink-3">请勿上传含幼儿声音的录音；音频只在园内服务器转写。</div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder="例如：13:10 午睡巡视，寝室窗户紧闭，巡视记录 12:30 后空白。"
          className="mt-3 w-full rounded-2xl border border-[#E9DCD0] bg-white p-3 text-[15px] outline-none focus:border-terra-300" />
      </Card>
      {/* 第 3 步 */}
      <Button size="lg" className="w-full" disabled={!!busy || (!text.trim() && !photos.length)} onClick={submit}>
        {busy ? <><Spinner />{busy}</> : <>3 · 提交给星宝诊断 <ISend /></>}
      </Button>
      {me?.role === 'staff' && !me.class_ids.length && <div className="text-center text-xs text-ink-3">你当前没有班级任职，可选择任意班级巡查</div>}
    </div>
  )
}

export function InspectionResult() {
  const { id } = useParams()
  const runId = Number(new URLSearchParams(location.search).get('run'))
  const [msgs, setMsgs] = useState<AgentMsg[]>([])
  const [agents, setAgents] = useState<any>({})
  const [insp, setInsp] = useState<any>(null)
  const [done, setDone] = useState(false)
  const [chunk, setChunk] = useState<any>(null)
  const [appeal, setAppeal] = useState<any>(null)
  const [t0] = useState(Date.now())
  const [elapsed, setElapsed] = useState(0)
  const toast = useToast()
  const nav = useNavigate()
  const loadInsp = () => api(`/inspections/${id}`).then(setInsp)
  useEffect(() => {
    loadInsp()
    const rid = runId || 0
    let stop = () => {}
    const go = async () => {
      const i = await api(`/inspections/${id}`)
      const r = await api(`/runs/${rid || i.run_id}`)
      setAgents(r.agents)
      if (r.status !== 'running') { setMsgs(r.messages); setDone(true); return }
      stop = streamRun(rid || i.run_id, (m) => setMsgs((x) => (x.some((y) => y.id === m.id) ? x : [...x, m])), () => { setDone(true); setElapsed((Date.now() - t0) / 1000); loadInsp() })
    }
    go()
    return () => stop()
  }, [id])
  return (
    <div className="space-y-4 px-4 pt-2">
      <button onClick={() => nav('/staff')} className="flex items-center gap-1 text-sm text-ink-2"><IBack size={16} />再巡查一条</button>
      {insp && (
        <Card className="p-4">
          <div className="flex items-center gap-2"><SegIcon seg={insp.segment} /><b>{insp.class_name}班 · {insp.segment}</b><span className="ml-auto text-xs text-ink-3">{fmtTime(insp.created_at)}</span></div>
          <div className="mt-2 text-sm text-ink-2">{insp.text}</div>
          {insp.media.length > 0 && <div className="mt-2 flex gap-2">{insp.media.map((m: any) => <img key={m.id} src={fileUrl(m.url)} className="h-16 w-20 rounded-lg object-cover" alt="" />)}</div>}
        </Card>
      )}
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="font-bold">对抗过程</div>
          {done ? <Badge tone="green">已完成{elapsed ? ` · ${elapsed.toFixed(0)} 秒` : ''}</Badge> : <Badge tone="amber"><Spinner className="h-3 w-3" /> 进行中</Badge>}
        </div>
        <ChatFlow messages={msgs} agents={agents} compact onChunk={(c) => api(`/chunks/${c}`).then(setChunk)} />
      </Card>
      {done && insp && (
        <Card className="p-4">
          <div className="mb-2 font-bold">诊断结果</div>
          {insp.findings.length === 0 && <Empty text="对照条款未发现问题，做得很好！" emotion="happy" />}
          <div className="space-y-3">
            {insp.findings.map((f: any) => (
              <div key={f.id} className="rounded-2xl bg-cream p-3">
                <div className="flex flex-wrap items-center gap-1.5"><b>{f.item}</b><Badge tone={SEV_TONE[f.severity]}>{f.category}·{f.severity}</Badge><VerdictBadge v={f.final_verdict} /></div>
                <div className="mt-1 text-sm text-ink-2">{f.verdict_reason}</div>
                <div className="mt-1 text-xs text-ink-3">置信度 {f.confidence.toFixed(2)}{f.needs_review ? ` · 已进入园长复核（${f.review_reason}）` : ''}</div>
                <ChunkList chunks={f.chunks || []} />
                <div className="mt-2 flex justify-end">
                  {f.appeal ? <Badge tone="blue">已申诉</Badge> : <Button size="sm" variant="ghost" onClick={() => setAppeal({ id: f.id, reason: '' })}>申诉</Button>}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-center text-xs text-ink-3">整改单一律由园长确认后下发</div>
        </Card>
      )}
      <Modal open={!!chunk} onClose={() => setChunk(null)} title="引用条款原文">{chunk && <ChunkList chunks={[chunk]} />}</Modal>
      <Modal open={!!appeal} onClose={() => setAppeal(null)} title="对结论提出申诉">
        <textarea rows={4} className="w-full rounded-xl border p-3" placeholder="说明当时的情境，例如：已有保育员替岗" value={appeal?.reason || ''} onChange={(e) => setAppeal({ ...appeal, reason: e.target.value })} />
        <Button className="mt-3 w-full" onClick={async () => { await api(`/findings/${appeal.id}/appeal`, { method: 'POST', json: { reason: appeal.reason } }); setAppeal(null); toast('申诉已提交园长复核'); loadInsp() }}>提交申诉</Button>
      </Modal>
    </div>
  )
}

export function MyInspections() {
  const [items, setItems] = useState<any[] | null>(null)
  const nav = useNavigate()
  useEffect(() => { api('/inspections?limit=40').then(setItems) }, [])
  if (!items) return <div className="p-6"><Spinner /></div>
  return (
    <div className="space-y-2 px-4 pt-2">
      <div className="text-lg font-black">巡查记录</div>
      {items.length === 0 && <Empty text="还没有巡查记录" />}
      {items.map((i) => (
        <button key={i.id} onClick={() => nav(`/staff/result/${i.id}?run=${i.run_id}`)} className="flex w-full items-center gap-3 rounded-2xl bg-white p-3 text-left shadow-sm">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cream text-terra-500"><SegIcon seg={i.segment} /></div>
          <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{i.class_name}班 · {i.text}</div><div className="text-xs text-ink-3">{fmtTime(i.created_at)}</div></div>
          <div className="flex gap-1">{i.findings.slice(0, 2).map((f: any) => <VerdictBadge key={f.id} v={f.final_verdict} />)}</div>
          <IChevron size={16} className="text-ink-3" />
        </button>
      ))}
    </div>
  )
}

export function MyRect() {
  const [items, setItems] = useState<any[] | null>(null)
  const [cur, setCur] = useState<any>(null)
  const [photo, setPhoto] = useState<{ id: number; url: string } | null>(null)
  const toast = useToast()
  const load = () => api('/rectifications?mine=true').then(setItems)
  useEffect(() => { load() }, [])
  return (
    <div className="space-y-3 px-4 pt-2">
      <div className="text-lg font-black">我的整改单</div>
      {!items ? <Spinner /> : items.length === 0 ? <Empty text="没有需要你处理的整改单" emotion="happy" /> : items.map((r) => (
        <Card key={r.id} className="p-4">
          <div className="flex items-start justify-between gap-2"><b>{r.title}</b><Badge tone={SEV_TONE[r.severity]}>{r.severity}</Badge></div>
          <div className="mt-1 text-xs text-ink-3">截止 {fmtTime(r.work_order?.due_at || r.due_at)} · {({ issued: '待整改', submitted: '已回传待验收', closed: '已关闭' } as any)[r.status]}</div>
          <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-ink-2">{r.requirement}</pre>
          {r.status === 'issued' && <Button size="sm" className="mt-2" onClick={() => setCur({ ...r, text: '' })}>回传整改</Button>}
        </Card>
      ))}
      <Modal open={!!cur} onClose={() => setCur(null)} title="回传整改">
        <textarea rows={3} className="w-full rounded-xl border p-3" placeholder="整改说明" value={cur?.text || ''} onChange={(e) => setCur({ ...cur, text: e.target.value })} />
        <input type="file" accept="image/*" capture="environment" className="mt-2 text-sm" onChange={async (e) => {
          const f = e.target.files?.[0]; if (!f) return
          const fd = new FormData(); fd.append('file', await compress(f), 'p.jpg'); fd.append('kind', 'image')
          const r = await upload('/media', fd); setPhoto({ id: r.id, url: r.preview_url })
        }} />
        {photo && <img src={fileUrl(photo.url)} className="mt-2 h-24 rounded-xl" alt="" />}
        <Button className="mt-3 w-full" onClick={async () => {
          await api(`/rectifications/${cur.id}`, { method: 'PATCH', json: { action: 'submit', evidence_text: cur.text, evidence_media_ids: photo ? [photo.id] : [] } })
          setCur(null); setPhoto(null); toast('已回传，等待园长验收'); load()
        }}>提交</Button>
      </Modal>
    </div>
  )
}

export function ParentQueue() {
  const [items, setItems] = useState<any[] | null>(null)
  const [reply, setReply] = useState<Record<number, string>>({})
  const toast = useToast()
  const load = () => api('/staff/parent-queue').then(setItems)
  useEffect(() => { load() }, [])
  return (
    <div className="space-y-3 px-4 pt-2">
      <div className="text-lg font-black">家长转人工</div>
      {!items ? <Spinner /> : items.length === 0 ? <Empty text="没有转来的家长问题" emotion="happy" /> : items.map((m) => (
        <Card key={m.id} className="p-4">
          <div className="flex items-center gap-2 text-xs text-ink-3">{m.class_name}班家长 · {fmtTime(m.created_at)} {m.route === 'blocked' && <Badge tone="red">红队拦截</Badge>}</div>
          <div className="mt-1">{m.content}</div>
          {m.reply ? <div className="mt-2 rounded-xl bg-[#E6F6EA] p-2 text-sm">已回复：{m.reply}</div> : (
            <div className="mt-2 flex gap-2">
              <input className="h-10 flex-1 rounded-full border px-3 text-sm" value={reply[m.id] || ''} onChange={(e) => setReply({ ...reply, [m.id]: e.target.value })} placeholder="回复家长" />
              <Button size="md" onClick={async () => { await api('/staff/parent-queue', { method: 'POST', json: { message_id: m.id, content: reply[m.id] } }); toast('已回复'); load() }}>发送</Button>
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}

export function StaffAssistant() {
  const [q, setQ] = useState('')
  const [items, setItems] = useState<{ q: string; a: string; chunks: any[] }[]>([])
  const [busy, setBusy] = useState(false)
  return (
    <div className="space-y-3 px-4 pt-2">
      <div className="flex items-center gap-3"><Mascot agent="aibao" emotion="happy" /><div><div className="text-lg font-black">问爱宝</div><div className="text-xs text-ink-3">查询本园制度条款</div></div></div>
      {items.map((it, i) => (
        <div key={i} className="space-y-1">
          <div className="text-right"><span className="inline-block rounded-2xl bg-terra-500 px-3 py-2 text-sm text-white">{it.q}</span></div>
          <div className="rounded-2xl bg-white p-3 text-sm shadow-sm">{it.a}</div>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">{['午睡巡视间隔是多少？', '户外器械谁负责检查？', '食品留样要求'].map((s) => <button key={s} onClick={() => setQ(s)} className="rounded-full bg-cream-2 px-3 py-1 text-xs">{s}</button>)}</div>
      <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (!q.trim()) return; setBusy(true); try { const r = await api('/assistant/chat', { method: 'POST', json: { q } }); setItems([...items, { q, a: r.answer, chunks: r.chunks }]); setQ('') } finally { setBusy(false) } }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} className="h-11 flex-1 rounded-full border border-[#E9DCD0] bg-white px-4" placeholder="输入问题" />
        <Button disabled={busy}>{busy ? <Spinner /> : '问'}</Button>
      </form>
    </div>
  )
}
