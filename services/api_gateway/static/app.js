/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Frontend Application
   Auth, routing, API, WebSocket, order management
   ═══════════════════════════════════════════════════════════ */

(() => {
  'use strict';

  // ── Constants ─────────────────────────────────────────
  const API_BASE = '';
  const WS_BASE = `ws://${location.host}`;
  const TOKEN_KEY = 'swifttrack_token';
  const USER_KEY = 'swifttrack_user';

  // ── State ─────────────────────────────────────────────
  let currentUser = null;
  let authToken = null;
  let ws = null;
  let orders = [];
  let pollingInterval = null;

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
    const user = localStorage.getItem(USER_KEY);
    if (token && user) {
      authToken = token;
      currentUser = JSON.parse(user);
      return true;
    }
    return false;
  }

  function saveSession(token, user) {
    authToken = token;
    currentUser = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    if (ws) { ws.close(); ws = null; }
    if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
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

  // ── Router ────────────────────────────────────────────

  // Route registry: path → { viewId, requiredRole, loader }
  // requiredRole: if set, only users with that role may access the route.
  //               if null, the route is public (e.g. /login).
  const ROUTES = {
    '/login':  { viewId: 'view-login',  requiredRole: null,     loader: null },
    '/client': { viewId: 'view-client', requiredRole: 'client', loader: loadClientDashboard },
    '/driver': { viewId: 'view-driver', requiredRole: 'driver', loader: loadDriverDashboard },
    '/admin':  { viewId: 'view-admin',  requiredRole: 'admin',  loader: loadAdminDashboard },
  };

  function showView(viewId) {
    $$('.view').forEach(v => v.classList.remove('active'));
    const view = $(`#${viewId}`);
    if (view) view.classList.add('active');
  }

  /** Map a user role to its default route path. */
  function roleToPath(role) {
    return ROUTES['/' + role] ? '/' + role : '/client';
  }

  /**
   * Navigate to a path via history.pushState.
   * This is the primary way to change routes programmatically.
   */
  function navigateTo(path) {
    // If not authenticated, always go to /login
    if (!currentUser) path = '/login';

    history.pushState(null, '', path);
    handleRoute();
  }

  /**
   * Core route resolver — reads location.pathname and activates
   * the correct view. Enforces auth + role guards.
   * Supports dynamic routes: /orders/:id
   */

  /** Pattern for dynamic order route: /orders/<uuid-or-id> */
  const ORDER_ROUTE_RE = /^\/orders\/([a-zA-Z0-9_-]+)$/;

  function handleRoute() {
    const path = location.pathname;
    const route = ROUTES[path];

    // ── 1. Not authenticated ────────────────────────────
    if (!currentUser) {
      // Allow /login; everything else redirects to /login
      if (route && route.requiredRole === null) {
        $('#app-shell').classList.add('hidden');
        showView(route.viewId);
        return;
      }
      $('#app-shell').classList.add('hidden');
      showView('view-login');
      if (path !== '/login') {
        history.replaceState(null, '', '/login');
      }
      return;
    }

    // ── 2. Authenticated user on /login (or root /) ─────
    if (path === '/login' || path === '/') {
      const target = roleToPath(currentUser.role);
      history.replaceState(null, '', target);
      handleRoute();
      return;
    }

    // ── 3. Dynamic route: /orders/:id ───────────────────
    const orderMatch = ORDER_ROUTE_RE.exec(path);
    if (orderMatch) {
      const orderId = orderMatch[1];
      // Show the user's dashboard behind the modal
      const dashPath = roleToPath(currentUser.role);
      const dashRoute = ROUTES[dashPath];
      $('#app-shell').classList.remove('hidden');
      $('#nav-user-name').textContent = currentUser.name;
      $('#nav-user-role').textContent = currentUser.role;
      showView(dashRoute.viewId);
      if (dashRoute.loader) dashRoute.loader();
      connectWebSocket();
      // Open order modal
      viewOrder(orderId).catch(() => {
        showToast('error', 'Invalid Order', `Order "${shortId(orderId)}" could not be found.`);
        history.replaceState(null, '', dashPath);
      });
      return;
    }

    // ── 4. Unknown route → role dashboard ───────────────
    if (!route) {
      const target = roleToPath(currentUser.role);
      history.replaceState(null, '', target);
      handleRoute();
      return;
    }

    // ── 5. Role guard ───────────────────────────────────
    if (route.requiredRole && route.requiredRole !== currentUser.role) {
      showToast('warning', 'Access Denied',
        `The ${path} dashboard requires the "${route.requiredRole}" role.`);
      const target = roleToPath(currentUser.role);
      history.replaceState(null, '', target);
      handleRoute();
      return;
    }

    // ── 6. Activate view ────────────────────────────────
    $('#app-shell').classList.remove('hidden');
    $('#nav-user-name').textContent = currentUser.name;
    $('#nav-user-role').textContent = currentUser.role;

    showView(route.viewId);
    if (route.loader) route.loader();

    // Connect WebSocket
    connectWebSocket();

    // Start polling for updates
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(() => {
      if (currentUser.role === 'client') loadOrders();
      else if (currentUser.role === 'driver') loadDriverOrders();
      else loadAdminOrders();
    }, 10000);
  }

  // ── WebSocket ─────────────────────────────────────────
  function connectWebSocket() {
    if (ws) ws.close();
    const wsUrl = `${WS_BASE}/ws/tracking/${currentUser.username}`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        $('#ws-status').classList.remove('disconnected');
        $('#ws-status').title = 'WebSocket connected';
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWsMessage(data);
        } catch (e) { /* ignore non-JSON */ }
      };

      ws.onclose = () => {
        $('#ws-status').classList.add('disconnected');
        $('#ws-status').title = 'WebSocket disconnected';
        // Reconnect after 5s
        setTimeout(() => {
          if (currentUser) connectWebSocket();
        }, 5000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      console.warn('WebSocket connection failed:', e);
    }
  }

  function handleWsMessage(data) {
    if (data.type === 'order_update') {
      showToast('info', 'Order Update', `Order ${shortId(data.order_id)} → ${formatStatus(data.status)}`);
      // Refresh order list
      if (currentUser.role === 'client') loadOrders();
      else if (currentUser.role === 'driver') loadDriverOrders();
      else loadAdminOrders();
    }
  }

  // ── Client Dashboard ──────────────────────────────────
  async function loadClientDashboard() {
    await loadOrders();
  }

  async function loadOrders(statusFilter = '') {
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      params.set('limit', '100');

      const data = await api('GET', `/api/orders?${params}`);
      orders = data.orders || [];
      renderOrders(orders);
      updateClientStats(orders);
    } catch (e) {
      console.error('Failed to load orders:', e);
    }
  }

  function updateClientStats(orderList) {
    const total = orderList.length;
    const delivered = orderList.filter(o => o.status === 'DELIVERED').length;
    const inTransit = orderList.filter(o => o.status === 'IN_TRANSIT').length;
    const inProgress = orderList.filter(o =>
      !['DELIVERED', 'FAILED', 'CANCELLED'].includes(o.status)
    ).length;

    $('#stat-total').textContent = total;
    $('#stat-delivered').textContent = delivered;
    $('#stat-in-progress').textContent = inProgress;
    $('#stat-in-transit').textContent = inTransit;
  }

  function renderOrders(orderList) {
    const tbody = $('#orders-tbody');
    const empty = $('#orders-empty');

    if (!orderList.length) {
      tbody.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }

    empty.classList.add('hidden');
    tbody.innerHTML = orderList.map(order => `
      <tr>
        <td><span class="order-id">${shortId(order.id)}</span></td>
        <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
        <td>${truncate(order.pickup_address, 25)}</td>
        <td>${truncate(order.delivery_address, 25)}</td>
        <td class="text-muted text-sm">${formatTime(order.created_at)}</td>
        <td class="cell-actions">
          <a href="/orders/${order.id}" data-link class="btn btn-sm btn-secondary">View</a>
        </td>
      </tr>
    `).join('');
  }

  async function createOrder(formData) {
    const btn = $('#create-order-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Creating...';

    try {
      const order = await api('POST', '/api/orders', {
        pickup_address: formData.pickup_address,
        delivery_address: formData.delivery_address,
        package_details: {
          weight: parseFloat(formData.weight) || 1.0,
          type: formData.type,
          description: formData.description,
        },
      });

      showToast('success', 'Order Created', `Order ${shortId(order.id)} submitted!`);
      $('#create-order-form').reset();
      await loadOrders();
    } catch (e) {
      showToast('error', 'Creation Failed', e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="ph ph-rocket-launch"></i> Create Order';
    }
  }

  // ── Driver Dashboard ──────────────────────────────────
  async function loadDriverDashboard() {
    await loadDriverOrders();
  }

  async function loadDriverOrders() {
    try {
      const data = await api('GET', '/api/orders?limit=100');
      const allOrders = data.orders || [];
      // Show orders that are READY or IN_TRANSIT (assigned to drivers)
      const driverOrders = allOrders.filter(o =>
        ['READY', 'IN_TRANSIT', 'ROUTE_OPTIMIZED', 'DELIVERED', 'FAILED'].includes(o.status)
      );

      renderDriverOrders(driverOrders);
      updateDriverStats(driverOrders);
    } catch (e) {
      console.error('Failed to load driver orders:', e);
    }
  }

  function updateDriverStats(orderList) {
    const assigned = orderList.filter(o => ['READY', 'ROUTE_OPTIMIZED'].includes(o.status)).length;
    const inTransit = orderList.filter(o => o.status === 'IN_TRANSIT').length;
    const delivered = orderList.filter(o => o.status === 'DELIVERED').length;

    $('#driver-stat-assigned').textContent = assigned;
    $('#driver-stat-transit').textContent = inTransit;
    $('#driver-stat-delivered').textContent = delivered;
  }

  function renderDriverOrders(orderList) {
    const tbody = $('#driver-orders-tbody');
    const empty = $('#driver-orders-empty');

    if (!orderList.length) {
      tbody.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }

    empty.classList.add('hidden');
    tbody.innerHTML = orderList.map(order => {
      const actions = getDriverActions(order);
      return `
        <tr>
          <td><span class="order-id">${shortId(order.id)}</span></td>
          <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
          <td>${truncate(order.pickup_address, 20)}</td>
          <td>${truncate(order.delivery_address, 20)}</td>
          <td class="cell-actions">${actions}</td>
        </tr>
      `;
    }).join('');
  }

  function getDriverActions(order) {
    if (order.status === 'READY' || order.status === 'ROUTE_OPTIMIZED') {
      return `<button class="btn btn-sm btn-primary" data-action="driver-status" data-order-id="${order.id}" data-status="IN_TRANSIT"><i class="ph ph-truck"></i> Start</button>`;
    }
    if (order.status === 'IN_TRANSIT') {
      return `
        <button class="btn btn-sm btn-success" data-action="driver-status" data-order-id="${order.id}" data-status="DELIVERED"><i class="ph ph-check-circle"></i> Deliver</button>
        <button class="btn btn-sm btn-danger" data-action="driver-status" data-order-id="${order.id}" data-status="FAILED"><i class="ph ph-x-circle"></i> Fail</button>
      `;
    }
    return `<span class="text-muted text-sm">${formatStatus(order.status)}</span>`;
  }

  async function driverAction(orderId, newStatus) {
    try {
      await api('PATCH', `/api/orders/${orderId}/status`, { status: newStatus });
      showToast('success', 'Status Updated', `Order → ${formatStatus(newStatus)}`);
      await loadDriverOrders();
    } catch (e) {
      showToast('error', 'Update Failed', e.message);
    }
  }

  // ── Admin Dashboard ───────────────────────────────────
  async function loadAdminDashboard() {
    await loadAdminOrders();
  }

  async function loadAdminOrders(statusFilter = '') {
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      params.set('limit', '200');

      const data = await api('GET', `/api/orders?${params}`);
      const allOrders = data.orders || [];
      renderAdminOrders(allOrders);
      updateAdminStats(allOrders);
    } catch (e) {
      console.error('Failed to load admin orders:', e);
    }
  }

  function updateAdminStats(orderList) {
    const total = orderList.length;
    const delivered = orderList.filter(o => o.status === 'DELIVERED').length;
    const processing = orderList.filter(o =>
      !['DELIVERED', 'FAILED', 'CANCELLED'].includes(o.status)
    ).length;
    const failed = orderList.filter(o => o.status === 'FAILED').length;

    $('#admin-stat-total').textContent = total;
    $('#admin-stat-delivered').textContent = delivered;
    $('#admin-stat-processing').textContent = processing;
    $('#admin-stat-failed').textContent = failed;
  }

  function renderAdminOrders(orderList) {
    const tbody = $('#admin-orders-tbody');
    const empty = $('#admin-orders-empty');

    if (!orderList.length) {
      tbody.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }

    empty.classList.add('hidden');
    tbody.innerHTML = orderList.map(order => `
      <tr>
        <td><span class="order-id">${shortId(order.id)}</span></td>
        <td class="text-sm">${order.client_id}</td>
        <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
        <td>${truncate(order.pickup_address, 20)}</td>
        <td>${truncate(order.delivery_address, 20)}</td>
        <td class="text-muted text-sm">${formatTime(order.created_at)}</td>
        <td class="cell-actions">
          <a href="/orders/${order.id}" data-link class="btn btn-sm btn-secondary">View</a>
        </td>
      </tr>
    `).join('');
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
        <label>Order ID</label>
        <span class="order-id">${order.id}</span>
      </div>
      <div class="detail-item">
        <label>Status</label>
        <span class="status-badge status-${order.status}">${formatStatus(order.status)}</span>
      </div>
      <div class="detail-item">
        <label>Client</label>
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
      ${order.driver_id ? `
        <div class="detail-item">
          <label>Driver</label>
          <span>${order.driver_id}</span>
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
    // If URL is still on a deep-link order route, go back to dashboard
    if (ORDER_ROUTE_RE.test(location.pathname) && currentUser) {
      history.replaceState(null, '', roleToPath(currentUser.role));
    }
  }

  // ── Toast Notifications ───────────────────────────────
  function showToast(type, title, message) {
    const container = $('#toast-container');
    const icons = { success: '<i class="ph ph-check-circle"></i>', info: 'ℹ️', warning: '<i class="ph ph-warning"></i>', error: '<i class="ph ph-x-circle"></i>' };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
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

  // ── Event Handlers ────────────────────────────────────
  function init() {
    // Login form
    $('#login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = $('#login-error');
      errEl.classList.remove('visible');

      const username = $('#login-username').value.trim();
      const password = $('#login-password').value;

      if (!username || !password) return;

      const btn = $('#login-btn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Signing in...';

      try {
        await login(username, password);
        navigateTo('/' + currentUser.role);
      } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.add('visible');
      } finally {
        btn.disabled = false;
        btn.innerHTML = 'Sign In';
      }
    });

    // Demo account chips
    $$('.demo-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        $('#login-username').value = chip.dataset.user;
        $('#login-password').value = chip.dataset.pass;
      });
    });

    // Logout
    $('#logout-btn').addEventListener('click', () => {
      clearSession();
      navigateTo('/login');
    });

    // Create order form
    $('#create-order-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      await createOrder({
        pickup_address: $('#pickup-address').value,
        delivery_address: $('#delivery-address').value,
        weight: $('#pkg-weight').value,
        type: $('#pkg-type').value,
        description: $('#pkg-description').value,
      });
    });

    // Filter (client)
    $('#filter-status').addEventListener('change', (e) => {
      loadOrders(e.target.value);
    });

    // Filter (admin)
    $('#admin-filter-status').addEventListener('change', (e) => {
      loadAdminOrders(e.target.value);
    });

    // Refresh buttons
    $('#refresh-orders-btn').addEventListener('click', () => loadOrders());
    $('#refresh-driver-btn').addEventListener('click', () => loadDriverOrders());
    $('#refresh-admin-btn').addEventListener('click', () => loadAdminOrders());

    // Modal close
    $('#modal-close').addEventListener('click', closeModal);
    $('#order-modal').addEventListener('click', (e) => {
      if (e.target === $('#order-modal')) closeModal();
    });

    // Keyboard
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });

    // ── Delegated click handler (replaces inline onclick) ──
    document.addEventListener('click', (e) => {
      // [data-link] — client-side navigation (e.g. <a href="/orders/..." data-link>)
      const link = e.target.closest('[data-link]');
      if (link) {
        e.preventDefault();
        navigateTo(link.getAttribute('href'));
        return;
      }

      // [data-action="driver-status"] — driver order actions
      const actionEl = e.target.closest('[data-action="driver-status"]');
      if (actionEl) {
        const orderId = actionEl.dataset.orderId;
        const status = actionEl.dataset.status;
        if (orderId && status) driverAction(orderId, status);
        return;
      }
    });

    // Listen for browser back / forward
    window.addEventListener('popstate', handleRoute);

    // Check existing session and resolve current URL
    loadSession();
    handleRoute();
  }

  // No more window.SwiftTrack needed — all actions use event delegation.

  // ── Boot ──────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
