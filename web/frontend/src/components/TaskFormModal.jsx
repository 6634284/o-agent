import { useEffect, useState } from 'react'

export default function TaskFormModal({ mode, initial, models, defaultSpec, tasks = [], onClose, onSubmit }) {
  const [name, setName] = useState(initial?.name || '')
  const [model, setModel] = useState(initial?.model || models[0]?.id || 'ppio/pa/claude-opus-4-7')
  const [maxIter, setMaxIter] = useState(initial?.max_iterations ?? 3)
  const [maxIterUnlimited, setMaxIterUnlimited] = useState(initial?.max_iterations == null)
  const [featureCount, setFeatureCount] = useState(initial?.feature_count ?? 20)
  const [description, setDescription] = useState(initial?.description || '')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [spec, setSpec] = useState(initial?.app_spec || '')
  const [forkFrom, setForkFrom] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState(null)

  // Only "built" tasks (with features generated or a completed run) make sense as fork sources.
  const forkableTasks = tasks.filter(t =>
    t.id !== initial?.id && (t.progress_total > 0 || t.status === 'completed')
  )
  const isCreate = mode === 'create'

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const submit = async () => {
    if (!forkFrom && !description.trim() && !spec.trim()) {
      setErr('请至少填写「任务描述」，或选择一个源项目 fork')
      return
    }
    setErr(null); setSubmitting(true)
    try {
      await onSubmit({
        name,
        model,
        max_iterations: maxIterUnlimited ? null : Number(maxIter),
        feature_count: Number(featureCount),
        description: description.trim(),
        app_spec: showAdvanced ? spec : '',
        ...(isCreate && forkFrom ? { fork_from_task_id: forkFrom } : {}),
      })
    } catch (e) {
      setErr(e.message); setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-ink-900 border border-ink-700 rounded-xl w-[720px] max-w-[92vw] max-h-[88vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-ink-700 flex items-center">
          <div className="text-lg font-semibold">{mode === 'create' ? '新建任务' : '编辑任务'}</div>
          <div className="flex-1" />
          <button onClick={onClose} className="text-ink-500 hover:text-ink-300">✕</button>
        </div>
        <div className="p-5 overflow-y-auto space-y-4">
          <Field label="任务名">
            <input
              data-testid="form-name"
              value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. claude.ai clone"
              className="w-full px-3 py-2 rounded bg-ink-800 border border-ink-700 focus:border-accent-500 outline-none"
            />
          </Field>
          {isCreate && forkableTasks.length > 0 && (
            <Field label="从已有项目 fork（可选）· 跳过从零开始">
              <select
                data-testid="form-fork-from"
                value={forkFrom} onChange={e => setForkFrom(e.target.value)}
                className="w-full px-3 py-2 rounded bg-ink-800 border border-ink-700 focus:border-accent-500 outline-none"
              >
                <option value="">（不 fork，从零开始）</option>
                {forkableTasks.map(t => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {t.progress_passing}/{t.progress_total} · {t.id}
                  </option>
                ))}
              </select>
              <div className="mt-1 text-[11px] text-ink-500">
                {forkFrom
                  ? '将复制该项目的代码与 git 历史到新任务。留空描述 = 纯复制；填写描述 = 基于原代码按新规格重建（会丢弃旧 feature_list）。'
                  : '选中后会基于该任务的代码库创建新任务，不用再手动 cp 目录。'}
              </div>
            </Field>
          )}
          <div className="grid grid-cols-3 gap-3">
            <Field label="模型">
              <select
                data-testid="form-model"
                value={model} onChange={e => setModel(e.target.value)}
                className="w-full px-3 py-2 rounded bg-ink-800 border border-ink-700 focus:border-accent-500 outline-none"
              >
                {models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </Field>
            <Field label="最大迭代数">
              <div className="flex items-center gap-2">
                <input
                  data-testid="form-max-iter"
                  type="number" min="1"
                  disabled={maxIterUnlimited}
                  value={maxIter} onChange={e => setMaxIter(e.target.value)}
                  className="w-24 px-3 py-2 rounded bg-ink-800 border border-ink-700 disabled:opacity-50 focus:border-accent-500 outline-none"
                />
                <label className="text-xs text-ink-400 flex items-center gap-1">
                  <input type="checkbox" checked={maxIterUnlimited} onChange={e => setMaxIterUnlimited(e.target.checked)} />
                  ∞
                </label>
              </div>
            </Field>
            <Field label="初始 Feature 数">
              <input
                data-testid="form-feature-count"
                type="number" min="5" max="500"
                value={featureCount} onChange={e => setFeatureCount(e.target.value)}
                className="w-full px-3 py-2 rounded bg-ink-800 border border-ink-700 focus:border-accent-500 outline-none"
              />
            </Field>
          </div>
          <Field label="任务描述 · 用自然语言说清楚要做什么">
            <textarea
              data-testid="form-description"
              value={description} onChange={e => setDescription(e.target.value)}
              rows={5}
              placeholder="e.g. 做一个羽毛球会员管理后台，第一版需要：报名、会员充值、客服、消息 四个功能"
              className="w-full px-3 py-2 rounded bg-ink-800 border border-ink-700 focus:border-accent-500 outline-none text-sm"
            />
            <div className="mt-1 text-[11px] text-ink-500">
              提交后会自动调用大模型把这段描述扩展成一份详细的项目规格，再交给 agent 去构建。
            </div>
          </Field>

          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(v => !v)}
              className="text-xs text-ink-400 hover:text-ink-200 underline-offset-2 hover:underline"
            >
              {showAdvanced ? '▼ 收起高级（手写 app_spec）' : '▶ 高级：手写完整 app_spec（可选）'}
            </button>
            {showAdvanced && (
              <div className="mt-2">
                <textarea
                  data-testid="form-spec"
                  value={spec} onChange={e => setSpec(e.target.value)}
                  rows={12}
                  placeholder="若填写，将直接作为 app_spec（不再自动扩展描述）"
                  className="w-full px-3 py-2 rounded bg-ink-800 border border-ink-700 focus:border-accent-500 outline-none mono text-xs"
                />
              </div>
            )}
          </div>

          {err && <div className="text-sm text-red-300">{err}</div>}
        </div>
        <div className="px-5 py-3 border-t border-ink-700 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 rounded bg-ink-800 hover:bg-ink-700 text-sm">取消</button>
          <button
            data-testid="form-submit"
            onClick={submit} disabled={submitting}
            className="px-4 py-2 rounded bg-accent-500 hover:bg-accent-400 text-white text-sm font-medium disabled:opacity-60"
          >
            {submitting ? '…' : mode === 'create' ? '创建任务' : '保存修改'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="text-xs uppercase tracking-widest text-ink-500 mb-1.5">{label}</div>
      {children}
    </label>
  )
}
