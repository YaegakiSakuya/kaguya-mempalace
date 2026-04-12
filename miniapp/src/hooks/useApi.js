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

  return { get, loading, error }
}
