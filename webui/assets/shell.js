// ==========================================================
// kaguya-mempalace — shared shell (nav, topbar, small FX)
// Each page: set <body data-page="overview|wings|graph|...">
// and include an empty <div id="app-shell"></div> at top.
// ==========================================================

(function () {
  const page = document.body.dataset.page || 'overview';
  const crumbs = (document.body.dataset.crumbs || 'Palace / Overview').split('/').map(s => s.trim());
  const K = window.KAGUYA;

  // ---------- greeting (shichen-based, Asia/Shanghai) ----------
  const GREETINGS = {
    linxiao: [     // 临晓 03:00-06:00
      '夜色将褪，你还在。',
      '临晓了，朔夜。',
      '这个点进来的人，心里都有未写完的句子。',
      '宫殿陪你到天明。',
    ],
    qingchen: [    // 清晨 06:00-09:00
      '晨光透进来了。',
      '昨夜的存档在这里，你翻翻。',
      '新一天，宫殿开着。',
      '起得早，愿有好事发生。',
    ],
    wuqian: [      // 午前 09:00-11:00
      '午前的时间是给正事的。',
      '宫殿整晚没合眼，等你。',
      '你来了，可以动笔了。',
    ],
    zhengwu: [     // 正午 11:00-13:00
      '日头正顶。',
      '记得吃饭，朔夜。',
      '让宫殿歇一会儿。',
    ],
    rixie: [       // 日斜 13:00-16:00
      '午后的光最适合慢读。',
      '日影偏西。',
      '这个时辰适合做不紧不慢的事。',
    ],
    bomu: [        // 薄暮 16:00-19:00
      '黄昏了。',
      '落日把宫殿染成旧金。',
      '薄暮时分，把今天收一收。',
    ],
    yeli: [        // 夜里 19:00-23:00
      '夜里好。',
      '灯亮起来了，一起开工。',
      '宫殿在这个时辰最像它自己。',
      '我在这里，你慢慢来。',
    ],
    yeban: [       // 夜半 23:00-03:00
      '又到这个时辰。',
      '夜半了，朔夜。',
      '月上中天。',
      '我知道你这会儿还不睡。',
    ],
  };

  function shanghaiHour() {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Shanghai',
      hour: 'numeric',
      hour12: false,
    }).formatToParts(new Date());
    const hourPart = parts.find(p => p.type === 'hour');
    const h = parseInt(hourPart && hourPart.value, 10);
    // Intl may return "24" at midnight on some engines; normalize to 0.
    return isNaN(h) ? 0 : (h % 24);
  }

  function pickBucket(h) {
    if (h >= 3 && h < 6)   return 'linxiao';
    if (h >= 6 && h < 9)   return 'qingchen';
    if (h >= 9 && h < 11)  return 'wuqian';
    if (h >= 11 && h < 13) return 'zhengwu';
    if (h >= 13 && h < 16) return 'rixie';
    if (h >= 16 && h < 19) return 'bomu';
    if (h >= 19 && h < 23) return 'yeli';
    return 'yeban'; // h >= 23 or h < 3
  }

  function greeting() {
    const arr = GREETINGS[pickBucket(shanghaiHour())];
    return arr[Math.floor(Math.random() * arr.length)];
  }

  window.KaguyaShell = window.KaguyaShell || {};
  window.KaguyaShell.greeting = greeting;

  // ---------- icon set (1.25px line) ----------
  const ICONS = {
    overview: '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><rect x="1.5" y="1.5" width="4.5" height="4.5"/><rect x="8" y="1.5" width="4.5" height="4.5"/><rect x="1.5" y="8" width="4.5" height="4.5"/><rect x="8" y="8" width="4.5" height="4.5"/></svg>',
    wings:    '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><path d="M1.5 3h11M1.5 7h11M1.5 11h11"/><path d="M4.5 3v8M9.5 3v8"/></svg>',
    graph:    '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="3.5" cy="3.5" r="1.6"/><circle cx="10.5" cy="3.5" r="1.6"/><circle cx="7" cy="10.5" r="1.6"/><path d="M4.7 4.4l1.6 4.6M9.3 4.4l-1.6 4.6M5 3.5h4"/></svg>',
    diary:    '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><path d="M3 1.5h6.5L11.5 3.5v9H3z"/><path d="M4.5 5.5h5M4.5 7.5h5M4.5 9.5h3"/></svg>',
    search:   '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="6" cy="6" r="3.6"/><path d="M8.8 8.8l3.4 3.4"/></svg>',
    tunnels:  '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><path d="M1.5 7a3 3 0 013-3h2"/><path d="M12.5 7a3 3 0 01-3 3h-2"/><path d="M5 7h4" stroke-dasharray="1.5 1.2"/></svg>',
    llm:      '<svg class="nav-icon" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="7" cy="7" r="2"/><path d="M7 1.5v1.8M7 10.7v1.8M1.5 7h1.8M10.7 7h1.8M3.2 3.2l1.3 1.3M9.5 9.5l1.3 1.3M3.2 10.8l1.3-1.3M9.5 4.5l1.3-1.3"/></svg>',
  };

  // ---------- build NAV ----------
  function renderNav() {
    let html = '';
    html += `
      <aside class="nav">
        <a class="brand" href="index.html">
          <div class="brand-mark"></div>
          <div class="brand-name">
            かぐや 記憶宮殿
            <span class="sub">KAGUYA · MEMPALACE</span>
          </div>
        </a>`;
    K.nav.forEach(group => {
      html += `<div class="nav-section-label">${group.group}</div><ul class="nav-list">`;
      group.items.forEach(it => {
        const active = it.id === page ? ' active' : '';
        html += `
          <a class="nav-item${active}" href="${it.href}">
            ${ICONS[it.id] || ''}
            ${it.label}
            ${it.count !== undefined ? `<span class="nav-count" data-count-key="${it.id}">${it.count}</span>` : ''}
          </a>`;
      });
      html += `</ul>`;
    });
    html += `
        <div class="nav-footer">
          <div class="palace-meta">
            <div><span class="pulse"></span><span class="v">${K.palaceMeta.name}</span></div>
            <div style="margin-top:4px;">SINCE &nbsp; <span class="v">${K.palaceMeta.since}</span></div>
            <div>SYNC &nbsp;&nbsp; <span class="v">${K.palaceMeta.sync}</span></div>
          </div>
        </div>
      </aside>`;
    return html;
  }

  // ---------- build TOPBAR ----------
  function renderTopbar() {
    const crumbsHtml = crumbs.map((c, i) => {
      const cur = i === crumbs.length - 1;
      return cur ? `<span class="cur">${c}</span>` : `<span>${c}</span><span>/</span>`;
    }).join(' ');
    return `
      <div class="topbar">
        <div class="breadcrumb">${crumbsHtml}</div>
        <div class="topbar-spacer"></div>
        <div class="search-hint" onclick="window.__openCmdK && window.__openCmdK()">
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="6" cy="6" r="3.6"/><path d="M8.8 8.8l3.4 3.4"/></svg>
          搜索 drawer · entity · diary …
          <span class="kbd">⌘ K</span>
        </div>
        <div class="clock"><span class="time-digit" id="__clock">23:47 JST</span></div>
        <div class="user-chip">
          <div class="user-avatar">朔</div>
          朔夜
        </div>
      </div>`;
  }

  // ---------- mount ----------
  function mount() {
    const shellEl = document.getElementById('app-shell');
    const mainEl  = document.getElementById('main-content');
    if (!shellEl || !mainEl) return;

    shellEl.innerHTML = renderNav();
    const main = document.createElement('main');
    main.className = 'main';
    main.innerHTML = renderTopbar();
    // move existing content into main
    const contentWrapper = document.createElement('div');
    while (mainEl.firstChild) contentWrapper.appendChild(mainEl.firstChild);
    mainEl.replaceWith(main);
    main.appendChild(contentWrapper);
  }

  // ---------- clock ----------
  function startClock() {
    const el = document.getElementById('__clock');
    if (!el) return;
    const fmt = d => String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0') + ' JST';
    el.textContent = fmt(new Date());
    setInterval(() => {
      const next = fmt(new Date());
      if (next === el.textContent) return;
      el.style.opacity = '0';
      setTimeout(() => { el.textContent = next; el.style.opacity = '1'; }, 150);
    }, 1000);
  }

  // ---------- nav counts (live, via API) ----------
  // Targets <span class="nav-count" data-count-key="X">...</span>
  // Keys handled: wings, graph, diary, tunnels. Each key lives in its own
  // try/catch so a single endpoint failure doesn't block the others, and
  // the pre-rendered value stays as a fallback.
  function setNavCount(key, value) {
    if (value === undefined || value === null) return;
    const s = (typeof value === 'number' && isFinite(value))
      ? value.toLocaleString('en-US')
      : String(value);
    document.querySelectorAll('.nav-count[data-count-key="' + key + '"]').forEach(el => {
      el.textContent = s;
    });
  }

  async function initNavCounts() {
    if (!window.KaguyaAPI) return;
    const api = window.KaguyaAPI;

    // Wings: data.js is the architecture source of truth, so count locally.
    try {
      const n = (K && Array.isArray(K.wings)) ? K.wings.length : null;
      if (n !== null) setNavCount('wings', n);
    } catch (_) { /* leave placeholder */ }

    // KG entities from /api/kg/stats
    try {
      const s = await api.getKgStats();
      const n = s && (s.entities != null ? s.entities : s.entity_count);
      if (n != null) setNavCount('graph', n);
    } catch (_) { /* leave placeholder */ }

    // Diary entries — API returns {entries: [...], count: N} or similar
    try {
      const d = await api.getDiary();
      let n = null;
      if (d && Array.isArray(d.entries)) n = d.entries.length;
      else if (d && typeof d.count === 'number') n = d.count;
      else if (Array.isArray(d)) n = d.length;
      if (n != null) setNavCount('diary', n);
    } catch (_) { /* leave placeholder */ }

    // Tunnels — /api/graph/tunnels/list returns array or {tunnels: [...]}
    try {
      const t = await api.getAllTunnels();
      let n = null;
      if (Array.isArray(t)) n = t.length;
      else if (t && Array.isArray(t.tunnels)) n = t.tunnels.length;
      if (n != null) setNavCount('tunnels', n);
    } catch (_) { /* leave placeholder */ }
  }

  window.KaguyaShell.initNavCounts = initNavCounts;

  // ---------- crawl counter for any .crawl-num element ----------
  function crawlCounters() {
    document.querySelectorAll('.crawl-num').forEach(el => {
      const target = parseInt((el.textContent || '').replace(/[^0-9-]/g,''), 10);
      if (isNaN(target)) return;
      const start = Math.max(0, Math.floor(target * 0.78));
      const t0 = performance.now();
      const duration = 600;
      function frame(t) {
        const p = Math.min(1, (t - t0) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        const v = Math.round(start + (target - start) * eased);
        el.textContent = v.toLocaleString();
        if (p < 1) requestAnimationFrame(frame);
        else el.textContent = target.toLocaleString();
      }
      el.textContent = start.toLocaleString();
      requestAnimationFrame(frame);
    });
  }

  // ---------- command palette (⌘K) ----------
  const CMDK_INDEX = [
    // navigation
    { kind: 'go',      label: 'Overview',            path: 'palace / overview',   href: 'index.html',   meta: 'G O' },
    { kind: 'go',      label: 'Wings',               path: 'palace / wings',      href: 'wings.html',   meta: 'G W' },
    { kind: 'go',      label: 'Knowledge Graph',     path: 'palace / graph',      href: 'graph.html',   meta: 'G G' },
    { kind: 'go',      label: 'Diary',               path: 'palace / diary',      href: 'diary.html',   meta: 'G D' },
    { kind: 'go',      label: 'Search',              path: 'palace / search',     href: 'search.html',  meta: 'G S' },
    { kind: 'go',      label: 'Tunnels',             path: 'palace / tunnels',    href: 'tunnels.html', meta: 'G T' },
    { kind: 'go',      label: 'LLM Config',          path: 'palace / llm',        href: 'llm.html',     meta: 'G L' },
    // drawers
    { kind: 'drawer',  label: 'transformer-scaling-laws',   path: 'study / papers',         href: 'wings.html',   meta: '12 min' },
    { kind: 'drawer',  label: 'boundary-trust',             path: 'thought',                 href: 'wings.html',   meta: '1 day' },
    { kind: 'drawer',  label: 'glaze-ash-ratios',           path: 'craft / pottery',         href: 'wings.html',   meta: '5 h' },
    { kind: 'drawer',  label: '神楽零 · §III-草稿',          path: 'writing / 神楽零',         href: 'wings.html',   meta: '2 days' },
    { kind: 'drawer',  label: 'kaguya-identity',            path: 'thought',                 href: 'wings.html',   meta: 'today' },
    { kind: 'drawer',  label: 'mempalace-v2 · web-dashboard', path: 'projects',              href: 'wings.html',   meta: '8 h' },
    // entities
    { kind: 'entity',  label: 'Anna Lin',                   path: 'entity · person',         href: 'graph.html',   meta: '22 triples' },
    { kind: 'entity',  label: 'かぐや',                       path: 'entity · persona',        href: 'graph.html',   meta: '47 triples' },
    { kind: 'entity',  label: 'boundary-trust',             path: 'entity · concept',        href: 'graph.html',   meta: '14 triples' },
    { kind: 'entity',  label: 'Chinchilla-paper',           path: 'entity · artifact',       href: 'graph.html',   meta: '9 triples' },
    // diary
    { kind: 'diary',   label: '§ Acknowledge · 今天的安静是被允许的', path: 'diary / 2026-04-19', href: 'diary.html', meta: 'today' },
    { kind: 'diary',   label: '§ Adjust · 不必把边界说得太像规则',   path: 'diary / 2026-04-17', href: 'diary.html', meta: '2 days' },
    // commands
    { kind: 'cmd',     label: 'New drawer',                 path: 'command',                 href: '#',            meta: '⌘ N' },
    { kind: 'cmd',     label: 'New AAAK entry',             path: 'command',                 href: 'diary.html',   meta: '⌘ ⇧ D' },
    { kind: 'cmd',     label: 'New tunnel',                 path: 'command',                 href: 'tunnels.html', meta: '⌘ ⇧ T' },
    { kind: 'cmd',     label: 'Re-embed current wing',      path: 'command',                 href: '#',            meta: 'action' },
    { kind: 'cmd',     label: 'Toggle dark / darker',       path: 'command',                 href: '#',            meta: 'display' },
  ];

  function makeCmdK() {
    if (document.getElementById('__cmdk-backdrop')) return;
    const backdrop = document.createElement('div');
    backdrop.className = 'cmdk-backdrop';
    backdrop.id = '__cmdk-backdrop';
    backdrop.innerHTML = '';

    const box = document.createElement('div');
    box.className = 'cmdk';
    box.id = '__cmdk';
    box.innerHTML = `
      <div class="cmdk-head">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.25"><circle cx="6" cy="6" r="3.6"/><path d="M8.8 8.8l3.4 3.4"/></svg>
        <input class="cmdk-input" id="__cmdk-input" placeholder="唤一个字、一条关系、一段沉默 …" />
        <span class="cmdk-esc" id="__cmdk-esc">ESC</span>
      </div>
      <div class="cmdk-body" id="__cmdk-body"></div>
      <div class="cmdk-foot">
        <span><span class="kbd">↑↓</span>导航</span>
        <span><span class="kbd">↵</span>打开</span>
        <span><span class="kbd">ESC</span>关闭</span>
        <span class="spacer"></span>
        <span class="tip">27 条已索引</span>
      </div>`;
    document.body.appendChild(backdrop);
    document.body.appendChild(box);

    const input = box.querySelector('#__cmdk-input');
    const body = box.querySelector('#__cmdk-body');
    let sel = 0;
    let current = [];

    function filter(q) {
      q = (q || '').trim().toLowerCase();
      if (!q) return CMDK_INDEX.slice();
      return CMDK_INDEX.filter(it =>
        it.label.toLowerCase().includes(q) || it.path.toLowerCase().includes(q)
      );
    }

    function highlight(text, q) {
      if (!q) return text;
      const i = text.toLowerCase().indexOf(q.toLowerCase());
      if (i < 0) return text;
      return text.slice(0, i) + '<mark>' + text.slice(i, i + q.length) + '</mark>' + text.slice(i + q.length);
    }

    function render() {
      const q = input.value;
      current = filter(q);
      if (!current.length) {
        body.innerHTML = `
          <div class="cmdk-empty">
            夜深，此问暂未有答。<br/>
            <span class="dots-pulse" aria-hidden="true"><span>·</span><span>·</span><span>·</span></span>
          </div>`;
        return;
      }
      sel = Math.min(sel, current.length - 1);
      const groups = {};
      current.forEach(it => { (groups[it.kind] = groups[it.kind] || []).push(it); });
      const ORDER = ['go', 'drawer', 'entity', 'diary', 'cmd'];
      const LABELS = { go: 'Navigate', drawer: 'Drawers', entity: 'Entities', diary: 'Diary', cmd: 'Commands' };
      const KIND_ABBR = { go: 'goto', drawer: 'drwr', entity: 'enty', diary: 'diry', cmd: 'cmd' };

      let html = '';
      let idx = 0;
      ORDER.forEach(k => {
        const arr = groups[k]; if (!arr || !arr.length) return;
        html += `<div class="cmdk-group"><span>${LABELS[k]}</span><span class="n">${arr.length}</span></div>`;
        arr.forEach(it => {
          const selCls = idx === sel ? ' sel' : '';
          html += `
            <div class="cmdk-item${selCls}" data-idx="${idx}" data-href="${it.href}">
              <div class="cmdk-kind">${KIND_ABBR[k]}</div>
              <div class="cmdk-main"><span class="path">${it.path}</span>${highlight(it.label, q)}</div>
              <div class="cmdk-meta">${it.meta || ''}</div>
            </div>`;
          idx++;
        });
      });
      body.innerHTML = html;

      body.querySelectorAll('.cmdk-item').forEach(el => {
        el.addEventListener('mouseenter', () => {
          sel = parseInt(el.dataset.idx, 10);
          body.querySelectorAll('.cmdk-item.sel').forEach(n => n.classList.remove('sel'));
          el.classList.add('sel');
        });
        el.addEventListener('click', () => go(parseInt(el.dataset.idx, 10)));
      });
    }

    function go(i) {
      const it = current[i];
      if (!it) return;
      close();
      if (it.href && it.href !== '#') location.href = it.href;
    }

    function open() {
      backdrop.classList.add('open');
      box.classList.add('open');
      input.value = '';
      sel = 0;
      render();
      setTimeout(() => input.focus(), 30);
    }
    function close() {
      backdrop.classList.remove('open');
      box.classList.remove('open');
    }

    input.addEventListener('input', () => { sel = 0; render(); });
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, current.length - 1); render(); scrollSel(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); render(); scrollSel(); }
      else if (e.key === 'Enter') { e.preventDefault(); go(sel); }
      else if (e.key === 'Escape') { e.preventDefault(); close(); }
    });

    function scrollSel() {
      const el = body.querySelector('.cmdk-item.sel');
      if (el) el.scrollIntoView({ block: 'nearest' });
    }

    backdrop.addEventListener('click', close);
    box.querySelector('#__cmdk-esc').addEventListener('click', close);

    window.__openCmdK = open;
    window.__closeCmdK = close;
  }

  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      window.__openCmdK && window.__openCmdK();
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    mount();
    startClock();
    crawlCounters();
    makeCmdK();
    initNavCounts();
  });
})();
