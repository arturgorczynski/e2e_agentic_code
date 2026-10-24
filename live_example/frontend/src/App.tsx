import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ArrowRight, BarChart3, BookOpen, Bot, Boxes, Database, Download, ExternalLink, FileText, GitBranch, Menu, MessageCircle, Package, Play, Plus, Search, Send, ShoppingBag, Terminal, UserRound, Wrench, X } from 'lucide-react'
import { api, post, type DocumentMeta, type Persona, type RecordRow, type Snapshot, type Thread } from './api'
import { categoryImage, productImageAlt, productImageLabel } from './catalogVisuals'
import { RowEditor } from './DatabaseTools'
import { DataAudit } from './DataAudit'
import { RelationshipMap } from './RelationshipGraph'
import { PersonaSwitch } from './PersonaSwitch'
import { Workbench } from './ToolWorkbench'
import { Execution } from './ExecutionInspector'
import { ResetPanel } from './ResetPanel'
import { OrderJourney } from './OrderJourney'
import { PurchaseJourney } from './PurchaseJourney'
import { BusinessInsights } from './BusinessInsights'

type View = 'home' | 'customer' | 'employee' | 'insights' | 'wiki' | 'tools' | 'database' | 'execution'
const links: { id: View; label: string; icon: typeof ShoppingBag }[] = [
  { id: 'home', label: 'Home', icon: ShoppingBag },
  { id: 'customer', label: 'My account', icon: UserRound },
  { id: 'employee', label: 'Workspace', icon: BarChart3 },
  { id: 'insights', label: 'Insights', icon: ShoppingBag },
  { id: 'wiki', label: 'Knowledge', icon: BookOpen },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'database', label: 'Database', icon: Database },
  { id: 'execution', label: 'Execution', icon: Terminal },
]

function useResource<T>(path: string | null, refresh = 0) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!path) { setData(null); return }
    let alive = true
    setLoading(true); setError(''); setData(null)
    api<T>(path).then(value => { if (alive) setData(value) }).catch(err => { if (alive) setError(err.message) }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [path, refresh])
  return { data, loading, error, reload: setData }
}

function Notice({ text }: { text: string }) { return <div className="notice">{text}</div> }
function Loading() { return <div className="loading"><span className="spinner" /> Loading Acme data…</div> }
function SectionTitle({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return <div className="section-title"><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>{description && <p>{description}</p>}</div>
}
function money(value: unknown) { return typeof value === 'number' ? `£${(value / 100).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—' }
function fmt(value: unknown) { return value === null || value === undefined ? '—' : String(value) }
function status(value: unknown) { return <span className={`status status-${String(value).replace(/[^a-z]/gi, '')}`}>{fmt(value)}</span> }

function Home({ navigate }: { navigate: (v: View) => void }) {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null)
  const bootstrap = useResource<{ counts: Record<string, number>; business_date: string; contemporary_date: string }>('/bootstrap')
  const catalog = useResource<{ rows: RecordRow[]; total: number; page: number }>(`/products?q=${encodeURIComponent(q)}&page=${page}`)
  const product = useResource<RecordRow>(selectedProduct ? `/products/${encodeURIComponent(selectedProduct)}` : null)
  return <><section className="hero"><div className="hero-content"><span className="hero-kicker">ACME WHOLESALE · LOCAL DEMO</span><h1>Made for the work<br/><em>behind every order.</em></h1><p>Products, people and practical knowledge in one place. Explore the fictional Acme Wholesale business through its real local demo data.</p><div className="hero-actions"><button className="button button-light" onClick={() => document.getElementById('catalog')?.scrollIntoView({ behavior: 'smooth' })}>Explore products <ArrowRight size={17}/></button><button className="button button-outline" onClick={() => navigate('customer')}>My account</button></div></div><div className="hero-art" aria-hidden="true"><div className="art-label">SUPPLY / SERVICE / INSIGHT</div></div></section>
    <section className="stats-strip">{Object.entries(bootstrap.data?.counts ?? {}).map(([key, value]) => <div key={key}><strong>{value.toLocaleString('en-GB')}</strong><span>{key}</span></div>)}<div><strong>{bootstrap.data?.business_date.slice(0, 4) ?? '2011'}</strong><span>source history reference</span></div><div><strong>{bootstrap.data?.contemporary_date.slice(0, 4) ?? '2026'}</strong><span>fictional scenario history</span></div></section>
    <section id="catalog" className="content-section"><div className="section-row"><SectionTitle eyebrow="OUR CATALOG" title="Products for every operation" description="Search the actual Acme product table. Pricing reflects the latest observed local record." /><label className="search-box catalog-search"><Search size={17}/><input value={q} onChange={e => { setQ(e.target.value); setPage(1) }} placeholder="Search products or codes" /></label></div>{catalog.loading && <Loading />}{catalog.error && <Notice text={catalog.error} />}<div className="product-grid">{catalog.data?.rows.map(item => <button type="button" className="product-card" key={String(item.id)} onClick={() => setSelectedProduct(String(item.id))}><div className="product-image">{categoryImage(item.category, item.id) ? <img src={categoryImage(item.category, item.id)} alt={productImageAlt(item.id, item.category, item.name)} loading="lazy"/> : <Package size={40} strokeWidth={1.3}/>}<span>{fmt(item.category)}</span><small>{productImageLabel(item.id, item.category)}</small></div><div className="product-info"><small>{fmt(item.id)}</small><h3>{fmt(item.name)}</h3><div className="product-bottom"><strong>{item.last_price_gbp ? `£${Number(item.last_price_gbp).toFixed(2)}` : 'Price on request'}</strong><ArrowRight size={18}/></div></div></button>)}</div>{catalog.data && <div className="pagination"><span>{catalog.data.total.toLocaleString()} products</span><button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button><strong>{page}</strong><button disabled={page * 24 >= catalog.data.total} onClick={() => setPage(page + 1)}>Next</button></div>}</section>
    <section className="callout"><div><span className="eyebrow">THE ACME PORTAL</span><h2>One company. Every perspective.</h2><p>Choose a demo customer, employee or superuser to follow the same data through orders, documents, tools and agent traces.</p></div><button className="button button-light" onClick={() => navigate('wiki')}>Browse knowledge <ArrowRight size={17}/></button></section>{selectedProduct && <ProductPreview data={product.data} loading={product.loading} error={product.error} close={() => setSelectedProduct(null)} />}</>
}

function ProductPreview({ data, loading, error, close }: { data: RecordRow | null; loading: boolean; error: string; close: () => void }) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [close])
  return <div className="modal-backdrop" onClick={close}>
    <div className="modal product-preview" role="dialog" aria-modal="true" aria-label="Product details" onClick={event => event.stopPropagation()}>
      <div className="modal-title"><div><span className="eyebrow">PRODUCT DETAIL</span><h2>{fmt(data?.name)}</h2></div><button className="icon-button" onClick={close} aria-label="Close product details"><X size={20}/></button></div>
      {loading && <Loading />}{error && <Notice text={error} />}
      {data && <div className="product-preview-body">
        <div className="product-preview-image">{categoryImage(data.category, data.id) ? <img src={categoryImage(data.category, data.id)} alt={productImageAlt(data.id, data.category, data.name)} /> : <Package size={46} />}<small>{productImageLabel(data.id, data.category)}</small></div>
        <div className="product-preview-facts"><div><small>Product code</small><strong>{fmt(data.id)}</strong></div>{data.source_stock_code != null && <div><small>Source stock code</small><strong>{fmt(data.source_stock_code)}</strong></div>}<div><small>Category</small><strong>{fmt(data.category)}</strong></div><div><small>Latest observed unit price</small><strong>{data.last_price_gbp ? `£${Number(data.last_price_gbp).toFixed(2)}` : 'Price on request'}</strong></div>{data.price_observed_at != null && <p>Price observed on {fmt(data.price_observed_at)} in the local historical dataset. This is a catalog observation, not a live offer.</p>}</div>
      </div>}
    </div>
  </div>
}

function ChatPanel({ persona }: { persona: Persona }) {
  const [thread, setThread] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const suggestions = persona.kind === 'customer'
    ? ['Show my recent orders', 'What is my current address?']
    : ['Find order DEMO-ORD-002', 'What does the returns policy say?']
  useEffect(() => { setThread(null); setSnapshot(null); api<Thread[]>('/conversations').then(rows => { const saved = rows.find(row => row.title !== 'Tools playground'); if (saved) setThread(saved.id) }).catch(() => {}) }, [persona.kind, persona.subject_id])
  useEffect(() => {
    if (!thread) return
    let active = true
    const load = () => api<Snapshot>(`/conversations/${thread}`).then(data => { if (active) setSnapshot(data) }).catch(err => { if (active) setError(err.message) })
    void load()
    const timer = setInterval(load, 2500)
    return () => { active = false; clearInterval(timer) }
  }, [thread])
  async function send() {
    if (!text.trim() || busy) return
    setBusy(true); setError('')
    try { const sent = await post<{ thread_id: string }>('/chat', { text, thread_id: thread }); setThread(sent.thread_id); setText(''); setSnapshot(await api<Snapshot>(`/conversations/${sent.thread_id}`)) }
    catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="chat-panel"><div className="chat-head"><div className="chat-icon"><Bot size={21}/></div><div><strong>{persona.kind === 'customer' ? 'Your Acme assistant' : 'Acme operations agent'}</strong><small>{persona.kind === 'customer' ? 'Answers from your account and available guides' : 'Answers grounded in company tools'}</small></div><button className="icon-button" title="New conversation" onClick={() => { setThread(null); setSnapshot(null) }}><MessageCircle size={17}/></button></div><div className="messages">{!snapshot?.chat.length && <div className="empty-chat"><Bot size={29}/><strong>What can I help you find?</strong><p>{persona.kind === 'customer' ? 'Try “What is my current address?” or “Show my recent orders.”' : 'Ask about an order, customer, policy or business summary.'}</p><div className="chat-suggestions">{suggestions.map(prompt => <button type="button" key={prompt} onClick={() => setText(prompt)}>{prompt}</button>)}</div></div>}{snapshot?.chat.map((message, index) => <div key={index} className={`message ${message.role}`}><span>{message.role === 'assistant' ? 'Acme assistant' : 'You'}</span><div><ReactMarkdown>{message.role === 'assistant' ? message.content.replace(/<tool_call>\s*$/i, '') : message.content}</ReactMarkdown></div></div>)}{snapshot && ['queued', 'running'].includes(snapshot.status) && <div className="thinking"><span className="spinner" /> Agent is working…</div>}</div>{snapshot?.error && <Notice text={snapshot.error} />}{error && <Notice text={error} />}<div className="chat-compose"><textarea value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }} placeholder="Ask Acme a question…" rows={2}/><button disabled={busy || !text.trim()} onClick={send} aria-label="Send message"><Send size={19}/></button></div><small className="chat-footnote">Local learning demo · inspect actual calls in Execution</small></div>
}

function Customer({ persona, choose }: { persona: Persona | null; choose: () => void }) {
  const allowed = persona?.kind === 'customer'
  const [ordersPage, setOrdersPage] = useState(1)
  const [invoicesPage, setInvoicesPage] = useState(1)
  const [order, setOrder] = useState<string | null>(null)
  const [invoice, setInvoice] = useState<string | null>(null)
  const [invoiceLedgerPage, setInvoiceLedgerPage] = useState(1)
  type AccountPage = {
    profile: RecordRow
    contacts: RecordRow[]
    activity: { order_count: number; invoice_count: number; first_order_at: string | null; last_order_at: string | null }
    orders: RecordRow[]
    invoices: RecordRow[]
    orders_page: number
    invoices_page: number
    page_size: number
  }
  const account = useResource<AccountPage>(
    allowed ? `/customer?orders_page=${ordersPage}&invoices_page=${invoicesPage}` : null
  )
  const detail = useResource<{ order: RecordRow; items: RecordRow[] }>(
    order ? `/customer/orders/${encodeURIComponent(order)}` : null
  )
  const invoiceDetail = useResource<{
    invoice: RecordRow; entries: RecordRow[]; total_entries: number; page: number; page_size: number
  }>(invoice ? `/customer/invoices/${encodeURIComponent(invoice)}?page=${invoiceLedgerPage}` : null)
  if (!allowed || !persona) return <Gate title="Your account, your orders" description="Choose a customer ID in the demo persona switcher to see its profile, purchases and private assistant." choose={choose}/>

  const data = account.data
  return <section className="content-section">
    <SectionTitle eyebrow="CUSTOMER PORTAL" title={`Good to see you, ${persona.display_name}`} description={`Customer ID ${persona.subject_id} · A live view of this customer's local records.`}/>
    {account.loading && <Loading/>}
    {account.error && <Notice text={account.error}/>}
    <div className="portal-grid">
      <div className="portal-main">{data && <>
        <div className="summary-grid">
          <div className="metric-card"><small>Orders</small><strong>{data.activity.order_count.toLocaleString()}</strong><span>Lifetime · browse all pages below</span></div>
          <div className="metric-card"><small>Invoices</small><strong>{data.activity.invoice_count.toLocaleString()}</strong><span>Lifetime · browse all pages below</span></div>
          <div className="metric-card"><small>Account segment</small><strong className="metric-word">{fmt(data.profile.segment)}</strong><span>Acme Wholesale</span></div>
          <div className="metric-card"><small>Last order</small><strong className="metric-word">{fmt(data.activity.last_order_at)}</strong><span>First: {fmt(data.activity.first_order_at)}</span></div>
        </div>
        <div className="card"><div className="card-heading"><h3>Account details</h3><UserRound size={18}/></div><div className="detail-grid">
          {['id', 'name', 'address', 'country', 'account_manager', 'payment_terms_days'].map(key =>
            <div key={key}><small>{key.replaceAll('_', ' ')}</small><strong>{fmt(data.profile[key])}{key === 'payment_terms_days' ? ' days' : ''}</strong></div>
          )}
        </div></div>
        <div className="card"><div className="card-heading"><h3>Customer contacts</h3><UserRound size={18}/></div><div className="detail-grid">
          {data.contacts.map(contact => <div key={String(contact.id)}><small>{fmt(contact.responsibility)}</small><strong>{fmt(contact.name)}</strong><small>{fmt(contact.email)}</small></div>)}
        </div></div>
        <div className="card"><div className="card-heading"><h3>Orders</h3><ShoppingBag size={18}/></div>
          <div className="list-table"><div className="list-head"><span>Order</span><span>Date</span><span>Status</span><span>Total</span></div>
            {data.orders.map(item => <button className="list-row" key={String(item.id)} onClick={() => setOrder(String(item.id))}><span className="mono">{fmt(item.id)}</span><span>{fmt(item.ordered_at)}</span><span>{status(item.status)}</span><strong>{money(item.total_pence)}</strong></button>)}
          </div>
          <div className="pagination"><span>{data.orders.length ? (ordersPage - 1) * data.page_size + 1 : 0}–{(ordersPage - 1) * data.page_size + data.orders.length} of {data.activity.order_count.toLocaleString()} orders</span><button disabled={ordersPage === 1} onClick={() => setOrdersPage(page => page - 1)}>Previous</button><strong>Page {ordersPage}</strong><button disabled={ordersPage * data.page_size >= data.activity.order_count} onClick={() => setOrdersPage(page => page + 1)}>Next</button></div>
        </div>
        <div className="card"><div className="card-heading"><h3>Invoices</h3><FileText size={18}/></div>
          <div className="list-table"><div className="list-head"><span>Invoice</span><span>Posted</span><span>Total</span><span>Outstanding</span></div>
            {data.invoices.map(item => <button className="list-row" key={String(item.id)} onClick={() => { setInvoice(String(item.id)); setInvoiceLedgerPage(1) }}><span className="mono">{fmt(item.id)}</span><span>{fmt(item.posted_on)}</span><span>{money(item.total_pence)}</span><strong>{money(item.outstanding_pence)}</strong></button>)}
          </div>
          <div className="pagination"><span>{data.invoices.length ? (invoicesPage - 1) * data.page_size + 1 : 0}–{(invoicesPage - 1) * data.page_size + data.invoices.length} of {data.activity.invoice_count.toLocaleString()} invoices</span><button disabled={invoicesPage === 1} onClick={() => setInvoicesPage(page => page - 1)}>Previous</button><strong>Page {invoicesPage}</strong><button disabled={invoicesPage * data.page_size >= data.activity.invoice_count} onClick={() => setInvoicesPage(page => page + 1)}>Next</button></div>
        </div>
      </>}</div>
      <ChatPanel persona={persona}/>
    </div>
    {order && <div className="modal-backdrop" onClick={() => setOrder(null)}><div className="modal" onClick={event => event.stopPropagation()}>
      <div className="modal-title"><div><span className="eyebrow">ORDER DETAIL</span><h2>{order}</h2></div><button className="icon-button" onClick={() => setOrder(null)} aria-label="Close order"><X size={20}/></button></div>
      {detail.loading && <Loading/>}{detail.error && <Notice text={detail.error}/>}
      {detail.data && <><p>{fmt(detail.data.order.ordered_at)} · {fmt(detail.data.order.status)}</p>{detail.data.items.map(item => <div className="order-line" key={String(item.id)}><div><strong>{fmt(item.product_name)}</strong><small>{fmt(item.product_id)} · Quantity {fmt(item.quantity)}</small></div><strong>{money(item.line_pence)}</strong></div>)}</>}
    </div></div>}
    {invoice && <div className="modal-backdrop" onClick={() => setInvoice(null)}><div className="modal" onClick={event => event.stopPropagation()}>
      <div className="modal-title"><div><span className="eyebrow">INVOICE DETAIL</span><h2>{invoice}</h2></div><button className="icon-button" onClick={() => setInvoice(null)} aria-label="Close invoice"><X size={20}/></button></div>
      {invoiceDetail.loading && <Loading/>}{invoiceDetail.error && <Notice text={invoiceDetail.error}/>}
      {invoiceDetail.data && <>
        <div className="detail-grid">
          <div><small>Order</small><strong>{fmt(invoiceDetail.data.invoice.order_id)}</strong></div>
          <div><small>Posted</small><strong>{fmt(invoiceDetail.data.invoice.posted_on)}</strong></div>
          <div><small>Due</small><strong>{fmt(invoiceDetail.data.invoice.due_on)}</strong></div>
          <div><small>Original amount</small><strong>{money(invoiceDetail.data.invoice.total_pence)}</strong></div>
          <div><small>Outstanding</small><strong>{money(invoiceDetail.data.invoice.outstanding_pence)}</strong></div>
        </div>
        <h3>Payments and credits</h3>
        <p>Payment allocations and credit notes reduce the balance. A credit note does not prove a cash refund.</p>
        {invoiceDetail.data.entries.length ? invoiceDetail.data.entries.map(entry => <div className="order-line" key={String(entry.id)}><div><strong>{entry.kind === 'credit_note' ? 'Credit note' : 'Payment allocation'} · {fmt(entry.id)}</strong><small>{fmt(entry.applied_on)} · {fmt(entry.reference_id)}{entry.reason ? ` · ${fmt(entry.reason)}` : ''}</small></div><strong>{money(entry.amount_pence)}</strong></div>) : <p>No linked payment allocations or credit notes.</p>}
        <div className="pagination"><span>{invoiceDetail.data.total_entries} entries</span><button disabled={invoiceLedgerPage === 1} onClick={() => setInvoiceLedgerPage(page => page - 1)}>Previous</button><strong>Page {invoiceLedgerPage}</strong><button disabled={invoiceLedgerPage * invoiceDetail.data.page_size >= invoiceDetail.data.total_entries} onClick={() => setInvoiceLedgerPage(page => page + 1)}>Next</button></div>
      </>}
    </div></div>}
  </section>
}

function Gate({ title, description, choose }: { title: string; description: string; choose: () => void }) { return <section className="gate"><div className="gate-icon"><UserRound size={32}/></div><span className="eyebrow">DEMO ACCESS</span><h2>{title}</h2><p>{description}</p><button className="button button-dark" onClick={choose}>Choose a persona <ArrowRight size={17}/></button></section> }

function Employee({ persona, choose, navigate }: { persona: Persona | null; choose: () => void; navigate: (v: View) => void }) {
  const allowed = persona?.kind === 'employee' || persona?.kind === 'super_user'
  const resource = useResource<{ counts: Record<string, number>; recent_orders: RecordRow[]; order_focus: string }>(allowed ? '/employee' : null)
  if (!allowed || !persona) return <Gate title="An operational view of Acme" description="Choose an employee or superuser persona to inspect company activity and work with the internal agent." choose={choose}/>
  return <section className="content-section"><SectionTitle eyebrow="EMPLOYEE WORKSPACE" title={`Welcome, ${persona.display_name}`} description={`${persona.job_title ?? persona.access_profile.replace('_', ' ')} · ${persona.department ?? 'Company'} / ${persona.permissions.length} enabled permissions`}/><p className="view-explainer">Workspace is an internal company overview. The counts cover the whole company. Orders belong to customers; the feed shows company-wide orders unless a superuser selects a department focus. My Account shows only the selected customer’s own profile, orders and invoices. The agent and tools use the selected persona's permissions.</p>{resource.error && <Notice text={resource.error}/>}<div className="portal-grid"><div className="portal-main"><div className="summary-grid">{Object.entries(resource.data?.counts ?? {}).map(([key, value]) => <div className="metric-card" key={key}><small>{key}</small><strong>{value.toLocaleString('en-GB')}</strong><span>In company database</span></div>)}</div><div className="card"><div className="card-heading"><h3>{resource.data?.order_focus && resource.data.order_focus !== 'all' ? `Recent customer orders · ${persona.display_name} focus` : 'Recent company customer orders'}</h3><ShoppingBag size={18}/></div>{resource.loading && <Loading/>}<div className="list-table"><div className="list-head"><span>Order</span><span>Customer</span><span>Date</span><span>Status</span></div>{resource.data?.recent_orders.map(item => <div className="list-row" key={String(item.id)}><span className="mono">{fmt(item.id)}</span><span>{fmt(item.customer)}</span><span>{fmt(item.ordered_at)}</span><span>{status(item.status)}</span></div>)}</div></div><div className="quick-links"><button onClick={() => navigate('database')}><Database size={19}/><span><strong>Explore the database</strong><small>Tables and views within your scope</small></span><ArrowRight size={17}/></button><button onClick={() => navigate('tools')}><Wrench size={19}/><span><strong>Open tool workbench</strong><small>Run the agent’s tools directly</small></span><ArrowRight size={17}/></button><button onClick={() => navigate('wiki')}><BookOpen size={19}/><span><strong>Search company knowledge</strong><small>Policies and working documents</small></span><ArrowRight size={17}/></button></div></div><ChatPanel persona={persona}/></div></section>
}

function Wiki({ persona, choose }: { persona: Persona | null; choose: () => void }) {
  const [q, setQ] = useState('')
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState('')
  const [tag, setTag] = useState('')
  const [scope, setScope] = useState('')
  const [docStatus, setDocStatus] = useState('')
  const [effectiveOn, setEffectiveOn] = useState(() => {
    const today = new Date()
    return [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-')
  })
  const [owner, setOwner] = useState('')
  const [linkedType, setLinkedType] = useState('')
  const [sort, setSort] = useState('title')
  const [selected, setSelected] = useState<DocumentMeta | null>(null)
  const params = new URLSearchParams({ q, keyword, category, tag, scope, status: docStatus, owner, linked_type: linkedType, sort })
  if (effectiveOn) params.set('effective_on', effectiveOn)
  const docs = useResource<{ documents: DocumentMeta[]; total: number; categories: string[] }>(persona ? `/documents?${params}` : null)
  const categoryList = useResource<{ categories: string[]; tags: string[]; scopes: string[]; statuses: string[]; owners: string[]; linked_types: string[] }>(persona ? '/documents/categories' : null)
  const detail = useResource<{ metadata: DocumentMeta; markdown: string }>(selected ? `/documents/${selected.document_id}/${selected.version}` : null)
  useEffect(() => {
    if (selected && docs.data && !docs.data.documents.some(doc =>
      doc.document_id === selected.document_id && doc.version === selected.version
    )) setSelected(null)
  }, [docs.data, selected])
  if (!persona) return <Gate title="The Acme knowledge library" description="Choose a demo persona to see documents available to that customer or employee." choose={choose}/>
  const categories = categoryList.data?.categories ?? []
  return <section className="content-section wiki-page"><SectionTitle eyebrow="COMPANY KNOWLEDGE" title="Knowledge, well organised." description="Policies, guides and operational notes from Acme’s existing Markdown corpus, with exact versions and visibility."/><div className="wiki-controls"><label className="search-box"><Search size={17}/><input value={q} maxLength={200} onChange={e => setQ(e.target.value)} placeholder="Search title or document ID" /></label><select value={category} onChange={e => setCategory(e.target.value)}><option value="">All categories</option>{categories.map(c => <option key={c} value={c}>{c.replaceAll('_', ' ')}</option>)}</select></div><div className="wiki-controls wiki-extra-filters"><label className="wiki-date-filter">Effective on <input aria-label="Document effective date" type="date" value={effectiveOn} onChange={e => setEffectiveOn(e.target.value)}/></label><button className="button button-small" onClick={() => setEffectiveOn('')}>All versions</button><label className="search-box"><Search size={16}/><input aria-label="Search document text" value={keyword} maxLength={200} onChange={e => setKeyword(e.target.value)} placeholder="Keyword in document text"/></label><select aria-label="Filter tag" value={tag} onChange={e => setTag(e.target.value)}><option value="">All tags</option>{categoryList.data?.tags.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Filter visibility" value={scope} onChange={e => setScope(e.target.value)}><option value="">All visibility scopes</option>{categoryList.data?.scopes.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Filter status" value={docStatus} onChange={e => setDocStatus(e.target.value)}><option value="">All statuses</option>{categoryList.data?.statuses.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Filter owner" value={owner} onChange={e => setOwner(e.target.value)}><option value="">All owners</option>{categoryList.data?.owners.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Filter linked record" value={linkedType} onChange={e => setLinkedType(e.target.value)}><option value="">Any linked record</option>{categoryList.data?.linked_types.map(value => <option key={value} value={value}>{value.replaceAll('_id', '')}</option>)}</select><select aria-label="Sort documents" value={sort} onChange={e => setSort(e.target.value)}><option value="title">Title</option><option value="newest">Newest effective</option></select><button className="button button-small" onClick={() => { setQ(''); setKeyword(''); setCategory(''); setTag(''); setScope(''); setDocStatus(''); setEffectiveOn(''); setOwner(''); setLinkedType(''); setSort('title') }}>Clear filters</button></div><p className="view-explainer">{effectiveOn ? 'The date view shows the latest version effective that day for each document. Choose All versions to inspect earlier reviews, including revisions made on the same day.' : 'All accessible versions are shown. Use the status filter to find superseded reviews.'}</p>{docs.error && <Notice text={docs.error}/>}<div className="wiki-layout"><div className="wiki-list">{docs.loading && <Loading/>}<small className="list-count">{docs.data?.total ?? 0} accessible versions</small>{docs.data?.documents.map(doc => <button key={`${doc.document_id}-${doc.version}`} className={`wiki-item ${selected?.document_id === doc.document_id && selected?.version === doc.version ? 'selected' : ''}`} onClick={() => setSelected(doc)}><span className="doc-icon"><FileText size={19}/></span><span><strong>{doc.title}</strong><small>{doc.category.replaceAll('_', ' ')} · v{doc.version} · {doc.document_id}</small><small>{doc.tags.slice(0, 5).join(" / ")}</small></span><ArrowRight size={16}/></button>)}</div><article className="document-panel">{!selected ? <div className="document-empty"><BookOpen size={38}/><h3>Select a document</h3><p>Read the full source, version details and linked records here.</p></div> : detail.loading ? <Loading/> : detail.error ? <Notice text={detail.error}/> : detail.data && <><div className="doc-sheet-brand"><strong>ACME <span>WHOLESALE</span></strong><small>OPERATIONS KNOWLEDGE</small></div><div className="doc-top"><span className="eyebrow">ACME WHOLESALE · {selected.category.replaceAll('_', ' ').toUpperCase()}</span><div className="doc-actions"><a className="button button-small" href={`/api/documents/${selected.document_id}/${selected.version}/download`}><Download size={15}/> Markdown</a><button className="button button-small" onClick={() => window.print()}><FileText size={15}/> Print / PDF</button></div></div><h2 className="doc-sheet-title">{selected.title}</h2><div className="doc-control-grid"><div><small>Document ID</small><strong>{selected.document_id}</strong></div><div><small>Version</small><strong>{selected.version}</strong></div><div><small>Status</small><strong>{selected.status}</strong></div><div><small>Effective from</small><strong>{selected.effective_from}</strong></div><div><small>Effective until</small><strong>{selected.effective_until ?? 'Open'}</strong></div><div><small>Document owner</small><strong>{selected.owner_employee_id}</strong></div><div className="doc-control-wide"><small>Distribution</small><strong>{selected.visibility_label}</strong></div></div><div className="doc-tags">{detail.data.metadata.tags.map(value => <span key={value}>{value}</span>)}</div><div className="markdown"><ReactMarkdown>{detail.data.markdown}</ReactMarkdown></div><div className="doc-footer"><div className="doc-footer-heading">Document record</div><strong>Source</strong> {selected.document_id} · v{selected.version}<br/><strong>Owner</strong> {selected.owner_employee_id}<br/><strong>Linked records</strong> {Object.entries(selected.record_links).map(([k,v]) => `${k}: ${v}`).join(', ') || 'None'}</div></>}</article></div></section>
}

function DatabaseView({ persona, choose }: { persona: Persona | null; choose: () => void }) {
  const allowed = persona?.kind === 'employee' || persona?.kind === 'super_user'
  const names = useResource<{ name: string; type: string }[]>(allowed ? '/database/objects' : null)
  const [table, setTable] = useState('customers')
  const [q, setQ] = useState('')
  const [filterColumn, setFilterColumn] = useState('')
  const [filterValue, setFilterValue] = useState('')
  const [page, setPage] = useState(1)
  const [refresh, setRefresh] = useState(0)
  const rows = useResource<{ columns: { name: string; type: string }[]; foreign_keys: Record<string, string>; rows: RecordRow[]; total: number; page: number; size: number }>(allowed ? `/database/${table}?q=${encodeURIComponent(q)}&column=${encodeURIComponent(filterColumn)}&value=${encodeURIComponent(filterValue)}&page=${page}` : null, refresh)
  const [selected, setSelected] = useState<RecordRow | null>(null)
  const [editorMode, setEditorMode] = useState<'create' | 'edit' | null>(null)
  const [editorField, setEditorField] = useState<string | undefined>(undefined)
  const [address, setAddress] = useState<RecordRow | null>(null)
  const [label, setLabel] = useState('')
  const [country, setCountry] = useState('')
  const [contactName, setContactName] = useState('')
  const [contactResponsibility, setContactResponsibility] = useState('')
  const [sql, setSql] = useState('SELECT id, name, segment FROM customers LIMIT 10')
  const [sqlResult, setSqlResult] = useState<{ columns: string[]; rows: RecordRow[]; truncated: boolean } | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [tab, setTab] = useState<'browse' | 'relations' | 'sql' | 'edits' | 'audit' | 'reset'>('browse')
  const audit = useResource<RecordRow[]>(allowed && tab === 'edits' ? '/edits' : null, refresh)
  useEffect(() => { if (persona?.kind !== 'super_user' && (tab === 'sql' || tab === 'audit' || tab === 'reset')) setTab('browse') }, [persona?.kind, tab])
  if (!allowed) return <Gate title="Explore the company database" description="Select an employee or superuser to browse all company tables and views. Superuser can edit customer addresses." choose={choose}/>
  async function inspect(item: RecordRow) { setSelected(item); setAddress(null); if (table === 'customer_contacts') { setContactName(String(item.name)); setContactResponsibility(String(item.responsibility)) } if (table === 'customers' && item.address_id) { try { const value = await api<RecordRow>(`/database/addresses/${encodeURIComponent(String(item.address_id))}`); setAddress(value); setLabel(String(value.label)); setCountry(String(value.country)) } catch (err) { setError((err as Error).message) } } }
  async function saveAddress() { if (!selected) return; setError(''); setMessage(''); try { const edit = await post<{ id: string; after: RecordRow }>(`/database/customers/${selected.id}/address`, { label, country }); setMessage(`Saved ${edit.id}. The customer and agent now read the new address.`); setRefresh(refresh + 1); setSelected({ ...selected, address_id: edit.after.address_id }); setAddress(edit.after) } catch (err) { setError((err as Error).message) } }
  async function saveContact() { if (!selected) return; setError(''); setMessage(''); try { const edit = await post<{ id: string; after: RecordRow }>(`/database/contacts/${selected.id}`, { name: contactName, responsibility: contactResponsibility }); setMessage(`Saved ${edit.id}. Contact details updated.`); setSelected({ ...selected, ...edit.after }); setRefresh(refresh + 1) } catch (err) { setError((err as Error).message) } }
  async function runSql() { setError(''); try { setSqlResult(await post('/database/query', { sql })) } catch (err) { setError((err as Error).message) } }
  async function follow(key: string, value: unknown) {
    const target = rows.data?.foreign_keys[key]
    if (!target || !names.data?.some(o => o.name === target)) return
    setError(''); setTable(target); setQ(''); setFilterColumn(''); setFilterValue(''); setPage(1); setSelected(null); setAddress(null)
    try { setSelected(await api<RecordRow>(`/database/${target}/${encodeURIComponent(String(value))}`)) }
    catch (err) { setError((err as Error).message) }
  }
  async function openRelatedRecord(target: string, identifier: string) {
    if (!names.data?.some(object => object.name === target)) return
    setError(''); setTable(target); setQ(''); setFilterColumn(''); setFilterValue(''); setPage(1); setSelected(null); setAddress(null)
    try { setSelected(await api<RecordRow>(`/database/${target}/${encodeURIComponent(identifier)}`)) }
    catch (err) { setError((err as Error).message) }
  }
  const editableTable = persona?.kind === 'super_user' &&
    names.data?.find(object => object.name === table)?.type === 'table' &&
    !['documents', 'document_versions', 'document_links'].includes(table)
  function openEditor(item: RecordRow, field?: string) {
    if (!editableTable) return
    setSelected(item)
    setEditorField(field)
    setEditorMode('edit')
  }
  function browseRelation(target: string) {
    setTable(target)
    setTab('browse')
    setQ('')
    setFilterColumn('')
    setFilterValue('')
    setPage(1)
    setSelected(null)
  }
  function onSaved(record: RecordRow, created: boolean) {
    setEditorMode(null)
    setSelected(record)
    setRefresh(value => value + 1)
    setMessage(`${created ? 'Added' : 'Saved'} ${fmt(record.id)}.`)
    setError('')
    if (created) {
      setQ(String(record.id))
      setPage(1)
      setFilterColumn('')
      setFilterValue('')
    }
  }
  function browseDependency(target: string, column: string, identifier: string) {
    setEditorMode(null)
    setSelected(null)
    setTable(target)
    setTab('browse')
    setQ('')
    setFilterColumn(column)
    setFilterValue(identifier)
    setPage(1)
  }
  return <section className="content-section database-page"><SectionTitle eyebrow="DATA EXPLORER" title="Explore company records." description={persona?.kind === 'super_user' ? "Inspect all tables and views, run bounded read-only SQL and review local edits." : "Inspect tables and views within your demo scope, and review local edits."}/><div className="db-tabs"><button className={tab === 'browse' ? 'active' : ''} onClick={() => setTab('browse')}><Database size={16}/> Browse</button><button className={tab === 'relations' ? 'active' : ''} onClick={() => setTab('relations')}><GitBranch size={16}/> Table connections</button>{persona?.kind === 'super_user' && <button className={tab === 'sql' ? 'active' : ''} onClick={() => setTab('sql')}><Terminal size={16}/> SQL query</button>}<button className={tab === 'edits' ? 'active' : ''} onClick={() => setTab('edits')}><FileText size={16}/> Edit history</button>{persona?.kind === 'super_user' && <button className={tab === 'audit' ? 'active' : ''} onClick={() => setTab('audit')}>Check links</button>}{persona?.kind === 'super_user' && <button className={tab === 'reset' ? 'active' : ''} onClick={() => setTab('reset')}>Reset data</button>}</div>{error && <Notice text={error}/ >}{message && <div className="success-notice">{message}</div>}{tab === 'relations' && <RelationshipMap currentTable={table} browse={browseRelation}/>}{tab === 'browse' && <div className="db-layout"><aside className="db-sidebar"><h3>Tables</h3>{names.data?.filter(o => o.type === 'table').map(o => <button key={o.name} className={table === o.name ? 'active' : ''} onClick={() => { setTable(o.name); setQ(''); setFilterColumn(''); setFilterValue(''); setPage(1); setSelected(null) }}>{o.name}</button>)}<h3>Views</h3>{names.data?.filter(o => o.type === 'view').map(o => <button key={o.name} className={table === o.name ? 'active' : ''} onClick={() => { setTable(o.name); setQ(''); setFilterColumn(''); setFilterValue(''); setPage(1); setSelected(null) }}>{o.name}</button>)}</aside><div className="db-main"><div className="db-toolbar"><div><span className="eyebrow">{names.data?.find(o => o.name === table)?.type ?? 'TABLE'}</span><h3>{table}</h3><small>{rows.data?.total.toLocaleString()} records</small></div>{editableTable && <button className="button button-dark db-new-row" onClick={() => { setSelected(null); setEditorField(undefined); setEditorMode('create') }}><Plus size={16}/> Add row</button>}<label className="search-box"><Search size={16}/><input value={q} onChange={e => { setQ(e.target.value); setPage(1) }} placeholder="Search text columns" /></label><select aria-label="Filter column" value={filterColumn} onChange={e => { setFilterColumn(e.target.value); setPage(1) }}><option value="">Filter column</option>{rows.data?.columns.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}</select><input className="filter-value" aria-label="Exact filter value" value={filterValue} onChange={e => { setFilterValue(e.target.value); setPage(1) }} placeholder="Exact value" /></div>{rows.loading && <Loading/>}{rows.error && <Notice text={rows.error}/>}{editableTable && <small className="db-table-hint">Click to inspect · double-click to edit a row.</small>}<div className="table-scroll"><table><thead><tr>{rows.data?.columns.map(c => <th key={c.name}>{c.name}</th>)}</tr></thead><tbody>{rows.data?.rows.map((item, i) => <tr key={i} tabIndex={0} onClick={() => void inspect(item)} onDoubleClick={() => openEditor(item)} onKeyDown={event => { if (event.key === 'Enter') { void inspect(item); openEditor(item) } }}>{rows.data?.columns.map(c => <td key={c.name} title={editableTable ? 'Double-click to edit this field' : undefined} onDoubleClick={event => { event.stopPropagation(); openEditor(item, c.name) }}>{fmt(item[c.name])}</td>)}</tr>)}</tbody></table></div><div className="pagination"><span>Page {page} · {rows.data?.total ?? 0} rows</span><button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button><button disabled={!rows.data || page * 25 >= rows.data.total} onClick={() => setPage(page + 1)}>Next</button></div>{selected && <div className="record-panel"><div className="card-heading"><h3>{fmt(selected.id ?? 'Record detail')}</h3><div className="db-record-actions">{editableTable && <button className="button button-small" onClick={() => openEditor(selected)}>Edit row</button>}<button className="icon-button" onClick={() => setSelected(null)}><X size={18}/></button></div></div><div className="record-fields">{Object.entries(selected).map(([key, value]) => <div key={key}><small>{key}</small><strong>{fmt(value)}</strong>{Boolean(value) && names.data?.some(o => o.name === rows.data?.foreign_keys[key]) && <button className="link-button" onClick={() => follow(key, value)}><ExternalLink size={13}/> Open related</button>}</div>)}</div>{table === 'orders' && persona?.kind === 'super_user' && <OrderJourney orderId={String(selected.id)} openRecord={(target, identifier) => void openRelatedRecord(target, identifier)} revision={refresh}/ >}{table === 'purchase_orders' && <PurchaseJourney orderId={String(selected.id)} openRecord={(target, identifier) => void openRelatedRecord(target, identifier)} revision={refresh}/ >}{table === 'customers' && address && <div className="address-form"><h4>Customer address</h4><p>Current: {fmt(address.label)}, {fmt(address.country)}</p>{persona?.kind === 'super_user' ? <><label>Address line<input value={label} onChange={e => setLabel(e.target.value)}/></label><label>Country<input value={country} onChange={e => setCountry(e.target.value)}/></label><button className="button button-dark" onClick={saveAddress}>Save audited edit</button></> : <small>Select superuser to edit this address.</small>}</div>}{table === 'customer_contacts' && persona?.kind === 'super_user' && <div className="address-form"><h4>Edit contact</h4><label>Name<input value={contactName} onChange={e => setContactName(e.target.value)}/></label><label>Responsibility<input value={contactResponsibility} onChange={e => setContactResponsibility(e.target.value)}/></label><button className="button button-dark" onClick={saveContact}>Save audited edit</button></div>}</div>}</div></div>}{tab === 'sql' && <div className="card sql-card"><h3>Read-only SQL</h3><p>Run SELECT, WITH or EXPLAIN against the local company database. Results are capped at 200 rows.</p><textarea className="code-editor" value={sql} onChange={e => setSql(e.target.value)} rows={6} spellCheck={false}/><button className="button button-dark" onClick={runSql}><Play size={16}/> Run query</button>{sqlResult && <><small>{sqlResult.rows.length} rows {sqlResult.truncated ? '· truncated' : ''}</small><div className="table-scroll"><table><thead><tr>{sqlResult.columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{sqlResult.rows.map((row, i) => <tr key={i}>{sqlResult.columns.map(c => <td key={c}>{fmt(row[c])}</td>)}</tr>)}</tbody></table></div></>}</div>}{tab === 'edits' && <div className="card"><h3>Audited changes</h3>{audit.data?.length ? audit.data.map(item => <div className="audit-row" key={String(item.id)}><strong>{fmt(item.record_id)}</strong><small>{fmt(item.created_at)} · {fmt(item.actor)}</small><pre>{fmt(item.before_json)} → {fmt(item.after_json)}</pre></div>) : <p>No portal edits yet.</p>}</div>}{tab === 'audit' && <DataAudit/>}{tab === 'reset' && <ResetPanel restored={() => { setRefresh(value => value + 1); setSelected(null) }}/>}{editorMode && <RowEditor key={`${table}:${editorMode}:${selected?.id ?? ''}`} table={table} record={editorMode === 'edit' ? selected : null} focusField={editorField} close={() => setEditorMode(null)} saved={onSaved} removed={id => { setEditorMode(null); setSelected(null); setRefresh(value => value + 1); setMessage(`Deleted ${id}.`) }} browseRelated={browseDependency}/>}</section>
}

export default function App() {
  const [view, setView] = useState<View>('home')
  const [persona, setPersona] = useState<Persona | null>(null)
  const [personaRevision, setPersonaRevision] = useState(0)
  const [personaOpen, setPersonaOpen] = useState(0)
  const [mobileOpen, setMobileOpen] = useState(false)
  useEffect(() => { api<{ persona: Persona | null }>('/bootstrap').then(value => setPersona(value.persona)).catch(() => {}) }, [])
  function navigate(next: View) { setView(next); setMobileOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  return <div className="app"><div className="demo-ribbon">LOCAL DEMO <span/> 2010–11 HISTORICAL DATA <span/> CONTEMPORARY FICTIONAL SCENARIOS</div><header className="site-header"><button className="brand" onClick={() => navigate('home')}><span className="brand-mark"><Boxes size={25}/></span><span>acme<strong>wholesale</strong><small>COMPANY PORTAL</small></span></button><nav className={mobileOpen ? 'open' : ''}>{links.map(item => <button key={item.id} className={view === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><item.icon size={17}/>{item.label}</button>)}</nav><div className="header-actions"><PersonaSwitch openSignal={personaOpen} persona={persona} changed={value => { setPersona(value); setPersonaRevision(current => current + 1) }} view={view}/><button className="menu-button" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Toggle navigation"><Menu size={21}/></button></div></header><main key={personaRevision}>{view === 'home' && <Home navigate={navigate}/ >}{view === 'customer' && <Customer persona={persona} choose={() => setPersonaOpen(personaOpen + 1)}/ >}{view === 'employee' && <Employee persona={persona} choose={() => setPersonaOpen(personaOpen + 1)} navigate={navigate}/ >}{view === 'insights' && <BusinessInsights persona={persona} choose={() => setPersonaOpen(personaOpen + 1)}/ >}{view === 'wiki' && <Wiki persona={persona} choose={() => setPersonaOpen(personaOpen + 1)}/ >}{view === 'tools' && <Workbench persona={persona} choose={() => setPersonaOpen(personaOpen + 1)}/ >}{view === 'database' && <DatabaseView persona={persona} choose={() => setPersonaOpen(personaOpen + 1)}/ >}{view === 'execution' && <Execution persona={persona} choose={() => setPersonaOpen(personaOpen + 1)}/ >}</main><footer className="site-footer"><div className="brand brand-footer"><span className="brand-mark"><Boxes size={22}/></span><span>acme<strong>wholesale</strong></span></div><p>One place for products, people and practical knowledge.</p><small>Fictional company · Local learning application · Historical data and contemporary scenarios</small></footer></div>
}
