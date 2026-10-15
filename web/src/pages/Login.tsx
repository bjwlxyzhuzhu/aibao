import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Button, Spinner, cx } from '../components/ui'
import { useApp } from '../store'

export const homeOf = (role: string) => ({ principal: '/principal', staff: '/staff', admin: '/admin', parent: '/parent' } as Record<string, string>)[role] || '/'

export default function Login() {
  const [info, setInfo] = useState<any>(null)
  const [mode, setMode] = useState<'pw' | 'invite'>('pw')
  const [login, setLogin] = useState('')
  const [pw, setPw] = useState('')
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const app = useApp()
  const nav = useNavigate()
  useEffect(() => { api('/public/info').then(setInfo).catch(() => {}) }, [])
  const go = async (body: () => Promise<any>) => {
    setBusy(true); setErr('')
    try { const r = await body(); app.login(r.token, r.me); nav(homeOf(r.me.role)) } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const quick = (a: any) => {
    if (a.portal === 'parent') go(() => api('/auth/invite', { method: 'POST', json: { code: a.login } }))
    else go(() => api('/auth/login', { method: 'POST', json: { login: a.login, password: info.demo_password } }))
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(ellipse_at_top_right,#FFE6D6,transparent_55%),radial-gradient(ellipse_at_bottom_left,#E9F6DE,transparent_50%)] bg-cream p-4">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[32px] bg-white/80 shadow-2xl backdrop-blur md:grid-cols-2">
        <div className="relative hidden flex-col justify-between bg-gradient-to-br from-[#FFF1E6] to-[#FBE0D2] p-10 md:flex">
          <div className="flex items-center gap-3">
            <img src="/logo.png" className="h-16 w-16" alt="宝鸡幼儿园园徽" />
            <div><div className="text-2xl font-black text-brand-orange">宝鸡幼儿园</div><div className="text-[10px] font-bold tracking-[0.2em] text-brand-orange/80">BAO JI YOU ER YUAN</div></div>
          </div>
          <div>
            <div className="text-4xl font-black leading-tight">爱宝园务大脑</div>
            <div className="mt-2 text-lg text-ink-2">幼儿园保教治理"对抗—协同"多智能体系统</div>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">{['保教巡查链', '家园沟通链', '园务议事链', '脱敏网关', '园长在回路'].map((t) => <span key={t} className="rounded-full bg-white/80 px-3 py-1">{t}</span>)}</div>
          </div>
          <div className="flex items-end gap-2">
            <img src="/mascot/aibao.png" className="h-44 drop-shadow-xl" alt="爱宝" />
            <img src="/mascot/xingbao.png" className="h-48 drop-shadow-xl" alt="星宝" />
          </div>
        </div>
        <div className="p-7 sm:p-10">
          <div className="md:hidden mb-6 flex items-center gap-3"><img src="/logo.png" className="h-12" alt="" /><div><div className="font-black text-brand-orange">宝鸡幼儿园</div><div className="font-bold">爱宝园务大脑</div></div></div>
          <div className="text-2xl font-black">欢迎登录</div>
          <div className="mt-1 text-sm text-ink-3">{info?.calendar ? `${info.calendar.date} ${info.calendar.weekday} · ${info.calendar.semester || ''}${info.calendar.week_no ? ` 第${info.calendar.week_no}周（${info.calendar.parity_cn}）` : ''}` : ''}</div>
          <div className="mt-6 inline-flex rounded-full bg-cream-2 p-1 text-sm">
            <button onClick={() => setMode('pw')} className={cx('rounded-full px-4 py-1.5', mode === 'pw' && 'bg-white font-bold shadow')}>教职工 / 园长</button>
            <button onClick={() => setMode('invite')} className={cx('rounded-full px-4 py-1.5', mode === 'invite' && 'bg-white font-bold shadow')}>家长</button>
          </div>
          {mode === 'pw' ? (
            <form className="mt-5 space-y-3" onSubmit={(e) => { e.preventDefault(); go(() => api('/auth/login', { method: 'POST', json: { login, password: pw } })) }}>
              <input value={login} onChange={(e) => setLogin(e.target.value)} placeholder="账号（手机号或姓名）" className="h-12 w-full rounded-2xl border border-[#E9DCD0] bg-white px-4 outline-none focus:border-terra-300" />
              <input value={pw} onChange={(e) => setPw(e.target.value)} type="password" placeholder="密码" className="h-12 w-full rounded-2xl border border-[#E9DCD0] bg-white px-4 outline-none focus:border-terra-300" />
              <Button size="lg" className="w-full" disabled={busy}>{busy ? <Spinner /> : '登录'}</Button>
            </form>
          ) : (
            <form className="mt-5 space-y-3" onSubmit={(e) => { e.preventDefault(); go(() => api('/auth/invite', { method: 'POST', json: { code } })) }}>
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="班级邀请码" className="h-12 w-full rounded-2xl border border-[#E9DCD0] bg-white px-4 uppercase outline-none focus:border-terra-300" />
              <Button size="lg" className="w-full" disabled={busy}>{busy ? <Spinner /> : '进入爱宝答疑'}</Button>
            </form>
          )}
          {err && <div className="mt-3 rounded-xl bg-[#FDE7E4] px-3 py-2 text-sm text-[#B83227]">{err}</div>}
          {info?.demo_mode && (
            <div className="mt-8">
              <div className="text-xs text-ink-3">演示模式 · 一键体验（生产环境设置 DEMO_MODE=false 后隐藏）</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {info.demo_accounts.map((a: any) => <button key={a.login} onClick={() => quick(a)} className="rounded-full bg-terra-50 px-3 py-1.5 text-sm text-terra-700 hover:bg-terra-100">{a.label}</button>)}
              </div>
            </div>
          )}
          <div className="mt-8 text-[11px] leading-5 text-ink-3">私有化部署 · 所有云端调用经过脱敏网关 · AI 结论与整改单均由园长确认</div>
        </div>
      </div>
    </div>
  )
}
