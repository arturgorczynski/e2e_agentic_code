import { DataValue } from './StructuredData'
import type { RecordRow } from './api'

export function ContextData({ context }: { context: RecordRow }) {
  return <div className="context-data">
    <div className="explain-card context-explanation"><div><strong>Context · supplied by the application</strong><p>Tools use the session to resolve identity and permissions. This safe view excludes credentials. These values are separate from state.messages.</p></div></div>
    {!Object.keys(context).length ? <p className="quiet-message">Context has not been recorded at this point. Select the first model call or a tool step.</p> : <>
      <section className="context-group"><h4>Identity resolved from the session</h4><DataValue value={{
        ...(context.resolved_customer ? { customer: context.resolved_customer } : {}),
        username: context.username, access_profile: context.access_profile,
      }}/></section>
      <details className="detail-section"><summary>Permissions and available tools</summary><DataValue value={{ permissions: context.permissions, selected_tools: context.selected_tools, allowed_record_entities: context.allowed_record_entities, tool_selection: context.tool_selection }}/></details>
      <details className="detail-section"><summary>Session provenance and execution IDs</summary><DataValue value={{ source: context.source, actor_id: context.actor_id, thread_id: context.thread_id, run_id: context.run_id }}/></details>
    </>}
  </div>
}

export function SqlEvidence({ payload, id }: { payload: RecordRow; id: string }) {
  const parameters = Array.isArray(payload.parameters) ? payload.parameters : []
  const sources = Array.isArray(payload.parameter_sources) ? payload.parameter_sources : []
  return <div className="sql-evidence">
    <p><strong>{String(payload.label ?? 'Database query')}</strong> · {String(payload.row_count ?? '?')} rows returned</p>
    <pre className="sql-statement"><code>{String(payload.sql ?? '')}</code></pre>
    {parameters.length > 0 ? <>
      <h4>Bound parameters</h4><p className="quiet-message">Each ? receives a value in order. SQLite executes the query with these values supplied separately.</p>
      <div className="parameter-list">{parameters.map((value, index) => <div className="parameter-binding" key={index}>
        <span className="parameter-number">? · parameter {index + 1}</span><code>{JSON.stringify(value)}</code>
        <small>Source: {String(sources[index] ?? 'Not recorded in this log')}</small>
      </div>)}</div>
    </> : <p className="quiet-message">This query has no bound parameters.</p>}
    <details className="detail-section"><summary>Query metadata and source ID</summary><DataValue value={{ id, integration: payload.integration, permission: payload.permission }}/></details>
  </div>
}
