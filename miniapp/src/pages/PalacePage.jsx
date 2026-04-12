import { useState, useEffect } from 'react'
import useTelegram from '../hooks/useTelegram'
import useApi from '../hooks/useApi'
import Overview from '../components/palace/Overview'
import WingBrowser from '../components/palace/WingBrowser'
import DiaryList from '../components/palace/DiaryList'

export default function PalacePage() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)

  const [overview, setOverview] = useState(null)
  const [wings, setWings] = useState([])
  const [diary, setDiary] = useState([])

  useEffect(() => {
    const load = async () => {
      const [ovRes, wRes, dRes] = await Promise.all([
        get('/miniapp/palace/overview'),
        get('/miniapp/palace/wings'),
        get('/miniapp/palace/diary?limit=5'),
      ])
      if (ovRes) setOverview(ovRes)
      if (wRes?.wings) setWings(wRes.wings)
      else if (Array.isArray(wRes)) setWings(wRes)
      if (dRes?.entries) setDiary(dRes.entries)
      else if (Array.isArray(dRes)) setDiary(dRes)
    }
    load()
  }, [get])

  return (
    <div className="px-4 pb-6 space-y-4">
      <Overview data={overview} />
      <WingBrowser wings={wings} />
      <DiaryList entries={diary} />
    </div>
  )
}
