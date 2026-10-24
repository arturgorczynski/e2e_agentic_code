export type Persona = { kind: 'customer' | 'employee' | 'super_user'; subject_id: string; display_name: string; permissions: string[]; access_profile: string; job_title?: string; department?: string }
export type RecordRow = Record<string, unknown>
export type DocumentMeta = { document_id: string; version: number; title: string; category: string; access_scope: string; effective_from: string; effective_until: string | null; status: string; visibility_label: string; owner_employee_id: string; record_links: Record<string, string>; tags: string[] }
export type ToolInfo = { name: string; title: string; description: string; detail: string; schema: RecordRow; example: RecordRow }
export type Thread = { id: string; title: string; updated_at: string; status: string; mode: string }
export type Snapshot = { chat: { role: string; content: string }[]; status: string; error: string | null; runs: RecordRow[]; events: RecordRow[]; operations: { id: string; kind: string; payload_json: string }[]; sources: RecordRow[] }

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const payload = await response.json() as { detail?: unknown }
      if (typeof payload.detail === 'string') detail = payload.detail
      else if (Array.isArray(payload.detail)) detail = payload.detail.map(item => {
        const issue = item as { loc?: unknown[]; msg?: string }
        return `${issue.loc?.join('.') ?? 'input'}: ${issue.msg ?? 'invalid value'}`
      }).join('; ')
    } catch { /* keep HTTP detail */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'POST', body: JSON.stringify(body) })
}
