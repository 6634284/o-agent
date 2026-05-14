export default function Sidebar({ tasks, selectedId, onSelect, onNew, onDelete }) {
  return (
    <aside className="w-80 shrink-0 flex flex-col border-r border-ink-700 bg-ink-900">
      <div className="p-3 border-b border-ink-700">
        <button
          data-testid="btn-new-task"
          onClick={onNew}
          className="w-full py-2 rounded-md bg-accent-500 hover:bg-accent-400 text-white text-sm font-medium"
        >+ 新建任务</button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {tasks.length === 0 && (
          <div className="p-5 text-sm text-ink-500">暂无任务</div>
        )}
        {tasks.map(t => (
          <TaskRow
            key={t.id}
            task={t}
            selected={t.id === selectedId}
            onClick={() => onSelect(t.id)}
            onDelete={() => onDelete(t.id)}
          />
        ))}
      </div>
    </aside>
  )
}

function TaskRow({ task, selected, onClick, onDelete }) {
  const pct = task.progress_total > 0 ? (task.progress_passing / task.progress_total) * 100 : 0
  return (
    <div
      data-testid={`task-row-${task.id}`}
      onClick={onClick}
      className={`group cursor-pointer px-4 py-3 border-b border-ink-700/60 transition-colors ${
        selected ? 'bg-ink-800' : 'hover:bg-ink-800/60'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="truncate font-medium text-ink-300">{task.name}</div>
        <StatusBadge status={task.status} />
      </div>
      <div className="mt-2 text-xs text-ink-500 flex items-center gap-2">
        <span className="mono">{task.progress_passing}/{task.progress_total}</span>
        <span className="flex-1 h-1 rounded bg-ink-700 overflow-hidden">
          <span
            className="block h-full bg-accent-500"
            style={{ width: `${pct}%` }}
          />
        </span>
        <span>{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[11px] text-ink-500">
        <span className="mono">{task.id.slice(0,8)} · {task.model.split('/').pop()}</span>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300"
          title="删除"
        >✕</button>
      </div>
    </div>
  )
}

export function StatusBadge({ status }) {
  const map = {
    draft:     { c: 'bg-ink-700 text-ink-300',       t: 'draft' },
    running:   { c: 'bg-emerald-900/60 text-emerald-300 animate-pulse', t: 'running' },
    completed: { c: 'bg-blue-900/60 text-blue-300',  t: 'completed' },
    stopped:   { c: 'bg-amber-900/60 text-amber-300', t: 'stopped' },
    error:     { c: 'bg-red-900/60 text-red-300',    t: 'error' },
  }
  const v = map[status] || map.draft
  return <span className={`text-[10px] px-2 py-0.5 rounded ${v.c}`}>{v.t}</span>
}
