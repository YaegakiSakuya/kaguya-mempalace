import { useState, useEffect, useCallback, useRef } from 'react'
import useTelegram from '../../hooks/useTelegram'
import useApi from '../../hooks/useApi'
import useHaptic from '../../hooks/useHaptic'

const TOAST_FAIL_COLOR = '#C44'

const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 16px',
  borderBottom: '1px solid var(--border)',
}

const labelStyle = { fontSize: '12px', color: 'var(--text-muted)' }

const selectStyle = {
  background: 'var(--bg-hover)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: '2px',
  padding: '6px 8px',
  fontSize: '13px',
  fontFamily: 'var(--font-mono)',
  flex: 1,
  minWidth: 0,
}

const inputStyle = {
  background: 'var(--bg-hover)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  borderRadius: '2px',
  padding: '6px 8px',
  fontSize: '13px',
  width: '100%',
  fontFamily: 'var(--font-mono)',
}

const btnStyle = {
  background: 'transparent',
  color: 'var(--text-muted)',
  border: '1px solid var(--border)',
  borderRadius: '2px',
  padding: '4px 10px',
  fontSize: '12px',
  cursor: 'pointer',
  fontFamily: 'var(--font-serif)',
}

const btnPrimaryStyle = {
  ...btnStyle,
  color: 'var(--accent)',
  borderColor: 'var(--accent-dim)',
}

function Toast({ toast }) {
  if (!toast) return null
  const bg = toast.type === 'fail' ? TOAST_FAIL_COLOR : 'var(--accent)'
  return (
    <div
      style={{
        position: 'fixed',
        top: '16px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: bg,
        color: 'var(--text)',
        padding: '8px 16px',
        borderRadius: '2px',
        fontSize: '13px',
        zIndex: 9999,
        maxWidth: '90vw',
        boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
      }}
    >
      {toast.message}
    </div>
  )
}

function ProviderForm({ initial, onSave, onCancel, isCreate }) {
  const { impact } = useHaptic()
  const [name, setName] = useState(initial?.name || '')
  const [baseUrl, setBaseUrl] = useState(initial?.base_url || '')
  const [apiKey, setApiKey] = useState('')
  const [localErr, setLocalErr] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    impact('medium')
    const n = name.trim()
    const u = baseUrl.trim()
    const k = apiKey.trim()
    if (!n) { setLocalErr('name 不能为空'); return }
    if (!u.startsWith('http://') && !u.startsWith('https://')) {
      setLocalErr('base_url 必须以 http:// 或 https:// 开头')
      return
    }
    if (isCreate && !k) { setLocalErr('api_key 不能为空'); return }
    setLocalErr('')
    setSaving(true)
    try {
      const payload = isCreate
        ? { name: n, base_url: u, api_key: k }
        : (() => {
            const p = {}
            if (n !== (initial?.name || '')) p.name = n
            if (u !== (initial?.base_url || '')) p.base_url = u
            if (k) p.api_key = k
            return p
          })()
      await onSave(payload)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-hover)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div>
          <div style={{ ...labelStyle, marginBottom: '4px' }}>name</div>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle}
            placeholder="站点名称"
          />
        </div>
        <div>
          <div style={{ ...labelStyle, marginBottom: '4px' }}>base_url</div>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            style={inputStyle}
            placeholder="https://..."
          />
        </div>
        <div>
          <div style={{ ...labelStyle, marginBottom: '4px' }}>api_key</div>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            style={inputStyle}
            placeholder={isCreate ? 'sk-...' : '留空保持不变'}
          />
        </div>
        {localErr && (
          <div style={{ fontSize: '12px', color: TOAST_FAIL_COLOR }}>{localErr}</div>
        )}
        <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
          <button
            onClick={submit}
            disabled={saving}
            style={{ ...btnPrimaryStyle, opacity: saving ? 0.5 : 1 }}
          >
            {saving ? '保存中...' : '保存'}
          </button>
          <button onClick={onCancel} disabled={saving} style={btnStyle}>
            取消
          </button>
        </div>
      </div>
    </div>
  )
}

export default function LLMConfigCard() {
  const { initData } = useTelegram()
  const { get, post, patch, del } = useApi(initData)
  const { impact, notification } = useHaptic()

  const [providers, setProviders] = useState([])
  const [activeProviderId, setActiveProviderId] = useState('')
  const [activeModel, setActiveModel] = useState('')
  const [activeProviderName, setActiveProviderName] = useState('')
  const [managementOpen, setManagementOpen] = useState(false)
  const [refreshingModels, setRefreshingModels] = useState(false)
  const [toast, setToast] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [creatingNew, setCreatingNew] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [pingingId, setPingingId] = useState(null)
  const [refreshingIdSet, setRefreshingIdSet] = useState(() => new Set())
  const [autoRefreshingId, setAutoRefreshingId] = useState(null)

  const toastTimer = useRef(null)
  const showToast = useCallback((message, type = 'ok') => {
    setToast({ message, type })
    notification(type === 'fail' ? 'error' : 'success')
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 3000)
  }, [notification])

  const handleError = useCallback((err, action) => {
    if (err?.status === 401) {
      showToast('鉴权失败，请重新打开 miniapp', 'fail')
    } else if (err?.networkError) {
      showToast('网络错误', 'fail')
    } else {
      const msg = err?.data?.error || err?.message || 'unknown'
      showToast(`${action} 失败：${msg}`, 'fail')
    }
  }, [showToast])

  const loadAll = useCallback(async () => {
    const listRes = await get('/miniapp/config/providers')
    if (listRes?.providers) {
      setProviders(listRes.providers)
      if (listRes.active_provider_id) {
        setActiveProviderId(listRes.active_provider_id)
      }
    }
    const activeRes = await get('/miniapp/config/active')
    if (activeRes?.provider_id) {
      setActiveProviderId(activeRes.provider_id)
      setActiveProviderName(activeRes.provider_name || '')
      setActiveModel(activeRes.model || '')
    }
  }, [get])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  useEffect(() => {
    const p = providers.find((x) => x.id === activeProviderId)
    if (p) setActiveProviderName(p.name || '')
  }, [providers, activeProviderId])

  const activeProvider = providers.find((p) => p.id === activeProviderId) || null

  const switchSeqRef = useRef(0)

  const switchActive = async (providerId, model) => {
    const prevId = activeProviderId
    const prevModel = activeModel
    const seq = ++switchSeqRef.current
    setActiveProviderId(providerId)
    setActiveModel(model)
    try {
      await post('/miniapp/config/active', { provider_id: providerId, model })
      if (seq !== switchSeqRef.current) return
      setProviders((ps) =>
        ps.map((p) => (p.id === providerId ? { ...p, last_model: model } : p))
      )
      notification('success')
    } catch (err) {
      if (seq !== switchSeqRef.current) return
      setActiveProviderId(prevId)
      setActiveModel(prevModel)
      handleError(err, '切换')
    }
  }

  const handleProviderChange = async (e) => {
    impact('light')
    const newId = e.target.value
    const p = providers.find((x) => x.id === newId)
    if (!p) return

    let candidate = p

    if ((candidate.available_models || []).length === 0) {
      const prevId = activeProviderId
      setActiveProviderId(newId)
      setAutoRefreshingId(newId)
      try {
        const res = await post(`/miniapp/config/providers/${newId}/models`)
        const models = res?.models || []
        setProviders((ps) =>
          ps.map((x) =>
            x.id === newId
              ? { ...x, available_models: models, models_refreshed_at: res?.refreshed_at || x.models_refreshed_at }
              : x
          )
        )
        candidate = { ...candidate, available_models: models }
      } catch (err) {
        setActiveProviderId(prevId)
        setAutoRefreshingId(null)
        handleError(err, '刷新')
        return
      }
      setAutoRefreshingId(null)
    }

    const models = candidate.available_models || []
    if (models.length === 0) {
      showToast(`${p.name} 暂无可用模型`, 'fail')
      return
    }

    const nextModel = candidate.last_model && models.includes(candidate.last_model)
      ? candidate.last_model
      : models[0]

    switchActive(newId, nextModel)
  }

  const handleModelChange = (e) => {
    impact('light')
    const newModel = e.target.value
    switchActive(activeProviderId, newModel)
  }

  const handleRefreshModels = async () => {
    impact('medium')
    if (!activeProviderId) return
    setRefreshingModels(true)
    try {
      const res = await post(`/miniapp/config/providers/${activeProviderId}/models`)
      const models = res?.models || []
      setProviders((ps) =>
        ps.map((p) =>
          p.id === activeProviderId
            ? { ...p, available_models: models, models_refreshed_at: res?.refreshed_at || p.models_refreshed_at }
            : p
        )
      )
      showToast(`刷新成功 · ${models.length} 个模型`, 'ok')
    } catch (err) {
      handleError(err, '刷新')
    } finally {
      setRefreshingModels(false)
    }
  }

  const handleRefreshProviderModels = async (provider) => {
    impact('medium')
    setRefreshingIdSet((prev) => {
      const next = new Set(prev)
      next.add(provider.id)
      return next
    })
    try {
      const res = await post(`/miniapp/config/providers/${provider.id}/models`)
      const models = res?.models || []
      setProviders((ps) =>
        ps.map((p) =>
          p.id === provider.id
            ? { ...p, available_models: models, models_refreshed_at: res?.refreshed_at || p.models_refreshed_at }
            : p
        )
      )
      showToast(`${provider.name} 刷新成功 · ${models.length} 个模型`, 'ok')
    } catch (err) {
      const msg = err?.data?.error || err?.message || 'unknown'
      showToast(`${provider.name} 刷新失败：${msg}`, 'fail')
    } finally {
      setRefreshingIdSet((prev) => {
        const next = new Set(prev)
        next.delete(provider.id)
        return next
      })
    }
  }

  const handlePing = async (provider) => {
    impact('medium')
    setPingingId(provider.id)
    try {
      const body = provider.last_model ? { model: provider.last_model } : {}
      const res = await post(`/miniapp/config/providers/${provider.id}/ping`, body)
      if (res?.ok) {
        showToast(`${provider.name} 连通 · ${res.latency_ms}ms · ${res.model}`, 'ok')
      } else {
        showToast(`${provider.name} 测试失败：${res?.error || 'unknown'}`, 'fail')
      }
    } catch (err) {
      handleError(err, 'Ping')
    } finally {
      setPingingId(null)
    }
  }

  const handleDelete = async (provider) => {
    try {
      await del(`/miniapp/config/providers/${provider.id}`)
      setProviders((ps) => ps.filter((p) => p.id !== provider.id))
      setConfirmDeleteId(null)
      showToast(`已删除 ${provider.name}`, 'ok')
    } catch (err) {
      handleError(err, '删除')
      setConfirmDeleteId(null)
    }
  }

  const handleCreate = async (payload) => {
    try {
      const res = await post('/miniapp/config/providers', payload)
      if (res?.provider) {
        setProviders((ps) => [...ps, res.provider])
      } else {
        await loadAll()
      }
      setCreatingNew(false)
      showToast('已新增站点', 'ok')
    } catch (err) {
      handleError(err, '新增')
    }
  }

  const handleEdit = async (provider, payload) => {
    try {
      const res = await patch(`/miniapp/config/providers/${provider.id}`, payload)
      if (res?.provider) {
        setProviders((ps) => ps.map((p) => (p.id === provider.id ? res.provider : p)))
      } else {
        await loadAll()
      }
      setEditingId(null)
      showToast('已更新', 'ok')
    } catch (err) {
      handleError(err, '编辑')
    }
  }

  const modelOptions = activeProvider?.available_models || []
  const modelsEmpty = modelOptions.length === 0

  return (
    <>
      <Toast toast={toast} />
      <div className="card" style={{ paddingLeft: '20px', paddingRight: '20px' }}>
        {/* 第一层：当前激活 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            padding: '14px 0',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span style={labelStyle}>当前调用</span>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
            <span style={{ fontSize: '14px', color: 'var(--accent)' }}>
              {activeProviderName || '\u2014'}
            </span>
            <span
              className="font-mono"
              style={{ fontSize: '13px', color: 'var(--text)' }}
            >
              {activeModel || '\u2014'}
            </span>
          </div>
        </div>

        {/* 第二层：快速切换 */}
        <div style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
          <div style={{ marginBottom: '10px' }}>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>Provider</div>
            <select
              value={activeProviderId}
              onChange={handleProviderChange}
              disabled={!!autoRefreshingId}
              style={{ ...selectStyle, opacity: autoRefreshingId ? 0.5 : 1 }}
            >
              {providers.length === 0 && <option value="">— 加载中 —</option>}
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div style={{ ...labelStyle, marginBottom: '4px' }}>Model</div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <select
                value={modelsEmpty ? '' : activeModel}
                onChange={handleModelChange}
                disabled={modelsEmpty}
                style={selectStyle}
              >
                {modelsEmpty ? (
                  <option value="">— 请先刷新模型列表 —</option>
                ) : (
                  modelOptions.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))
                )}
              </select>
              <button
                onClick={handleRefreshModels}
                disabled={refreshingModels || !activeProviderId}
                style={{ ...btnStyle, whiteSpace: 'nowrap', opacity: refreshingModels ? 0.5 : 1 }}
              >
                {refreshingModels ? '刷新中...' : '刷新模型列表'}
              </button>
            </div>
          </div>
        </div>

        {/* 第三层：管理站点 */}
        <div>
          <div
            onClick={() => { impact('light'); setManagementOpen(!managementOpen) }}
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px 0',
              cursor: 'pointer',
              color: 'var(--text-muted)',
              fontSize: '13px',
              gap: '6px',
            }}
          >
            <span>{managementOpen ? '\u25BE' : '\u25B8'}</span>
            <span>管理站点</span>
          </div>
          {managementOpen && (
            <div style={{ marginLeft: '-20px', marginRight: '-20px', borderTop: '1px solid var(--border)' }}>
              {providers.map((p) => {
                const isEditing = editingId === p.id
                const isConfirmingDelete = confirmDeleteId === p.id
                if (isEditing) {
                  return (
                    <ProviderForm
                      key={p.id}
                      initial={p}
                      isCreate={false}
                      onSave={(payload) => handleEdit(p, payload)}
                      onCancel={() => setEditingId(null)}
                    />
                  )
                }
                return (
                  <div key={p.id} style={{ ...rowStyle, flexDirection: 'column', alignItems: 'stretch', gap: '6px' }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'baseline',
                        gap: '8px',
                      }}
                    >
                      <span style={{ fontSize: '13px', color: 'var(--text)' }}>{p.name}</span>
                      <span
                        className="font-mono"
                        style={{ fontSize: '12px', color: 'var(--text-secondary)' }}
                      >
                        {p.api_key || '—'}
                      </span>
                    </div>
                    {isConfirmingDelete ? (
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>确定？</span>
                        <button
                          onClick={() => handleDelete(p)}
                          style={{ ...btnStyle, color: TOAST_FAIL_COLOR, borderColor: TOAST_FAIL_COLOR }}
                        >
                          是
                        </button>
                        <button onClick={() => setConfirmDeleteId(null)} style={btnStyle}>
                          否
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => { impact('medium'); setEditingId(p.id) }} style={btnStyle}>
                          编辑
                        </button>
                        <button
                          onClick={() => handleRefreshProviderModels(p)}
                          disabled={refreshingIdSet.has(p.id)}
                          style={{ ...btnStyle, opacity: refreshingIdSet.has(p.id) ? 0.5 : 1 }}
                        >
                          {refreshingIdSet.has(p.id) ? '刷新中...' : '刷新模型'}
                        </button>
                        <button
                          onClick={() => handlePing(p)}
                          disabled={pingingId === p.id}
                          style={{ ...btnStyle, opacity: pingingId === p.id ? 0.5 : 1 }}
                        >
                          {pingingId === p.id ? '测试中...' : '测试'}
                        </button>
                        <button
                          onClick={() => { notification('warning'); setConfirmDeleteId(p.id) }}
                          style={{ ...btnStyle, color: TOAST_FAIL_COLOR }}
                        >
                          删除
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
              {creatingNew ? (
                <ProviderForm
                  isCreate
                  onSave={handleCreate}
                  onCancel={() => setCreatingNew(false)}
                />
              ) : (
                <div style={{ padding: '12px 16px' }}>
                  <button onClick={() => { impact('medium'); setCreatingNew(true) }} style={btnPrimaryStyle}>
                    + 新增站点
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
