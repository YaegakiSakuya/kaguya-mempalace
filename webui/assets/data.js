// ==========================================================
// kaguya-mempalace — mock data (client-side only)
// Structure mirrors the real schema but inline/hand-authored.
// ==========================================================

window.KAGUYA = (function () {
  const wings = [
    { id: 'US',         name: 'us',         jp: '吾々', code: 'W-01', rooms: [], drawers: 0 },
    { id: 'CREATIVE',   name: 'creative',   jp: '創作', code: 'W-02', rooms: [], drawers: 0 },
    { id: 'PHILOSOPHY', name: 'philosophy', jp: '思索', code: 'W-03', rooms: [], drawers: 0 },
    { id: 'BODY',       name: 'body',       jp: '身体', code: 'W-04', rooms: [], drawers: 0 },
    { id: 'DAILY',      name: 'daily',      jp: '日々', code: 'W-05', rooms: [], drawers: 0 },
    { id: 'WORK',       name: 'work',       jp: '工房', code: 'W-06', rooms: [], drawers: 0 },
    { id: 'REFLECTION', name: 'reflection', jp: '内省', code: 'W-07', rooms: [], drawers: 0 },
  ];

  const nav = [
    { group: 'Palace',      items: [
      { id: 'overview',  label: 'Overview',        href: 'index.html',          count: '—' },
      { id: 'wings',     label: 'Wings',           href: 'wings.html',          count: '—' },
      { id: 'graph',     label: 'Knowledge Graph', href: 'graph.html',          count: '—' },
      { id: 'diary',     label: 'Diary',           href: 'diary.html',          count: '—' },
      { id: 'search',    label: 'Search',          href: 'search.html'          },
    ]},
    { group: 'Connections', items: [
      { id: 'tunnels',   label: 'Tunnels',         href: 'tunnels.html',        count: '—' },
      { id: 'llm',       label: 'LLM Config',      href: 'llm.html'             },
    ]},
  ];

  const palaceMeta = { name: 'kaguya.main', since: '2026.04.17', sync: '—' };

  return { wings, nav, palaceMeta };
})();
