import { useEffect, useRef, useState } from 'react'
import { api, streamRun } from '../../api'
import { ISend } from '../../components/icons'
import { Spinner, cx } from '../../components/ui'
import { useApp, useAvatar } from '../../store'

const FAQ = ['几点入园？', '每周食谱在哪里看？', '户外特色课有哪些？', '孩子需要带备用衣物吗？', '周五下午有什么安排？', '我家孩子今天有点咳嗽可以来吗？']

export default function ParentChat() {
  const { me, logout } = useApp()
  const [thread, setThread] = useState<any>(null)
  const [q, setQ] = useState('')
  const [emotion, setEmotion] = useState('bye')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const face = useAvatar('aibao', emotion)
  const load = () => api('/parent/thread').then(setThread)
  useEffect(() => { load() }, [])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [thread?.messages?.length, busy])
  const ask = async (text: string) => {
    if (!text.trim() || busy) return
    setBusy(true); setQ(''); setEmotion('doubt')
    setThread((t: any) => ({ ...t, messages: [...(t?.messages || []), { id: -1, role: 'parent', content: text }] }))
    const r = await api('/parent/chat', { method: 'POST', json: { content: text } })
    streamRun(r.run_id, (m) => {
      if (m.agent === 'weishi') setEmotion(m.content?.risk_level === 'high' ? 'surprised' : 'doubt')
      else if (m.action === 'route' && m.text.startsWith('转教师')) setEmotion('bye')
      else if (m.action === 'state') setEmotion('happy')
      else if (m.action === 'statement') setEmotion('cheer')
    }, async () => { await load(); setBusy(false) })
  }
  return (
    <div className="mx-auto flex min-h-screen max-w-[520px] flex-col bg-gradient-to-b from-[#FFF3EA] to-cream">
      <header className="flex items-center gap-3 px-4 pb-2 pt-[max(env(safe-area-inset-top),12px)]">
        <img src="/logo.png" className="h-9 w-9" alt="" />
        <div className="leading-tight"><div className="text-sm font-black text-brand-orange">宝鸡幼儿园</div><div className="text-xs text-ink-3">{thread?.class_name ? `${thread.class_name}班家长` : '家长'} · 爱宝答疑</div></div>
        <button onClick={logout} className="ml-auto rounded-full bg-white px-3 py-1 text-xs text-ink-3">退出</button>
      </header>
      <div className="flex flex-col items-center px-4">
        <img src={face} className="h-28 w-28 rounded-3xl object-cover shadow-lg transition-all" alt="爱宝" />
        <div className="mt-2 text-center text-sm text-ink-2">{busy ? '爱宝正在查资料，小卫士在帮忙把关…' : '你好呀，我是爱宝！作息、食谱、入园须知都可以问我～'}</div>
      </div>
      <div className="flex-1 space-y-3 overflow-auto px-4 py-4">
        {thread?.messages?.map((m: any) => (
          <div key={m.id} className={cx('flex', m.role === 'parent' ? 'justify-end' : 'justify-start')}>
            <div className={cx('max-w-[80%] rounded-2xl px-3.5 py-2.5 text-[15px] leading-6 shadow-sm',
              m.role === 'parent' ? 'rounded-br-sm bg-terra-500 text-white' : m.role === 'teacher' ? 'rounded-bl-sm bg-[#E6F6EA]' : 'rounded-bl-sm bg-white')}>
              {m.role === 'teacher' && <div className="mb-0.5 text-xs font-bold text-[#0E7A2F]">班级老师回复</div>}
              {m.content}
              {m.sources?.length > 0 && <div className="mt-1 text-[11px] text-ink-3">依据来自{m.sources.map((s: any) => `《${s.title}》${s.clause}`).join('、')}</div>}
              {m.route === 'transfer' && m.role === 'aibao' && <div className="mt-1 text-[11px] text-ink-3">老师会在工作时间内回复，回复会显示在这里</div>}
            </div>
          </div>
        ))}
        {busy && <div className="flex"><div className="rounded-2xl bg-white px-4 py-3 shadow-sm"><Spinner className="text-terra-400" /></div></div>}
        <div ref={end} />
      </div>
      <div className="no-scrollbar flex gap-2 overflow-x-auto px-4 pb-2">{FAQ.map((f) => <button key={f} onClick={() => ask(f)} className="shrink-0 rounded-full bg-white px-3 py-1.5 text-xs text-ink-2 shadow-sm">{f}</button>)}</div>
      <form className="flex gap-2 px-4 pb-[max(env(safe-area-inset-bottom),12px)] pt-1" onSubmit={(e) => { e.preventDefault(); ask(q) }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="问问爱宝…" className="h-12 flex-1 rounded-full border border-[#EBDCCF] bg-white px-4 outline-none focus:border-terra-300" />
        <button disabled={busy} className="flex h-12 w-12 items-center justify-center rounded-full bg-terra-500 text-white shadow-pill disabled:opacity-50"><ISend /></button>
      </form>
      <div className="pb-3 text-center text-[10px] text-ink-3">涉及具体孩子的问题会自动转给班级老师{me?.login?.startsWith('parent') ? '' : ' · 园长/管理员体验模式'}</div>
    </div>
  )
}
