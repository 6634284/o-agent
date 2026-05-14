import { useEffect, useRef, useState } from 'react'
import { openEvents, api } from '../api'
import { StatusBadge } from './Sidebar.jsx'
import SessionTimeline from './SessionTimeline.jsx'
import EventStream from './EventStream.jsx'
import FeatureList from './FeatureList.jsx'

export default function TaskDetail({ task, onStart, onStop, onEdit, onDelete, onFollowUp }) {
  const [tab, setTab] = useState('events')
  const [events, setEvents] = useState([])
  const [features, setFeatures] = useState([])
  const esRef = useRef(null)
  const canFollowUp = task.status !== 'running' && task.progress_total > 0

  // reset + subscribe on task change
  useEffect(() => {
    setEvents([])
    if (esRef.current) esRef.current.close()
    esRef.current = openEvents(task.id, (ev) => {
      setEvents(prev => [...prev, ev].slice(-2000))
    })
    return () => { if (esRef.current) esRef.current.close() }
  }, [task.id])

  useEffect(() => {
    let alive = true
    const pull = () => api.features(task.id).then(f => { if (alive) setFeatures(f) }).catch(() => {})
    pull()
    const t = setInterval(pull, 4000)
    return () => { alive = false; clearInterval(t) }
  }, [task.id])

  const pct = task.progress_total > 0 ? (task.progress_passing / task.progress_total) * 100 : 0

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-4 border-b border-ink-700 bg-ink-900">
        <div className="flex items-center gap-3">
          <h1 data-testid="detail-task-name" className="text-lg font-semibold text-ink-300">{task.name}</h1>
          <StatusBadge status={task.status} />
          <span className="text-xs text-ink-500 mono">{task.id}</span>
          <span className="text-xs text-ink-500">· {task.model}</span>
          <span className="text-xs text-ink-500">
            · max-iter: {task.max_iterations ?? '∞'} · features: {task.feature_count}
          </span>
        </div>
        <div className="mt-3 flex items-center gap-2">
          {task.status !== 'running' ? (
            <button
              data-testid="btn-start"
              onClick={onStart}
              className="px-3 py-1.5 text-sm rounded bg-emerald-700 hover:bg-emerald-600 text-white"
            >▶ 启动</button>
          ) : (
            <button
              data-testid="btn-stop"
              onClick={onStop}
              className="px-3 py-1.5 text-sm rounded bg-amber-700 hover:bg-amber-600 text-white"
            >■ 停止</button>
          )}
          <button
            data-testid="btn-edit"
            disabled={task.status === 'running'}
            onClick={onEdit}
            className="px-3 py-1.5 text-sm rounded bg-ink-700 hover:bg-ink-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >编辑</button>
          <button
            data-testid="btn-delete"
            onClick={onDelete}
            className="px-3 py-1.5 text-sm rounded bg-red-900/70 hover:bg-red-800 text-red-100"
          >删除</button>
          <div className="flex-1" />
          <div className="text-xs text-ink-400">
            进度 <span className="mono text-ink-300">{task.progress_passing}/{task.progress_total}</span>{' '}
            ({pct.toFixed(1)}%)
          </div>
        </div>
        <div className="mt-2 h-1.5 rounded bg-ink-700 overflow-hidden">
          <div className="h-full bg-accent-500 transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </div>
        {task.last_error && (
          <div className="mt-3 px-3 py-2 text-xs text-red-200 bg-red-900/30 border border-red-900/60 rounded">
            last error: {task.last_error}
          </div>
        )}
      </div>

      <SessionTimeline sessions={task.sessions} />

      <div className="px-5 pt-2 border-b border-ink-700 bg-ink-900 flex gap-1 text-sm">
        {['events', 'features', 'follow_ups', 'config'].map(k => (
          <button
            key={k}
            data-testid={`tab-${k}`}
            onClick={() => setTab(k)}
            className={`px-3 py-2 border-b-2 ${
              tab === k ? 'border-accent-500 text-ink-300' : 'border-transparent text-ink-500 hover:text-ink-300'
            }`}
          >
            {k === 'events' ? '事件流'
              : k === 'features' ? `Features (${features.length})`
              : k === 'follow_ups' ? `继续迭代 (${(task.follow_ups || []).length})`
              : '配置'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden">
        {tab === 'events' && <EventStream events={events} />}
        {tab === 'features' && <FeatureList features={features} />}
        {tab === 'follow_ups' && (
          <FollowUpPanel task={task} canFollowUp={canFollowUp} onFollowUp={onFollowUp} />
        )}
        {tab === 'config' && <ConfigView task={task} />}
      </div>
    </div>
  )
}

function FollowUpPanel({ task, canFollowUp, onFollowUp }) {
  const [text, setText] = useState('')
  const [maxIter, setMaxIter] = useState(2)
  const [expand, setExpand] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async () => {
    setErr(null)
    if (!text.trim()) { setErr('请输入要做的修改'); return }
    setSubmitting(true)
    try {
      await onFollowUp({ prompt: text.trim(), max_iterations: Number(maxIter) || 2, expand })
      setText('')
    } catch (e) {
      setErr(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const history = task.follow_ups || []

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      <div className="bg-ink-800/60 border border-ink-700 rounded-lg p-4">
        <div className="text-sm font-semibold text-ink-300 mb-1">继续迭代</div>
        <div className="text-xs text-ink-500 mb-3">
          在已构建好的项目基础上打补丁。不会重新生成 feature_list，只跑 1-2 轮 coding session 做你说的改动。
          {!canFollowUp && (
            <span className="text-amber-400 ml-1">
              {task.status === 'running'
                ? '（任务正在运行，停止后才能发起迭代）'
                : '（当前任务还没有跑出进度，请先启动任务完成首次构建）'}
            </span>
          )}
        </div>
        <textarea
          data-testid="follow-up-text"
          rows={4}
          value={text}
          onChange={e => setText(e.target.value)}
          disabled={!canFollowUp || submitting}
          placeholder={'e.g. 在活动报名页面加一个「我的报名记录」入口，显示当前用户报过的所有活动'}
          className="w-full px-3 py-2 rounded bg-ink-900 border border-ink-700 focus:border-accent-500 outline-none text-sm disabled:opacity-50"
        />
        <div className="mt-2 flex items-center gap-3 flex-wrap">
          <label className="text-xs text-ink-500 flex items-center gap-1.5">
            最大迭代数
            <input
              data-testid="follow-up-max-iter"
              type="number" min="1" max="10"
              value={maxIter} onChange={e => setMaxIter(e.target.value)}
              disabled={!canFollowUp || submitting}
              className="w-20 px-2 py-1 rounded bg-ink-900 border border-ink-700 text-sm disabled:opacity-50"
            />
          </label>
          <label className="text-xs text-ink-400 flex items-center gap-1.5" title="开启后，会先让 LLM 把你的一句话扩展成更具体的改动清单再交给 coding agent。适合描述比较简略时使用。">
            <input
              data-testid="follow-up-expand"
              type="checkbox"
              checked={expand} onChange={e => setExpand(e.target.checked)}
              disabled={!canFollowUp || submitting}
            />
            先扩展为详细方案
          </label>
          <div className="flex-1" />
          <button
            data-testid="follow-up-submit"
            onClick={submit}
            disabled={!canFollowUp || submitting}
            className="px-4 py-1.5 rounded bg-accent-500 hover:bg-accent-400 text-white text-sm font-medium disabled:opacity-50"
          >
            {submitting ? '…' : '▶ 执行这次迭代'}
          </button>
        </div>
        {err && <div className="mt-2 text-sm text-red-300">{err}</div>}
      </div>

      <div>
        <div className="text-xs uppercase tracking-widest text-ink-500 mb-2">历史</div>
        {history.length === 0 && <div className="text-sm text-ink-500">尚无迭代记录</div>}
        <ul className="space-y-2">
          {[...history].reverse().map((fu, i) => (
            <li key={i} className="border border-ink-700 rounded p-3 bg-ink-900/60">
              <div className="flex items-center gap-2 text-xs text-ink-500 mb-1">
                <span className="mono">{fu.created_at}</span>
                <FollowUpStatus status={fu.status} />
                {fu.ended_at && <span>· 结束 <span className="mono">{fu.ended_at}</span></span>}
                {fu.expanded_text && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide bg-accent-500/20 text-accent-300">
                    已扩展
                  </span>
                )}
              </div>
              <div className="text-sm text-ink-200 whitespace-pre-wrap">{fu.text}</div>
              {fu.expanded_text && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-[11px] text-ink-500 hover:text-ink-300">
                    展开后的详细方案 (传给 coding agent 的版本)
                  </summary>
                  <div className="mt-1 text-xs text-ink-400 whitespace-pre-wrap bg-ink-900 border border-ink-700 rounded p-2">
                    {fu.expanded_text}
                  </div>
                </details>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function FollowUpStatus({ status }) {
  const colors = {
    running: 'bg-amber-900/50 text-amber-300',
    completed: 'bg-emerald-900/50 text-emerald-300',
    error: 'bg-red-900/50 text-red-300',
    stopped: 'bg-ink-700 text-ink-300',
  }
  const cls = colors[status] || 'bg-ink-700 text-ink-300'
  return <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide ${cls}`}>{status}</span>
}

function ConfigView({ task }) {
  return (
    <div className="h-full overflow-y-auto p-5 text-sm">
      <div className="grid grid-cols-2 gap-3 max-w-2xl">
        <Row label="name" value={task.name} />
        <Row label="id" value={<span className="mono">{task.id}</span>} />
        <Row label="model" value={<span className="mono">{task.model}</span>} />
        <Row label="max iterations" value={task.max_iterations ?? '∞'} />
        <Row label="feature count" value={task.feature_count} />
        <Row label="status" value={task.status} />
        <Row label="created" value={task.created_at} />
        <Row label="updated" value={task.updated_at} />
      </div>
      <div className="mt-6">
        <div className="text-xs uppercase tracking-widest text-ink-500 mb-2">app_spec</div>
        <pre className="mono text-xs bg-ink-900 border border-ink-700 rounded p-3 overflow-x-auto whitespace-pre-wrap">{task.app_spec}</pre>
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-ink-500 w-32 text-xs uppercase tracking-widest">{label}</span>
      <span className="text-ink-300">{value}</span>
    </div>
  )
}
