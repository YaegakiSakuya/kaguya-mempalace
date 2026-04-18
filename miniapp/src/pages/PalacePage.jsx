import { useState, useEffect } from 'react'
import useTelegram from '../hooks/useTelegram'
import useApi from '../hooks/useApi'
import LLMConfigCard from '../components/palace/LLMConfigCard'
import Overview from '../components/palace/Overview'
import WingBrowser from '../components/palace/WingBrowser'
import AllRoomsFlat from '../components/palace/AllRoomsFlat'
import RecentDrawers from '../components/palace/RecentDrawers'
import KGSummary from '../components/palace/KGSummary'
import DiaryList from '../components/palace/DiaryList'

function DrillDown({ selected, wings }) {
  let content = null
  if (selected === 'wings') content = <WingBrowser wings={wings} />
  else if (selected === 'rooms') content = <AllRoomsFlat wings={wings} />
  else if (selected === 'drawers') content = <RecentDrawers />
  else if (selected === 'kg_entities') content = <KGSummary initialTab="entities" />
  else if (selected === 'kg_triples') content = <KGSummary initialTab="triples" />

  return (
    <div
      key={selected}
      style={{
        animation: 'drilldown-fade 200ms ease',
      }}
    >
      {content}
    </div>
  )
}

export default function PalacePage() {
  const { initData } = useTelegram()
  const { get } = useApi(initData)

  const [overview, setOverview] = useState(null)
  const [wings, setWings] = useState([])
  const [diary, setDiary] = useState([])
  const [selected, setSelected] = useState('wings')

  useEffect(() => {
    const load = async () => {
      const [ovRes, wRes, dRes] = await Promise.all([
        get('/miniapp/palace/overview'),
        get('/miniapp/palace/wings'),
        get('/miniapp/palace/diary?limit=5'),
      ])
      if (ovRes) setOverview(ovRes)
      if (wRes?.wings) {
        setWings(Array.isArray(wRes.wings) ? wRes.wings : Object.keys(wRes.wings))
      } else if (Array.isArray(wRes)) setWings(wRes)
      if (Array.isArray(dRes)) setDiary(dRes)
      else if (dRes?.entries) setDiary(dRes.entries)
      else if (dRes?.diary) setDiary(Array.isArray(dRes.diary) ? dRes.diary : [])
      else if (dRes && typeof dRes === 'object') setDiary([dRes])
    }
    load()
  }, [get])

  return (
    <div className="px-4 pb-6 space-y-6">
      <style>{`
        @keyframes drilldown-fade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
      <LLMConfigCard />
      <Overview
        data={overview}
        selected={selected}
        onSelect={setSelected}
      />
      <DrillDown selected={selected} wings={wings} />
      <DiaryList entries={diary} />
    </div>
  )
}
