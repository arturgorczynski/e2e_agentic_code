import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, MessageCircle, Terminal } from 'lucide-react'
import { api, post, type Persona, type RecordRow } from './api'

type Conversation = {
  id: string; title: string; topic: string; search_text: string; owner_id: string; owner_name: string; owner_kind: string
  subject_id: string; updated_at: string; message_count: number; run_count: number
  tools: string[]; status: string
}
type Snapshot = {
  chat: { role: string; content: string }[]; runs: RecordRow[]
  operations: { id: string; kind: string; payload_json: string }[]
  status: string; error: string | null; can_decide: boolean
}
type TraceEvent = { seq: number; kind: string; created_at: string; payload: RecordRow }
type EventPage = { events: TraceEvent[]; has_more: boolean; next_cursor: number | null }

export function Execution({ persona, choose }: { persona: Persona | null; choose: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [thread, setThread] = useState<string | null>(null)
  const [owner, setOwner] = useState('')
  const [topic, setTopic] = useState('')
  const [minLength, setMinLength] = useState('')
  const [maxLength, setMaxLength] = useState('')
  const [tool, setTool] = useState('')
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [cursor, setCursor] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [keyEventsOnly, setKeyEventsOnly] = useState(false)

  useEffect(() => {
    if (!persona) return
    let active = true
    api<Conversation[]>('/execution/conversations').then(rows => { if (active) { setConversations(rows); setError('') } })
      .catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [persona?.kind, persona?.subject_id, revision])
  useEffect(() => { setThread(null); setOwner(''); setTopic(''); setTool('') }, [persona?.kind, persona?.subject_id])
  useEffect(() => {
    if (!thread) { setSnapshot(null); setEvents([]); return }
    let active = true
    setLoading(true)
    api<Snapshot>(`/execution/conversations/${thread}`).then(value => { if (active) setSnapshot(value) })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [thread, revision])
  useEffect(() => {
    if (!thread) return
    let active = true
    api<EventPage>(`/execution/conversations/${thread}/events?after=${cursor}`).then(page => {
      if (active) {
        setEvents(previous => cursor === 0 ? page.events : [...previous, ...page.events])
        setHasMore(page.has_more)
      }
    }).catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [thread, cursor, revision])

  const owners = useMemo(() => [...new Map(conversations.map(item => [item.owner_id, item])).values()].sort((a, b) => a.owner_name.localeCompare(b.owner_name)), [conversations])
  const tools = useMemo(() => [...new Set(conversations.flatMap(item => item.tools))].sort(), [conversations])
  const filtered = conversations.filter(item =>
    (!owner || item.owner_id === owner) &&
    (!topic || `${item.title} ${item.search_text ?? ''}`.toLowerCase().includes(topic.toLowerCase())) &&
    (!minLength || item.message_count >= Number(minLength)) &&
    (!maxLength || item.message_count <= Number(maxLength)) &&
    (!tool || item.tools.includes(tool)))
  const shownEvents = keyEventsOnly ? events.filter(event => [
    'request_accepted', 'model_request', 'model_response', 'tool_attempt_started',
    'native_tool_started', 'native_tool_finished', 'native_tool_error',
    'tool_result', 'tool_error', 'tool_message', 'tool_attempt_finished',
    'sql', 'retrieval', 'document_read', 'approval_requested', 'approval_decided',
    'business_decision', 'run_completed', 'run_failed', 'model_error',
    'provider_error', 'retry', 'tool_selection_denied',
  ].includes(event.kind)) : events

  if (!persona) return <section className="content-section"><div className="empty-state"><Terminal size={36}/><h2>Inspect every conversation</h2><p>Choose a persona to inspect saved chats and recorded execution.</p><button className="button button-dark" onClick={choose}>Choose persona</button></div></section>

  async function decide(id: string, choice: 'approve' | 'reject') {
    if (!thread) return
    try {
      await post(`/conversations/${thread}/operations/${id}`, { decision: choice })
      setRevision(value => value + 1)
    } catch (err) { setError((err as Error).message) }
  }

  function selectThread(id: string) {
    setThread(id); setCursor(0); setEvents([]); setHasMore(false); setSnapshot(null)
  }

  return <section className="content-section"><div className="section-title"><span className="eyebrow">EXECUTION INSPECTOR</span><h2>From question to evidence.</h2><p>Internal personas can inspect all saved conversations. Customer personas see their own. Every unfiltered conversation appears below; long event histories have explicit pages.</p></div>
    {error && <div className="notice" role="alert">{error}</div>}
    <div className="execution-filters"><label>User<select value={owner} onChange={event => setOwner(event.target.value)}><option value="">All users</option>{owners.map(item => <option key={item.owner_id} value={item.owner_id}>{item.owner_name} · {item.subject_id || item.owner_kind}</option>)}</select></label><label>Topic<input value={topic} onChange={event => setTopic(event.target.value)} placeholder="Search conversation text"/></label><label>Messages from<input type="number" min="0" value={minLength} onChange={event => setMinLength(event.target.value)}/></label><label>to<input type="number" min="0" value={maxLength} onChange={event => setMaxLength(event.target.value)}/></label><label>Tool used<select value={tool} onChange={event => setTool(event.target.value)}><option value="">Any tool</option>{tools.map(name => <option key={name}>{name}</option>)}</select></label><button className="button button-small" onClick={() => { setOwner(''); setTopic(''); setMinLength(''); setMaxLength(''); setTool('') }}>Clear filters</button></div>
    <div className="execution-layout"><div className="thread-list"><h3>Conversations</h3><small className="execution-count">Showing {filtered.length} of {conversations.length}</small>{filtered.map(item => <button key={item.id} className={thread === item.id ? 'selected' : ''} onClick={() => selectThread(item.id)}><MessageCircle size={17}/><span><strong>{item.topic.slice(0, 95)}</strong><small>{item.owner_name} · {item.owner_kind} · {item.message_count} messages · {item.run_count} runs</small><small>{item.updated_at?.slice(0, 19)}{item.tools.length ? ` · ${item.tools.join(', ')}` : ''}</small></span></button>)}{!conversations.length && <p>No saved conversations yet.</p>}{conversations.length > 0 && !filtered.length && <p>No conversations match these filters.</p>}</div>
      <div className="execution-main">{!thread ? <div className="empty-state"><Terminal size={36}/><h3>Select a conversation</h3><p>Inspect the complete saved transcript and event timeline.</p></div> : <><div className="card"><div className="card-heading"><h3>Conversation</h3><span>{snapshot?.status}</span></div>{loading && <p>Loading transcript…</p>}{snapshot?.chat.map((message, index) => <div key={index} className="transcript-row"><small>{message.role === 'assistant' ? 'AGENT OUTPUT' : 'USER INPUT'}</small><p>{message.content}</p></div>)}{snapshot && <small>{snapshot.chat.length} stored chat messages · {snapshot.runs.length} runs</small>}</div><div className="card"><div className="card-heading"><h3>Recorded execution</h3><button className="button button-small" onClick={() => setKeyEventsOnly(!keyEventsOnly)}>{keyEventsOnly ? `Show all ${events.length} loaded events` : 'Key events only'}</button></div>{keyEventsOnly && <small>Showing {shownEvents.length} key events of {events.length} loaded. Change the toggle to see every event.</small>}{shownEvents.map(event => <details className="event-row" key={event.seq}><summary><span className={`event-dot ${event.kind}`}/><strong>{event.kind.replaceAll('_', ' ')}</strong><small>{event.created_at?.slice(0, 19)}</small></summary><pre>{JSON.stringify(event.payload, null, 2)}</pre></details>)}{!events.length && <p>No recorded events for this conversation.</p>}{hasMore && <button className="button button-small" onClick={() => setCursor(events[events.length - 1].seq)}>Load more events <ArrowRight size={15}/></button>}<small>{events.length} events loaded{hasMore ? ' · more available' : ' · complete'}</small></div>{snapshot?.operations.map(operation => <div className="card" key={operation.id}><h3>Pending approval · {operation.kind}</h3><pre>{operation.payload_json}</pre>{snapshot.can_decide && <div className="db-editor-actions"><button className="button button-dark" onClick={() => decide(operation.id, 'approve')}>Approve</button><button className="button button-small" onClick={() => decide(operation.id, 'reject')}>Reject</button></div>}</div>)}</>}</div>
    </div>
  </section>
}
