import { useEffect, useState, useCallback } from 'react'
import { api } from './api'
import Sidebar from './components/Sidebar.jsx'
import TaskDetail from './components/TaskDetail.jsx'
import TaskFormModal from './components/TaskFormModal.jsx'

export default function App() {
  const [tasks, setTasks] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [modal, setModal] = useState(null)   // { mode: 'create'|'edit', task? }
  const [models, setModels] = useState([])
  const [defaultSpec, setDefaultSpec] = useState('')
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const list = await api.listTasks()
      setTasks(list)
      if (!selectedId && list.length) setSelectedId(list[0].id)
    } catch (e) { setError(e.message) }
  }, [selectedId])

  useEffect(() => {
    api.models().then(r => { setModels(r.models); setDefaultSpec(r.default_spec) }).catch(e => setError(e.message))
    refresh()
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [refresh])

  const selected = tasks.find(t => t.id === selectedId) || null

  const handleCreate = async (body) => {
    const t = await api.createTask(body)
    setSelectedId(t.id)
    setModal(null)
    refresh()
  }
  const handleEdit = async (body) => {
    await api.updateTask(modal.task.id, body)
    setModal(null)
    refresh()
  }
  const handleDelete = async (id) => {
    if (!confirm('确定删除该任务？工作区和日志会一并清除。')) return
    await api.deleteTask(id)
    if (selectedId === id) setSelectedId(null)
    refresh()
  }
  const handleStart = async (id) => { await api.startTask(id); refresh() }
  const handleStop = async (id) => { await api.stopTask(id); refresh() }
  const handleFollowUp = async (id, body) => { await api.followUpTask(id, body); refresh() }

  return (
    <div className="h-full flex flex-col">
      <header className="flex items-center justify-between px-5 py-3 border-b border-ink-700 bg-ink-900">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-accent-500" />
          <div className="font-semibold tracking-wide">o-agent</div>
          <div className="text-xs text-ink-500">long-running agent console</div>
        </div>
        <div className="text-xs text-ink-500">
          {tasks.length} task{tasks.length === 1 ? '' : 's'} · running:{' '}
          <span className="text-accent-400">{tasks.filter(t => t.status === 'running').length}</span>
        </div>
      </header>

      {error && (
        <div className="px-5 py-2 bg-red-900/30 text-red-200 text-sm border-b border-red-900">
          {error}
          <button onClick={() => setError(null)} className="ml-3 underline">dismiss</button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          tasks={tasks}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onNew={() => setModal({ mode: 'create' })}
          onDelete={handleDelete}
        />
        <main className="flex-1 overflow-hidden">
          {selected ? (
            <TaskDetail
              task={selected}
              onStart={() => handleStart(selected.id)}
              onStop={() => handleStop(selected.id)}
              onEdit={() => setModal({ mode: 'edit', task: selected })}
              onDelete={() => handleDelete(selected.id)}
              onFollowUp={(body) => handleFollowUp(selected.id, body)}
            />
          ) : (
            <Empty onNew={() => setModal({ mode: 'create' })} />
          )}
        </main>
      </div>

      {modal && (
        <TaskFormModal
          mode={modal.mode}
          initial={modal.task}
          models={models}
          defaultSpec={defaultSpec}
          tasks={tasks}
          onClose={() => setModal(null)}
          onSubmit={modal.mode === 'create' ? handleCreate : handleEdit}
        />
      )}
    </div>
  )
}

function Empty({ onNew }) {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center">
        <div className="text-2xl font-semibold text-ink-300">还没有任务</div>
        <div className="mt-2 text-ink-500">创建一个任务，描述你要构建的应用，agent 会跨多个 session 持续推进。</div>
        <button
          onClick={onNew}
          className="mt-6 px-5 py-2.5 rounded-lg bg-accent-500 hover:bg-accent-400 text-white font-medium"
        >+ 新建任务</button>
      </div>
    </div>
  )
}
