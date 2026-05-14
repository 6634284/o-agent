import { useEffect, useMemo, useRef, useState } from 'react'

const FILTERS = [
  { k: 'all',   label: '全部' },
  { k: 'tool',  label: '工具调用' },
  { k: 'text',  label: '文本输出' },
  { k: 'progress', label: '进度' },
  { k: 'error', label: '错误' },
]

export default function EventStream({ events }) {
  const [filter, setFilter] = useState('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const endRef = useRef(null)

  const filtered = useMemo(() => events.filter(ev => {
    if (filter === 'all') return true
    if (filter === 'tool') return ev.kind === 'tool_use' || ev.kind === 'tool_result'
    if (filter === 'text') return ev.kind === 'text' || ev.kind === 'info'
    if (filter === 'progress') return ev.kind === 'progress' || ev.kind === 'session'
    if (filter === 'error') return ev.kind === 'error' || (ev.kind === 'tool_result' && ev.status !== 'done')
    return true
  }), [events, filter])

  useEffect(() => {
    if (autoScroll && endRef.current) endRef.current.scrollIntoView({ block: 'end' })
  }, [filtered, autoScroll])

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-2 border-b border-ink-700 flex items-center gap-2 text-xs">
        {FILTERS.map(f => (
          <button
            key={f.k}
            data-testid={`filter-${f.k}`}
            onClick={() => setFilter(f.k)}
            className={`px-2 py-1 rounded ${filter === f.k ? 'bg-accent-500/20 text-accent-400' : 'text-ink-500 hover:text-ink-300'}`}
          >{f.label}</button>
        ))}
        <div className="flex-1" />
        <label className="text-ink-500 flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
          自动滚动
        </label>
        <span className="text-ink-500">{filtered.length} / {events.length}</span>
      </div>
      <div data-testid="event-stream" className="flex-1 overflow-y-auto px-5 py-3 mono text-[12.5px] leading-[1.55]">
        {filtered.length === 0 && (
          <div className="text-ink-500">暂无事件。启动任务后会实时流入。</div>
        )}
        {filtered.map((ev, i) => <EventRow key={i} ev={ev} />)}
        <div ref={endRef} />
      </div>
    </div>
  )
}

function EventRow({ ev }) {
  const ts = (ev.ts || '').split('T')[1] || ''
  switch (ev.kind) {
    case 'session':
      return (
        <div className="mt-3 -mx-5 px-5 py-2 border-y border-ink-700 bg-ink-900">
          <span className="text-accent-400 font-semibold">
            ── SESSION #{ev.session} · {ev.role.toUpperCase()} ──
          </span>
          <span className="ml-2 text-ink-500">{ts}</span>
        </div>
      )
    case 'tool_use':
      return (
        <div className="flex gap-3 py-0.5">
          <span className="text-ink-500 shrink-0">{ts}</span>
          <span className="text-blue-400 shrink-0">▶ {ev.name}</span>
          <span className="text-ink-400 truncate">{ev.input}</span>
        </div>
      )
    case 'tool_result': {
      const color = ev.status === 'done'
        ? 'text-emerald-400'
        : ev.status === 'blocked'
          ? 'text-amber-400'
          : 'text-red-400'
      return (
        <div className="flex gap-3 py-0.5 pl-6">
          <span className={`${color} shrink-0`}>
            {ev.status === 'done' ? '✓' : ev.status === 'blocked' ? '⛔' : '✗'} {ev.status}
          </span>
          {ev.detail && <span className="text-ink-400">{ev.detail}</span>}
        </div>
      )
    }
    case 'progress':
      return (
        <div className="flex gap-3 py-0.5 text-accent-400">
          <span className="text-ink-500 shrink-0">{ts}</span>
          <span>⦿ progress: {ev.passing}/{ev.total} ({ev.pct}%)</span>
        </div>
      )
    case 'error':
      return (
        <div className="flex gap-3 py-0.5 text-red-400">
          <span className="text-ink-500 shrink-0">{ts}</span>
          <span>✗ {ev.text}</span>
        </div>
      )
    case 'exit':
      return (
        <div className="py-1 text-ink-500">── process exit code {ev.code} ──</div>
      )
    case 'info':
      return <div className="py-0.5 text-ink-500">{ev.text}</div>
    case 'text':
    default:
      return <div className="py-0.5 text-ink-300 whitespace-pre-wrap">{ev.text}</div>
  }
}
