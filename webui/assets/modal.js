/**
 * Kaguya Mempalace — shared modal component
 * ==========================================
 * Single-instance modal used by wings / graph / diary detail popups.
 *
 * API:
 *   KaguyaModal.open({ title, subtitle, body, actions, onClose })
 *   KaguyaModal.update({ body?, actions? })   // in-place swap, no reopen
 *   KaguyaModal.close()
 *
 *   body: string (inserted as-is, pre-escape yourself) or HTMLElement
 *   actions: [{ label, onClick, variant: 'primary'|'danger'|'ghost' }]
 *
 * Close paths: backdrop click / ESC / "×" button / programmatic close.
 * DOM + class names are a contract with shell.css `.kg-modal-*` rules;
 * do not rename them or CSS will fall off.
 */

window.KaguyaModal = (function () {
  'use strict';

  const esc = (s) =>
    (window.KaguyaAPI && typeof window.KaguyaAPI.escapeHtml === 'function')
      ? window.KaguyaAPI.escapeHtml(s)
      : String(s == null ? '' : s)
          .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  let current = null; // { backdrop, onClose, keyHandler, prevOverflow }
  let pending = null; // a modal mid-close whose cleanup hasn't run yet

  function renderActions(actionsEl, actions) {
    actionsEl.innerHTML = '';
    const list = Array.isArray(actions) ? actions : [];
    list.forEach((a) => {
      if (!a || typeof a.label !== 'string') return;
      const btn = document.createElement('button');
      let cls = 'btn';
      if (a.variant === 'primary') cls += ' primary';
      else if (a.variant === 'danger') cls += ' danger';
      else if (a.variant === 'ghost') cls += ' ghost';
      btn.className = cls;
      btn.textContent = a.label;
      if (typeof a.onClick === 'function') {
        btn.addEventListener('click', (ev) => {
          try { a.onClick(ev); } catch (err) { console.error('modal action threw:', err); }
        });
      }
      actionsEl.appendChild(btn);
    });
  }

  function update(opts) {
    if (!current) return;
    opts = opts || {};
    const card = current.backdrop.querySelector('.kg-modal-card');
    if (!card) return;

    if (opts.body !== undefined) {
      const bodyEl = card.querySelector('.kg-modal-body');
      if (bodyEl) {
        bodyEl.innerHTML = '';
        if (opts.body instanceof HTMLElement) {
          bodyEl.appendChild(opts.body);
        } else if (typeof opts.body === 'string') {
          bodyEl.innerHTML = opts.body;
        }
      }
    }

    if (opts.actions !== undefined) {
      const actionsEl = card.querySelector('.kg-modal-actions');
      if (actionsEl) renderActions(actionsEl, opts.actions);
    }
  }

  function close() {
    if (!current) return;
    const me = current;
    current = null;
    pending = me;

    document.removeEventListener('keydown', me.keyHandler, true);
    me.backdrop.classList.remove('open');

    const backdrop = me.backdrop;
    const done = () => {
      if (backdrop && backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
      if (pending === me) pending = null;
      // Only restore body overflow if no replacement modal (opened or still closing)
      // is around — otherwise we'd unlock scroll while another modal is visible,
      // or on the final close snap the page back to the 'hidden' we imposed.
      if (!current && !pending) {
        document.body.style.overflow = me.prevOverflow || '';
      }
    };
    const handler = (ev) => {
      if (ev.target !== backdrop) return;
      backdrop.removeEventListener('transitionend', handler);
      done();
    };
    backdrop.addEventListener('transitionend', handler);
    // fallback in case transitionend never fires
    setTimeout(() => {
      backdrop.removeEventListener('transitionend', handler);
      done();
    }, 260);

    try { if (typeof me.onClose === 'function') me.onClose(); } catch (err) { console.error('modal onClose threw:', err); }
  }

  function open(opts) {
    opts = opts || {};
    // Inherit prevOverflow from the outgoing (or still-closing) modal so the
    // pre-modal page style isn't lost to the 'hidden' we imposed on the body.
    const predecessor = current || pending;
    const inheritedPrev = predecessor ? predecessor.prevOverflow : null;
    if (current) close();

    const backdrop = document.createElement('div');
    backdrop.className = 'kg-modal-backdrop';

    const card = document.createElement('div');
    card.className = 'kg-modal-card';
    card.setAttribute('role', 'dialog');
    card.setAttribute('aria-modal', 'true');

    const closeBtn = document.createElement('button');
    closeBtn.className = 'kg-modal-close';
    closeBtn.setAttribute('aria-label', '关闭');
    closeBtn.textContent = '×';

    const head = document.createElement('div');
    head.className = 'kg-modal-head';
    const title = document.createElement('div');
    title.className = 'kg-modal-title';
    title.innerHTML = esc(opts.title || '');
    head.appendChild(title);
    if (opts.subtitle) {
      const sub = document.createElement('div');
      sub.className = 'kg-modal-subtitle';
      sub.innerHTML = esc(opts.subtitle);
      head.appendChild(sub);
    }

    const body = document.createElement('div');
    body.className = 'kg-modal-body';
    if (opts.body instanceof HTMLElement) {
      body.appendChild(opts.body);
    } else if (typeof opts.body === 'string') {
      body.innerHTML = opts.body;
    }

    const actionsWrap = document.createElement('div');
    actionsWrap.className = 'kg-modal-actions';
    renderActions(actionsWrap, opts.actions);

    card.appendChild(closeBtn);
    card.appendChild(head);
    card.appendChild(body);
    card.appendChild(actionsWrap);
    backdrop.appendChild(card);

    backdrop.addEventListener('click', (ev) => {
      if (ev.target === backdrop) close();
    });
    closeBtn.addEventListener('click', (ev) => {
      ev.preventDefault();
      close();
    });

    const keyHandler = (ev) => {
      if (ev.key === 'Escape' || ev.key === 'Esc') {
        ev.preventDefault();
        ev.stopPropagation();
        close();
      }
    };
    document.addEventListener('keydown', keyHandler, true);

    const prevOverflow = inheritedPrev !== null ? inheritedPrev : document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.body.appendChild(backdrop);

    // next frame so the opening transition can run
    requestAnimationFrame(() => backdrop.classList.add('open'));

    current = { backdrop, onClose: opts.onClose, keyHandler, prevOverflow };
    return { close };
  }

  return { open, update, close };
})();
