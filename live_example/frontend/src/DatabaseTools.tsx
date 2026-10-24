import { useEffect, useState } from 'react'
import { ArrowRight, Database, ExternalLink, GitBranch, Plus, Search, X } from 'lucide-react'
import { api, type RecordRow } from './api'

type Column = {
  name: string
  type: string
  required: boolean
  primary_key: boolean
  default: string | null
}
type ForeignKey = { column: string; table: string; target_column: string }
type TableSchema = {
  name: string
  type: 'table' | 'view'
  editable: boolean
  reason: string | null
  columns: Column[]
  foreign_keys: ForeignKey[]
  suggestions: Record<string, string[]>
}
type Dependency = { table: string; column: string; count: number; sample_ids: string[] }
type DependencyPreview = { table: string; id: string; can_delete: boolean; dependencies: Dependency[] }
type Relation = ForeignKey & { source: string; target: string }
type RelationshipData = { tables: { name: string; type: string }[]; edges: Relation[] }

function display(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

function FieldLabel({ column, automatic }: { column: Column; automatic: boolean }) {
  return <span>{column.name.replaceAll('_', ' ')}{column.required && !automatic && <b aria-label="required"> *</b>}<small>{automatic ? 'Automatic if blank' : (column.type || 'TEXT') + (column.name.endsWith('_pence') ? ' ? GBP pence' : '')}</small></span>
}

function ForeignKeyField({ value, target, onChange }: { value: string; target: string; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [matches, setMatches] = useState<RecordRow[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    if (!open) return
    let active = true
    api<{ rows: RecordRow[] }>(`/database/${target}?q=${encodeURIComponent(search)}&size=20`)
      .then(result => { if (active) { setMatches(result.rows); setError('') } })
      .catch(err => { if (active) setError((err as Error).message) })
    return () => { active = false }
  }, [open, search, target])
  return <div className="db-fk-control">
    <div className="db-fk-entry"><input value={value} onChange={event => onChange(event.target.value)} placeholder={`ID in ${target}`} /><button type="button" onClick={() => { setOpen(!open); setSearch('') }} aria-label={`Find record in ${target}`}><Search size={15}/> Find</button></div>
    {open && <div className="db-fk-picker"><label className="search-box"><Search size={14}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder={`Search ${target} by ID or text`} /></label>{error && <p>{error}</p>}<div className="db-fk-results">{matches.map(item => <button type="button" key={display(item.id)} onClick={() => { onChange(display(item.id)); setOpen(false) }}><strong>{display(item.id)}</strong><small>{display(item.name ?? item.title ?? item.label ?? item.status ?? item.category ?? '')}</small></button>)}</div><small>Showing up to 20 matches. Type to narrow the list.</small></div>}
  </div>
}

export function RowEditor({ table, record, focusField, close, saved, removed, browseRelated }: { table: string; record: RecordRow | null; focusField?: string; close: () => void; saved: (record: RecordRow, created: boolean) => void; removed: (id: string) => void; browseRelated: (table: string, column: string, id: string) => void }) {
  const [schema, setSchema] = useState<TableSchema | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [dependencies, setDependencies] = useState<DependencyPreview | null>(null)
  const creating = record === null
  useEffect(() => {
    let active = true
    api<TableSchema>(`/database/schema/${table}`)
      .then(result => { if (active) setSchema(result) })
      .catch(err => { if (active) setError((err as Error).message) })
    setDraft(Object.fromEntries(Object.entries(record ?? {}).map(([key, value]) => [key, display(value)])))
    return () => { active = false }
  }, [table, record])
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [close])
  useEffect(() => {
    if (!confirmDelete || !record) return
    let active = true
    setDependencies(null)
    api<DependencyPreview>(`/database/rows/${table}/${encodeURIComponent(display(record.id))}/dependencies`)
      .then(result => { if (active) setDependencies(result) })
      .catch(err => { if (active) setError((err as Error).message) })
    return () => { active = false }
  }, [confirmDelete, record, table])
  async function save() {
    if (!schema?.editable) return
    setError('')
    setBusy(true)
    try {
      const values: Record<string, string | null> = {}
      for (const column of schema.columns) {
        if (!creating && column.primary_key) continue
        const current = draft[column.name] ?? ''
        if (creating && !current) continue
        if (!creating && current === display(record?.[column.name])) continue
        values[column.name] = current || null
      }
      const path = creating ? `/database/rows/${table}` : `/database/rows/${table}/${encodeURIComponent(display(record?.id))}`
      const result = await api<{ id: string; record: RecordRow; created: boolean }>(path, {
        method: creating ? 'POST' : 'PATCH',
        body: JSON.stringify(creating ? { values } : { values, expected: record }),
      })
      saved(result.record, result.created)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  async function remove() {
    if (!record || !schema?.editable || !dependencies?.can_delete) return
    setBusy(true); setError('')
    try {
      await api(`/database/rows/${table}/${encodeURIComponent(display(record.id))}`, {
        method: 'DELETE', body: JSON.stringify({ expected: record }),
      })
      removed(display(record.id))
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="modal-backdrop" onClick={close}>
    <div className="modal db-editor" role="dialog" aria-modal="true" aria-label={creating ? `Add row to ${table}` : `Edit row in ${table}`} onClick={event => event.stopPropagation()}>
      <div className="modal-title"><div><span className="eyebrow">{creating ? 'NEW RECORD' : 'EDIT RECORD'}</span><h2>{table.replaceAll('_', ' ')}</h2><p>{creating ? 'Add a row to the local exercise database.' : `Editing ${display(record?.id)}. Double-check related records before saving.`}</p></div><button className="icon-button" onClick={close} aria-label="Close editor"><X size={20}/></button></div>
      {!schema && !error && <p>Loading table fields…</p>}
      {schema && !schema.editable && <div className="notice">{schema.reason}</div>}
      {schema?.editable && <><div className="db-editor-note"><GitBranch size={18}/><span>Foreign keys must point to existing rows. Changing a shared row, such as an address, changes every record that refers to it. Use the dedicated customer address form to change only one customer.{table === 'company_expenses' && ' For a new expense, leave ID, currency and provenance blank. Selecting a purchase order fills its supplier automatically.'}</span></div><div className="db-editor-fields">{schema.columns.map(column => {
        const foreign = schema.foreign_keys.find(key => key.column === column.name)
        return <label key={column.name} className="db-editor-field"><FieldLabel column={column} automatic={creating && (column.name === 'id' || column.name === 'provenance' || (table === 'company_expenses' && column.name === 'currency'))}/>{foreign ? <ForeignKeyField value={draft[column.name] ?? ''} target={foreign.table} onChange={value => setDraft(previous => ({ ...previous, [column.name]: value }))}/> : <><input autoFocus={column.name === focusField} type={/(?:_on$|^as_of$|^valid_from$|^valid_until$)/.test(column.name) ? 'date' : 'text'} list={schema.suggestions[column.name]?.length ? table + '-' + column.name + '-suggestions' : undefined} value={draft[column.name] ?? ''} onChange={event => setDraft(previous => ({ ...previous, [column.name]: event.target.value }))} disabled={!creating && column.primary_key} inputMode={column.type.toUpperCase().includes('INT') ? 'numeric' : 'text'} placeholder={creating && column.name === 'id' ? 'Leave blank for an automatic ID' : creating && column.name === 'provenance' ? table === 'company_expenses' ? 'fictional_contemporary_expense if blank' : 'portal_demo_edit if blank' : creating && table === 'company_expenses' && column.name === 'currency' ? 'GBP if blank' : column.required ? 'Required' : 'Optional'} />{schema.suggestions[column.name]?.length ? <datalist id={table + '-' + column.name + '-suggestions'}>{schema.suggestions[column.name].map(value => <option key={value} value={value}/>)}</datalist> : null}</>}{foreign && <small>References {foreign.table}.{foreign.target_column}</small>}</label>
      })}</div><div className="db-editor-actions">{!creating && <button className="button button-small db-delete" onClick={() => setConfirmDelete(!confirmDelete)} disabled={busy}>Delete row</button>}<button className="button button-small" onClick={close}>Cancel</button><button className="button button-dark" onClick={save} disabled={busy}>{creating ? <Plus size={16}/> : <Database size={16}/>} {busy ? 'Saving…' : creating ? 'Add row' : 'Save changes'}</button></div>{confirmDelete && <div className="db-delete-confirm"><strong>Delete {display(record?.id)}?</strong>{dependencies ? dependencies.can_delete ? <p>No records in other tables reference this row. A successful deletion is recorded in the audit log.</p> : <><p>This row has linked records. Open them and remove or reassign them before deleting this row.</p><div className="db-dependency-list">{dependencies.dependencies.map(item => <button type="button" key={item.table + ':' + item.column} onClick={() => browseRelated(item.table, item.column, display(record?.id))}><strong>{item.table}</strong><span>{item.count.toLocaleString()} via {item.column}</span><small>Examples: {item.sample_ids.join(', ')}</small><ExternalLink size={14}/></button>)}</div></> : <p>Checking links in other tables...</p>}<button className="button button-dark" onClick={remove} disabled={busy || !dependencies?.can_delete}>Yes, delete this row</button><button className="button button-small" onClick={() => setConfirmDelete(false)}>Keep row</button></div>}</>}
      {error && <div className="notice" role="alert">{error}</div>}
    </div>
  </div>
}

export function RelationshipMap({ currentTable, browse }: { currentTable: string; browse: (table: string) => void }) {
  const [data, setData] = useState<RelationshipData | null>(null)
  const [focus, setFocus] = useState(currentTable)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { setFocus(currentTable) }, [currentTable])
  useEffect(() => {
    let active = true
    api<RelationshipData>('/database/relationships')
      .then(result => { if (active) setData(result) })
      .catch(err => { if (active) setError((err as Error).message) })
    return () => { active = false }
  }, [])
  const incoming = data?.edges.filter(edge => edge.target === focus) ?? []
  const outgoing = data?.edges.filter(edge => edge.source === focus) ?? []
  const matches = data?.tables.filter(item => item.name.toLowerCase().includes(search.toLowerCase())) ?? []
  return <div className="db-relations card"><div className="db-relations-head"><div><span className="eyebrow">SCHEMA MAP</span><h3>How the tables connect</h3><p>Arrows point from a foreign-key column to the table it references. Select a table to follow its links.</p></div>{data && <small>{data.tables.length} objects · {data.edges.length} visible relationships</small>}</div>{error && <div className="notice">{error}</div>}{!data && !error && <p>Loading relationships…</p>}{data && <><div className="db-relations-picker"><label className="search-box"><Search size={16}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a table or view" /></label><select aria-label="Focus table" value={focus} onChange={event => setFocus(event.target.value)}>{matches.some(item => item.name === focus) || !search ? null : <option value={focus}>{focus}</option>}{matches.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></div><div className="db-relation-flow"><div className="db-relation-column"><h4>Referenced by <small>{incoming.length}</small></h4>{incoming.length ? incoming.map((edge, index) => <button className="db-relation-node" key={`${edge.source}-${edge.column}-${index}`} onClick={() => setFocus(edge.source)}><strong>{edge.source}</strong><small>{edge.column} → {focus}.{edge.target_column}</small></button>) : <p>No visible table points here.</p>}</div><div className="db-relation-center"><div className="db-relation-focus"><GitBranch size={28}/><small>{data.tables.find(item => item.name === focus)?.type ?? 'table'}</small><strong>{focus}</strong><span>{incoming.length} incoming · {outgoing.length} outgoing</span><button className="button button-light" onClick={() => browse(focus)}>Browse records <ExternalLink size={15}/></button></div></div><div className="db-relation-column"><h4>References <small>{outgoing.length}</small></h4>{outgoing.length ? outgoing.map((edge, index) => <button className="db-relation-node" key={`${edge.target}-${edge.column}-${index}`} onClick={() => setFocus(edge.target)}><strong>{edge.target}</strong><small>{focus}.{edge.column} → {edge.target_column}</small></button>) : <p>No foreign keys from this table.</p>}</div></div><div className="db-relation-help"><ArrowRight size={17}/> Example: <code>orders.customer_id → customers.id</code> means each order belongs to one customer.</div></>}
  </div>
}
