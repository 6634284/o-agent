export default function SessionTimeline({ sessions = [] }) {
  return (
    <div className="px-5 py-3 bg-ink-900/60 border-b border-ink-700 overflow-x-auto">
      <div className="text-[11px] uppercase tracking-widest text-ink-500 mb-2">Session timeline</div>
      <div className="flex items-center gap-2">
        {sessions.length === 0 && (
          <div className="text-sm text-ink-500">尚未开始</div>
        )}
        {sessions.map((s, i) => {
          const active = !s.ended_at
          const isInit = s.role === 'initializer'
          return (
            <div key={i} className="flex items-center">
              <div
                className={`px-3 py-1.5 rounded-md border text-xs whitespace-nowrap ${
                  active
                    ? 'border-accent-500 bg-accent-500/10 text-accent-400 animate-pulse'
                    : isInit
                      ? 'border-blue-900/60 bg-blue-900/20 text-blue-300'
                      : 'border-ink-700 bg-ink-800 text-ink-300'
                }`}
              >
                <span className="mono mr-1">#{s.num}</span>
                {isInit ? 'INIT' : 'CODING'}
                {active && <span className="ml-1">…</span>}
              </div>
              {i < sessions.length - 1 && <div className="w-4 h-px bg-ink-700" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
