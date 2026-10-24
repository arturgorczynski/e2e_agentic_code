import { useEffect, useState } from 'react'
import { BarChart3, CalendarDays, ReceiptText, Search, ShoppingBag, X } from 'lucide-react'
import { api, type Persona } from './api'

type Cohort = 'historical' | 'contemporary'
type Month = {
  month: string; invoice_count: number; gross_billed_pence: number
  credits_issued_pence: number; net_billing_activity_pence: number
  payment_count: number | null; customer_cash_received_pence: number | null
  expense_count: number | null; recorded_cash_outflow_pence: number | null
  recorded_cash_difference_pence: number | null
}
type ExpenseCategory = { category: string; expense_count: number; amount_pence: number }
type Finance = {
  months: Month[]; expense_ledger_available: boolean; expense_categories: ExpenseCategory[] | null
  totals: Omit<Month, 'month'> & { current_outstanding_for_invoice_cohort_pence: number | null }
  definitions: Record<string, string>
}
type Order = {
  id: string; customer_id: string; customer_name: string; ordered_at: string
  status: string; provenance: string; line_count: number; basket_pence: number
}
type OrderPage = { rows: Order[]; total: number; page: number; page_size: number; basket_note: string }
type OrderDetail = {
  order: Order; line_count: number; preview_limit: number
  lines: { id: string; product_id: string; product_name: string; quantity: number; line_pence: number; shipped_quantity: number | null }[]
  statuses: { id: string; occurred_at: string; status: string; reason: string }[]
  shipments: { id: string; dispatched_on: string; delivered_on: string | null; carrier: string; units: number }[] | null
  invoice: { id: string; posted_on: string; due_on: string; total_pence: number; outstanding_pence: number } | null
}
type Expense = {
  id: string; paid_on: string; category: string; payee: string; amount_pence: number
  supplier_id: string | null; purchase_order_id: string | null; description: string
}
type ExpensePage = { available: boolean; total: number; rows: Expense[]; page_size: number; filtered_amount_pence: number | null }

const gbp = (pence: number | null | undefined) => pence == null ? '—' :
  `£${(pence / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const today = () => {
  const now = new Date()
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-')
}

export function BusinessInsights({ persona, choose }: { persona: Persona | null; choose: () => void }) {
  const internal = persona?.kind === 'employee' || persona?.kind === 'super_user'
  const financeScope = persona?.kind === 'super_user' || Boolean(persona?.permissions.some(p => p === 'finance.read' || p === 'analytics.read'))
  const settlementScope = persona?.kind === 'super_user' || Boolean(persona?.permissions.includes('finance.read'))
  const [cohort, setCohort] = useState<Cohort>('contemporary')
  const [start, setStart] = useState('2026-01-01')
  const [end, setEnd] = useState(today)
  const [tab, setTab] = useState<'orders' | 'finance' | 'expenses'>('orders')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [orderPage, setOrderPage] = useState(1)
  const [expensePage, setExpensePage] = useState(1)
  const [category, setCategory] = useState('')
  const [expenseQuery, setExpenseQuery] = useState('')
  const [orders, setOrders] = useState<OrderPage | null>(null)
  const [finance, setFinance] = useState<Finance | null>(null)
  const [expenses, setExpenses] = useState<ExpensePage | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<OrderDetail | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const period = new URLSearchParams({ start, end, cohort })

  useEffect(() => {
    if (tab === 'expenses' && !settlementScope) setTab(financeScope ? 'finance' : 'orders')
    else if (tab === 'finance' && !financeScope) setTab('orders')
  }, [tab, financeScope, settlementScope])

  useEffect(() => { setSelected(null) }, [start, end, cohort, query, status, customerId])

  useEffect(() => {
    if (!internal) return
    let active = true
    const params = new URLSearchParams({ start, end, cohort, page: String(orderPage), q: query, status, customer_id: customerId })
    setBusy(true); setError(''); setOrders(null)
    api<OrderPage>(`/insights/orders?${params}`)
      .then(data => { if (active) setOrders(data) })
      .catch(reason => { if (active) setError((reason as Error).message) })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [internal, start, end, cohort, orderPage, query, status, customerId, persona?.subject_id])

  useEffect(() => {
    if (!internal || !financeScope) { setFinance(null); return }
    let active = true
    setFinance(null)
    api<Finance>(`/insights/finance?${period}`)
      .then(data => { if (active) setFinance(data) })
      .catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [internal, financeScope, start, end, cohort, persona?.subject_id])

  useEffect(() => {
    if (!internal || !settlementScope) { setExpenses(null); return }
    let active = true
    setExpenses(null)
    const params = new URLSearchParams({ start, end, cohort, page: String(expensePage), category, q: expenseQuery })
    api<ExpensePage>(`/insights/expenses?${params}`)
      .then(data => { if (active) setExpenses(data) })
      .catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [internal, settlementScope, start, end, cohort, expensePage, category, expenseQuery, persona?.subject_id])

  useEffect(() => {
    if (!selected) { setDetail(null); return }
    let active = true
    setDetail(null)
    api<OrderDetail>(`/insights/orders/${encodeURIComponent(selected)}`)
      .then(data => { if (active) setDetail(data) })
      .catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [selected, persona?.subject_id])

  if (!internal) return <section className="content-section"><div className="gate"><BarChart3 size={32}/><h2>Company history and insights</h2><p>Choose an employee or superuser persona to explore company orders and business activity.</p><button className="button button-dark" onClick={choose}>Choose a persona</button></div></section>

  function changeCohort(next: Cohort) {
    setCohort(next); setStart(next === 'historical' ? '2010-01-01' : '2026-01-01')
    setEnd(next === 'historical' ? '2011-12-09' : today())
    setOrderPage(1); setExpensePage(1); setSelected(null)
  }
  const moneyMax = Math.max(1, ...(finance?.months.flatMap(month => [month.gross_billed_pence, month.customer_cash_received_pence ?? 0, month.recorded_cash_outflow_pence ?? 0]) ?? []))
  return <section className="content-section insights-page">
    <div className="insights-heading"><div><span className="eyebrow">BUSINESS HISTORY</span><h2>Follow the numbers to their records.</h2><p>Explore customer orders, monthly billing and recorded cash. Every cohort is labeled so the historic retail reconstruction stays separate from fictional 2026 cases.</p></div><BarChart3 size={37}/></div>
    <div className="insights-controls"><div className="insights-cohort"><button className={cohort === 'contemporary' ? 'active' : ''} onClick={() => changeCohort('contemporary')}>Fictional 2026</button><button className={cohort === 'historical' ? 'active' : ''} onClick={() => changeCohort('historical')}>2010–11 history</button></div><label><CalendarDays size={16}/> From<input type="date" value={start} onChange={event => { setStart(event.target.value); setOrderPage(1); setExpensePage(1) }}/></label><label>To<input type="date" value={end} onChange={event => { setEnd(event.target.value); setOrderPage(1); setExpensePage(1) }}/></label></div>
    <div className="db-tabs"><button className={tab === 'orders' ? 'active' : ''} onClick={() => setTab('orders')}><ShoppingBag size={16}/> Order history</button>{financeScope && <button className={tab === 'finance' ? 'active' : ''} onClick={() => setTab('finance')}><BarChart3 size={16}/> Money activity</button>}{settlementScope && <button className={tab === 'expenses' ? 'active' : ''} onClick={() => setTab('expenses')}><ReceiptText size={16}/> Expense ledger</button>}</div>
    {error && <div className="notice" role="alert">{error}</div>}
    {tab === 'orders' && <><div className="insights-order-filters"><label className="search-box"><Search size={16}/><input aria-label="Search orders or customers" value={query} placeholder="Order ID or customer name" onChange={event => { setQuery(event.target.value); setOrderPage(1) }}/></label><input aria-label="Customer ID" value={customerId} placeholder="Customer ID" onChange={event => { setCustomerId(event.target.value); setOrderPage(1) }}/><select aria-label="Order status" value={status} onChange={event => { setStatus(event.target.value); setOrderPage(1) }}><option value="">All statuses</option>{['confirmed', 'partial', 'fulfilled', 'cancelled'].map(value => <option key={value} value={value}>{value}</option>)}</select></div><p className="insights-note">{orders?.basket_note} {cohort === 'historical' ? 'Orders reconstruct source baskets or authored older cases.' : 'These orders are authored contemporary scenarios.'}</p>{busy && <p>Loading orders…</p>}<div className="insights-order-list"><div className="insights-list-head"><span>Order / customer</span><span>Placed</span><span>Status</span><span>Basket</span></div>{orders?.rows.map(order => <button key={order.id} className={`insights-order-row ${selected === order.id ? 'selected' : ''}`} onClick={() => setSelected(order.id)}><span><strong>{order.id}</strong><small>{order.customer_name} · {order.customer_id}</small></span><time>{order.ordered_at}</time><span className="journey-status">{order.status}</span><b>{gbp(order.basket_pence)}</b></button>)}{orders && orders.total === 0 && <p className="insights-empty">No orders match these filters.</p>}</div><div className="pagination"><span>{orders?.total.toLocaleString() ?? 0} matching orders</span><button disabled={orderPage === 1} onClick={() => { setOrderPage(value => value - 1); setSelected(null) }}>Previous</button><strong>Page {orderPage}</strong><button disabled={!orders || orderPage * orders.page_size >= orders.total} onClick={() => { setOrderPage(value => value + 1); setSelected(null) }}>Next</button></div>{selected && <div className="insights-detail card"><div className="card-heading"><h3>{selected}</h3><button className="icon-button" aria-label="Close order detail" onClick={() => setSelected(null)}><X size={17}/></button></div>{!detail ? <p>Loading order history…</p> : <><p>{detail.order.customer_name} · {detail.order.ordered_at} · {detail.order.status}</p><div className="insights-detail-grid"><div><h4>Status history</h4>{detail.statuses.length ? detail.statuses.map(item => <p key={item.id}><time>{item.occurred_at}</time><strong>{item.status}</strong><small>{item.reason}</small></p>) : <p>No separate status transitions recorded.</p>}</div><div><h4>Linked records</h4>{detail.invoice && <p><strong>Invoice {detail.invoice.id}</strong><small>{gbp(detail.invoice.total_pence)} billed · {gbp(detail.invoice.outstanding_pence)} currently outstanding</small></p>}{detail.shipments?.map(item => <p key={item.id}><strong>Shipment {item.id}</strong><small>{item.units} units dispatched {item.dispatched_on} · {item.delivered_on ? `delivered ${item.delivered_on}` : 'delivery not recorded'}</small></p>)}{detail.invoice === null && detail.shipments === null && <p>Finance and logistics details require their respective employee scopes.</p>}</div></div><h4>Order lines</h4>{detail.lines.map(line => <div className="insights-line" key={line.id}><span>{line.product_name}<small>{line.product_id}</small></span><span>{line.shipped_quantity == null ? 'Fulfillment restricted' : String(line.shipped_quantity) + ' / ' + String(line.quantity) + ' shipped'}</span><strong>{gbp(line.line_pence)}</strong></div>)}{detail.line_count > detail.lines.length && <small>First {detail.preview_limit} of {detail.line_count} lines shown. Use Database Browse for the complete set.</small>}</>}</div>}</>}
    {tab === 'finance' && financeScope && <>{finance ? <><div className="insights-metrics"><div><small>Gross billed</small><strong>{gbp(finance.totals.gross_billed_pence)}</strong><span>{finance.totals.invoice_count} invoices posted</span></div><div><small>Credit notes issued</small><strong>{gbp(finance.totals.credits_issued_pence)}</strong></div><div><small>Net billing activity</small><strong>{gbp(finance.totals.net_billing_activity_pence)}</strong><span>Billing less dated credits</span></div>{settlementScope && <><div><small>Customer cash received</small><strong>{gbp(finance.totals.customer_cash_received_pence)}</strong><span>{finance.totals.payment_count} recorded receipts</span></div><div><small>Recorded cash outflow</small><strong>{gbp(finance.totals.recorded_cash_outflow_pence)}</strong><span>Fictional expense ledger only</span></div><div><small>Recorded cash difference</small><strong>{gbp(finance.totals.recorded_cash_difference_pence)}</strong><span>Not company profit</span></div><div><small>Current outstanding</small><strong>{gbp(finance.totals.current_outstanding_for_invoice_cohort_pence)}</strong><span>For invoices posted in this period</span></div></>}</div><div className="card insights-chart"><div className="card-heading"><h3>Monthly activity · GBP</h3><small>Hover for exact amounts</small></div><div className="insights-legend"><span className="billed">Invoice postings</span>{settlementScope && <><span className="received">Customer cash</span><span className="spent">Recorded outflow</span></>}</div>{finance.months.map(month => <div className="insights-month" key={month.month}><strong>{month.month}</strong><div className="insights-bars"><div className="billed" style={{ width: `${Math.max(0, month.gross_billed_pence / moneyMax * 100)}%` }} title={`Invoice postings ${gbp(month.gross_billed_pence)}`}/>{settlementScope && <><div className="received" style={{ width: `${Math.max(0, (month.customer_cash_received_pence ?? 0) / moneyMax * 100)}%` }} title={`Customer cash ${gbp(month.customer_cash_received_pence)}`}/><div className="spent" style={{ width: `${Math.max(0, (month.recorded_cash_outflow_pence ?? 0) / moneyMax * 100)}%` }} title={`Recorded outflow ${gbp(month.recorded_cash_outflow_pence)}`}/></>}</div><span>{gbp(month.net_billing_activity_pence)} net billing</span></div>)}</div>
      {settlementScope && finance.expense_categories !== null &&
        <div className="card insights-category-card">
          <div className="card-heading"><h3>Recorded outflow by category</h3>
            <small>Select a category to inspect its ledger entries</small></div>
          {finance.expense_categories.length ? finance.expense_categories.map(item =>
            <button type="button" className="insights-category" key={item.category}
              aria-label={`Browse ${item.category.replaceAll('_', ' ')} expenses`}
              onClick={() => { setCategory(item.category); setExpensePage(1); setTab('expenses') }}>
              <span>{item.category.replaceAll('_', ' ')}</span>
              <div className="insights-category-track" aria-hidden="true"><div
                style={{ width: Math.max(0, item.amount_pence /
                  (finance.totals.recorded_cash_outflow_pence || 1) * 100) + '%' }}/></div>
              <strong>{gbp(item.amount_pence)}<small>{item.expense_count} payments</small></strong>
            </button>) : <p className="insights-note">No recorded expenses in this period.</p>}
        </div>}
      <p className="insights-note">{finance.definitions.net_billing_activity} {finance.definitions.customer_cash_received} {finance.definitions.outflows}</p></> : <p>Loading financial activity…</p>}</>}
    {tab === 'expenses' && settlementScope && <>
      <p className="insights-note">This is an explicitly fictional 2026 cash ledger. Payments linked to supplier orders do not prove those orders are fully settled. The ledger covers selected scenarios, not all company expenses.</p>
      <div className="insights-order-filters">
        <label className="search-box"><Search size={16}/><input
          aria-label="Search expenses" value={expenseQuery} maxLength={100}
          placeholder="Payee, expense ID, supplier or purchase order"
          onChange={event => { setExpenseQuery(event.target.value); setExpensePage(1) }}
        /></label>
        <select aria-label="Expense category" value={category}
          onChange={event => { setCategory(event.target.value); setExpensePage(1) }}>
          <option value="">All expense categories</option>
          {['supplier_payment', 'logistics', 'packaging', 'marketing', 'software'].map(value =>
            <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
        </select>
      </div>
      {expenses && !expenses.available && <div className="notice">No expense ledger is installed for this cohort.</div>}
      {expenses?.available && <p className="insights-note">{expenses.total} matching payments |
        {gbp(expenses.filtered_amount_pence)} recorded outflow across all matching pages.</p>}
      {expenses?.rows.map(item =>
        <div className="card insights-expense" key={item.id}>
          <div>
            <small>{item.paid_on} | {item.category.replaceAll('_', ' ')}</small>
            <h3>{item.payee}</h3>
            <p>{item.description}</p>
            <small>{item.id}{item.purchase_order_id ? ' | Purchase order ' + item.purchase_order_id : ''}
              {item.supplier_id ? ' | Supplier ' + item.supplier_id : ''}</small>
          </div>
          <strong>{gbp(item.amount_pence)}</strong>
        </div>)}
      {expenses?.available && expenses.total === 0 &&
        <p className="insights-empty">No expenses match this period and filters.</p>}
      <div className="pagination">
        <span>{expenses?.total ?? 0} recorded expenses</span>
        <button disabled={expensePage === 1} onClick={() => setExpensePage(value => value - 1)}>Previous</button>
        <strong>Page {expensePage}</strong>
        <button disabled={!expenses || expensePage * expenses.page_size >= expenses.total}
          onClick={() => setExpensePage(value => value + 1)}>Next</button>
      </div>
    </>}
  </section>
}
