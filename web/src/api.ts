// fetch + SSE 客户端
export type Me = {
  user_id: number
  login: string
  role: 'principal' | 'staff' | 'admin' | 'parent'
  name: string
  positions: string[]
  class_ids: number[]
  classes: string[]
  vice_class_ids: number[]
  scope: string
  must_change_password: boolean
  staff_id: number | null
}

const TOKEN_KEY = 'aibao_token'
export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}
export const setToken = (t: string) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, msg: string) { super(msg); this.status = status }
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) }
  const t = getToken()
  if (t) headers.Authorization = `Bearer ${t}`
  let body = opts.body
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.json)
  }
  const r = await fetch(`/api${path}`, { ...opts, headers, body })
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* */ }
    if (r.status === 401 && !path.startsWith('/auth')) { setToken(''); if (!location.pathname.startsWith('/login')) location.href = '/login' }
    throw new ApiError(r.status, msg)
  }
  const ct = r.headers.get('content-type') || ''
  return (ct.includes('json') ? r.json() : (r.text() as any)) as Promise<T>
}

export function upload<T = any>(path: string, form: FormData): Promise<T> {
  return api<T>(path, { method: 'POST', body: form })
}

export type AgentMsg = {
  id: number
  run_id: number
  round: number
  agent: string
  action: string
  target: string | null
  finding_id: string | null
  text: string
  cited_chunks: number[]
  confidence: number | null
  emotion: string
  content: any
  at: string
}

export function streamRun(runId: number, onMsg: (m: AgentMsg) => void, onDone: () => void): () => void {
  const es = new EventSource(`/api/runs/${runId}/stream?token=${encodeURIComponent(getToken())}`)
  es.onmessage = (e) => { try { onMsg(JSON.parse(e.data)) } catch { /* */ } }
  es.addEventListener('done', () => { es.close(); onDone() })
  es.onerror = () => { es.close(); onDone() }
  return () => es.close()
}

export const fileUrl = (u?: string | null) => (u ? `${u}${u.includes('?') ? '&' : '?'}token=${encodeURIComponent(getToken())}` : '')
