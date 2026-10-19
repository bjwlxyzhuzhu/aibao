import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp, useSchool } from '../store'
import { cx } from './ui'
import { IBell, IBook, IChevron, IClip, IDB, IFile, IHome, ILogout, ISearch, ISettings, IShield, IUpload, IUsers, IClock, IPlay } from './icons'

export function Brand({ compact }: { compact?: boolean }) {
  const school = useSchool()
  return (
    <div className={cx('flex items-center', compact ? 'gap-2' : 'flex-col gap-1 text-center')}>
      <img src={school.logo} alt="标识" className={cx(compact ? 'h-9 w-9' : 'h-16 w-16', 'object-contain')} />
      <div className={compact ? 'leading-tight' : ''}>
        <div className={cx('font-black tracking-wide text-brand-orange', compact ? 'text-sm' : 'text-lg')}>{school.name}</div>
        {!compact && !school.anon && <div className="text-[9px] font-bold tracking-[0.18em] text-brand-orange/80">BAO JI YOU ER YUAN</div>}
        <div className={cx('font-bold text-ink', compact ? 'text-xs' : 'mt-1 text-[17px]')}>爱宝保教智囊团</div>
      </div>
    </div>
  )
}

type NavItem = { to: string; label: string; icon: ReactNode; end?: boolean }

const PRINCIPAL_NAV: NavItem[] = [
  { to: '/principal', label: '驾驶舱', icon: <IHome />, end: true },
  { to: '/principal/inspect', label: '保教巡查', icon: <ISearch /> },
  { to: '/principal/council', label: '园务议事', icon: <IUsers /> },
  { to: '/principal/arena', label: '对抗回放', icon: <IPlay /> },
  { to: '/principal/knowledge', label: '知识库', icon: <IBook /> },
]
const MENTOR_NAV: NavItem[] = [
  { to: '/mentor', label: '学生总览', icon: <IUsers />, end: true },
  { to: '/mentor/review', label: '记录评阅', icon: <IClip /> },
  { to: '/mentor/arena', label: '对抗回放', icon: <IPlay /> },
  { to: '/mentor/metrics', label: '成效数据', icon: <IFile /> },
  { to: '/mentor/knowledge', label: '知识库', icon: <IBook /> },
]
const ADMIN_NAV: NavItem[] = [
  { to: '/admin', label: '初始化向导', icon: <IHome />, end: true },
  { to: '/admin/import', label: '导入中心', icon: <IUpload /> },
  { to: '/admin/kb', label: '知识库', icon: <IBook /> },
  { to: '/admin/org', label: '组织与账号', icon: <IUsers /> },
  { to: '/admin/semester', label: '学期与任职', icon: <IClip /> },
  { to: '/admin/schedule', label: '作息与课表', icon: <IClock /> },
  { to: '/admin/settings', label: '模型与阈值', icon: <ISettings /> },
  { to: '/admin/logs', label: '脱敏日志', icon: <IShield /> },
  { to: '/admin/sla', label: '工单时限', icon: <IFile /> },
  { to: '/admin/brand', label: '形象与品牌', icon: <IDB /> },
]

export function DeskLayout({ kind }: { kind: 'principal' | 'admin' | 'mentor' }) {
  const { me, logout } = useApp()
  const nav = kind === 'principal' ? PRINCIPAL_NAV : kind === 'mentor' ? MENTOR_NAV : ADMIN_NAV
  const [notes, setNotes] = useState<{ id: number; title: string; read: boolean }[]>([])
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  useEffect(() => { api('/notifications').then(setNotes).catch(() => {}) }, [])
  const unread = notes.filter((n) => !n.read).length
  return (
    <div className="min-h-screen bg-cream lg:flex">
      <aside className="hidden lg:flex w-[210px] shrink-0 flex-col border-r border-[#F0E4D8] bg-[#FBF3EC]/80 px-3 py-6 sticky top-0 h-screen">
        <Brand />
        <nav className="mt-8 flex flex-col gap-1.5">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => cx('flex items-center gap-3 rounded-2xl px-4 py-3 text-[15px] transition',
                isActive ? 'bg-terra-500 text-white shadow-pill font-semibold' : 'text-ink-2 hover:bg-white/70')}>
              {n.icon}<span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto">
          {me?.role === 'principal' && (
            <button onClick={() => navigate('/staff')} className="mb-2 w-full rounded-xl px-3 py-2 text-left text-xs text-ink-3 hover:bg-white/70">切换到手机巡查端 →</button>
          )}
          <div className="flex items-center gap-2 rounded-2xl bg-white/70 p-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-terra-100 font-bold text-terra-600">{me?.name?.[0] || '园'}</div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate font-semibold">{me?.name}</div>
              <div className="truncate text-xs text-ink-3">{me?.positions?.join('、') || (me?.role === 'mentor' ? '高校导师' : '')}</div>
            </div>
            <button onClick={logout} title="退出登录" className="rounded-full p-1.5 text-ink-3 hover:bg-cream-2"><ILogout size={18} /></button>
          </div>
        </div>
      </aside>
      {/* 平板 / 手机顶栏 */}
      <div className="lg:hidden sticky top-0 z-30 flex items-center justify-between border-b border-[#F0E4D8] bg-cream/95 px-4 py-2 backdrop-blur">
        <Brand compact />
        <div className="flex gap-1 overflow-x-auto">
          {nav.slice(0, 5).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => cx('rounded-full px-3 py-1.5 text-xs whitespace-nowrap', isActive ? 'bg-terra-500 text-white' : 'text-ink-2')}>{n.label}</NavLink>
          ))}
        </div>
      </div>
      <main className="relative min-w-0 flex-1">
        <div className="absolute right-6 top-5 z-20 hidden lg:flex items-center gap-4">
          <div className="relative">
            <button onClick={() => { setOpen(!open); if (unread) api('/notifications/read', { method: 'POST' }).catch(() => {}) }}
              className="relative rounded-full p-2 text-ink hover:bg-white" aria-label="提醒">
              <IBell size={22} />
              {unread > 0 && <span className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full bg-[#E5483B] ring-2 ring-cream" />}
            </button>
            {open && (
              <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-white p-3 shadow-2xl">
                <div className="mb-2 text-sm font-semibold">站内提醒</div>
                {notes.length === 0 ? <div className="py-6 text-center text-sm text-ink-3">暂无提醒</div> :
                  notes.slice(0, 8).map((n) => <div key={n.id} className="border-t border-cream-2 py-2 text-sm">{n.title}</div>)}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-terra-100 to-terra-200 text-lg font-bold text-terra-600 ring-2 ring-white">{me?.name?.[0]}</div>
            <span className="text-[15px]">{me?.role === 'admin' ? '管理员' : me?.role === 'mentor' ? '高校导师' : me?.positions?.[0] || '园长'}</span>
            <IChevron size={16} className="rotate-90 text-ink-3" />
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
