// 2D 对话流：手机端 / WebGL 不可用时的降级展示（头像 + 气泡）
import { useEffect, useRef } from 'react'
import type { AgentMsg } from '../api'
import { useApp, avatarUrl } from '../store'
import { Badge, cx } from './ui'

const ACTION_LABEL: Record<string, string> = {
  route: '调度', statement: '陈述', challenge: '质疑', support: '同意', verdict: '裁定', redteam: '红队审查', brief: '简报', state: '状态',
}

export default function ChatFlow({ messages, agents, compact, onChunk }: {
  messages: AgentMsg[]; agents: Record<string, { name: string; role: string; color: string }>; compact?: boolean; onChunk?: (id: number) => void
}) {
  const { avatars } = useApp()
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [messages.length])
  const visible = messages.filter((m, i) => m.action !== 'think' || i === messages.length - 1)
  return (
    <div className={cx('space-y-3', compact && 'text-sm')}>
      {visible.map((m) => {
        const a = agents[m.agent] || { name: m.agent, role: '', color: '#D46A47' }
        const target = m.target ? agents[m.target]?.name : null
        return (
          <div key={m.id} className="flex gap-2.5">
            <img src={avatarUrl(avatars, m.agent, m.action === 'think' ? 'doubt' : m.emotion)} alt={a.name}
              className="h-10 w-10 shrink-0 rounded-xl object-cover bg-cream-2" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <b style={{ color: a.color }}>{a.name}</b><span className="text-ink-3">{a.role.split(' ')[0]}</span>
                {m.action !== 'think' && <Badge tone={m.action === 'challenge' ? 'amber' : m.action === 'support' ? 'green' : m.action === 'verdict' ? 'red' : 'gray'}>{ACTION_LABEL[m.action] || m.action}</Badge>}
                {target && <span className="text-ink-3">→ {target}</span>}
                {m.round > 1 && <span className="text-ink-3">第 {m.round} 轮</span>}
              </div>
              {m.action === 'think' ? (
                <div className="mt-1 inline-flex gap-1 rounded-2xl bg-white px-3 py-2 shadow-sm">
                  {[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-terra-400" style={{ animationDelay: `${i * 0.15}s` }} />)}
                </div>
              ) : (
                <div className="mt-1 rounded-2xl rounded-tl-sm bg-white px-3 py-2 leading-6 shadow-sm" style={{ borderLeft: `3px solid ${a.color}` }}>
                  {m.text}
                  {m.cited_chunks?.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.cited_chunks.map((c) => (
                        <button key={c} onClick={() => onChunk?.(c)} className="rounded-full bg-[#FFF5DC] px-2 py-0.5 text-[11px] text-[#A86400] hover:underline">📖 条款 #{c}</button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
      <div ref={end} />
    </div>
  )
}
