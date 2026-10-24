import { useEffect, useState } from 'react'
import { ExternalLink, Search } from 'lucide-react'
import { api } from './api'

type Edge = { source: string; target: string; column: string; target_column: string }
type Graph = { tables: { name: string; type: string }[]; edges: Edge[] }

export function RelationshipMap({ currentTable, browse }: { currentTable: string; browse: (table: string) => void }) {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [focus, setFocus] = useState(currentTable)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { setFocus(currentTable) }, [currentTable])
  useEffect(() => {
    let active = true
    api<Graph>('/database/relationships').then(value => { if (active) setGraph(value) })
      .catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [])
  const incoming = graph?.edges.filter(edge => edge.target === focus) ?? []
  const outgoing = graph?.edges.filter(edge => edge.source === focus) ?? []
  const left = [...new Set(incoming.map(edge => edge.source))]
  const right = [...new Set(outgoing.map(edge => edge.target))]
  const count = Math.max(left.length, right.length, 1)
  const height = Math.max(380, count * 85 + 100)
  const y = (index: number, length: number) => height / 2 + (index - (length - 1) / 2) * 85
  const matches = graph?.tables.filter(item => item.name.toLowerCase().includes(search.toLowerCase())) ?? []
  const node = (name: string, x: number, cy: number, selected = false) => <g key={`${name}:${x}`} className={`graph-node ${selected ? 'selected' : ''}`} role="button" tabIndex={0} onClick={() => setFocus(name)} onKeyDown={event => { if (event.key === 'Enter') setFocus(name) }} aria-label={`Focus ${name}`}>
    <rect x={x - 115} y={cy - 29} width="230" height="58" rx="11"/>
    <text x={x} y={cy + 5} textAnchor="middle">{name}</text>
  </g>
  return <div className="db-relations card"><div className="db-relations-head"><div><span className="eyebrow">SCHEMA MAP</span><h3>How the tables connect</h3><p>Each arrow follows a foreign key from its source table to the referenced table. Select a node to explore its neighbours.</p></div>{graph && <small>{graph.tables.length} objects · {graph.edges.length} relationships</small>}</div>
    {error && <div className="notice">{error}</div>}{!graph && !error && <p>Loading relationships…</p>}
    {graph && <><div className="db-relations-picker"><label className="search-box"><Search size={16}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a table or view"/></label><select aria-label="Focus table" value={focus} onChange={event => setFocus(event.target.value)}>{matches.some(item => item.name === focus) || !search ? null : <option value={focus}>{focus}</option>}{matches.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select><button className="button button-small" onClick={() => browse(focus)}>Browse {focus} <ExternalLink size={14}/></button></div>
      <div className="graph-scroll"><svg className="relationship-graph" viewBox={`0 0 1000 ${height}`} role="img" aria-label={`Relationship graph around ${focus}`}>
        <defs><marker id="graph-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z"/></marker></defs>
        <text className="graph-heading" x="150" y="34" textAnchor="middle">REFERENCED BY ({left.length})</text><text className="graph-heading" x="850" y="34" textAnchor="middle">REFERENCES ({right.length})</text>
        {incoming.map((edge, index) => { const cy = y(left.indexOf(edge.source), left.length); return <g key={`in:${index}`}><path className="graph-edge" d={`M265 ${cy} C360 ${cy}, 385 ${height / 2}, 475 ${height / 2}`} markerEnd="url(#graph-arrow)"/><title>{edge.source}.{edge.column} → {focus}.{edge.target_column}</title></g> })}
        {outgoing.map((edge, index) => { const cy = y(right.indexOf(edge.target), right.length); return <g key={`out:${index}`}><path className="graph-edge" d={`M615 ${height / 2} C700 ${height / 2}, 730 ${cy}, 735 ${cy}`} markerEnd="url(#graph-arrow)"/><title>{focus}.{edge.column} → {edge.target}.{edge.target_column}</title></g> })}
        {left.map((name, index) => node(name, 150, y(index, left.length)))}
        {node(focus, 500, height / 2, true)}
        {right.map((name, index) => node(name, 850, y(index, right.length)))}
      </svg></div>
      <div className="graph-legend"><span>{focus} is referenced by {incoming.length} foreign keys and references {outgoing.length} others.</span>{[...incoming, ...outgoing].map((edge, index) => <button key={index} onClick={() => setFocus(edge.source === focus ? edge.target : edge.source)}>{edge.source}.{edge.column} → {edge.target}.{edge.target_column}</button>)}</div>
    </>}
  </div>
}
