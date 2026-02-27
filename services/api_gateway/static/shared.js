/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Shared Module
   Auth, API client, WebSocket, toast notifications, utilities,
   order modal. Exposed via window.SwiftTrack namespace.
   ═══════════════════════════════════════════════════════════ */

(() => {
  'use strict';

  // ── Constants ─────────────────────────────────────────
  const API_BASE = '';
  const TOKEN_KEY = 'swifttrack_token';
  const USER_KEY  = 'swifttrack_user';

  // ── State ─────────────────────────────────────────────
  let currentUser = null;
  let authToken   = null;
  let ws          = null;

  // ── DOM Helpers ───────────────────────────────────────
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── API Client ────────────────────────────────────────
  async function api(method, path, body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || `API error: ${res.status}`);
    }
    return data;
  }

  // ── Auth Module ───────────────────────────────────────
  function loadSession() {
    const token = localStorage.getItem(TOKEN_KEY);
    const user  = localStorage.getItem(USER_KEY);
    if (token && user) {
      authToken   = token;
      currentUser = JSON.parse(user);
      return true;
    }
    return false;
  }

  function saveSession(token, user) {
    authToken   = token;
    currentUser = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    authToken   = null;
    currentUser = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    if (ws) { ws.close(); ws = null; }
  }

  async function login(username, password) {
    const data = await api('POST', '/api/auth/login', { username, password });
    saveSession(data.access_token, {
      username: data.username,
      role: data.role,
      name: data.name,
    });
    return data;
  }

  /**
   * Auth guard for dashboard pages.
   * If user is not logged in → redirects to /login.
   * If user's role doesn't match requiredRole → redirects to their own dashboard.
   * Returns true if the user is authorized for this page.
   */
  function requireAuth(requiredRole) {
    if (!loadSession()) {
      window.location.replace('/login');
      return false;
    }
    if (requiredRole && currentUser.role !== requiredRole) {
      window.location.replace('/' + currentUser.role);
      return false;
    }
    return true;
  }

  /** Redirect already-authenticated users away from the login page. */
  function redirectIfAuthenticated() {
    if (loadSession()) {
      window.location.replace('/' + currentUser.role);
      return true;
    }
    return false;
  }

  function getUser() { return currentUser; }
  function getToken() { return authToken; }

  // ── Navigation ────────────────────────────────────────
  function logout() {
    clearSession();
    window.location.replace('/login');
  }

  // ── WebSocket ─────────────────────────────────────────
  let onOrderUpdate = null; // callback set by page scripts

  function connectWebSocket() {
    if (!currentUser) return;
    if (ws) ws.close();
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${location.host}/ws/tracking/${currentUser.username}`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        const el = $('#ws-status');
        if (el) { el.classList.remove('disconnected'); el.title = 'WebSocket connected'; }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'order_update') {
            showToast('info', 'Order Update',
              `Order ${shortId(data.order_id)} → ${formatStatus(data.status)}`);
            if (onOrderUpdate) onOrderUpdate(data);
          }
        } catch (e) { /* ignore non-JSON */ }
      };

      ws.onclose = () => {
        const el = $('#ws-status');
        if (el) { el.classList.add('disconnected'); el.title = 'WebSocket disconnected'; }
        setTimeout(() => { if (currentUser) connectWebSocket(); }, 5000);
      };

      ws.onerror = () => { ws.close(); };
    } catch (e) {
      console.warn('WebSocket connection failed:', e);
    }
  }

  function setOrderUpdateCallback(fn) {
    onOrderUpdate = fn;
  }

  // ── Order Detail Modal ────────────────────────────────
  async function viewOrder(orderId) {
    try {
      const order = await api('GET', `/api/orders/${orderId}`);
      renderOrderModal(order);
      $('#order-modal').classList.add('active');
    } catch (e) {
      showToast('error', 'Error', 'Could not load order details');
    }
  }

  function renderOrderModal(order) {
    const details = $('#modal-details');
    details.innerHTML = `
      <div class="detail-item">
        <label>Display ID</label>
        <span class="order-id" style="font-size:1.1em; font-weight:600;">${order.display_id || order.id}</span>
      </div>
      <div class="detail-item" style="grid-column: 1 / -1;">
        <label>System UUID</label>
        <span class="text-xs text-muted" style="user-select:all">${order.id}</span>
      </div>
      <div class="detail-item">
        <label>Status</label>
        <span class="status-badge status-${order.status}">${formatStatus(order.status)}</span>
      </div>
      <div class="detail-item">
        <label>Sender</label>
        <span>${order.sender_name || order.client_id}</span>
      </div>
      <div class="detail-item">
        <label>Receiver</label>
        <span>${order.receiver_name || '-'}</span>
      </div>
      <div class="detail-item">
        <label>Client ID</label>
        <span>${order.client_id}</span>
      </div>
      <div class="detail-item">
        <label>Created</label>
        <span>${formatDateTime(order.created_at)}</span>
      </div>
      <div class="detail-item">
        <label>Pickup</label>
        <span>${order.pickup_address}</span>
      </div>
      <div class="detail-item">
        <label>Delivery</label>
        <span>${order.delivery_address}</span>
      </div>
      ${order.cms_reference ? `
        <div class="detail-item">
          <label>CMS Ref</label>
          <span>${order.cms_reference}</span>
        </div>
      ` : ''}
      ${order.wms_reference ? `
        <div class="detail-item">
          <label>WMS Ref</label>
          <span>${order.wms_reference}</span>
        </div>
      ` : ''}
      ${order.route_id ? `
        <div class="detail-item">
          <label>Route ID</label>
          <span>${order.route_id}</span>
        </div>
      ` : ''}
      ${order.pickup_driver_id ? `
        <div class="detail-item">
          <label>Pickup Driver</label>
          <span>${order.pickup_driver_id}</span>
        </div>
      ` : ''}
      ${order.delivery_driver_id ? `
        <div class="detail-item">
          <label>Delivery Driver</label>
          <span>${order.delivery_driver_id}</span>
        </div>
      ` : ''}
      ${order.delivery_attempts !== undefined ? `
        <div class="detail-item">
          <label>Delivery Attempts</label>
          <span>${order.delivery_attempts} / ${order.max_delivery_attempts || 3}</span>
        </div>
      ` : ''}
    `;

    // Timeline
    const timeline = $('#modal-timeline');
    const history = order.status_history || [];

    if (history.length) {
      timeline.innerHTML = history.map(h => `
        <div class="timeline-item">
          <div class="timeline-status">
            <span class="status-badge status-${h.new_status}">${formatStatus(h.new_status)}</span>
          </div>
          <div class="timeline-details">${h.details || ''}</div>
          <div class="timeline-time">${formatDateTime(h.created_at)}</div>
        </div>
      `).join('');
    } else {
      timeline.innerHTML = '<p class="text-muted text-sm">No status history available.</p>';
    }
  }

  function closeModal() {
    $('#order-modal').classList.remove('active');
  }

  // ── Custom Prompt Modal ───────────────────────────────
  function showPromptDialog(title, message, placeholder = "") {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay active";
      overlay.style.zIndex = "9999";
      
      overlay.innerHTML = `
        <div class="modal prompt-modal" style="max-width:400px;text-align:left;">
          <div class="modal-header">
            <h2>${title}</h2>
            <button class="modal-close" type="button" id="prompt-x">&times;</button>
          </div>
          <div id="modal-body" style="padding-top: var(--space-sm);">
            <p style="margin-bottom: var(--space-md); color: var(--text-secondary);">${message}</p>
            <input type="text" class="form-input" id="prompt-input" placeholder="${placeholder}">
            <div class="form-row" style="margin-top: var(--space-lg); display: flex; gap: var(--space-sm); justify-content: flex-end;">
              <button class="btn btn-secondary" id="prompt-cancel" style="width: auto;">Cancel</button>
              <button class="btn btn-primary" id="prompt-confirm" style="width: auto;">Confirm</button>
            </div>
          </div>
        </div>
      `;
      
      document.body.appendChild(overlay);
      const input = overlay.querySelector("#prompt-input");
      const cancelBtn = overlay.querySelector("#prompt-cancel");
      const confirmBtn = overlay.querySelector("#prompt-confirm");
      const closeBtn = overlay.querySelector("#prompt-x");
      
      setTimeout(() => input.focus(), 50);
      
      const cleanup = () => {
        overlay.classList.remove("active");
        setTimeout(() => overlay.remove(), 250);
      };
      
      cancelBtn.onclick = closeBtn.onclick = () => { cleanup(); resolve(null); };
      confirmBtn.onclick = () => { cleanup(); resolve(input.value); };
      input.onkeydown = (e) => {
        if (e.key === "Enter") confirmBtn.click();
        if (e.key === "Escape") cancelBtn.click();
      };
    });
  }

  // ── Toast Notifications ───────────────────────────────
  function showToast(type, title, message) {
    const container = $('#toast-container');
    if (!container) return;
    const icons = { success: '<i class="ph ph-check-circle"></i>', info: '<i class="ph ph-info"></i>', warning: '<i class="ph ph-warning"></i>', error: '<i class="ph ph-x-circle"></i>' };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || '<i class="ph ph-info"></i>'}</span>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
      </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('removing');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ── Utilities ─────────────────────────────────────────
  function shortId(id) {
    return id ? id.substring(0, 8) + '...' : '';
  }

  function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  function formatStatus(status) {
    if (!status) return '';
    return status.replace(/_/g, ' ');
  }

  function formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }

  // ── Shared Init (called by page scripts) ──────────────
  function initShell() {
    const user = getUser();
    if (!user) return;

    // Populate navbar user info
    const nameEl = $('#nav-user-name');
    const roleEl = $('#nav-user-role');
    if (nameEl) nameEl.textContent = user.name;
    if (roleEl) roleEl.textContent = user.role;

    // Logout button
    const logoutBtn = $('#logout-btn');
    if (logoutBtn) logoutBtn.addEventListener('click', logout);

    // Modal close
    const modalClose = $('#modal-close');
    if (modalClose) modalClose.addEventListener('click', closeModal);

    const modal = $('#order-modal');
    if (modal) modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    // Keyboard
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });

    // Delegated click: [data-action="view-order"]
    document.addEventListener('click', (e) => {
      const viewBtn = e.target.closest('[data-action="view-order"]');
      if (viewBtn) {
        e.preventDefault();
        const orderId = viewBtn.dataset.orderId;
        if (orderId) viewOrder(orderId);
      }
    });

    // Connect WebSocket
    connectWebSocket();
  }

  // ── Public API ────────────────────────────────────────
  window.SwiftTrack = {
    // DOM helpers
    $, $$,
    // API
    api,
    // Auth
    loadSession, saveSession, clearSession, login,
    requireAuth, redirectIfAuthenticated,
    getUser, getToken, logout,
    // WebSocket
    connectWebSocket, setOrderUpdateCallback,
    // Modal
    viewOrder, closeModal, showPromptDialog,
    // Toast
    showToast,
    // Utilities
    shortId, truncate, formatStatus, formatTime, formatDateTime,
    // Shell init
    initShell,
  };

})();
