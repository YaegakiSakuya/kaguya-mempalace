import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import BottomSheet from '../components/BottomSheet';
import PageShell from '../components/PageShell';
import Toast from '../components/Toast';
import { useApi } from '../hooks/useApi';
import { useHaptic } from '../hooks/useHaptic';
import { useAppContext } from '../context/AppContext';
import { CONFIG_KEYS, configRowsToMap, pickMappedValues } from '../utils/config';
import CurrentProcess from '../components/message-panel/CurrentProcess';
import HistoryList from '../components/message-panel/HistoryList';

export default function Home() {
  const navigate = useNavigate();
  const { get, loading, error } = useApi();
  const { initData, setConfigSnapshot, sse, historyVersion } = useAppContext();
  const haptic = useHaptic();
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [data, setData] = useState({
    configMap: {},
    protocols: [],
    memoryStats: null,
    summaryTotal: 0,
    mode: null,
  });

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await get('/cot/history?page=1&limit=20');
      setHistory(res?.items || []);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [get]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory, historyVersion]);

  useEffect(() => {
    if (!menuOpen) return;
    const load = async () => {
      try {
        const [configRes, protocolRes, memoryRes, summaryRes, modeRes] = await Promise.all([
          get('/config'),
          get('/protocols'),
          get('/memories/stats'),
          get('/summaries?page=1&limit=1'),
          get('/mode/current'),
        ]);
        const configMap = configRowsToMap(configRes.configs || []);
        setConfigSnapshot(configMap);
        setData({
          configMap,
          protocols: protocolRes.groups || [],
          memoryStats: memoryRes,
          summaryTotal: summaryRes?.pagination?.total || 0,
          mode: modeRes,
        });
      } catch {
        setToast('管理数据加载失败');
      }
    };
    load();
  }, [menuOpen, get, setConfigSnapshot]);

  const activeProtocolCount = useMemo(
    () => data.protocols.reduce((sum, group) => sum + (group.protocols || []).filter((item) => item.is_active).length, 0),
    [data.protocols],
  );

  const profileView = pickMappedValues(data.configMap, CONFIG_KEYS.profile);
  const assistantView = pickMappedValues(data.configMap, CONFIG_KEYS.assistant);

  return (
    <PageShell>
      <div className="mx-auto flex min-h-screen w-full max-w-2xl flex-col p-6">

        {/* === 居中心跳顶栏 === */}
        <div className="relative mb-6 flex items-center justify-between">
          {/* 左翼：菜单按钮 */}
          <button
            type="button"
            className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-surface text-primary shadow-button transition-colors hover:text-accent cursor-pointer"
            onClick={() => { haptic.medium(); setMenuOpen(true); }}
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"></path></svg>
          </button>

          {/* 中心：心电图生命线 */}
          <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center w-[120px] h-[24px]">
            <svg width="100" height="24" viewBox="0 0 100 24" fill="none">
              <defs>
                <linearGradient id="ecgFade" x1="0" y1="0" x2="100" y2="0" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0" />
                  <stop offset="15%" stopColor="var(--color-accent)" stopOpacity="1" />
                  <stop offset="85%" stopColor="var(--color-accent)" stopOpacity="1" />
                  <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
                </linearGradient>
                <filter id="ecgGlow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              {sse.canConnect && sse.connected ? (
                <>
                  {/* 在线：7重心率变异流体脉冲 */}
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite 0s'}} d="M 5 12 L 35 12 L 38 9 L 41 12 L 44 12 L 47 16 L 50 3 L 53 21 L 56 12 L 62 12 L 65 9 L 68 12 L 95 12" />
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite -18s'}} d="M 5 12 L 35 12 L 38 9 L 41 12 L 44 12 L 47 15 L 50 2 L 53 23 L 56 12 L 62 12 L 65 9 L 68 12 L 95 12" />
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite -15s'}} d="M 5 12 L 35 12 L 38 9 L 41 12 L 43 12 L 46 16 L 50 3 L 54 21 L 57 12 L 62 12 L 65 9 L 68 12 L 95 12" />
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite -12s'}} d="M 5 12 L 35 12 L 38 9 L 41 12 L 44 12 L 47 16 L 50 3 L 53 21 L 56 12 L 62 12 L 65 7 L 68 12 L 95 12" />
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite -9s'}} d="M 5 12 L 33 12 L 35 10 L 37 12 L 39 10 L 41 12 L 44 12 L 47 16 L 50 3 L 53 21 L 56 12 L 62 12 L 65 9 L 68 12 L 95 12" />
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite -6s'}} d="M 5 12 L 35 12 L 38 10 L 41 12 L 44 12 L 47 14 L 50 5 L 53 19 L 56 12 L 62 12 L 65 10 L 68 12 L 95 12" />
                  <path style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',strokeDasharray:160,opacity:0,filter:'url(#ecgGlow)',animation:'ecg-flow-7 21s infinite -3s'}} d="M 5 12 L 30 12 L 35 11 L 38 8 L 41 11 L 44 11 L 47 16 L 50 3 L 53 21 L 56 13 L 62 13 L 65 10 L 68 12 L 95 12" />
                </>
              ) : (
                /* 离线：蛰伏微颤 */
                <path
                  style={{stroke:'url(#ecgFade)',strokeWidth:'1.5px',strokeLinecap:'round',strokeLinejoin:'round',animation:'offline-energy-flicker 1.5s ease-in-out infinite',filter:'url(#ecgGlow)'}}
                  d="M 5 12 L 95 12"
                >
                  <animate
                    attributeName="d"
                    dur="0.4s"
                    repeatCount="indefinite"
                    calcMode="discrete"
                    values="M 5 12 L 12 11.5 L 18 12.5 L 25 12 L 32 11 L 38 13 L 45 12 L 52 11.5 L 58 12.5 L 65 12 L 72 11.5 L 78 12.5 L 85 12 L 95 12;M 5 12 L 14 12.5 L 20 11 L 28 12.5 L 35 11.5 L 42 12 L 48 13 L 55 11 L 62 12.5 L 68 11.5 L 75 12 L 82 13 L 88 11 L 95 12;M 5 12 L 10 11 L 16 13 L 24 11.5 L 30 12.5 L 38 11 L 44 12 L 50 12.5 L 56 11.5 L 64 13 L 70 11 L 78 12.5 L 84 11.5 L 95 12;M 5 12 L 15 12.5 L 22 11.5 L 29 12 L 36 13 L 40 11 L 47 12.5 L 53 11.5 L 60 12 L 66 11 L 74 13 L 80 11.5 L 86 12.5 L 95 12;M 5 12 L 12 11.5 L 18 12.5 L 25 12 L 32 11 L 38 13 L 45 12 L 52 11.5 L 58 12.5 L 65 12 L 72 11.5 L 78 12.5 L 85 12 L 95 12"
                  />
                </path>
              )}
            </svg>
          </div>

          {/* 右翼：刷新按钮 */}
          <button
            type="button"
            className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-surface text-secondary shadow-button transition-colors hover:text-primary active:scale-95 cursor-pointer"
            onClick={() => { haptic.light(); loadHistory(); }}
          >
            {historyLoading ? (
               <span className="h-4 w-4 animate-spin rounded-full border-2 border-secondary border-t-transparent"></span>
            ) : (
               <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
            )}
          </button>
        </div>

        {sse.error && sse.canConnect ? (
          <p className="mb-4 rounded-card bg-red-50/80 p-3 text-xs text-danger">{sse.error}</p>
        ) : null}

        {/* 实时处理区 — idle 时完全隐藏 */}
        <CurrentProcess
          status={sse.status}
          processingText={sse.processingText}
          thinkingText={sse.thinkingText}
          replyText={sse.replyText}
          thinkingMs={sse.thinkingMs}
          replyingMs={sse.replyingMs}
          stats={sse.stats}
        />

        {/* 历史记录 */}
        <div className="flex-1">
          <HistoryList items={history} loading={historyLoading} onRefresh={loadHistory} />
        </div>

        {/* 管理菜单抽屉 — 无标题，直接展示卡片 */}
        <BottomSheet isOpen={menuOpen} onClose={() => { haptic.light(); setMenuOpen(false); }}>
          <div className="grid grid-cols-2 gap-4">
            <MenuCard
              title="Profile"
              subtitle={profileView.nickname ? profileView.nickname : 'Unset'}
              onClick={() => { haptic.tick(); setMenuOpen(false); navigate('/profile'); }}
            />
            <MenuCard
              title="World Book"
              subtitle={`${activeProtocolCount} Active Rules`}
              onClick={() => { haptic.tick(); setMenuOpen(false); navigate('/worldview'); }}
            />
            <MenuCard
              title="Memory Core"
              subtitle={`${data.memoryStats?.active ?? 0} Nodes`}
              onClick={() => { haptic.tick(); setMenuOpen(false); navigate('/memory'); }}
            />
            <MenuCard
              title="Persona"
              subtitle={assistantView.name || 'Assistant'}
              onClick={() => { haptic.tick(); setMenuOpen(false); navigate('/assistant'); }}
            />
            <MenuCard
              title="Settings"
              subtitle={data.mode?.mode === 'long' ? 'Extended' : 'Standard'}
              onClick={() => { haptic.tick(); setMenuOpen(false); navigate('/settings'); }}
            />
            <MenuCard
              title="Inspection"
              subtitle="TOPICS · JOBS"
              onClick={() => { haptic.tick(); setMenuOpen(false); navigate('/inspection'); }}
            />
          </div>
        </BottomSheet>

        <Toast type="error" message={toast || error} onClose={() => setToast('')} />
      </div>
    </PageShell>
  );
}

function MenuCard({ title, subtitle, onClick }) {
  const isPrimary = title === 'Memory Core' || title === 'Profile';

  return (
    <div
      onClick={onClick}
      className="group relative flex aspect-square cursor-pointer flex-col justify-between overflow-hidden rounded-card bg-surface p-5 shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-sheet border border-white"
    >
      <div className={`flex h-10 w-10 items-center justify-center rounded-2xl transition-transform duration-300 group-hover:scale-110 ${isPrimary ? 'bg-[#FFF6F3] text-accent' : 'bg-slate-50 text-secondary'}`}>
         <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5"></path></svg>
      </div>
      <div>
        <p className="font-serif text-[17px] font-medium text-primary">{title}</p>
        {subtitle ? (
          <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-secondary line-clamp-1">
            {subtitle}
          </p>
        ) : null}
      </div>
    </div>
  );
}
