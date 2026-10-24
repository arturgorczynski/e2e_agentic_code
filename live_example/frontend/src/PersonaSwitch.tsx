import { useEffect, useState } from 'react'
import { ArrowRight, ChevronDown, Plus, Search, ShieldCheck, UserRound, X } from 'lucide-react'
import { api, post, type Persona } from './api'

type Kind = Persona['kind']
type Candidate = {
  id: string; name: string; segment?: string; job_title?: string
  order_count?: number; total_pence?: number; cancelled_count?: number
  department?: string; location?: string; hired_on?: string; managed_customers?: number
  responsibility?: string
  history_period?: string
}
type Options = { departments: { id: string; name: string }[]; locations: { id: string; name: string }[]; job_titles: string[] }
type Scenario = {
  name: string; order_count: number; items_per_order: number
  total_gbp: string; cancelled_count: number; fulfilled_count: number
  payment_profile: 'settled' | 'partial' | 'unpaid'
}

export function PersonaSwitch({ persona, changed, openSignal, view }: {
  persona: Persona | null; changed: (value: Persona) => void
  openSignal: number; view: string
}) {
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState<Kind>(persona?.kind ?? 'customer')
  const [query, setQuery] = useState('')
  const [minOrders, setMinOrders] = useState('')
  const [maxOrders, setMaxOrders] = useState('')
  const [status, setStatus] = useState('')
  const [period, setPeriod] = useState('all')
  const [sort, setSort] = useState('orders_desc')
  const [department, setDepartment] = useState('')
  const [location, setLocation] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [minCustomers, setMinCustomers] = useState('')
  const [activeOnly, setActiveOnly] = useState(false)
  const [options, setOptions] = useState<Options>({ departments: [], locations: [], job_titles: [] })
  const [creating, setCreating] = useState(false)
  const [description, setDescription] = useState('')
  const [scenario, setScenario] = useState<Scenario>({ name: '', order_count: 3, items_per_order: 2, total_gbp: '120', cancelled_count: 0, fulfilled_count: 2, payment_profile: 'settled' })
  const [items, setItems] = useState<Candidate[]>([])
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const allowed: Kind[] = view === 'customer' ? ['customer'] :
    ['employee', 'tools', 'database'].includes(view) ? ['employee', 'super_user'] :
    ['customer', 'employee', 'super_user']

  useEffect(() => { if (openSignal) setOpen(true) }, [openSignal])
  useEffect(() => { if (!allowed.includes(kind)) { setItems([]); setKind(allowed[0]); setSort(allowed[0] === 'customer' ? 'orders_desc' : 'customers_desc'); setDepartment('') } }, [view, kind])
  useEffect(() => { if (open) api<Options>('/personas/options').then(setOptions).catch(() => {}) }, [open])
  useEffect(() => {
    if (!open || creating) return
    let active = true
    setItems([]); setSearching(true)
    const params = new URLSearchParams({ kind, q: query, sort })
    if (kind === 'customer') {
      params.set('status', status)
      params.set('period', period)
      if (minOrders) params.set('min_orders', minOrders)
      if (maxOrders) params.set('max_orders', maxOrders)
    }
    if (kind === 'employee') {
      params.set('department', department); params.set('location', location)
      params.set('job_title', jobTitle)
      if (minCustomers) params.set('min_customers', minCustomers)
    }
    if (kind === 'super_user') params.set('active_only', String(activeOnly))
    const timer = window.setTimeout(() => {
      api<Candidate[]>(`/personas/search?${params}`).then(rows => {
        if (active) { setItems(rows); setError(''); setSearching(false) }
      }).catch(err => { if (active) { setError(err.message); setSearching(false) } })
    }, 220)
    return () => { active = false; window.clearTimeout(timer) }
  }, [open, creating, kind, query, minOrders, maxOrders, status, period, sort, department, location, jobTitle, minCustomers, activeOnly])

  async function choose(id: string) {
    setBusy(true); setError('')
    try {
      changed(await post<Persona>('/personas/select', { kind, subject_id: id }))
      setOpen(false)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function createScenario() {
    setBusy(true); setError('')
    try {
      const created = await post<{ id: string }>('/personas/scenarios', {
        name: scenario.name,
        order_count: scenario.order_count,
        items_per_order: scenario.items_per_order,
        total_pence: Math.round(Number(scenario.total_gbp) * 100),
        cancelled_count: scenario.cancelled_count,
        fulfilled_count: scenario.fulfilled_count,
        payment_profile: scenario.payment_profile,
      })
      changed(await post<Persona>('/personas/select', { kind: 'customer', subject_id: created.id }))
      setKind('customer'); setCreating(false); setOpen(false)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  function changeNumber(key: 'order_count' | 'items_per_order' | 'cancelled_count' | 'fulfilled_count', value: string) {
    setScenario(previous => ({ ...previous, [key]: Number(value) }))
  }

  function applyDescription() {
    const read = (pattern: RegExp) => description.match(pattern)?.[1]
    const orders = read(/(\d+)\s+orders?/i)
    const items = read(/(\d+)\s+items?(?:\s+per\s+order)?/i)
    const total = read(/(?:£|GBP\s*)(\d+(?:\.\d{1,2})?)/i)
    const cancelled = read(/(\d+)\s+(?:cancelled|rejected)/i)
    const fulfilled = read(/(\d+)\s+fulfilled/i)
    if (![orders, items, total, cancelled, fulfilled].some(Boolean)) {
      setError('Try: 5 orders, 2 items per order, £250 total, 1 cancelled, 3 fulfilled')
      return
    }
    setScenario(previous => ({ ...previous,
      order_count: orders ? Number(orders) : previous.order_count,
      items_per_order: items ? Number(items) : previous.items_per_order,
      total_gbp: total ?? previous.total_gbp,
      cancelled_count: cancelled ? Number(cancelled) : previous.cancelled_count,
      fulfilled_count: fulfilled ? Number(fulfilled) : previous.fulfilled_count,
    }))
    setError('')
  }

  return <div className="persona-wrap">
    <button className="persona-trigger" onClick={() => setOpen(!open)}><span className="persona-avatar">{persona?.kind === 'super_user' ? <ShieldCheck size={18}/> : <UserRound size={18}/>}</span><span className="persona-label"><strong>{persona?.display_name ?? 'Choose demo persona'}</strong><small>{persona ? persona.job_title ?? persona.kind.replace('_', ' ') : 'Customer · Employee · Superuser'}</small></span><ChevronDown size={16}/></button>
    {open && <div className="persona-popover">
      <div className="popover-head"><strong>Demo persona</strong><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close"><X size={17}/></button></div>
      <p>Switch identities and test different company histories.</p>
      <div className="segmented">{allowed.map(option => <button key={option} className={kind === option ? 'active' : ''} onClick={() => { setItems([]); setKind(option); setCreating(false); setQuery(''); setDepartment(''); setLocation(''); setJobTitle(''); setSort(option === 'customer' ? 'orders_desc' : option === 'employee' ? 'customers_desc' : 'name') }}>{option === 'super_user' ? 'Superuser' : option}</button>)}</div>
      <label className="search-box"><Search size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder={kind === 'super_user' ? 'Search company or department focus' : `Search ${kind} name, role or ID`}/></label>
      {kind === 'customer' && <div className="persona-filters">
        <label>History<select value={period} onChange={event => setPeriod(event.target.value)}><option value="all">All periods</option><option value="historical">2010–11 archive</option><option value="contemporary">Contemporary fictional</option></select></label>
        <label>Orders from<input type="number" min="0" value={minOrders} onChange={event => setMinOrders(event.target.value)}/></label>
        <label>to<input type="number" min="0" value={maxOrders} onChange={event => setMaxOrders(event.target.value)}/></label>
        <label>Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="">Any</option>{['confirmed', 'partial', 'fulfilled', 'cancelled'].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        <label>Sort<select value={sort} onChange={event => setSort(event.target.value)}><option value="orders_desc">Most orders</option><option value="orders_asc">Fewest orders</option><option value="value_desc">Highest value</option><option value="name">Name</option></select></label>
      </div>}
      {kind === 'employee' && <div className="persona-filters">
        <label>Department<select value={department} onChange={event => setDepartment(event.target.value)}><option value="">All departments</option>{options.departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Location<select value={location} onChange={event => setLocation(event.target.value)}><option value="">All locations</option>{options.locations.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Role<select value={jobTitle} onChange={event => setJobTitle(event.target.value)}><option value="">All roles</option>{options.job_titles.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
        <label>Managed customers from<input type="number" min="0" value={minCustomers} onChange={event => setMinCustomers(event.target.value)}/></label>
        <label>Sort<select value={sort} onChange={event => setSort(event.target.value)}><option value="customers_desc">Most managed customers</option><option value="customers_asc">Fewest managed customers</option><option value="name">Name</option><option value="hired">Hire date</option></select></label>
      </div>}
      {kind === 'super_user' && <div className="persona-filters"><p>Choose a department focus for the Workspace order feed. Superuser permissions stay company-wide.</p>
        <label>Department<select value={department} onChange={event => setDepartment(event.target.value)}><option value="">Any focus</option>{options.departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Sort<select value={sort} onChange={event => setSort(event.target.value)}><option value="name">Name</option><option value="customers_desc">Most managed customers</option><option value="orders_desc">Most customer orders</option></select></label>
        <label className="persona-check"><input type="checkbox" checked={activeOnly} onChange={event => setActiveOnly(event.target.checked)}/> With managed customers</label>
      </div>}
      {kind === 'customer' && <button className="button button-small persona-create-toggle" onClick={() => setCreating(!creating)}><Plus size={15}/>{creating ? 'Browse customers' : 'Create scenario customer'}</button>}
      {creating && kind === 'customer' ? <div className="persona-create">
        <label>Describe quantities (optional)<textarea value={description} onChange={event => setDescription(event.target.value)} placeholder="5 orders, 2 items per order, £250 total, 1 cancelled, 3 fulfilled" rows={2}/></label><button className="button button-small" onClick={applyDescription}>Apply description to fields</button>
        <label>Name<input value={scenario.name} onChange={event => setScenario({ ...scenario, name: event.target.value })} placeholder="e.g. North Quay Supplies"/></label>
        <label>Orders<input type="number" min="0" max="30" value={scenario.order_count} onChange={event => changeNumber('order_count', event.target.value)}/></label>
        <label>Items per order<input type="number" min="1" max="10" value={scenario.items_per_order} onChange={event => changeNumber('items_per_order', event.target.value)}/></label>
        <label>Total value (£)<input type="number" min="0" step="0.01" value={scenario.total_gbp} onChange={event => setScenario({ ...scenario, total_gbp: event.target.value })}/></label>
        <label>Rejected / cancelled orders<input type="number" min="0" max={scenario.order_count} value={scenario.cancelled_count} onChange={event => changeNumber('cancelled_count', event.target.value)}/></label>
        <label>Fulfilled orders<input type="number" min="0" max={scenario.order_count - scenario.cancelled_count} value={scenario.fulfilled_count} onChange={event => changeNumber('fulfilled_count', event.target.value)}/></label>
        <label>Payment history<select value={scenario.payment_profile} onChange={event => setScenario({ ...scenario, payment_profile: event.target.value as Scenario['payment_profile'] })}><option value="settled">Fully paid</option><option value="partial">Partly paid</option><option value="unpaid">Unpaid</option></select></label>
        <p>This creates a separate fictional contemporary history, dated relative to today. Fulfilled orders include invoices, shipments and stock movements. Choose whether their invoices are fully paid, partly paid or unpaid. Remaining orders stay confirmed.</p>
        <button className="button button-dark" disabled={busy} onClick={createScenario}>Create and switch</button>
      </div> : <div className="persona-list">{items.filter(item => kind !== 'super_user' || !department || item.id === department).map(item => <button disabled={busy || searching} key={item.id} onClick={() => choose(item.id)}><span><strong>{item.name}</strong><small>{item.id} · {item.segment ?? item.job_title ?? item.responsibility ?? ''}</small>{kind === 'customer' && <small>{item.history_period} · {item.order_count} orders · £{((item.total_pence ?? 0) / 100).toFixed(2)} · {item.cancelled_count} cancelled</small>}{kind === 'employee' && <small>{item.department ?? 'Unassigned'} · {item.location ?? 'No location'} · {item.managed_customers} managed customers · hired {item.hired_on}</small>}{kind === 'super_user' && <small>{item.managed_customers} managed customers · {item.order_count} customer orders</small>}</span><ArrowRight size={16}/></button>)}{!items.length && <small>{searching ? 'Finding personas…' : 'No matching personas.'}</small>}</div>}
      {error && <div className="notice" role="alert">{error}</div>}
    </div>}
  </div>
}
