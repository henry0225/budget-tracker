import type { DashboardData, UploadResponse } from './types'

export async function uploadCSV(file: File): Promise<UploadResponse> {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `Upload failed (${res.status})`)
  }
  return res.json() as Promise<UploadResponse>
}

export async function uploadP2PCSV(
  file: File,
  sessionId?: string,
): Promise<UploadResponse> {
  const body = new FormData()
  body.append('file', file)
  if (sessionId) body.append('session_id', sessionId)
  const res = await fetch('/api/upload-p2p', { method: 'POST', body })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `Upload failed (${res.status})`)
  }
  return res.json() as Promise<UploadResponse>
}

export interface StreamHandlers {
  onProgress: (done: number, total: number) => void
  onDone: () => void
  onError: (msg: string) => void
}

export function streamCategorize(
  sessionId: string,
  apiKey: string,
  handlers: StreamHandlers,
): EventSource {
  const params = new URLSearchParams()
  if (apiKey) params.set('api_key', apiKey)
  const url = `/api/categorize/${encodeURIComponent(sessionId)}?${params}`
  const es = new EventSource(url)

  es.onmessage = (e: MessageEvent<string>) => {
    const msg = JSON.parse(e.data) as {
      type: string
      done?: number
      total?: number
      message?: string
    }
    if (msg.type === 'progress' && msg.done != null && msg.total != null) {
      handlers.onProgress(msg.done, msg.total)
    } else if (msg.type === 'done') {
      es.close()
      handlers.onDone()
    } else if (msg.type === 'error') {
      es.close()
      handlers.onError(msg.message ?? 'Categorization failed')
    }
  }

  es.onerror = () => {
    es.close()
    handlers.onError('Lost connection to server')
  }

  return es
}

export async function mergeCSVs(sessionIds: string[]): Promise<UploadResponse> {
  const res = await fetch('/api/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_ids: sessionIds }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `Merge failed (${res.status})`)
  }
  return res.json() as Promise<UploadResponse>
}

export async function getDashboard(sessionId: string): Promise<DashboardData> {
  const res = await fetch(`/api/dashboard/${encodeURIComponent(sessionId)}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `Failed to load dashboard (${res.status})`)
  }
  return res.json() as Promise<DashboardData>
}
