import { useState } from 'react'
import { api, post } from './api'

type Change = { key: string; table: string; id: string; kind: 'added' | 'modified' | 'removed' }
type Preview = {
  baseline_version: string; stamp: string; total: number
  counts: Record<string, number>; changes: Change[]; truncated: boolean
  release_managed: { documents: number; linked_history: number; fictional_expenses?: number }
}

export function ResetPanel({ restored }: { restored: () => void }) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const [preserve, setPreserve] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function load() {
    setBusy(true); setError(''); setMessage('')
    try { setPreview(await api<Preview>('/database/reset-preview')); setPreserve([]) }
    catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function reset() {
    if (!preview) return
    setBusy(true); setError('')
    try {
      const result = await post<{ backup: string; preserved: number }>('/database/reset', { stamp: preview.stamp, preserve })
      setMessage(`Restored the installed baseline. ${result.preserved} records were preserved. Backup: ${result.backup}`)
      setPreview(null); setPreserve([]); restored()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  function toggle(key: string) {
    setPreserve(previous => previous.includes(key) ? previous.filter(item => item !== key) : [...previous, key])
  }

  return <div className="card reset-panel"><span className="eyebrow">LOCAL DATA RESET</span><h3>Restore the installed company baseline</h3><p>Preview added, changed and removed exercise records. Select changes to preserve; every other listed difference will be reset. Installed document versions and the fictional cases they describe stay together. A complete copy of the current company and app databases is saved before reset. Conversations remain available in Execution.</p>
    <button className="button button-small" onClick={load} disabled={busy}>{busy ? 'Working…' : 'Preview differences'}</button>
    {error && <div className="notice" role="alert">{error}</div>}{message && <div className="success-notice">{message}</div>}
    {preview && <><div className="reset-summary"><strong>{preview.total} resettable changes</strong><span>{preview.counts.added} added · {preview.counts.modified} modified · {preview.counts.removed} removed</span><small>Baseline {preview.baseline_version}</small></div>
      {(preview.release_managed.documents > 0 || preview.release_managed.linked_history > 0 || Boolean(preview.release_managed.fictional_expenses)) && <p>{preview.release_managed.documents} document rows belong to the installed release; {preview.release_managed.linked_history} linked contemporary-history rows and {preview.release_managed.fictional_expenses ?? 0} fictional expense rows are retained. These are excluded from the selectable changes above.</p>}
      {preview.truncated && <div className="notice">Showing the first {preview.changes.length} differences. Reset affects all {preview.total}; only listed changes can be preserved here.</div>}
      <div className="reset-changes">{preview.changes.map(change => <label key={change.key}><input type="checkbox" checked={preserve.includes(change.key)} onChange={() => toggle(change.key)}/><span><strong>{change.table}</strong> · {change.id}</span><small>{change.kind}</small></label>)}</div>
      <p>Preserving a scenario customer also preserves its generated address, orders, items, invoices, payments, shipments, product and stock history. New parent records required by other preserved rows are included automatically.</p>
      <button className="button button-dark" onClick={reset} disabled={busy || preview.total === 0}>Reset {preview.total - preserve.length} unselected changes</button>
    </>}
  </div>
}
