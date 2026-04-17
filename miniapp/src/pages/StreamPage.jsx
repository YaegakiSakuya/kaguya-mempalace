import { useState, useEffect, useCallback } from 'react'
import useTelegram from '../hooks/useTelegram'
import useApi from '../hooks/useApi'
import LiveProcess from '../components/stream/LiveProcess'
import HistoryList from '../components/stream/HistoryList'

export default function StreamPage({ sse }) {
  const { initData } = useTelegram()
  const { get, loading } = useApi(initData)
  const [history, setHistory] = useState([])

  const fetchHistory = useCallback(async () => {
    const data = await get('/miniapp/history?limit=20')
    if (data?.items) setHistory(data.items)
  }, [get])

  // Refresh history when SSE receives a done event
  const { status, events, stats, connected } = sse
  useEffect(() => {
    if (status !== 'done') return

    const timer = setTimeout(() => {
      fetchHistory()
    }, 1200)

    return () => clearTimeout(timer)
  }, [status, fetchHistory])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  return (
    <div className="px-4 flex flex-col gap-4 pb-6">
      <LiveProcess status={status} events={events} stats={stats} connected={connected} />
      <HistoryList items={history} onRefresh={fetchHistory} loading={loading} />
    </div>
  )
}
