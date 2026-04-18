import { useState, useEffect } from 'react'
import useTelegram from '../hooks/useTelegram'
import useApi from '../hooks/useApi'
import LLMConfigCard from '../components/palace/LLMConfigCard'
import PulseSection from '../components/palace/PulseSection'
import StructureSection from '../components/palace/StructureSection'
import MindSection from '../components/palace/MindSection'

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
      if (Array.isArray(wRes?.wings)) {
        setWings(wRes.wings)
      } else if (wRes?.wings) {
        setWings(Object.keys(wRes.wings))
      } else if (Array.isArray(wRes)) {
        setWings(wRes)
      }
      if (Array.isArray(dRes)) setDiary(dRes)
      else if (dRes?.entries) setDiary(dRes.entries)
      else if (dRes?.diary) setDiary(Array.isArray(dRes.diary) ? dRes.diary : [])
      else if (dRes && typeof dRes === 'object') setDiary([dRes])
    }
    load()
  }, [get])

  return (
    <div className="px-4 pb-6 space-y-8">
      <LLMConfigCard />
      <PulseSection overview={overview} />
      <StructureSection wings={wings} />
      <MindSection diary={diary} />
    </div>
  )
}
