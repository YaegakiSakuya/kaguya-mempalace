import { useState, useEffect, useRef, useCallback } from 'react'

export default function useSSE(initData, onDone) {
  const [status, setStatus] = useState('idle')
  const [events, setEvents] = useState([])
  const [stats, setStats] = useState(null)
  const [connected, setConnected] = useState(false)
  const esRef = useRef(null)
  const resetTimerRef = useRef(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  const addEvent = useCallback((type, data) => {
    setEvents(prev => [...prev, { type, data, timestamp: Date.now() }])
  }, [])

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_BASE || ''
    const fullUrl = `${apiBase}/miniapp/stream?initData=${encodeURIComponent(initData)}`
    const es = new EventSource(fullUrl)
    esRef.current = es

    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)

    es.addEventListener('processing', (e) => {
      const data = JSON.parse(e.data)
      setStatus(prev => {
        if (prev === 'idle' || prev === 'done') {
          setEvents([])
          if (resetTimerRef.current) {
            clearTimeout(resetTimerRef.current)
            resetTimerRef.current = null
          }
        }
        return 'processing'
      })
      addEvent('processing', data)
    })

    es.addEventListener('tool_call', (e) => {
      const data = JSON.parse(e.data)
      setStatus('tool_call')
      addEvent('tool_call', data)
    })

    es.addEventListener('tool_done', (e) => {
      const data = JSON.parse(e.data)
      addEvent('tool_done', data)
    })

    es.addEventListener('done', (e) => {
      const data = JSON.parse(e.data)
      setStatus('done')
      setStats(data)
      addEvent('done', data)
      onDoneRef.current?.()

      resetTimerRef.current = setTimeout(() => {
        setStatus('idle')
        setEvents([])
        resetTimerRef.current = null
      }, 3000)
    })

    return () => {
      es.close()
      esRef.current = null
      if (resetTimerRef.current) {
        clearTimeout(resetTimerRef.current)
      }
    }
  }, [initData, addEvent])

  return { status, events, stats, connected }
}
