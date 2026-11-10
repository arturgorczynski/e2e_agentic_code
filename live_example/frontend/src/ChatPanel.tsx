import { useEffect, useRef, useState } from 'react'
import { Bot, GitBranch, MessageSquare, Plus, Search, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api, post, type Persona, type Snapshot, type Thread } from './api'
import { ConversationActions } from './ConversationActions'

export function ChatPanel({ persona }: { persona: Persona }) {
  const storageKey = `acme-chat:${persona.kind}:${persona.subject_id}`
  const [thread, setThread] = useState<string | null>(null)
  const [threads, setThreads] = useState<Thread[]>([])
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [text, setText] = useState('')
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const pending = useRef<{ text: string; thread: string | null; id: string } | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const running = busy || Boolean(snapshot && ['queued', 'running'].includes(snapshot.status))
  const current = threads.find(row => row.id === thread)

  useEffect(() => {
    let active = true
    api<Thread[]>('/conversations').then(rows => {
      if (!active) return
      const available = rows.filter(row => row.status === 'active')
      setThreads(available)
      const saved = localStorage.getItem(storageKey)
      setThread(previous => previous && available.some(row => row.id === previous) ? previous : saved === 'draft' ? null : available.find(row => row.id === saved)?.id ?? available[0]?.id ?? null)
      setReady(true)
    }).catch(err => { if (active) { setError(err.message); setReady(true) } })
    return () => { active = false }
  }, [storageKey, revision])

  useEffect(() => {
    if (!ready) return
    localStorage.setItem(storageKey, thread ?? 'draft')
    setSnapshot(null)
    if (!thread) return
    let active = true
    const load = () => api<Snapshot>(`/conversations/${thread}`).then(data => { if (active) setSnapshot(data) }).catch(err => { if (active) setError(err.message) })
    void load()
    const timer = window.setInterval(load, 2500)
    return () => { active = false; window.clearInterval(timer) }
  }, [thread, ready, storageKey])

  useEffect(() => { bottom.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [snapshot?.chat.length])

  async function send() {
    if (!text.trim() || running || !ready) return
    setBusy(true); setError('')
    if (!pending.current || pending.current.text !== text || pending.current.thread !== thread) pending.current = { text, thread, id: crypto.randomUUID() }
    try {
      const sent = await post<{ thread_id: string }>('/chat', { text, thread_id: thread, submission_id: pending.current.id })
      localStorage.setItem(storageKey, sent.thread_id)
      setThread(sent.thread_id); setText(''); pending.current = null
      setSnapshot(await api<Snapshot>(`/conversations/${sent.thread_id}`))
      setRevision(value => value + 1)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  function newChat() { setThread(null); setSnapshot(null); setText(''); setError(''); localStorage.setItem(storageKey, 'draft') }
  function inspect(id: string) { window.dispatchEvent(new CustomEvent('acme:inspect', { detail: id })) }

  return <div className="chat-workspace">
    <section className="chat-panel" aria-label="Assistant conversation">
      <div className="chat-head"><div className="chat-icon"><Bot size={21}/></div><div><strong>{current?.title ?? 'New conversation'}</strong><small>{persona.display_name} · {persona.kind === 'customer' ? 'Your Acme assistant' : 'Acme operations agent'}</small></div>{current && <ConversationActions id={current.id} title={current.title} archived={false} disabled={running} changed={() => setRevision(value => value + 1)}/>}</div>
      {thread && <button className="chat-inspect" onClick={() => inspect(thread)}><GitBranch size={15}/> See how this answer was made <span>Open execution →</span></button>}
      <div className="messages" aria-live="polite">{!snapshot?.chat.length && <div className="empty-chat"><Bot size={32}/><strong>A fresh conversation</strong><p>Ask about {persona.kind === 'customer' ? 'your account' : 'company records'}. Follow the evidence behind each answer.</p><button className="button button-small" onClick={() => setText(persona.kind === 'customer' ? 'Call my_profile and show my current address.' : 'Find order DEMO-ORD-002.')}>Try a record lookup</button></div>}
        {snapshot?.chat.map((message, index) => <div key={index} className={`message ${message.role}`}><span>{message.role === 'assistant' ? 'Acme assistant' : 'You'}</span><div><ReactMarkdown>{message.content}</ReactMarkdown></div></div>)}
        {running && <div className="thinking"><span className="spinner"/>Agent is working…</div>}<div ref={bottom}/>
      </div>
      {snapshot?.error && <p className="notice" role="alert">{snapshot.error}</p>}{error && <p className="notice" role="alert">{error}</p>}
      <div className="chat-compose"><textarea aria-label="Message" value={text} maxLength={8000} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }} placeholder="Ask Acme a question…" rows={3}/><button disabled={running || !ready || !text.trim()} onClick={() => void send()} aria-label="Send message"><Send size={18}/></button></div><small className="chat-footnote">Enter to send · Shift + Enter for a new line</small>
    </section>
    <aside className="chat-history" aria-label="Chat history"><div className="history-heading"><MessageSquare size={18}/><h3>Your conversations</h3></div><button className="button button-dark new-chat" disabled={busy} onClick={newChat}><Plus size={16}/> New conversation</button>
      <label className="history-search"><Search size={15}/><input aria-label="Search chats" placeholder="Search chats" value={search} onChange={e => setSearch(e.target.value)}/></label>
      <div className="history-list">{threads.filter(row => row.title.toLowerCase().includes(search.toLowerCase())).map(row => <div className={`history-item ${thread === row.id ? 'selected' : ''}`} key={row.id}><button className="history-select" disabled={busy} onClick={() => { setThread(row.id); setText(''); setError(''); pending.current = null }}><strong>{row.title}</strong><small>{new Date(row.updated_at).toLocaleDateString()}</small></button><ConversationActions id={row.id} title={row.title} archived={false} disabled={running && thread === row.id} changed={() => setRevision(value => value + 1)}/></div>)}{!threads.length && <p className="quiet-message">Your chats appear here after the first message.</p>}</div>
      <button className="history-footer" onClick={() => window.dispatchEvent(new CustomEvent('acme:inspect', { detail: null }))}>All conversations & trash →</button>
    </aside>
  </div>
}
