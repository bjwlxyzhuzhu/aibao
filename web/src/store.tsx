import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken, type Me } from './api'

type School = { name: string; logo: string; anon: boolean }

type Avatars = { agents: Record<string, { name: string; role: string; color: string }>; images: Record<string, Record<string, string>> }

type Ctx = {
  me: Me | null
  loading: boolean
  avatars: Avatars | null
  school: School
  login: (token: string, me: Me) => void
  logout: () => void
}

const DEFAULT_SCHOOL: School = { name: '实践基地园', logo: '/logo.png', anon: false }
const AppCtx = createContext<Ctx>({ me: null, loading: true, avatars: null, school: DEFAULT_SCHOOL, login: () => {}, logout: () => {} })

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [avatars, setAvatars] = useState<Avatars | null>(null)
  const [school, setSchool] = useState<School>(DEFAULT_SCHOOL)
  useEffect(() => {
    api('/public/info').then((i: any) => setSchool({ name: i.school, anon: !!i.anon, logo: i.anon ? '/mascot/aibao-mini.png' : '/logo.png' })).catch(() => {})
    api<Avatars>('/avatars').then(setAvatars).catch(() => {})
    if (!getToken()) { setLoading(false); return }
    api<Me>('/me').then(setMe).catch(() => setToken('')).finally(() => setLoading(false))
  }, [])
  return (
    <AppCtx.Provider value={{
      me, loading, avatars, school,
      login: (t, m) => { setToken(t); setMe(m) },
      logout: () => { setToken(''); setMe(null); location.href = '/login' },
    }}>{children}</AppCtx.Provider>
  )
}

export const useApp = () => useContext(AppCtx)

// 表情别名：PRD 6.3 状态 → 各角色已有表情文件
const EMO_FALLBACK: Record<string, string[]> = {
  cheer: ['cheer', 'happy', 'front'],
  support: ['support', 'love', 'happy'],
  surprised: ['surprised', 'doubt'],
  doubt: ['doubt', 'surprised'],
  sad: ['sad', 'please'],
  sleep: ['sleep'],
  angry: ['angry'],
  happy: ['happy', 'laugh', 'cheer'],
  bye: ['bye', 'hello', 'happy'],
  please: ['please', 'sad'],
  front: ['front', 'happy'],
}

export function useAvatar(agent: string, emotion = 'happy'): string {
  const { avatars } = useApp()
  const imgs = avatars?.images?.[agent]
  if (!imgs) return agent === 'xingbao' ? '/mascot/xingbao.png' : '/mascot/aibao-mini.png'
  for (const e of EMO_FALLBACK[emotion] || [emotion, 'happy']) if (imgs[e]) return imgs[e]
  return Object.values(imgs)[0]
}

export function avatarUrl(avatars: Avatars | null, agent: string, emotion = 'happy'): string {
  const imgs = avatars?.images?.[agent]
  if (!imgs) return '/mascot/aibao-mini.png'
  for (const e of EMO_FALLBACK[emotion] || [emotion, 'happy']) if (imgs[e]) return imgs[e]
  return Object.values(imgs)[0]
}

export const AGENT_FALLBACK: Record<string, { name: string; role: string; color: string }> = {
  aibao: { name: '爱宝', role: '调度官', color: '#E2603A' },
  xingbao: { name: '星宝', role: '巡查诊断员', color: '#2F7BE0' },
}

export const useSchool = () => useContext(AppCtx).school
