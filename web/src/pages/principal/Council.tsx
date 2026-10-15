import { useEffect, useState } from 'react'
import { api } from '../../api'
import { IAlert, IBulb, ICheck, IFile } from '../../components/icons'
import { Badge, Button, Card, Modal, Spinner, fmtTime, useToast } from '../../components/ui'
import { ArenaPlayer } from './Arena'

const VIEW_CN: Record<string, string> = { health: '保健', teacher: '教师', parent: '家长', safety: '安全' }

export default function Council() {
  const [topics, setTopics] = useState<any[] | null>(null)
  const [cur, setCur] = useState<any>(null)
  const [newOpen, setNewOpen] = useState(false)
  const [decOpen, setDecOpen] = useState(false)
  const [form, setForm] = useState({ title: '冬季午睡时间是否提前 20 分钟？', detail: '讨论冬季午睡时间调整方案，综合保健、教师、家长与安全四方意见。' })
  const [decision, setDecision] = useState('')
  const toast = useToast()
  const load = async (selectId?: number) => {
    const t = await api('/council/topics')
    setTopics(t)
    const pick = t.find((x: any) => x.id === (selectId ?? cur?.id)) || t[0]
    setCur(pick || null)
  }
  useEffect(() => { load() }, [])
  // 议事进行中时轮询简报
  useEffect(() => {
    if (!cur || cur.status !== 'running') return
    const t = setInterval(async () => {
      const x = await api(`/council/topics/${cur.id}`)
      if (x.status !== 'running') { setCur(x); load(x.id) }
    }, 2500)
    return () => clearInterval(t)
  }, [cur?.id, cur?.status])
  const brief = cur?.brief || {}
  return (
    <div className="mx-auto max-w-[1360px] px-5 pb-16 pt-6 lg:px-8 lg:pt-8">
      <div className="flex flex-wrap items-center gap-3 text-sm text-ink-2">
        <span>{new Date().getFullYear()} 秋季学期</span><Badge tone="terra">AI 草稿 · 园长确认</Badge>
      </div>
      <div className="mt-2 flex flex-wrap items-end gap-4">
        <h1 className="text-5xl font-black">园务议事</h1>
        <div className="pb-1.5 text-lg text-ink-2">共商 · 共识 · 共建更好的童年</div>
        <div className="ml-auto flex gap-2">
          {topics && topics.length > 0 && (
            <select value={cur?.id || ''} onChange={(e) => setCur(topics.find((t) => t.id === Number(e.target.value)))} className="h-10 rounded-full border border-[#E9DCD0] bg-white px-4 text-sm">
              {topics.map((t) => <option key={t.id} value={t.id}>{t.title}（{fmtTime(t.created_at)}）</option>)}
            </select>
          )}
          <Button onClick={() => setNewOpen(true)}>发起议题</Button>
        </div>
      </div>

      {!topics ? <div className="mt-10"><Spinner /></div> : !cur ? (
        <Card className="mt-6 p-10 text-center">
          <img src="/mascot/aibao.png" className="mx-auto h-40" alt="" />
          <div className="mt-4 text-lg font-bold">还没有议题</div>
          <div className="mt-1 text-ink-2">例如"冬季午睡时间是否提前 20 分钟"，爱宝会请保健、教师、家长、安全四位视角依次发言并交叉质询。</div>
          <Button className="mt-5" onClick={() => setNewOpen(true)}>发起第一个议题</Button>
        </Card>
      ) : (
        <div className="mt-6 grid gap-5 xl:grid-cols-[1fr_440px]">
          <div>{cur.run_id && <ArenaPlayer key={cur.run_id} runId={cur.run_id} height={600} showFlow={false} />}</div>
          <Card className="flex flex-col p-6">
            <div className="flex items-center justify-between">
              <div className="text-2xl font-black">议题简报</div>
              <Badge tone={cur.final_decision ? 'green' : 'terra'} className="text-sm">{cur.final_decision ? '园长已决定' : cur.status === 'running' ? '议事进行中' : '简报待确认'}</Badge>
            </div>
            <div className="mt-4 text-2xl font-bold leading-snug">{cur.title}</div>
            {cur.detail && <div className="mt-2 leading-7 text-ink-2">{cur.detail}</div>}
            {cur.status === 'running' ? (
              <div className="mt-8 flex items-center gap-2 text-ink-3"><Spinner />四位视角正在发言，简报生成中…</div>
            ) : (
              <div className="mt-5 space-y-3">
                <Block tone="green" icon={<ICheck size={18} />} title="共识" items={brief.consensus || []} />
                <Block tone="red" icon={<IAlert size={18} />} title="分歧（保留）" items={(brief.disagreements || []).map((d: any) => `${d.between.map((b: string) => VIEW_CN[b] || b).join(' ↔ ')}：${d.point}`)} />
                <Block tone="amber" icon={<IBulb size={18} />} title="备选方案" items={(brief.options || []).map((o: any) => `${o.name}　✔ ${o.pros}　✘ ${o.cons}`)} />
                {brief.risks?.length > 0 && <div className="text-sm text-ink-2"><b>风险：</b>{brief.risks.join('；')}</div>}
              </div>
            )}
            {cur.final_decision && (
              <div className="mt-4 rounded-2xl bg-[#E6F6EA] p-4"><div className="text-sm font-bold text-[#0E7A2F]">园长最终决定 · {fmtTime(cur.decided_at)}</div><div className="mt-1">{cur.final_decision}</div></div>
            )}
            <div className="mt-auto pt-5">
              <Button size="lg" className="w-full" disabled={cur.status === 'running'} onClick={() => { setDecision(cur.final_decision || ''); setDecOpen(true) }}><IFile />记录园长决定</Button>
              <div className="mt-3 text-center text-xs text-ink-3">ⓘ AI 草稿，待园长确认。所有决策均需园长最终确认。</div>
            </div>
          </Card>
        </div>
      )}

      <Modal open={newOpen} onClose={() => setNewOpen(false)} title="发起园务议题">
        <div className="space-y-3">
          <input className="h-11 w-full rounded-xl border border-[#E9DCD0] px-3" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="议题" />
          <textarea rows={4} className="w-full rounded-xl border border-[#E9DCD0] p-3" value={form.detail} onChange={(e) => setForm({ ...form, detail: e.target.value })} placeholder="背景说明（可选）" />
          <div className="flex flex-wrap gap-2 text-xs">{['冬季午睡时间是否提前 20 分钟？', '雨雪天户外活动是否改为室内体能循环？', '离园时段是否分年级错峰？'].map((s) => (
            <button key={s} onClick={() => setForm({ ...form, title: s })} className="rounded-full bg-cream-2 px-3 py-1">{s}</button>))}</div>
          <Button className="w-full" onClick={async () => { const t = await api('/council/topics', { method: 'POST', json: form }); setNewOpen(false); toast('议题已发起，四方开始发言'); load(t.id) }}>开始议事</Button>
        </div>
      </Modal>
      <Modal open={decOpen} onClose={() => setDecOpen(false)} title="记录园长决定">
        <textarea rows={4} className="w-full rounded-xl border border-[#E9DCD0] p-3" value={decision} onChange={(e) => setDecision(e.target.value)} placeholder="例如：先在小一、中一两个班试行两周，用巡查数据评估后再定。" />
        <Button className="mt-3 w-full" onClick={async () => { await api(`/council/topics/${cur.id}/decision`, { method: 'POST', json: { decision } }); setDecOpen(false); toast('决定已归档'); load(cur.id) }}>归档决定</Button>
      </Modal>
    </div>
  )
}

function Block({ tone, icon, title, items }: { tone: 'green' | 'red' | 'amber'; icon: React.ReactNode; title: string; items: string[] }) {
  const s = { green: ['bg-[#F1F7EC]', 'text-[#3E7A22]', 'bg-[#5C9A3A]'], red: ['bg-[#FDF0EC]', 'text-[#C2412F]', 'bg-[#D9573F]'], amber: ['bg-[#FFF6E8]', 'text-[#C7700A]', 'bg-[#F2A516]'] }[tone]
  return (
    <div className={`rounded-2xl p-4 ${s[0]}`}>
      <div className={`flex items-center gap-2 text-lg font-bold ${s[1]}`}><span className={`flex h-7 w-7 items-center justify-center rounded-full text-white ${s[2]}`}>{icon}</span>{title}</div>
      <ul className="mt-2 space-y-1.5 pl-9 text-[15px] leading-6">{items.length ? items.map((t, i) => <li key={i}>{t}</li>) : <li className="text-ink-3">—</li>}</ul>
    </div>
  )
}
