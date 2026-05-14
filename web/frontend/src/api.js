const BASE = ''  // same-origin via vite proxy

async function j(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    throw new Error(`${r.status} ${r.statusText}: ${text}`)
  }
  const ct = r.headers.get('content-type') || ''
  return ct.includes('application/json') ? r.json() : r.text()
}

export const api = {
  listTasks: () => j('/api/tasks'),
  getTask: (id) => j(`/api/tasks/${id}`),
  createTask: (body) => j('/api/tasks', { method: 'POST', body: JSON.stringify(body) }),
  updateTask: (id, body) => j(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteTask: (id) => j(`/api/tasks/${id}`, { method: 'DELETE' }),
  startTask: (id) => j(`/api/tasks/${id}/start`, { method: 'POST' }),
  stopTask: (id) => j(`/api/tasks/${id}/stop`, { method: 'POST' }),
  followUpTask: (id, body) => j(`/api/tasks/${id}/follow_up`, { method: 'POST', body: JSON.stringify(body) }),
  features: (id) => j(`/api/tasks/${id}/features`),
  models: () => j('/api/models'),
}

export function openEvents(taskId, onEvent, onError) {
  const es = new EventSource(`/api/tasks/${taskId}/events`)
  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data))
    } catch (_) { /* keepalive or malformed */ }
  }
  es.onerror = (e) => {
    if (onError) onError(e)
  }
  return es
}
