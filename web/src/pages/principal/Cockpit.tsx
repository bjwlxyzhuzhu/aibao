import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api'
import { IAlert, IArrow, IChevron, IClip, IFile, ISend, IShield } from '../../components/icons'
import { HEAT, SegIcon, heatColor } from '../../components/segments'
import { Badge, Button, Card, Mascot, Modal, Ring, Spinner, Tabs, cx, fmtTime, pct } from '../../components/ui'

type Dash = any

export default function Cockpit() {
  const [d, setD] = useState<Dash | null>(null)
  const [range, setRange] = useState<'today' | 'week' | 'semester'>('week')
  const [source, setSource] = useState<'auto' | 'real' | 'demo'>('auto')
  const nav = useNavigate()
  useEffect(() => {
    let alive = true
    const load = () => api(`/dashboard?range=${range}&source=${source}`).then((x) => alive && setD(x)).catch(() => {})
    load()
    const t = setInterval(load, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [range, source])
  if (!d) return <div className="flex h-screen items-center justify-center text-ink-3"><Spinner /> 正在加载驾驶舱…</div>
  const k = d.kpi
  const max = Math.max(1, ...d.heatmap.values.flat())
  const cal = d.calendar
  return (
    <div className="mx-auto max-w-[1320px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
      {/* 标题区 */}
      <div className="relative flex flex-col gap-6 xl:flex-row">
        <div className="flex-1">
          <h1 className="text-4xl font-black tracking-tight text-ink lg:text-[56px] lg:leading-[1.1]">今日园务，一目了然</h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[15px] text-ink-2 lg:text-lg">
            <span>{cal.date.replace(/^(\d+)-(\d+)-(\d+)$/, (_: string, y: string, m: string, dd: string) => `${y}年${+m}月${+dd}日`)}</span>
            <span>{cal.weekday}</span><span className="text-ink-3">|</span>
            <span>{cal.semester?.replace('秋', ' 秋季学期')}{cal.week_no ? ` · 第${cal.week_no}周（${cal.parity_cn}）` : ''}</span>
            <span className="text-ink-3">|</span>
            {d.data_source === 'demo' ? <Badge tone="terra" className="text-sm">演示数据</Badge> : <Badge tone="green" className="text-sm">真实试用数据</Badge>}
            <Badge tone={d.engine === 'llm' ? 'blue' : 'gray'}>{d.engine === 'llm' ? '通义千问 · 在线' : '离线规则引擎'}</Badge>
          </div>
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Kpi tile="bg-terra-500" icon={<IClip size={30} className="text-white" />} value={String(k.inspections_today).padStart(2, '0')} label="今日巡查" hint="今天提交的巡查条数" />
            <Kpi tile="bg-[#EFA35C]" icon={<IFile size={30} className="text-white" />} value={String(k.pending_review).padStart(2, '0')} label="待复核" hint="安全卫生健康类与低置信度条目，100% 由园长复核" onClick={() => nav('/principal/inspect?tab=review')} />
            <Card className="flex items-center gap-5 p-5">
              <Ring value={k.closure_rate ?? 0}><span /></Ring>
              <div>
                <div className="text-4xl font-black">{pct(k.closure_rate)}<span className="text-xl">%</span></div>
                <div className="mt-1 text-ink-2" title="已关闭整改单 / 已下发整改单">整改闭环率 <span className="text-xs text-ink-3">({k.rect_closed}/{k.rect_issued})</span></div>
              </div>
            </Card>
          </div>
        </div>
        <div className="pointer-events-none hidden xl:block w-[260px] shrink-0">
          <img src="/mascot/aibao.png" alt="爱宝" className="mx-auto mt-6 w-[230px] drop-shadow-xl animate-[float_5s_ease-in-out_infinite]" />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* 热力图 */}
        <Card className="min-w-0 p-5 lg:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-2xl font-black">问题分布</div>
              <div className="mt-1 text-ink-2">颜色越深，问题越多 · 环节 × {d.heatmap.classes.length} 个班</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Tabs value={range} onChange={setRange} items={[{ value: 'today', label: '今日' }, { value: 'week', label: '本周' }, { value: 'semester', label: '本学期' }]} />
              <select value={source} onChange={(e) => setSource(e.target.value as any)} className="h-9 rounded-full border border-[#E9DCD0] bg-white px-3 text-sm">
                <option value="auto">自动（有真实数据时用真实）</option><option value="real">只看真实试用数据</option><option value="demo">演示数据</option>
              </select>
            </div>
          </div>
          <div className="mt-5 overflow-x-auto rounded-2xl bg-[#FBF7F3] p-3">
            <table className="w-full border-separate" style={{ borderSpacing: 5 }}>
              <thead>
                <tr>
                  <th className="w-20" />
                  {d.heatmap.classes.map((c: string) => <th key={c} className="min-w-[26px] text-center text-[13px] font-medium text-ink-2">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {d.heatmap.segments.map((s: string, i: number) => (
                  <tr key={s}>
                    <td className="whitespace-nowrap pr-2 text-[15px] font-medium"><span className="inline-flex items-center gap-2"><SegIcon seg={s} />{s}</span></td>
                    {d.heatmap.values[i].map((v: number, j: number) => (
                      <td key={j} title={`${d.heatmap.classes[j]}班 · ${s}：${v} 条`}
                        className="h-11 rounded-lg text-center text-xs font-semibold transition hover:scale-105 hover:ring-2 hover:ring-terra-300"
                        style={{ background: heatColor(v, max), color: v / max > 0.55 ? '#fff' : 'transparent' }}>{v || ''}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center gap-3 text-sm text-ink-2">
            <span>巡查情况</span><span>少</span>
            {HEAT.slice(0, 5).map((c) => <span key={c} className="h-6 w-8 rounded-md" style={{ background: c }} />)}
            <span>多</span>
            <span className="ml-auto text-ink-3">统计：{d.kpi.inspections} 次巡查 · {d.kpi.issues} 条问题</span>
          </div>
        </Card>

        {/* 待复核 */}
        <Card className="flex min-w-0 flex-col p-5 lg:p-6">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-black">待复核事项 ({d.kpi.pending_review})</div>
            <button onClick={() => nav('/principal/inspect?tab=review')} className="flex items-center text-sm text-ink-2 hover:text-terra-600">全部 <IChevron size={16} /></button>
          </div>
          <div className="mt-3 flex-1 divide-y divide-[#F2E8DE]">
            {d.pending.length === 0 && <div className="py-10 text-center text-ink-3">暂时没有待复核事项 🎉</div>}
            {d.pending.slice(0, 4).map((p: any) => (
              <button key={p.id} onClick={() => nav(`/principal/inspect?tab=review&f=${p.id}`)} className="flex w-full items-center gap-4 py-4 text-left hover:bg-cream/60">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-terra-50 text-terra-500"><SegIcon seg={p.segment} size={26} /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-[16px] font-bold">{p.item}</span>
                    <Badge tone="terra">待复核</Badge>
                  </div>
                  <div className="mt-1 text-sm text-ink-3">{fmtTime(p.created_at)} · {p.class_name}班 · {p.category}</div>
                </div>
                <IChevron className="text-ink-3" />
              </button>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3 rounded-2xl bg-gradient-to-r from-terra-50 to-[#FFF6F0] p-3">
            <img src="/mascot/aibao-mini.png" className="h-16 w-16 object-contain" alt="" />
            <div>
              <div className="text-lg font-black text-terra-600">爱宝提醒</div>
              <div className="text-[15px]">今日有 <b className="text-2xl text-terra-500">{d.kpi.pending_review}</b> 项待您复核{k.rect_drafts ? `，${k.rect_drafts} 张整改单待确认` : ''}。</div>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 flex justify-center">
        <Button size="lg" className="w-full max-w-sm" onClick={() => nav('/principal/inspect?tab=review')}>查看待复核 <IArrow /></Button>
      </div>

      {/* 第二屏：证据与运营指标 */}
      <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
        <Card className="p-5">
          <div className="flex items-center gap-2 font-bold"><IShield size={18} className="text-terra-500" />对抗前后误判率</div>
          <div className="mt-1 text-xs text-ink-3">以园长复核结论为标准答案，已复核 {d.accuracy.reviewed} 条</div>
          <div className="mt-4 space-y-3">
            <Bar label="诊断员单独判断" v={d.accuracy.solo_error_rate} color="#E99A7E" />
            <Bar label="对抗后裁定" v={d.accuracy.adversarial_error_rate} color="#5C7A2E" />
          </div>
          <div className="mt-3 text-xs text-ink-3">另有 {d.accuracy.adversarial_deferred} 条由裁判主动转园长，不计入误判</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 font-bold"><IAlert size={18} className="text-terra-500" />工单时限</div>
          <div className="mt-3 flex items-end gap-6">
            <div><div className={cx('text-3xl font-black', d.kpi.overdue ? 'text-[#C9402F]' : '')}>{d.kpi.overdue}</div><div className="text-xs text-ink-3">超时工单</div></div>
            <div><div className="text-3xl font-black">{pct(d.kpi.ontime_rate)}<span className="text-base">%</span></div><div className="text-xs text-ink-3">按时完成率</div></div>
          </div>
          <div className="mt-3 space-y-1 text-sm">
            {d.sla.overdue.slice(0, 3).map((w: any) => (
              <div key={w.id} className="flex items-center gap-2 truncate"><Badge tone={w.level >= 2 ? 'red' : 'amber'}>{w.level >= 2 ? '二级' : w.level ? '一级' : '超时'}</Badge><span className="truncate">{w.title}</span></div>
            ))}
            {!d.sla.overdue.length && <div className="text-ink-3">没有超时工单</div>}
          </div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 font-bold"><ISend size={18} className="text-terra-500" />家长端 · 爱宝答疑</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <Stat v={`${pct(d.parent.auto_rate)}%`} l="自动答复率" />
            <Stat v={d.parent.blocked} l="红队拦截" />
            <Stat v={d.parent.transferred} l="转教师" />
          </div>
          <div className="mt-3 text-xs text-ink-3">高频问题：{d.parent.top.slice(0, 3).map((t: any) => t.q).join(' / ') || '暂无'}</div>
        </Card>
        <Card className="p-5">
          <div className="font-bold">待办提醒</div>
          <div className="mt-2 space-y-2 text-sm">
            <div className="flex justify-between"><span>人工复核占比</span><b>{pct(d.kpi.review_ratio)}%</b></div>
            <button onClick={() => nav('/principal/inspect?tab=rect')} className="flex w-full justify-between hover:text-terra-600"><span>整改单草稿待确认 →</span><b>{d.kpi.rect_drafts}</b></button>
            {d.reminders.map((r: any, i: number) => (
              <button key={i} onClick={() => nav(r.type === 'rotation' ? '/principal/semester' : '/principal/knowledge')}
                className="block w-full rounded-lg bg-[#FFF5E6] px-2 py-1.5 text-left text-[#8A5A00] hover:bg-[#FFEBCC]">{r.title} →</button>
            ))}
          </div>
        </Card>
      </div>
      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-2">
        <WeeklyReport />
        <Assistant />
      </div>
    </div>
  )
}

function Kpi({ tile, icon, value, label, hint, onClick }: { tile: string; icon: React.ReactNode; value: string; label: string; hint: string; onClick?: () => void }) {
  return (
    <Card className={cx('flex items-center gap-5 p-5', onClick && 'cursor-pointer hover:-translate-y-0.5 transition')} onClick={onClick}>
      <div className={cx('flex h-[76px] w-[76px] items-center justify-center rounded-2xl shadow-inner', tile)}>{icon}</div>
      <div>
        <div className="text-4xl font-black">{value}</div>
        <div className="mt-1 flex items-center gap-1 text-ink-2">{label}<span title={hint} className="cursor-help text-xs text-ink-3">ⓘ</span></div>
      </div>
    </Card>
  )
}

function Bar({ label, v, color }: { label: string; v: number | null; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm"><span>{label}</span><b>{v == null ? '—' : `${Math.round(v * 100)}%`}</b></div>
      <div className="mt-1 h-2.5 rounded-full bg-cream-2"><div className="h-full rounded-full" style={{ width: `${(v ?? 0) * 100}%`, background: color }} /></div>
    </div>
  )
}

const Stat = ({ v, l }: { v: any; l: string }) => (
  <div className="rounded-xl bg-cream p-2"><div className="text-xl font-black">{v}</div><div className="text-xs text-ink-3">{l}</div></div>
)

function WeeklyReport() {
  const [r, setR] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div><div className="font-bold">巡查周报</div><div className="text-xs text-ink-3">决策综合员爱宝自动生成 · AI 草稿，经园长确认</div></div>
        <Button size="sm" variant="soft" disabled={busy} onClick={async () => { setBusy(true); try { setR(await api('/reports/weekly', { method: 'POST' })); setOpen(true) } finally { setBusy(false) } }}>
          {busy ? <Spinner /> : null}生成本周周报
        </Button>
      </div>
      {r && <p className="mt-3 line-clamp-3 text-sm text-ink-2">{r.summary}</p>}
      <Modal open={open} onClose={() => setOpen(false)} title="本周巡查周报" wide>
        {r && (
          <div id="weekly-print" className="space-y-4 bg-white p-6 rounded-2xl">
            <div className="flex items-center gap-3 border-b pb-3"><img src="/logo.png" className="h-10" alt="" /><div><div className="font-black text-brand-orange">实践基地园</div><div className="text-xs text-ink-3">爱宝保教智囊团 · 巡查周报 · {fmtTime(r.generated_at)}</div></div>
              <Badge tone="amber" className="ml-auto">{r.note}</Badge></div>
            <p className="leading-7">{r.summary}</p>
            <div><div className="font-bold">重点</div><ul className="ml-5 list-disc text-sm">{r.highlights.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul></div>
            <div><div className="font-bold">下周建议</div><ul className="ml-5 list-disc text-sm">{r.suggestions.map((h: string, i: number) => <li key={i}>{h}</li>)}</ul></div>
            <div className="text-xs text-ink-3">数据来源：{r.data_source === 'demo' ? '演示数据' : '真实试用数据'} · 生成引擎：{r.engine === 'llm' ? '通义千问' : '离线规则引擎'} · 不含教师个人排名</div>
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => window.print()}>导出 PDF（打印）</Button></div>
      </Modal>
    </Card>
  )
}

function Assistant() {
  const [q, setQ] = useState('')
  const [items, setItems] = useState<{ q: string; a: string }[]>([])
  const [busy, setBusy] = useState(false)
  const ask = async (text: string) => {
    if (!text.trim()) return
    setBusy(true)
    try {
      const r = await api('/assistant/chat', { method: 'POST', json: { q: text } })
      setItems((x) => [...x, { q: text, a: r.answer }])
      setQ('')
    } finally { setBusy(false) }
  }
  return (
    <Card className="p-5">
      <div className="flex items-center gap-3"><Mascot agent="aibao" emotion="happy" size={40} /><div><div className="font-bold">问问爱宝</div><div className="text-xs text-ink-3">用自然语言问数据或制度条款</div></div></div>
      <div className="mt-3 max-h-48 space-y-2 overflow-auto text-sm">
        {items.map((it, i) => (
          <div key={i}><div className="text-right"><span className="inline-block rounded-2xl bg-terra-50 px-3 py-1.5">{it.q}</span></div>
            <div className="mt-1"><span className="inline-block rounded-2xl bg-cream px-3 py-1.5">{it.a}</span></div></div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {['这周哪个环节问题最多？', '午睡巡视间隔是多少？'].map((s) => <button key={s} onClick={() => ask(s)} className="rounded-full bg-cream-2 px-3 py-1 text-xs text-ink-2">{s}</button>)}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(q) }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="例如：这周哪个班问题最多" className="h-10 flex-1 rounded-full border border-[#E9DCD0] bg-white px-4 text-sm outline-none focus:border-terra-300" />
        <Button size="md" disabled={busy}>{busy ? <Spinner /> : '提问'}</Button>
      </form>
    </Card>
  )
}
