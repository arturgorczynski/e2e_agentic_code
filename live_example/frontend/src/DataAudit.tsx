import { useState } from 'react'
import { AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react'
import { api } from './api'

type ModernAudit = {
  status: 'ok' | 'invalid'
  counts: Record<string, number>
  order_dates: { first: string | null; last: string | null }
  violations: Record<string, number>
}

export function DataAudit() {
  const [result, setResult] = useState<ModernAudit | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showAll, setShowAll] = useState(false)

  async function run() {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      setResult(await api<ModernAudit>('/database/audit-modern'))
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const checks = Object.entries(result?.violations ?? {})
  const failed = checks.filter(([, count]) => count > 0)
  const visible = showAll ? checks : failed

  return <section className="card db-audit-panel">
    <div className="db-audit-heading">
      <div>
        <h3>Check business links</h3>
        <p>Read-only checks for the fictional 2026 history: invoices, payments, orders, stock, support and planning.</p>
      </div>
      <button className="button button-dark" onClick={run} disabled={loading}>
        <RefreshCw size={16} /> {loading ? 'Checking…' : result ? 'Run again' : 'Run checks'}
      </button>
    </div>
    {error && <div className="notice">{error}</div>}
    {result && <>
      <div className={`db-audit-status ${result.status}`}>
        {result.status === 'ok' ? <CheckCircle2 size={21} /> : <AlertTriangle size={21} />}
        <strong>{result.status === 'ok' ? `All ${checks.length} checks passed` : `${failed.length} of ${checks.length} checks found issues`}</strong>
      </div>
      <p className="db-audit-context">{result.counts.orders} contemporary orders · {result.counts.invoices} invoices · {result.counts.payments} payments · {result.counts.shipments} shipments. Order dates: {result.order_dates.first ?? 'none'} to {result.order_dates.last ?? 'none'}.</p>
      {result.counts.orders === 0 && <p className="db-audit-context">No contemporary orders are present in this exercise state, so the business-history checks have no 2026 order cohort to inspect.</p>}
      <button className="button button-small" onClick={() => setShowAll(value => !value)}>{showAll ? 'Hide passing checks' : `Show all ${checks.length} checks`}</button>
      {visible.length > 0 && <div className="db-audit-checks">
        {visible.map(([name, count]) => <div key={name} className={count ? 'failed' : ''}>
          <span>{name.replaceAll('_', ' ')}</span><strong>{count ? `${count} issue${count === 1 ? '' : 's'}` : 'Passed'}</strong>
        </div>)}
      </div>}
      <small className="db-audit-context">A passing audit checks internal consistency. It does not verify that fictional records describe real events. Run it again after editing records.</small>
    </>}
  </section>
}
