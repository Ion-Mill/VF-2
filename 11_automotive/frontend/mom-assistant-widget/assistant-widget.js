/*
 * MOM 운영 비서 플로팅 위젯 (의존성 없음, 바닐라 JS)
 *
 *   const assistant = new MomAssistant({
 *     onSend: async (text) => '답변',          // 채팅 전송 → 답변 문자열을 돌려주는 함수 (백엔드/LLM 연결 지점)
 *     onOpenReport: (shift) => { ... },        // 교대 보고서 알림을 눌렀을 때 (보고서 페이지로 이동 등)
 *     shiftReminders: [{ time: '17:20', shift: '주간조' }],  // 이 시각이 되면 교대 보고서 알림을 띄움
 *   });
 *   assistant.setData({ brief, alerts, history });
 *
 * 공개 메서드: open(tab) · close() · toggle() · setData(data) · addMessage(role, text)
 *             notify(notice) · dismissNotice() · notifyShiftReport(shift) · destroy()
 * tab 이름: 'brief' | 'alert' | 'chat' | 'history'
 */
(function (global) {
  'use strict';

  var TABS = [
    { key: 'brief', label: '브리핑', icon: ['M6 3h12v18H6z', 'M9 8h6M9 12h6M9 16h4'] },
    { key: 'alert', label: '알림', icon: ['M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2z', 'M10 20a2 2 0 0 0 4 0'] },
    { key: 'chat', label: '채팅', icon: ['M4 5h16v11H9l-5 4z', ''] },
    { key: 'history', label: '채팅기록', icon: ['M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0', 'M12 7v5l3 2'] }
  ];
  var LEVELS = { warn: 1, danger: 1, info: 1, done: 1, ai: 1 };

  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function level(v) { return LEVELS[v] ? v : 'info'; }
  function icon(paths, size) {
    return '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size + '" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      paths.filter(Boolean).map(function (d) { return '<path d="' + d + '"></path>'; }).join('') + '</svg>';
  }
  var ICON_X = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>';
  var ICON_UP = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"></path></svg>';

  /* 로봇 아이콘 (visor 형) — state: idle | think | alert | done | off */
  function robot(state, size, disc) {
    var acc = state === 'off' ? '#7D867F' : '#C8F03C';
    var pad = disc ? Math.round(size * 0.16) : 0;
    function n(x) { return Math.round(x * 100) / 100; }
    function eye(cx, cy) {
      var w = 5.6, h = 9, r = w / 2;
      if (state === 'think') { cy -= h * 0.27; cx += w * 0.35; h *= 0.7; }
      if (state === 'alert') {
        var rr = Math.max(w, h) * 0.5;
        return '<circle cx="' + cx + '" cy="' + cy + '" r="' + n(rr) + '" fill="#FFB020"></circle>';
      }
      if (state === 'done') {
        return '<path d="M' + n(cx - w * 0.85) + ' ' + n(cy + h * 0.2) + ' Q' + cx + ' ' + n(cy - h * 0.75) + ' ' + n(cx + w * 0.85) + ' ' + n(cy + h * 0.2) +
          '" fill="none" stroke="' + acc + '" stroke-width="' + n(w * 0.55) + '" stroke-linecap="round"></path>';
      }
      if (state === 'off') {
        return '<path d="M' + n(cx - w * 0.8) + ' ' + cy + ' H' + n(cx + w * 0.8) + '" stroke="#6D757B" stroke-width="2" stroke-linecap="round"></path>';
      }
      var hh = Math.max(h, w);
      return '<rect x="' + n(cx - r) + '" y="' + n(cy - hh / 2) + '" width="' + w + '" height="' + n(hh) + '" rx="' + n(r) + '" fill="' + acc + '"></rect>';
    }
    return '<span style="position:relative;display:block;width:' + size + 'px;height:' + size + 'px;flex-shrink:0">' +
      (disc ? '<span style="position:absolute;inset:0;border-radius:50%;background:#1A1F23"></span>' : '') +
      '<svg viewBox="0 0 64 64" aria-hidden="true" style="position:absolute;inset:' + pad + 'px;width:calc(100% - ' + (pad * 2) + 'px);height:calc(100% - ' + (pad * 2) + 'px)">' +
      '<line x1="32" y1="8" x2="32" y2="15" stroke="#C9D0C6" stroke-width="2.6" stroke-linecap="round"></line>' +
      '<circle cx="32" cy="7" r="3.4" fill="' + acc + '"></circle>' +
      '<rect x="5" y="28" width="6.5" height="14" rx="2.6" fill="#C9D0C6"></rect>' +
      '<rect x="52.5" y="28" width="6.5" height="14" rx="2.6" fill="#C9D0C6"></rect>' +
      '<rect x="9" y="15" width="46" height="39" rx="13" fill="#F2F4EF"></rect>' +
      '<rect x="15" y="23.5" width="34" height="18" rx="9" fill="#14181B"></rect>' +
      '<rect x="27" y="46.5" width="10" height="2.6" rx="1.3" fill="#C9D0C6"></rect>' +
      eye(24.5, 32.5) + eye(39.5, 32.5) +
      '</svg></span>';
  }

  function MomAssistant(options) {
    this.opts = Object.assign({
      mount: document.body,
      title: '운영 비서',
      onSend: null,
      onOpenReport: null,
      shiftReminders: [],
      now: function () { return new Date(); }
    }, options || {});
    this.mode = 'closed';            // closed | menu | brief | alert | chat | history
    this.data = { brief: null, alerts: [], history: [] };
    this.messages = [];
    this.unread = { brief: 0, alert: 0, chat: 0, history: 0 };
    this.notice = null;
    this.waiting = false;
    this.firedReminders = {};
    this._build();
    this._render();
    this._startReminders();
  }

  MomAssistant.prototype._build = function () {
    var self = this;
    var root = document.createElement('div');
    root.className = 'ma-root';
    root.innerHTML =
      '<div class="ma-toast ma-rise" role="status" data-el="toast" hidden></div>' +
      '<div class="ma-menu" role="menu" aria-label="' + esc(this.opts.title) + ' 메뉴" data-el="menu" hidden></div>' +
      '<aside class="ma-panel ma-side" data-el="panel" aria-label="' + esc(this.opts.title) + '" hidden>' +
        '<header class="ma-panel-head">' + robot('idle', 30, true) +
          '<strong class="ma-panel-title" data-el="title"></strong>' +
          '<button type="button" class="ma-icon-btn" data-act="close" aria-label="창 닫기">' + ICON_X + '</button>' +
        '</header>' +
        '<div class="ma-tabs" role="tablist" aria-label="' + esc(this.opts.title) + ' 메뉴" data-el="tabs"></div>' +
        '<div class="ma-body" role="tabpanel" data-el="body"></div>' +
        '<form class="ma-compose" data-el="compose" hidden>' +
          '<div class="ma-compose-box">' +
            '<label class="ma-sr" for="ma-input">비서에게 질문</label>' +
            '<input id="ma-input" class="ma-input" data-el="input" autocomplete="off" placeholder="질문을 입력하세요">' +
            '<button type="submit" class="ma-send" data-el="send" aria-label="보내기">' + ICON_UP + '</button>' +
          '</div>' +
        '</form>' +
      '</aside>' +
      '<button type="button" class="ma-fab" data-act="toggle" data-el="fab" aria-expanded="false"></button>';

    this.root = root;
    this.el = {};
    root.querySelectorAll('[data-el]').forEach(function (node) { self.el[node.getAttribute('data-el')] = node; });

    this._onClick = function (e) {
      var t = e.target.closest('[data-act]');
      if (!t || !root.contains(t)) return;
      var act = t.getAttribute('data-act');
      var arg = t.getAttribute('data-arg');
      if (act === 'toggle') self.toggle();
      else if (act === 'close') self.close();
      else if (act === 'tab') self.open(arg);
      else if (act === 'alert') self._runAlert(arg);
      else if (act === 'brief-action') self._runBriefAction(Number(arg));
      else if (act === 'history') self._runHistory(Number(arg));
      else if (act === 'notice-primary') self._runNotice(true);
      else if (act === 'notice-dismiss') self.dismissNotice();
    };
    this._onSubmit = function (e) {
      e.preventDefault();
      var text = self.el.input.value.trim();
      if (!text || self.waiting) return;
      self.el.input.value = '';
      self._send(text);
    };
    this._onKey = function (e) {
      if (e.key !== 'Escape') return;
      if (self.mode === 'menu' || self._isPanel()) { self.close(); self.el.fab.focus(); }
    };
    this._onTabKey = function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      var i = TABS.findIndex(function (t) { return t.key === self.mode; });
      var next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length].key;
      self.open(next);
      var b = self.el.tabs.querySelector('[data-arg="' + next + '"]');
      if (b) b.focus();
    };
    root.addEventListener('click', this._onClick);
    this.el.compose.addEventListener('submit', this._onSubmit);
    this.el.tabs.addEventListener('keydown', this._onTabKey);
    document.addEventListener('keydown', this._onKey);
    this.opts.mount.appendChild(root);
  };

  /* ── 공개 API ── */
  MomAssistant.prototype.toggle = function () {
    this.notice = this.mode === 'closed' ? null : this.notice;
    this.mode = this.mode === 'closed' ? 'menu' : 'closed';
    this._render();
    if (this.mode === 'menu') {
      var first = this.el.menu.querySelector('button');
      if (first) first.focus();
    }
  };
  MomAssistant.prototype.open = function (tab) {
    if (!TABS.some(function (t) { return t.key === tab; })) tab = 'brief';
    var wasPanel = this._isPanel();
    this.mode = tab;
    this.unread[tab] = 0;
    if (tab === 'alert') this.data.alerts.forEach(function (a) { a.unread = false; });
    if (tab === 'brief' && this.data.brief) this.data.brief.unread = false;
    this._render();
    if (tab === 'chat') this.el.input.focus();
    else if (!wasPanel) { var b = this.el.tabs.querySelector('[aria-selected="true"]'); if (b) b.focus(); }
  };
  MomAssistant.prototype.close = function () { this.mode = 'closed'; this._render(); };

  MomAssistant.prototype.setData = function (data) {
    data = data || {};
    if ('brief' in data) this.data.brief = data.brief;
    if ('alerts' in data) this.data.alerts = (data.alerts || []).map(function (a) { return Object.assign({}, a); });
    if ('history' in data) this.data.history = data.history || [];
    this.unread.brief = this.data.brief && this.data.brief.unread && this.mode !== 'brief' ? 1 : 0;
    this.unread.alert = this.mode === 'alert' ? 0 : this.data.alerts.filter(function (a) { return a.unread; }).length;
    this._render();
  };

  MomAssistant.prototype.addMessage = function (role, text) {
    this.messages.push({ role: role === 'user' ? 'user' : 'bot', text: String(text) });
    if (role !== 'user' && this.mode !== 'chat') this.unread.chat += 1;
    this._render();
  };

  /* notice: { time, title, body, primaryLabel, secondaryLabel, onPrimary } */
  MomAssistant.prototype.notify = function (notice) {
    this.notice = notice;
    this._render();
  };
  MomAssistant.prototype.dismissNotice = function () { this.notice = null; this._render(); };

  MomAssistant.prototype.notifyShiftReport = function (shift, time) {
    var self = this;
    var alertId = 'shift-report-' + shift;
    var report = function () {
      self.dismissNotice();
      self.close();
      if (typeof self.opts.onOpenReport === 'function') self.opts.onOpenReport(shift);
    };
    var others = this.data.alerts.filter(function (a) { return a.id !== alertId; });
    this.data.alerts = [{
      id: alertId, level: 'ai', tag: 'AI', time: (time || '') + ' · ' + shift + ' 마감',
      title: '교대 보고서 작성할 시간이에요', body: '실적·설비·품질 내용을 미리 채워 뒀어요 · 누르면 작성 화면으로 가요',
      unread: true, onClick: report
    }].concat(others);
    this.unread.alert = this.mode === 'alert' ? 0 : this.data.alerts.filter(function (a) { return a.unread; }).length;
    this.notify({
      time: (time ? time + ' · ' : '') + shift + ' 마감 전',
      title: '교대 보고서 작성할 시간이에요',
      body: '실적·설비·품질 내용을 미리 채워 뒀어요. 확인하고 제출만 하면 돼요.',
      primaryLabel: '보고서 작성', secondaryLabel: '나중에', onPrimary: report
    });
  };

  MomAssistant.prototype.destroy = function () {
    clearInterval(this._timer);
    document.removeEventListener('keydown', this._onKey);
    this.root.remove();
  };

  /* ── 내부 동작 ── */
  MomAssistant.prototype._isPanel = function () {
    return this.mode === 'brief' || this.mode === 'alert' || this.mode === 'chat' || this.mode === 'history';
  };

  MomAssistant.prototype._runAlert = function (id) {
    var a = this.data.alerts.find(function (x) { return String(x.id) === id; });
    if (a && typeof a.onClick === 'function') a.onClick(a);
  };
  MomAssistant.prototype._runBriefAction = function (i) {
    var b = this.data.brief;
    var act = b && b.actions && b.actions[i];
    if (!act) return;
    if (act.tab) this.open(act.tab);
    if (typeof act.onClick === 'function') act.onClick();
  };
  MomAssistant.prototype._runHistory = function (i) {
    var h = this.data.history[i];
    if (h && typeof h.onClick === 'function') h.onClick(h);
  };
  MomAssistant.prototype._runNotice = function () {
    var n = this.notice;
    if (n && typeof n.onPrimary === 'function') n.onPrimary();
    else this.dismissNotice();
  };

  MomAssistant.prototype._send = function (text) {
    var self = this;
    this.addMessage('user', text);
    if (typeof this.opts.onSend !== 'function') {
      this.addMessage('bot', '아직 답변 기능이 연결되지 않았어요.');
      return;
    }
    this.waiting = true;
    this._render();
    Promise.resolve()
      .then(function () { return self.opts.onSend(text, self.messages.slice()); })
      .then(function (reply) { self.waiting = false; self.addMessage('bot', reply == null ? '' : reply); })
      .catch(function () { self.waiting = false; self.addMessage('bot', '답변을 가져오지 못했어요. 잠시 후 다시 물어봐 주세요.'); });
  };

  MomAssistant.prototype._startReminders = function () {
    var self = this;
    var list = this.opts.shiftReminders || [];
    if (!list.length) return;
    var check = function () {
      var d = self.opts.now();
      var hm = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
      var day = d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
      list.forEach(function (r) {
        var key = day + ' ' + r.time + ' ' + r.shift;
        if (hm >= r.time && !self.firedReminders[key] && hm < self._plusMinutes(r.time, 60)) {
          self.firedReminders[key] = true;
          self.notifyShiftReport(r.shift, r.time);
        }
      });
    };
    check();
    this._timer = setInterval(check, 30000);
  };
  MomAssistant.prototype._plusMinutes = function (hm, add) {
    var p = hm.split(':');
    var t = Math.min(23 * 60 + 59, Number(p[0]) * 60 + Number(p[1]) + add);
    return ('0' + Math.floor(t / 60)).slice(-2) + ':' + ('0' + (t % 60)).slice(-2);
  };

  /* ── 그리기 ── */
  MomAssistant.prototype._render = function () {
    var el = this.el;
    var mode = this.mode;
    var isPanel = this._isPanel();
    var unread = this.unread;
    var total = unread.brief + unread.alert + unread.chat;
    var showNotice = !!this.notice && mode === 'closed';

    this.root.classList.toggle('is-panel', isPanel);

    // 로봇 버튼
    el.fab.setAttribute('aria-expanded', mode === 'closed' ? 'false' : 'true');
    el.fab.setAttribute('aria-label', mode === 'closed' ? this.opts.title + ' 메뉴 열기' : this.opts.title + ' 닫기');
    el.fab.innerHTML = robot(this.waiting ? 'think' : showNotice ? 'alert' : 'idle', 44, false) +
      (mode === 'closed' && total > 0 ? '<span class="ma-fab-badge" aria-hidden="true">' + total + '</span>' : '');
    if (mode === 'closed' && total > 0) el.fab.setAttribute('aria-label', this.opts.title + ' 메뉴 열기, 새 소식 ' + total + '건');

    // 아이콘 메뉴
    var wasMenu = !el.menu.hidden;
    el.menu.hidden = mode !== 'menu';
    if (mode === 'menu' && !wasMenu) {
      el.menu.innerHTML = TABS.map(function (t, i) {
        var c = unread[t.key];
        return '<button type="button" role="menuitem" class="ma-menu-item ma-rise" style="animation-delay:' + (i * 50) + 'ms" data-act="tab" data-arg="' + t.key + '">' +
          '<span class="ma-menu-label">' + t.label + '</span>' +
          '<span class="ma-menu-icon">' + icon(t.icon, 20) +
          (c > 0 ? '<span class="ma-menu-badge" aria-label="새 소식 ' + c + '건">' + c + '</span>' : '') +
          '</span></button>';
      }).join('');
    }

    // 토스트
    el.toast.hidden = !showNotice;
    if (showNotice) {
      var n = this.notice;
      el.toast.innerHTML =
        '<button type="button" class="ma-toast-main" data-act="notice-primary">' + robot('alert', 36, true) +
          '<span class="ma-toast-text">' +
            (n.time ? '<span class="ma-toast-time ma-mono">' + esc(n.time) + '</span>' : '') +
            '<strong class="ma-toast-title">' + esc(n.title) + '</strong>' +
            (n.body ? '<span class="ma-toast-body">' + esc(n.body) + '</span>' : '') +
          '</span></button>' +
        '<div class="ma-actions">' +
          '<button type="button" class="ma-btn ma-btn-primary" data-act="notice-primary">' + esc(n.primaryLabel || '열기') + '</button>' +
          '<button type="button" class="ma-btn ma-btn-ghost" data-act="notice-dismiss">' + esc(n.secondaryLabel || '닫기') + '</button>' +
        '</div>';
    }

    // 우측 창
    el.panel.hidden = !isPanel;
    el.compose.hidden = mode !== 'chat';
    if (!isPanel) return;
    var tab = TABS.find(function (t) { return t.key === mode; });
    el.title.textContent = this.opts.title + ' · ' + tab.label;
    el.tabs.innerHTML = TABS.map(function (t) {
      var on = t.key === mode;
      var c = unread[t.key];
      return '<button type="button" role="tab" class="ma-tab" data-act="tab" data-arg="' + t.key + '" aria-selected="' + on + '" tabindex="' + (on ? 0 : -1) + '">' +
        t.label + (c > 0 ? '<span class="ma-tab-badge" aria-label="새 소식 ' + c + '건">' + c + '</span>' : '') + '</button>';
    }).join('');
    el.body.innerHTML = this['_' + mode]();
    el.send.disabled = this.waiting;
    if (mode === 'chat') el.body.scrollTop = el.body.scrollHeight;
  };

  MomAssistant.prototype._brief = function () {
    var b = this.data.brief;
    if (!b) return '<p class="ma-empty">아직 브리핑이 없어요.</p>';
    return '<div class="ma-pad">' +
      '<div style="display:flex;align-items:baseline;gap:8px"><h3 class="ma-h3">' + esc(b.title) + '</h3>' +
        (b.time ? '<span class="ma-mono ma-mute" style="font-size:12px">' + esc(b.time) + '</span>' : '') + '</div>' +
      (b.summary ? '<p class="ma-p ma-sub">' + esc(b.summary) + '</p>' : '') +
      (b.rows && b.rows.length ? '<div class="ma-rows">' + b.rows.map(function (r) {
        return '<div class="ma-row"><span class="ma-row-label">' + esc(r.label) + '</span><span>' + esc(r.text) + '</span>' +
          '<span class="ma-row-val ma-mono' + (r.level ? ' ma-tone-' + level(r.level) : '') + '">' + esc(r.value) + '</span></div>';
      }).join('') + '</div>' : '') +
      (b.handover && b.handover.length ? '<div style="display:flex;flex-direction:column;gap:6px"><p class="ma-caption">' + esc(b.handoverTitle || '다음 조에 넘길 것') + '</p>' +
        b.handover.map(function (h) { return '<p class="ma-p">· ' + esc(h) + '</p>'; }).join('') + '</div>' : '') +
      (b.actions && b.actions.length ? '<div class="ma-actions">' + b.actions.map(function (a, i) {
        return '<button type="button" class="ma-btn ' + (a.primary ? 'ma-btn-primary' : 'ma-btn-ghost') + '" data-act="brief-action" data-arg="' + i + '">' + esc(a.label) + '</button>';
      }).join('') + '</div>' : '') +
      '</div>';
  };

  MomAssistant.prototype._alert = function () {
    var list = this.data.alerts;
    if (!list.length) return '<p class="ma-empty">새 알림이 없어요.</p>';
    return list.map(function (a) {
      var lv = level(a.level);
      var cls = 'ma-alert' + (lv === 'ai' ? ' is-ai' : lv === 'done' ? ' is-done' : ' is-open');
      var inner = '<span class="ma-alert-meta"><span class="ma-chip ma-chip-' + lv + '">' + esc(a.tag || '') + '</span>' +
        '<span class="ma-alert-time ma-mono">' + esc(a.time || '') + '</span></span>' +
        '<span class="ma-alert-title">' + esc(a.title) + '</span>' +
        (a.body ? '<span class="ma-alert-body">' + esc(a.body) + '</span>' : '');
      return typeof a.onClick === 'function'
        ? '<button type="button" class="' + cls + '" data-act="alert" data-arg="' + esc(a.id) + '">' + inner + '</button>'
        : '<div class="' + cls + '">' + inner + '</div>';
    }).join('');
  };

  MomAssistant.prototype._chat = function () {
    if (!this.messages.length && !this.waiting) return '<p class="ma-empty">라인 상황, 작업지시, 재고 등 무엇이든 물어보세요.</p>';
    return '<div class="ma-pad" aria-live="polite">' + this.messages.map(function (m) {
      return m.role === 'user' ? '<div class="ma-msg-user">' + esc(m.text) + '</div>' : '<p class="ma-msg-bot">' + esc(m.text) + '</p>';
    }).join('') + (this.waiting ? '<p class="ma-msg-bot ma-typing">답변을 만드는 중…</p>' : '') + '</div>';
  };

  MomAssistant.prototype._history = function () {
    var list = this.data.history;
    if (!list.length) return '<p class="ma-empty">지난 대화가 없어요.</p>';
    var html = '<div class="ma-history">';
    var group = null;
    list.forEach(function (h, i) {
      if (h.group && h.group !== group) { group = h.group; html += '<p class="ma-history-group">' + esc(group) + '</p>'; }
      html += '<button type="button" class="ma-history-item" data-act="history" data-arg="' + i + '"><strong>' + esc(h.title) + '</strong>' +
        (h.meta ? '<span>' + esc(h.meta) + '</span>' : '') + '</button>';
    });
    return html + '</div>';
  };

  global.MomAssistant = MomAssistant;
})(window);
