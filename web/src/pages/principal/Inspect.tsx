import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, fileUrl } from '../../api'
import { IPlay } from '../../components/icons'
import { SegIcon } from '../../components/segments'
import { Badge, Button, Card, Empty, Modal, SEV_TONE, Spinner, Tabs, VerdictBadge, cx, fmtTime, useToast } from '../../components/ui'

type Tab = 'review' | 'rect' | 'list' | 'orders'

export default function PrincipalInspect() {
  const [sp, setSp] = useSearchParams()
  const tab = (sp.get('tab') as Tab) || 'review'
  return (
    <div className="mx-auto max-w-[1200px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
      <h1 className="text-4xl font-black">保教巡查</h1>
      <div className="mt-1 text-ink-2">复核 · 整改确认 · 巡查记录 · 工单时限 —— 所有结论与整改单都由园长确认</div>
      <div className="mt-5">
        <Tabs value={tab} onChange={(v) => setSp({ tab: v })} items={[
          { value: 'review', label: '复核队列' }, { value: 'rect', label: '整改单' }, { value: 'list', label: '巡查记录' }, { value: 'orders', label: '工单与时限' },
        ]} />
      </div>
      <div className="mt-5">
        {tab === 'review' && <ReviewQueue focus={Number(sp.get('f')) || undefined} />}
        {tab === 'rect' && <Rectifications />}
        {tab === 'list' && <InspectionList />}
        {tab === 'orders' && <WorkOrders />}
      </div>
    </div>
  )
}

export function ChunkList({ chunks }: { chunks: any[] }) {
  return (
    <div className="space-y-2">
      {chunks.filter(Boolean).map((c) => (
        <div key={c.id} className="rounded-xl border border-[#F0D9A8] bg-[#FFFBF0] p-3 text-sm">
          <div className="mb-1 text-xs font-semibold text-[#A86400]">📖 切片 #{c.id} ·《{c.doc_title}》{c.clause_no}</div>
          <div className="whitespace-pre-wrap leading-6 text-ink-2">{c.text}</div>
        </div>
      ))}
    </div>
  )
}

function ReviewQueue({ focus }: { focus?: number }) {
  const [items, setItems] = useState<any[] | null>(null)
  const [notes, setNotes] = useState<Record<number, string>>({})
  const toast = useToast()
  const nav = useNavigate()
  const load = () => api('/reviews/queue').then(setItems)
  useEffect(() => { load() }, [])
  useEffect(() => { if (focus && items) document.getElementById(`f-${focus}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }, [focus, items])
  const decide = async (id: number, decision: 'valid' | 'invalid') => {
    const r = await api('/reviews', { method: 'POST', json: { finding_id: id, decision, note: notes[id] || '' } })
    toast(decision === 'valid' ? (r.rectification_id ? '已认定成立，整改单草稿已生成' : '已认定成立') : '已认定不成立')
    load()
  }
  if (!items) return <Spinner />
  if (!items.length) return <Card className="p-6"><Empty text="复核队列已清空，辛苦了！" emotion="happy" /></Card>
  return (
    <div className="space-y-4">
      {items.map((f) => (
        <Card key={f.id} id={`f-${f.id}`} className={cx('p-5', focus === f.id && 'ring-2 ring-terra-300')}>
          <div className="flex flex-wrap items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-terra-50 text-terra-500"><SegIcon seg={f.segment} size={24} /></div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-lg font-bold">{f.item}</span>
                <Badge tone={SEV_TONE[f.severity]}>{f.category} · {f.severity}</Badge>
                <VerdictBadge v={f.final_verdict} />
                {f.appeal && <Badge tone="blue">教师申诉</Badge>}
              </div>
              <div className="mt-1 text-sm text-ink-3">{f.class_name}班 · {f.segment} · {fmtTime(f.created_at)} · 进入原因：{f.review_reason || '—'}{f.due_at ? ` · 复核时限 ${fmtTime(f.due_at)}` : ''}</div>
            </div>
            <Button variant="ghost" size="sm" onClick={() => nav(`/principal/arena?run=${f.run_id}`)}><IPlay size={14} />看对抗过程</Button>
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <div className="rounded-xl bg-cream p-3 text-sm"><div className="mb-1 text-xs text-ink-3">巡查原文（园内可见）</div>{f.inspection_text}</div>
              {f.media?.length > 0 && <div className="flex gap-2">{f.media.map((m: string) => <img key={m} src={fileUrl(m)} className="h-24 w-32 rounded-xl object-cover" alt="已打码照片" />)}</div>}
              <div className="rounded-xl bg-white p-3 text-sm ring-1 ring-cream-3">
                <div className="text-xs text-ink-3">诊断员理由</div><div>{f.reason}</div>
                <div className="mt-2 text-xs text-ink-3">裁判裁定（置信度 {f.confidence.toFixed(2)}）</div><div>{f.verdict_reason}</div>
                {f.appeal && <><div className="mt-2 text-xs text-ink-3">教师申诉理由</div><div className="text-[#2160B8]">{f.appeal.reason}</div></>}
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-semibold">引用条款原文</div>
              <ChunkList chunks={f.chunks || []} />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <input value={notes[f.id] || ''} onChange={(e) => setNotes({ ...notes, [f.id]: e.target.value })} placeholder="复核备注（可选）"
              className="h-10 min-w-[200px] flex-1 rounded-full border border-[#E9DCD0] bg-white px-4 text-sm" />
            <Button variant="danger" onClick={() => decide(f.id, 'valid')}>成立</Button>
            <Button className="!bg-[#2F7BE0]" onClick={() => decide(f.id, 'invalid')}>不成立</Button>
          </div>
        </Card>
      ))}
    </div>
  )
}

function Rectifications() {
  const navTo = useNavigate()
  const [items, setItems] = useState<any[] | null>(null)
  const [edit, setEdit] = useState<any>(null)
  const [staff, setStaff] = useState<any[]>([])
  const toast = useToast()
  const load = () => api('/rectifications').then(setItems)
  useEffect(() => { load(); api('/staff/search').then(setStaff) }, [])
  const act = async (id: number, action: string, extra: any = {}) => {
    try { await api(`/rectifications/${id}`, { method: 'PATCH', json: { action, ...extra } }); toast('已更新'); setEdit(null); load() } catch (e: any) { toast(e.message, 'err') }
  }
  if (!items) return <Spinner />
  const groups: [string, string][] = [['draft', '草稿 · 待园长确认下发'], ['submitted', '已回传 · 待验收'], ['issued', '已下发 · 整改中'], ['closed', '已关闭']]
  return (
    <div className="space-y-6">
      {groups.map(([st, label]) => {
        const rows = items.filter((r) => r.status === st)
        if (!rows.length) return null
        return (
          <div key={st}>
            <div className="mb-2 font-bold">{label}（{rows.length}）</div>
            <div className="grid gap-3 md:grid-cols-2">
              {rows.map((r) => (
                <Card key={r.id} className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-bold">{r.title}</div>
                    <Badge tone={SEV_TONE[r.severity]}>{r.severity}</Badge>
                  </div>
                  <div className="mt-1 text-sm text-ink-3">责任人：<b className="text-ink">{r.assignee}</b>（{r.suggested_by_rule}）· 期限 {fmtTime(r.work_order?.due_at || r.due_at)}</div>
                  <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-ink-2">{r.requirement}</pre>
                  {r.source && (
                    <details className="mt-2 rounded-xl bg-cream p-2.5 text-sm">
                      <summary className="cursor-pointer text-xs font-semibold text-ink-2">来源：{r.source.segment} · {r.source.category} · 裁定置信度 {r.source.confidence.toFixed(2)}（展开看原始巡查）</summary>
                      <div className="mt-2 text-ink-2">{r.source.inspection_text}</div>
                      {r.source.media.length > 0 && <div className="mt-2 flex gap-2">{r.source.media.map((m: string) => <img key={m} src={fileUrl(m)} className="h-16 rounded-lg" alt="已打码" />)}</div>}
                      <div className="mt-2 text-xs text-ink-3">裁判理由：{r.source.verdict_reason}</div>
                      <button onClick={() => navTo(`/principal/arena?run=${r.source.run_id}`)} className="mt-2 text-xs text-terra-600 hover:underline">▶ 看对抗过程</button>
                    </details>
                  )}
                  {r.status === 'submitted' && (
                    <div className="mt-2 rounded-xl bg-[#E6F6EA] p-2 text-sm">回传：{r.evidence_text || '（照片）'}
                      <div className="mt-1 flex gap-2">{r.evidence_media.map((m: string) => <img key={m} src={fileUrl(m)} className="h-16 rounded-lg" alt="" />)}</div></div>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {st === 'draft' && <><Button size="sm" onClick={() => act(r.id, 'issue')}>确认下发</Button><Button size="sm" variant="ghost" onClick={() => setEdit({ ...r })}>修改</Button></>}
                    {st === 'submitted' && <><Button size="sm" variant="green" onClick={() => act(r.id, 'close')}>验收关闭</Button><Button size="sm" variant="ghost" onClick={() => act(r.id, 'reject')}>退回</Button></>}
                    {st === 'issued' && r.work_order && <span className="text-xs text-ink-3">{r.work_order.escalation_level ? `已升级至第 ${r.work_order.escalation_level} 级` : '在时限内'}</span>}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )
      })}
      {!items.length && <Card className="p-6"><Empty text="还没有整改单" /></Card>}
      <Modal open={!!edit} onClose={() => setEdit(null)} title="修改整改单草稿">
        {edit && (
          <div className="space-y-3 text-sm">
            <label className="block">标题<input className="mt-1 h-10 w-full rounded-xl border px-3" value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></label>
            <label className="block">整改要求<textarea rows={5} className="mt-1 w-full rounded-xl border p-3" value={edit.requirement} onChange={(e) => setEdit({ ...edit, requirement: e.target.value })} /></label>
            <label className="block">责任人（系统建议：{edit.suggested_by_rule}）
              <select className="mt-1 h-10 w-full rounded-xl border px-3" value={edit.assignee_staff_id || ''} onChange={(e) => setEdit({ ...edit, assignee_staff_id: Number(e.target.value) })}>
                <option value="">请选择</option>{staff.map((s) => <option key={s.id} value={s.id}>{s.name}{s.note ? `（${s.note}）` : ''}</option>)}
              </select></label>
            <Button onClick={() => act(edit.id, 'update', { title: edit.title, requirement: edit.requirement, assignee_staff_id: edit.assignee_staff_id })}>保存</Button>
          </div>
        )}
      </Modal>
    </div>
  )
}

function InspectionList() {
  const [items, setItems] = useState<any[] | null>(null)
  const nav = useNavigate()
  useEffect(() => { api('/inspections?limit=80').then(setItems) }, [])
  if (!items) return <Spinner />
  return (
    <Card className="divide-y divide-cream-2">
      {items.map((i) => (
        <div key={i.id} className="flex flex-wrap items-center gap-3 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cream text-terra-500"><SegIcon seg={i.segment} /></div>
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{i.class_name}班 · {i.segment} — {i.text}</div>
            <div className="text-xs text-ink-3">{fmtTime(i.created_at)} · 提交人 {i.submitter} · 在岗 {i.on_duty.join('、') || '—'} {i.is_demo && '· 演示数据'}</div>
          </div>
          <div className="flex gap-1">{i.findings.map((f: any) => <VerdictBadge key={f.id} v={f.final_verdict} />)}{!i.findings.length && <Badge tone="green">无问题</Badge>}</div>
          {i.run_id && <Button size="sm" variant="ghost" onClick={() => nav(`/principal/arena?run=${i.run_id}`)}><IPlay size={14} />回放</Button>}
        </div>
      ))}
    </Card>
  )
}

function WorkOrders() {
  const [items, setItems] = useState<any[] | null>(null)
  const [status, setStatus] = useState<'open' | 'all'>('open')
  const toast = useToast()
  const load = () => api(`/work-orders?status=${status}`).then(setItems)
  useEffect(() => { load() }, [status])
  const TYPE: Record<string, string> = { review: '待复核', rectification: '整改单', acceptance: '待验收', appeal: '申诉', parent: '家长转人工' }
  return (
    <div>
      <Tabs value={status} onChange={setStatus} items={[{ value: 'open', label: '进行中' }, { value: 'all', label: '全部（含时间线）' }]} />
      <div className="mt-4 space-y-2">
        {!items ? <Spinner /> : items.map((w) => (
          <Card key={w.id} className="p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="gray">{TYPE[w.type] || w.type}</Badge>
              <span className="font-medium">{w.title}</span>
              {w.overdue && <Badge tone="red">已超时{w.escalation_level ? ` · ${w.escalation_level} 级升级` : ''}</Badge>}
              <span className="ml-auto text-sm text-ink-3">处理人 {w.assignee} · 截止 {fmtTime(w.due_at)}</span>
              {w.status === 'open' && w.extended_count === 0 && <Button size="sm" variant="ghost" onClick={async () => { await api(`/work-orders/${w.id}/extend`, { method: 'POST', json: { reason: '园长批准延期', hours: 8 } }); toast('已延期 8 个工作小时'); load() }}>批准延期</Button>}
            </div>
            {status === 'all' && <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-3">{w.events.map((e: any, i: number) => <span key={i}>{fmtTime(e.at)} {({ created: '创建', reminded: '过半提醒', escalated: '升级', extended: '延期', done: '完成', extend_request: '申请延期' } as any)[e.event] || e.event}{e.note ? `（${e.note}）` : ''} →</span>)}</div>}
          </Card>
        ))}
      </div>
    </div>
  )
}
