import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { useAvatar } from '../store'

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

export function Card({ className, children, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('rounded-xl2 bg-white/90 shadow-card border border-[#F1E6DC]', className)} {...p}>{children}</div>
}

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'soft' | 'danger' | 'green'; size?: 'sm' | 'md' | 'lg' }
export function Button({ variant = 'primary', size = 'md', className, ...p }: BtnProps) {
  const v = {
    primary: 'bg-terra-500 text-white hover:bg-terra-600 shadow-pill',
    ghost: 'bg-white text-ink border border-[#E9DCD0] hover:bg-cream-2',
    soft: 'bg-terra-50 text-terra-600 hover:bg-terra-100',
    danger: 'bg-[#D9483B] text-white hover:bg-[#C23B2F]',
    green: 'bg-brand-green text-white hover:brightness-95',
  }[variant]
  const s = { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4', lg: 'h-14 px-8 text-lg' }[size]
  return <button className={cx('inline-flex items-center justify-center gap-2 rounded-full font-medium transition disabled:opacity-50 disabled:cursor-not-allowed', v, s, className)} {...p} />
}

export function Badge({ tone = 'terra', children, className }: { tone?: 'terra' | 'green' | 'blue' | 'amber' | 'red' | 'gray'; children: ReactNode; className?: string }) {
  const t = {
    terra: 'bg-terra-50 text-terra-600', green: 'bg-[#E6F6EA] text-[#0E7A2F]', blue: 'bg-[#E7F0FC] text-[#2160B8]',
    amber: 'bg-[#FFF2DB] text-[#A86400]', red: 'bg-[#FDE7E4] text-[#B83227]', gray: 'bg-cream-2 text-ink-2',
  }[tone]
  return <span className={cx('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', t, className)}>{children}</span>
}

// 状态色：成立 = 红，不成立 = 蓝，转园长 = 琥珀；同时配文字
export function VerdictBadge({ v }: { v: string }) {
  if (v === 'valid') return <Badge tone="red">● 成立</Badge>
  if (v === 'invalid') return <Badge tone="blue">○ 不成立</Badge>
  return <Badge tone="amber">◆ 转园长</Badge>
}

export const SEV_TONE: Record<string, 'red' | 'amber' | 'gray'> = { 高: 'red', 中: 'amber', 低: 'gray' }

export function Spinner({ className }: { className?: string }) {
  return <span className={cx('inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent', className)} />
}

export function Empty({ text, emotion = 'sleep' }: { text: string; emotion?: string }) {
  const src = useAvatar('aibao', emotion)
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-ink-3">
      <img src={src} className="h-20 w-20 rounded-2xl object-cover opacity-90" alt="" />
      <div className="text-sm">{text}</div>
    </div>
  )
}

export function Mascot({ agent, emotion = 'happy', size = 48, className, ring }: { agent: string; emotion?: string; size?: number; className?: string; ring?: string }) {
  const src = useAvatar(agent, emotion)
  return <img src={src} alt={agent} width={size} height={size} style={{ width: size, height: size, boxShadow: ring ? `0 0 0 3px ${ring}` : undefined }}
    className={cx('rounded-2xl object-cover bg-cream-2 shrink-0', className)} />
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; wide?: boolean }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30 p-0 sm:p-6" onClick={onClose}>
      <div className={cx('max-h-[92vh] w-full overflow-auto rounded-t-3xl sm:rounded-3xl bg-cream p-5 sm:p-6 shadow-2xl', wide ? 'sm:max-w-4xl' : 'sm:max-w-lg')}
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <div className="text-lg font-bold">{title}</div>
          <button onClick={onClose} className="rounded-full p-1 text-ink-3 hover:bg-cream-2" aria-label="关闭">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

const ToastCtx = createContext<(msg: string, tone?: 'ok' | 'err') => void>(() => {})
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string; tone: string }[]>([])
  const push = useCallback((msg: string, tone: 'ok' | 'err' = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((x) => [...x, { id, msg, tone }])
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed left-1/2 top-4 z-[60] flex -translate-x-1/2 flex-col gap-2">
        {items.map((i) => (
          <div key={i.id} className={cx('rounded-full px-4 py-2 text-sm text-white shadow-lg', i.tone === 'err' ? 'bg-[#C23B2F]' : 'bg-ink')}>{i.msg}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

export function Ring({ value, size = 76, stroke = 9, color = '#5C7A2E', track = '#EEF0E4', children }: { value: number; size?: number; stroke?: number; color?: string; track?: string; children?: ReactNode }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(1, value)))} style={{ transition: 'stroke-dashoffset .8s' }} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">{children}</div>
    </div>
  )
}

export const fmtTime = (s?: string | null) => {
  if (!s) return '—'
  const d = new Date(s)
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
export const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}`)

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode }[] }) {
  return (
    <div className="inline-flex rounded-full bg-cream-2 p-1">
      {items.map((i) => (
        <button key={i.value} onClick={() => onChange(i.value)}
          className={cx('rounded-full px-4 py-1.5 text-sm transition', value === i.value ? 'bg-white font-semibold text-terra-600 shadow' : 'text-ink-2 hover:text-ink')}>
          {i.label}
        </button>
      ))}
    </div>
  )
}
