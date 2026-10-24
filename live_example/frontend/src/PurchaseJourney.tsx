import { useEffect, useState } from 'react'
import { ArrowUpRight, CircleCheck, PackageCheck, Truck } from 'lucide-react'
import { api } from './api'

type Line = {
  id: string; product_id: string; product_name: string; ordered_units: number
  received_units: number; outstanding_units: number; inventory_id: string | null
  on_hand: number | null; reserved: number | null; inventory_as_of: string | null
}
type Receipt = {
  id: string; received_on: string; quantity: number; purchase_order_item_id: string
  product_id: string; product_name: string; movement_id: string | null
  movement_quantity: number | null; movement_on: string | null; movement_kind: string | null
  movement_warehouse_id: string | null; movement_product_id: string | null
}
type Journey = {
  order: { id: string; supplier_id: string; supplier_name: string; warehouse_id: string; warehouse_name: string; placed_on: string; expected_on: string; status: string }
  basis: string
  totals: { line_count: number; ordered_units: number; received_units: number; outstanding_units: number; receipt_count: number }
  lines: Line[]; receipts: Receipt[]; preview_limit: number
}

export function PurchaseJourney({ orderId, openRecord, revision }: {
  orderId: string
  openRecord: (table: string, id: string) => void
  revision: number
}) {
  const [data, setData] = useState<Journey | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError('')
    api<Journey>(`/database/purchase-journey/${encodeURIComponent(orderId)}`)
      .then(value => { if (active) setData(value) })
      .catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [orderId, revision])
  if (error) return <div className="notice">Supplier journey: {error}</div>
  if (!data) return <p className="journey-loading">Loading linked supplier history…</p>
  const { order, totals } = data
  return <section className="order-journey" aria-label="Supplier order journey">
    <div className="journey-heading"><div><span className="eyebrow">LINKED BUSINESS HISTORY</span><h4>Supplier order journey</h4></div><span className="journey-status">{order.status}</span></div>
    <p className="journey-intro">Follow the order from supplier to goods receipt and stock ledger. Quantities come from linked records, not the status or original description.</p>
    <div className="journey-summary">
      <button onClick={() => openRecord('suppliers', order.supplier_id)}><small>Supplier</small><strong>{order.supplier_name}</strong><ArrowUpRight size={15}/></button>
      <button onClick={() => openRecord('warehouses', order.warehouse_id)}><small>Warehouse</small><strong>{order.warehouse_name}</strong><ArrowUpRight size={15}/></button>
      <div><small>Received / ordered</small><strong>{totals.received_units} / {totals.ordered_units} units</strong></div>
      <div><small>Outstanding</small><strong>{totals.outstanding_units} units</strong></div>
    </div>
    <div className="journey-timeline">
      <div className="journey-event"><div className="journey-icon"><CircleCheck size={16}/></div><div className="journey-event-body"><div className="journey-event-top"><time>{order.placed_on}</time><span className="journey-basis">{data.basis}</span></div><strong>Purchase order placed</strong><p>Expected {order.expected_on}. {totals.line_count} lines and {totals.ordered_units} units.</p></div></div>
      {data.receipts.map(receipt => {
        const matched = receipt.movement_id !== null && receipt.movement_kind === 'receipt' && receipt.movement_quantity === receipt.quantity && receipt.movement_on === receipt.received_on && receipt.movement_product_id === receipt.product_id && receipt.movement_warehouse_id === order.warehouse_id
        return <div className="journey-event" key={receipt.id}><div className="journey-icon journey-delivery"><Truck size={16}/></div><div className="journey-event-body"><div className="journey-event-top"><time>{receipt.received_on}</time><span className="journey-basis">{data.basis}</span></div><strong>{receipt.quantity} units received · {receipt.product_name}</strong><p>{matched ? 'Linked stock receipt matches product, warehouse, date and quantity.' : receipt.movement_id ? 'Linked stock movement needs review: details do not match this receipt.' : 'No linked stock movement found for this receipt.'}</p><button className="link-button" onClick={() => openRecord('goods_receipts', receipt.id)}>Open goods receipt <ArrowUpRight size={13}/></button>{receipt.movement_id && <button className="link-button" onClick={() => openRecord('stock_movements', receipt.movement_id!)}>Open stock movement <ArrowUpRight size={13}/></button>}<button className="link-button" onClick={() => openRecord('purchase_order_items', receipt.purchase_order_item_id)}>Open order line <ArrowUpRight size={13}/></button></div><b className="journey-amount">+{receipt.quantity}</b></div>
      })}
    </div>
    <div className="journey-items"><h5>Purchase lines</h5>{data.lines.map(line => <div key={line.id}><button className="link-button" onClick={() => openRecord('products', line.product_id)}>{line.product_name} <ArrowUpRight size={13}/></button><span>{line.received_units} / {line.ordered_units} received</span><strong>{line.outstanding_units} due</strong><small className="purchase-line-detail"><button className="link-button" onClick={() => openRecord('purchase_order_items', line.id)}>Open line <ArrowUpRight size={13}/></button>{line.inventory_id ? <button className="link-button" onClick={() => openRecord('inventory', line.inventory_id!)}><PackageCheck size={13}/> Current inventory: {line.on_hand} on hand, {line.reserved} reserved · {line.inventory_as_of}</button> : <span>No inventory row for this warehouse and product.</span>}</small></div>)}</div>
    {(totals.line_count > data.lines.length || totals.receipt_count > data.receipts.length) && <p className="journey-footnote">Showing the first {data.preview_limit} lines and receipts at most; totals cover every linked row. Use Browse to inspect the rest.</p>}
    <p className="journey-footnote">{data.basis}. The purchase order describes a modeled workflow; it is not a source supplier transaction. Inventory is a current warehouse balance, not stock reserved for this purchase order. The original provenance field describes the seed scenario and may predate later receipts.</p>
  </section>
}
