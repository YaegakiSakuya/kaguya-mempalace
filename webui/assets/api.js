/**
 * Kaguya Mempalace — API client
 * =============================
 * Thin wrapper around the inspector API (see app/inspector/api.py).
 *
 * Auth is handled transparently by nginx Basic Auth at the edge — the
 * browser attaches the `Authorization: Basic ...` header automatically,
 * and nginx rewrites it to `Bearer <INSPECTOR_TOKEN>` before forwarding
 * to the upstream. This module does not manage auth headers.
 *
 * Usage:
 *   const wings = await KaguyaAPI.getWings();
 *   const res = await KaguyaAPI.search('今夜');
 *
 * Quick test in DevTools Console on any palace page:
 *   await KaguyaAPI.getOverview()
 */

window.KaguyaAPI = (function () {
  const BASE = '/api';

  async function apiFetch(path, options) {
    let res;
    try {
      res = await fetch(BASE + path, options);
    } catch (err) {
      throw new Error('network error: ' + (err && err.message ? err.message : String(err)));
    }

    if (res.status === 401) {
      throw new Error('unauthorized');
    }

    if (!res.ok) {
      let detail = '';
      try {
        const body = await res.clone().json();
        detail = body && body.detail ? body.detail : '';
      } catch (_) {
        try { detail = await res.text(); } catch (_) { detail = ''; }
      }
      throw new Error('HTTP ' + res.status + ': ' + (detail || res.statusText));
    }

    try {
      return await res.json();
    } catch (err) {
      throw new Error('invalid JSON response: ' + (err && err.message ? err.message : String(err)));
    }
  }

  function buildQuery(params) {
    const q = new URLSearchParams();
    Object.keys(params || {}).forEach(k => {
      const v = params[k];
      if (v === undefined || v === null || v === '') return;
      q.append(k, String(v));
    });
    const s = q.toString();
    return s ? '?' + s : '';
  }

  // ----- overview & basic browsing -----

  async function getOverview() {
    return apiFetch('/overview');
  }

  async function getTaxonomy() {
    return apiFetch('/taxonomy');
  }

  async function getWings() {
    return apiFetch('/wings');
  }

  async function getRooms(wing) {
    return apiFetch('/rooms' + buildQuery({ wing }));
  }

  async function getDrawers({ wing, room, limit, offset } = {}) {
    return apiFetch('/drawers' + buildQuery({ wing, room, limit, offset }));
  }

  async function search(query, { topK, wing } = {}) {
    return apiFetch('/search' + buildQuery({ q: query, limit: topK, wing }));
  }

  // ----- knowledge graph -----

  async function getKgStats() {
    return apiFetch('/kg/stats');
  }

  async function getKgEntities({ limit, offset } = {}) {
    return apiFetch('/kg/entities' + buildQuery({ limit, offset }));
  }

  async function getKgTriples({ entity, limit } = {}) {
    return apiFetch('/kg/triples' + buildQuery({ entity, limit }));
  }

  async function getKgTimeline({ entity } = {}) {
    return apiFetch('/kg/timeline' + buildQuery({ entity }));
  }

  // ----- graph / tunnels -----

  async function getGraphStats() {
    return apiFetch('/graph/stats');
  }

  async function getGraphNodes() {
    return apiFetch('/graph/nodes');
  }

  async function getGraphTunnels({ wingA, wingB } = {}) {
    return apiFetch('/graph/tunnels' + buildQuery({ wing_a: wingA, wing_b: wingB }));
  }

  async function getAllTunnels({ wing } = {}) {
    return apiFetch('/graph/tunnels/list' + buildQuery({ wing }));
  }

  // ----- llm config -----

  async function getLlmConfig() {
    return apiFetch('/llm/config');
  }

  // ----- diary / usage / tools / turns -----

  async function getDiary() {
    return apiFetch('/diary');
  }

  async function getUsage() {
    return apiFetch('/usage');
  }

  async function getToolCalls() {
    return apiFetch('/tools/calls');
  }

  async function getTurns() {
    return apiFetch('/turns');
  }

  // ----- rendering helpers -----

  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return '';
    const t = new Date(isoString);
    if (isNaN(t.getTime())) return '';
    const diffMs = Date.now() - t.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return diffMin + ' min ago';
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + ' h ago';
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay <= 6) return diffDay + ' d ago';
    const mm = String(t.getMonth() + 1).padStart(2, '0');
    const dd = String(t.getDate()).padStart(2, '0');
    return mm + '-' + dd;
  }

  function truncate(text, maxLen) {
    if (text === null || text === undefined) return '';
    const s = String(text);
    if (!maxLen || s.length <= maxLen) return s;
    return s.slice(0, maxLen) + '…';
  }

  function formatCount(n) {
    const num = Number(n);
    if (!isFinite(num)) return '';
    if (Math.abs(num) >= 10000) {
      return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    }
    return num.toLocaleString('en-US');
  }

  return {
    fetch: apiFetch,
    getOverview,
    getTaxonomy,
    getWings,
    getRooms,
    getDrawers,
    search,
    getKgStats,
    getKgEntities,
    getKgTriples,
    getKgTimeline,
    getGraphStats,
    getGraphNodes,
    getGraphTunnels,
    getAllTunnels,
    getLlmConfig,
    getDiary,
    getUsage,
    getToolCalls,
    getTurns,
    escapeHtml,
    formatRelativeTime,
    truncate,
    formatCount,
  };
})();
