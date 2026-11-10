import ReactMarkdown from 'react-markdown'

export type Message = { type: string; data: { id?: string; content?: unknown; name?: string; status?: string; tool_call_id?: string; tool_calls?: { name: string; args: unknown; id?: string }[] } }

function messageKey(message: Message) {
  return message.type === 'tool' ? message.data.tool_call_id ?? message.data.id : message.data.id
}

function ToolResult({ content }: { content: unknown }) {
  let value = content
  if (typeof value === 'string') {
    try { value = JSON.parse(value) } catch { return <DataValue value={content}/> }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value) || !('records' in value)) return <DataValue value={value}/>
  const result = value as Record<string, unknown>
  if (!Array.isArray(result.records) || result.records.some(record => !record || typeof record !== 'object' || Array.isArray(record))) return <DataValue value={value}/>
  const records = result.records
  const facts = result.facts && typeof result.facts === 'object' ? result.facts as Record<string, unknown> : {}
  return <div className="tool-result-content">
    <p className="result-status">Result: <strong>{String(result.status ?? 'Returned')}</strong> · {records.length} {records.length === 1 ? 'record' : 'records'}</p>
    {records.map((record, index) => <section className="result-record" key={index}>
      <h5>{String(record?.name ?? record?.id ?? `Record ${index + 1}`)}</h5><DataValue value={record}/>
    </section>)}
    {Object.entries(facts).map(([name, fact]) => <section className="result-facts" key={name}><h5>{name.replaceAll('_', ' ')}</h5>{Array.isArray(fact) ? fact.map((record, index) => <div className="result-record" key={index}><DataValue value={record}/></div>) : <DataValue value={fact}/>}</section>)}
    {Object.entries(result).filter(([name]) => !['status', 'records', 'facts', 'sources'].includes(name)).map(([name, data]) => <section key={name}><h5>{name.replaceAll('_', ' ')}</h5><DataValue value={data}/></section>)}
    {result.sources !== undefined && <details className="detail-section"><summary>Source references · recorded query IDs</summary><DataValue value={result.sources}/></details>}
  </div>
}

export function DataValue({ value, depth = 0, emptyObjectLabel = 'No fields' }: { value: unknown; depth?: number; emptyObjectLabel?: string }) {
  if (value === null || value === undefined) return <span className="data-null">Not supplied</span>
  if (typeof value === 'string') {
    if (/^\s*[\[{]/.test(value)) {
      try { return <DataValue value={JSON.parse(value)} depth={depth}/> } catch { /* ordinary text */ }
    }
    return <div className="readable-text"><ReactMarkdown>{value || '(empty)'}</ReactMarkdown></div>
  }
  if (typeof value !== 'object') return <span className={`data-scalar ${typeof value}`}>{String(value)}</span>
  const entries = Object.entries(value)
  if (!entries.length) return <span className="data-null">{Array.isArray(value) ? 'Empty list' : emptyObjectLabel}</span>
  const content = <dl className={`data-tree depth-${Math.min(depth, 3)}`}>{entries.map(([key, child]) => <div className="data-entry" key={key}><dt>{Array.isArray(value) ? `Item ${Number(key) + 1}` : key.replaceAll('_', ' ')}</dt><dd><DataValue value={child} depth={depth + 1}/></dd></div>)}</dl>
  const longList = Array.isArray(value) && entries.length > 4 && depth > 0
  return depth > 1 || longList ? <details className="data-disclosure" open={depth < 3 && !longList}><summary>{Array.isArray(value) ? 'List' : 'Fields'} · {entries.length} {Array.isArray(value) ? 'items' : 'fields'}</summary>{content}</details> : content
}

export function Messages({ messages, empty = 'No messages at this step.', stateMessages, added = [], changed = [], collapseEarlier = false }: { messages: Message[]; empty?: string; stateMessages?: Message[]; added?: Message[]; changed?: Message[]; collapseEarlier?: boolean }) {
  if (!messages.length) return <p className="quiet-message">{empty}</p>
  return <div className="message-cards">{messages.map((message, index) => {
    const position = stateMessages?.findIndex(item => item === message || Boolean(messageKey(message) && messageKey(item) === messageKey(message))) ?? -1
    const contains = (items: Message[]) => items.some(item => item === message || Boolean(messageKey(message) && messageKey(item) === messageKey(message)))
    const isAdded = contains(added)
    const isChanged = contains(changed)
    return <details className={`message-card role-${message.type}`} open={!collapseEarlier || isAdded || isChanged || index >= messages.length - 2} key={`${message.data.id ?? index}-${index}`}>
    <summary className="message-card-label"><span>{position >= 0 ? `#${position + 1} · ` : ''}{message.type === 'human' ? 'User · HumanMessage' : message.type === 'ai' ? 'Model · AIMessage' : message.type === 'tool' ? `Tool · ${message.data.name ?? 'result'} · ToolMessage` : message.type}</span>{isAdded && <b className="message-change">New</b>}{isChanged && <b className="message-change">Updated</b>}{message.data.status === 'error' && <span className="error-badge">Error</span>}</summary>
    {position >= 0 && <code className="message-path">state.messages[{position}]</code>}
    {message.data.content ? message.type === 'tool' ? <ToolResult content={message.data.content}/> : <DataValue value={message.data.content}/> : null}
    {message.data.tool_calls?.map((call, i) => <div className="tool-call-card" key={call.id ?? i}><strong>Call {call.name}</strong><DataValue value={call.args} emptyObjectLabel="No arguments · {}"/></div>)}
  </details>})}</div>
}
