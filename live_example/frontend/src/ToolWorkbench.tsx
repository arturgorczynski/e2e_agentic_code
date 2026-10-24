import { useEffect, useState } from 'react'
import { ArrowRight, Check, Play, Wrench } from 'lucide-react'
import { api, post, type Persona, type RecordRow, type ToolInfo } from './api'

type Property = { type?: string; title?: string; description?: string; enum?: unknown[]; default?: unknown; anyOf?: Property[] }

function valueType(property: Property): string {
  return property.type ?? property.anyOf?.find(item => item.type !== 'null')?.type ?? 'string'
}

export function Workbench({ persona, choose }: { persona: Persona | null; choose: () => void }) {
  const allowed = persona?.kind === 'employee' || persona?.kind === 'super_user'
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [selected, setSelected] = useState<ToolInfo | null>(null)
  const [mode, setMode] = useState<'form' | 'json'>('form')
  const [values, setValues] = useState<RecordRow>({})
  const [complexText, setComplexText] = useState<Record<string, string>>({})
  const [raw, setRaw] = useState('{}')
  const [result, setResult] = useState<unknown>(null)
  const [sent, setSent] = useState<unknown>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!allowed) return
    let active = true
    api<{ tools: ToolInfo[] }>('/tools').then(data => { if (active) setTools(data.tools) })
      .catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [allowed, persona?.subject_id])

  if (!allowed) return <section className="content-section"><div className="empty-state"><Wrench size={36}/><h2>Work directly with Acme tools</h2><p>Choose an employee or superuser persona to run the tool catalog.</p><button className="button button-dark" onClick={choose}>Choose persona</button></div></section>

  function selectTool(tool: ToolInfo) {
    setSelected(tool); setValues(tool.example); setRaw(JSON.stringify(tool.example, null, 2))
    setComplexText(Object.fromEntries(Object.entries(tool.example).filter(([, value]) => typeof value === 'object' && value !== null).map(([name, value]) => [name, JSON.stringify(value, null, 2)])))
    setResult(null); setSent(null); setError(''); setMode('form')
  }

  function update(name: string, value: unknown) {
    setValues(previous => {
      const next = { ...previous, [name]: value }
      setRaw(JSON.stringify(next, null, 2))
      return next
    })
  }

  function formArguments(): RecordRow {
    const args = { ...values }
    for (const [name, property] of Object.entries((selected?.schema.properties ?? {}) as Record<string, Property>)) {
      if (['array', 'object'].includes(valueType(property))) {
        const text = complexText[name]
        if (text !== undefined) {
          if (!text.trim()) delete args[name]
          else {
            try { args[name] = JSON.parse(text) }
            catch { throw new Error(`${name} must contain valid JSON`) }
          }
        }
      }
    }
    return args
  }

  async function run() {
    if (!selected) return
    setBusy(true); setError(''); setResult(null)
    try {
      const args = mode === 'json' ? JSON.parse(raw) as RecordRow : formArguments()
      setSent(args)
      setResult(await post(`/tools/${selected.name}/run`, { arguments: args }))
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  const properties = (selected?.schema.properties ?? {}) as Record<string, Property>
  const required = new Set((selected?.schema.required ?? []) as string[])
  return <section className="content-section">
    <div className="section-title"><span className="eyebrow">TOOL WORKBENCH</span><h2>The tools behind the answers.</h2><p>Read each tool’s purpose, fill in its API arguments and inspect the exact request and result.</p></div>
    {error && <div className="notice" role="alert">{error}</div>}
    <div className="workbench-grid"><div className="tool-list">{tools.map(tool => <button key={tool.name} className={selected?.name === tool.name ? 'selected' : ''} onClick={() => selectTool(tool)}><span className="tool-icon"><Wrench size={17}/></span><span><strong>{tool.title}</strong><small>{tool.name}</small></span><ArrowRight size={16}/></button>)}</div>
      <div className="tool-detail card">{selected ? <>
        <span className="eyebrow">DIRECT TOOL CALL</span><h2>{selected.title}</h2><p>{selected.description}</p><div className="tool-explanation"><strong>Purpose and behavior</strong><p>{selected.detail}</p></div>
        <div className="tool-mode"><strong>Arguments</strong><div className="segmented"><button className={mode === 'form' ? 'active' : ''} onClick={() => { if (mode === 'json') { try { const parsed = JSON.parse(raw) as RecordRow; setValues(parsed); setComplexText(Object.fromEntries(Object.entries(parsed).filter(([, value]) => typeof value === 'object' && value !== null).map(([name, value]) => [name, JSON.stringify(value, null, 2)]))); setError('') } catch { setError('Fix the JSON before switching to the form'); return } } setMode('form') }}>Form</button><button className={mode === 'json' ? 'active' : ''} onClick={() => { try { setRaw(JSON.stringify(formArguments(), null, 2)); setMode('json'); setError('') } catch (err) { setError((err as Error).message) } }}>JSON</button></div></div>
        {mode === 'json' ? <textarea className="code-editor" value={raw} onChange={event => setRaw(event.target.value)} rows={12} spellCheck={false}/> : <div className="tool-form">{Object.entries(properties).map(([name, property]) => {
          const type = valueType(property)
          const current = values[name]
          return <label key={name}><span><strong>{property.title ?? name.replaceAll('_', ' ')}</strong>{required.has(name) && <b> *</b>}<small>{property.description ?? `${name} · ${type}`}</small></span>
            {property.enum ? <select value={String(current ?? '')} onChange={event => update(name, event.target.value)}><option value="">Choose…</option>{property.enum.map(option => <option key={String(option)} value={String(option)}>{String(option)}</option>)}</select> : type === 'boolean' ? <input type="checkbox" checked={Boolean(current)} onChange={event => update(name, event.target.checked)}/> : type === 'object' || type === 'array' ? <textarea value={complexText[name] ?? JSON.stringify(current ?? (type === 'array' ? [] : {}), null, 2)} onChange={event => setComplexText(previous => ({ ...previous, [name]: event.target.value }))} rows={5} spellCheck={false}/> : <input type={type === 'integer' || type === 'number' ? 'number' : 'text'} value={String(current ?? '')} onChange={event => update(name, type === 'integer' || type === 'number' ? Number(event.target.value) : event.target.value)}/>}</label>
        })}</div>}
        <button className="button button-dark" onClick={run} disabled={busy}><Play size={16}/>{busy ? 'Running…' : 'Run tool'}</button>
        <details className="tool-schema"><summary>Full API schema</summary><pre>{JSON.stringify(selected.schema, null, 2)}</pre></details>
        <div className="tool-raw"><h3>Raw request</h3><pre>{JSON.stringify(sent ?? (mode === 'json' ? raw : values), null, 2)}</pre><h3>Raw result</h3>{result !== null ? <><Check size={17}/><pre>{JSON.stringify(result, null, 2)}</pre></> : <p>Run the tool to see its actual response.</p>}</div>
      </> : <div className="empty-state"><Wrench size={36}/><h3>Select a tool</h3><p>Choose from the catalog to inspect its schema and try a real call.</p></div>}</div>
    </div>
  </section>
}
