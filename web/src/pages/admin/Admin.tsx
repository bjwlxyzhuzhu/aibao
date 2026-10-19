import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fileUrl, getToken, upload } from '../../api'
import { ICheck, IUpload } from '../../components/icons'
import { Badge, Button, Card, Spinner, Tabs, cx, fmtTime, useToast } from '../../components/ui'
import { useApp } from '../../store'

const Page = ({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) => (
  <div className="mx-auto max-w-[1200px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
    <h1 className="text-4xl font-black">{title}</h1>
    {sub && <div className="mt-1 text-ink-2">{sub}</div>}
    <div className="mt-6">{children}</div>
  </div>
)

const dl = async (path: string, name: string) => {
  const r = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  const b = await r.blob()
  const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = name; a.click()
}

export function Wizard() {
  const [steps, setSteps] = useState<any[] | null>(null)
  const nav = useNavigate()
  const toast = useToast()
  useEffect(() => { api('/admin/setup-wizard').then(setSteps) }, [])
  const links = ['/admin/brand', '/admin/org', '/admin/import', '/admin/import', '/admin/schedule', '/admin/brand', '/admin/kb', '/admin/settings']
  return (
    <Page title="初始化向导" sub="首次部署按顺序完成；管理员不写代码，只用导入中心，30 分钟内完成">
      <div className="grid gap-3 md:grid-cols-2">
        {!steps ? <Spinner /> : steps.map((s, i) => (
          <Card key={i} className="flex cursor-pointer items-center gap-4 p-4 hover:-translate-y-0.5 transition" onClick={() => nav(links[i])}>
            <div className={cx('flex h-10 w-10 items-center justify-center rounded-full font-bold', s.done ? 'bg-brand-green text-white' : 'bg-cream-2 text-ink-3')}>{s.done ? <ICheck /> : i + 1}</div>
            <div className="flex-1 font-medium">{s.step}</div>
            <Badge tone={s.done ? 'green' : 'amber'}>{s.done ? '已完成' : '待完成'}</Badge>
          </Card>
        ))}
      </div>
      <Card className="mt-6 p-5">
        <div className="font-bold">演示数据</div>
        <div className="mt-1 text-sm text-ink-2">演示数据带"演示"标记，只用于录屏前的界面展示；真实试用数据产生后，驾驶舱自动切换为真实数据。参赛证据只使用真实数据。</div>
        <div className="mt-3 flex gap-2">
          <Button variant="ghost" onClick={async () => { const r = await api('/admin/demo/clear', { method: 'POST' }); toast(`已清除 ${r.removed_inspections} 条演示巡查`) }}>清除演示数据</Button>
          <Button variant="soft" onClick={async () => { toast('正在生成…'); await api('/admin/demo/seed', { method: 'POST' }); toast('已重新生成演示数据') }}>重新生成演示数据</Button>
        </div>
      </Card>
    </Page>
  )
}

const KINDS = [
  { k: 'all', label: '整本模板（人员 + 校历 + 作息 + 课表）', accept: '.xlsx' },
  { k: 'staff', label: '人员名单与班级任职', accept: '.xlsx' },
  { k: 'calendar', label: '校历周次与值周', accept: '.xlsx' },
  { k: 'routine', label: '作息时段', accept: '.xlsx' },
  { k: 'course', label: '特色课表（单双周）', accept: '.xlsx' },
  { k: 'children', label: '幼儿名册', accept: '.xlsx' },
  { k: 'logo', label: '园徽', accept: 'image/*' },
  { k: 'mascot', label: '吉祥物 / 智能体形象', accept: 'image/*' },
]

export function ImportCenter() {
  const [kind, setKind] = useState('all')
  const [file, setFile] = useState<File | null>(null)
  const [report, setReport] = useState<any>(null)
  const [jobs, setJobs] = useState<any[]>([])
  const [eff, setEff] = useState('')
  const [agent, setAgent] = useState('aibao')
  const [view, setView] = useState('front')
  const [strip, setStrip] = useState(false)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const loadJobs = () => api('/admin/import/jobs').then(setJobs)
  useEffect(() => { loadJobs() }, [])
  const send = async () => {
    if (!file) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('kind', kind); fd.append('file', file); fd.append('agent', agent); fd.append('view', view); fd.append('strip_bg', String(strip))
      setReport(await upload('/admin/import/upload', fd))
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  const commit = async () => {
    const r = await api(`/admin/import/${report.job_id}/commit`, { method: 'POST', json: { effective_from: eff || null } })
    toast('已确认生效')
    setReport({ ...report, committed: r.result })
    loadJobs()
  }
  const cur = KINDS.find((x) => x.k === kind)!
  return (
    <Page title="导入中心" sub="下载模板 / 选图片 → 上传 → 校验报告（红 / 黄 / 绿）→ 预览 → 确认生效 → 版本可回滚">
      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => dl('/admin/import/templates', '爱宝保教智囊团_管理员导入模板_2026秋.xlsx')}>下载导入模板</Button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
            {KINDS.map((x) => (
              <button key={x.k} onClick={() => { setKind(x.k); setReport(null); setFile(null) }}
                className={cx('rounded-2xl p-3 text-left text-sm', kind === x.k ? 'bg-terra-500 text-white shadow-pill' : 'bg-cream text-ink-2')}>{x.label}</button>
            ))}
          </div>
          {kind === 'mascot' && (
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <select value={agent} onChange={(e) => setAgent(e.target.value)} className="h-9 rounded-xl border px-2">
                {['aibao', 'xingbao', 'humiao', 'mingli', 'xiaobu', 'weishi', 'xiaoyi', 'xiaoshi', 'xiaojia', 'xiaodun'].map((a) => <option key={a}>{a}</option>)}
              </select>
              <select value={view} onChange={(e) => setView(e.target.value)} className="h-9 rounded-xl border px-2">
                {['front', 'side', 'back', 'happy', 'cheer', 'doubt', 'surprised', 'sad', 'sleep', 'angry', 'support', 'bye'].map((a) => <option key={a}>{a}</option>)}
              </select>
            </div>
          )}
          {(kind === 'logo' || kind === 'mascot') && <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={strip} onChange={(e) => setStrip(e.target.checked)} />自动去白底</label>}
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl border-2 border-dashed border-terra-200 p-5">
            <IUpload className="text-terra-400" />
            <input type="file" accept={cur.accept} onChange={(e) => { setFile(e.target.files?.[0] || null); setReport(null) }} className="text-sm" />
            <Button disabled={!file || busy} onClick={send}>{busy ? <Spinner /> : null}上传并校验</Button>
          </div>
          {report && (
            <div className="mt-5 space-y-3">
              <div className="font-bold">校验报告 · 版本 v{report.version}</div>
              {report.red.map((m: string, i: number) => <div key={'r' + i} className="rounded-xl bg-[#FDE7E4] px-3 py-2 text-sm text-[#B83227]">✖ {m}</div>)}
              {report.yellow.map((m: string, i: number) => <div key={'y' + i} className="rounded-xl bg-[#FFF2DB] px-3 py-2 text-sm text-[#8A5A00]">⚠ {m}</div>)}
              {report.green.map((m: string, i: number) => <div key={'g' + i} className="rounded-xl bg-[#E6F6EA] px-3 py-2 text-sm text-[#0E7A2F]">✔ {m}</div>)}
              <Preview kind={kind} p={report.preview} />
              {report.committed ? (
                <div className="rounded-xl bg-[#E6F6EA] p-3 text-sm">已生效：{JSON.stringify(report.committed)}
                  {report.committed.password_file && <Button size="sm" variant="ghost" className="ml-2" onClick={() => dl(`/admin/import/password-file/${report.committed.password_file}`, report.committed.password_file)}>下载初始密码表</Button>}</div>
              ) : report.ok && (
                <div className="flex flex-wrap items-center gap-2">
                  {['staff', 'calendar', 'course', 'all'].includes(kind) && <label className="text-sm">自某日起生效 <input type="date" value={eff} onChange={(e) => setEff(e.target.value)} className="h-9 rounded-xl border px-2" /></label>}
                  <Button variant="green" onClick={commit}>确认生效</Button>
                  {['staff', 'all'].includes(kind) && <span className="text-xs text-ink-3">班级任职导入后仍需园长确认</span>}
                </div>
              )}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <div className="font-bold">导入历史与版本</div>
          <div className="mt-3 space-y-2">
            {jobs.map((j) => (
              <div key={j.id} className="rounded-xl bg-cream p-3 text-sm">
                <div className="flex items-center gap-2"><b>{KINDS.find((x) => x.k === j.kind)?.label || j.kind}</b><span className="text-ink-3">v{j.version}</span>
                  <Badge tone={j.status === 'committed' ? 'green' : j.status === 'rolled_back' ? 'gray' : 'amber'} className="ml-auto">{({ committed: '已生效', rolled_back: '已回滚', validated: '待确认' } as any)[j.status]}</Badge></div>
                <div className="mt-1 text-xs text-ink-3">{j.filename} · {fmtTime(j.created_at)} · 红 {j.red} / 黄 {j.yellow}</div>
                {j.status === 'committed' && <button className="mt-1 text-xs text-terra-600 hover:underline" onClick={async () => { if (confirm('整体回滚这次导入？')) { await api(`/admin/import/${j.id}/rollback`, { method: 'POST' }); toast('已回滚'); loadJobs() } }}>回滚</button>}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Page>
  )
}

function Preview({ kind, p }: { kind: string; p: any }) {
  if (!p) return null
  if (kind === 'logo' && p.paths) return (
    <div className="flex flex-wrap items-end gap-4 rounded-2xl bg-white p-4">
      <div className="text-sm">取色：{p.palette.map((c: string) => <span key={c} className="mr-1 inline-block h-5 w-5 rounded-full align-middle" style={{ background: c }} title={c} />)}</div>
      <div className="text-xs text-ink-3">已生成 4 种尺寸，确认后各端顶栏、登录页、浏览器图标、PDF 页眉同步更换</div>
    </div>
  )
  return (
    <div className="grid gap-2 text-sm md:grid-cols-3">
      {p.staff_count != null && <div className="rounded-xl bg-white p-3">教职工 <b>{p.staff_count}</b> 人</div>}
      {p.classes && <div className="rounded-xl bg-white p-3">班级 <b>{p.classes.length}</b> 个：{p.classes.join('、')}</div>}
      {p.weeks && <div className="rounded-xl bg-white p-3">校历 <b>{p.weeks.length}</b> 周（含跨假期合并周 {p.weeks.filter((w: any) => w.ranges.length > 1).length} 个）</div>}
      {p.routines && <div className="rounded-xl bg-white p-3">作息 <b>{p.routines.length}</b> 段，已确认 {p.routines.filter((r: any) => r.confirmed).length}</div>}
      {p.courses && <div className="rounded-xl bg-white p-3">课表格子 <b>{p.courses.length}</b> 个</div>}
      {p.children_count != null && <div className="rounded-xl bg-white p-3">幼儿 <b>{p.children_count}</b> 人</div>}
    </div>
  )
}

export function Org() {
  const [tab, setTab] = useState<'staff' | 'pos' | 'class'>('staff')
  const [staff, setStaff] = useState<any[] | null>(null)
  const [pos, setPos] = useState<any[] | null>(null)
  const [classes, setClasses] = useState<any[] | null>(null)
  const [q, setQ] = useState('')
  const [invites, setInvites] = useState<any[]>([])
  const toast = useToast()
  useEffect(() => { api('/admin/staff').then(setStaff); api('/admin/positions').then(setPos); api('/admin/classes').then(setClasses); api('/admin/invites').then(setInvites) }, [])
  return (
    <Page title="组织与账号" sub="四层管理架构 · 岗位 + 数据范围决定可见内容 · 一人多岗取并集">
      <Tabs value={tab} onChange={setTab} items={[{ value: 'staff', label: '人员与账号' }, { value: 'pos', label: '组织架构与岗位' }, { value: 'class', label: '班级与幼儿' }]} />
      {tab === 'staff' && (
        <Card className="mt-4 overflow-x-auto p-4">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索姓名" className="mb-3 h-9 rounded-full border px-4 text-sm" />
          <table className="w-full text-sm">
            <thead><tr className="text-left text-ink-3"><th className="py-2">姓名</th><th>登录账号</th><th>岗位</th><th>备注</th><th /></tr></thead>
            <tbody>
              {staff?.filter((s) => s.name.includes(q)).map((s) => (
                <tr key={s.id} className="border-t border-cream-2">
                  <td className="py-2 font-medium">{s.name}</td><td>{s.login}</td>
                  <td>{s.positions.map((p: string) => <Badge key={p} tone="gray" className="mr-1">{p}</Badge>)}</td>
                  <td className="text-ink-3">{s.note}</td>
                  <td className="text-right">
                    <select className="mr-2 h-8 rounded-lg border text-xs" defaultValue="" onChange={async (e) => { if (!e.target.value) return; await api('/admin/user-positions', { method: 'POST', json: { staff_id: s.id, position: e.target.value } }); toast('已授予岗位'); api('/admin/staff').then(setStaff) }}>
                      <option value="">+ 授予岗位</option>{pos?.map((p) => <option key={p.id}>{p.name}</option>)}
                    </select>
                    <button className="text-xs text-terra-600" onClick={async () => { const r = await api(`/admin/staff/${s.id}/reset-password`, { method: 'POST' }); alert(`账号 ${r.login} 新密码：${r.password}（首次登录强制修改）`) }}>重置密码</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {tab === 'pos' && (
        <div className="mt-4 space-y-4">
          {[['1', '第一层'], ['2', '第二层'], ['3', '第三层'], ['4', '第四层'], ['class', '班级岗位'], ['special', '专任教师'], ['admin', '系统']].map(([t, label]) => (
            <Card key={t} className="p-4">
              <div className="mb-2 font-bold">{label}</div>
              <div className="flex flex-wrap gap-2">{pos?.filter((p) => p.tier === t).map((p) => (
                <div key={p.id} className="rounded-xl bg-cream px-3 py-2 text-sm"><b>{p.name}</b><span className="ml-1 text-xs text-ink-3">{p.portal} · {p.scope}</span>
                  <div className="text-xs text-ink-2">{p.holders.length ? `${p.holders.slice(0, 6).join('、')}${p.holders.length > 6 ? ` 等 ${p.holders.length} 人` : ''}` : '暂无人员（待导入）'}</div></div>
              ))}</div>
            </Card>
          ))}
        </div>
      )}
      {tab === 'class' && (
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {classes?.map((c) => (
            <Card key={c.id} className="p-4">
              <div className="flex items-center justify-between"><b className="text-lg">{c.name}班</b><Badge tone="gray">{({ big: '大班', middle: '中班', small: '小班' } as any)[c.grade]}</Badge></div>
              <div className="mt-1 text-xs text-ink-3">{c.children ?? '—'} 人（男 {c.boys ?? '—'} / 女 {c.girls ?? '—'}）{c.from_roster ? '· 名册统计' : '· 参考人数'}</div>
              <div className="mt-2 space-y-0.5 text-sm">{c.staff.map((s: any) => (
                <div key={s.id}>{s.name} <span className="text-xs text-ink-3">{({ teacher: '班级教师', care: '保育员', vice_lead: '副班长' } as any)[s.slot]}{s.is_lead ? '·班长' : ''}{s.shift ? `·${s.shift === 'mon_wed_fri' ? '一三五早班' : '二四早班'}` : ''}</span></div>
              ))}</div>
              <button className="mt-2 text-xs text-terra-600" onClick={async () => { const r = await api(`/admin/invites?class_id=${c.id}`, { method: 'POST' }); toast(`家长邀请码：${r.code}`); api('/admin/invites').then(setInvites) }}>生成家长邀请码</button>
              <div className="text-xs text-ink-3">{invites.filter((i) => i.class_name === c.name).map((i) => i.code).join('、')}</div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}

export function SemesterPage() {
  const { me } = useApp()
  const [sems, setSems] = useState<any[]>([])
  const [sel, setSel] = useState<number | null>(null)
  const [rows, setRows] = useState<any[] | null>(null)
  const [swapShift, setSwapShift] = useState(false)
  const toast = useToast()
  const load = async () => { const s = await api('/admin/semesters'); setSems(s); if (!sel && s[0]) setSel(s[0].id) }
  useEffect(() => { load() }, [])
  useEffect(() => { if (sel) api(`/admin/semesters/${sel}/assignments`).then(setRows) }, [sel])
  const s = sems.find((x) => x.id === sel)
  return (
    <Page title="学期与班级任职" sub="任职按学期保存，历史不覆盖；巡查和整改按发生时的任职归属责任">
      <div className="flex flex-wrap items-center gap-2">
        {sems.map((x) => <button key={x.id} onClick={() => setSel(x.id)} className={cx('rounded-full px-4 py-1.5 text-sm', sel === x.id ? 'bg-terra-500 text-white' : 'bg-white')}>{x.name}（{x.status}）</button>)}
        <label className="ml-auto flex items-center gap-1 text-sm"><input type="checkbox" checked={swapShift} onChange={(e) => setSwapShift(e.target.checked)} />早班也互换</label>
        <Button variant="soft" onClick={async () => { const r = await api(`/admin/semesters/next/assignments?swap_shift=${swapShift}`, { method: 'POST' }); toast(`已生成 ${r.semester} 草案 ${r.rows} 条，提交园长确认`); await load() }}>按惯例互换 → 生成下学期草案</Button>
      </div>
      {s && (
        <Card className="mt-4 p-4">
          <div className="font-bold">校历 · {s.name}（{s.start} 至 {s.end}）</div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">{s.weeks.map((w: any) => (
            <span key={w.no} className={cx('rounded-lg px-2 py-1', w.parity === 'single' ? 'bg-terra-50 text-terra-700' : 'bg-[#E7F0FC] text-[#2160B8]')} title={w.ranges.map((r: string[]) => r.join('~')).join('，')}>
              第{w.no}周{w.ranges.length > 1 ? '*' : ''} {w.parity === 'single' ? '单' : '双'}</span>
          ))}</div>
          <div className="mt-1 text-xs text-ink-3">* 跨假期合并周；单双周按校历周次判定，不按日期推算</div>
        </Card>
      )}
      <Card className="mt-4 overflow-x-auto p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="font-bold">班级任职表</div>
          {me?.role === 'principal' && sel && <Button size="sm" variant="green" onClick={async () => { await api(`/admin/semesters/${sel}/assignments/confirm`, { method: 'POST' }); toast('已确认生效'); api(`/admin/semesters/${sel}/assignments`).then(setRows) }}>园长确认生效</Button>}
        </div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-ink-3"><th className="py-2">班级</th><th>姓名</th><th>岗位</th><th>早班</th><th>本学期角色</th><th>状态</th></tr></thead>
          <tbody>{rows?.map((r) => (
            <tr key={r.id} className={cx('border-t border-cream-2', r.not_rotated && 'bg-[#FFF5E6]')}>
              <td className="py-1.5">{r.class_name}</td><td>{r.name}{r.is_lead && <Badge tone="terra" className="ml-1">班长</Badge>}</td>
              <td>{({ teacher: '班级教师', care: '保育员', vice_lead: '副班长' } as any)[r.slot]}</td>
              <td>{r.shift === 'mon_wed_fri' ? '一三五' : r.shift === 'tue_thu' ? '二四' : '—'}</td>
              <td>{({ teaching: '教学', care: '保育' } as any)[r.teaching_role] || '—'}{r.not_rotated && <Badge tone="amber" className="ml-1">未轮换</Badge>}</td>
              <td><Badge tone={r.status === 'confirmed' ? 'green' : 'amber'}>{r.status === 'confirmed' ? '已确认' : '草案'}</Badge></td>
            </tr>
          ))}</tbody>
        </table>
      </Card>
    </Page>
  )
}

const COURSE_COLOR: Record<string, string> = {
  足球: 'bg-[#E6F6EA] text-[#0E6B2B]', 篮球: 'bg-[#FFF0E0] text-[#A85300]', 体技: 'bg-[#E7F0FC] text-[#1F5AA8]',
  户外搭建: 'bg-[#FFF6D6] text-[#8A6A00]', 大型玩具: 'bg-[#FDE9F0] text-[#A3345C]', 科发: 'bg-[#F0EAFB] text-[#5B3BA0]',
  晨练: 'bg-[#E3F5F3] text-[#0F6E66]', 集体教育: 'bg-cream-2 text-ink-2', 体能循环: 'bg-[#EAF2DC] text-[#4C6B16]', 教研: 'bg-[#EEEEEE] text-ink-3',
}

export function SchedulePage() {
  const [routines, setRoutines] = useState<any[]>([])
  const [courses, setCourses] = useState<any[]>([])
  const [wt, setWt] = useState<'single' | 'double'>('double')
  const toast = useToast()
  const load = () => { api('/admin/routines').then(setRoutines); api('/admin/special-courses').then(setCourses) }
  useEffect(() => { load() }, [])
  const days = [1, 2, 3, 4, 5]
  const slots = Array.from(new Set(courses.filter((c) => c.week_type === wt).map((c) => `${c.start}-${c.end}`))).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
  return (
    <Page title="作息与课表" sub="巡查环节预选与在岗教师推算的依据；家长端只用已确认的作息回答">
      <Card className="p-4">
        <div className="font-bold">作息时段（2026 秋）</div>
        <div className="mt-2 divide-y divide-cream-2">{routines.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="w-24 tabular-nums">{r.start}–{r.end}</span><span className="flex-1">{r.segment}</span><Badge tone="gray">{r.segment_key}</Badge>
            <span className="text-xs text-ink-3">{r.source}</span>
            {r.confirmed ? <Badge tone="green">已确认</Badge> : <button onClick={async () => { await api(`/admin/routines/${r.id}?confirmed=true`, { method: 'PATCH' }); toast('已确认'); load() }}><Badge tone="amber">待确认 · 点此确认</Badge></button>}
          </div>
        ))}</div>
      </Card>
      <Card className="mt-4 overflow-x-auto p-4">
        <div className="flex items-center gap-3"><div className="font-bold">单双周特色课表</div><Tabs value={wt} onChange={setWt} items={[{ value: 'single', label: '单周' }, { value: 'double', label: '双周' }]} /></div>
        <table className="mt-3 w-full text-xs">
          <thead><tr><th className="w-24" />{days.map((d) => <th key={d} className="py-1">周{'一二三四五'[d - 1]}</th>)}</tr></thead>
          <tbody>{slots.map((s) => (
            <tr key={s} className="border-t border-cream-2 align-top">
              <td className="py-2 font-medium">{s}</td>
              {days.map((d) => (
                <td key={d} className="p-1">{courses.filter((c) => c.week_type === wt && c.weekday === d && `${c.start}-${c.end}` === s).map((c, i) => (
                  <div key={i} className={cx('mb-1 rounded-lg px-1.5 py-1', COURSE_COLOR[c.course] || 'bg-cream')}><b>{c.class_name}</b> {c.course}<div className="opacity-70">{c.teacher || '班级教师'}</div></div>
                ))}</td>
              ))}
            </tr>
          ))}</tbody>
        </table>
      </Card>
    </Page>
  )
}

export function Settings() {
  const [s, setS] = useState<any>(null)
  const [test, setTest] = useState<any>(null)
  const toast = useToast()
  useEffect(() => { api('/admin/settings').then(setS) }, [])
  if (!s) return <Page title="模型与阈值"><Spinner /></Page>
  const save = async () => { await api('/admin/settings', { method: 'PUT', json: { llm_base_url: s.llm_base_url, agent_models: s.agent_models, agent_thinking: s.agent_thinking, thresholds: s.thresholds } }); toast('已保存') }
  const NAMES: Record<string, string> = { aibao: '爱宝（调度/答疑/综合）', xingbao: '星宝（巡查诊断员）', humiao: '护苗（一线质询员）', mingli: '明理（条款裁判员）', xiaobu: '小步（整改跟踪员）', weishi: '小卫士（红队）', xiaoyi: '小医（保健视角）', xiaoshi: '小师（教师视角）', xiaojia: '小家（家长视角）', xiaodun: '小盾（安全视角）' }
  return (
    <Page title="模型与阈值" sub="密钥只存服务器环境变量（.env），不进前端、不进代码包">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <div className="font-bold">模型接口</div>
          <label className="mt-3 block text-sm">Base URL（OpenAI 兼容）<input className="mt-1 h-10 w-full rounded-xl border px-3" value={s.llm_base_url} onChange={(e) => setS({ ...s, llm_base_url: e.target.value })} /></label>
          <div className="mt-2 text-sm">API Key：{s.api_key_set ? <Badge tone="green">已在服务器配置</Badge> : <Badge tone="amber">未配置 · 当前使用离线规则引擎</Badge>}</div>
          <div className="mt-1 text-sm text-ink-3">强模型 {s.model_strong} · 快模型 {s.model_fast}</div>
          <Button size="sm" variant="ghost" className="mt-3" onClick={async () => setTest(await api('/admin/llm/test', { method: 'POST' }))}>连通测试</Button>
          {test && <div className={cx('mt-2 rounded-xl p-2 text-xs', test.ok ? 'bg-[#E6F6EA]' : 'bg-[#FDE7E4]')}>{test.ok ? `连通成功：${JSON.stringify(test.reply)}` : `失败：${test.error}`}</div>}
        </Card>
        <Card className="p-5">
          <div className="font-bold">阈值与对抗轮数</div>
          <label className="mt-3 block text-sm">复核置信度阈值（低于则转园长）<input type="number" step="0.05" min="0" max="1" className="mt-1 h-10 w-full rounded-xl border px-3" value={s.thresholds.review_confidence} onChange={(e) => setS({ ...s, thresholds: { ...s.thresholds, review_confidence: Number(e.target.value) } })} /></label>
          <label className="mt-2 block text-sm">对抗最大轮数<input type="number" min="1" max="2" className="mt-1 h-10 w-full rounded-xl border px-3" value={s.thresholds.debate_rounds} onChange={(e) => setS({ ...s, thresholds: { ...s.thresholds, debate_rounds: Number(e.target.value) } })} /></label>
          <label className="mt-2 block text-sm">必须复核的类别（逗号分隔）<input className="mt-1 h-10 w-full rounded-xl border px-3" value={s.thresholds.force_review_categories.join(',')} onChange={(e) => setS({ ...s, thresholds: { ...s.thresholds, force_review_categories: e.target.value.split(/[,，]/).filter(Boolean) } })} /></label>
        </Card>
        <Card className="p-5 lg:col-span-2">
          <div className="font-bold">每个智能体的模型与深度思考</div>
          <div className="mt-1 text-xs text-ink-3">深度思考默认关闭：关闭后单次调用约快 3 倍，巡查链 60 秒内出结论；判断要求高的岗位可单独开启</div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">{Object.entries(s.agent_models).map(([a, t]) => (
            <div key={a} className="flex items-center justify-between rounded-xl bg-cream px-3 py-2 text-sm"><span>{NAMES[a] || a}</span>
              <span className="flex items-center gap-2">
                <label className="flex items-center gap-1 text-xs text-ink-2"><input type="checkbox" checked={!!s.agent_thinking?.[a]} onChange={(e) => setS({ ...s, agent_thinking: { ...s.agent_thinking, [a]: e.target.checked } })} />深度思考</label>
                <select value={t as string} onChange={(e) => setS({ ...s, agent_models: { ...s.agent_models, [a]: e.target.value } })} className="h-8 rounded-lg border px-2"><option value="max">max</option><option value="flash">flash</option></select>
              </span></div>
          ))}</div>
          <Button className="mt-4" onClick={save}>保存设置</Button>
        </Card>
        <Card className="p-5 lg:col-span-2">
          <div className="font-bold">最近模型调用</div>
          <div className="mt-2 space-y-1 text-xs">{s.calls.length === 0 ? <div className="text-ink-3">暂无云端调用</div> : s.calls.map((c: any, i: number) => (
            <div key={i} className="flex gap-3"><span>{fmtTime(c.at)}</span><span>{c.agent}</span><span>{c.model}</span><span>{c.latency_ms}ms</span><Badge tone={c.ok ? 'green' : 'red'}>{c.ok ? 'OK' : '失败'}</Badge><span className="truncate text-ink-3">{c.error}</span></div>
          ))}</div>
        </Card>
      </div>
    </Page>
  )
}

export function Logs() {
  const [logs, setLogs] = useState<any[] | null>(null)
  const [media, setMedia] = useState<any[]>([])
  useEffect(() => { api('/admin/redaction-logs').then(setLogs); api('/admin/media-logs').then(setMedia) }, [])
  return (
    <Page title="脱敏对比日志" sub="每次模型调用前的脱敏前后对比、替换项、人脸数；只有管理员可看，保留 180 天">
      <Card className="p-4">
        <div className="font-bold">照片打码记录</div>
        <div className="mt-2 flex flex-wrap gap-3">{media.filter((m) => m.redacted).slice(0, 12).map((m) => (
          <div key={m.id} className="text-center text-xs"><img src={fileUrl(m.redacted)} className="h-20 w-28 rounded-lg object-cover" alt="" /><div>人脸 {m.faces}</div></div>
        ))}{!media.length && <span className="text-sm text-ink-3">暂无照片</span>}</div>
      </Card>
      <div className="mt-4 space-y-2">{logs?.map((l) => (
        <Card key={l.id} className="p-3 text-sm">
          <div className="flex flex-wrap gap-2 text-xs text-ink-3"><span>{fmtTime(l.created_at)}</span><Badge tone="gray">{l.agent}</Badge><span>call {l.call_id}</span>
            {l.replacements.map((r: any, i: number) => <Badge key={i} tone="amber">{r.from_type} → {r.to}</Badge>)}</div>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            <div className="rounded-lg bg-[#FDF0EC] p-2"><div className="text-[10px] text-ink-3">脱敏前（园内）</div><div className="line-clamp-3 whitespace-pre-wrap">{l.before}</div></div>
            <div className="rounded-lg bg-[#E6F6EA] p-2"><div className="text-[10px] text-ink-3">发往模型</div><div className="line-clamp-3 whitespace-pre-wrap">{l.after}</div></div>
          </div>
        </Card>
      ))}</div>
    </Page>
  )
}

export function Sla() {
  const [rows, setRows] = useState<any[]>([])
  const toast = useToast()
  useEffect(() => { api('/admin/sla-policies').then(setRows) }, [])
  return (
    <Page title="工单时限与升级规则" sub="只算校历内工作日 7:30–18:00；夜间不推送，次日 7:30 统一提醒；改动只对新建工单生效">
      <Card className="overflow-x-auto p-4">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-ink-3"><th className="py-2">规则</th><th>时限（工作分钟）</th><th>提醒时点</th><th>升级对象</th></tr></thead>
          <tbody>{rows.map((r, i) => (
            <tr key={r.id} className="border-t border-cream-2">
              <td className="py-2">{r.label}</td>
              <td><input type="number" className="h-8 w-24 rounded-lg border px-2" value={r.duration_minutes} onChange={(e) => { const x = [...rows]; x[i] = { ...r, duration_minutes: Number(e.target.value) }; setRows(x) }} /></td>
              <td><input type="number" step="0.1" className="h-8 w-20 rounded-lg border px-2" value={r.remind_ratio} onChange={(e) => { const x = [...rows]; x[i] = { ...r, remind_ratio: Number(e.target.value) }; setRows(x) }} /></td>
              <td className="text-xs text-ink-2">一级：{(r.escalation.l1 || []).join('、')}{r.escalation.l2 ? `；二级：${r.escalation.l2.join('、')}` : ''}</td>
            </tr>
          ))}</tbody>
        </table>
        <Button className="mt-3" onClick={async () => { await api('/admin/sla-policies', { method: 'PUT', json: rows.map((r) => ({ id: r.id, duration_minutes: r.duration_minutes, remind_ratio: r.remind_ratio })) }); toast('已保存') }}>保存</Button>
      </Card>
    </Page>
  )
}

export function BrandPage() {
  const { avatars } = useApp()
  const nav = useNavigate()
  return (
    <Page title="形象与品牌" sub="园徽与吉祥物只作展示，不进入任何模型调用；真人形象须附本人授权书">
      <Card className="flex flex-wrap items-center gap-6 p-5">
        <img src="/logo.png" className="h-24" alt="园徽" />
        <div><div className="text-2xl font-black text-brand-orange">实践基地园</div><div className="mt-1 flex gap-2">{['#019E33', '#C4EA03', '#F56D01', '#D46A47'].map((c) => <span key={c} className="flex items-center gap-1 text-xs"><i className="h-5 w-5 rounded-full" style={{ background: c }} />{c}</span>)}</div></div>
        <Button className="ml-auto" variant="soft" onClick={() => nav('/admin/import')}>上传 / 替换园徽与形象</Button>
      </Card>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {Object.entries(avatars?.agents || {}).map(([k, a]) => (
          <Card key={k} className="p-4">
            <div className="flex items-center gap-2"><b style={{ color: a.color }}>{a.name}</b><span className="text-sm text-ink-3">{a.role}</span></div>
            <div className="mt-2 flex flex-wrap gap-2">{Object.entries(avatars?.images?.[k] || {}).map(([v, u]) => (
              <div key={v} className="text-center text-[10px] text-ink-3"><img src={u} className="h-14 w-14 rounded-xl bg-cream object-contain" alt={v} />{v}</div>
            ))}</div>
          </Card>
        ))}
      </div>
    </Page>
  )
}
