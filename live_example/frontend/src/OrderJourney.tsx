import { useEffect, useState } from 'react'
import { ArrowUpRight, CircleCheck, Clock3, ReceiptText, Truck } from 'lucide-react'
import { api } from './api'

type Event = {
  date: string
  kind: string
  title: string
  detail: string
  basis: string
  table: string
  record_id: string
  amount_pence: number | null
}
type Journey = {
  order: { id: string; customer_id: string; customer_name: string; status: string; source_invoice_no: string | null }
  invoice: { id: string; total_pence: number; outstanding_pence: number } | null
  items: { id: string; product_id: string; product_name: string; quantity: number; shipped_quantity: number; line_pence: number }[]
  events: Event[]
}

const pounds = (pence: number) => `£${(pence / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export function OrderJourney({ orderId, openRecord, revision }: {
  orderId: string
  openRecord: (table: string, id: string) => void
  revision: number
}) {
  const [data, setData] = useState<Journey | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError('')
    api<Journey>(`/database/order-journey/${encodeURIComponent(orderId)}`)
      .then(value => { if (active) setData(value) })
      .catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [orderId, revision])
  if (error) return <div className="notice">Order journey: {error}</div>
  if (!data) return <p className="journey-loading">Loading linked order history…</p>
  return <section className="order-journey" aria-label="Order journey">
    <div className="journey-heading">
      <div><span className="eyebrow">LINKED BUSINESS HISTORY</span><h4>Order journey</h4></div>
      <span className="journey-status">{data.order.status}</span>
    </div>
    <p className="journey-intro">Follow this order across sales, billing, delivery, settlement and service. Labels show how each event was created.</p>
    <div className="journey-summary">
      <button onClick={() => openRecord('customers', data.order.customer_id)}><small>Customer</small><strong>{data.order.customer_name}</strong><ArrowUpRight size={15}/></button>
      <div><small>Invoice</small><strong>{data.invoice ? pounds(data.invoice.total_pence) : 'No invoice'}</strong></div>
      <div><small>Outstanding</small><strong>{data.invoice ? pounds(data.invoice.outstanding_pence) : '—'}</strong></div>
      <div><small>Shipped units</small><strong>{data.items.reduce((sum, item) => sum + item.shipped_quantity, 0)} / {data.items.reduce((sum, item) => sum + item.quantity, 0)}</strong></div>
    </div>
    <div className="journey-timeline">
      {data.events.map((event, index) => <div className="journey-event" key={`${event.kind}:${event.record_id}:${event.date}:${index}`}>
        <div className={`journey-icon journey-${event.kind}`} aria-hidden="true">{event.kind === 'invoice' || event.kind === 'credit' || event.kind === 'payment' ? <ReceiptText size={16}/> : event.kind === 'dispatch' || event.kind === 'delivery' ? <Truck size={16}/> : event.kind === 'order' ? <CircleCheck size={16}/> : <Clock3 size={16}/>}</div>
        <div className="journey-event-body"><div className="journey-event-top"><time>{event.date}</time><span className="journey-basis">{event.basis}</span></div><strong>{event.title}</strong><p>{event.detail}</p><button className="link-button" onClick={() => openRecord(event.table, event.record_id)}>Open {event.table} record <ArrowUpRight size={13}/></button></div>
        {event.amount_pence !== null && <b className="journey-amount">{pounds(event.amount_pence)}</b>}
      </div>)}
    </div>
    <div className="journey-items"><h5>Order lines</h5>{data.items.map(item => <div key={item.id}><button className="link-button" onClick={() => openRecord('products', item.product_id)}>{item.product_name} <ArrowUpRight size={13}/></button><span>{item.shipped_quantity} / {item.quantity} shipped</span><strong>{pounds(item.line_pence)}</strong></div>)}</div>
    <p className="journey-footnote">{data.order.source_invoice_no
      ? 'The invoice date and basket lines come from the prepared retail dataset. The order, logistics, settlement and service steps are reconstructed or fictional, as labeled above.'
      : 'This order is an authored demo scenario. Its business history does not claim to come from source transactions.'}</p>
  </section>
}
