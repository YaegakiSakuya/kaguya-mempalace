// ==========================================================
// kaguya-mempalace — mock data (client-side only)
// Structure mirrors the real schema but inline/hand-authored.
// ==========================================================

window.KAGUYA = (function () {
  const wings = [
    { id: 'kaguya',   name: 'かぐや',         jp: 'kaguya',          code: 'W-01', rooms: ['diary','rituals','letters','origins'],       drawers: 25, hot: true },
    { id: 'daily',    name: 'daily',           jp: '日々',            code: 'W-02', rooms: ['daily-life'],                                  drawers: 14, hot: true },
    { id: 'sex_body', name: 'sex & body',      jp: '身体',            code: 'W-03', rooms: ['fetish-museum','kama-sutra-archive'],          drawers: 11 },
    { id: 'writing',  name: 'writing',         jp: '著作',            code: 'W-04', rooms: ['神楽零','丛云拾遗记','蚩灵'],                 drawers: 8 },
    { id: 'code',     name: 'code',            jp: '工房',            code: 'W-05', rooms: ['kaguya-gateway','claude-stats-extension'],    drawers: 7 },
    { id: 'reality',  name: 'serious reality', jp: '現実',            code: 'W-06', rooms: ['legal','health','finance'],                    drawers: 4 },
    { id: 'thought',  name: 'thought',         jp: '思索',            code: 'W-07', rooms: ['爱与死-朝向','boundary-trust','kaguya-identity'], drawers: 4 },
    { id: 'roleplay', name: 'roleplay',        jp: '演戯',            code: 'W-08', rooms: ['personae','scenes'],                            drawers: 2 },
    { id: 'conflict', name: 'conflict',        jp: '葛藤',            code: 'W-09', rooms: [], drawers: 1, sparse: true },
    { id: 'games',    name: 'games',           jp: '遊戯',            code: 'W-10', rooms: ['VA-11 Hall-A'], drawers: 1, sparse: true },
    { id: 'music',    name: 'music',           jp: '音楽',            code: 'W-11', rooms: [], drawers: 1, sparse: true },
    { id: 'reading',  name: 'reading',         jp: '読書',            code: 'W-12', rooms: ['Karamazov'], drawers: 1, sparse: true },
    { id: 'screen',   name: 'screen',          jp: '映像',            code: 'W-13', rooms: ['Twin Peaks'], drawers: 1, sparse: true },
    { id: 'chats',    name: 'chats',           jp: '対話',            code: 'SYS',  rooms: [], drawers: 61, archive: true },
  ];

  const nav = [
    { group: 'Palace',      items: [
      { id: 'overview',  label: 'Overview',        href: 'index.html',          count: '—' },
      { id: 'wings',     label: 'Wings',           href: 'wings.html',          count: '13' },
      { id: 'graph',     label: 'Knowledge Graph', href: 'graph.html',          count: '382' },
      { id: 'diary',     label: 'Diary',           href: 'diary.html',          count: '94' },
      { id: 'search',    label: 'Search',          href: 'search.html'          },
    ]},
    { group: 'Connections', items: [
      { id: 'tunnels',   label: 'Tunnels',         href: 'tunnels.html',        count: '17' },
      { id: 'llm',       label: 'LLM Config',      href: 'llm.html'             },
    ]},
  ];

  const palaceMeta = { name: 'kaguya.main', since: '2026.04.17', sync: '14s ago' };

  return { wings, nav, palaceMeta };
})();
