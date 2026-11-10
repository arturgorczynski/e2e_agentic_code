import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Bot, Check, ChevronRight, Database, GitBranch, Layers, MessageSquare, RefreshCw, Search, ShieldCheck, Trash2, Wrench } from 'lucide-react'
import { api, post, type Persona, type RecordRow } from './api'
import { ConversationActions } from './ConversationActions'
import { DataValue, Messages, type Message } from './StructuredData'
import { ContextData, SqlEvidence } from './ExecutionData'

type Conversation = { id: string; title: string; topic: string; search_text: string; owner_name: string; subject_id: string; status: string; run_count: number; tools: string[]; can_manage: boolean }
type Step = {
  id: string; run_id: string; kind: string; title: string; origin: string; number: number
  detail: { text?: string; restored_messages?: number; system_prompt?: string; input_messages?: Message[]; output_messages?: Message[]; tools?: RecordRow[]; arguments?: unknown; direct?: boolean; result?: unknown; settings?: unknown; input_changes?: unknown; input_state_changes?: { added: Message[]; changed: Message[]; removed: Message[] }; state_field_changes?: { values: RecordRow; removed: string[] } }
  evidence: { id: string; kind: string; payload: RecordRow }[]
  before: Message[]; after: Message[]; changes: { added: Message[]; changed: Message[]; removed: Message[] }
  context: RecordRow; state_fields: RecordRow; state_basis: string; sources: string[]; error?: unknown
}
type Run = { id: string; steps: Step[]; restored_messages: number }
type Flow = { runs: Run[]; event_count: number; conversation: { chat: { role: string; content: string }[]; runs: RecordRow[]; status: string; can_decide: boolean; operations: { id: string; kind: string; payload_json: string }[] } }

function StepIcon({ kind }: { kind: string }) {
  const Icon = kind === 'model' ? Bot : kind === 'tool' ? Wrench : kind === 'evidence' ? Database : kind === 'input' ? MessageSquare : Layers
  return <Icon size={18}/>
}

function StepDetail({ step, mode }: { step: Step; mode: 'changes' | 'state' | 'context' | 'input' }) {
  return <div className="step-detail-body">
    {step.error ? <div className="flow-error" role="alert"><strong>This step reported an error</strong><DataValue value={step.error}/></div> : null}
    {mode === 'context' ? <ContextData context={step.context}/> : mode === 'state' ? <>
      <div className="explain-card"><Layers size={18}/><div><strong>State after this step</strong><p>{step.before.length} → {step.after.length} messages · {step.state_basis}. This is the conversation's working history; runtime context is supplied separately.</p></div></div>
      <h4>state.messages · {step.after.length} messages</h4>
      <div className="message-legend"><span className="user-key">User</span><span className="model-key">Model</span><span className="tool-key">Tool result</span><span>New / Updated = changed in this step</span></div>
      <Messages messages={step.after} stateMessages={step.after} added={step.changes.added} changed={step.changes.changed} collapseEarlier/>
      {Object.keys(step.state_fields).length > 0 && <details className="detail-section"><summary>Other state fields · last captured at model input</summary><DataValue value={step.state_fields}/></details>}
    </> : mode === 'input' ? <>
      <div className="explain-card"><Bot size={18}/><div><strong>Exactly what the model received</strong><p>The request combines selected messages, the system instructions and offered tools. It can differ from saved graph state.</p></div></div>
      <details className="detail-section"><summary>System instructions · includes application profile</summary><DataValue value={step.detail.system_prompt}/></details>
      {step.detail.input_changes && <details className="detail-section"><summary>How this request differs from saved message state</summary><DataValue value={step.detail.input_changes}/></details>}
      <h4>Messages sent to this model call</h4><Messages messages={step.detail.input_messages ?? []}/>
      <details className="detail-section"><summary>Available tools · {step.detail.tools?.length ?? 0}</summary>{step.detail.tools?.map((tool, index) => <details className="tool-schema" key={index}><summary>{String(tool.name ?? 'Tool')}</summary><DataValue value={tool}/></details>)}</details>
      <details className="detail-section"><summary>Model settings</summary><DataValue value={step.detail.settings}/></details>
    </> : <>
      {step.kind === 'input' && <div className="explain-card"><MessageSquare size={18}/><div><strong>{step.detail.restored_messages ? `${step.detail.restored_messages} earlier messages restored` : 'A fresh thread: no earlier messages'}</strong><p>The user adds a message to this conversation's state.</p></div></div>}
      {step.kind === 'tool' && <><div className="explain-card"><Wrench size={18}/><div><strong>{step.detail.direct ? 'Direct invocation → Python tool' : 'Model arguments → Python tool'}</strong><p>{step.detail.direct ? 'This tool was called directly by the application. Its result does not add a model conversation message.' : 'The tool can also read runtime.context. Evidence below shows which records or documents it actually accessed.'}</p></div></div><h4>{step.detail.direct ? 'Arguments supplied by the caller' : 'Arguments supplied by the model'}</h4><DataValue value={step.detail.arguments} emptyObjectLabel="No arguments · {}"/>{step.detail.direct && step.detail.result !== undefined && <><h4>Returned result</h4><DataValue value={step.detail.result}/></>}</>}
      {step.kind === 'model' && <div className="explain-card"><Bot size={18}/><div><strong>{step.detail.input_messages?.length ?? 0} input messages + {step.detail.tools?.length ?? 0} offered tools</strong><p>Open Model input to inspect the complete request, including profile information added to the system instructions.</p></div></div>}
      {step.evidence.map(evidence => <details className="evidence-card" open key={evidence.id}><summary><Database size={16}/>{evidence.kind === 'sql' ? 'SQL · executed query' : evidence.kind.replaceAll('_', ' ')}</summary>{evidence.kind === 'sql' ? <SqlEvidence payload={evidence.payload} id={evidence.id}/> : <DataValue value={evidence.payload}/>}</details>)}
      {step.changes.added.length > 0 && <><h4 className="change-label added">Added to state · {step.changes.added.length} messages</h4><p className="quiet-message">Appended to state.messages. A tool result is one message containing the returned data.</p><Messages messages={step.changes.added} stateMessages={step.after} added={step.changes.added}/></>}
      {step.changes.changed.length > 0 && <><h4 className="change-label changed">Updated in state · {step.changes.changed.length}</h4><Messages messages={step.changes.changed}/></>}
      {step.changes.removed.length > 0 && <details className="detail-section"><summary>Removed from state · {step.changes.removed.length}</summary><Messages messages={step.changes.removed}/></details>}
      {step.detail.state_field_changes && (Object.keys(step.detail.state_field_changes.values).length > 0 || step.detail.state_field_changes.removed.length > 0) && <details className="detail-section" open><summary>Other state fields · changes since previous capture</summary><DataValue value={step.detail.state_field_changes}/></details>}
      {!['input', 'context', 'model', 'tool', 'evidence'].includes(step.kind) && <DataValue value={step.detail}/>}
      {step.kind === 'model' && !step.error && !step.detail.output_messages && <p className="quiet-message">No completed response has been recorded for this request yet.</p>}
    </>}
    {(mode === 'state' || mode === 'changes') && step.detail.input_state_changes && Object.values(step.detail.input_state_changes).some(messages => messages.length > 0) && <details className="detail-section" open><summary>State changes captured before this model call</summary>{Object.entries(step.detail.input_state_changes).filter(([, messages]) => messages.length > 0).map(([change, messages]) => <section key={change}><h4>{change} · {messages.length}</h4><Messages messages={messages}/></section>)}</details>}
    <details className="detail-section source-reference"><summary>Recorded sources · {step.sources.length} events</summary><p>These IDs link this view to the saved event log. The flow groups repeated framework notifications into one step.</p><DataValue value={step.sources}/></details>
  </div>
}

export function Execution({ persona, choose, initialThread = null }: { persona: Persona | null; choose: () => void; initialThread?: string | null }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [thread, setThread] = useState<string | null>(initialThread)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<'active' | 'archived' | 'all'>('active')
  const [flow, setFlow] = useState<Flow | null>(null)
  const [runId, setRunId] = useState('')
  const [stepId, setStepId] = useState('')
  const [mode, setMode] = useState<'changes' | 'state' | 'context' | 'input'>('changes')
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [owner, setOwner] = useState('')
  const [libraryVisible, setLibraryVisible] = useState(() => localStorage.getItem('acme-conversation-library') !== 'hidden')
  useEffect(() => {
    if (!persona) return
    let active = true
    api<Conversation[]>('/execution/conversations').then(rows => { if (active) { setConversations(rows); setError('') } }).catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [persona?.kind, persona?.subject_id, revision])
  useEffect(() => { setThread(initialThread); setFlow(null); setRunId(''); setStepId('') }, [initialThread, persona?.kind, persona?.subject_id])
  useEffect(() => {
    if (!thread) { setFlow(null); return }
    let active = true
    setLoading(true)
    api<Flow>(`/execution/conversations/${thread}/flow`).then(value => {
      if (!active) return
      setFlow(value); setRunId(previous => value.runs.some(run => run.id === previous) ? previous : value.runs[0]?.id ?? ''); setError('')
    }).catch(err => { if (active) setError(err.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [thread, revision])
  const current = conversations.find(item => item.id === thread)
  const run = flow?.runs.find(item => item.id === runId)
  const step = run?.steps.find(item => item.id === stepId) ?? run?.steps[0]
  const stepIndex = step ? run?.steps.findIndex(item => item.id === step.id) ?? 0 : 0
  const visible = conversations.filter(item => (status === 'all' || item.status === status) && (!owner || item.owner_name === owner) && `${item.title} ${item.search_text} ${item.subject_id}`.toLowerCase().includes(query.toLowerCase()))
  function pick(id: string) { setThread(id); setFlow(null); setRunId(''); setStepId(''); setMode('changes') }
  async function decide(id: string, decision: string) {
    try { await post(`/conversations/${thread}/operations/${id}`, { decision }); setRevision(v => v + 1) }
    catch (err) { setError((err as Error).message) }
  }
  if (!persona) return <section className="content-section"><div className="empty-state"><GitBranch size={38}/><h2>Conversations & execution</h2><p>Choose a persona to explore its saved conversations and follow the evidence.</p><button className="button button-dark" onClick={choose}>Choose persona</button></div></section>
  return <section className="content-section execution-page">
    <div className="experience-heading"><div><span className="eyebrow">CONVERSATIONS & EXECUTION</span><h2>Follow the answer.</h2><p>One step at a time. See what changed, where it came from, and what the model saw.</p></div><button className="button button-small" onClick={() => setRevision(v => v + 1)}><RefreshCw size={16}/> Refresh</button></div>
    {error && <p className="notice" role="alert">{error}</p>}
    <div className="inspection-toolbar"><button className="button button-small" aria-expanded={libraryVisible} aria-controls="conversation-library" onClick={() => { setLibraryVisible(!libraryVisible); localStorage.setItem('acme-conversation-library', libraryVisible ? 'hidden' : 'visible') }}><Search size={16}/>{libraryVisible ? 'Hide conversations' : 'Show conversations'}</button><div className="data-legend"><span><ShieldCheck size={15}/><strong>Context</strong> Application identity and access</span><span><Layers size={15}/><strong>State</strong> Messages and working data</span></div></div>
    <div className={`inspection-workspace ${libraryVisible ? '' : 'library-hidden'}`}>
      <aside id="conversation-library" className="conversation-library" hidden={!libraryVisible}><label className="history-search"><Search size={16}/><input aria-label="Search conversations" placeholder="Search name, message or ID" value={query} onChange={e => setQuery(e.target.value)}/></label>
        <div className="library-tabs" aria-label="Conversation status">{(['active', 'archived', 'all'] as const).map(value => <button className={status === value ? 'active' : ''} key={value} onClick={() => setStatus(value)}>{value === 'archived' ? <><Trash2 size={13}/> Trash</> : value === 'active' ? 'Active' : 'All'}</button>)}</div>
        {persona.kind !== 'customer' && <select aria-label="Conversation owner" value={owner} onChange={e => setOwner(e.target.value)}><option value="">All people</option>{[...new Set(conversations.map(c => c.owner_name))].map(name => <option key={name}>{name}</option>)}</select>}
        <small className="library-count">{visible.length} conversations</small>
        <div className="library-list">{visible.map(item => <div className={`library-item ${thread === item.id ? 'selected' : ''}`} key={item.id}><button className="library-select" onClick={() => pick(item.id)}><span className="library-item-title">{item.title}</span><small>{item.owner_name} · {item.run_count} turns</small>{item.status === 'archived' && <span className="trash-badge">In trash · history retained</span>}</button>{item.can_manage && <ConversationActions id={item.id} title={item.title} archived={item.status === 'archived'} changed={() => setRevision(v => v + 1)}/>}</div>)}{!visible.length && <p className="quiet-message">{status === 'archived' ? 'Trash is empty.' : 'No conversations match this view.'}</p>}</div>
      </aside>
      <div className="inspection-main">{!thread ? <div className="inspection-empty"><GitBranch size={48}/><h3>Choose a conversation</h3><p>Its execution becomes a clickable flow. Tool results stay beside their evidence; the message state grows as you move through it.</p><div className="empty-flow"><span>User</span><ArrowRight size={16}/><span>Model</span><ArrowRight size={16}/><span>Tool</span><ArrowRight size={16}/><span>Answer</span></div></div> : <>
        <div className="conversation-title"><div><h3>{current?.title ?? 'Conversation'}</h3><p>{current?.owner_name}{current?.status === 'archived' ? ' · In trash; messages and execution retained' : ''}</p></div>{current?.can_manage && <ConversationActions id={current.id} title={current.title} archived={current.status === 'archived'} changed={() => setRevision(v => v + 1)}/>}</div>
        {loading && <p className="quiet-message" role="status">Loading recorded execution…</p>}
        {flow && <>
          <details className="conversation-transcript"><summary><MessageSquare size={16}/> Read conversation · {flow.conversation.chat.length} messages</summary><Messages messages={flow.conversation.chat.map(m => ({ type: m.role === 'user' ? 'human' : 'ai', data: { content: m.content } }))}/></details>
          <div className="run-picker" aria-label="Conversation turns">{flow.runs.map((item, index) => <button key={item.id} className={runId === item.id ? 'selected' : ''} onClick={() => { setRunId(item.id); setStepId(''); setMode('changes') }}><span>Turn {index + 1}</span><small>{item.steps.find(s => s.kind === 'input')?.detail.text?.slice(0, 90) ?? 'Recorded activity'}</small></button>)}</div>
          {run && step ? <><div className="flow-summary"><span><Check size={14}/>{run.steps.length} recorded actions</span><span><Layers size={14}/>{run.restored_messages} messages restored</span><small>Steps follow recorded results. Tools may overlap; each keeps its own evidence.</small></div>
            <div className="flow-workspace"><div className="flow-graph" aria-label="Interactive execution graph">{run.steps.map((item, index) => <div className="flow-node-group" key={item.id}>
              {index > 0 && <div className="flow-connector" aria-hidden="true"><svg viewBox="0 0 24 32"><path d="M12 0V27M7 22L12 28L17 22"/></svg><span>{item.kind === 'tool' ? 'execute tool request' : item.kind === 'model' ? 'assemble model input' : 'next recorded step'}</span></div>}
              <button className={`flow-node kind-${item.kind} ${step.id === item.id ? 'selected' : ''}`} aria-pressed={step.id === item.id} onClick={() => { setStepId(item.id); if (mode === 'input' && item.kind !== 'model') setMode('changes') }}><span className="node-number">{index + 1}</span><span className="node-symbol"><StepIcon kind={item.kind}/></span><span className="node-copy"><strong>{item.title}</strong><small>{item.origin}</small><span className="node-tags"><span>{item.before.length} → {item.after.length} messages</span>{item.changes.added.length > 0 && <span>+{item.changes.added.length} new</span>}{item.evidence.length > 0 && <span>{item.evidence.length} evidence</span>}{item.error ? <span className="error-badge">Error</span> : null}</span></span><ChevronRight size={16}/></button>
            </div>)}</div>
              <section className="step-detail" aria-label="Selected step details"><div className="step-detail-heading"><div><span className="eyebrow">STEP {stepIndex + 1} OF {run.steps.length}</span><h3><StepIcon kind={step.kind}/>{step.title}</h3><p>{step.origin}</p></div><div className="step-navigation"><button aria-label="Previous step" disabled={stepIndex === 0} onClick={() => { const next = run.steps[stepIndex - 1]; setStepId(next.id); if (mode === 'input' && next.kind !== 'model') setMode('changes') }}><ArrowLeft size={17}/></button><button aria-label="Next step" disabled={stepIndex === run.steps.length - 1} onClick={() => { const next = run.steps[stepIndex + 1]; setStepId(next.id); if (mode === 'input' && next.kind !== 'model') setMode('changes') }}><ArrowRight size={17}/></button></div></div>
                <div className="detail-tabs" role="tablist" aria-label="Step data view"><button role="tab" aria-selected={mode === 'changes'} onClick={() => setMode('changes')}>New data</button><button role="tab" aria-selected={mode === 'state'} onClick={() => setMode('state')}>State</button><button role="tab" aria-selected={mode === 'context'} onClick={() => setMode('context')}>Context</button>{step.kind === 'model' && <button role="tab" aria-selected={mode === 'input'} onClick={() => setMode('input')}>Model input</button>}</div>
                <StepDetail key={step.id + mode} step={step} mode={mode}/>
              </section>
            </div></> : !loading && <p className="quiet-message">No execution has been recorded yet. Send a message in My account or Workspace, then refresh.</p>}
          {flow.conversation.operations.map(operation => <div className="card" key={operation.id}><h3>Pending approval · {operation.kind}</h3><DataValue value={operation.payload_json}/>{flow.conversation.can_decide && <div className="dialog-actions"><button className="button button-dark" onClick={() => void decide(operation.id, 'approve')}>Approve</button><button className="button button-small" onClick={() => void decide(operation.id, 'reject')}>Reject</button></div>}</div>)}
        </>}
      </>}</div>
    </div>
    <div className="flow-legend"><span><MessageSquare size={15}/> User input</span><span><Bot size={15}/> Model input & output</span><span><Wrench size={15}/> Tools & evidence</span><span><Layers size={15}/> State grows through the steps</span></div>
  </section>
}
