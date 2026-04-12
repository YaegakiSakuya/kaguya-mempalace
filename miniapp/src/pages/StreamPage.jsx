import { useState, useEffect, useCallback } from 'react'
import useTelegram from '../hooks/useTelegram'
import useSSE from '../hooks/useSSE'
import useApi from '../hooks/useApi'
import LiveProcess from '../components/stream/LiveProcess'
import HistoryList from '../components/stream/HistoryList'

export default function StreamPage() {
  const { initData } = useTelegram()
  const { get, loading } = useApi(initData)
  const [history, setHistory] = useState([])

  const fetchHistory = useCallback(async () => {
    const data = await get('/miniapp/history?limit=20')
    if (data) setHistory(data)
  }, [get])

  const { status, events, stats, connected } = useSSE(initData, fetchHistory)

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  return (
    <div className="px-4 flex flex-col gap-3 pb-6">
      <LiveProcess status={status} events={events} stats={stats} connected={connected} />
      <HistoryList items={history} onRefresh={fetchHistory} loading={loading} />
    </div>
  )
}
