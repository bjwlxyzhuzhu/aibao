import { useEffect, useState } from 'react'
import { api, upload } from '../api'
import { IBook, ISearch, IUpload } from '../components/icons'
import { Badge, Button, Card, Modal, Spinner, fmtTime, useToast } from '../components/ui'

const KIND: Record<string, string> = { national: '国家文件', policy: '本园制度', experience: '本园经验', faq: 'FAQ / 公开' }

export default function Knowledge({ admin }: { admin?: boolean }) {
  const [docs, setDocs] = useState<any[] | null>(null)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<any[] | null>(null)
  const [view, setView] = useState<any>(null)
  const [up, setUp] = useState({ title: '', kind: 'policy', visibility: 'internal' })
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const load = () => api('/admin/kb/docs').then(setDocs)
  useEffect(() => { load() }, [])
  const doUpload = async () => {
    if (!file) return
    setBusy(true)
    const t0 = Date.now()
    try {
      const f = new FormData()
      f.append('file', file); f.append('title', up.title); f.append('kind', up.kind); f.append('visibility', up.visibility)
      const r = await upload('/admin/kb/docs', f)
      toast(`解析完成：${r.chunk_count} 个条款切片，用时 ${((Date.now() - t0) / 1000).toFixed(1)} 秒，已可被检索引用`)
      setFile(null); load()
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <div className="mx-auto max-w-[1200px] px-5 pb-16 pt-6 lg:px-8 lg:pt-10">
      <h1 className="text-4xl font-black">知识库</h1>
      <div className="mt-1 text-ink-2">PDF / Word → 按章、条切片（保留条款号）→ 智能体检索并引用；公开知识只给家长端爱宝使用</div>
      {admin && (
        <Card className="mt-5 p-5">
          <div className="flex items-center gap-2 font-bold"><IUpload size={18} />上传制度文件</div>
          <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_140px_140px_auto]">
            <input type="file" accept=".pdf,.doc,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] || null)} className="text-sm" />
            <input placeholder="标题（默认文件名）" value={up.title} onChange={(e) => setUp({ ...up, title: e.target.value })} className="h-10 rounded-xl border border-[#E9DCD0] px-3 text-sm" />
            <select value={up.kind} onChange={(e) => setUp({ ...up, kind: e.target.value })} className="h-10 rounded-xl border border-[#E9DCD0] px-2 text-sm">
              {Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={up.visibility} onChange={(e) => setUp({ ...up, visibility: e.target.value })} className="h-10 rounded-xl border border-[#E9DCD0] px-2 text-sm">
              <option value="internal">内部</option><option value="public">公开给家长</option>
            </select>
            <Button disabled={!file || busy} onClick={doUpload}>{busy ? <Spinner /> : null}上传解析</Button>
          </div>
          <div className="mt-2 text-xs text-ink-3">"本园经验"类文件须附本人书面同意书；文件只存园方服务器。</div>
        </Card>
      )}
      <Card className="mt-5 p-5">
        <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (q.trim()) setHits(await api(`/admin/kb/search?q=${encodeURIComponent(q)}`)) }}>
          <div className="relative flex-1"><ISearch className="absolute left-3 top-2.5 text-ink-3" size={18} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="检索条款，例如：午睡巡视间隔" className="h-10 w-full rounded-full border border-[#E9DCD0] pl-10 pr-4 text-sm" /></div>
          <Button>检索</Button>
        </form>
        {hits && (
          <div className="mt-4 space-y-2">
            {hits.length === 0 && <div className="text-sm text-ink-3">没有命中</div>}
            {hits.map((h) => (
              <div key={h.id} className="rounded-xl bg-[#FFFBF0] p-3 text-sm ring-1 ring-[#F0D9A8]">
                <div className="text-xs font-semibold text-[#A86400]">#{h.id}《{h.doc_title}》{h.clause_no} · 相关度 {h.score}</div>
                <div className="mt-1 whitespace-pre-wrap">{h.text}</div>
              </div>
            ))}
          </div>
        )}
      </Card>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {!docs ? <Spinner /> : docs.map((d) => (
          <Card key={d.id} className="cursor-pointer p-4 hover:-translate-y-0.5 transition" onClick={async () => setView({ ...d, chunks: await api(`/admin/kb/docs/${d.id}/chunks`) })}>
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-terra-50 text-terra-500"><IBook /></div>
              <div className="min-w-0 flex-1">
                <div className="font-bold">{d.title}</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <Badge tone="gray">{KIND[d.kind] || d.kind}</Badge>
                  <Badge tone={d.visibility === 'public' ? 'green' : 'gray'}>{d.visibility === 'public' ? '公开' : '内部'}</Badge>
                  <Badge tone={d.status === 'ready' ? 'green' : 'amber'}>{d.status === 'ready' ? `${d.chunk_count} 个切片` : d.status}</Badge>
                  {d.is_sample && <Badge tone="amber">示例，待替换</Badge>}
                </div>
                <div className="mt-1 text-xs text-ink-3">{fmtTime(d.created_at)}</div>
              </div>
              {admin && <button className="text-xs text-ink-3 hover:text-[#C23B2F]" onClick={async (e) => { e.stopPropagation(); if (confirm('删除该文件及其切片？')) { await api(`/admin/kb/docs/${d.id}`, { method: 'DELETE' }); load() } }}>删除</button>}
            </div>
          </Card>
        ))}
      </div>
      <Modal open={!!view} onClose={() => setView(null)} title={view?.title} wide>
        <div className="space-y-2">{view?.chunks?.map((c: any) => (
          <div key={c.id} className="rounded-xl bg-white p-3 text-sm"><div className="text-xs font-semibold text-terra-600">#{c.id} · {c.clause_no}</div><div className="mt-1 whitespace-pre-wrap">{c.text}</div></div>
        ))}</div>
      </Modal>
    </div>
  )
}
