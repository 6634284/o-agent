import { useMemo, useState } from 'react'

export default function FeatureList({ features }) {
  const [filter, setFilter] = useState('all')   // all | passing | failing
  const [q, setQ] = useState('')
  const [openIdx, setOpenIdx] = useState(null)

  const filtered = useMemo(() => features.filter((f, i) => {
    if (filter === 'passing' && !f.passes) return false
    if (filter === 'failing' && f.passes) return false
    if (q && !(`${i} ${f.description || ''} ${f.category || ''}`.toLowerCase().includes(q.toLowerCase()))) return false
    return true
  }).map((f, i) => ({ ...f, _i: features.indexOf(f) })), [features, filter, q])

  const passing = features.filter(f => f.passes).length

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-2 border-b border-ink-700 flex items-center gap-3 text-xs">
        {['all', 'passing', 'failing'].map(k => (
          <button
            key={k}
            data-testid={`feat-filter-${k}`}
            onClick={() => setFilter(k)}
            className={`px-2 py-1 rounded ${filter === k ? 'bg-accent-500/20 text-accent-400' : 'text-ink-500 hover:text-ink-300'}`}
          >{k}</button>
        ))}
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="search..."
          className="ml-2 px-2 py-1 rounded bg-ink-800 border border-ink-700 text-ink-300 text-xs outline-none focus:border-accent-500"
        />
        <div className="flex-1" />
        <span className="text-ink-500">
          {passing} / {features.length} passing · showing {filtered.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {features.length === 0 && (
          <div className="p-6 text-sm text-ink-500">feature_list.json 尚未生成。Initializer 生成后自动刷新。</div>
        )}
        {filtered.map(f => (
          <div
            key={f._i}
            className="px-5 py-2.5 border-b border-ink-700/60 cursor-pointer hover:bg-ink-800/40"
            onClick={() => setOpenIdx(openIdx === f._i ? null : f._i)}
          >
            <div className="flex items-start gap-3">
              <span className={`shrink-0 mt-0.5 w-4 h-4 rounded border text-[10px] flex items-center justify-center ${
                f.passes ? 'border-emerald-500 text-emerald-400 bg-emerald-900/30' : 'border-ink-600 text-ink-500'
              }`}>{f.passes ? '✓' : ''}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink-800 text-ink-400 mono shrink-0">#{f._i + 1}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink-800 text-ink-400 shrink-0">{f.category || '-'}</span>
              <span className={`text-sm ${f.passes ? 'text-ink-400' : 'text-ink-300'}`}>{f.description}</span>
            </div>
            {openIdx === f._i && (
              <ol className="mt-2 ml-12 text-xs text-ink-400 list-decimal list-inside space-y-0.5">
                {(f.steps || []).map((s, j) => <li key={j}>{s}</li>)}
              </ol>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
