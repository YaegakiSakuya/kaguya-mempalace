import { useState, useEffect, useCallback, useRef } from 'react'
import useTelegram from '../../hooks/useTelegram'
import useApi from '../../hooks/useApi'
import useHaptic from '../../hooks/useHaptic'

const TOAST_FAIL_COLOR = 'var(--fail)'

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
    if (!n) { setLocalErr('name required'); return }
    if (!u.startsWith('http://') && !u.startsWith('https://')) {
      setLocalErr('base_url must start with http:// or https://')
      return
    }
    if (isCreate && !k) { setLocalErr('api_key required'); return }
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
            placeholder="provider name"
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
            placeholder={isCreate ? 'sk-...' : 'leave blank to keep'}
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
            {saving ? 'saving…' : 'save'}
          </button>
          <button onClick={onCancel} disabled={saving} style={btnStyle}>
            cancel
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
      showToast('auth failed · reopen miniapp', 'fail')
    } else if (err?.networkError) {
      showToast('network error', 'fail')
    } else {
      const msg = err?.data?.error || err?.message || 'unknown'
      showToast(`${action} failed · ${msg}`, 'fail')
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
      handleError(err, 'switch')
    }
  }

  const handleProviderChange = async (e) => {
    impact('light')
    const newId = e.target.value
    const p = providers.find((x) => x.id === newId)
    if (!p) return

    let candidate = p
    const prevId = activeProviderId
    let didOptimisticSwitch = false

    if ((candidate.available_models || []).length === 0) {
      setActiveProviderId(newId)
      didOptimisticSwitch = true
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
        handleError(err, 'refresh')
        return
      }
      setAutoRefreshingId(null)
    }

    const models = candidate.available_models || []
    if (models.length === 0) {
      if (didOptimisticSwitch) setActiveProviderId(prevId)
      showToast(`${p.name} has no models`, 'fail')
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
      showToast(`refreshed · ${models.length} models`, 'ok')
    } catch (err) {
      handleError(err, 'refresh')
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
      showToast(`${provider.name} refreshed · ${models.length} models`, 'ok')
    } catch (err) {
      const msg = err?.data?.error || err?.message || 'unknown'
      showToast(`${provider.name} refresh failed · ${msg}`, 'fail')
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
        showToast(`${provider.name} ok · ${res.latency_ms}ms · ${res.model}`, 'ok')
      } else {
        showToast(`${provider.name} ping failed · ${res?.error || 'unknown'}`, 'fail')
      }
    } catch (err) {
      handleError(err, 'ping')
    } finally {
      setPingingId(null)
    }
  }

  const handleDelete = async (provider) => {
    try {
      await del(`/miniapp/config/providers/${provider.id}`)
      setProviders((ps) => ps.filter((p) => p.id !== provider.id))
      setConfirmDeleteId(null)
      showToast(`deleted ${provider.name}`, 'ok')
    } catch (err) {
      handleError(err, 'delete')
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
      showToast('provider created', 'ok')
    } catch (err) {
      handleError(err, 'create')
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
      showToast('updated', 'ok')
    } catch (err) {
      handleError(err, 'edit')
    }
  }

  const modelOptions = activeProvider?.available_models || []
  const modelsEmpty = modelOptions.length === 0

  return (
    <>
      <Toast toast={toast} />
      <div className="card" style={{ paddingLeft: '20px', paddingRight: '20px' }}>
        {/* 第一层：Provider + Model 单行 · 刷新按钮图标化 */}
        <div style={{ padding: '14px 0', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select
              value={activeProviderId}
              onChange={handleProviderChange}
              disabled={!!autoRefreshingId}
              aria-label="Provider"
              style={{ ...selectStyle, opacity: autoRefreshingId ? 0.5 : 1 }}
            >
              {providers.length === 0 && <option value="">— loading —</option>}
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              value={modelsEmpty ? '' : activeModel}
              onChange={handleModelChange}
              disabled={modelsEmpty}
              aria-label="Model"
              style={selectStyle}
            >
              {modelsEmpty ? (
                <option value="">— refresh to load —</option>
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
              aria-label="Refresh models"
              title="Refresh models"
              style={{
                ...btnStyle,
                padding: '6px 8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                opacity: refreshingModels ? 0.5 : 1,
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{
                  animation: refreshingModels ? 'spin 1s linear infinite' : 'none',
                }}
              >
                <path d="M12 7a5 5 0 1 1-1.5-3.5" />
                <polyline points="12,2 12,5 9,5" />
              </svg>
            </button>
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
              fontSize: '12px',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              gap: '6px',
            }}
          >
            <span>{managementOpen ? '\u25BE' : '\u25B8'}</span>
            <span>providers</span>
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
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>delete?</span>
                        <button
                          onClick={() => handleDelete(p)}
                          style={{ ...btnStyle, color: TOAST_FAIL_COLOR, borderColor: TOAST_FAIL_COLOR }}
                        >
                          yes
                        </button>
                        <button onClick={() => setConfirmDeleteId(null)} style={btnStyle}>
                          no
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => { impact('medium'); setEditingId(p.id) }} style={btnStyle}>
                          edit
                        </button>
                        <button
                          onClick={() => handleRefreshProviderModels(p)}
                          disabled={refreshingIdSet.has(p.id)}
                          style={{ ...btnStyle, opacity: refreshingIdSet.has(p.id) ? 0.5 : 1 }}
                        >
                          {refreshingIdSet.has(p.id) ? 'refreshing…' : 'refresh'}
                        </button>
                        <button
                          onClick={() => handlePing(p)}
                          disabled={pingingId === p.id}
                          style={{ ...btnStyle, opacity: pingingId === p.id ? 0.5 : 1 }}
                        >
                          {pingingId === p.id ? 'pinging…' : 'ping'}
                        </button>
                        <button
                          onClick={() => { notification('warning'); setConfirmDeleteId(p.id) }}
                          style={{ ...btnStyle, color: TOAST_FAIL_COLOR }}
                        >
                          delete
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
                    + new provider
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
