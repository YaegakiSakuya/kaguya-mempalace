import { useState, useCallback, useRef } from 'react'

export default function useApi(initData) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const initDataRef = useRef(initData)
  initDataRef.current = initData

  const baseUrl = import.meta.env.VITE_API_BASE || ''

  const get = useCallback(async (path) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${baseUrl}${path}`, {
        headers: { 'X-Telegram-Init-Data': initDataRef.current }
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return await res.json()
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setLoading(false)
    }
  }, [baseUrl])

  const callWithBody = useCallback(async (method, path, body) => {
    setLoading(true)
    setError(null)
    try {
      const opts = {
        method,
        headers: { 'X-Telegram-Init-Data': initDataRef.current },
      }
      if (body !== undefined) {
        opts.headers['Content-Type'] = 'application/json'
        opts.body = JSON.stringify(body)
      }
      let res
      try {
        res = await fetch(`${baseUrl}${path}`, opts)
      } catch (netErr) {
        const e = new Error('network error')
        e.networkError = true
        throw e
      }
      const text = await res.text()
      let data = null
      if (text) {
        try { data = JSON.parse(text) } catch { data = null }
      }
      if (!res.ok) {
        const msg = (data && data.error) || `HTTP ${res.status}`
        const e = new Error(msg)
        e.status = res.status
        e.data = data
        throw e
      }
      return data
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [baseUrl])

  const post = useCallback((path, body) => callWithBody('POST', path, body), [callWithBody])
  const patch = useCallback((path, body) => callWithBody('PATCH', path, body), [callWithBody])
  const del = useCallback((path) => callWithBody('DELETE', path), [callWithBody])

  return { get, post, patch, del, loading, error }
}
