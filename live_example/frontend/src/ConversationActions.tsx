import { useState } from 'react'
import { Pencil, RotateCcw, Trash2, X } from 'lucide-react'
import { api } from './api'

export function ConversationActions({ id, title, archived, changed, disabled = false }: {
  id: string; title: string; archived: boolean; changed: () => void; disabled?: boolean
}) {
  const [action, setAction] = useState<'rename' | 'delete' | null>(null)
  const [name, setName] = useState(title)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  async function save(body: object) {
    setSaving(true); setError('')
    try { await api(`/conversations/${id}`, { method: 'PATCH', body: JSON.stringify(body) }); setAction(null); changed() }
    catch (err) { setError((err as Error).message) }
    finally { setSaving(false) }
  }
  return <>
    <div className="conversation-actions">
      <button className="icon-button" disabled={disabled || saving} title="Rename conversation" aria-label={`Rename ${title}`} onClick={() => { setName(title); setError(''); setAction('rename') }}><Pencil size={15}/></button>
      {archived ? <button className="icon-button" disabled={saving} title="Restore conversation" aria-label={`Restore ${title}`} onClick={() => void save({ status: 'active' })}><RotateCcw size={15}/></button> : <button className="icon-button" disabled={disabled || saving} title="Move conversation to trash" aria-label={`Delete ${title}`} onClick={() => { setError(''); setAction('delete') }}><Trash2 size={15}/></button>}
    </div>
    {error && !action && <p className="notice" role="alert">{error}</p>}
    {action && <div className="modal-backdrop" onClick={() => !saving && setAction(null)}><div className="modal conversation-modal" role="dialog" aria-modal="true" aria-labelledby={`dialog-${id}`} onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape' && !saving) setAction(null) }}>
      <div className="card-heading"><h2 id={`dialog-${id}`}>{action === 'rename' ? 'Rename conversation' : 'Move to trash?'}</h2><button className="icon-button" aria-label="Close dialog" disabled={saving} onClick={() => setAction(null)}><X size={18}/></button></div>
      {action === 'rename' ? <label className="field-label">Conversation name<input autoFocus maxLength={120} value={name} onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && name.trim()) void save({ title: name.trim() }) }}/></label> : <p>“{title}” will leave your active chats. Its messages and execution remain in Conversations → Trash, where you can restore it.</p>}
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="dialog-actions"><button className="button button-small" disabled={saving} onClick={() => setAction(null)}>Cancel</button><button className="button button-dark" disabled={saving || (action === 'rename' && !name.trim())} onClick={() => void save(action === 'rename' ? { title: name.trim() } : { status: 'archived' })}>{saving ? 'Saving…' : action === 'rename' ? 'Save name' : 'Move to trash'}</button></div>
    </div></div>}
  </>
}
